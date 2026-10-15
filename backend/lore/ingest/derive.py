"""Derived graph: who-knows-what and how people actually work together.

EXPERT_IN(score)        time-decayed sum of contributions to a system/topic
COLLABORATES_WITH(w)    co-participation in threads, tickets and meetings
Person.influence        algo.pageRank over COLLABORATES_WITH
Person.broker           algo.betweenness over COLLABORATES_WITH (knowledge brokers)
Person.community        algo.labelPropagation over COLLABORATES_WITH (real working groups)
"""

from __future__ import annotations

import math
from collections import defaultdict
from itertools import combinations

from .. import config, db

WEIGHTS = {
    "chunk": 2.0,       # wrote documentation about it
    "message": 0.6,     # discussed it
    "comment": 0.8,
    "ticket": 0.5,      # reported a ticket about it
    "meeting": 0.5,     # organised a meeting about it
    "assigned_done": 2.0,
    "assigned_open": 1.0,
    "proposed": 1.5,    # proposed a decision affecting it
    "attended": 0.3,
}
STRONG_TIE = 0.5


def run(tenant: str) -> None:
    expertise(tenant)
    collaboration(tenant)
    algorithms(tenant)


def _now(tenant: str) -> int:
    r = db.query(tenant, "MATCH (m:Meta) OPTIONAL MATCH (s:Source) RETURN m.now_t AS now, max(s.t) AS latest")
    if not r:
        return 0
    return max(r[0]["now"] or 0, r[0]["latest"] or 0)


def expertise(tenant: str) -> None:
    rows = db.query(tenant, """
        MATCH (p:Person)-[:AUTHORED]->(s:Source)-[:MENTIONS]->(x) WHERE x:System OR x:Topic
        RETURN p.id AS p, x.id AS x, s.kind AS kind, s.t AS t, s.id AS sid
        UNION ALL
        MATCH (p:Person)-[:ASSIGNED_TO]->(tk:Ticket)-[:TOUCHES|MENTIONS]->(x) WHERE x:System OR x:Topic
        RETURN p.id AS p, x.id AS x, CASE WHEN tk.status = 'done' THEN 'assigned_done' ELSE 'assigned_open' END AS kind,
               tk.t AS t, tk.id AS sid
        UNION ALL
        MATCH (p:Person)<-[:PROPOSED_BY]-(d:Decision)-[:AFFECTS|ABOUT]->(x) WHERE x:System OR x:Topic
        MATCH (d)-[:DECIDED_IN]->(src)
        RETURN p.id AS p, x.id AS x, 'proposed' AS kind, d.decided_t AS t, src.id AS sid
        UNION ALL
        MATCH (p:Person)-[:ATTENDED]->(m:Meeting)-[:MENTIONS]->(x) WHERE x:System OR x:Topic
        RETURN p.id AS p, x.id AS x, 'attended' AS kind, m.t AS t, m.id AS sid
    """)
    now = _now(tenant)
    tau = config.EXPERTISE_TAU_DAYS * 86400
    agg: dict[tuple[str, str], dict] = {}
    for r in rows:
        w = WEIGHTS.get(r["kind"], 0.5) * math.exp(-max(0, now - r["t"]) / tau)
        a = agg.setdefault((r["p"], r["x"]), {"score": 0.0, "n": 0, "last": 0, "ev": defaultdict(float)})
        a["score"] += w
        a["n"] += 1
        a["last"] = max(a["last"], r["t"])
        a["ev"][r["sid"]] += w
    out = [
        {"p": p, "x": x, "score": round(a["score"], 3), "n": a["n"], "last": a["last"],
         "evidence": [sid for sid, _ in sorted(a["ev"].items(), key=lambda kv: -kv[1])[:5]]}
        for (p, x), a in agg.items()
    ]
    db.query(tenant, "MATCH ()-[e:EXPERT_IN]->() DELETE e")
    db.query(tenant, """UNWIND $rows AS r MATCH (p:Person {id:r.p})
        MATCH (x) WHERE x.id = r.x AND (x:System OR x:Topic)
        CREATE (p)-[:EXPERT_IN {score:r.score, contributions:r.n, last_seen_t:r.last, evidence:r.evidence}]->(x)""",
             {"rows": out})


def collaboration(tenant: str) -> None:
    groups = db.query(tenant, """
        MATCH (p:Person)-[:AUTHORED]->(:Message)-[:IN_THREAD]->(th:Thread)
        RETURN th.id AS g, collect(DISTINCT p.id) AS people
        UNION ALL
        MATCH (tk:Ticket) OPTIONAL MATCH (a:Person)-[:ASSIGNED_TO]->(tk) OPTIONAL MATCH (r:Person)-[:AUTHORED]->(tk)
        OPTIONAL MATCH (c:Person)-[:AUTHORED]->(:Comment)-[:ON]->(tk)
        RETURN tk.id AS g, collect(DISTINCT a.id) + collect(DISTINCT r.id) + collect(DISTINCT c.id) AS people
        UNION ALL
        MATCH (p:Person)-[:ATTENDED]->(m:Meeting) RETURN m.id AS g, collect(DISTINCT p.id) AS people
    """)
    w: dict[tuple[str, str], float] = defaultdict(float)
    for g in groups:
        people = sorted({p for p in g["people"] if p})
        if len(people) < 2:
            continue
        share = 1.0 / (len(people) - 1)  # big meetings count less per pair
        for a, b in combinations(people, 2):
            w[(a, b)] += share
    rows = [{"a": a, "b": b, "w": round(v, 3)} for (a, b), v in w.items()]
    db.query(tenant, "MATCH ()-[e:COLLABORATES_WITH]->() DELETE e")
    db.query(tenant, """UNWIND $rows AS r MATCH (a:Person {id:r.a}), (b:Person {id:r.b})
        CREATE (a)-[:COLLABORATES_WITH {weight:r.w}]->(b), (b)-[:COLLABORATES_WITH {weight:r.w}]->(a)""",
             {"rows": rows})


def algorithms(tenant: str) -> None:
    db.query(tenant, """CALL algo.pageRank('Person', 'COLLABORATES_WITH') YIELD node, score
        SET node.influence = score""")
    db.query(tenant, """CALL algo.betweenness({nodeLabels:['Person'], relationshipTypes:['COLLABORATES_WITH']})
        YIELD node, score SET node.broker = score""")
    # Communities on strong ties only; weak ties (one big meeting together) would merge everyone.
    db.query(tenant, "MATCH ()-[e:WORKS_CLOSELY_WITH]->() DELETE e")
    db.query(tenant, f"""MATCH (a:Person)-[c:COLLABORATES_WITH]->(b:Person) WHERE c.weight >= {STRONG_TIE}
        CREATE (a)-[:WORKS_CLOSELY_WITH {{weight:c.weight}}]->(b)""")
    db.query(tenant, "MATCH (p:Person) SET p.community = null")
    db.query(tenant, """CALL algo.labelPropagation({nodeLabels:['Person'], relationshipTypes:['WORKS_CLOSELY_WITH']})
        YIELD node, communityId SET node.community = communityId""")
