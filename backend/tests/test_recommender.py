"""Focused content_v1 regression coverage; no external API calls."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.main import app
from app.models import (
    Interaction,
    PreferenceEvent,
    RecommendationImpression,
    Trigger,
    User,
    UserPreference,
    Video,
    VideoTrigger,
)
from app.recommender import SKIP_COOLDOWN, WEIGHTS, rank_home, score_video

ROOT = "/api/v1"


@pytest.fixture
def home_api(db, monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "recommender-tests-secret-at-least-32-bytes")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    with Session(db, join_transaction_mode="create_savepoint") as session:

        def override():
            try:
                yield session
            finally:
                session.rollback()

        app.dependency_overrides[get_session] = override
        try:
            with TestClient(app, base_url="https://testserver") as client:
                client.post(f"{ROOT}/session")
                user = session.scalar(select(User))
                user.onboarding_completed = True
                user.voice_mode = "both"
                trigger = Trigger(key="tapping", display_name="Tapping", family="sound")
                session.add(trigger)
                session.commit()
                yield client, session, user, trigger
        finally:
            app.dependency_overrides.pop(get_session)


def add_video(db, trigger, index, confidence="1", **values):
    video = Video(
        youtube_video_id=f"video{index:06d}",
        title=f"Video {index}",
        channel_id=values.pop("channel_id", f"channel{index}"),
        channel_name="Channel",
        last_synced_at=datetime.now(timezone.utc),
        **values,
    )
    db.add(video)
    db.flush()
    if trigger is not None:
        db.add(
            VideoTrigger(
                video_id=video.id,
                trigger_id=trigger.id,
                confidence=Decimal(confidence),
                source="manual",
                tagger_version="test",
                created_at=datetime.now(timezone.utc),
            )
        )
    db.commit()
    return video


def react(client, video, kind, **values):
    return client.post(
        f"{ROOT}/videos/{video.id}/interactions",
        json={"type": kind, **values},
    )


def test_signed_family_weights_and_positive_reasons():
    features = []
    preferences = {}
    for index, family in enumerate(WEIGHTS, 1):
        trigger = SimpleNamespace(
            id=index,
            key=family,
            family=family,
            display_name=family,
        )
        features.append((SimpleNamespace(confidence=Decimal("0.8")), trigger))
        preferences[index] = Decimal("0.5") if index % 2 else Decimal("-0.5")
    user = SimpleNamespace(voice_mode="both", language_no_preference=True)
    score, reasons = score_video(
        SimpleNamespace(language="en"), features, preferences, user, set()
    )
    expected = sum(
        preferences[index] * weight for index, weight in enumerate(WEIGHTS.values(), 1)
    ) / sum(WEIGHTS.values())
    assert score == expected
    assert [reason["key"] for reason in reasons] == ["sound", "speed"]


@pytest.mark.parametrize(
    "mode,key,language,no_preference,expected",
    [
        ("talking", "whisper", "en", False, "0.20"),
        ("talking", "soft_spoken", "ja", False, "0.12"),
        ("talking", "no_talking", "en", False, "-0.05"),
        ("no_talking", "whisper", "en", False, "-0.05"),
        ("no_talking", "no_talking", "en", False, "0.12"),
        ("both", "whisper", "en", False, "0.08"),
        ("both", "whisper", "en", True, "0"),
    ],
)
def test_soft_voice_and_language(mode, key, language, no_preference, expected):
    trigger = SimpleNamespace(id=1, key=key, family="voice", display_name=key)
    features = [(SimpleNamespace(confidence=Decimal(1)), trigger)]
    user = SimpleNamespace(voice_mode=mode, language_no_preference=no_preference)
    score, reasons = score_video(
        SimpleNamespace(language=language),
        features,
        {},
        user,
        {"en"},
    )
    assert score == Decimal(expected)
    assert reasons == []  # No invented feature evidence for an unknown profile.


def test_home_filters_impressions_and_no_preference_mutation(home_api):
    client, db, user, trigger = home_api
    active = add_video(db, trigger, 1)
    disliked = add_video(db, trigger, 2)
    skipped = add_video(db, trigger, 3)
    add_video(db, trigger, 4, availability_status="private")
    add_video(db, trigger, 5, embeddable=False)
    add_video(db, None, 6)
    add_video(db, trigger, 7, confidence="0")
    now = datetime.now(timezone.utc)
    for video, kind in [(disliked, "dislike"), (skipped, "skip")]:
        db.add(
            Interaction(user_id=user.id, video_id=video.id, type=kind, created_at=now)
        )
    db.commit()
    response = client.get(f"{ROOT}/recommendations")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert [item["video_id"] for item in response.json()["items"]] == [active.id]
    impression = db.scalar(select(RecommendationImpression))
    assert impression.surface == "home"
    assert impression.algorithm_version == "content_v1"
    assert impression.reason_json == []
    assert db.scalar(select(func.count()).select_from(UserPreference)) == 0
    assert db.scalar(select(func.count()).select_from(PreferenceEvent)) == 0
    skip = db.scalar(select(Interaction).where(Interaction.type == "skip"))
    skip.created_at = now - SKIP_COOLDOWN - timedelta(seconds=1)
    db.commit()
    items = client.get(f"{ROOT}/recommendations").json()["items"]
    assert [item["video_id"] for item in items] == [skipped.id, active.id]


def test_determinism_diversity_positive_match_and_limit(home_api):
    client, db, user, trigger = home_api
    videos = [
        add_video(db, trigger, i, channel_id=f"channel{i // 3}") for i in range(33)
    ]
    now = datetime.now(timezone.utc)
    first = rank_home(db, user, 100, now)
    assert first == rank_home(db, user, 100, now)
    ids = [item["video_id"] for item in first]
    assert ids[:4] == [videos[i].id for i in (0, 1, 3, 4)]
    assert len(ids) == 33
    for channel in {item["channel_id"] for item in first[:20]}:
        assert sum(item["channel_id"] == channel for item in first[:20]) <= 2
    unknown = Trigger(key="brushing", display_name="Brushing", family="sound")
    db.add(unknown)
    db.flush()
    unmatched = add_video(db, unknown, 100)
    db.add(
        UserPreference(
            user_id=user.id,
            trigger_id=trigger.id,
            score=Decimal("0.35"),
            evidence_count=1,
            last_evidence_source="self_report",
            updated_at=now,
        )
    )
    db.commit()
    items = client.get(f"{ROOT}/recommendations?limit=100").json()["items"]
    assert unmatched.id not in {item["video_id"] for item in items}
    assert all(item["reasons"][0]["key"] == "tapping" for item in items)
    assert db.get(UserPreference, (user.id, trigger.id)).score == Decimal("0.3500")
    assert client.get(f"{ROOT}/recommendations?limit=0").status_code == 422
    user.onboarding_completed = False
    db.commit()
    assert client.get(f"{ROOT}/recommendations").status_code == 409


def test_feedback_threshold_retry_and_changed_sentiment(home_api):
    client, db, user, trigger = home_api
    video = add_video(db, trigger, 1, confidence="0.60")
    low = Trigger(key="brushing", display_name="Brushing", family="sound")
    db.add(low)
    db.flush()
    db.add(
        VideoTrigger(
            video_id=video.id,
            trigger_id=low.id,
            confidence=Decimal("0.599"),
            source="manual",
            tagger_version="test",
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    for kind in ("like", "like", "play", "skip", "like"):
        assert react(client, video, kind, watch_duration_sec=12).status_code == 200
    preference = db.get(UserPreference, (user.id, trigger.id))
    assert preference.score == Decimal("0.1200")
    assert preference.evidence_count == 1
    assert db.get(UserPreference, (user.id, low.id)) is None
    event = db.scalar(select(PreferenceEvent))
    assert event.source == "video_like" and event.observation == 1
    assert event.reference_type == "interaction"
    assert db.get(Interaction, int(event.reference_id)).type == "like"
    for _ in range(2):
        assert react(client, video, "dislike").status_code == 200
    db.refresh(preference)
    assert preference.score == Decimal("-0.0144")
    assert preference.evidence_count == 2
    assert preference.last_evidence_source == "video_dislike"
    assert db.scalar(select(func.count()).select_from(PreferenceEvent)) == 2
    assert db.scalar(select(func.count()).select_from(Interaction)) == 7
    assert client.get(f"{ROOT}/recommendations").json()["items"] == []


def test_skip_and_play_leave_features_untouched_and_identity_is_cookie_only(home_api):
    client, db, user, trigger = home_api
    video = add_video(db, trigger, 1)
    sibling = add_video(db, trigger, 2)
    assert react(client, video, "play").status_code == 200
    assert react(client, video, "skip").status_code == 200
    assert db.scalar(select(func.count()).select_from(UserPreference)) == 0
    assert db.scalar(select(func.count()).select_from(PreferenceEvent)) == 0
    assert [
        item["video_id"]
        for item in client.get(
            f"{ROOT}/recommendations",
        ).json()["items"]
    ] == [sibling.id]
    assert react(client, video, "like", user_id=str(user.id)).status_code == 422
    assert react(client, video, "save").status_code == 422
    assert react(client, video, "play", watch_duration_sec=-1).status_code == 422
    assert (
        client.post(
            f"{ROOT}/videos/999999/interactions", json={"type": "like"}
        ).status_code
        == 404
    )
    video.embeddable = False
    db.commit()
    assert react(client, video, "like").status_code == 409
    client.cookies.clear()
    assert (
        client.post(
            f"{ROOT}/videos/{sibling.id}/interactions?user_id={user.id}",
            json={"type": "like"},
        ).status_code
        == 200
    )
    assert db.get(UserPreference, (user.id, trigger.id)) is None
    assert db.scalar(select(PreferenceEvent)).user_id != user.id


@pytest.mark.parametrize("surface", [None, "home", "discover", "search", "favorites"])
def test_discover_like_attribution_keeps_scoring_and_retry_rules(home_api, surface):
    client, db, user, trigger = home_api
    video = add_video(db, trigger, 1)
    payload = {} if surface is None else {"surface": surface}
    assert react(client, video, "like", **payload).status_code == 200
    expected = "discover_like" if surface == "discover" else "video_like"
    event = db.scalar(select(PreferenceEvent))
    assert event.source == expected
    assert event.observation == 1
    preference = db.get(UserPreference, (user.id, trigger.id))
    assert preference.score == Decimal("0.2000")
    assert preference.evidence_count == 1
    assert preference.last_evidence_source == expected
    recent = client.get(f"{ROOT}/me/preferences").json()["recent_discoveries"]
    assert [item["key"] for item in recent] == (
        [trigger.key] if surface == "discover" else []
    )
    # Retrying on another surface must not add/relabel existing evidence.
    for retry_surface in ("discover", "home", "search", "favorites"):
        assert react(client, video, "like", surface=retry_surface).status_code == 200
    assert db.scalar(select(func.count()).select_from(PreferenceEvent)) == 1
    db.refresh(event)
    assert event.source == expected
    assert react(client, video, "dislike", surface="discover").status_code == 200
    db.refresh(preference)
    assert preference.score == Decimal("-0.0400")
    assert preference.evidence_count == 2
    assert preference.last_evidence_source == "video_dislike"
    assert react(client, video, "like", surface="unknown").status_code == 422
