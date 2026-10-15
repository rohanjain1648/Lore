"""LLM-based extractor for messy real-world text (Groq first, OpenAI fallback, via llm.py). Returns the
same Extraction structure as the rule extractor; names are resolved through the EntityIndex so the graph
stays canonical. Any failure falls back to the rule extractor for that item."""

from __future__ import annotations

import json
import logging

from .. import llm
from ..entities import EntityIndex
from ..models import DecisionDraft, Extraction, OwnershipClaim, SourceItem
from . import extract_rules

log = logging.getLogger(__name__)

SCHEMA = {
    "type": "object",
    "properties": {
        "ownership": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "system": {"type": "string"},
                    "owner": {"type": "string"},
                    "owner_type": {"type": "string", "enum": ["Team", "Person"]},
                    "sentence": {"type": "string"},
                },
                "required": ["system", "owner", "owner_type", "sentence"],
                "additionalProperties": False,
            },
        },
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "proposer": {"type": "string"},
                    "approver": {"type": "string"},
                    "affects": {"type": "array", "items": {"type": "string"}},
                    "topics": {"type": "array", "items": {"type": "string"}},
                    "reverses_or_replaces_earlier_decision": {"type": "boolean"},
                    "sentence": {"type": "string"},
                },
                "required": ["title", "proposer", "approver", "affects", "topics",
                             "reverses_or_replaces_earlier_decision", "sentence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["ownership", "decisions"],
    "additionalProperties": False,
}

PROMPT = """You extract organisational knowledge from one piece of company text.

Known systems: {systems}
Known teams: {teams}
Known topics: {topics}

Extract:
1. ownership: statements that a team or person owns / maintains / is responsible for a system,
   including transfers ("ownership of X moves to Y" -> owner is Y). Only explicit statements.
2. decisions: explicit decisions or policies that were made (not proposals or questions).
   Use a short imperative title. proposer/approver are person names or "" if not stated.
   affects = system or project names it applies to. topics = known topic names it is about.

Return empty arrays if there is nothing. Text ({kind}, by {author}, {ts}):
---
{text}
---"""


def extract(item: SourceItem, index: EntityIndex, org: dict) -> Extraction:
    base = extract_rules.extract(item, index)  # mentions + ticket refs are deterministic either way
    try:
        prompt = PROMPT.format(
            systems=", ".join(s["id"] for s in org["systems"]),
            teams=", ".join(t["name"] for t in org["teams"]),
            topics=", ".join(t["name"] for t in org.get("topics", [])),
            kind=item.kind, author=item.author or "unknown", ts=item.ts, text=item.text,
        )
        prompt += "\n\nReply with ONLY a JSON object matching this JSON Schema:\n" + json.dumps(SCHEMA)
        msg, _provider = llm.chat([{"role": "user", "content": prompt}], json_mode=True, kind="extract", max_tokens=3000)
        data = json.loads(msg.content or "{}")
        if not isinstance(data, dict):
            return base
    except Exception as e:
        log.warning("LLM extraction failed for %s (%s); using rules", item.id, e)
        return base

    def person(name: str | None) -> str | None:
        r = index.resolve(name, ("Person",)) if name else None
        return r[1] if r else None

    claims = []
    for o in data.get("ownership") or []:
        sys_r = index.resolve(o.get("system", ""), ("System",))
        own_r = index.resolve(o.get("owner", ""), (o.get("owner_type", "Team"),)) or index.resolve(o.get("owner", ""), ("Team", "Person"))
        if sys_r and own_r:
            claims.append(OwnershipClaim(system=sys_r[1], owner_label=own_r[0], owner_id=own_r[1], sentence=o.get("sentence", "")))
    decisions = []
    for d in data.get("decisions") or []:
        if not d.get("title"):
            continue
        affects = {r[1] for a in d.get("affects") or [] if (r := index.resolve(a, ("System", "Project")))}
        topics = {r[1] for t in d.get("topics") or [] if (r := index.resolve(t, ("Topic",)))}
        decisions.append(DecisionDraft(
            title=d["title"], sentence=d.get("sentence", d["title"]), proposer=person(d.get("proposer")),
            approver=person(d.get("approver")), affects=sorted(affects), topics=sorted(topics),
            supersede_hint=bool(d.get("reverses_or_replaces_earlier_decision")),
        ))
    base.claims, base.decisions = claims, decisions
    return base
