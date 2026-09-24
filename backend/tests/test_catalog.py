"""Saved, Discover and Search regression coverage without external API calls."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.main import app
from app.models import (
    Favorite,
    Interaction,
    PreferenceEvent,
    RecommendationImpression,
    Trigger,
    User,
    UserPreference,
    Video,
    VideoTrigger,
)
from app.sessions import COOKIE_NAME, read_identity

ROOT = "/api/v1"
SECRET = "catalog-tests-secret-at-least-32-bytes"


@pytest.fixture
def catalog_api(db, monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", SECRET)
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
                identity = read_identity(
                    client.cookies.get(COOKIE_NAME), SECRET.encode()
                )
                yield client, session, session.get(User, identity)
        finally:
            app.dependency_overrides.pop(get_session)


def trigger(db, key, family="sound", active=True):
    item = Trigger(key=key, display_name=key, family=family, active=active)
    db.add(item)
    db.commit()
    return item


def video(db, index, tags=(), **values):
    now = datetime.now(timezone.utc)
    item = Video(
        youtube_video_id=f"catalog{index:04d}",
        title=f"Video {index}",
        channel_id=f"channel{index}",
        channel_name="Quiet Channel",
        description="Gentle sounds",
        last_synced_at=now,
        **values,
    )
    db.add(item)
    db.flush()
    for feature, confidence in tags:
        db.add(
            VideoTrigger(
                video_id=item.id,
                trigger_id=feature.id,
                confidence=Decimal(confidence),
                source="manual",
                tagger_version="test",
                created_at=now,
            )
        )
    db.commit()
    return item


def ids(response):
    assert response.status_code == 200, response.text
    return [item["video_id"] for item in response.json()["items"]]


def counts(db):
    return tuple(
        db.scalar(select(func.count()).select_from(model))
        for model in (
            UserPreference,
            PreferenceEvent,
            Interaction,
        )
    )


def test_saved_idempotent_newest_active_and_cookie_isolation(catalog_api):
    client, db, user = catalog_api
    first = video(db, 1)
    second = video(db, 2)
    before = counts(db)
    for item in (first, second):
        url = f"{ROOT}/videos/{item.id}/favorite"
        assert client.post(url).status_code == 200
        saved_at = db.get(Favorite, (user.id, item.id)).created_at
        assert client.post(url).status_code == 200
        assert db.get(Favorite, (user.id, item.id)).created_at == saved_at
    db.get(Favorite, (user.id, first.id)).created_at -= timedelta(days=1)
    db.commit()
    response = client.get(f"{ROOT}/favorites")
    assert ids(response) == [second.id, first.id]
    assert response.json()["items"][0]["title"] == second.title
    second.availability_status = "private"
    db.commit()
    assert ids(client.get(f"{ROOT}/favorites")) == [first.id]
    assert client.post(f"{ROOT}/videos/{second.id}/favorite").status_code == 409
    for _ in range(2):
        assert client.delete(f"{ROOT}/videos/{second.id}/favorite").status_code == 200
    original_cookie = client.cookies.get(COOKIE_NAME)
    client.cookies.clear()
    assert ids(client.get(f"{ROOT}/favorites", params={"user_id": str(user.id)})) == []
    client.delete(
        f"{ROOT}/videos/{first.id}/favorite", params={"user_id": str(user.id)}
    )
    assert db.get(Favorite, (user.id, first.id)) is not None
    client.cookies.clear()
    client.cookies.set(COOKIE_NAME, original_cookie)
    assert ids(client.get(f"{ROOT}/favorites")) == [first.id]
    assert counts(db) == before


def test_discover_explores_all_families_guards_and_records(catalog_api):
    client, db, user = catalog_api
    liked = trigger(db, "tapping")
    unknown = trigger(db, "scratching")
    visual = trigger(db, "hand_movements", "visual")
    format_feature = trigger(db, "roleplay", "format")
    disliked = trigger(db, "mouth_sounds")
    now = datetime.now(timezone.utc)
    for feature, score, evidence in ((liked, "0.8", 8), (disliked, "-0.8", 8)):
        db.add(
            UserPreference(
                user_id=user.id,
                trigger_id=feature.id,
                score=Decimal(score),
                evidence_count=evidence,
                updated_at=now,
            )
        )
    db.commit()
    familiar = video(db, 1, [(liked, "1")])
    adjacent = video(db, 2, [(liked, "1"), (unknown, "1")])
    visual_video = video(db, 3, [(visual, "1")])
    format_video = video(db, 4, [(format_feature, "1")])
    video(db, 5, [(disliked, "0.8"), (unknown, "1")])
    video(db, 6, [(unknown, "1")], embeddable=False)
    video(db, 7, [(unknown, "1")], availability_status="deleted")
    skipped = video(db, 8, [(unknown, "1")])
    db.add(
        Interaction(user_id=user.id, video_id=skipped.id, type="skip", created_at=now)
    )
    db.commit()
    before = counts(db)
    response = client.get(f"{ROOT}/discover")
    assert ids(response) == [adjacent.id, visual_video.id, format_video.id, familiar.id]
    assert response.json()["algorithm_version"] == "content_v1"
    impressions = list(db.scalars(select(RecommendationImpression)))
    assert len(impressions) == 4
    assert all(item.surface == "discover" for item in impressions)
    assert all(item.algorithm_version == "content_v1" for item in impressions)
    assert all(item.reason_json for item in impressions)
    assert counts(db) == before
    assert db.get(UserPreference, (user.id, unknown.id)) is None
    assert db.get(UserPreference, (user.id, liked.id)).score == Decimal("0.8")


def test_discover_unknown_then_low_evidence_and_limit(catalog_api):
    client, db, user = catalog_api
    features = [trigger(db, key) for key in ("tapping", "scratching", "ear_cleaning")]
    videos = [video(db, i, [(feature, "1")]) for i, feature in enumerate(features)]
    # No positive evidence is required to explore an entirely unknown profile.
    assert ids(client.get(f"{ROOT}/discover", params={"limit": 1})) == [videos[0].id]
    now = datetime.now(timezone.utc)
    for feature, evidence in zip(features[:2], (8, 1)):
        db.add(
            UserPreference(
                user_id=user.id,
                trigger_id=feature.id,
                score=Decimal(0),
                evidence_count=evidence,
                updated_at=now,
            )
        )
    db.commit()
    assert ids(client.get(f"{ROOT}/discover")) == [
        videos[2].id,
        videos[1].id,
        videos[0].id,
    ]
    db.add(
        Interaction(
            user_id=user.id,
            video_id=videos[2].id,
            type="dislike",
            created_at=now,
        )
    )
    db.commit()
    assert ids(client.get(f"{ROOT}/discover")) == [videos[1].id, videos[0].id]


def test_search_combined_filters_reliability_paging_and_no_learning(catalog_api):
    client, db, user = catalog_api
    tapping = trigger(db, "tapping")
    scratching = trigger(db, "scratching")
    whisper = trigger(db, "whisper", "voice")
    slow = trigger(db, "slow", "speed")
    roleplay = trigger(db, "roleplay", "format")
    attention = trigger(db, "personal_attention", "format")
    tags = [
        (feature, "0.6")
        for feature in (
            tapping,
            scratching,
            whisper,
            slow,
            roleplay,
            attention,
        )
    ]
    first = video(db, 1, tags, language="en", duration_sec=100)
    second = video(db, 2, tags, language="ja", duration_sec=200)
    video(db, 3, tags[:-1], language="en", duration_sec=100)
    video(db, 4, [(tapping, "0.59")] + tags[1:], language="en", duration_sec=100)
    video(db, 5, tags, language="ko", duration_sec=100)
    video(db, 6, tags, language="en", duration_sec=201)
    video(db, 7, tags, language="en", duration_sec=100, embeddable=False)
    video(db, 8, tags, language="en", duration_sec=100, availability_status="private")
    video(db, 9, tags, language="en")
    params = [
        ("sound", "tapping"),
        ("sound", "scratching"),
        ("voice", "whisper"),
        ("speed", "slow"),
        ("format", "roleplay"),
        ("format", "personal_attention"),
        ("language", "en"),
        ("language", "ja"),
        ("min_duration_sec", 100),
        ("max_duration_sec", 200),
        ("q", "QUIET"),
    ]
    before = counts(db)
    assert ids(client.get(f"{ROOT}/search", params=params)) == [first.id, second.id]
    assert ids(client.get(f"{ROOT}/search", params=params)) == [first.id, second.id]
    response = client.get(f"{ROOT}/search", params=params + [("limit", 1)])
    assert ids(response) == [first.id]
    assert response.json()["next_page"] == 2
    assert ids(
        client.get(f"{ROOT}/search", params=params + [("limit", 1), ("page", 2)])
    ) == [second.id]
    for query in ({"sound": "roleplay"}, {"sound": "nonexistent"}, {"q": "%"}):
        assert ids(client.get(f"{ROOT}/search", params=query)) == []
    assert counts(db) == before
    assert db.scalar(select(func.count()).select_from(RecommendationImpression)) == 0
    tapping.active = False
    db.commit()
    assert ids(client.get(f"{ROOT}/search", params=params)) == []


@pytest.mark.parametrize(
    "path",
    [
        "/search?min_duration_sec=10&max_duration_sec=9",
        "/search?min_duration_sec=-1",
        "/search?limit=0",
        "/search?limit=101",
        "/search?page=0",
        "/discover?limit=0",
    ],
)
def test_invalid_bounds(catalog_api, path):
    client, _, _ = catalog_api
    assert client.get(ROOT + path).status_code == 422
