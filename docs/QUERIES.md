# Cypher queries and graph algorithms Lore depends on

Every query below runs on FalkorDB (one graph per company: `lore_<tenant>`). They are copied from
the code. The file and function are given for each one so you can find it in context.

## 1. Schema and indexes. `backend/lore/schema.py`

```cypher
CREATE INDEX FOR (n:Person) ON (n.id)          -- likewise Team, System, Project, Topic, Document, Source,
CREATE INDEX FOR (n:Claim) ON (n.subject_key)   -- Thread, Ticket(key), Decision, Claim, Action
CREATE VECTOR INDEX FOR (s:Source) ON (s.embedding) OPTIONS {dimension:384, similarityFunction:'cosine'}
CREATE VECTOR INDEX FOR (d:Decision) ON (d.embedding) OPTIONS {dimension:384, similarityFunction:'cosine'}
CREATE FULLTEXT INDEX FOR (s:Source) ON (s.text)
CREATE FULLTEXT INDEX FOR (d:Decision) ON (d.title)
```

Every piece of evidence (doc section, chat message, ticket, comment, meeting notes) has a second label `:Source`.
That way a single vector index and a single full-text index cover all of them.

## 2. Ingestion. `backend/lore/ingest/pipeline.py`

**Structural load** (`upsert_sources`): batched `UNWIND … MERGE` per evidence type, with typed edges:
```cypher
UNWIND $rows AS r MERGE (s:Source:Message {id:r.id})
SET s.text=r.text, s.ts=r.ts, s.t=r.t, s.url=r.url, s.title=r.title, s.author_id=r.author,
    s.embedding=vecf32(r.embedding)
WITH s, r OPTIONAL MATCH (a:Person {id:r.author})
FOREACH (_ IN CASE WHEN a IS NULL THEN [] ELSE [1] END | MERGE (a)-[:AUTHORED]->(s))
-- plus HAS_CHUNK, IN_THREAD, REPLIES_TO, PART_OF, ASSIGNED_TO, TOUCHES, ON, ATTENDED
```

**Temporal reconciliation of facts** (`reconcile_claim`). A new ownership statement is checked against the
claim that is currently true:
```cypher
MATCH (x:Claim {subject_key:$k, status:'current'})
RETURN x.id AS id, x.value AS value, x.value_name AS value_name, x.valid_from_t AS t
```
- **Same value**: the existing claim gets corroborated with `MERGE (x)-[:SUPPORTED_BY]->(s)`.
- **Different value**: a new claim is created, the old one is closed, and the ownership edge history is updated:
```cypher
MATCH (new:Claim {id:$new}), (old:Claim {id:$old})
SET old.status='superseded', old.valid_to=$ts, old.valid_to_t=$t
CREATE (new)-[:SUPERSEDES]->(old)
WITH old MATCH ()-[o:OWNS {claim_id:$old}]->() SET o.until=$ts, o.until_t=$t
```

**Decision supersession** (`reconcile_decision`). Earlier decisions that are still in force and share a
system or topic become candidates. Lore compares their embeddings with the new decision, and a match creates a
`SUPERSEDES` edge (marked `partial` when the decision is only amended):
```cypher
MATCH (x:Decision) WHERE x.status IN ['active','amended'] AND x.decided_t < $t AND x.id <> $id
  AND (any(a IN x.affects WHERE a IN $affects) OR any(tp IN x.topics WHERE tp IN $topics))
RETURN x.id AS id, x.title AS title, x.embedding AS embedding
```

**Evidence and implementation links** (`post_link`). Vector search from the decision's embedding over all
sources. Matches from before the decision become `BASED_ON` evidence, and tickets from after it become
`IMPLEMENTED_BY`:
```cypher
CALL db.idx.vector.queryNodes('Source', 'embedding', 25, vecf32($v)) YIELD node, score
RETURN node.id AS id, node.kind AS kind, node.t AS t, node.text AS text, score
```

**Stale documents** (`post_link`). A doc is out of date when a claim it supports has been replaced by a newer
claim that the doc doesn't support:
```cypher
MATCH (doc:Document)-[:HAS_CHUNK]->(ch:Chunk)<-[:SUPPORTED_BY]-(old:Claim {status:'superseded'})
MATCH (cur:Claim {status:'current'}) WHERE cur.subject_key = old.subject_key
  AND NOT (cur)-[:SUPPORTED_BY]->(:Chunk)<-[:HAS_CHUNK]-(doc) AND cur.valid_from_t > doc.updated_t
RETURN doc.id, ch.id, old.subject, old.value_name AS was, cur.value_name AS now, cur.valid_from AS since
```
The same check runs for policies: a doc section that a decision was made in, where that decision has since been
replaced.

## 3. Derived graph and algorithms. `backend/lore/ingest/derive.py`

**Expertise**: contributions gathered by four `UNION ALL` branches, then a time-decayed score
`Σ weight(kind) · e^(−age/120d)` written to `EXPERT_IN`:
```cypher
MATCH (p:Person)-[:AUTHORED]->(s:Source)-[:MENTIONS]->(x) WHERE x:System OR x:Topic
RETURN p.id, x.id, s.kind, s.t, s.id
UNION ALL
MATCH (p:Person)-[:ASSIGNED_TO]->(tk:Ticket)-[:TOUCHES|MENTIONS]->(x) WHERE x:System OR x:Topic ...
UNION ALL
MATCH (p:Person)<-[:PROPOSED_BY]-(d:Decision)-[:AFFECTS|ABOUT]->(x) ...
UNION ALL
MATCH (p:Person)-[:ATTENDED]->(m:Meeting)-[:MENTIONS]->(x) ...
```

**Collaboration network**: people who share a thread, ticket or meeting, weighted by `1/(group size − 1)`,
are linked with `COLLABORATES_WITH`.

**FalkorDB algorithms**, with results stored on `Person` and shown in the UI:
```cypher
CALL algo.pageRank('Person', 'COLLABORATES_WITH') YIELD node, score SET node.influence = score
CALL algo.betweenness({nodeLabels:['Person'], relationshipTypes:['COLLABORATES_WITH']})
  YIELD node, score SET node.broker = score                       -- knowledge brokers
CALL algo.labelPropagation({nodeLabels:['Person'], relationshipTypes:['WORKS_CLOSELY_WITH']})
  YIELD node, communityId SET node.community = communityId          -- real working groups
```

## 4. Agent tools. `backend/lore/tools.py`

Every tool accepts an **as-of** time `$t`. Without one, it is set to the year 2100 ("now").

| Tool | Core query |
|---|---|
| `search` | `db.idx.vector.queryNodes('Source',…) WHERE node.t <= $t` + `db.idx.fulltext.queryNodes('Source', $q)`, fused by reciprocal rank, then a one-hop expansion `(s)-[:MENTIONS]->(e)` |
| `who_owns` | `MATCH (c:Claim {subject:$s}) WHERE c.recorded_t <= $t OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(src) WHERE src.t <= $t` → the current claim is the one whose `[valid_from, valid_to)` contains `$t`; stale docs: `(d:Document)-[:HAS_CHUNK]->(ch)<-[:SUPPORTED_BY]-(c:Claim) WHERE c.valid_to_t <= $t AND d.updated_t < c.valid_to_t` |
| `find_experts` | `MATCH (p:Person)-[e:EXPERT_IN]->(x {id:$id}) RETURN … ORDER BY e.score DESC` (plus `p.active`, `p.left_at`) |
| `bus_factor` | `EXPERT_IN` scores per system → number of active experts, top expert's share, whether the top expert has left |
| `trace_decision` | `db.idx.vector.queryNodes('Decision',…) WHERE node.decided_t <= $t` + `(d)-[:AFFECTS\|ABOUT]->(x)`; lineage: `MATCH (:Decision {id:$id})-[:SUPERSEDES*1..6]-(x:Decision)`; details: `DECIDED_IN`, `PROPOSED_BY`, `APPROVED_BY`, `BASED_ON`, `IMPLEMENTED_BY` |
| `whats_changed` | `(new:Claim)-[:SUPERSEDES]->(old:Claim) WHERE new.valid_from_t > $t0 AND new.valid_from_t <= $t1` + decisions in the window + `Person.left_at` |
| `connect` | `WITH shortestPath((x)-[:MEMBER_OF\|OWNS\|EXPERT_IN\|USES\|…*..6]-(y)) AS p RETURN nodes(p), relationships(p)` |
| `profile` | neighbourhood queries per label (Person/Team/System/Project) |
| `cypher` | read-only (`GRAPH.RO_QUERY`) escape hatch, `LIMIT` enforced |
| actions | `CREATE (a:Action {…})` + `MERGE (a)-[:ABOUT]->(target)` |

## 5. Time travel

All time values are stored twice: as an ISO string (`ts`, `valid_from`, …) and as epoch seconds (`t`,
`valid_from_t`, …) for range filters. Ownership edges carry `since_t` / `until_t`, so the current ownership graph
at any date is:
```cypher
MATCH (o)-[r:OWNS]->(s:System) WHERE r.since_t <= $t AND coalesce(r.until_t, $open) > $t RETURN o, s
```
