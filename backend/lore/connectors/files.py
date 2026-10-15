"""Connector for a company export on disk (the format produced by data/northwind/generate.py):

    org.json       people, teams, systems, projects, topics
    docs.json      wiki pages (markdown)       -> Document + Chunk sources (one per section)
    tickets.json   tracker issues + comments    -> Ticket + Comment sources
    chat.json      channels / threads / msgs    -> Thread + Message sources
    meetings.json  meeting notes                -> Meeting sources
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..models import SourceItem


def load(path: Path) -> tuple[dict, list[dict], list[SourceItem]]:
    """Returns (org, documents, source items sorted by time)."""
    rd = lambda n: json.loads((path / f"{n}.json").read_text(encoding="utf-8"))  # noqa: E731
    org = rd("org")
    items: list[SourceItem] = []
    documents = []

    for d in rd("docs"):
        documents.append({k: d[k] for k in ("id", "title", "author", "updated_at", "url")})
        for i, (heading, text) in enumerate(split_sections(d["body"])):
            items.append(SourceItem(
                id=f"{d['id']}#s{i + 1}", kind="chunk", text=text, ts=d["updated_at"], author=d["author"],
                url=f"{d['url']}#s{i + 1}", title=f"{d['title']} › {heading}" if heading else d["title"],
                parent=d["id"],
            ))

    for t in rd("tickets"):
        items.append(SourceItem(
            id=t["key"], kind="ticket", text=f"{t['title']}. {t['description']}", ts=t["created"],
            author=t["reporter"], url=t["url"], title=f"{t['key']}: {t['title']}", parent=None,
            meta={k: t.get(k) for k in ("project", "assignee", "components", "status", "closed")},
        ))
        for c in t["comments"]:
            items.append(SourceItem(
                id=c["id"], kind="comment", text=c["text"], ts=c["ts"], author=c["author"], url=c["url"],
                title=f"Comment on {t['key']}", parent=t["key"],
            ))

    for th in rd("chat"):
        prev = None
        for m in th["messages"]:
            items.append(SourceItem(
                id=m["id"], kind="message", text=m["text"], ts=m["ts"], author=m["author"], url=m["url"],
                title=f"#{th['channel']}", parent=th["id"], meta={"channel": th["channel"], "reply_to": prev},
            ))
            prev = m["id"]

    for mt in rd("meetings"):
        items.append(SourceItem(
            id=mt["id"], kind="meeting", text=mt["notes"], ts=mt["date"], author=mt["organizer"], url=mt["url"],
            title=mt["title"], meta={"attendees": mt["attendees"]},
        ))

    items.sort(key=lambda s: s.ts)
    return org, documents, items


def split_sections(body: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, text) sections on '#'/'##' headings."""
    out: list[tuple[str, str]] = []
    heading, buf = "", []
    for line in body.splitlines():
        m = re.match(r"^#{1,3}\s+(.*)", line)
        if m:
            if "".join(buf).strip():
                out.append((heading, "\n".join(buf).strip()))
            heading, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    if "".join(buf).strip():
        out.append((heading, "\n".join(buf).strip()))
    return out
