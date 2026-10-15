"""Graph schema: indexes for lookup, vector and full-text search.

Every evidence-bearing node (doc chunk, chat message, ticket, comment, meeting) also carries
the :Source label, so one vector index and one full-text index cover all of them.
"""

from __future__ import annotations

from . import config, db

RANGE_INDEXES = [
    ("Person", "id"), ("Team", "id"), ("System", "id"), ("Project", "id"), ("Topic", "id"),
    ("Document", "id"), ("Source", "id"), ("Thread", "id"), ("Ticket", "key"),
    ("Decision", "id"), ("Claim", "id"), ("Claim", "subject_key"), ("Action", "id"),
]


def create(tenant: str) -> None:
    stmts = [f"CREATE INDEX FOR (n:{label}) ON (n.{prop})" for label, prop in RANGE_INDEXES]
    stmts += [
        f"CREATE VECTOR INDEX FOR (s:Source) ON (s.embedding) OPTIONS {{dimension:{config.EMBED_DIM}, similarityFunction:'cosine'}}",
        f"CREATE VECTOR INDEX FOR (d:Decision) ON (d.embedding) OPTIONS {{dimension:{config.EMBED_DIM}, similarityFunction:'cosine'}}",
        "CREATE FULLTEXT INDEX FOR (s:Source) ON (s.text)",
        "CREATE FULLTEXT INDEX FOR (d:Decision) ON (d.title)",
    ]
    for s in stmts:
        try:
            db.query(tenant, s)
        except Exception as e:
            if "already indexed" not in str(e).lower() and "already exists" not in str(e).lower():
                raise
