"""Alias index for resolving names in free text to graph entities."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Match:
    label: str
    id: str
    start: int
    end: int
    text: str


class EntityIndex:
    def __init__(self, org: dict):
        self.names: dict[tuple[str, str], str] = {}
        # (pattern, label, id, case_sensitive)
        entries: list[tuple[str, str, str, bool]] = []
        first_names: dict[str, list[str]] = {}
        for p in org["people"]:
            self.names[("Person", p["id"])] = p["name"]
            entries.append((p["name"], "Person", p["id"], False))
            entries.append(("@" + p["handle"], "Person", p["id"], False))
            first_names.setdefault(p["name"].split()[0], []).append(p["id"])
        for first, ids in first_names.items():
            if len(ids) == 1:  # only unambiguous first names, and only capitalized
                entries.append((first, "Person", ids[0], True))
        for t in org["teams"]:
            self.names[("Team", t["id"])] = t["name"]
            entries.append((t["name"], "Team", t["id"], False))
            short = t["name"].replace(" team", "")
            if short != t["name"]:
                entries.append((f"{short} team", "Team", t["id"], False))
                entries.append((short, "Team", t["id"], True))
        for s in org["systems"]:
            self.names[("System", s["id"])] = s["name"]
            for a in [s["id"], s["name"], *s.get("aliases", [])]:
                entries.append((a, "System", s["id"], False))
        for pr in org["projects"]:
            self.names[("Project", pr["id"])] = pr["name"]
            entries.append((pr["name"], "Project", pr["id"], False))
            entries.append((pr["name"].replace("Project ", ""), "Project", pr["id"], True))
        for tp in org.get("topics", []):
            self.names[("Topic", tp["id"])] = tp["name"]
            entries.append((tp["name"], "Topic", tp["id"], False))
            for k in tp.get("keywords", []):
                entries.append((k, "Topic", tp["id"], False))
        # longest first so "payments-service" wins over "Payments"
        entries.sort(key=lambda e: -len(e[0]))
        self.entries = [
            (re.compile(r"(?<![\w-])" + re.escape(p) + r"(?![\w-])", 0 if cs else re.IGNORECASE), label, eid)
            for p, label, eid, cs in entries
        ]

    def find(self, text: str) -> list[Match]:
        taken: list[tuple[int, int]] = []
        out: list[Match] = []
        for rx, label, eid in self.entries:
            for m in rx.finditer(text):
                s, e = m.span()
                if any(s < te and e > ts for ts, te in taken):
                    continue
                taken.append((s, e))
                out.append(Match(label, eid, s, e, m.group(0)))
        out.sort(key=lambda m: m.start)
        return out

    def resolve(self, name: str, labels: tuple[str, ...] | None = None) -> tuple[str, str] | None:
        name = name.strip()
        if not name:
            return None
        for (label, eid), display in self.names.items():
            if labels and label not in labels:
                continue
            if name.lower() in (eid.lower(), display.lower()):
                return label, eid
        for m in self.find(name):
            if not labels or m.label in labels:
                return m.label, m.id
        return None

    def display(self, label: str, eid: str) -> str:
        return self.names.get((label, eid), eid)
