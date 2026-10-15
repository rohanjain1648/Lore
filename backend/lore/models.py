from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SourceItem:
    """A normalized piece of evidence from any connector."""

    id: str
    kind: str  # chunk | message | ticket | comment | meeting
    text: str
    ts: str  # ISO 8601
    author: str | None
    url: str
    title: str = ""
    parent: str | None = None  # document id / thread id / ticket key
    meta: dict = field(default_factory=dict)

    @property
    def t(self) -> int:
        return to_epoch(self.ts)


@dataclass
class OwnershipClaim:
    system: str
    owner_label: str  # Team | Person
    owner_id: str
    sentence: str


@dataclass
class DecisionDraft:
    title: str
    sentence: str
    proposer: str | None = None
    approver: str | None = None
    affects: list[str] = field(default_factory=list)  # system / project ids
    topics: list[str] = field(default_factory=list)
    supersede_hint: bool = False


@dataclass
class Extraction:
    mentions: list[tuple[str, str]] = field(default_factory=list)  # (label, id)
    ticket_refs: list[str] = field(default_factory=list)
    claims: list[OwnershipClaim] = field(default_factory=list)
    decisions: list[DecisionDraft] = field(default_factory=list)


def to_epoch(ts: str) -> int:
    return int(datetime.fromisoformat(ts.replace("Z", "")).timestamp())


def from_epoch(t: int) -> str:
    return datetime.fromtimestamp(t).strftime("%Y-%m-%dT%H:%M:%S")
