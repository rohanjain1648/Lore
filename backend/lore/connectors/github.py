"""Real public data: turn public GitHub repositories into a company export Lore can ingest.

    uv run python -m lore.connectors.github --org FalkorDB --repos falkordb-py GraphRAG-SDK --out ../data/falkordb/raw
    uv run python -m lore.cli --tenant falkordb seed --data ../data/falkordb/raw

Mapping
    repository        -> System           (CODEOWNERS -> "repo is maintained by @login" ownership statements)
    contributor       -> Person           (GitHub login; only public profile handle, no emails)
    label             -> Topic
    milestone         -> Project
    issue / PR        -> Ticket           (labels become components via the repo; assignee kept)
    issue comment     -> Comment
    README, docs/*.md -> Document + Chunks
Set GITHUB_TOKEN for a higher rate limit (60 requests/hour without it).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
from collections import Counter
from pathlib import Path

import httpx

API = "https://api.github.com"


class GH:
    def __init__(self):
        h = {"Accept": "application/vnd.github+json", "User-Agent": "lore-company-brain"}
        if tok := os.getenv("GITHUB_TOKEN"):
            h["Authorization"] = f"Bearer {tok}"
        self.c = httpx.Client(base_url=API, headers=h, timeout=30)

    def get(self, path: str, **params):
        r = self.c.get(path, params=params)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


BOTS = {"copilot", "coderabbitai", "dependabot", "github-actions", "renovate", "codecov", "sonarcloud", "gemini-code-assist"}


def is_bot(login: str | None) -> bool:
    return not login or login.endswith("[bot]") or login.lower() in BOTS


def iso(ts: str | None) -> str | None:
    return ts.replace("Z", "") if ts else None


def fetch(org: str, repos: list[str], max_issues: int = 150, max_docs: int = 8) -> dict:
    gh = GH()
    people: Counter = Counter()
    labels: dict[str, str] = {}
    milestones: dict[str, dict] = {}
    docs, tickets = [], []
    systems = []
    for repo in repos:
        full = f"{org}/{repo}"
        meta = gh.get(f"/repos/{full}") or {}
        systems.append({"id": repo.lower(), "name": repo.lower(), "kind": "repository",
                        "aliases": [repo, full, repo.replace("-", " ")]})
        # docs: README + docs/*.md
        files = []
        if (rd := gh.get(f"/repos/{full}/readme")):
            files.append(rd)
        for d in (gh.get(f"/repos/{full}/contents/docs") or [])[:max_docs]:
            if isinstance(d, dict) and d.get("name", "").endswith(".md"):
                files.append(gh.get(f"/repos/{full}/contents/{d['path']}"))
        commits = gh.get(f"/repos/{full}/commits", per_page=1) or [{}]
        updated = iso(((commits[0].get("commit") or {}).get("committer") or {}).get("date")) or iso(meta.get("pushed_at"))
        for f in files:
            if not f or "content" not in f:
                continue
            body = base64.b64decode(f["content"]).decode("utf-8", "replace")
            body = re.sub(r"<[^>]+>", "", body)[:20000]
            docs.append({"id": f"doc-{repo}-{f['path'].replace('/', '-')}".lower(), "title": f"{repo}/{f['path']}",
                         "author": None, "updated_at": updated, "body": body, "url": f["html_url"], "source": "github"})
        # CODEOWNERS -> ownership statements
        for path in (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"):
            co = gh.get(f"/repos/{full}/contents/{path}")
            if co and "content" in co:
                owners = re.findall(r"@([\w-]+)", base64.b64decode(co["content"]).decode("utf-8", "replace"))
                lines = [f"{repo.lower()} is maintained by @{o}." for o in dict.fromkeys(owners) if "/" not in o]
                if lines:
                    people.update(o for o in owners if "/" not in o)
                    docs.append({"id": f"doc-{repo}-codeowners".lower(), "title": f"{repo}/{path}", "author": None,
                                 "updated_at": updated, "body": "# Code owners\n" + "\n".join(lines),
                                 "url": co["html_url"], "source": "github"})
                break
        # issues + PRs
        issues = []
        page = 1
        while len(issues) < max_issues:
            batch = gh.get(f"/repos/{full}/issues", state="all", per_page=100, page=page, sort="updated") or []
            issues += batch
            if len(batch) < 100:
                break
            page += 1
        comments_by_issue: dict[int, list] = {}
        for c in gh.get(f"/repos/{full}/issues/comments", per_page=100, sort="created", direction="desc") or []:
            n = int(c["issue_url"].rsplit("/", 1)[1])
            comments_by_issue.setdefault(n, []).append(c)
        for it in issues[:max_issues]:
            user = (it.get("user") or {}).get("login")
            if is_bot(user):
                continue
            people[user] += 1
            for lb in it.get("labels", []):
                labels[lb["name"].lower()] = lb["name"]
            ms = it.get("milestone")
            if ms:
                milestones[str(ms["id"])] = {"id": f"ms-{ms['id']}", "name": ms["title"], "status": ms["state"],
                                             "summary": (ms.get("description") or "")[:200], "systems": [repo.lower()],
                                             "lead": (ms.get("creator") or {}).get("login")}
            assignee = (it.get("assignee") or {}).get("login")
            assignee = None if is_bot(assignee) else assignee
            if assignee:
                people[assignee] += 1
            key = f"{repo.upper()}-{it['number']}"
            kind = "PR" if "pull_request" in it else "Issue"
            comments = []
            for i, c in enumerate(sorted(comments_by_issue.get(it["number"], []), key=lambda c: c["created_at"])):
                cu = (c.get("user") or {}).get("login")
                if is_bot(cu):
                    continue
                people[cu] += 1
                comments.append({"id": f"{key}-c{i + 1}", "author": cu, "ts": iso(c["created_at"]),
                                 "text": (c.get("body") or "")[:2000], "url": c["html_url"]})
            tickets.append({
                "key": key, "project": f"ms-{ms['id']}" if ms else None,
                "title": f"[{kind}] {it['title']}", "assignee": assignee, "reporter": user,
                "components": [repo.lower()], "status": "done" if it["state"] == "closed" else "open",
                "created": iso(it["created_at"]), "closed": iso(it.get("closed_at")),
                "description": ((it.get("body") or "")[:3000]) + (" Labels: " + ", ".join(l["name"] for l in it["labels"]) if it["labels"] else ""),
                "comments": comments, "source": "github", "url": it["html_url"],
            })
    all_ts = [t["created"] for t in tickets] + [c["ts"] for t in tickets for c in t["comments"]]
    org_json = {
        "company": f"{org} (public GitHub)",
        "now": max(all_ts) if all_ts else None,
        "teams": [{"id": "team-contributors", "name": "Contributors team"}],
        "people": [{"id": login.lower(), "name": login, "handle": login, "team": "team-contributors",
                    "role": "contributor", "left_at": None} for login, _ in people.most_common()],
        "systems": systems,
        "projects": [m for m in milestones.values() if m["lead"]] ,
        "topics": [{"id": re.sub(r"[^a-z0-9]+", "-", k).strip("-") or "label", "name": v, "keywords": [k]} for k, v in labels.items()],
    }
    for p in org_json["projects"]:
        p["lead"] = p["lead"].lower()
    for t in tickets:
        t["assignee"] = t["assignee"].lower() if t["assignee"] else None
        t["reporter"] = t["reporter"].lower()
        for c in t["comments"]:
            c["author"] = c["author"].lower()
    return {"org": org_json, "docs": docs, "tickets": tickets, "chat": [], "meetings": []}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", required=True)
    ap.add_argument("--repos", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-issues", type=int, default=150)
    a = ap.parse_args()
    data = fetch(a.org, a.repos, a.max_issues)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for k, v in data.items():
        (out / f"{k}.json").write_text(json.dumps(v, indent=2), encoding="utf-8")
    print(f"{a.org}: {len(data['org']['people'])} people, {len(data['docs'])} docs, {len(data['tickets'])} tickets -> {out}")


if __name__ == "__main__":
    main()
