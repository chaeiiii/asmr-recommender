"""Deterministic content_v1 Home ranking and anonymous video feedback."""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.models import (
    Interaction,
    PreferenceEvent,
    RecommendationImpression,
    Trigger,
    UserLanguagePreference,
    UserPreference,
    Video,
    VideoTrigger,
)
from app.onboarding import feature_identity
from app.sound_test import Database, Identity

router = APIRouter()
ALGORITHM_VERSION = "content_v1"
WEIGHTS = {
    "sound": Decimal("1.00"),
    "voice": Decimal("0.65"),
    "visual": Decimal("0.40"),
    "format": Decimal("0.35"),
    "speed": Decimal("0.45"),
    "intensity": Decimal("0.30"),
}
# Product specs leave cooling periods tunable. Impressions affect only ordering,
# with seen candidates used as fallback when the unseen catalog is exhausted.
SKIP_COOLDOWN = timedelta(hours=24)
IMPRESSION_WINDOW = timedelta(hours=1)


class InteractionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["play", "like", "dislike", "skip"]
    watch_duration_sec: int | None = Field(default=None, ge=0, strict=True)


def usable_features(db, video_id=None):
    query = (
        select(VideoTrigger, Trigger)
        .join(
            Trigger,
            Trigger.id == VideoTrigger.trigger_id,
        )
        .where(
            Trigger.active.is_(True),
            Trigger.family.in_(WEIGHTS),
            VideoTrigger.confidence > 0,
            VideoTrigger.confidence <= 1,
        )
    )
    if video_id is not None:
        query = query.where(VideoTrigger.video_id == video_id)
    return db.execute(query.order_by(Trigger.key, Trigger.id)).all()


def score_video(video, features, preferences, user, languages):
    """Return the signed normalized score and up to two positive contributors."""
    denominator = Decimal(0)
    numerator = Decimal(0)
    positives = []
    voice_keys = set()
    for tag, trigger in features:
        weight = tag.confidence * WEIGHTS[trigger.family]
        contribution = preferences.get(trigger.id, Decimal(0)) * weight
        denominator += weight
        numerator += contribution
        if contribution > 0:
            positives.append((contribution, trigger))
        if trigger.family == "voice":
            voice_keys.add(trigger.key)
    score = numerator / max(denominator, Decimal("0.000001"))
    spoken = bool(voice_keys & {"whisper", "soft_spoken"})
    silent = "no_talking" in voice_keys
    if user.voice_mode == "talking":
        score += (
            Decimal("0.12") if spoken else (Decimal("-0.05") if silent else Decimal(0))
        )
    elif user.voice_mode == "no_talking":
        score += (
            Decimal("0.12") if silent else (Decimal("-0.05") if spoken else Decimal(0))
        )
    if (
        spoken
        and user.voice_mode in {"talking", "both"}
        and not user.language_no_preference
        and video.language in languages
    ):
        score += Decimal("0.08")
    positives.sort(key=lambda item: (-item[0], item[1].key, item[1].id))
    return score, [feature_identity(trigger) for _, trigger in positives[:2]]


def rank_home(db, user, limit, now):
    preferences = dict(
        db.execute(
            select(
                UserPreference.trigger_id,
                UserPreference.score,
            ).where(UserPreference.user_id == user.id)
        ).all()
    )
    languages = set(
        db.scalars(
            select(UserLanguagePreference.language).where(
                UserLanguagePreference.user_id == user.id,
            )
        )
    )
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
    recent = set(
        db.scalars(
            select(RecommendationImpression.video_id).where(
                RecommendationImpression.user_id == user.id,
                RecommendationImpression.surface == "home",
                RecommendationImpression.created_at >= now - IMPRESSION_WINDOW,
            )
        )
    )
    features = defaultdict(list)
    for tag, trigger in usable_features(db):
        features[tag.video_id].append((tag, trigger))
    positive_evidence = any(score > 0 for score in preferences.values())
    candidates = []
    for video in db.scalars(
        select(Video).where(
            Video.availability_status == "active",
            Video.embeddable.is_(True),
        )
    ):
        if video.id in excluded or not features[video.id]:
            continue
        score, reasons = score_video(
            video,
            features[video.id],
            preferences,
            user,
            languages,
        )
        if positive_evidence and not reasons:
            continue
        candidates.append((video, score, reasons))
    candidates.sort(
        key=lambda item: (
            item[0].id in recent,
            -item[1],
            item[0].id,
        )
    )
    channels = Counter()
    selected = []
    for candidate in candidates:
        video = candidate[0]
        if len(selected) < 20 and channels[video.channel_id] >= 2:
            continue
        selected.append(candidate)
        channels[video.channel_id] += 1
        if len(selected) == 20:
            break
    # The channel cap must not be relaxed to fill a sparse first page. Beyond
    # position 20, resume the original ordering without the channel constraint.
    if len(selected) == 20 and limit > 20:
        chosen = {item[0].id for item in selected}
        selected.extend(item for item in candidates if item[0].id not in chosen)
    return [
        {
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
                for tag, trigger in features[video.id]
            ],
            "score": float(score),
            "reasons": reasons,
        }
        for video, score, reasons in selected[:limit]
    ]


@router.get("/recommendations")
def recommendations(
    user: Identity,
    db: Database,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    if not user.onboarding_completed:
        raise HTTPException(
            409,
            detail={
                "code": "ONBOARDING_REQUIRED",
                "message": "Complete onboarding first.",
            },
        )
    now = datetime.now(timezone.utc)
    items = rank_home(db, user, limit, now)
    for item in items:
        db.add(
            RecommendationImpression(
                user_id=user.id,
                video_id=item["video_id"],
                surface="home",
                algorithm_version=ALGORITHM_VERSION,
                score=Decimal(str(item["score"])),
                reason_json=item["reasons"],
                created_at=now,
            )
        )
    db.commit()
    return {"items": items, "algorithm_version": ALGORITHM_VERSION}


@router.post("/videos/{video_id}/interactions")
def interact(
    video_id: int, body: InteractionBody, user: Identity, db: Database
) -> dict:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(
            404,
            detail={
                "code": "VIDEO_NOT_FOUND",
                "message": "Video not found.",
            },
        )
    if video.availability_status != "active" or not video.embeddable:
        raise HTTPException(
            409,
            detail={
                "code": "VIDEO_UNAVAILABLE",
                "message": "This video is no longer available.",
            },
        )
    now = datetime.now(timezone.utc)
    previous = db.scalar(
        select(Interaction)
        .where(
            Interaction.user_id == user.id,
            Interaction.video_id == video_id,
            Interaction.type.in_(("like", "dislike")),
        )
        .order_by(Interaction.created_at.desc(), Interaction.id.desc())
        .limit(1)
    )
    interaction = Interaction(
        user_id=user.id,
        video_id=video_id,
        type=body.type,
        watch_duration_sec=body.watch_duration_sec,
        created_at=now,
    )
    db.add(interaction)
    db.flush()
    # Identity holds the existing per-user lock through commit. Repeated same
    # sentiment (including retries after play/skip) logs activity but cannot
    # inflate evidence. Changed sentiment is a new chronological observation.
    if body.type in {"like", "dislike"} and (
        previous is None or previous.type != body.type
    ):
        observation = Decimal(1 if body.type == "like" else -1)
        source = f"video_{body.type}"
        for tag, trigger in usable_features(db, video_id):
            if tag.confidence < Decimal("0.60"):
                continue
            preference = db.get(UserPreference, (user.id, trigger.id))
            if preference is None:
                preference = UserPreference(
                    user_id=user.id,
                    trigger_id=trigger.id,
                    score=Decimal(0),
                    evidence_count=0,
                )
                db.add(preference)
            alpha = Decimal("0.20") * tag.confidence
            preference.score = (
                (1 - alpha) * preference.score + alpha * observation
            ).quantize(Decimal("0.0001"))
            preference.evidence_count += 1
            preference.last_evidence_source = source
            preference.updated_at = now
            db.add(
                PreferenceEvent(
                    user_id=user.id,
                    trigger_id=trigger.id,
                    source=source,
                    observation=observation,
                    reference_type="interaction",
                    reference_id=str(interaction.id),
                    created_at=now,
                )
            )
    result = {"interaction_id": interaction.id, "video_id": video_id, "type": body.type}
    db.commit()
    return result
