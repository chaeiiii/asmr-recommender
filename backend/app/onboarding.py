"""Conditional onboarding and the current, evidence-based My Taste profile."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import select

from app.models import (
    InitialTestAssignment,
    PreferenceEvent,
    Trigger,
    TriggerSample,
    UserLanguagePreference,
    UserPreference,
)
from app.sessions import next_route
from app.sound_test import Database, Identity

router = APIRouter()
LANGUAGES = ("ko", "en", "ja", "other")
EXTRA_ROUTE = "/onboarding/extra-preferences"


class VoiceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    voice_mode: Literal["talking", "no_talking", "both"]


class LanguagesBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    languages: list[Literal["ko", "en", "ja", "other"]]
    no_preference: bool

    @model_validator(mode="after")
    def exclusive_selection(self):
        if self.no_preference == bool(self.languages):
            raise ValueError("Choose specific languages or no_preference exclusively")
        return self


class ExtraBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    liked_features: list[str]


def require_test(user):
    if user.initial_test_completed_at is None:
        raise HTTPException(409, "Complete the sound test first")


def language_rows(user, db):
    return list(db.scalars(select(UserLanguagePreference).where(
        UserLanguagePreference.user_id == user.id,
    )))


def language_payload(user, db):
    selected = {row.language for row in language_rows(user, db)}
    return {
        "languages": [code for code in LANGUAGES if code in selected],
        "no_preference": user.language_no_preference,
    }


@router.get("/onboarding/voice")
def get_voice(user: Identity, db: Database) -> dict:
    require_test(user)
    return {"voice_mode": user.voice_mode, "next_route": next_route(user, db)}


@router.post("/onboarding/voice")
def set_voice(body: VoiceBody, user: Identity, db: Database) -> dict:
    require_test(user)
    if user.onboarding_completed and user.voice_mode != body.voice_mode:
        raise HTTPException(409, "Onboarding already completed")
    user.voice_mode = body.voice_mode
    if body.voice_mode == "no_talking":
        for row in language_rows(user, db):
            db.delete(row)
        user.language_no_preference = False
    db.commit()
    return {
        "next_route": EXTRA_ROUTE if body.voice_mode == "no_talking"
        else "/onboarding/languages",
    }


@router.get("/onboarding/languages")
def get_languages(user: Identity, db: Database) -> dict:
    require_test(user)
    if user.voice_mode is None:
        raise HTTPException(409, "Choose a voice preference first")
    return {
        **language_payload(user, db),
        "options": list(LANGUAGES),
        "next_route": next_route(user, db),
    }


@router.post("/onboarding/languages")
def set_languages(body: LanguagesBody, user: Identity, db: Database) -> dict:
    require_test(user)
    if user.voice_mode not in {"talking", "both"}:
        raise HTTPException(409, "Language selection requires talking or both")
    rows = language_rows(user, db)
    existing = {row.language for row in rows}
    selected = set(body.languages)
    if user.onboarding_completed and (
        existing != selected or user.language_no_preference != body.no_preference
    ):
        raise HTTPException(409, "Onboarding already completed")
    for row in rows:
        if row.language not in selected:
            db.delete(row)
    now = datetime.now(timezone.utc)
    for code in selected - existing:
        db.add(UserLanguagePreference(user_id=user.id, language=code, created_at=now))
    user.language_no_preference = body.no_preference
    db.commit()
    return {"next_route": EXTRA_ROUTE}


def eligible_options(user, db):
    presented = select(TriggerSample.primary_trigger_id).join(
        InitialTestAssignment,
        InitialTestAssignment.sample_id == TriggerSample.id,
    ).where(InitialTestAssignment.user_id == user.id)
    return list(db.scalars(select(Trigger).where(
        Trigger.active.is_(True),
        (
            (Trigger.family == "sound") & Trigger.is_core.is_(True)
            & Trigger.id.not_in(presented)
        ) | Trigger.family.in_(("visual", "format")),
    ).order_by(Trigger.family, Trigger.key)))


def require_extra(user, db):
    require_test(user)
    if not user.onboarding_completed and next_route(user, db) != EXTRA_ROUTE:
        raise HTTPException(409, "Complete voice and language preferences first")


def feature_identity(trigger):
    return {
        "key": trigger.key,
        "display_name": trigger.display_name,
        "family": trigger.family,
    }


@router.get("/onboarding/extra-preferences")
def get_extra(user: Identity, db: Database) -> dict:
    require_extra(user, db)
    groups = {family: [] for family in ("sound", "visual", "format")}
    for trigger in eligible_options(user, db):
        groups[trigger.family].append(feature_identity(trigger))
    return {"groups": groups}


@router.post("/onboarding/extra-preferences")
def set_extra(body: ExtraBody, user: Identity, db: Database) -> dict:
    require_extra(user, db)
    selected = set(body.liked_features)
    events = list(db.scalars(select(PreferenceEvent).where(
        PreferenceEvent.user_id == user.id,
        PreferenceEvent.source == "self_report",
        PreferenceEvent.reference_type == "onboarding_extra",
    )))
    recorded = {db.get(Trigger, event.trigger_id).key for event in events}
    # The completion flag also makes an empty Skip safely replayable. Changes
    # after completion must not reinterpret later, stronger profile evidence.
    if user.onboarding_completed:
        if recorded != selected:
            raise HTTPException(409, "Onboarding already completed")
        db.commit()
        return {"next_route": "/my-taste?first=1"}
    eligible = {trigger.key: trigger for trigger in eligible_options(user, db)}
    if selected - eligible.keys():
        raise HTTPException(422, "All liked_features must be eligible options")
    now = datetime.now(timezone.utc)
    for key in sorted(selected - recorded):
        trigger = eligible[key]
        db.add(PreferenceEvent(
            user_id=user.id, trigger_id=trigger.id, source="self_report",
            observation=Decimal("0.35"), reference_type="onboarding_extra",
            reference_id=key, created_at=now,
        ))
        preference = db.get(UserPreference, (user.id, trigger.id))
        if preference is None:
            preference = UserPreference(
                user_id=user.id, trigger_id=trigger.id, evidence_count=0,
            )
            db.add(preference)
        if preference.evidence_count == 0:
            preference.score = Decimal("0.35")
        preference.evidence_count += 1
        preference.last_evidence_source = "self_report"
        preference.updated_at = now
    user.onboarding_completed = True
    db.commit()
    return {"next_route": "/my-taste?first=1"}


def display_state(score: Decimal, evidence_count: int) -> str:
    if evidence_count == 0:
        return "not_tried"
    if score >= Decimal("0.65"):
        return "love"
    if score >= Decimal("0.25"):
        return "like"
    if score <= Decimal("-0.25"):
        return "dislike"
    return "neutral"


@router.get("/me/preferences")
def get_preferences(user: Identity, db: Database) -> dict:
    preferences = {row.trigger_id: row for row in db.scalars(
        select(UserPreference).where(UserPreference.user_id == user.id)
    )}
    items = {}
    for trigger in db.scalars(select(Trigger).where(
        Trigger.active.is_(True),
    ).order_by(Trigger.family, Trigger.key)):
        preference = preferences.get(trigger.id)
        count = preference.evidence_count if preference else 0
        score = preference.score if preference and count else Decimal(0)
        items[trigger.id] = {
            **feature_identity(trigger),
            "score": float(score),
            "evidence_count": count,
            "display_state": display_state(score, count),
        }
    recent = []
    seen = set()
    for event in db.scalars(select(PreferenceEvent).where(
        PreferenceEvent.user_id == user.id,
        PreferenceEvent.source == "discover_like",
    ).order_by(PreferenceEvent.created_at.desc(), PreferenceEvent.id.desc())):
        if event.trigger_id in items and event.trigger_id not in seen:
            recent.append({**items[event.trigger_id], "discovered_at": event.created_at})
            seen.add(event.trigger_id)
            if len(recent) == 10:
                break
    return {
        "taxonomy_version": user.taxonomy_version,
        "voice_mode": user.voice_mode,
        **language_payload(user, db),
        "features": list(items.values()),
        "recent_discoveries": recent,
        # Two observations is the minimum for leaving the low-evidence bucket.
        "unknown_or_low_evidence": [
            item for item in items.values() if item["evidence_count"] < 2
        ],
    }
