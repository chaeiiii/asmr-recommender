"""Refresh stored metadata, retaining unavailable rows and batch progress."""

import logging
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Video
from app.services.youtube_catalog import (
    duration_seconds,
    normalized_language,
    video_row,
)
from app.services.youtube_client import YouTubeClient, YouTubeError

logger = logging.getLogger(__name__)


@dataclass
class RefreshResult:
    api_calls: int = 0
    candidates: int = 0
    updated: int = 0
    unavailable: int = 0
    blocked_embed: int = 0
    failures: Counter = field(default_factory=Counter)
    stopped: bool = False


def refresh_youtube(
    client: YouTubeClient,
    session: Session,
    *,
    stale_days: int = 30,
    now: datetime | None = None,
) -> RefreshResult:
    """Use a dedicated session; commit every successful videos.list batch."""
    if not 0 <= stale_days <= 30:
        raise ValueError("stale_days must be between 0 and 30")
    now = now or datetime.now(timezone.utc)
    if now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    ids = list(
        session.scalars(
            select(Video.youtube_video_id)
            .where(Video.last_synced_at <= now - timedelta(days=stale_days))
            .order_by(Video.id)
        )
    )
    result = RefreshResult(candidates=len(ids))
    batches = iter(client.iter_video_batches(ids))
    try:
        for offset in range(0, len(ids), 50):
            result.api_calls += 1
            batch = next(batches)
            rows = {
                row.youtube_video_id: row
                for row in session.scalars(
                    select(Video).where(
                        Video.youtube_video_id.in_(ids[offset : offset + 50])
                    )
                )
            }
            unavailable = blocked = 0
            for metadata in batch.videos:
                row = rows[metadata.id]
                snippet = metadata.snippet
                row.title = snippet.title
                row.description = snippet.description
                row.channel_id = snippet.channel_id
                row.channel_name = snippet.channel_title
                row.published_at = snippet.published_at
                row.duration_sec = duration_seconds(metadata.content_details.duration)
                row.language = normalized_language(
                    snippet.default_audio_language or snippet.default_language
                )
                row.thumbnail_url = next(
                    (
                        snippet.thumbnails[key].url
                        for key in ("maxres", "standard", "high", "medium", "default")
                        if key in snippet.thumbnails
                        and snippet.thumbnails[key].url.startswith("https://")
                    ),
                    None,
                )
                row.embeddable = metadata.status.embeddable is True
                eligible, _ = video_row(metadata, now)
                if metadata.status.privacy_status != "public":
                    row.availability_status = "unavailable"
                elif not row.embeddable:
                    row.availability_status = "blocked_embed"
                else:
                    row.availability_status = "active" if eligible else "unavailable"
                row.last_synced_at = now
                unavailable += row.availability_status == "unavailable"
                blocked += row.availability_status == "blocked_embed"
            for video_id in batch.missing_ids:
                row = rows[video_id]
                row.availability_status = "unavailable"
                row.embeddable = False
                row.last_synced_at = now
                unavailable += 1
            session.commit()
            result.updated += len(batch.videos) + len(batch.missing_ids)
            result.unavailable += unavailable
            result.blocked_embed += blocked
    except YouTubeError as exc:
        session.rollback()
        result.stopped = True
        result.failures[exc.reason] += 1
    except Exception:
        session.rollback()
        result.failures["database_or_processing"] += 1
        raise
    finally:
        logger.info("youtube_refresh result=%s", asdict(result))
    return result
