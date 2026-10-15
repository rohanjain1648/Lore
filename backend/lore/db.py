"""Thin FalkorDB wrapper: one graph per tenant (FalkorDB multi-graph)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from falkordb import FalkorDB, Graph
from falkordb.node import Node
from falkordb.edge import Edge
from falkordb.path import Path

from . import config


@lru_cache(maxsize=1)
def client() -> FalkorDB:
    return FalkorDB(
        host=config.FALKORDB_HOST,
        port=config.FALKORDB_PORT,
        username=config.FALKORDB_USERNAME,
        password=config.FALKORDB_PASSWORD,
    )


def graph(tenant: str) -> Graph:
    return client().select_graph(config.graph_name(tenant))


def list_tenants() -> list[str]:
    prefix = "lore_"
    return sorted(g[len(prefix):] for g in client().list_graphs() if g.startswith(prefix))


def _plain(v: Any) -> Any:
    if isinstance(v, Node):
        props = {k: val for k, val in v.properties.items() if k != "embedding"}
        return {"_labels": list(v.labels), **props}
    if isinstance(v, Edge):
        return {"_type": v.relation, **v.properties}
    if isinstance(v, Path):
        return {"nodes": [_plain(n) for n in v.nodes()], "edges": [_plain(e) for e in v.edges()]}
    if isinstance(v, list):
        return [_plain(x) for x in v]
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items() if k != "embedding"}
    return v


def query(tenant: str, cypher: str, params: dict | None = None, read_only: bool = False) -> list[dict]:
    g = graph(tenant)
    res = g.ro_query(cypher, params or {}) if read_only else g.query(cypher, params or {})
    cols = [h[1] if isinstance(h, (list, tuple)) else h for h in (res.header or [])]
    cols = [c.decode() if isinstance(c, bytes) else c for c in cols]
    return [dict(zip(cols, (_plain(v) for v in row))) for row in res.result_set]


def drop(tenant: str) -> None:
    try:
        graph(tenant).delete()
    except Exception:
        pass
