"""The Lore agent.

Two modes share the same graph tools and the same citation guarantee:
  * llm     - an LLM chooses and chains tools (tool-use loop), then writes the answer. Groq is the
              primary provider and OpenAI the fallback (see llm.py).
  * offline - a deterministic router picks tools from the question; used when no API key is set,
              and as a fallback if every provider fails.

Citation guarantee: tools register every piece of evidence and return labels like [S3]. After the
answer is written, every [S#] is checked against this turn's registry; unknown labels are removed
and reported, so an answer can never cite a source the agent did not actually retrieve.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta

from . import llm, tools
from .tools import Ctx, d10

log = logging.getLogger(__name__)

CITE_RX = re.compile(r"\[(S\d+)\]")

TOOL_SPECS = [
    {"name": "search", "description": "Hybrid semantic + keyword search over all company docs, tickets, chat and meeting notes. Use for open questions or to find context.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "k": {"type": "integer", "description": "results, default 8"}}, "required": ["query"]}},
    {"name": "who_owns", "description": "Current owner of a system (or of a project's systems, or which systems a team owns), with ownership history, evidence, best contacts and documents that are now out of date.",
     "input_schema": {"type": "object", "properties": {"entity": {"type": "string"}}, "required": ["entity"]}},
    {"name": "find_experts", "description": "People who know a system or topic best, ranked by time-decayed contributions, including whether they still work here.",
     "input_schema": {"type": "object", "properties": {"subject": {"type": "string"}, "k": {"type": "integer"}}, "required": ["subject"]}},
    {"name": "bus_factor", "description": "Knowledge concentration risk for one system or all systems: active experts and whether the top expert left.",
     "input_schema": {"type": "object", "properties": {"system": {"type": "string", "description": "omit for all systems"}}}},
    {"name": "trace_decision", "description": "Find the decision behind a question and trace it to where it was made, who proposed/approved it, evidence, implementing tickets, and every earlier/later decision that replaced it.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "whats_changed", "description": "Ownership moves, new or reversed decisions and departures since a date (YYYY-MM-DD), optionally for one system/topic/team.",
     "input_schema": {"type": "object", "properties": {"since": {"type": "string"}, "entity": {"type": "string"}}, "required": ["since"]}},
    {"name": "freshness", "description": "Documents that are out of date, with the newer evidence that contradicts them.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "connect", "description": "Shortest path between two people, teams, systems, projects or topics in the company graph.",
     "input_schema": {"type": "object", "properties": {"a": {"type": "string"}, "b": {"type": "string"}}, "required": ["a", "b"]}},
    {"name": "profile", "description": "Everything known about one person, team, system or project.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "onboarding_brief", "description": "Gather everything needed for an onboarding brief on a project or system.",
     "input_schema": {"type": "object", "properties": {"subject": {"type": "string"}}, "required": ["subject"]}},
    {"name": "cypher", "description": "Read-only Cypher against the graph. Labels: Person, Team, System, Project, Topic, Document, Chunk, Message, Ticket, Comment, Meeting, Decision, Claim. Use only when other tools can't answer.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "create_ticket", "description": "Open a follow-up ticket. Only when the user asks you to take action.",
     "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "system": {"type": "string"}, "assignee": {"type": "string"}}, "required": ["title", "description"]}},
    {"name": "flag_stale_doc", "description": "Flag a document as out of date and notify its author. Only when the user asks.",
     "input_schema": {"type": "object", "properties": {"document": {"type": "string"}, "reason": {"type": "string"}}, "required": ["document", "reason"]}},
    {"name": "draft_message", "description": "Draft a message to a person or team (e.g. to ask an expert). Only when the user asks.",
     "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["to", "subject", "body"]}},
]

SYSTEM_PROMPT = """You are Lore, the company brain for {company}. You answer questions about how the company works
(people, teams, systems, projects, documents, decisions) using only the company knowledge graph, through your tools.

Today is {today}.{as_of_line}

How to answer:
- Use the tools first. Chain them when a question needs several hops (e.g. owner -> experts -> recent decisions).
- Tool results contain citation labels like [S3]. Put the matching labels right after each factual sentence.
  Only use labels that appeared in tool results. Never make up a label. If the tools found nothing, say so.
- Prefer the current state of things. If a document is out of date, or a fact changed, say what changed and when.
- If the best expert has left the company, say so and name who is still here.
- Be brief: a direct answer first, then the supporting details. Plain sentences, short bullet lists at most.
- Only use create_ticket, flag_stale_doc or draft_message when the user asks you to do something."""


def _company(tenant: str) -> tuple[str, str]:
    rows = tools.db.query(tenant, "MATCH (m:Meta) RETURN m.company AS c, m.now AS now", read_only=True)
    if rows:
        return rows[0]["c"], rows[0]["now"] or datetime.now().isoformat()
    return tenant, datetime.now().isoformat()


def run_tool(ctx: Ctx, name: str, args: dict) -> dict:
    fn = tools.REGISTRY.get(name)
    if not fn:
        return {"error": f"unknown tool {name}"}
    try:
        return fn(ctx, **args)
    except TypeError as e:
        return {"error": f"bad arguments for {name}: {e}"}
    except Exception as e:  # tool errors go back to the model / user, not crash the turn
        log.exception("tool %s failed", name)
        return {"error": f"{name} failed: {e}"}


def ask(tenant: str, question: str, as_of: str | None = None, history: list[dict] | None = None,
        force_offline: bool = False) -> dict:
    ctx = Ctx(tenant=tenant, as_of=as_of)
    steps: list[dict] = []
    mode = "offline"
    answer = None
    warnings: list[str] = []
    providers_used: list[str] = []
    if llm.available() and not force_offline:
        try:
            answer = _ask_llm(ctx, question, history or [], steps, providers_used)
            mode = "llm"
        except Exception as e:
            log.warning("LLM agent failed (%s); falling back to the offline agent", e)
            warnings.append("The LLM providers were unavailable; answered with the offline agent.")
            ctx = Ctx(tenant=tenant, as_of=as_of)
            steps = []
            providers_used = []
    if answer is None:
        answer = _ask_offline(ctx, question, steps)
    answer, bad = verify_citations(answer, ctx)
    if bad:
        warnings.append(f"Removed {len(bad)} citation(s) that did not match retrieved evidence: {', '.join(bad)}")
    used = list(dict.fromkeys(CITE_RX.findall(answer)))
    if ctx.registry and not used:
        warnings.append("The answer does not cite any source.")
    by_sid = {sid: sid_src for sid_src, sid in ctx.registry.items()}
    details = {d["id"]: d for d in tools.source_details(tenant, list(ctx.registry.keys()))}
    citations = []
    for sid in sorted(ctx.registry.values(), key=lambda s: int(s[1:])):
        d = details.get(by_sid[sid])
        if d:
            citations.append({"sid": sid, "used": sid in used, **d})
    stale_cited = tools.db.query(tenant, """MATCH (d:Document {stale:true})-[:HAS_CHUNK]->(c:Chunk) WHERE c.id IN $ids
        RETURN DISTINCT d.title AS title""", {"ids": [by_sid[s] for s in used if s in by_sid]}, read_only=True)
    for s in stale_cited:
        warnings.append(f"'{s['title']}' is cited but is out of date; newer evidence is preferred.")
    return {
        "question": question, "as_of": as_of, "answer": answer, "mode": mode,
        "provider": providers_used[-1] if providers_used else None, "citations": citations,
        "steps": steps, "warnings": warnings,
        "subgraph": {"nodes": list(ctx.nodes.values()), "edges": list(ctx.edges.values())},
    }


def verify_citations(answer: str, ctx: Ctx) -> tuple[str, list[str]]:
    valid = set(ctx.registry.values())
    bad = sorted({c for c in CITE_RX.findall(answer) if c not in valid})
    for b in bad:
        answer = answer.replace(f"[{b}]", "")
    return answer, bad


# --------------------------------------------------------------------------------------
# Claude mode
# --------------------------------------------------------------------------------------
OPENAI_TOOLS = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                  "parameters": t["input_schema"]}} for t in TOOL_SPECS]


def _ask_llm(ctx: Ctx, question: str, history: list[dict], steps: list[dict], used: list[str]) -> str:
    """Tool-use loop over the provider chain (Groq first, OpenAI on failure). `used` collects provider names."""
    company, now = _company(ctx.tenant)
    system = SYSTEM_PROMPT.format(
        company=company, today=d10(now),
        as_of_line=f"\nThe user is looking at the company AS OF {d10(ctx.as_of)}: tools already filter to that date; "
                   "answer as of that date." if ctx.as_of else "")
    messages: list[dict] = [{"role": "system", "content": system}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history[-6:] if m.get("content")]
    messages.append({"role": "user", "content": question})
    for _ in range(8):
        msg, provider = llm.chat(messages, tools=OPENAI_TOOLS, kind="agent", max_tokens=4000)
        if provider not in used:
            used.append(provider)
        calls = getattr(msg, "tool_calls", None) or []
        if not calls:
            return (msg.content or "").strip()
        messages.append(llm.assistant_message(msg))
        for c in calls:
            args = llm.parse_args(c.function.arguments)
            out = run_tool(ctx, c.function.name, args)
            steps.append({"tool": c.function.name, "input": args,
                          "summary": (out.get("summary") or out.get("error") or "")[:600]})
            messages.append({"role": "tool", "tool_call_id": c.id, "content": json.dumps(out, default=str)[:24000]})
    return "I ran out of steps before finishing. Here is what I found:\n" + "\n".join(s["summary"] for s in steps[-3:])


# --------------------------------------------------------------------------------------
# Offline (deterministic) mode
# --------------------------------------------------------------------------------------
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                      "august", "september", "october", "november", "december"], 1)}


def _since(question: str, ctx: Ctx) -> str:
    if m := re.search(r"(20\d\d-\d\d-\d\d)", question):
        return m.group(1)
    q = question.lower()
    for name, num in MONTHS.items():
        if name in q:
            return f"2026-{num:02d}-01"
    _, now = _company(ctx.tenant)
    base = datetime.fromisoformat(ctx.as_of or now)
    days = 90 if "quarter" in q else 7 if "week" in q else 30
    return (base - timedelta(days=days)).strftime("%Y-%m-%d")


def route(question: str) -> str:
    q = question.lower()
    rules = [
        ("action_ticket", r"\b(open|create|file|raise)\b.*\bticket\b"),
        ("action_message", r"\b(draft|write|send)\b.*\b(message|note|dm)\b"),
        ("action_flag", r"\bflag\b.*\b(doc|page|runbook|document)"),
        ("connect", r"\b(connected|connection|related|path) (to|between)\b|\bhow (is|are) .* (connected|related)\b"),
        ("whats_changed", r"\bwhat('s| has)? changed\b|\bwhat changed\b|\bwhat'?s new\b|\bchanges since\b"),
        ("onboarding_brief", r"\bonboard|\bbrief\b|\bnew to\b|\bget started\b"),
        ("bus_factor", r"\bbus factor\b|\bsingle point\b|\bknowledge risk\b|\bat risk\b|\brisk\b"),
        ("freshness", r"\bstale\b|\bout of date\b|\boutdated\b|\bwrong docs?\b"),
        ("who_owns", r"\bwho owns\b|\bowner\b|\bowned\b|\bresponsible for\b|\bwho maintains\b|\bescalat"),
        ("find_experts", r"\bwho knows\b|\bexpert|\bwho (should|can) i (ask|talk)|\bwho can help\b|\bask about\b"),
        ("trace_decision", r"\bwhy\b|\bdecid|\bdecision|\bpolicy\b|\bchose|\bchoose|\bfreeze\b|\ballowed\b|\bcan we\b|\bshould we\b"
                           r"|\bwho (approved|proposed|signed off)\b"),
        ("profile", r"\btell me about\b|\bwho is\b|\bwhat is\b|\bwhat does\b"),
    ]
    for name, rx in rules:
        if re.search(rx, q):
            return name
    return "search"


def _subject(ctx: Ctx, question: str, labels: tuple[str, ...]) -> str | None:
    for m in tools.index(ctx.tenant).find(question):
        if m.label in labels:
            return m.id
    return None


def _ask_offline(ctx: Ctx, question: str, steps: list[dict]) -> str:
    intent = route(question)

    def call(tool_name: str, **args) -> dict:
        out = run_tool(ctx, tool_name, args)
        steps.append({"tool": tool_name, "input": args, "summary": (out.get("summary") or out.get("error") or "")[:600]})
        return out

    if intent == "connect":
        ents = list(dict.fromkeys(m.id for m in tools.index(ctx.tenant).find(question) if m.label != "Topic"))
        if len(ents) >= 2:
            return call("connect", a=ents[0], b=ents[1])["summary"]
        intent = "search"
    if intent == "whats_changed":
        ent = _subject(ctx, question, ("System", "Topic", "Project", "Team"))
        return call("whats_changed", since=_since(question, ctx), entity=ent).get("summary", "")
    if intent == "onboarding_brief":
        subj = _subject(ctx, question, ("Project", "System"))
        if subj:
            return call("onboarding_brief", subject=subj)["summary"]
        intent = "search"
    if intent == "bus_factor":
        return call("bus_factor", system=_subject(ctx, question, ("System",)))["summary"]
    if intent == "freshness":
        return call("freshness")["summary"]
    if intent == "who_owns":
        subj = _subject(ctx, question, ("System", "Project", "Team"))
        if subj:
            return call("who_owns", entity=subj)["summary"]
        intent = "search"
    if intent == "find_experts":
        subj = _subject(ctx, question, ("System", "Topic")) or re.sub(r"(?i).*\b(about|on|knows|expert in|with)\b", "", question).strip(" ?")
        out = call("find_experts", subject=subj)
        return out["summary"]
    if intent == "trace_decision":
        out = call("trace_decision", query=question)
        if "error" not in out:
            return out["summary"]
        intent = "search"
    if intent == "profile":
        ents = [m for m in tools.index(ctx.tenant).find(question) if m.label != "Topic"]
        if ents:
            return call("profile", name=ents[0].id)["summary"]
        intent = "search"
    if intent == "action_ticket":
        subj = _subject(ctx, question, ("System",))
        title = re.sub(r"(?i)^.*\bticket\b\s*(to|for|about)?\s*", "", question).strip(" ?.") or question
        return call("create_ticket", title=title[:120], description=question, system=subj)["summary"]
    if intent == "action_message":
        who = _subject(ctx, question, ("Person", "Team")) or "the expert"
        return call("draft_message", to=who, subject=question[:80], body=question)["summary"]
    if intent == "action_flag":
        doc = re.sub(r"(?i)^.*\bflag\b\s*(the)?\s*", "", question).strip(" ?.")
        return call("flag_stale_doc", document=doc, reason=question)["summary"]
    out = call("search", query=question)
    if not out["results"]:
        return "I couldn't find anything about that in the company graph."
    return "Here is the most relevant evidence I found:\n" + out["summary"]
