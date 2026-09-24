"""Run from backend: python -m app.scripts.refresh_youtube [--stale-days 30]."""

import argparse
import logging

from sqlalchemy.orm import Session

from app.database import get_engine
from app.services.youtube_client import YouTubeClient, YouTubeConfig
from app.services.youtube_refresh import refresh_youtube


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stale-days", type=int, choices=range(31), default=30)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    with (
        Session(get_engine()) as session,
        YouTubeClient(YouTubeConfig.from_env()) as client,
    ):
        result = refresh_youtube(client, session, stale_days=args.stale_days)
    return 1 if result.stopped else 0


if __name__ == "__main__":
    raise SystemExit(main())
