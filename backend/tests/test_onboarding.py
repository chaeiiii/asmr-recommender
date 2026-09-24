"""Onboarding and My Taste coverage; uses only the isolated database fixture."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.main import app
from app.models import (
    InitialTestAssignment,
    PreferenceEvent,
    Trigger,
    TriggerSample,
    User,
    UserLanguagePreference,
    UserPreference,
    Video,
)
from app.onboarding import display_state

ROOT = "/api/v1/onboarding"


@pytest.fixture
def onboarding_api(db, monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "onboarding-test-secret-at-least-32-bytes")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    with Session(db, join_transaction_mode="create_savepoint") as session:
        for key, family, core, active in (
            ("tapping", "sound", True, True),
            ("paper_crinkling", "sound", True, True),
            ("non_core", "sound", False, True),
            ("inactive", "visual", False, False),
            ("hand_movements", "visual", False, True),
            ("roleplay", "format", False, True),
            ("whisper", "voice", False, True),
        ):
            session.add(
                Trigger(
                    key=key,
                    display_name=key,
                    family=family,
                    is_core=core,
                    active=active,
                )
            )
        session.commit()

        def override():
            try:
                yield session
            finally:
                session.rollback()

        app.dependency_overrides[get_session] = override
        try:
            with TestClient(app, base_url="https://testserver") as client:
                client.post("/api/v1/session")
                user = session.scalar(select(User))
                user.initial_test_completed_at = datetime.now(timezone.utc)
                session.commit()
                yield client, session, user.id
        finally:
            app.dependency_overrides.pop(get_session)


@pytest.mark.parametrize("mode", ["talking", "both"])
def test_voice_language_validation_replacement_and_resume(onboarding_api, mode):
    client, db, user_id = onboarding_api
    assert client.get(f"{ROOT}/voice").json()["voice_mode"] is None
    assert (
        client.post(f"{ROOT}/voice", json={"voice_mode": "invalid"}).status_code == 422
    )
    for _ in range(2):
        assert client.post(f"{ROOT}/voice", json={"voice_mode": mode}).json() == {
            "next_route": "/onboarding/languages",
        }
    assert client.get(f"{ROOT}/extra-preferences").status_code == 409
    for payload in (
        {"languages": [], "no_preference": False},
        {"languages": ["ko"], "no_preference": True},
        {"languages": ["fr"], "no_preference": False},
    ):
        assert client.post(f"{ROOT}/languages", json=payload).status_code == 422
    for _ in range(2):
        result = client.post(
            f"{ROOT}/languages",
            json={
                "languages": ["ko", "en", "ja", "other", "ko"],
                "no_preference": False,
            },
        )
        assert result.status_code == 200
    assert len(list(db.scalars(select(UserLanguagePreference)))) == 4
    assert client.post("/api/v1/session").json()["next_route"] == (
        "/onboarding/extra-preferences"
    )
    assert (
        client.post(
            f"{ROOT}/languages",
            json={
                "languages": [],
                "no_preference": True,
            },
        ).status_code
        == 200
    )
    assert not list(db.scalars(select(UserLanguagePreference)))
    assert db.get(User, user_id).language_no_preference
    client.post(f"{ROOT}/languages", json={"languages": ["ko"], "no_preference": False})
    for _ in range(2):
        assert client.post(
            f"{ROOT}/voice", json={"voice_mode": "no_talking"}
        ).json() == {
            "next_route": "/onboarding/extra-preferences",
        }
    assert not list(db.scalars(select(UserLanguagePreference)))
    assert not db.get(User, user_id).language_no_preference
    assert (
        client.post(
            f"{ROOT}/languages",
            json={
                "languages": [],
                "no_preference": True,
            },
        ).status_code
        == 409
    )
    client.post(f"{ROOT}/voice", json={"voice_mode": mode})
    assert (
        client.post("/api/v1/session").json()["next_route"] == "/onboarding/languages"
    )


@pytest.mark.parametrize("phase", ["base", "optional"])
def test_extra_eligibility_and_atomic_validation(onboarding_api, phase):
    client, db, user_id = onboarding_api
    now = datetime.now(timezone.utc)
    trigger = db.scalar(select(Trigger).where(Trigger.key == "tapping"))
    video = Video(
        youtube_video_id="test0000001",
        title="fixture",
        channel_id="fixture",
        channel_name="fixture",
        last_synced_at=now,
    )
    db.add(video)
    db.flush()
    sample = TriggerSample(
        primary_trigger_id=trigger.id,
        video_id=video.id,
        start_sec=0,
        end_sec=10,
        verified=True,
        created_at=now,
    )
    db.add(sample)
    db.flush()
    db.add(
        InitialTestAssignment(
            user_id=user_id,
            sample_id=sample.id,
            phase=phase,
            position=1 if phase == "base" else 7,
            test_version="fixture",
            created_at=now,
        )
    )
    db.commit()
    client.post(f"{ROOT}/voice", json={"voice_mode": "no_talking"})
    groups = client.get(f"{ROOT}/extra-preferences").json()["groups"]
    assert {
        family: [item["key"] for item in items] for family, items in groups.items()
    } == {
        "sound": ["paper_crinkling"],
        "visual": ["hand_movements"],
        "format": ["roleplay"],
    }
    assert all(
        set(item) == {"key", "display_name", "family"}
        for items in groups.values()
        for item in items
    )
    for key in ("tapping", "non_core", "inactive", "whisper", "missing"):
        assert (
            client.post(
                f"{ROOT}/extra-preferences",
                json={
                    "liked_features": ["roleplay", key],
                },
            ).status_code
            == 422
        )
    assert not list(db.scalars(select(PreferenceEvent)))
    assert not db.get(User, user_id).onboarding_completed


@pytest.mark.parametrize("selected", [[], ["paper_crinkling", "roleplay", "roleplay"]])
def test_extra_completes_and_retries_do_not_count_twice(onboarding_api, selected):
    client, db, user_id = onboarding_api
    client.post(f"{ROOT}/voice", json={"voice_mode": "no_talking"})
    for _ in range(2):
        assert client.post(
            f"{ROOT}/extra-preferences",
            json={
                "liked_features": selected,
            },
        ).json() == {"next_route": "/my-taste?first=1"}
    assert db.get(User, user_id).onboarding_completed
    assert client.post("/api/v1/session").json()["next_route"] == "/home"
    events = list(db.scalars(select(PreferenceEvent)))
    preferences = list(db.scalars(select(UserPreference)))
    assert len(events) == len(preferences) == len(set(selected))
    assert all(
        event.source == "self_report" and event.observation == Decimal("0.35")
        for event in events
    )
    assert all(
        row.score == Decimal("0.35") and row.evidence_count == 1 for row in preferences
    )
    assert (
        client.post(
            f"{ROOT}/extra-preferences",
            json={
                "liked_features": ["hand_movements"],
            },
        ).status_code
        == 409
    )
    assert (
        client.post(f"{ROOT}/voice", json={"voice_mode": "talking"}).status_code == 409
    )
    profile = client.get("/api/v1/me/preferences").json()
    omitted = next(
        item for item in profile["features"] if item["key"] == "hand_movements"
    )
    assert omitted["display_state"] == "not_tried"
    assert omitted["evidence_count"] == 0


@pytest.mark.parametrize(
    "score,count,state",
    [
        ("0.9", 0, "not_tried"),
        ("0.65", 1, "love"),
        ("0.6499", 1, "like"),
        ("0.25", 1, "like"),
        ("0.2499", 1, "neutral"),
        ("0", 1, "neutral"),
        ("-0.2499", 1, "neutral"),
        ("-0.25", 1, "dislike"),
    ],
)
def test_display_boundaries(score, count, state):
    assert display_state(Decimal(score), count) == state


def test_profile_preserves_stronger_evidence_and_recent_discoveries(onboarding_api):
    client, db, user_id = onboarding_api
    now = datetime.now(timezone.utc)
    trigger = db.scalar(select(Trigger).where(Trigger.key == "roleplay"))
    db.add(
        UserPreference(
            user_id=user_id,
            trigger_id=trigger.id,
            score=Decimal("-0.7"),
            evidence_count=2,
            last_evidence_source="discover_dislike",
            updated_at=now,
        )
    )
    for source in ("discover_like", "discover_dislike"):
        db.add(
            PreferenceEvent(
                user_id=user_id,
                trigger_id=trigger.id,
                source=source,
                observation=1 if source == "discover_like" else -1,
                created_at=now,
            )
        )
    db.commit()
    client.post(f"{ROOT}/voice", json={"voice_mode": "both"})
    client.post(f"{ROOT}/languages", json={"languages": ["ja"], "no_preference": False})
    for _ in range(2):
        assert (
            client.post(
                f"{ROOT}/extra-preferences",
                json={
                    "liked_features": ["roleplay"],
                },
            ).status_code
            == 200
        )
    result = client.get("/api/v1/me/preferences")
    assert result.headers["cache-control"] == "no-store"
    profile = result.json()
    assert profile["taxonomy_version"] == "2.0"
    assert profile["voice_mode"] == "both"
    assert profile["languages"] == ["ja"] and not profile["no_preference"]
    feature = next(item for item in profile["features"] if item["key"] == "roleplay")
    assert feature["score"] == -0.7
    assert feature["evidence_count"] == 3 and feature["display_state"] == "dislike"
    assert [item["key"] for item in profile["recent_discoveries"]] == ["roleplay"]
    assert feature not in profile["unknown_or_low_evidence"]


def test_session_identity_and_step_guards(onboarding_api):
    client, db, user_id = onboarding_api
    assert (
        client.post(
            f"{ROOT}/voice",
            json={
                "voice_mode": "both",
                "user_id": str(user_id),
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{ROOT}/extra-preferences",
            json={
                "liked_features": [],
            },
        ).status_code
        == 409
    )
    client.cookies.clear()
    profile = client.get(f"/api/v1/me/preferences?user_id={user_id}").json()
    assert profile["voice_mode"] is None
    assert all(item["evidence_count"] == 0 for item in profile["features"])
    assert (
        client.post(
            f"{ROOT}/voice?user_id={user_id}",
            json={
                "voice_mode": "no_talking",
            },
        ).status_code
        == 409
    )
    assert db.get(User, user_id).voice_mode is None
