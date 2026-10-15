"""Golden-question evaluation: Lore (graph agent) vs. a vector-only RAG baseline over the same data.

    uv run python -m lore.evaluate                 # offline agent (deterministic, free)
    uv run python -m lore.evaluate --llm           # LLM agent (needs GROQ_API_KEY and/or OPENAI_API_KEY)

Metrics per question
  fact      every expected fact string appears in the answer
  evidence  at least one expected source is cited (Lore) / retrieved in the top-k (baseline)
  current   for questions whose answer changed over time: the current fact is stated before the stale one
            (or the stale one is absent). This is what a reader would take away as "the answer".

The baseline is the classic RAG pipeline without a graph: embed the question, take the top-k most
similar chunks/messages/tickets, and return them in rank order (we score the retrieved context, which
is an upper bound on what an LLM could answer from it). It has no notion of time, so as-of questions
use the same unfiltered retrieval.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import agent, config, db
from .embed import embed_one

GOLDEN = config.ROOT / "eval" / "golden.json"
OUT = config.ROOT / "eval"


def baseline(tenant: str, question: str, k: int = 8) -> tuple[str, list[str]]:
    rows = db.query(tenant, """CALL db.idx.vector.queryNodes('Source', 'embedding', $k, vecf32($v)) YIELD node, score
        RETURN node.id AS id, node.title AS title, node.text AS text ORDER BY score""",
                    {"k": k, "v": embed_one(question)}, read_only=True)
    context = "\n".join(f"{r['title']}: {r['text']}" for r in rows)
    return context, [r["id"] for r in rows]


def score(item: dict, answer: str, sources: list[str]) -> dict:
    low = answer.lower()
    fact = all(f.lower() in low for f in item.get("facts", []))
    evidence = None
    if item.get("sources_any"):
        evidence = any(s in sources for s in item["sources_any"])
    current = None
    if item.get("current"):
        c, s = low.find(item["current"].lower()), low.find(item["stale"].lower())
        current = c >= 0 and (s < 0 or c < s)
    return {"fact": fact, "evidence": evidence, "current": current}


def run(tenant: str, use_llm: bool) -> dict:
    items = json.loads(GOLDEN.read_text(encoding="utf-8"))
    rows = []
    for it in items:
        res = agent.ask(tenant, it["q"], as_of=it.get("as_of"), force_offline=not use_llm)
        cited = [c["id"] for c in res["citations"] if c["used"]]
        lore = score(it, res["answer"], cited)
        ctx, ids = baseline(tenant, it["q"])
        base = score(it, ctx, ids)
        rows.append({"id": it["id"], "bucket": it["bucket"], "q": it["q"], "as_of": it.get("as_of"),
                     "lore": lore, "baseline": base, "tools": [s["tool"] for s in res["steps"]], "mode": res["mode"]})

    def rate(system: str, metric: str, bucket: str | None = None) -> tuple[int, int]:
        vals = [r[system][metric] for r in rows if r[system][metric] is not None and (bucket is None or r["bucket"] == bucket)]
        return sum(vals), len(vals)

    summary = {}
    for m in ("fact", "evidence", "current"):
        summary[m] = {s: rate(s, m) for s in ("lore", "baseline")}
    buckets = sorted({r["bucket"] for r in rows})
    by_bucket = {b: {s: rate(s, "fact", b) for s in ("lore", "baseline")} for b in buckets}
    return {"rows": rows, "summary": summary, "by_bucket": by_bucket, "mode": rows[0]["mode"] if rows else None}


def pct(t: tuple[int, int]) -> str:
    return f"{t[0]}/{t[1]} ({100 * t[0] / t[1]:.0f}%)" if t[1] else "n/a"


def write_report(res: dict) -> str:
    s, b = res["summary"], res["by_bucket"]
    lines = [
        "# Evaluation: Lore vs. vector-only RAG",
        "",
        f"Agent mode: **{res['mode']}**. {len(res['rows'])} golden questions over the Northwind Labs dataset "
        "(`eval/golden.json`). Reproduce with `uv run python -m lore.evaluate`.",
        "",
        "| Metric | Lore (graph) | Vector-only RAG |",
        "|---|---|---|",
        f"| Answer contains the expected facts | {pct(s['fact']['lore'])} | {pct(s['fact']['baseline'])} |",
        f"| Expected source cited / retrieved | {pct(s['evidence']['lore'])} | {pct(s['evidence']['baseline'])} |",
        f"| Gives the *current* fact first (facts that changed) | {pct(s['current']['lore'])} | {pct(s['current']['baseline'])} |",
        "",
        "## Expected facts by question type",
        "",
        "| Bucket | Lore | Vector-only RAG |",
        "|---|---|---|",
        *[f"| {k} | {pct(v['lore'])} | {pct(v['baseline'])} |" for k, v in b.items()],
        "",
        "The baseline is scored on its whole top-8 retrieved context (an upper bound for an LLM answering from it), "
        "and it has no notion of time, so it is not given the as-of date.",
        "",
        "## Per question",
        "",
        "| id | question | as of | tools | Lore fact / evidence / current | RAG fact / evidence / current |",
        "|---|---|---|---|---|---|",
    ]
    mark = lambda v: "-" if v is None else ("✅" if v else "❌")  # noqa: E731
    for r in res["rows"]:
        lo, ba = r["lore"], r["baseline"]
        lines.append(f"| {r['id']} | {r['q']} | {(r['as_of'] or '')[:10]} | {', '.join(r['tools'])} | "
                     f"{mark(lo['fact'])} {mark(lo['evidence'])} {mark(lo['current'])} | "
                     f"{mark(ba['fact'])} {mark(ba['evidence'])} {mark(ba['current'])} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", default=config.DEFAULT_TENANT)
    ap.add_argument("--llm", action="store_true")
    a = ap.parse_args()
    res = run(a.tenant, a.llm)
    md = write_report(res)
    name = "results_llm" if a.llm else "results"
    (OUT / f"{name}.md").write_text(md, encoding="utf-8")
    (OUT / f"{name}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
