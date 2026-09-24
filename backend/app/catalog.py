"""Saved videos, content_v1 exploration, and request-only catalog search."""

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import delete, or_, select

from app.models import (
    Favorite,
    Interaction,
    RecommendationImpression,
    Trigger,
    UserPreference,
    Video,
    VideoTrigger,
)
from app.onboarding import feature_identity
from app.recommender import ALGORITHM_VERSION, SKIP_COOLDOWN, usable_features
from app.sound_test import Database, Identity

router = APIRouter()
RELIABLE_CONFIDENCE = Decimal("0.60")
EXPLORATION_FAMILIES = {"sound", "visual", "format"}


def active_videos():
    return select(Video).where(
        Video.availability_status == "active", Video.embeddable.is_(True)
    )


def feature_map(db):
    features = defaultdict(list)
    for tag, trigger in usable_features(db):
        if tag.confidence >= RELIABLE_CONFIDENCE:
            features[tag.video_id].append((tag, trigger))
    return features


def video_metadata(video, features):
    return {
        "video_id": video.id,
        "youtube_video_id": video.youtube_video_id,
        "title": video.title,
        "description": video.description,
        "channel_id": video.channel_id,
        "channel_name": video.channel_name,
        "thumbnail_url": video.thumbnail_url,
        "duration_sec": video.duration_sec,
        "language": video.language,
        "published_at": video.published_at,
        "features": [
            {**feature_identity(trigger), "confidence": float(tag.confidence)}
            for tag, trigger in features
        ],
    }


@router.post("/videos/{video_id}/favorite")
def add_favorite(video_id: int, user: Identity, db: Database) -> dict:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(
            404, detail={"code": "VIDEO_NOT_FOUND", "message": "Video not found."}
        )
    if video.availability_status != "active" or not video.embeddable:
        raise HTTPException(
            409,
            detail={"code": "VIDEO_UNAVAILABLE", "message": "Video is unavailable."},
        )
    # Identity serializes writes for this cookie's user, including concurrent adds.
    if db.get(Favorite, (user.id, video_id)) is None:
        db.add(
            Favorite(
                user_id=user.id,
                video_id=video_id,
                created_at=datetime.now(timezone.utc),
            )
        )
    db.commit()
    return {"video_id": video_id, "saved": True}


@router.delete("/videos/{video_id}/favorite")
def remove_favorite(video_id: int, user: Identity, db: Database) -> dict:
    db.execute(
        delete(Favorite).where(
            Favorite.user_id == user.id, Favorite.video_id == video_id
        )
    )
    db.commit()
    return {"video_id": video_id, "saved": False}


@router.get("/favorites")
def favorites(user: Identity, db: Database) -> dict:
    videos = db.execute(
        active_videos()
        .add_columns(Favorite.created_at)
        .join(Favorite, Favorite.video_id == Video.id)
        .where(Favorite.user_id == user.id)
        .order_by(Favorite.created_at.desc(), Video.id.desc())
    ).all()
    features = feature_map(db)
    return {
        "items": [
            {**video_metadata(video, features[video.id]), "saved_at": saved_at}
            for video, saved_at in videos
        ]
    }


@router.get("/discover")
def discover(
    user: Identity,
    db: Database,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> dict:
    now = datetime.now(timezone.utc)
    preferences = {
        preference.trigger_id: preference
        for preference in db.scalars(
            select(UserPreference).where(UserPreference.user_id == user.id)
        )
    }
    excluded = set(
        db.scalars(
            select(Interaction.video_id).where(
                Interaction.user_id == user.id,
                (Interaction.type == "dislike")
                | (
                    (Interaction.type == "skip")
                    & (Interaction.created_at >= now - SKIP_COOLDOWN)
                ),
            )
        )
    )
    features = feature_map(db)
    candidates = []
    for video in db.scalars(active_videos()):
        if video.id in excluded:
            continue
        exploration = []
        adjacent = False
        guarded = False
        for tag, trigger in features[video.id]:
            preference = preferences.get(trigger.id)
            score = preference.score if preference is not None else Decimal(0)
            evidence = preference.evidence_count if preference is not None else 0
            if score <= Decimal("-0.80") and tag.confidence >= Decimal("0.80"):
                guarded = True
            adjacent |= score > 0
            if trigger.family in EXPLORATION_FAMILIES and score >= 0:
                # Skipped/omitted features have no evidence, so remain explorable.
                novelty = tag.confidence / Decimal(1 + evidence)
                exploration.append((novelty, trigger))
        if guarded or not exploration:
            continue
        exploration.sort(key=lambda item: (-item[0], item[1].key))
        score = exploration[0][0] + (Decimal("0.25") if adjacent else Decimal(0))
        reasons = [feature_identity(trigger) for _, trigger in exploration[:2]]
        candidates.append((video, score, reasons))
    candidates.sort(key=lambda item: (-item[1], item[0].id))
    items = []
    for video, score, reasons in candidates[:limit]:
        items.append(
            {
                **video_metadata(video, features[video.id]),
                "score": float(score),
                "reasons": reasons,
            }
        )
        db.add(
            RecommendationImpression(
                user_id=user.id,
                video_id=video.id,
                surface="discover",
                algorithm_version=ALGORITHM_VERSION,
                score=score,
                reason_json=reasons,
                created_at=now,
            )
        )
    db.commit()
    return {"items": items, "algorithm_version": ALGORITHM_VERSION}


@router.get("/search")
def search(
    user: Identity,
    db: Database,
    q: str | None = None,
    sound: Annotated[list[str] | None, Query()] = None,
    voice: str | None = None,
    speed: str | None = None,
    language: Annotated[list[str] | None, Query()] = None,
    format: Annotated[list[str] | None, Query()] = None,
    min_duration_sec: Annotated[int | None, Query(ge=0)] = None,
    max_duration_sec: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    page: Annotated[int, Query(ge=1)] = 1,
) -> dict:
    if (
        min_duration_sec is not None
        and max_duration_sec is not None
        and min_duration_sec > max_duration_sec
    ):
        raise HTTPException(
            422,
            detail={
                "code": "INVALID_DURATION_RANGE",
                "message": "Minimum exceeds maximum.",
            },
        )
    query = active_videos()
    if q and q.strip():
        text = q.strip()
        query = query.where(
            or_(
                Video.title.icontains(text, autoescape=True),
                Video.channel_name.icontains(text, autoescape=True),
                Video.description.icontains(text, autoescape=True),
            )
        )
    # Repeated features are conjunctive; languages are alternatives. Unknown or
    # wrong-family keys match nothing instead of silently dropping hard filters.
    for family, keys in (
        ("sound", sound or []),
        ("voice", [] if voice is None else [voice]),
        ("speed", [] if speed is None else [speed]),
        ("format", format or []),
    ):
        for key in set(keys):
            query = query.where(
                select(VideoTrigger.video_id)
                .join(Trigger, Trigger.id == VideoTrigger.trigger_id)
                .where(
                    VideoTrigger.video_id == Video.id,
                    Trigger.active.is_(True),
                    Trigger.family == family,
                    Trigger.key == key,
                    VideoTrigger.confidence >= RELIABLE_CONFIDENCE,
                    VideoTrigger.confidence <= 1,
                )
                .exists()
            )
    if language:
        query = query.where(Video.language.in_(language))
    if min_duration_sec is not None:
        query = query.where(Video.duration_sec >= min_duration_sec)
    if max_duration_sec is not None:
        query = query.where(Video.duration_sec <= max_duration_sec)
    videos = list(
        db.scalars(query.order_by(Video.id).offset((page - 1) * limit).limit(limit + 1))
    )
    features = feature_map(db)
    return {
        "items": [
            video_metadata(video, features[video.id]) for video in videos[:limit]
        ],
        "next_page": page + 1 if len(videos) > limit else None,
    }
