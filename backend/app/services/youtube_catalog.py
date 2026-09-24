"""Collect metadata only; commit each successful batch before requesting more."""

import logging
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from sqlalchemy import literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Video
from app.services.youtube_client import VideoMetadata, YouTubeClient, YouTubeError

logger = logging.getLogger(__name__)


def active_catalog_query():
    """Shared eligibility predicate for active catalog consumers."""
    return select(Video).where(
        Video.availability_status == "active", Video.embeddable.is_(True)
    )

# Discovery terms only: these do not assign any taxonomy labels.
SEED_QUERIES = (
    "ASMR tapping",
    "ASMR scratching",
    "ASMR brushing",
    "ASMR crinkling",
    "ASMR rubbing",
    "ASMR water sounds",
    "ASMR mouth sounds",
    "ASMR chewing",
    "ASMR typing",
    "ASMR cutting",
    "ASMR page turning",
    "ASMR blowing",
    "ASMR whisper",
    "ASMR soft spoken",
    "ASMR no talking",
    "ASMR hand movements",
    "ASMR light triggers",
    "ASMR personal attention",
    "ASMR roleplay",
    "ASMR 한국어 소리",
    "ASMR English",
    "ASMR 日本語 音",
)
_DURATION = re.compile(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?")


@dataclass
class CollectionResult:
    queries: int = 0
    # Logical API requests, excluding retries performed inside YouTubeClient.
    api_calls: int = 0
    candidates: int = 0
    inserted: int = 0
    updated: int = 0
    duplicates: int = 0
    rejected: int = 0
    unavailable: int = 0
    rejection_reasons: Counter = field(default_factory=Counter)
    failures: Counter = field(default_factory=Counter)
    stopped: bool = False


def duration_seconds(value: str | None) -> int | None:
    match = _DURATION.fullmatch(value or "")
    if not match or not any(match.groups()) or (value or "").endswith("T"):
        return None
    # Avoid pathological numeric input and PostgreSQL INTEGER overflow.
    if any(len(part) > 10 for part in match.groups() if part):
        return None
    seconds = sum(
        int(part or 0) * scale
        for part, scale in zip(match.groups(), (86400, 3600, 60, 1))
    )
    return seconds if 0 < seconds <= 2147483647 else None


def normalized_language(value: str | None) -> str | None:
    if not value or not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", value):
        return None
    primary = value.split("-", 1)[0].lower()
    return None if primary in {"und", "zxx", "mul"} else primary


def video_row(
    video: VideoMetadata, synced_at: datetime
) -> tuple[dict | None, str | None]:
    snippet = video.snippet
    if video.status.privacy_status != "public":
        return None, "not_public"
    if video.status.embeddable is not True:
        return None, "not_embeddable"
    if video.status.upload_status not in {None, "processed"}:
        return None, "not_processed"
    if (
        not re.fullmatch(r"[A-Za-z0-9_-]{1,20}", video.id)
        or not snippet.title.strip()
        or not snippet.channel_id.strip()
        or len(snippet.channel_id) > 64
        or not snippet.channel_title.strip()
        or snippet.published_at.utcoffset() is None
    ):
        return None, "invalid_metadata"
    duration = duration_seconds(video.content_details.duration)
    if duration is None:
        return None, "invalid_duration"
    evidence = unicodedata.normalize(
        "NFKC", " ".join([snippet.title, snippet.description, *snippet.tags])
    ).casefold()
    if not re.search(r"(?<![a-z])asmr(?![a-z])", evidence):
        return None, "no_asmr_evidence"
    thumbnail = next(
        (
            snippet.thumbnails[key].url
            for key in ("maxres", "standard", "high", "medium", "default")
            if key in snippet.thumbnails
            and snippet.thumbnails[key].url.startswith("https://")
        ),
        None,
    )
    return {
        "youtube_video_id": video.id,
        "title": snippet.title,
        "description": snippet.description,
        "channel_id": snippet.channel_id,
        "channel_name": snippet.channel_title,
        "thumbnail_url": thumbnail,
        "duration_sec": duration,
        "language": normalized_language(
            snippet.default_audio_language or snippet.default_language
        ),
        "published_at": snippet.published_at,
        "embeddable": True,
        "availability_status": "active",
        "last_synced_at": synced_at,
    }, None


def upsert_videos(session: Session, rows: list[dict]) -> tuple[int, int]:
    """Atomic PostgreSQL upsert; preserve primary keys, created_at and relations."""
    if not rows:
        return 0, 0
    statement = insert(Video).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[Video.youtube_video_id],
        set_={
            key: statement.excluded[key] for key in rows[0] if key != "youtube_video_id"
        },
    ).returning(literal_column("xmax = 0").label("inserted"))
    outcomes = list(session.execute(statement).scalars())
    inserted = sum(bool(value) for value in outcomes)
    return inserted, len(outcomes) - inserted


def collect_catalog(
    client: YouTubeClient,
    session: Session,
    queries: Iterable[str] = SEED_QUERIES,
    *,
    pages_per_query: int = 1,
) -> CollectionResult:
    """Use a dedicated session: each metadata batch is its own transaction."""
    if pages_per_query < 1:
        raise ValueError("pages_per_query must be positive")
    result = CollectionResult()
    seen: set[str] = set()
    try:
        for query in queries:
            if not query.strip():
                raise ValueError("Seed queries must not be blank")
            result.queries += 1
            logger.info("youtube_catalog query=%s", query)
            token = None
            for _ in range(pages_per_query):
                result.api_calls += 1
                page = client.search_videos(query, page_token=token)
                ids = []
                for video_id in page.video_ids:
                    result.candidates += 1
                    if video_id in seen:
                        result.duplicates += 1
                    else:
                        seen.add(video_id)
                        ids.append(video_id)
                batches = iter(client.iter_video_batches(ids))
                for _ in range(0, len(ids), 50):
                    result.api_calls += 1
                    batch = next(batches)
                    rows = []
                    result.unavailable += len(batch.missing_ids)
                    result.rejected += len(batch.missing_ids)
                    result.rejection_reasons["not_retrievable"] += len(
                        batch.missing_ids
                    )
                    for video in batch.videos:
                        row, reason = video_row(video, datetime.now(timezone.utc))
                        if row is None:
                            result.rejected += 1
                            result.rejection_reasons[reason] += 1
                        else:
                            rows.append(row)
                    try:
                        inserted, updated = upsert_videos(session, rows)
                        session.commit()
                    except Exception:
                        session.rollback()
                        result.failures["database"] += 1
                        raise
                    result.inserted += inserted
                    result.updated += updated
                token = page.next_page_token
                if not token:
                    break
    except YouTubeError as exc:
        result.stopped = True
        result.failures[exc.reason] += 1
        logger.warning(
            "youtube_catalog stopped reason=%s status=%s", exc.reason, exc.status_code
        )
    finally:
        logger.info("youtube_catalog result=%s", asdict(result))
    return result
