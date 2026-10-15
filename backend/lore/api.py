"""HTTP API for the web UI.

    uv run uvicorn lore.api:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import agent, config, db, llm, tools
from .ingest import pipeline
from .tools import Ctx

log = logging.getLogger("lore")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Lore - company brain on FalkorDB", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
_ingest_lock = threading.Lock()


def _tenant(t: str | None) -> str:
    return t or config.DEFAULT_TENANT


def _with_ctx(tenant: str, as_of: str | None, fn, **kw) -> dict:
    ctx = Ctx(tenant=tenant, as_of=as_of or None)
    result = fn(ctx, **kw)
    details = {d["id"]: d for d in tools.source_details(tenant, list(ctx.registry))}
    return {
        "result": result,
        "citations": [{"sid": sid, **details[src]} for src, sid in ctx.registry.items() if src in details],
        "subgraph": {"nodes": list(ctx.nodes.values()), "edges": list(ctx.edges.values())},
    }


@app.on_event("startup")
def _startup() -> None:
    if os.getenv("LORE_SEED_ON_START") != "1":
        return
    # seed every tenant that has an export on disk and isn't in FalkorDB yet
    for d in sorted(config.DATA_DIR.glob("*/raw")):
        t = d.parent.name
        try:
            if db.query(t, "MATCH (m:Meta) RETURN m.company AS c"):
                continue
        except Exception:
            pass
        log.info("seeding tenant '%s' from %s", t, d)
        pipeline.seed(t, d)


# --------------------------------------------------------------------------------------
@app.get("/api/health")
def health():
    db.client().connection.ping()
    return {"ok": True, "llm": llm.available(), **llm.status()}


@app.get("/api/tenants")
def tenants():
    return {"tenants": db.list_tenants(), "default": config.DEFAULT_TENANT}


@app.get("/api/meta")
def meta(tenant: str | None = None):
    t = _tenant(tenant)
    m = db.query(t, "MATCH (m:Meta) RETURN m.company AS company, m.now AS now", read_only=True)
    if not m:
        raise HTTPException(404, f"tenant '{t}' is not seeded")
    rng = db.query(t, "MATCH (s:Source) RETURN min(s.ts) AS first, max(s.ts) AS last", read_only=True)[0]
    return {**m[0], **rng, "stats": pipeline.stats(t), "llm": llm.available(), **llm.status()}


class AskBody(BaseModel):
    question: str
    as_of: str | None = None
    tenant: str | None = None
    history: list[dict] = []
    offline: bool = False


@app.post("/api/ask")
def ask(body: AskBody):
    return agent.ask(_tenant(body.tenant), body.question, as_of=body.as_of or None, history=body.history,
                     force_offline=body.offline)


@app.get("/api/ownership")
def ownership(entity: str, as_of: str | None = None, tenant: str | None = None):
    return _with_ctx(_tenant(tenant), as_of, tools.who_owns, entity=entity)


@app.get("/api/experts")
def experts(subject: str, tenant: str | None = None):
    return _with_ctx(_tenant(tenant), None, tools.find_experts, subject=subject, k=8)


@app.get("/api/bus-factor")
def bus_factor(tenant: str | None = None):
    return _with_ctx(_tenant(tenant), None, tools.bus_factor)


@app.get("/api/decisions")
def decisions(as_of: str | None = None, tenant: str | None = None):
    return _with_ctx(_tenant(tenant), as_of, tools.list_decisions)


@app.get("/api/decision")
def decision(query: str, as_of: str | None = None, tenant: str | None = None):
    return _with_ctx(_tenant(tenant), as_of, tools.trace_decision, query=query)


@app.get("/api/freshness")
def freshness(tenant: str | None = None):
    return _with_ctx(_tenant(tenant), None, tools.freshness)


@app.get("/api/changes")
def changes(since: str, as_of: str | None = None, entity: str | None = None, tenant: str | None = None):
    return _with_ctx(_tenant(tenant), as_of, tools.whats_changed, since=since, entity=entity)


@app.get("/api/profile")
def profile(name: str, as_of: str | None = None, tenant: str | None = None):
    return _with_ctx(_tenant(tenant), as_of, tools.profile, name=name)


@app.get("/api/people")
def people(tenant: str | None = None):
    t = _tenant(tenant)
    rows = db.query(t, """MATCH (p:Person) OPTIONAL MATCH (p)-[:MEMBER_OF]->(tm:Team)
        OPTIONAL MATCH (p)-[e:EXPERT_IN]->(x) WITH p, tm, e, x ORDER BY e.score DESC
        RETURN p.id AS id, p.name AS name, p.role AS role, p.active AS active, p.left_at AS left_at, tm.name AS team,
               p.influence AS influence, p.broker AS broker, p.community AS community,
               collect(coalesce(x.name, x.id))[0..4] AS knows
        ORDER BY influence DESC""", read_only=True)
    return {"people": rows}


@app.get("/api/systems")
def systems(as_of: str | None = None, tenant: str | None = None):
    t = _tenant(tenant)
    ctx = Ctx(tenant=t, as_of=as_of or None)
    risk = {s["system"]: s for s in tools.bus_factor(ctx)["systems"]}
    rows = db.query(t, """MATCH (s:System) OPTIONAL MATCH (o)-[r:OWNS]->(s) WHERE r.since_t <= $t AND coalesce(r.until_t, $far) > $t
        OPTIONAL MATCH (pr:Project)-[:USES]->(s)
        RETURN s.id AS id, s.kind AS kind, collect(DISTINCT o.name)[0] AS owner, collect(DISTINCT pr.name) AS projects
        ORDER BY id""", {"t": ctx.t, "far": tools.OPEN_END}, read_only=True)
    for r in rows:
        r["risk"] = risk.get(r["id"], {}).get("risk")
        r["active_experts"] = risk.get(r["id"], {}).get("active_experts", [])
        r["top_expert"] = risk.get(r["id"], {}).get("top_expert")
        r["top_expert_active"] = risk.get(r["id"], {}).get("top_expert_active")
    return {"systems": rows}


@app.get("/api/graph/overview")
def graph_overview(as_of: str | None = None, tenant: str | None = None):
    """Organisation-level graph for the explorer: people, teams, systems, projects, decisions."""
    t = _tenant(tenant)
    ctx = Ctx(tenant=t, as_of=as_of or None)
    nodes = db.query(t, """MATCH (n) WHERE n:Person OR n:Team OR n:System OR n:Project OR n:Decision OR n:Topic
        RETURN n.id AS id, labels(n)[0] AS label, coalesce(n.name, n.title, n.id) AS name, n.active AS active,
               n.influence AS influence, n.community AS community, n.status AS status, n.decided_t AS decided_t""", read_only=True)
    nodes = [n for n in nodes if n["label"] != "Decision" or (n["decided_t"] or 0) <= ctx.t]
    ids = {n["id"] for n in nodes}
    edges = db.query(t, """MATCH (a)-[r]->(b)
        WHERE type(r) IN ['MEMBER_OF', 'USES', 'LED_BY', 'AFFECTS', 'SUPERSEDES', 'PROPOSED_BY', 'WORKS_CLOSELY_WITH']
           OR (type(r) = 'OWNS' AND r.since_t <= $t AND coalesce(r.until_t, $far) > $t)
           OR (type(r) = 'EXPERT_IN' AND r.score >= 2.5)
        RETURN a.id AS source, b.id AS target, type(r) AS type, r.score AS score""",
                     {"t": ctx.t, "far": tools.OPEN_END}, read_only=True)
    edges = [e for e in edges if e["source"] in ids and e["target"] in ids]
    return {"nodes": nodes, "edges": edges}


class MessageBody(BaseModel):
    channel: str
    author: str
    text: str
    ts: str | None = None
    tenant: str | None = None


@app.post("/api/ingest/message")
def ingest_message(body: MessageBody):
    t = _tenant(body.tenant)
    who = tools.index(t).resolve(body.author, ("Person",))
    if not who:
        raise HTTPException(400, f"unknown author '{body.author}'")
    with _ingest_lock:
        item = pipeline.new_message_item(t, body.channel.lstrip("#"), who[1], body.text, body.ts)
        res = pipeline.ingest_live(t, item)
    tools.invalidate_index()
    return res


@app.get("/api/actions")
def actions(tenant: str | None = None):
    return {"actions": tools.list_actions(Ctx(tenant=_tenant(tenant)))}


class ActionBody(BaseModel):
    kind: str  # ticket | doc_update | message
    title: str
    body: str = ""
    target: str | None = None
    tenant: str | None = None


@app.post("/api/actions")
def create_action(b: ActionBody):
    ctx = Ctx(tenant=_tenant(b.tenant))
    if b.kind == "doc_update":
        return tools.flag_stale_doc(ctx, document=b.target or b.title, reason=b.body)
    if b.kind == "message":
        return tools.draft_message(ctx, to=b.target or "", subject=b.title, body=b.body)
    return tools.create_ticket(ctx, title=b.title, description=b.body, system=b.target)


@app.get("/api/schema")
def schema_info(tenant: str | None = None):
    return pipeline.stats(_tenant(tenant))


@app.post("/api/reset")
def reset(tenant: str | None = None):
    if os.getenv("LORE_ALLOW_RESET", "1") != "1":
        raise HTTPException(403, "reset disabled")
    t = _tenant(tenant)
    src = config.DATA_DIR / t / "raw"
    if not src.exists():
        raise HTTPException(404, f"no export for tenant '{t}' at {src}")
    with _ingest_lock:
        st = pipeline.seed(t, src)
    tools.invalidate_index()
    return st


# --------------------------------------------------------------------------------------
# Serve the built frontend (single deployable)
_dist = Path(os.getenv("LORE_UI_DIST", config.ROOT / "frontend" / "dist"))
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = _dist / path
        return FileResponse(f if path and f.is_file() else _dist / "index.html")
