"""Ingestion pipeline.

    connector -> SourceItems -> (1) structural load  -> (2) embeddings
              -> (3) extraction (rules or LLM)      -> (4) temporal reconciliation of
                 ownership claims and decisions     -> (5) evidence linking + stale docs
              -> (6) derived graph (expertise, collaboration, algorithms)

Batch seeding and live single-item ingestion share steps 3-6, so a new chat message goes
through exactly the same reconciliation as the seed data.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path

from .. import config, db, schema
from ..embed import cosine, embed, embed_one
from ..entities import EntityIndex
from ..models import DecisionDraft, Extraction, OwnershipClaim, SourceItem, to_epoch
from ..connectors import files
from . import derive, extract_rules

log = logging.getLogger(__name__)

KIND_LABEL = {"chunk": "Chunk", "message": "Message", "ticket": "Ticket", "comment": "Comment", "meeting": "Meeting"}
SUPERSEDE_MIN_SIM = 0.55
EVIDENCE_MIN_SIM = 0.68
EVIDENCE_MIN_SHARED_WORDS = 2
IMPLEMENT_MIN_SIM = 0.78
DAY = 86400
STOPWORDS = set("""a an the and or of to in on for from with by at is are was were be been it its this that
as we our us you your i me my they them their not no but if then so up out into over after before about
all any can could should would will just than via per back again new""".split())


def content_words(text: str, index: EntityIndex) -> set[str]:
    """Lower-cased content words with org entity names (systems, teams, people, projects) removed,
    so 'payments-service chatter' doesn't look related to every payments-service decision."""
    for m in sorted(index.find(text), key=lambda m: -m.start):
        if m.label != "Topic":
            text = text[:m.start] + " " + text[m.end:]
    words = {w.rstrip("s") for w in re.findall(r"[a-z][a-z0-9]+", text.lower())}
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


# --------------------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------------------
def seed(tenant: str, data_dir: Path, reset: bool = True) -> dict:
    org, documents, items = files.load(data_dir)
    if reset:
        db.drop(tenant)
    schema.create(tenant)
    load_org(tenant, org)
    load_documents(tenant, documents)
    upsert_sources(tenant, items)
    index = EntityIndex(org)
    for item in items:
        link_item(tenant, item, extract(item, index, org))
    post_link(tenant)
    derive.run(tenant)
    return stats(tenant)


def ingest_live(tenant: str, item: SourceItem) -> dict:
    """Ingest one new item (e.g. a chat message) and update everything downstream."""
    org = org_from_graph(tenant)
    index = EntityIndex(org)
    upsert_sources(tenant, [item])
    ex = extract(item, index, org)
    changes = link_item(tenant, item, ex)
    post_link(tenant)
    derive.run(tenant)
    return {
        "item": item.id,
        "mentions": [{"label": l, "id": i, "name": index.display(l, i)} for l, i in ex.mentions],
        "changes": changes,
    }


def extract(item: SourceItem, index: EntityIndex, org: dict) -> Extraction:
    if config.EXTRACTOR == "llm" and config.HAS_LLM and item.kind in ("message", "comment", "meeting", "chunk"):
        from . import extract_llm

        return extract_llm.extract(item, index, org)
    return extract_rules.extract(item, index)


# --------------------------------------------------------------------------------------
# (1) Structural load
# --------------------------------------------------------------------------------------
def load_org(tenant: str, org: dict) -> None:
    q = lambda c, **p: db.query(tenant, c, p)  # noqa: E731
    q("MERGE (m:Meta {id:'meta'}) SET m.company=$company, m.now=$now, m.now_t=$now_t",
      company=org["company"], now=org["now"], now_t=to_epoch(org["now"]))
    q("UNWIND $rows AS r MERGE (t:Team {id:r.id}) SET t.name=r.name", rows=org["teams"])
    q("""UNWIND $rows AS r MERGE (p:Person {id:r.id})
         SET p.name=r.name, p.handle=r.handle, p.role=r.role, p.left_at=r.left_at, p.active = r.left_at IS NULL
         WITH p, r MATCH (t:Team {id:r.team}) MERGE (p)-[:MEMBER_OF]->(t)""", rows=org["people"])
    q("UNWIND $rows AS r MERGE (s:System {id:r.id}) SET s.name=r.name, s.kind=r.kind, s.aliases=r.aliases",
      rows=org["systems"])
    q("UNWIND $rows AS r MERGE (t:Topic {id:r.id}) SET t.name=r.name, t.keywords=r.keywords", rows=org.get("topics", []))
    q("""UNWIND $rows AS r MERGE (p:Project {id:r.id}) SET p.name=r.name, p.status=r.status, p.summary=r.summary
         WITH p, r OPTIONAL MATCH (lead:Person {id:r.lead}) FOREACH (_ IN CASE WHEN lead IS NULL THEN [] ELSE [1] END | MERGE (p)-[:LED_BY]->(lead))
         WITH p, r UNWIND r.systems AS sid MATCH (s:System {id:sid}) MERGE (p)-[:USES]->(s)""", rows=org["projects"])


def org_from_graph(tenant: str) -> dict:
    q = lambda c: db.query(tenant, c, read_only=True)  # noqa: E731
    meta = (q("MATCH (m:Meta) RETURN m.company AS company, m.now AS now") or [{"company": tenant, "now": None}])[0]
    return {
        "company": meta["company"], "now": meta["now"],
        "teams": q("MATCH (t:Team) RETURN t.id AS id, t.name AS name"),
        "people": q("""MATCH (p:Person) OPTIONAL MATCH (p)-[:MEMBER_OF]->(t:Team)
                       RETURN p.id AS id, p.name AS name, p.handle AS handle, t.id AS team, p.role AS role, p.left_at AS left_at"""),
        "systems": q("MATCH (s:System) RETURN s.id AS id, s.name AS name, s.kind AS kind, coalesce(s.aliases, []) AS aliases"),
        "projects": q("""MATCH (p:Project) OPTIONAL MATCH (p)-[:USES]->(s:System) OPTIONAL MATCH (p)-[:LED_BY]->(l:Person)
                         RETURN p.id AS id, p.name AS name, p.status AS status, p.summary AS summary,
                                collect(DISTINCT s.id) AS systems, l.id AS lead"""),
        "topics": q("MATCH (t:Topic) RETURN t.id AS id, t.name AS name, coalesce(t.keywords, []) AS keywords"),
    }


def load_documents(tenant: str, documents: list[dict]) -> None:
    db.query(tenant, """UNWIND $rows AS r MERGE (d:Document {id:r.id})
        SET d.title=r.title, d.url=r.url, d.updated_at=r.updated_at, d.updated_t=r.t, d.stale=false, d.author_id=r.author
        WITH d, r MATCH (p:Person {id:r.author}) MERGE (p)-[:AUTHORED]->(d)""",
             {"rows": [{**d, "t": to_epoch(d["updated_at"])} for d in documents]})


def upsert_sources(tenant: str, items: list[SourceItem]) -> None:
    vectors = embed([f"{i.title}\n{i.text}" for i in items])
    by_kind: dict[str, list[dict]] = {}
    for it, vec in zip(items, vectors):
        by_kind.setdefault(it.kind, []).append({
            "id": it.id, "kind": it.kind, "text": it.text, "ts": it.ts, "t": it.t, "url": it.url,
            "title": it.title, "author": it.author, "parent": it.parent, "embedding": vec,
            "meta": {k: v for k, v in it.meta.items() if v is not None and not isinstance(v, (list, dict))},
            "components": it.meta.get("components") or [], "attendees": it.meta.get("attendees") or [],
            "reply_to": it.meta.get("reply_to"), "channel": it.meta.get("channel"),
        })
    for kind, rows in by_kind.items():
        label = KIND_LABEL[kind]
        db.query(tenant, f"""UNWIND $rows AS r MERGE (s:Source:{label} {{id:r.id}})
            SET s.kind=r.kind, s.text=r.text, s.ts=r.ts, s.t=r.t, s.url=r.url, s.title=r.title,
                s.author_id=r.author, s.embedding=vecf32(r.embedding)
            SET s += r.meta
            WITH s, r OPTIONAL MATCH (a:Person {{id:r.author}})
            FOREACH (_ IN CASE WHEN a IS NULL THEN [] ELSE [1] END | MERGE (a)-[:AUTHORED]->(s))""", {"rows": rows})
        if kind == "chunk":
            db.query(tenant, """UNWIND $rows AS r MATCH (s:Chunk {id:r.id}), (d:Document {id:r.parent})
                MERGE (d)-[:HAS_CHUNK]->(s)""", {"rows": rows})
        elif kind == "message":
            db.query(tenant, """UNWIND $rows AS r MATCH (s:Message {id:r.id})
                MERGE (th:Thread {id:r.parent}) SET th.channel=r.channel
                MERGE (s)-[:IN_THREAD]->(th)
                WITH s, r MATCH (prev:Message {id:r.reply_to}) MERGE (s)-[:REPLIES_TO]->(prev)""", {"rows": rows})
        elif kind == "ticket":
            db.query(tenant, """UNWIND $rows AS r MATCH (s:Ticket {id:r.id}) SET s.key=r.id
                WITH s, r OPTIONAL MATCH (p:Project {id:r.meta.project})
                FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END | MERGE (s)-[:PART_OF]->(p))
                WITH s, r OPTIONAL MATCH (a:Person {id:r.meta.assignee})
                FOREACH (_ IN CASE WHEN a IS NULL THEN [] ELSE [1] END | MERGE (a)-[:ASSIGNED_TO]->(s))
                WITH s, r UNWIND r.components AS c MATCH (sys:System {id:c}) MERGE (s)-[:TOUCHES]->(sys)""", {"rows": rows})
        elif kind == "comment":
            db.query(tenant, """UNWIND $rows AS r MATCH (s:Comment {id:r.id}), (t:Ticket {id:r.parent})
                MERGE (s)-[:ON]->(t)""", {"rows": rows})
        elif kind == "meeting":
            db.query(tenant, """UNWIND $rows AS r MATCH (s:Meeting {id:r.id})
                UNWIND r.attendees AS pid MATCH (p:Person {id:pid}) MERGE (p)-[:ATTENDED]->(s)""", {"rows": rows})


# --------------------------------------------------------------------------------------
# (3)+(4) Link extraction results, reconcile claims and decisions over time
# --------------------------------------------------------------------------------------
def link_item(tenant: str, item: SourceItem, ex: Extraction) -> list[dict]:
    changes: list[dict] = []
    if ex.mentions:
        db.query(tenant, """MATCH (s:Source {id:$sid})
            MATCH (e) WHERE e.id IN $ids AND (e:Person OR e:Team OR e:System OR e:Project OR e:Topic)
            MERGE (s)-[:MENTIONS]->(e)""", {"sid": item.id, "ids": [i for _, i in ex.mentions]})
    if ex.ticket_refs:
        db.query(tenant, """MATCH (s:Source {id:$sid}) MATCH (t:Ticket) WHERE t.id IN $refs
            MERGE (s)-[:MENTIONS]->(t)""", {"sid": item.id, "refs": ex.ticket_refs})
    for d in ex.decisions:
        changes.extend(reconcile_decision(tenant, item, d))
    for c in ex.claims:
        changes.extend(reconcile_claim(tenant, item, c))
    return changes


def reconcile_claim(tenant: str, item: SourceItem, c: OwnershipClaim) -> list[dict]:
    key = f"{c.system}|owner"
    cur = db.query(tenant, """MATCH (x:Claim {subject_key:$k, status:'current'})
        RETURN x.id AS id, x.value AS value, x.value_name AS value_name, x.valid_from_t AS t""", {"k": key})
    if cur and cur[0]["value"] == c.owner_id:
        db.query(tenant, """MATCH (x:Claim {id:$cid}), (s:Source {id:$sid}) MERGE (x)-[:SUPPORTED_BY]->(s)
            SET x.last_confirmed = CASE WHEN coalesce(x.last_confirmed_t, 0) < $t THEN $ts ELSE x.last_confirmed END,
                x.last_confirmed_t = CASE WHEN coalesce(x.last_confirmed_t, 0) < $t THEN $t ELSE x.last_confirmed_t END,
                x.support = coalesce(x.support, 1) + 1""",
                 {"cid": cur[0]["id"], "sid": item.id, "t": item.t, "ts": item.ts})
        return [{"type": "claim_confirmed", "claim": cur[0]["id"], "subject": c.system, "owner": c.owner_id}]
    if cur and item.t < cur[0]["t"]:
        return []  # older than what we already know; keep as history only via MENTIONS
    owner_name = db.query(tenant, "MATCH (o {id:$id}) WHERE o:Team OR o:Person RETURN o.name AS n", {"id": c.owner_id})
    cid = f"claim-{c.system}-{item.t}-{c.owner_id}"
    db.query(tenant, f"""MATCH (sys:System {{id:$sys}}), (s:Source {{id:$sid}}), (o:{c.owner_label} {{id:$oid}})
        CREATE (x:Claim {{id:$cid, subject_key:$k, subject:$sys, predicate:'owner', value:$oid, value_label:$ol,
                         value_name:$oname, text:$text, valid_from:$ts, valid_from_t:$t, recorded_at:$ts, recorded_t:$t,
                         last_confirmed:$ts, last_confirmed_t:$t, support:1, status:'current'}})
        CREATE (x)-[:ABOUT]->(sys), (x)-[:SUPPORTED_BY]->(s)
        CREATE (o)-[:OWNS {{since:$ts, since_t:$t, claim_id:$cid}}]->(sys)""",
             {"sys": c.system, "sid": item.id, "oid": c.owner_id, "ol": c.owner_label, "cid": cid, "k": key,
              "oname": owner_name[0]["n"] if owner_name else c.owner_id, "text": c.sentence, "ts": item.ts, "t": item.t})
    out = [{"type": "claim_created", "claim": cid, "subject": c.system, "owner": c.owner_id}]
    if cur:
        db.query(tenant, """MATCH (new:Claim {id:$new}), (old:Claim {id:$old})
            SET old.status='superseded', old.valid_to=$ts, old.valid_to_t=$t
            CREATE (new)-[:SUPERSEDES]->(old)
            WITH old MATCH ()-[o:OWNS {claim_id:$old}]->() SET o.until=$ts, o.until_t=$t""",
                 {"new": cid, "old": cur[0]["id"], "ts": item.ts, "t": item.t})
        out.append({"type": "claim_superseded", "claim": cur[0]["id"], "subject": c.system,
                    "from": cur[0]["value_name"], "to": owner_name[0]["n"] if owner_name else c.owner_id})
    return out


def reconcile_decision(tenant: str, item: SourceItem, d: DecisionDraft) -> list[dict]:
    did = "dec-" + hashlib.sha1(f"{item.id}|{d.title}".encode()).hexdigest()[:10]
    if db.query(tenant, "MATCH (x:Decision {id:$id}) RETURN x.id", {"id": did}):
        return []
    vec = embed_one(d.title)
    db.query(tenant, """MATCH (s:Source {id:$sid})
        CREATE (x:Decision {id:$id, title:$title, summary:$summary, decided_at:$ts, decided_t:$t, status:'active',
                            affects:$affects, topics:$topics, embedding:vecf32($vec)})
        CREATE (x)-[:DECIDED_IN]->(s)
        WITH x OPTIONAL MATCH (p:Person {id:$proposer})
        FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END | MERGE (x)-[:PROPOSED_BY]->(p))
        WITH x OPTIONAL MATCH (a:Person {id:$approver})
        FOREACH (_ IN CASE WHEN a IS NULL THEN [] ELSE [1] END | MERGE (x)-[:APPROVED_BY]->(a))
        WITH x UNWIND (CASE WHEN size($affects) = 0 THEN [null] ELSE $affects END) AS aid
        OPTIONAL MATCH (e) WHERE e.id = aid AND (e:System OR e:Project)
        FOREACH (_ IN CASE WHEN e IS NULL THEN [] ELSE [1] END | MERGE (x)-[:AFFECTS]->(e))
        WITH DISTINCT x UNWIND (CASE WHEN size($topics) = 0 THEN [null] ELSE $topics END) AS tid
        OPTIONAL MATCH (tp:Topic {id:tid})
        FOREACH (_ IN CASE WHEN tp IS NULL THEN [] ELSE [1] END | MERGE (x)-[:ABOUT]->(tp))""",
             {"sid": item.id, "id": did, "title": d.title, "summary": d.sentence, "ts": item.ts, "t": item.t,
              "affects": d.affects, "topics": d.topics, "vec": vec, "proposer": d.proposer, "approver": d.approver})
    out = [{"type": "decision_created", "decision": did, "title": d.title}]
    if not d.supersede_hint or not (d.affects or d.topics):
        return out
    cands = db.query(tenant, """MATCH (x:Decision) WHERE x.status IN ['active', 'amended'] AND x.decided_t < $t AND x.id <> $id
          AND (any(a IN x.affects WHERE a IN $affects) OR any(tp IN x.topics WHERE tp IN $topics))
        RETURN x.id AS id, x.title AS title, x.embedding AS embedding""",
                     {"t": item.t, "id": did, "affects": d.affects, "topics": d.topics})
    partial = extract_rules.is_partial(d.title)
    for c in cands:
        sim = cosine(vec, list(c["embedding"]))
        if sim < SUPERSEDE_MIN_SIM:
            continue
        db.query(tenant, """MATCH (new:Decision {id:$new}), (old:Decision {id:$old})
            CREATE (new)-[:SUPERSEDES {partial:$partial, similarity:$sim}]->(old)
            SET old.status = CASE WHEN $partial THEN 'amended' ELSE 'superseded' END,
                old.superseded_at=$ts, old.superseded_t=$t, old.superseded_by=$new""",
                 {"new": did, "old": c["id"], "partial": partial, "sim": round(sim, 3), "ts": item.ts, "t": item.t})
        out.append({"type": "decision_superseded" if not partial else "decision_amended",
                    "decision": c["id"], "title": c["title"], "by": d.title})
    return out


# --------------------------------------------------------------------------------------
# (5) Evidence linking and freshness
# --------------------------------------------------------------------------------------
def post_link(tenant: str) -> None:
    index = EntityIndex(org_from_graph(tenant))
    decisions = db.query(tenant, """MATCH (d:Decision)-[:DECIDED_IN]->(src)
        RETURN d.id AS id, d.title AS title, d.decided_t AS t, d.embedding AS embedding, src.id AS src""")
    for d in decisions:
        # tickets referenced in the meeting / message where the decision was made
        db.query(tenant, """MATCH (d:Decision {id:$id})-[:DECIDED_IN]->(src)-[:MENTIONS]->(t:Ticket)
            WHERE t.t <= d.decided_t MERGE (d)-[:BASED_ON]->(t)""", {"id": d["id"]})
        hits = db.query(tenant, """CALL db.idx.vector.queryNodes('Source', 'embedding', 25, vecf32($v)) YIELD node, score
            RETURN node.id AS id, node.kind AS kind, node.t AS t, node.text AS text, score""", {"v": list(d["embedding"])})
        dwords = content_words(d["title"], index)
        before = [h for h in hits if h["id"] != d["src"] and d["t"] - 60 * DAY <= h["t"] < d["t"]
                  and 1 - h["score"] >= EVIDENCE_MIN_SIM
                  and len(dwords & content_words(h["text"], index)) >= EVIDENCE_MIN_SHARED_WORDS]
        after = [h for h in hits if h["kind"] == "ticket" and d["t"] <= h["t"] <= d["t"] + 30 * DAY
                 and 1 - h["score"] >= IMPLEMENT_MIN_SIM]
        if before:
            db.query(tenant, """MATCH (d:Decision {id:$id}) MATCH (s:Source) WHERE s.id IN $ids
                MERGE (d)-[r:BASED_ON]->(s) SET r.similarity = 1""", {"id": d["id"], "ids": [h["id"] for h in before[:3]]})
        if after:
            db.query(tenant, """MATCH (d:Decision {id:$id}) MATCH (t:Ticket) WHERE t.id IN $ids
                MERGE (d)-[:IMPLEMENTED_BY]->(t)""", {"id": d["id"], "ids": [h["id"] for h in after[:2]]})

    # Stale documents: a doc section supports an ownership claim that has since been superseded,
    # and the doc has no section supporting the claim that replaced it.
    db.query(tenant, "MATCH (d:Document) SET d.stale=false, d.stale_reasons=[]")
    rows = db.query(tenant, """MATCH (doc:Document)-[:HAS_CHUNK]->(ch:Chunk)<-[:SUPPORTED_BY]-(old:Claim {status:'superseded'})
        MATCH (cur:Claim {status:'current'}) WHERE cur.subject_key = old.subject_key
          AND NOT (cur)-[:SUPPORTED_BY]->(:Chunk)<-[:HAS_CHUNK]-(doc) AND cur.valid_from_t > doc.updated_t
        RETURN doc.id AS doc, ch.id AS chunk, old.subject AS subject, old.value_name AS was, cur.value_name AS now,
               cur.valid_from AS since, cur.id AS claim""")
    rows += db.query(tenant, """MATCH (doc:Document)-[:HAS_CHUNK]->(ch:Chunk)<-[:DECIDED_IN]-(old:Decision)
        WHERE old.status IN ['superseded', 'amended'] AND old.superseded_t > doc.updated_t
        MATCH (newer:Decision) WHERE newer.id = old.superseded_by
        RETURN doc.id AS doc, ch.id AS chunk, old.title AS subject, old.title AS was, newer.title AS now,
               newer.decided_at AS since, newer.id AS claim""")
    by_doc: dict[str, list[str]] = {}
    for r in rows:
        if r["subject"] == r["was"]:  # decision-based
            reason = f"Policy \"{r['was']}\" was changed on {r['since'][:10]}: \"{r['now']}\""
        else:
            reason = f"Says {r['subject']} is owned by {r['was']}, but since {r['since'][:10]} it is {r['now']}"
        by_doc.setdefault(r["doc"], []).append(reason)
    for doc, reasons in by_doc.items():
        db.query(tenant, "MATCH (d:Document {id:$id}) SET d.stale=true, d.stale_reasons=$r",
                 {"id": doc, "r": sorted(set(reasons))})


def stats(tenant: str) -> dict:
    rows = db.query(tenant, "MATCH (n) UNWIND labels(n) AS l RETURN l AS label, count(*) AS n ORDER BY n DESC", read_only=True)
    rels = db.query(tenant, "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS n ORDER BY n DESC", read_only=True)
    return {"nodes": {r["label"]: r["n"] for r in rows}, "relationships": {r["type"]: r["n"] for r in rels}}


def new_message_item(tenant: str, channel: str, author: str, text: str, ts: str | None = None) -> SourceItem:
    ts = ts or datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    mid = "live-" + hashlib.sha1(f"{author}|{ts}|{text}".encode()).hexdigest()[:10]
    return SourceItem(id=mid, kind="message", text=text, ts=ts, author=author,
                      url=f"https://chat.{tenant}.example/{channel}/{mid}", title=f"#{channel}",
                      parent=f"live-{channel}", meta={"channel": channel, "reply_to": None})


def dump_json(obj) -> str:
    return json.dumps(obj, indent=2, default=str)
