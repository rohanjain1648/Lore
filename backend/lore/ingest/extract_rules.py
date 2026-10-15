"""Deterministic extractor: entity mentions, ownership statements and decisions.

Works without any API key. The LLM extractor (extract_llm.py) produces the same
Extraction structure from messier text.
"""

from __future__ import annotations

import re

from ..entities import EntityIndex
from ..models import DecisionDraft, Extraction, OwnershipClaim, SourceItem

TICKET_REF = re.compile(r"\b([A-Z]{2,5}-\d+)\b")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z@])|\n+")
PASSIVE = re.compile(r"\b(?:owned by|maintained by)\b", re.I)
ACTIVE = re.compile(r"\b(?:owns|maintains|(?:is|are) responsible for)\b", re.I)
TRANSFER = re.compile(r"\bownership of\b", re.I)
DECISION_LINE = re.compile(r"^\s*(?:Decision|Policy|Decided)\s*:\s*(.+)$", re.I)
WE_DECIDED = re.compile(r"\bwe (?:have )?decided to\s+(.+)$", re.I)
SUPERSEDE_HINT = re.compile(
    r"\b(?:lift|lifted|revert|reverted|reinstate|reinstated|replace|replaces|instead of|supersede[sd]?|back to|no longer|roll back|rollback)\b",
    re.I,
)
PARTIAL_HINT = re.compile(r"\b(?:keep|partially|only for|except)\b", re.I)
PROPOSED = re.compile(r"Proposed by ([A-Z][\w-]+(?: [A-Z][\w-]+)?)")
APPROVED = re.compile(r"approved by ([A-Z][\w-]+(?: [A-Z][\w-]+)?)", re.I)


def extract(item: SourceItem, index: EntityIndex) -> Extraction:
    ex = Extraction()
    seen = set()
    for m in index.find(item.text):
        if (m.label, m.id) not in seen:
            seen.add((m.label, m.id))
            ex.mentions.append((m.label, m.id))
    ex.ticket_refs = sorted({r for r in TICKET_REF.findall(item.text) if r != item.id})

    for sentence in SENTENCE_SPLIT.split(item.text):
        c = ownership_from_sentence(sentence.strip(), index)
        if c:
            ex.claims.append(c)

    for line in item.text.splitlines():
        d = decision_from_line(line, index)
        if d:
            ex.decisions.append(d)
    return ex


def ownership_from_sentence(s: str, index: EntityIndex) -> OwnershipClaim | None:
    if not s:
        return None
    ms = index.find(s)
    systems = [m for m in ms if m.label == "System"]
    owners = [m for m in ms if m.label in ("Team", "Person")]
    if not systems or not owners:
        return None
    if TRANSFER.search(s):
        sys_m, own_m = systems[0], owners[-1]  # "ownership of X from A to B" -> B
    elif (p := PASSIVE.search(s)):
        after = [o for o in owners if o.start > p.start()]
        before = [x for x in systems if x.start < p.start()] or systems
        if not after:
            return None
        sys_m, own_m = before[-1], after[0]
    elif (p := ACTIVE.search(s)):
        before = [o for o in owners if o.start < p.start()]
        after = [x for x in systems if x.start > p.start()]
        if not before or not after:
            return None
        sys_m, own_m = after[0], before[-1]
    else:
        return None
    return OwnershipClaim(system=sys_m.id, owner_label=own_m.label, owner_id=own_m.id, sentence=s)


def decision_from_line(line: str, index: EntityIndex) -> DecisionDraft | None:
    m = DECISION_LINE.match(line) or WE_DECIDED.search(line)
    if not m:
        return None
    rest = m.group(1).strip()
    title = re.split(r"(?<=[.!?])\s+(?=[A-Z])", rest)[0].rstrip(".")
    ms = index.find(title)
    proposer = approver = None
    if (p := PROPOSED.search(line)) and (r := index.resolve(p.group(1), ("Person",))):
        proposer = r[1]
    if (a := APPROVED.search(line)) and (r := index.resolve(a.group(1), ("Person",))):
        approver = r[1]
    return DecisionDraft(
        title=title[0].upper() + title[1:],
        sentence=line.strip(),
        proposer=proposer,
        approver=approver,
        affects=sorted({x.id for x in ms if x.label in ("System", "Project")}),
        topics=sorted({x.id for x in ms if x.label == "Topic"}),
        supersede_hint=bool(SUPERSEDE_HINT.search(title)),
    )


def is_partial(title: str) -> bool:
    return bool(PARTIAL_HINT.search(title))
