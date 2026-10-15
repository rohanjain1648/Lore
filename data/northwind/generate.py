"""Generate the synthetic "Northwind Labs" company dataset.

Everything here is fictional. The story threads are hand-written so the demo and the
eval have known ground truth; routine "background" chatter, tickets and comments are
generated from templates with a fixed seed so every run produces identical files.

Planted facts (see eval/golden.yaml):
  F1  payments-service ownership moved Payments -> Platform on 2026-06-15; the runbook
      still names Priya/Payments (stale doc).
  F2  search-api moved Platform -> Growth on 2026-04-02; Team Directory is stale on it.
  F3  Decision: FalkorDB (not Neo4j) as the graph store for recs-engine, 2026-03-12,
      based on benchmark ticket ATL-14.
  F4  Friday deploy freeze: policy (Jan) -> lifted (May) -> reinstated after INC-7 (Aug).
  F5  REST -> gRPC for internal calls (Feb), partially reverted for mobile APIs (Jul).
  F6  auth-gateway bus factor: Sam Okafor did most of the work and left on 2026-07-31.
  F7  Aiko Tanaka is the Kafka / data-pipeline expert.

Run:  python data/northwind/generate.py
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).parent / "raw"
WIKI = "https://wiki.northwind.example"
TRACKER = "https://tracker.northwind.example"
CHAT = "https://chat.northwind.example"

rng = random.Random(42)

# --------------------------------------------------------------------------------------
# Org
# --------------------------------------------------------------------------------------
TEAMS = [
    {"id": "team-leadership", "name": "Leadership"},
    {"id": "team-platform", "name": "Platform team"},
    {"id": "team-payments", "name": "Payments team"},
    {"id": "team-growth", "name": "Growth team"},
    {"id": "team-data", "name": "Data team"},
    {"id": "team-sre", "name": "SRE team"},
    {"id": "team-mobile", "name": "Mobile team"},
]

PEOPLE = [
    # id, name, handle, team, role, left_at
    ("dev.patel", "Dev Patel", "dev", "team-leadership", "CTO", None),
    ("nora.fischer", "Nora Fischer", "nora", "team-leadership", "VP Engineering", None),
    ("marco.rossi", "Marco Rossi", "marco", "team-platform", "Engineering Manager, Platform", None),
    ("sam.okafor", "Sam Okafor", "sam", "team-platform", "Senior Engineer", "2026-07-31"),
    ("jonas.weber", "Jonas Weber", "jonas", "team-platform", "Engineer", None),
    ("mei.lin", "Mei Lin", "mei", "team-platform", "Junior Engineer", None),
    ("priya.sharma", "Priya Sharma", "priya", "team-payments", "Engineering Manager, Payments", None),
    ("carlos.mendes", "Carlos Mendes", "carlos", "team-payments", "Senior Engineer", None),
    ("fatima.zahra", "Fatima Zahra", "fatima", "team-payments", "Engineer", None),
    ("lena.novak", "Lena Novak", "lena", "team-growth", "Tech Lead, Growth", None),
    ("arjun.mehta", "Arjun Mehta", "arjun", "team-growth", "ML Engineer", None),
    ("chloe.dubois", "Chloe Dubois", "chloe", "team-growth", "Engineer", None),
    ("aiko.tanaka", "Aiko Tanaka", "aiko", "team-data", "Staff Data Engineer", None),
    ("ben.carter", "Ben Carter", "ben", "team-data", "Data Engineer", None),
    ("olu.adeyemi", "Olu Adeyemi", "olu", "team-sre", "SRE Lead", None),
    ("hannah.kim", "Hannah Kim", "hannah", "team-sre", "SRE", None),
    ("diego.alvarez", "Diego Alvarez", "diego", "team-mobile", "Mobile Lead", None),
    ("sara.lindqvist", "Sara Lindqvist", "sara", "team-mobile", "iOS Engineer", None),
]

SYSTEMS = [
    {"id": "payments-service", "name": "payments-service", "kind": "service", "aliases": ["payments service", "payment service", "payments api"]},
    {"id": "auth-gateway", "name": "auth-gateway", "kind": "service", "aliases": ["auth gateway", "auth service", "sso gateway"]},
    {"id": "recs-engine", "name": "recs-engine", "kind": "service", "aliases": ["recs engine", "recommendation engine", "recommendations engine", "recommendations service"]},
    {"id": "checkout-web", "name": "checkout-web", "kind": "frontend", "aliases": ["checkout web", "web checkout", "checkout frontend"]},
    {"id": "data-pipeline", "name": "data-pipeline", "kind": "infra", "aliases": ["data pipeline", "event pipeline", "kafka pipeline"]},
    {"id": "deploy-pipeline", "name": "deploy-pipeline", "kind": "infra", "aliases": ["deploy pipeline", "ci/cd", "release pipeline"]},
    {"id": "mobile-app", "name": "mobile-app", "kind": "client", "aliases": ["mobile app", "ios app", "android app"]},
    {"id": "search-api", "name": "search-api", "kind": "service", "aliases": ["search api", "search service"]},
]

PROJECTS = [
    {"id": "atlas", "name": "Project Atlas", "status": "active", "summary": "Recommendations v2 on a graph store.", "systems": ["recs-engine", "data-pipeline"], "lead": "lena.novak"},
    {"id": "ledger", "name": "Project Ledger", "status": "active", "summary": "Payments re-platform and PCI scope reduction.", "systems": ["payments-service"], "lead": "priya.sharma"},
    {"id": "shield", "name": "Project Shield", "status": "at-risk", "summary": "Auth hardening, SSO and token rotation.", "systems": ["auth-gateway"], "lead": "sam.okafor"},
    {"id": "swift", "name": "Project Swift", "status": "active", "summary": "One-tap mobile checkout.", "systems": ["mobile-app", "checkout-web"], "lead": "diego.alvarez"},
    {"id": "beacon", "name": "Project Beacon", "status": "active", "summary": "Observability and safer releases.", "systems": ["deploy-pipeline"], "lead": "olu.adeyemi"},
]

TOPICS = [
    {"id": "kafka", "name": "Kafka", "keywords": ["kafka", "consumer lag", "topic partition", "event stream"]},
    {"id": "graph-database", "name": "Graph databases", "keywords": ["falkordb", "neo4j", "graph store", "graph database", "cypher"]},
    {"id": "deploy-policy", "name": "Deploy policy", "keywords": ["deploy freeze", "friday deploy", "friday deploys", "deploys on fridays", "release window", "canary"]},
    {"id": "api-protocol", "name": "API protocol (REST/gRPC)", "keywords": ["grpc", "grpc-web", "protobuf", "rest api", "back to rest"]},
    {"id": "sso", "name": "SSO and tokens", "keywords": ["sso", "oauth", "token rotation", "jwt", "saml"]},
    {"id": "observability", "name": "Observability", "keywords": ["tracing", "dashboards", "alerting", "slo", "opentelemetry"]},
    {"id": "pci", "name": "PCI compliance", "keywords": ["pci", "card data", "tokenization", "compliance audit"]},
    {"id": "idempotency", "name": "Idempotency", "keywords": ["idempotency", "duplicate charge", "retry storm", "exactly-once"]},
]

TEAM_SYSTEMS_JAN = {
    "team-payments": ["payments-service", "checkout-web"],
    "team-platform": ["auth-gateway", "search-api"],
    "team-growth": ["recs-engine"],
    "team-data": ["data-pipeline"],
    "team-sre": ["deploy-pipeline"],
    "team-mobile": ["mobile-app"],
}
PERSON_SYSTEMS = {  # who works on what (drives background chatter)
    "marco.rossi": ["auth-gateway", "search-api", "payments-service"],
    "sam.okafor": ["auth-gateway"],
    "jonas.weber": ["search-api", "payments-service"],
    "mei.lin": ["auth-gateway"],
    "priya.sharma": ["payments-service"],
    "carlos.mendes": ["payments-service", "checkout-web"],
    "fatima.zahra": ["checkout-web", "payments-service"],
    "lena.novak": ["recs-engine", "search-api"],
    "arjun.mehta": ["recs-engine"],
    "chloe.dubois": ["recs-engine", "search-api"],
    "aiko.tanaka": ["data-pipeline"],
    "ben.carter": ["data-pipeline"],
    "olu.adeyemi": ["deploy-pipeline"],
    "hannah.kim": ["deploy-pipeline"],
    "diego.alvarez": ["mobile-app", "checkout-web"],
    "sara.lindqvist": ["mobile-app"],
}
SYSTEM_TOPICS = {
    "payments-service": ["idempotency", "pci"],
    "auth-gateway": ["sso"],
    "recs-engine": ["graph-database"],
    "checkout-web": ["idempotency"],
    "data-pipeline": ["kafka"],
    "deploy-pipeline": ["observability", "deploy-policy"],
    "mobile-app": ["api-protocol"],
    "search-api": ["observability"],
}

START = datetime(2026, 1, 5, 9, 0)
END = datetime(2026, 9, 30, 18, 0)


def iso(d: datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%S")


def person_left(pid: str) -> datetime | None:
    for p in PEOPLE:
        if p[0] == pid and p[5]:
            return datetime.fromisoformat(p[5])
    return None


# --------------------------------------------------------------------------------------
# Documents (wiki)
# --------------------------------------------------------------------------------------
DOCS = [
    {
        "id": "doc-team-directory",
        "title": "Engineering Team Directory",
        "author": "nora.fischer",
        "updated_at": "2026-01-10T10:00:00",
        "body": """# Engineering Team Directory

Who to talk to for each system. Keep this page current.

## Ownership
The Payments team owns payments-service. Contact Priya Sharma.
The Payments team owns checkout-web.
The Platform team owns auth-gateway. Sam Okafor is the primary engineer.
The Platform team owns search-api.
The Growth team owns recs-engine.
The Data team owns data-pipeline. Aiko Tanaka runs the Kafka cluster.
The SRE team owns deploy-pipeline.
The Mobile team owns mobile-app.

## Escalation
For production incidents page the on-call SRE first, then the owning team.
""",
    },
    {
        "id": "doc-payments-runbook",
        "title": "Payments Service Runbook",
        "author": "priya.sharma",
        "updated_at": "2026-02-18T15:30:00",
        "body": """# Payments Service Runbook

## Ownership
payments-service is owned by the Payments team. Contact Priya Sharma for anything urgent.

## Retries and idempotency
Every charge request carries an idempotency key. Retries reuse the same key so a retry storm
can never create a duplicate charge. Keys expire after 24 hours.

## PCI
Card data never touches payments-service directly; tokenization happens at the vault.
""",
    },
    {
        "id": "doc-deploy-policy",
        "title": "Deployment Policy",
        "author": "olu.adeyemi",
        "updated_at": "2026-01-20T11:00:00",
        "body": """# Deployment Policy

Policy: no production deploys on Fridays. Changes merged on Friday ship on Monday.

## Release process
All services ship through the deploy-pipeline with automated rollbacks.
Canary releases are recommended for user-facing services.
""",
    },
    {
        "id": "doc-auth-gateway-design",
        "title": "auth-gateway Design Notes",
        "author": "sam.okafor",
        "updated_at": "2026-03-03T09:20:00",
        "body": """# auth-gateway Design Notes

auth-gateway terminates SSO (SAML and OAuth) and issues short-lived JWT access tokens.

## Token rotation
Signing keys rotate every 30 days. The rotation job lives in auth-gateway/rotation and only
Sam Okafor has run it in production so far. The procedure is not automated yet.

## Known sharp edges
The SAML metadata refresh is manual. If it lapses, enterprise SSO logins fail.
""",
    },
    {
        "id": "doc-atlas-architecture",
        "title": "Project Atlas Architecture",
        "author": "lena.novak",
        "updated_at": "2026-03-20T14:00:00",
        "body": """# Project Atlas Architecture

recs-engine v2 models users, items and sessions as a graph and serves recommendations with
multi-hop Cypher queries. Events arrive from the data-pipeline over Kafka.

## Graph store
We use FalkorDB as the graph store for recs-engine, chosen at the Atlas architecture review
on 2026-03-12. See ATL-14 for the benchmark.
""",
    },
    {
        "id": "doc-data-pipeline-guide",
        "title": "Data Pipeline Guide",
        "author": "aiko.tanaka",
        "updated_at": "2026-04-15T10:00:00",
        "body": """# Data Pipeline Guide

The data-pipeline is a Kafka cluster with 3 brokers. Topic partitions are keyed by user id.
Consumer lag alerts fire at 5 minutes.

## Contacts
Aiko Tanaka designed the Kafka topology. Ben Carter handles schema registry changes.
""",
    },
    {
        "id": "doc-api-guidelines",
        "title": "Internal API Guidelines",
        "author": "marco.rossi",
        "updated_at": "2026-02-12T16:00:00",
        "body": """# Internal API Guidelines

Internal service-to-service calls use gRPC with protobuf contracts.
Policy: mobile-facing APIs use gRPC-web through the edge proxy.
""",
    },
    {
        "id": "doc-oncall",
        "title": "On-call Handbook",
        "author": "hannah.kim",
        "updated_at": "2026-05-02T09:00:00",
        "body": """# On-call Handbook

SRE runs primary on-call. Dashboards live in Grafana; tracing uses OpenTelemetry.
Every alert must link to a runbook. SLO burn alerts page immediately.
""",
    },
    {
        "id": "doc-swift-plan",
        "title": "Project Swift Plan",
        "author": "diego.alvarez",
        "updated_at": "2026-04-28T13:00:00",
        "body": """# Project Swift Plan

One-tap checkout in the mobile-app, backed by checkout-web and payments-service.
Launch target: end of Q3. Depends on idempotency guarantees in payments-service.
""",
    },
]

# --------------------------------------------------------------------------------------
# Meetings
# --------------------------------------------------------------------------------------
MEETINGS = [
    {
        "id": "mtg-2026-02-10-arch",
        "title": "Architecture sync: service protocols",
        "date": "2026-02-10T15:00:00",
        "organizer": "marco.rossi",
        "attendees": ["marco.rossi", "sam.okafor", "jonas.weber", "dev.patel", "diego.alvarez", "lena.novak"],
        "notes": """Marco presented the latency numbers for REST between payments-service and search-api.
Decision: migrate internal service-to-service calls from REST to gRPC. Proposed by Marco Rossi, approved by Dev Patel.
Diego raised concerns about gRPC-web on the mobile-app; to be revisited.
Action: Jonas to draft the protobuf contracts.""",
    },
    {
        "id": "mtg-2026-03-12-atlas",
        "title": "Atlas architecture review",
        "date": "2026-03-12T14:00:00",
        "organizer": "lena.novak",
        "attendees": ["lena.novak", "arjun.mehta", "chloe.dubois", "aiko.tanaka", "dev.patel"],
        "notes": """Arjun walked through the benchmark in ATL-14: FalkorDB answered 3-hop recommendation queries about 4x faster than Neo4j on our sample.
Decision: use FalkorDB as the graph store for recs-engine instead of Neo4j. Proposed by Lena Novak, approved by Dev Patel.
Aiko confirmed the data-pipeline can stream events into the graph through Kafka.
Action: Chloe to set up the FalkorDB cluster.""",
    },
    {
        "id": "mtg-2026-05-08-release",
        "title": "Release process review",
        "date": "2026-05-08T11:00:00",
        "organizer": "olu.adeyemi",
        "attendees": ["olu.adeyemi", "hannah.kim", "nora.fischer", "marco.rossi", "priya.sharma"],
        "notes": """Canary releases have been stable for two months with automated rollback.
Decision: lift the Friday deploy freeze; deploys are allowed on Fridays before 2pm with a canary. Proposed by Olu Adeyemi, approved by Nora Fischer.
Hannah will update the deploy-pipeline guardrails.""",
    },
    {
        "id": "mtg-2026-06-15-reorg",
        "title": "Engineering reorg briefing",
        "date": "2026-06-15T10:00:00",
        "organizer": "nora.fischer",
        "attendees": ["nora.fischer", "dev.patel", "marco.rossi", "priya.sharma", "carlos.mendes"],
        "notes": """Payments team will focus on Project Ledger compliance work.
Decision: move ownership of payments-service from the Payments team to the Platform team. Proposed by Nora Fischer, approved by Dev Patel.
Marco Rossi becomes the escalation contact for payments-service.""",
    },
    {
        "id": "mtg-2026-07-22-mobile",
        "title": "Mobile API retro",
        "date": "2026-07-22T16:00:00",
        "organizer": "diego.alvarez",
        "attendees": ["diego.alvarez", "sara.lindqvist", "marco.rossi", "jonas.weber"],
        "notes": """gRPC-web added 40% to mobile-app bundle size and broke two older Android versions.
Decision: revert mobile-facing APIs back to REST; keep gRPC for internal service-to-service calls. Proposed by Diego Alvarez, approved by Marco Rossi.
Jonas to restore the REST endpoints on the edge proxy.""",
    },
    {
        "id": "mtg-2026-08-31-inc7",
        "title": "INC-7 postmortem: Friday checkout outage",
        "date": "2026-08-31T13:00:00",
        "organizer": "olu.adeyemi",
        "attendees": ["olu.adeyemi", "hannah.kim", "nora.fischer", "carlos.mendes", "fatima.zahra", "marco.rossi"],
        "notes": """On Friday 2026-08-28 a checkout-web deploy at 1:40pm passed canary but broke card payments for 3 hours (INC-7).
Decision: reinstate the Friday deploy freeze after the INC-7 checkout outage. Proposed by Olu Adeyemi, approved by Nora Fischer.
Fatima to add an idempotency check to the canary analysis.""",
    },
    {
        "id": "mtg-2026-08-05-shield",
        "title": "Project Shield status",
        "date": "2026-08-05T10:00:00",
        "organizer": "marco.rossi",
        "attendees": ["marco.rossi", "mei.lin", "jonas.weber", "nora.fischer"],
        "notes": """Sam Okafor left on 2026-07-31. Mei Lin is picking up auth-gateway but has not run token rotation yet.
Shield is at risk: the SAML metadata refresh and key rotation were only ever done by Sam.
Action: Marco to find a second engineer for auth-gateway.""",
    },
]

# --------------------------------------------------------------------------------------
# Chat threads (story)
# --------------------------------------------------------------------------------------
STORY_THREADS = [
    {
        "id": "th-atlas-graphstore",
        "channel": "proj-atlas",
        "messages": [
            ("arjun.mehta", "2026-03-05T10:12:00", "Benchmark for recs-engine is up in ATL-14. FalkorDB vs Neo4j on 3-hop queries over the event graph."),
            ("lena.novak", "2026-03-05T10:20:00", "Nice. FalkorDB numbers look about 4x better on p95. Let's take it to the Atlas architecture review."),
            ("chloe.dubois", "2026-03-05T10:31:00", "Memory footprint is lower too. Cypher support covers everything we need."),
            ("aiko.tanaka", "2026-03-05T11:02:00", "From the data-pipeline side, Kafka consumers can write to either. No blocker."),
        ],
    },
    {
        "id": "th-search-handover",
        "channel": "eng-announcements",
        "messages": [
            ("lena.novak", "2026-04-02T09:30:00", "Heads up: search-api is now owned by the Growth team. Ranking work lives with recs, so it makes sense. Ping me or Chloe."),
            ("marco.rossi", "2026-04-02T09:41:00", "Confirmed from Platform side, handover doc is in the tracker."),
        ],
    },
    {
        "id": "th-payments-reorg",
        "channel": "eng-announcements",
        "messages": [
            ("nora.fischer", "2026-06-15T12:00:00", "Reorg update: payments-service is now owned by the Platform team. Marco Rossi is the escalation contact. Payments team focuses on Ledger compliance."),
            ("priya.sharma", "2026-06-15T12:08:00", "Thanks Nora. I'll walk Marco's team through the idempotency internals this week."),
            ("marco.rossi", "2026-06-15T12:15:00", "Welcome payments-service to Platform. Jonas will be primary on-call for it."),
        ],
    },
    {
        "id": "th-friday-deploys",
        "channel": "sre",
        "messages": [
            ("hannah.kim", "2026-05-08T14:00:00", "Friday deploys are allowed again before 2pm, canary required. Guardrails are live in the deploy-pipeline."),
            ("carlos.mendes", "2026-05-08T14:05:00", "Great, that unblocks the payments-service hotfix train."),
        ],
    },
    {
        "id": "th-inc7",
        "channel": "incidents",
        "messages": [
            ("hannah.kim", "2026-08-28T13:52:00", "INC-7: card payments failing at checkout. Rolling back the 1:40pm checkout-web deploy."),
            ("fatima.zahra", "2026-08-28T14:30:00", "Root cause: checkout-web sent a new payload shape that payments-service rejected. Canary only covered the browse flow."),
            ("olu.adeyemi", "2026-08-28T17:10:00", "Resolved after 3 hours. Postmortem Monday. I'm going to propose bringing back the Friday deploy freeze."),
        ],
    },
    {
        "id": "th-sam-leaving",
        "channel": "platform",
        "messages": [
            ("sam.okafor", "2026-07-20T10:00:00", "As you know my last day is July 31. I'm writing up the auth-gateway token rotation steps but the SAML refresh is still manual."),
            ("mei.lin", "2026-07-20T10:15:00", "I can shadow the next token rotation. I haven't touched the SAML metadata job yet."),
            ("marco.rossi", "2026-07-20T10:20:00", "Thanks Sam. Mei, let's pair on auth-gateway next week."),
        ],
    },
    {
        "id": "th-kafka-lag",
        "channel": "data",
        "messages": [
            ("ben.carter", "2026-06-03T09:10:00", "Consumer lag on the recs topic is climbing again, 7 minutes."),
            ("aiko.tanaka", "2026-06-03T09:18:00", "It's the partition skew from the user-id key. I'll rebalance the topic partitions on the data-pipeline; we need 12 instead of 6."),
            ("aiko.tanaka", "2026-06-03T11:40:00", "Rebalanced. Kafka consumer lag back under 30s."),
        ],
    },
    {
        "id": "th-grpc-mobile",
        "channel": "mobile",
        "messages": [
            ("sara.lindqvist", "2026-07-10T15:00:00", "gRPC-web is adding 40% to the mobile-app bundle. Older Android builds crash on the streaming calls."),
            ("diego.alvarez", "2026-07-10T15:12:00", "Let's put a rollback to REST for mobile on the retro agenda."),
        ],
    },
]

# --------------------------------------------------------------------------------------
# Tickets (story)
# --------------------------------------------------------------------------------------
STORY_TICKETS = [
    {"key": "ATL-14", "project": "atlas", "title": "Benchmark FalkorDB vs Neo4j for recs-engine", "assignee": "arjun.mehta", "reporter": "lena.novak",
     "components": ["recs-engine"], "status": "done", "created": "2026-02-25T10:00:00", "closed": "2026-03-05T10:00:00",
     "description": "Compare graph stores for recs-engine 3-hop queries. Result: FalkorDB p95 4x lower than Neo4j, lower memory.",
     "comments": [("chloe.dubois", "2026-03-04T12:00:00", "Added the memory numbers, FalkorDB uses less RAM on the same graph.")]},
    {"key": "ATL-21", "project": "atlas", "title": "Set up FalkorDB cluster for recs-engine", "assignee": "chloe.dubois", "reporter": "lena.novak",
     "components": ["recs-engine"], "status": "done", "created": "2026-03-13T09:00:00", "closed": "2026-03-27T17:00:00",
     "description": "Implements the Atlas architecture review decision to use FalkorDB as the graph store.", "comments": []},
    {"key": "PLAT-88", "project": "ledger", "title": "Handover payments-service to Platform", "assignee": "marco.rossi", "reporter": "nora.fischer",
     "components": ["payments-service"], "status": "done", "created": "2026-06-15T13:00:00", "closed": "2026-06-30T17:00:00",
     "description": "payments-service is now owned by the Platform team. Transfer on-call, dashboards and runbooks.",
     "comments": [("priya.sharma", "2026-06-20T10:00:00", "Walked Jonas and Marco through idempotency keys and the PCI boundary.")]},
    {"key": "SHD-31", "project": "shield", "title": "Automate auth-gateway signing key rotation", "assignee": "sam.okafor", "reporter": "sam.okafor",
     "components": ["auth-gateway"], "status": "open", "created": "2026-05-12T10:00:00", "closed": None,
     "description": "Token rotation is a manual script only Sam has run. Automate it before the next rotation.",
     "comments": [("mei.lin", "2026-08-06T11:00:00", "Picking this up after Sam's departure. Need someone who has done a rotation to review.")]},
    {"key": "SHD-35", "project": "shield", "title": "Automate SAML metadata refresh", "assignee": "mei.lin", "reporter": "marco.rossi",
     "components": ["auth-gateway"], "status": "open", "created": "2026-08-05T12:00:00", "closed": None,
     "description": "SAML metadata refresh is manual; if it lapses enterprise SSO fails.", "comments": []},
    {"key": "PLAT-61", "project": "ledger", "title": "Draft protobuf contracts for internal gRPC", "assignee": "jonas.weber", "reporter": "marco.rossi",
     "components": ["payments-service", "search-api"], "status": "done", "created": "2026-02-11T09:00:00", "closed": "2026-03-10T17:00:00",
     "description": "Implements the decision to migrate internal service-to-service calls from REST to gRPC.", "comments": []},
    {"key": "MOB-140", "project": "swift", "title": "Restore REST endpoints for mobile-app", "assignee": "jonas.weber", "reporter": "diego.alvarez",
     "components": ["mobile-app"], "status": "done", "created": "2026-07-23T09:00:00", "closed": "2026-08-07T17:00:00",
     "description": "Implements the decision to revert mobile-facing APIs back to REST.", "comments": []},
    {"key": "INC-7", "project": "swift", "title": "Checkout outage: card payments failing", "assignee": "hannah.kim", "reporter": "hannah.kim",
     "components": ["checkout-web", "payments-service"], "status": "done", "created": "2026-08-28T13:50:00", "closed": "2026-08-28T17:10:00",
     "description": "Friday 1:40pm checkout-web deploy broke card payments for 3 hours. Canary missed the payment flow.",
     "comments": [("fatima.zahra", "2026-08-28T14:30:00", "Payload shape mismatch between checkout-web and payments-service.")]},
    {"key": "SRE-52", "project": "beacon", "title": "Friday deploy guardrails in deploy-pipeline", "assignee": "hannah.kim", "reporter": "olu.adeyemi",
     "components": ["deploy-pipeline"], "status": "done", "created": "2026-05-08T12:00:00", "closed": "2026-05-15T17:00:00",
     "description": "Allow Friday deploys before 2pm with canary, per the release process review.", "comments": []},
    {"key": "SRE-71", "project": "beacon", "title": "Re-enable Friday deploy freeze", "assignee": "olu.adeyemi", "reporter": "olu.adeyemi",
     "components": ["deploy-pipeline"], "status": "done", "created": "2026-08-31T15:00:00", "closed": "2026-09-02T17:00:00",
     "description": "Reinstate the Friday deploy freeze after INC-7.", "comments": []},
    {"key": "DATA-19", "project": "atlas", "title": "Rebalance recs Kafka topic partitions", "assignee": "aiko.tanaka", "reporter": "ben.carter",
     "components": ["data-pipeline"], "status": "done", "created": "2026-06-03T09:15:00", "closed": "2026-06-03T11:45:00",
     "description": "Consumer lag from partition skew; move from 6 to 12 partitions.", "comments": []},
]

# --------------------------------------------------------------------------------------
# Background generation
# --------------------------------------------------------------------------------------
CHATTER = [
    "Pushed a fix for {sys} retry handling, should cut the error rate.",
    "Anyone seeing latency spikes on {sys} this morning?",
    "Reviewed the {sys} PR, left a couple of comments on the {topic} part.",
    "Added dashboards for {sys}; {topic} metrics are in the second row.",
    "{sys} release went out cleanly.",
    "Pairing on {sys} {topic} edge cases this afternoon if anyone wants to join.",
    "Wrote up notes on how {sys} handles {topic}.",
    "Flaky test in {sys} again, quarantining it.",
    "Bumped dependencies in {sys}.",
    "Load test on {sys} passed at 2x peak.",
]
TICKET_TITLES = [
    "Improve {topic} handling in {sys}",
    "Fix flaky integration test in {sys}",
    "Add alerting for {sys}",
    "Upgrade runtime for {sys}",
    "Investigate p99 latency regression in {sys}",
    "Document {topic} behaviour of {sys}",
]
TOPIC_WORDS = {
    "kafka": "Kafka consumer lag", "graph-database": "Cypher query", "deploy-policy": "canary",
    "api-protocol": "gRPC", "sso": "token rotation", "observability": "tracing",
    "pci": "PCI tokenization", "idempotency": "idempotency",
}
# extra weight for the people the story says are the real experts
ACTIVITY = {"sam.okafor": 3.0, "aiko.tanaka": 2.5, "carlos.mendes": 1.6, "chloe.dubois": 1.4, "olu.adeyemi": 1.3, "mei.lin": 0.25}


def rand_time(lo: datetime, hi: datetime) -> datetime:
    span = (hi - lo).total_seconds()
    d = lo + timedelta(seconds=rng.random() * span)
    return d.replace(hour=rng.randint(9, 17), minute=rng.randint(0, 59), second=0)


def background():
    threads, tickets = [], []
    n_thread = 0
    for pid, systems in PERSON_SYSTEMS.items():
        left = person_left(pid)
        hi = left or END
        n = int(10 * ACTIVITY.get(pid, 1.0))
        for _ in range(n):
            sys_id = rng.choice(systems)
            topic = TOPIC_WORDS[rng.choice(SYSTEM_TOPICS[sys_id])]
            ts = rand_time(START, hi)
            # payments-service work by Platform only after the reorg, by Payments mostly before it
            if sys_id == "payments-service" and pid in ("marco.rossi", "jonas.weber") and ts < datetime(2026, 6, 15):
                ts = rand_time(datetime(2026, 6, 16), END)
            n_thread += 1
            text = rng.choice(CHATTER).format(sys=sys_id, topic=topic)
            threads.append({"id": f"th-bg-{n_thread:03d}", "channel": sys_id, "messages": [(pid, iso(ts), text)]})
        n_t = max(1, int(3 * ACTIVITY.get(pid, 1.0)))
        for i in range(n_t):
            sys_id = rng.choice(systems)
            topic = TOPIC_WORDS[rng.choice(SYSTEM_TOPICS[sys_id])]
            created = rand_time(START, hi - timedelta(days=3))
            if sys_id == "payments-service" and pid in ("marco.rossi", "jonas.weber") and created < datetime(2026, 6, 15):
                created = rand_time(datetime(2026, 6, 16), END - timedelta(days=5))
            closed = created + timedelta(days=rng.randint(1, 12))
            status = "done" if closed < END and rng.random() < 0.8 else "open"
            proj = next((p["id"] for p in PROJECTS if sys_id in p["systems"]), "beacon")
            tickets.append({
                "key": f"BG-{len(tickets) + 100}", "project": proj,
                "title": rng.choice(TICKET_TITLES).format(sys=sys_id, topic=topic),
                "assignee": pid, "reporter": pid, "components": [sys_id], "status": status,
                "created": iso(created), "closed": iso(closed) if status == "done" else None,
                "description": f"Work item on {sys_id} ({topic}).", "comments": [],
            })
    return threads, tickets


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bg_threads, bg_tickets = background()

    org = {
        "company": "Northwind Labs",
        "now": iso(END),
        "teams": TEAMS,
        "people": [
            {"id": p[0], "name": p[1], "handle": p[2], "team": p[3], "role": p[4], "left_at": p[5]}
            for p in PEOPLE
        ],
        "systems": SYSTEMS,
        "projects": PROJECTS,
        "topics": TOPICS,
    }
    docs = [{**d, "url": f"{WIKI}/{d['id']}", "source": "wiki"} for d in DOCS]
    meetings = [{**m, "url": f"{WIKI}/meetings/{m['id']}", "source": "meetings"} for m in MEETINGS]

    def thread_out(t):
        return {
            "id": t["id"], "channel": t["channel"], "source": "chat",
            "url": f"{CHAT}/{t['channel']}/{t['id']}",
            "messages": [
                {"id": f"{t['id']}-m{i + 1}", "author": a, "ts": ts, "text": txt,
                 "url": f"{CHAT}/{t['channel']}/{t['id']}#m{i + 1}"}
                for i, (a, ts, txt) in enumerate(t["messages"])
            ],
        }

    chat = [thread_out(t) for t in STORY_THREADS + bg_threads]

    def ticket_out(t):
        return {
            **t, "source": "tracker", "url": f"{TRACKER}/{t['key']}",
            "comments": [
                {"id": f"{t['key']}-c{i + 1}", "author": a, "ts": ts, "text": txt, "url": f"{TRACKER}/{t['key']}#c{i + 1}"}
                for i, (a, ts, txt) in enumerate(t["comments"])
            ],
        }

    tickets = [ticket_out(t) for t in STORY_TICKETS + bg_tickets]

    for name, data in [("org", org), ("docs", docs), ("meetings", meetings), ("chat", chat), ("tickets", tickets)]:
        (OUT / f"{name}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    n_msgs = sum(len(t["messages"]) for t in chat)
    print(f"Northwind Labs: {len(org['people'])} people, {len(docs)} docs, {len(meetings)} meetings, "
          f"{len(chat)} threads / {n_msgs} messages, {len(tickets)} tickets -> {OUT}")


if __name__ == "__main__":
    main()
