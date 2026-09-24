"""Run from backend: python -m app.scripts.tag_videos --help.

Optional --tags-json is a JSON object mapping YouTube video IDs to string lists.
The catalog schema does not persist YouTube tags; supply the same snapshot on
reruns to retain tags supported only by that evidence. No API calls are made.
"""

import argparse
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Video
from app.services.tagging import tag_video


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--tags-json", type=Path)
    parser.add_argument("--video-id", action="append", help="YouTube ID; repeatable")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("Set DATABASE_URL or pass --database-url")
    tags = {}
    if args.tags_json:
        tags = json.loads(args.tags_json.read_text(encoding="utf-8"))
        if not isinstance(tags, dict) or any(
            not isinstance(key, str) or not isinstance(value, list)
            or any(not isinstance(tag, str) for tag in value)
            for key, value in tags.items()
        ):
            parser.error("--tags-json must map YouTube IDs to lists of strings")
    engine = create_engine(args.database_url)
    totals = {"videos": 0, "created": 0, "updated": 0, "deleted": 0}
    try:
        with Session(engine) as session, session.begin():
            query = select(Video).order_by(Video.id)
            if args.video_id:
                query = query.where(Video.youtube_video_id.in_(args.video_id))
            for video in session.scalars(query):
                counts = tag_video(session, video, tags.get(video.youtube_video_id, ()))
                totals["videos"] += 1
                for key, count in counts.items():
                    totals[key] += count
        print(json.dumps(totals, sort_keys=True))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
