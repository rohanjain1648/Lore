"""Command line: seed the graph, ask questions, run the eval.

    uv run python -m lore.cli seed [--tenant northwind] [--data ../data/northwind/raw]
    uv run python -m lore.cli ask "Who owns payments-service?"
    uv run python -m lore.cli stats
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

from . import config


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    ap = argparse.ArgumentParser(prog="lore")
    ap.add_argument("--tenant", default=config.DEFAULT_TENANT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seed")
    s.add_argument("--data", default=str(config.DATA_DIR / "northwind" / "raw"))
    a = sub.add_parser("ask")
    a.add_argument("question")
    a.add_argument("--as-of", default=None)
    a.add_argument("--offline", action="store_true", help="force the deterministic agent")
    sub.add_parser("stats")
    args = ap.parse_args()

    if args.cmd == "seed":
        from .ingest import pipeline

        t0 = time.time()
        st = pipeline.seed(args.tenant, Path(args.data))
        print(json.dumps(st, indent=2))
        print(f"seeded tenant '{args.tenant}' in {time.time() - t0:.1f}s")
    elif args.cmd == "ask":
        from . import agent

        res = agent.ask(args.tenant, args.question, as_of=args.as_of, force_offline=args.offline)
        print(res["answer"])
        print("\nSources:")
        for c in res["citations"]:
            print(f"  [{c['sid']}] {c['title']} ({c['kind']}, {c.get('author_name') or c.get('author') or ''}, {c['ts'][:10]}) {c['url']}")
        if res["warnings"]:
            print("\nWarnings:", *res["warnings"], sep="\n  ")
        print(f"\nmode={res['mode']} steps={[s['tool'] for s in res['steps']]}")
    elif args.cmd == "stats":
        from .ingest import pipeline

        print(json.dumps(pipeline.stats(args.tenant), indent=2))


if __name__ == "__main__":
    main()
