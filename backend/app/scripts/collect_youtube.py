"""Run from backend: python -m app.scripts.collect_youtube [--query 'ASMR']."""

import argparse
import logging

from sqlalchemy.orm import Session

from app.database import get_engine
from app.services.youtube_catalog import SEED_QUERIES, collect_catalog
from app.services.youtube_client import YouTubeClient, YouTubeConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect YouTube catalog metadata")
    parser.add_argument("--query", action="append", help="Repeat to override seed queries")
    parser.add_argument("--pages-per-query", type=int, default=1)
    args = parser.parse_args()
    if args.pages_per_query < 1:
        parser.error("--pages-per-query must be positive")
    if args.query and any(not query.strip() for query in args.query):
        parser.error("--query must not be blank")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    with YouTubeClient(YouTubeConfig.from_env()) as client:
        with Session(get_engine()) as session:
            result = collect_catalog(
                client, session, args.query or SEED_QUERIES,
                pages_per_query=args.pages_per_query,
            )
    return 1 if result.stopped else 0


if __name__ == "__main__":
    raise SystemExit(main())
