"""Graph tools shared by the web agent, the offline agent and the MCP server.

Every tool works on a Ctx that
  * pins an optional as-of time (time travel: what did the company know / what was true then),
  * registers every piece of evidence it uses and hands back citation labels ([S1], [S2] ...),
  * records the subgraph it touched so the UI can draw the reasoning path.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from functools import lru_cache

from . import db
from .embed import embed_one
from .entities import EntityIndex
from .models import from_epoch, to_epoch

FAR_FUTURE = 4_102_444_800  # 2100-01-01: 'now' when no as-of date is set
OPEN_END = 2 * FAR_FUTURE  # end of an interval that hasn't ended


# --------------------------------------------------------------------------------------
# Context
# --------------------------------------------------------------------------------------
@dataclass
class Ctx:
    tenant: str
    as_of: str | None = None
    registry: dict[str, str] = field(default_factory=dict)  # source id -> "S1"
    nodes: dict[str, dict] = field(default_factory=dict)
    edges: dict[tuple, dict] = field(default_factory=dict)

    @property
    def t(self) -> int:
        return to_epoch(self.as_of) if self.as_of else FAR_FUTURE

    def sid(self, source_id: str) -> str:
        if source_id not in self.registry:
            self.registry[source_id] = f"S{len(self.registry) + 1}"
        return self.registry[source_id]

    def cite(self, *ids) -> str:
        flat = [i for x in ids for i in (x if isinstance(x, (list, tuple)) else [x]) if i]
        return "".join(f"[{self.sid(i)}]" for i in dict.fromkeys(flat))

    def node(self, nid: str, label: str, name: str, **props) -> None:
        if nid and nid not in self.nodes:
            self.nodes[nid] = {"id": nid, "label": label, "name": name, **props}
        elif nid:
            self.nodes[nid].update({k: v for k, v in props.items() if v is not None})

    def edge(self, a: str, b: str, rel: str, **props) -> None:
        if a and b:
            self.edges[(a, b, rel)] = {"source": a, "target": b, "type": rel, **props}

    def q(self, cypher: str, **params) -> list[dict]:
        return db.query(self.tenant, cypher, params, read_only=True)

    def w(self, cypher: str, **params) -> list[dict]:
        return db.query(self.tenant, cypher, params)


@lru_cache(maxsize=16)
def _index(tenant: str, _version: int) -> EntityIndex:
    from .ingest.pipeline import org_from_graph

    return EntityIndex(org_from_graph(tenant))


_index_version = {"v": 0}


def invalidate_index() -> None:
    _index_version["v"] += 1


def index(tenant: str) -> EntityIndex:
    return _index(tenant, _index_version["v"])


def resolve(ctx: Ctx, name: str, labels: tuple[str, ...] | None = None) -> tuple[str, str] | None:
    return index(ctx.tenant).resolve(name, labels)


def display(ctx: Ctx, label: str, eid: str) -> str:
    return index(ctx.tenant).display(label, eid)


def d10(ts: str | None) -> str:
    return (ts or "")[:10]


def source_details(tenant: str, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    rows = db.query(tenant, """MATCH (s:Source) WHERE s.id IN $ids
        OPTIONAL MATCH (a:Person {id: s.author_id})
        RETURN s.id AS id, s.kind AS kind, s.title AS title, s.text AS text, s.url AS url, s.ts AS ts,
               s.author_id AS author, a.name AS author_name""", {"ids": ids}, read_only=True)
    by = {r["id"]: r for r in rows}
    out = []
    for i in ids:
        r = by.get(i)
        if r:
            txt = r.pop("text") or ""
            r["snippet"] = txt if len(txt) <= 280 else txt[:277] + "..."
            out.append(r)
    return out


def _source_nodes(ctx: Ctx, ids: list[str]) -> None:
    for s in source_details(ctx.tenant, ids):
        ctx.node(s["id"], s["kind"].capitalize(), s["title"], ts=s["ts"], url=s["url"], sid=ctx.sid(s["id"]))


# --------------------------------------------------------------------------------------
# search
# --------------------------------------------------------------------------------------
KIND_BOOST = {"chunk": 1.5, "meeting": 1.25, "ticket": 1.1, "comment": 1.0, "message": 1.0}
SYSTEM_WORDS = [r"[a-z]+-(?:service|gateway|engine|web|pipeline|app|api)"]
STOP = set("who what when where why how does did do is are was the a an of to for on in about with and or our we "
           "us me my you your it its this that there which own owns owned knows know should ask".split())


def search(ctx: Ctx, query: str, k: int = 8, kinds: list[str] | None = None) -> dict:
    """Hybrid retrieval: vector (semantic) + full-text (keyword), fused with reciprocal rank,
    filtered to what existed at the as-of time, then expanded one hop to mentioned entities."""
    vec = embed_one(query)
    vhits = ctx.q("""CALL db.idx.vector.queryNodes('Source', 'embedding', $k, vecf32($v)) YIELD node, score
        WHERE node.t <= $t RETURN node.id AS id, node.kind AS kind, score""", k=k * 3, v=vec, t=ctx.t)
    words = [w for w in re.findall(r"[A-Za-z0-9]+", query.lower()) if w not in STOP and len(w) > 2]
    fhits = []
    if words:
        try:
            fhits = ctx.q("""CALL db.idx.fulltext.queryNodes('Source', $q) YIELD node, score
                WHERE node.t <= $t RETURN node.id AS id, node.kind AS kind, score LIMIT $k""",
                          q="|".join(words), t=ctx.t, k=k * 3)
        except Exception:
            fhits = []
    fused: dict[str, float] = {}
    kind_of = {}
    for rank, h in enumerate(vhits):
        fused[h["id"]] = fused.get(h["id"], 0) + 1 / (60 + rank)
        kind_of[h["id"]] = h["kind"]
    for rank, h in enumerate(fhits):
        fused[h["id"]] = fused.get(h["id"], 0) + 1 / (60 + rank)
        kind_of[h["id"]] = h["kind"]
    for i in fused:  # curated knowledge (docs, meeting notes) beats chatter at equal relevance
        fused[i] *= KIND_BOOST.get(kind_of[i], 1.0)
    candidates = [i for i, _ in sorted(fused.items(), key=lambda kv: -kv[1]) if not kinds or kind_of[i] in kinds]
    details, seen_text = [], set()
    for d in source_details(ctx.tenant, candidates[: k * 3]):
        norm = re.sub(r"[^a-z]+", " ", re.sub(r"\b(" + "|".join(SYSTEM_WORDS) + r")\b", "", d["snippet"].lower())).strip()
        if norm in seen_text:
            continue  # near-identical text (e.g. the same routine message about another service)
        seen_text.add(norm)
        details.append(d)
        if len(details) == k:
            break
    ranked = [d["id"] for d in details]
    ents = ctx.q("""MATCH (s:Source)-[:MENTIONS]->(e) WHERE s.id IN $ids AND NOT e:Source
        RETURN s.id AS sid, e.id AS id, labels(e)[0] AS label, e.name AS name""", ids=ranked)
    _source_nodes(ctx, ranked)
    for e in ents:
        ctx.node(e["id"], e["label"], e["name"])
        ctx.edge(e["sid"], e["id"], "MENTIONS")
    results = [{
        "cite": ctx.cite(d["id"]), "kind": d["kind"], "title": d["title"], "author": d["author_name"],
        "date": d10(d["ts"]), "text": d["snippet"],
        "mentions": [e["name"] for e in ents if e["sid"] == d["id"]],
    } for d in details]
    summary = "\n".join(f"- {r['text']} {r['cite']}" for r in results[:5])
    return {"results": results, "summary": summary}


# --------------------------------------------------------------------------------------
# ownership
# --------------------------------------------------------------------------------------
def who_owns(ctx: Ctx, entity: str) -> dict:
    """Current owner of a system (or the systems of a project/team) as of ctx.as_of, with the full
    ownership history, the evidence for each period, and documents that are now out of date."""
    r = resolve(ctx, entity, ("System", "Project", "Team"))
    if not r:
        return {"error": f"Could not find a system, project or team called '{entity}'."}
    label, eid = r
    if label == "Project":
        systems = [x["id"] for x in ctx.q("MATCH (:Project {id:$id})-[:USES]->(s:System) RETURN s.id AS id", id=eid)]
        ctx.node(eid, "Project", display(ctx, label, eid))
        for s in systems:
            ctx.edge(eid, s, "USES")
    elif label == "Team":
        systems = [x["id"] for x in ctx.q("""MATCH (:Team {id:$id})-[o:OWNS]->(s:System)
            WHERE o.since_t <= $t AND coalesce(o.until_t, $far) > $t RETURN DISTINCT s.id AS id""", id=eid, t=ctx.t, far=OPEN_END)]
        if not systems:
            return {"team": display(ctx, label, eid), "systems": [], "summary": f"{display(ctx, label, eid)} owns no systems as of {ctx.as_of or 'now'}."}
    else:
        systems = [eid]

    out, lines = [], []
    for sys_id in systems:
        claims = ctx.q("""MATCH (c:Claim {subject:$s}) WHERE c.recorded_t <= $t
            OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(src:Source) WHERE src.t <= $t
            RETURN c.id AS id, c.value AS owner_id, c.value_label AS owner_label, c.value_name AS owner,
                   c.valid_from AS since, c.valid_from_t AS since_t, c.valid_to AS until, c.valid_to_t AS until_t,
                   collect(src.id) AS evidence ORDER BY since_t""", s=sys_id, t=ctx.t)
        ctx.node(sys_id, "System", sys_id)
        if not claims:
            top = find_experts(ctx, sys_id, k=3)["experts"]
            active = [p for p in top if p["active"]]
            msg = f"I found no explicit ownership statement for {sys_id}."
            if active:
                msg += " The people who have done the most work on it are: " + "; ".join(
                    f"{p['name']} ({p['contributions']} contributions) {p['cite']}" for p in active) + "."
            lines.append(msg)
            out.append({"system": sys_id, "current_owner": None, "most_active": [p["name"] for p in active]})
            continue
        current = [c for c in claims if c["since_t"] <= ctx.t and (c["until_t"] is None or c["until_t"] > ctx.t)]
        cur = current[-1] if current else None
        history = []
        for c in claims:
            history.append({"owner": c["owner"], "from": d10(c["since"]), "to": d10(c["until"]) if c["until_t"] and c["until_t"] <= ctx.t else None,
                            "cite": ctx.cite(c["evidence"])})
            ctx.node(c["owner_id"], c["owner_label"], c["owner"])
            ctx.edge(c["owner_id"], sys_id, "OWNS", since=d10(c["since"]), until=d10(c["until"]) if c["until"] else None,
                     current=bool(cur and c["id"] == cur["id"]))
        _source_nodes(ctx, [e for c in claims for e in c["evidence"]])
        for c in claims:
            for e in c["evidence"]:
                ctx.edge(e, c["owner_id"], "SAYS_OWNER")
        contacts = []
        if cur and cur["owner_label"] == "Team":
            contacts = ctx.q("""MATCH (p:Person {active:true})-[:MEMBER_OF]->(:Team {id:$id})
                OPTIONAL MATCH (p)-[e:EXPERT_IN]->(:System {id:$s})
                RETURN p.id AS id, p.name AS name, p.role AS role, coalesce(e.score, 0) AS score
                ORDER BY score DESC LIMIT 3""", id=cur["owner_id"], s=sys_id)
            for p in contacts:
                ctx.node(p["id"], "Person", p["name"], role=p["role"])
                ctx.edge(p["id"], cur["owner_id"], "MEMBER_OF")
        stale = ctx.q("""MATCH (d:Document)-[:HAS_CHUNK]->(ch:Chunk)<-[:SUPPORTED_BY]-(c:Claim {subject:$s})
            WHERE c.valid_to_t IS NOT NULL AND c.valid_to_t <= $t AND d.updated_t < c.valid_to_t
            RETURN DISTINCT d.id AS id, d.title AS title, c.value_name AS says, ch.id AS chunk""", s=sys_id, t=ctx.t)
        warnings = [f"'{s['title']}' still says {s['says']} {ctx.cite(s['chunk'])}" for s in stale]
        for s in stale:
            ctx.node(s["id"], "Document", s["title"], stale=True)
            ctx.edge(s["id"], s["chunk"], "HAS_CHUNK")
        item = {"system": sys_id, "current_owner": cur["owner"] if cur else None,
                "since": d10(cur["since"]) if cur else None, "cite": ctx.cite(cur["evidence"]) if cur else "",
                "history": history, "contacts": [f"{p['name']} ({p['role']})" for p in contacts],
                "outdated_docs": warnings}
        out.append(item)
        when = f"as of {d10(ctx.as_of)}" if ctx.as_of else "currently"
        if cur:
            s = f"{sys_id} is {when} owned by the {cur['owner']} (since {d10(cur['since'])}) {item['cite']}."
            prev = [h for h in history if h["to"]]
            if prev:
                s += " Before that: " + "; ".join(f"{h['owner']} {h['from']} to {h['to']} {h['cite']}" for h in prev) + "."
            if contacts:
                s += f" Best contacts on that team: {', '.join(item['contacts'])}."
            if warnings:
                s += " Out of date: " + "; ".join(warnings) + "."
        else:
            s = f"No owner was recorded for {sys_id} {when}."
        lines.append(s)
    return {"systems": out, "summary": "\n".join(lines)}


# --------------------------------------------------------------------------------------
# expertise
# --------------------------------------------------------------------------------------
def find_experts(ctx: Ctx, subject: str, k: int = 5) -> dict:
    """People who know a system or topic, ranked by time-decayed contribution score
    (docs written, tickets closed, decisions proposed, discussions), with evidence."""
    r = resolve(ctx, subject, ("System", "Topic"))
    if r:
        label, xid = r
        rows = ctx.q(f"""MATCH (p:Person)-[e:EXPERT_IN]->(x:{label} {{id:$id}})
            OPTIONAL MATCH (p)-[:MEMBER_OF]->(t:Team)
            RETURN p.id AS id, p.name AS name, p.role AS role, p.active AS active, p.left_at AS left_at, t.name AS team,
                   e.score AS score, e.contributions AS n, e.last_seen_t AS last, e.evidence AS evidence, p.influence AS influence
            ORDER BY score DESC LIMIT $k""", id=xid, k=k)
        target = display(ctx, label, xid)
        ctx.node(xid, label, target)
    else:
        # Semantic fallback: authors of the most relevant evidence
        hits = search(ctx, subject, k=12)
        ids = list(ctx.registry.keys())
        rows = ctx.q("""MATCH (p:Person)-[:AUTHORED]->(s:Source) WHERE s.id IN $ids
            OPTIONAL MATCH (p)-[:MEMBER_OF]->(t:Team)
            RETURN p.id AS id, p.name AS name, p.role AS role, p.active AS active, p.left_at AS left_at, t.name AS team,
                   count(s) AS score, count(s) AS n, max(s.t) AS last, collect(s.id) AS evidence, p.influence AS influence
            ORDER BY score DESC LIMIT $k""", ids=ids, k=k)
        target, xid = subject, None
        del hits
    people = []
    for p in rows:
        ev = list(p["evidence"] or [])[:3]
        people.append({
            "name": p["name"], "team": p["team"], "role": p["role"], "active": p["active"],
            "left_at": p["left_at"], "score": round(float(p["score"]), 2), "contributions": p["n"],
            "last_active": d10(from_epoch(p["last"])) if p["last"] else None, "cite": ctx.cite(ev),
        })
        ctx.node(p["id"], "Person", p["name"], role=p["role"], active=p["active"])
        if xid:
            ctx.edge(p["id"], xid, "EXPERT_IN", score=round(float(p["score"]), 2))
        _source_nodes(ctx, ev)
        for e in ev:
            ctx.edge(p["id"], e, "AUTHORED")
    active = [p for p in people if p["active"]]
    lines = []
    if people:
        top = people[0]
        if not top["active"]:
            lines.append(f"Warning: the strongest expert on {target}, {top['name']}, left on {top['left_at']} {top['cite']}.")
        for p in active[:3]:
            lines.append(f"{p['name']} ({p['role']}, {p['team']}) - score {p['score']} from {p['contributions']} contributions, "
                         f"last active {p['last_active']} {p['cite']}")
    else:
        lines.append(f"I found nobody with recorded work on {target}.")
    return {"subject": target, "experts": people, "summary": "\n".join(lines)}


def bus_factor(ctx: Ctx, system: str | None = None, threshold: float = 1.5) -> dict:
    """Knowledge concentration risk per system: how many *active* people have real expertise,
    and whether the top expert has left."""
    sys_ids = [resolve(ctx, system, ("System",))[1]] if system and resolve(ctx, system, ("System",)) else \
        [r["id"] for r in ctx.q("MATCH (s:System) RETURN s.id AS id ORDER BY id")]
    out = []
    for sid in sys_ids:
        rows = ctx.q("""MATCH (p:Person)-[e:EXPERT_IN]->(:System {id:$id})
            RETURN p.id AS id, p.name AS name, p.active AS active, p.left_at AS left_at, e.score AS score, e.evidence AS ev
            ORDER BY score DESC""", id=sid)
        experts = [r for r in rows if r["score"] >= threshold]
        active = [r for r in experts if r["active"]]
        top = rows[0] if rows else None
        share = (top["score"] / sum(r["score"] for r in rows)) if rows else 0
        risk = "high" if len(active) <= 1 or (top and not top["active"]) else ("medium" if len(active) == 2 or share > 0.6 else "low")
        item = {"system": sid, "risk": risk, "active_experts": [r["name"] for r in active],
                "top_expert": top["name"] if top else None, "top_expert_active": bool(top and top["active"]),
                "top_expert_left_at": top["left_at"] if top and not top["active"] else None,
                "top_share": round(share, 2), "cite": ctx.cite(list(top["ev"] or [])[:2]) if top else ""}
        out.append(item)
        if system or risk == "high":
            ctx.node(sid, "System", sid, risk=risk)
            for r in rows[:4]:
                ctx.node(r["id"], "Person", r["name"], active=r["active"])
                ctx.edge(r["id"], sid, "EXPERT_IN", score=round(r["score"], 2))
    out.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["risk"]])
    lines = []
    for x in out:
        if x["risk"] == "high" or system:
            why = (f"top expert {x['top_expert']} left on {x['top_expert_left_at']}" if not x["top_expert_active"] and x["top_expert"]
                   else f"only {len(x['active_experts'])} active expert(s): {', '.join(x['active_experts']) or 'none'}")
            lines.append(f"{x['system']}: {x['risk']} risk - {why}; active experts: {', '.join(x['active_experts']) or 'none'} {x['cite']}")
    return {"systems": out, "summary": "\n".join(lines) or "No high-risk systems."}


# --------------------------------------------------------------------------------------
# decisions
# --------------------------------------------------------------------------------------
def _decision_rows(ctx: Ctx, ids: list[str]) -> list[dict]:
    return ctx.q("""MATCH (d:Decision) WHERE d.id IN $ids
        OPTIONAL MATCH (d)-[:DECIDED_IN]->(src:Source)
        OPTIONAL MATCH (d)-[:PROPOSED_BY]->(p:Person)
        OPTIONAL MATCH (d)-[:APPROVED_BY]->(a:Person)
        OPTIONAL MATCH (d)-[:BASED_ON]->(b:Source)
        OPTIONAL MATCH (d)-[:IMPLEMENTED_BY]->(i:Ticket)
        OPTIONAL MATCH (d)-[:SUPERSEDES]->(old:Decision)
        RETURN d.id AS id, d.title AS title, d.decided_at AS at, d.decided_t AS t, d.status AS status,
               d.superseded_t AS superseded_t, src.id AS src, src.title AS src_title, p.id AS pid, p.name AS proposer,
               a.id AS aid, a.name AS approver, collect(DISTINCT b.id) AS based_on, collect(DISTINCT i.id) AS implemented,
               collect(DISTINCT i.status) AS impl_status, collect(DISTINCT old.id) AS supersedes""", ids=ids)


def trace_decision(ctx: Ctx, query: str) -> dict:
    """Find the decision(s) behind a question and trace each one back to where it was made, who made it,
    the evidence it was based on, the tickets that implemented it, and the full chain of earlier and later
    decisions that replaced it. Status is evaluated at the as-of time."""
    vec = embed_one(query)
    hits = ctx.q("""CALL db.idx.vector.queryNodes('Decision', 'embedding', 6, vecf32($v)) YIELD node, score
        WHERE node.decided_t <= $t RETURN node.id AS id, score ORDER BY score""", v=vec, t=ctx.t)
    r = resolve(ctx, query, ("System", "Topic", "Project"))
    if r:
        linked = ctx.q("""MATCH (d:Decision)-[:AFFECTS|ABOUT]->(x {id:$id}) WHERE d.decided_t <= $t
            RETURN d.id AS id, 0.2 AS score""", id=r[1], t=ctx.t)
        hits = linked + hits
    if not hits:
        return {"error": "No decision found for that question.", "summary": "I could not find a recorded decision about that."}
    best = hits[0]["id"]
    # whole lineage: everything connected through SUPERSEDES
    chain = [best] + [r["id"] for r in ctx.q("""MATCH (:Decision {id:$id})-[:SUPERSEDES*1..6]-(x:Decision)
        RETURN DISTINCT x.id AS id""", id=best)]
    rows = sorted(_decision_rows(ctx, list(dict.fromkeys(chain))), key=lambda x: x["t"])
    rows = [x for x in rows if x["t"] <= ctx.t]
    later_by = {}
    for x in rows:
        for old in x["supersedes"]:
            later_by[old] = x
    lineage = []
    for x in rows:
        newer = later_by.get(x["id"])
        status = "in force"
        if newer and newer["t"] <= ctx.t:
            partial = x["status"] == "amended"
            status = f"{'amended' if partial else 'replaced'} on {d10(newer['at'])} by \"{newer['title']}\""
        lineage.append({
            "title": x["title"], "decided": d10(x["at"]), "status": status,
            "made_in": x["src_title"], "cite": ctx.cite(x["src"]),
            "proposed_by": x["proposer"], "approved_by": x["approver"],
            "evidence": [{"cite": ctx.cite(b)} for b in x["based_on"]],
            "evidence_cite": ctx.cite(x["based_on"]),
            "implemented_by": x["implemented"], "implemented_cite": ctx.cite(x["implemented"]),
        })
        ctx.node(x["id"], "Decision", x["title"], status="active" if status == "in force" else "superseded", decided=d10(x["at"]))
        ctx.edge(x["id"], x["src"], "DECIDED_IN")
        if x["pid"]:
            ctx.node(x["pid"], "Person", x["proposer"])
            ctx.edge(x["id"], x["pid"], "PROPOSED_BY")
        if x["aid"]:
            ctx.node(x["aid"], "Person", x["approver"])
            ctx.edge(x["id"], x["aid"], "APPROVED_BY")
        for b in x["based_on"]:
            ctx.edge(x["id"], b, "BASED_ON")
        for i in x["implemented"]:
            ctx.edge(x["id"], i, "IMPLEMENTED_BY")
        for old in x["supersedes"]:
            ctx.edge(x["id"], old, "SUPERSEDES")
        _source_nodes(ctx, [x["src"], *x["based_on"], *x["implemented"]])
    current = [l for l in lineage if l["status"] == "in force"]
    lines = []
    for l in lineage:
        s = f"{l['decided']}: \"{l['title']}\" - decided in {l['made_in']} {l['cite']}"
        if l["proposed_by"]:
            s += f", proposed by {l['proposed_by']}" + (f", approved by {l['approved_by']}" if l["approved_by"] else "")
        if l["evidence_cite"]:
            s += f"; based on {l['evidence_cite']}"
        if l["implemented_by"]:
            s += f"; implemented in {', '.join(l['implemented_by'])} {l['implemented_cite']}"
        s += f". Status: {l['status']}."
        lines.append(s)
    head = (f"The decision in force {'as of ' + d10(ctx.as_of) if ctx.as_of else 'now'} is \"{current[-1]['title']}\" "
            f"({current[-1]['decided']}) {current[-1]['cite']}." if current else "")
    return {"lineage": lineage, "summary": (head + "\nHistory:\n" if head else "") + "\n".join(lines)}


def list_decisions(ctx: Ctx) -> dict:
    rows = ctx.q("""MATCH (d:Decision) WHERE d.decided_t <= $t
        OPTIONAL MATCH (d)-[:DECIDED_IN]->(src) OPTIONAL MATCH (d)-[:SUPERSEDES]->(o:Decision)
        OPTIONAL MATCH (n:Decision)-[:SUPERSEDES]->(d) WHERE n.decided_t <= $t
        RETURN d.id AS id, d.title AS title, d.decided_at AS at, d.affects AS affects, d.topics AS topics,
               src.id AS src, src.title AS src_title, collect(DISTINCT o.id) AS supersedes,
               collect(DISTINCT n.id) AS superseded_by ORDER BY at""", t=ctx.t)
    for r in rows:
        r["status"] = "active" if not r["superseded_by"] else "superseded"
        r["cite"] = ctx.cite(r["src"])
    return {"decisions": rows}


# --------------------------------------------------------------------------------------
# change over time
# --------------------------------------------------------------------------------------
def whats_changed(ctx: Ctx, since: str, entity: str | None = None) -> dict:
    """Everything that changed between `since` and the as-of time: ownership moves, new or reversed
    decisions, people who left, docs that went stale."""
    t0, t1 = to_epoch(since), ctx.t
    r = resolve(ctx, entity, ("System", "Topic", "Project", "Team")) if entity else None
    eid = r[1] if r else None
    own = ctx.q("""MATCH (new:Claim)-[:SUPERSEDES]->(old:Claim) WHERE new.valid_from_t > $t0 AND new.valid_from_t <= $t1
          AND ($e IS NULL OR new.subject = $e OR new.value = $e OR old.value = $e)
        MATCH (new)-[:SUPPORTED_BY]->(s:Source)
        RETURN new.subject AS system, old.value_name AS was, new.value_name AS now, new.valid_from AS at, collect(s.id) AS ev
        ORDER BY at""", t0=t0, t1=t1, e=eid)
    dec = ctx.q("""MATCH (d:Decision)-[:DECIDED_IN]->(s) WHERE d.decided_t > $t0 AND d.decided_t <= $t1
          AND ($e IS NULL OR $e IN d.affects OR $e IN d.topics)
        OPTIONAL MATCH (d)-[:SUPERSEDES]->(o:Decision)
        RETURN d.title AS title, d.decided_at AS at, s.id AS src, collect(o.title) AS replaces ORDER BY at""", t0=t0, t1=t1, e=eid)
    left = ctx.q("""MATCH (p:Person) WHERE p.left_at IS NOT NULL
        OPTIONAL MATCH (p)-[e:EXPERT_IN]->(s:System) WITH p, s, e ORDER BY e.score DESC
        RETURN p.name AS name, p.left_at AS left_at, collect(s.id)[0..3] AS systems""")
    left = [p for p in left if t0 < to_epoch(p["left_at"]) <= t1]
    lines = []
    for o in own:
        lines.append(f"{d10(o['at'])}: {o['system']} ownership moved from {o['was']} to {o['now']} {ctx.cite(o['ev'])}")
    for d in dec:
        s = f"{d10(d['at'])}: decided \"{d['title']}\" {ctx.cite(d['src'])}"
        if d["replaces"]:
            s += f" (replacing \"{d['replaces'][0]}\")"
        lines.append(s)
    for p in left:
        lines.append(f"{p['left_at']}: {p['name']} left the company (knew most about {', '.join(p['systems'])})")
    lines.sort()
    return {"ownership_changes": own, "decisions": dec, "departures": left,
            "summary": "\n".join(lines) or f"No recorded changes since {since}."}


def freshness(ctx: Ctx) -> dict:
    """Out-of-date documents and the newer evidence that contradicts them."""
    docs = ctx.q("""MATCH (d:Document) WHERE d.stale = true
        OPTIONAL MATCH (a:Person {id: d.author_id})
        RETURN d.id AS id, d.title AS title, d.url AS url, d.updated_at AS updated, d.stale_reasons AS reasons,
               a.name AS author ORDER BY updated""")
    lines = []
    for d in docs:
        chunk = ctx.q("MATCH (:Document {id:$id})-[:HAS_CHUNK]->(c) RETURN c.id AS id LIMIT 1", id=d["id"])
        d["cite"] = ctx.cite(chunk[0]["id"]) if chunk else ""
        ctx.node(d["id"], "Document", d["title"], stale=True)
        lines.append(f"'{d['title']}' (last updated {d10(d['updated'])} by {d['author']}) {d['cite']}: " + "; ".join(d["reasons"]))
    return {"stale_documents": docs, "summary": "\n".join(lines) or "All documents are consistent with the latest evidence."}


# --------------------------------------------------------------------------------------
# connections and profiles
# --------------------------------------------------------------------------------------
def connect(ctx: Ctx, a: str, b: str) -> dict:
    """Shortest path between two people / teams / systems / projects / topics through the company graph."""
    ra, rb = resolve(ctx, a), resolve(ctx, b)
    if not ra or not rb:
        return {"error": f"Could not resolve {'%s' % a if not ra else b}."}
    rows = ctx.q(f"""MATCH (x:{ra[0]} {{id:$a}}), (y:{rb[0]} {{id:$b}})
        WITH shortestPath((x)-[:MEMBER_OF|OWNS|EXPERT_IN|USES|LED_BY|ASSIGNED_TO|TOUCHES|AUTHORED|MENTIONS|PROPOSED_BY|AFFECTS|COLLABORATES_WITH*..6]-(y)) AS p
        RETURN [n IN nodes(p) | {{id: n.id, label: labels(n)[0], name: coalesce(n.name, n.title, n.id)}}] AS nodes,
               [r IN relationships(p) | type(r)] AS rels""", a=ra[1], b=rb[1])
    if not rows or not rows[0]["nodes"]:
        return {"summary": f"No connection found between {a} and {b} within 6 hops."}
    nodes, rels = rows[0]["nodes"], rows[0]["rels"]
    parts = []
    for i, n in enumerate(nodes):
        ctx.node(n["id"], n["label"], n["name"])
        if i:
            ctx.edge(nodes[i - 1]["id"], n["id"], rels[i - 1])
        cite = ctx.cite(n["id"]) if n["label"] in ("Chunk", "Message", "Ticket", "Comment", "Meeting") else ""
        parts.append(f"{n['name']} ({n['label']}){cite}")
    path = parts[0] + "".join(f" -[{r}]- {p}" for r, p in zip(rels, parts[1:]))
    return {"path": nodes, "relationships": rels, "summary": f"{len(rels)} hops: {path}"}


def profile(ctx: Ctx, name: str) -> dict:
    """Everything the graph knows about one person, team, system or project."""
    r = resolve(ctx, name)
    if not r:
        return {"error": f"Unknown entity '{name}'."}
    label, eid = r
    ctx.node(eid, label, display(ctx, label, eid))
    if label == "Person":
        p = ctx.q("""MATCH (p:Person {id:$id}) OPTIONAL MATCH (p)-[:MEMBER_OF]->(t:Team)
            RETURN p.name AS name, p.role AS role, p.active AS active, p.left_at AS left_at, t.name AS team,
                   p.influence AS influence, p.broker AS broker, p.community AS community""", id=eid)[0]
        exp = ctx.q("""MATCH (:Person {id:$id})-[e:EXPERT_IN]->(x) RETURN x.id AS id, labels(x)[0] AS label,
            coalesce(x.name, x.id) AS name, e.score AS score ORDER BY score DESC LIMIT 6""", id=eid)
        col = ctx.q("""MATCH (:Person {id:$id})-[c:COLLABORATES_WITH]->(o:Person) RETURN o.id AS id, o.name AS name,
            c.weight AS w ORDER BY w DESC LIMIT 5""", id=eid)
        recent = ctx.q("""MATCH (:Person {id:$id})-[:AUTHORED]->(s:Source) WHERE s.t <= $t
            RETURN s.id AS id ORDER BY s.t DESC LIMIT 3""", id=eid, t=ctx.t)
        for x in exp:
            ctx.node(x["id"], x["label"], x["name"])
            ctx.edge(eid, x["id"], "EXPERT_IN", score=round(x["score"], 2))
        for c in col:
            ctx.node(c["id"], "Person", c["name"])
            ctx.edge(eid, c["id"], "COLLABORATES_WITH")
        status = "active" if p["active"] else f"left on {p['left_at']}"
        summary = (f"{p['name']} - {p['role']}, {p['team']} ({status}). Knows most about: "
                   f"{', '.join(x['name'] for x in exp[:4]) or 'n/a'}. Works most with: {', '.join(c['name'] for c in col[:4])}. "
                   f"Recent work: {ctx.cite([x['id'] for x in recent])}")
        _source_nodes(ctx, [x["id"] for x in recent])
        return {"person": p, "expertise": exp, "collaborators": col, "summary": summary}
    if label == "System":
        own = who_owns(ctx, eid)
        exp = find_experts(ctx, eid, k=4)
        projects = ctx.q("MATCH (p:Project)-[:USES]->(:System {id:$id}) RETURN p.name AS name", id=eid)
        open_t = ctx.q("""MATCH (t:Ticket)-[:TOUCHES]->(:System {id:$id}) WHERE t.status <> 'done' AND t.t <= $t
            RETURN t.id AS id, t.title AS title ORDER BY t.t DESC LIMIT 5""", id=eid, t=ctx.t)
        summary = (own["summary"] + f"\nProjects: {', '.join(p['name'] for p in projects)}.\nExperts:\n" + exp["summary"] +
                   ("\nOpen tickets: " + "; ".join(f"{t['title']} {ctx.cite(t['id'])}" for t in open_t) if open_t else ""))
        return {"ownership": own, "experts": exp["experts"], "projects": projects, "open_tickets": open_t, "summary": summary}
    if label == "Team":
        mem = ctx.q("MATCH (p:Person)-[:MEMBER_OF]->(:Team {id:$id}) RETURN p.id AS id, p.name AS name, p.role AS role, p.active AS active", id=eid)
        for m in mem:
            ctx.node(m["id"], "Person", m["name"], active=m["active"])
            ctx.edge(m["id"], eid, "MEMBER_OF")
        own = who_owns(ctx, eid)
        return {"members": mem, "ownership": own,
                "summary": f"Members: {', '.join(m['name'] + ('' if m['active'] else ' (left)') for m in mem)}.\n{own['summary']}"}
    if label == "Project":
        pr = ctx.q("""MATCH (p:Project {id:$id}) OPTIONAL MATCH (p)-[:LED_BY]->(l:Person) OPTIONAL MATCH (p)-[:USES]->(s:System)
            RETURN p.name AS name, p.status AS status, p.summary AS summary, l.name AS lead, l.active AS lead_active,
                   collect(s.id) AS systems""", id=eid)[0]
        tickets = ctx.q("""MATCH (t:Ticket)-[:PART_OF]->(:Project {id:$id}) WHERE t.t <= $t
            RETURN t.id AS id, t.title AS title, t.status AS status ORDER BY t.t DESC LIMIT 6""", id=eid, t=ctx.t)
        for s in pr["systems"]:
            ctx.node(s, "System", s)
            ctx.edge(eid, s, "USES")
        lead = pr["lead"] + ("" if pr["lead_active"] else " (has left the company)") if pr["lead"] else "n/a"
        summary = (f"{pr['name']} ({pr['status']}): {pr['summary']} Lead: {lead}. Systems: {', '.join(pr['systems'])}.\n"
                   "Recent tickets: " + "; ".join(f"{t['title']} [{t['status']}] {ctx.cite(t['id'])}" for t in tickets))
        return {"project": pr, "tickets": tickets, "summary": summary}
    return {"summary": f"{display(ctx, label, eid)} ({label})."}


def onboarding_brief(ctx: Ctx, subject: str) -> dict:
    """Material for an onboarding brief on a project or system: what it is, who owns it, who to ask,
    the decisions that shaped it, open risks and which docs are out of date."""
    prof = profile(ctx, subject)
    r = resolve(ctx, subject, ("Project", "System"))
    systems = []
    if r and r[0] == "Project":
        systems = prof.get("project", {}).get("systems", [])
    elif r:
        systems = [r[1]]
    parts = [prof.get("summary", "")]
    for s in systems:
        if r and r[0] == "Project":
            parts.append(who_owns(ctx, s)["summary"])
            parts.append(find_experts(ctx, s, k=3)["summary"])
        parts.append(bus_factor(ctx, s)["summary"])
        dec = ctx.q("MATCH (d:Decision) WHERE $s IN d.affects RETURN d.title AS title LIMIT 3", s=s)
        for d in dec:
            parts.append(trace_decision(ctx, d["title"])["summary"])
    parts.append(freshness(ctx)["summary"])
    return {"summary": "\n\n".join(p for p in parts if p)}


def cypher(ctx: Ctx, query: str) -> dict:
    """Run a read-only Cypher query (escape hatch for questions the other tools don't cover)."""
    if re.search(r"\b(CREATE|MERGE|DELETE|SET|REMOVE|DROP)\b", query, re.I):
        return {"error": "Only read-only queries are allowed."}
    if not re.search(r"\bLIMIT\b", query, re.I):
        query += " LIMIT 50"
    try:
        rows = ctx.q(query)
    except Exception as e:
        return {"error": str(e)}
    return {"rows": rows[:50], "summary": f"{len(rows)} rows"}


# --------------------------------------------------------------------------------------
# actions (getting work done)
# --------------------------------------------------------------------------------------
def _action(ctx: Ctx, kind: str, title: str, body: str, links: list[tuple[str, str]]) -> dict:
    aid = f"act-{int(time.time() * 1000)}"
    ctx.w("""CREATE (a:Action {id:$id, kind:$kind, title:$title, body:$body, status:'open', created_at:$ts})""",
          id=aid, kind=kind, title=title, body=body, ts=time.strftime("%Y-%m-%dT%H:%M:%S"))
    for label, eid in links:
        ctx.w(f"MATCH (a:Action {{id:$a}}), (x:{label} {{id:$id}}) MERGE (a)-[:ABOUT]->(x)", a=aid, id=eid)
    ctx.node(aid, "Action", title, kind=kind)
    for _, eid in links:
        ctx.edge(aid, eid, "ABOUT")
    return {"action_id": aid, "kind": kind, "title": title, "status": "open"}


def create_ticket(ctx: Ctx, title: str, description: str, system: str | None = None, assignee: str | None = None) -> dict:
    """Open a follow-up ticket (stored as an Action in the graph, linked to the system and assignee)."""
    links = []
    if system and (r := resolve(ctx, system, ("System",))):
        links.append(r)
    if assignee and (r := resolve(ctx, assignee, ("Person",))):
        links.append(r)
    res = _action(ctx, "ticket", title, description, links)
    res["summary"] = f"Opened ticket {res['action_id']}: {title}" + (f" (assigned to {assignee})" if assignee else "")
    return res


def flag_stale_doc(ctx: Ctx, document: str, reason: str) -> dict:
    """Flag a document as out of date and notify its author."""
    rows = ctx.q("""MATCH (d:Document) WHERE toLower(d.title) CONTAINS toLower($q) OR d.id = $q
        RETURN d.id AS id, d.title AS title, d.author_id AS author LIMIT 1""", q=document)
    if not rows:
        return {"error": f"No document matching '{document}'."}
    d = rows[0]
    links = [("Document", d["id"])] + ([("Person", d["author"])] if d["author"] else [])
    res = _action(ctx, "doc_update", f"Update '{d['title']}'", reason, links)
    res["summary"] = f"Flagged '{d['title']}' for update and notified its author."
    return res


def draft_message(ctx: Ctx, to: str, subject: str, body: str) -> dict:
    """Draft a message to a person (e.g. ask the expert). Stored as an Action for the user to send."""
    r = resolve(ctx, to, ("Person", "Team"))
    res = _action(ctx, "message", f"Message to {to}: {subject}", body, [r] if r else [])
    res["summary"] = f"Drafted a message to {display(ctx, *r) if r else to}."
    return res


def list_actions(ctx: Ctx) -> list[dict]:
    return ctx.q("""MATCH (a:Action) OPTIONAL MATCH (a)-[:ABOUT]->(x)
        RETURN a.id AS id, a.kind AS kind, a.title AS title, a.body AS body, a.status AS status, a.created_at AS created_at,
               collect(coalesce(x.name, x.title, x.id)) AS about ORDER BY created_at DESC""")


REGISTRY = {
    "search": search, "who_owns": who_owns, "find_experts": find_experts, "bus_factor": bus_factor,
    "trace_decision": trace_decision, "whats_changed": whats_changed, "freshness": freshness,
    "connect": connect, "profile": profile, "onboarding_brief": onboarding_brief, "cypher": cypher,
    "create_ticket": create_ticket, "flag_stale_doc": flag_stale_doc, "draft_message": draft_message,
}
