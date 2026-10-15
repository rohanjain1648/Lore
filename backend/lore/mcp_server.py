"""Lore as an MCP server: the same company-graph tools for any MCP client (Claude Desktop, Claude Code, Cursor...)

    stdio (Claude Desktop / Claude Code):   uv run python -m lore.mcp_server
    HTTP:                                    uv run python -m lore.mcp_server --http --port 8765

Every tool returns text with [S#] citations followed by the list of sources they refer to.
"""

from __future__ import annotations

import argparse
import json

from mcp.server.mcpserver import MCPServer

from . import agent, config, tools
from .tools import Ctx

mcp = MCPServer(
    name="lore",
    instructions=(
        "Lore is a company brain backed by a FalkorDB knowledge graph of people, teams, systems, projects, documents, "
        "tickets, chats, meetings and decisions. Use it to find owners and experts, trace decisions to their sources, "
        "see what changed and which docs are out of date. Keep the [S#] citations in your answer. "
        "Pass as_of (YYYY-MM-DD) to see the company as it was on that date."
    ),
)


def _render(ctx: Ctx, result: dict) -> str:
    text = result.get("summary") or result.get("error") or json.dumps(result, default=str)[:4000]
    if ctx.registry:
        lines = ["", "Sources:"]
        for d in tools.source_details(ctx.tenant, list(ctx.registry)):
            lines.append(f"[{ctx.registry[d['id']]}] {d['title']} ({d['kind']}, {d.get('author_name') or ''}, "
                         f"{(d['ts'] or '')[:10]}) {d['url']}")
        text += "\n".join(lines)
    return text


def _ctx(tenant: str | None, as_of: str | None) -> Ctx:
    return Ctx(tenant=tenant or config.DEFAULT_TENANT, as_of=f"{as_of[:10]}T23:59:59" if as_of else None)


@mcp.tool()
def ask_company(question: str, as_of: str | None = None, tenant: str | None = None) -> str:
    """Ask Lore anything about how the company works. Lore picks and chains its graph tools and answers with citations."""
    res = agent.ask(tenant or config.DEFAULT_TENANT, question, as_of=f"{as_of[:10]}T23:59:59" if as_of else None)
    srcs = "\n".join(f"[{c['sid']}] {c['title']} ({c['kind']}, {c.get('author_name') or ''}, {c['ts'][:10]}) {c['url']}"
                     for c in res["citations"] if c["used"])
    warn = ("\nWarnings: " + "; ".join(res["warnings"])) if res["warnings"] else ""
    return f"{res['answer']}\n\nSources:\n{srcs}{warn}"


@mcp.tool()
def who_owns(entity: str, as_of: str | None = None, tenant: str | None = None) -> str:
    """Current owner of a system (or a project's systems / a team's systems), ownership history and out-of-date docs."""
    ctx = _ctx(tenant, as_of)
    return _render(ctx, tools.who_owns(ctx, entity))


@mcp.tool()
def find_experts(subject: str, tenant: str | None = None) -> str:
    """Who knows a system or topic best (time-decayed contribution score), and whether they still work here."""
    ctx = _ctx(tenant, None)
    return _render(ctx, tools.find_experts(ctx, subject))


@mcp.tool()
def trace_decision(query: str, as_of: str | None = None, tenant: str | None = None) -> str:
    """Trace a decision to where it was made, who made it, its evidence, implementing tickets, and what replaced it."""
    ctx = _ctx(tenant, as_of)
    return _render(ctx, tools.trace_decision(ctx, query))


@mcp.tool()
def whats_changed(since: str, entity: str | None = None, as_of: str | None = None, tenant: str | None = None) -> str:
    """Ownership moves, new/reversed decisions and departures since a date (YYYY-MM-DD)."""
    ctx = _ctx(tenant, as_of)
    return _render(ctx, tools.whats_changed(ctx, since=since, entity=entity))


@mcp.tool()
def bus_factor(system: str | None = None, tenant: str | None = None) -> str:
    """Knowledge-concentration risk per system: active experts and whether the top expert has left."""
    ctx = _ctx(tenant, None)
    return _render(ctx, tools.bus_factor(ctx, system))


@mcp.tool()
def stale_documents(tenant: str | None = None) -> str:
    """Documents that are out of date, with the newer evidence that contradicts them."""
    ctx = _ctx(tenant, None)
    return _render(ctx, tools.freshness(ctx))


@mcp.tool()
def search_company(query: str, as_of: str | None = None, tenant: str | None = None) -> str:
    """Hybrid semantic + keyword search across docs, tickets, chat and meeting notes."""
    ctx = _ctx(tenant, as_of)
    return _render(ctx, tools.search(ctx, query))


@mcp.tool()
def graph_query(cypher: str, tenant: str | None = None) -> str:
    """Read-only Cypher against the company graph (FalkorDB)."""
    ctx = _ctx(tenant, None)
    return json.dumps(tools.cypher(ctx, cypher), default=str)[:20000]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--http", action="store_true")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    if a.http:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=a.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
