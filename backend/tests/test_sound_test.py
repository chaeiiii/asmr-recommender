"""Sound-test API coverage using the isolated PostgreSQL fixture; no YouTube calls."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.main import app
from app.models import (
    InitialTestAssignment,
    PreferenceEvent,
    Trigger,
    TriggerSample,
    User,
    UserPreference,
    Video,
)
from app.models import (
    TestResponse as SampleResponse,
)
from app.sound_test import BASE, OPTIONAL

ROOT = "/api/v1/test"


@pytest.fixture
def sound_api(db, monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "sound-test-only-secret-at-least-32-bytes")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    with Session(db, join_transaction_mode="create_savepoint") as session:
        now = datetime.now(timezone.utc)
        for index, key in enumerate(BASE + OPTIONAL, start=1):
            trigger = Trigger(key=key, display_name=key, family="sound")
            video = Video(
                youtube_video_id=f"test{index:07d}",
                title=key,
                channel_id="test",
                channel_name="test",
                last_synced_at=now,
            )
            session.add_all([trigger, video])
            session.flush()
            # The smaller sample ID is deliberately unverified.
            for verified in (False, True, True):
                session.add(
                    TriggerSample(
                        primary_trigger_id=trigger.id,
                        video_id=video.id,
                        start_sec=10,
                        end_sec=20,
                        verified=verified,
                        created_at=now,
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
                assert client.post("/api/v1/session").status_code == 200
                yield client, session
        finally:
            app.dependency_overrides.pop(get_session)


def answer(client, sample, value="skip"):
    return client.post(
        f"{ROOT}/samples/{sample['sample_id']}/response",
        json={"response": value},
    )


def test_stable_verified_base_and_hidden_labels(sound_api):
    client, db = sound_api
    result = client.get(f"{ROOT}/samples")
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    samples = result.json()["samples"]
    assert len(samples) == 6
    assert client.get(f"{ROOT}/samples").json() == result.json()
    keys = []
    for item in samples:
        assert set(item) == {
            "sample_id",
            "phase",
            "position",
            "youtube_video_id",
            "start_sec",
            "end_sec",
            "response",
        }
        sample = db.get(TriggerSample, item["sample_id"])
        assert sample.verified
        keys.append(db.get(Trigger, sample.primary_trigger_id).key)
    assert keys == list(BASE)
    assert answer(client, samples[0], "like").status_code == 200
    revealed = client.get(f"{ROOT}/samples").json()["samples"]
    assert revealed[0]["primary_trigger"]["key"] == "tapping"
    assert "primary_trigger" not in revealed[1]


def test_response_replacement_and_skip_remove_evidence(sound_api):
    client, db = sound_api
    sample = client.get(f"{ROOT}/samples").json()["samples"][0]
    for value, expected in [
        ("like", "0.4500"),
        ("like", "0.4500"),
        ("dislike", "-0.4500"),
        ("neutral", "0.0000"),
        ("like", "0.4500"),
    ]:
        assert answer(client, sample, value).status_code == 200
        preference = db.scalar(select(UserPreference))
        assert preference.score == Decimal(expected)
        assert preference.evidence_count == 1
        assert preference.last_evidence_source == "test"
        events = list(db.scalars(select(PreferenceEvent)))
        assert len(events) == 1
        assert events[0].trigger_id == preference.trigger_id
        assert events[0].observation == {"like": 1, "neutral": 0, "dislike": -1}[value]
    for _ in range(2):
        assert answer(client, sample).status_code == 200
        assert db.scalar(select(func.count()).select_from(UserPreference)) == 0
        assert db.scalar(select(func.count()).select_from(PreferenceEvent)) == 0
    assert db.scalar(select(func.count()).select_from(SampleResponse)) == 1
    assert answer(client, sample, "dislike").status_code == 200
    assert db.scalar(select(UserPreference)).score == Decimal("-0.4500")


@pytest.mark.parametrize("extended", [False, True])
def test_completion_and_optional_guards(sound_api, extended):
    client, db = sound_api
    assert client.post(f"{ROOT}/complete").status_code == 409
    assert client.post(f"{ROOT}/extend").status_code == 409
    base = client.get(f"{ROOT}/samples").json()["samples"]
    for sample in base[:-1]:
        assert answer(client, sample).status_code == 200
    assert client.post(f"{ROOT}/extend").status_code == 409
    assert client.post(f"{ROOT}/complete").status_code == 409
    answer(client, base[-1])
    if extended:
        result = client.post(f"{ROOT}/extend")
        assert result.status_code == 200
        assert client.post(f"{ROOT}/extend").json() == result.json()
        assert client.get(f"{ROOT}/samples").json() == result.json()
        samples = result.json()["samples"]
        assert len(samples) == 8
        extra = samples[6:]
        keys = {
            db.get(
                Trigger, db.get(TriggerSample, item["sample_id"]).primary_trigger_id
            ).key
            for item in extra
        }
        assert len(keys) == 2 and keys <= set(OPTIONAL)
        assert client.post(f"{ROOT}/complete").status_code == 409
        answer(client, extra[0])
        assert client.post(f"{ROOT}/complete").status_code == 409
        answer(client, extra[1])
    assert client.post(f"{ROOT}/complete").json() == {"next_route": "/onboarding/voice"}
    completed_at = db.scalar(select(User.initial_test_completed_at))
    assert completed_at is not None
    assert client.post(f"{ROOT}/complete").status_code == 200
    assert db.scalar(select(User)).initial_test_completed_at == completed_at
    assert client.post("/api/v1/session").json()["next_route"] == "/onboarding/voice"
    assert answer(client, base[0], "like").status_code == 409
    if not extended:
        assert client.post(f"{ROOT}/extend").status_code == 409


def test_identity_validation_and_unassigned_sample(sound_api):
    client, db = sound_api
    sample = client.get(f"{ROOT}/samples").json()["samples"][0]
    user_id = db.scalar(select(User.id))
    assert answer(client, sample, "invalid").status_code == 422
    assert (
        client.post(
            f"{ROOT}/samples/{sample['sample_id']}/response",
            json={"response": "like", "user_id": str(user_id)},
        ).status_code
        == 422
    )
    client.cookies.clear()
    assert (
        client.post(
            f"{ROOT}/samples/{sample['sample_id']}/response?user_id={user_id}",
            json={"response": "like"},
        ).status_code
        == 404
    )
    assert db.scalar(select(func.count()).select_from(SampleResponse)) == 0


def test_missing_verified_catalog_is_atomic_and_optional_does_not_block(sound_api):
    client, db = sound_api
    trigger = db.scalar(select(Trigger).where(Trigger.key == BASE[-1]))
    for sample in db.scalars(
        select(TriggerSample).where(
            TriggerSample.primary_trigger_id == trigger.id,
        )
    ):
        sample.verified = False
    db.commit()
    assert client.get(f"{ROOT}/samples").status_code == 503
    assert db.scalar(select(func.count()).select_from(InitialTestAssignment)) == 0
    sample.verified = True
    db.commit()
    base = client.get(f"{ROOT}/samples").json()["samples"]
    for item in base:
        answer(client, item)
    for sample in db.scalars(
        select(TriggerSample)
        .join(Trigger)
        .where(
            Trigger.key.in_(OPTIONAL),
        )
    ):
        sample.verified = False
    db.commit()
    assert client.post(f"{ROOT}/extend").status_code == 503
    assert db.scalar(select(func.count()).select_from(InitialTestAssignment)) == 6
    assert client.post(f"{ROOT}/complete").status_code == 200
