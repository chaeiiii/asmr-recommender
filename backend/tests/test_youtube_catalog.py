"""Offline fixtures; optional PostgreSQL coverage uses TEST_DATABASE_URL only."""

import os
from datetime import datetime, timezone
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy import MetaData, create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from app.models import Video
from app.services import youtube_catalog as catalog
from app.services.youtube_client import (
    SearchPage,
    VideoBatch,
    VideoMetadata,
    YouTubeClient,
    YouTubeConfig,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def metadata(video_id="video1", title="ASMR tapping"):
    return VideoMetadata.model_validate({
        "id": video_id,
        "snippet": {
            "title": title,
            "channelId": "channel1",
            "channelTitle": "Test channel",
            "publishedAt": "2025-01-01T00:00:00Z",
            "defaultAudioLanguage": "en-US",
            "thumbnails": {"high": {"url": "https://example.test/thumb.jpg"}},
        },
        "contentDetails": {"duration": "PT12M30S"},
        "status": {"privacyStatus": "public", "embeddable": True,
                   "uploadStatus": "processed"},
    })


@pytest.mark.parametrize("value, expected", [
    ("PT12M30S", 750), ("P1DT2H", 93600), ("PT1S", 1),
    (None, None), ("PT0S", None), ("P", None), ("PT", None),
    ("P1DT", None), ("PT-3S", None), ("garbage", None),
    ("PT2147483648S", None),
])
def test_duration(value, expected):
    assert catalog.duration_seconds(value) == expected


@pytest.mark.parametrize("section, field, value, reason", [
    ("status", "privacy_status", "private", "not_public"),
    ("status", "privacy_status", "unlisted", "not_public"),
    ("status", "embeddable", False, "not_embeddable"),
    ("status", "embeddable", None, "not_embeddable"),
    ("status", "upload_status", "failed", "not_processed"),
    ("snippet", "title", " ", "invalid_metadata"),
    ("snippet", "channel_id", "", "invalid_metadata"),
    ("snippet", "channel_title", "", "invalid_metadata"),
    ("snippet", "published_at", datetime(2025, 1, 1), "invalid_metadata"),
    ("content_details", "duration", "PT0S", "invalid_duration"),
    ("snippet", "title", "Ordinary video", "no_asmr_evidence"),
])
def test_ineligible_metadata(section, field, value, reason):
    video = metadata()
    setattr(getattr(video, section), field, value)
    assert catalog.video_row(video, NOW) == (None, reason)


def test_maps_metadata_and_allows_title_only_evidence():
    row, reason = catalog.video_row(metadata(), NOW)
    assert reason is None
    assert row == {
        "youtube_video_id": "video1", "title": "ASMR tapping",
        "description": "", "channel_id": "channel1",
        "channel_name": "Test channel",
        "thumbnail_url": "https://example.test/thumb.jpg",
        "duration_sec": 750, "language": "en",
        "published_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "embeddable": True, "availability_status": "active",
        "last_synced_at": NOW,
    }


@pytest.mark.parametrize("source", ["description", "tags"])
def test_asmr_evidence_can_come_from_description_or_tags(source):
    video = metadata(title="Tapping")
    setattr(video.snippet, source, ["ASMR"] if source == "tags" else "ＡＳＭＲ")
    assert catalog.video_row(video, NOW)[0] is not None


@pytest.mark.parametrize("value, expected", [
    (None, None), ("und", None), ("zxx", None), ("mul", None),
    ("English", None), ("ko-KR", "ko"), ("ja", "ja"),
])
def test_language_uses_explicit_metadata_only(value, expected):
    assert catalog.normalized_language(value) == expected


def test_dedupe_across_pages_queries_and_missing_metadata(monkeypatch):
    client = Mock()
    client.search_videos.side_effect = [
        SearchPage(("video1", "video1"), "next"),
        SearchPage(("video1", "missing"), None),
        SearchPage(("video1",), None),
    ]
    client.iter_video_batches.side_effect = [
        iter([VideoBatch((metadata(),), ())]),
        iter([VideoBatch((), ("missing",))]), iter([]),
    ]
    upsert = Mock(side_effect=[(1, 0), (0, 0)])
    monkeypatch.setattr(catalog, "upsert_videos", upsert)
    result = catalog.collect_catalog(client, Mock(), ["one", "two"], pages_per_query=2)
    assert result.candidates == 5
    assert result.duplicates == 3
    assert result.inserted == 1
    assert result.rejected == result.unavailable == 1
    assert result.api_calls == 5
    assert client.iter_video_batches.call_args_list[0].args == (["video1"],)
    assert client.iter_video_batches.call_args_list[1].args == (["missing"],)
    assert client.search_videos.call_args_list[1].kwargs["page_token"] == "next"


def test_later_403_preserves_successful_batch(monkeypatch):
    session = Mock()
    monkeypatch.setattr(catalog, "upsert_videos", Mock(return_value=(1, 0)))
    searches = 0

    def handler(request):
        nonlocal searches
        if request.url.path.endswith("/search"):
            searches += 1
            return httpx.Response(200, json={
                "items": [{"id": {"videoId": f"video{searches}"}}],
            })
        if searches == 1:
            return httpx.Response(200, json={
                "items": [metadata().model_dump(mode="json", by_alias=True)],
            })
        # The prior successful metadata batch must already be durable.
        session.commit.assert_called_once()
        return httpx.Response(403)

    with YouTubeClient(YouTubeConfig("fixture-key"),
                       transport=httpx.MockTransport(handler)) as client:
        result = catalog.collect_catalog(client, session, ["one", "two", "three"])
    assert result.stopped
    assert result.inserted == 1
    assert result.failures == {"forbidden_or_quota": 1}
    assert searches == 2
    session.commit.assert_called_once()


def test_failed_database_batch_is_rolled_back(monkeypatch):
    client = Mock()
    client.search_videos.return_value = SearchPage(("video1",), None)
    client.iter_video_batches.return_value = iter([VideoBatch((metadata(),), ())])
    monkeypatch.setattr(catalog, "upsert_videos", Mock(side_effect=RuntimeError("db")))
    session = Mock()
    with pytest.raises(RuntimeError, match="db"):
        catalog.collect_catalog(client, session, ["ASMR"])
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_postgresql_fixture_run_is_idempotent_and_updates_metadata():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL for PostgreSQL integration coverage")
    engine = create_engine(url)
    if engine.dialect.name != "postgresql":
        engine.dispose()
        pytest.skip("PostgreSQL required")
    try:
        with engine.connect() as connection:
            # A connection-local table shadows videos; no persistent schema writes.
            table = Video.__table__.to_metadata(MetaData())
            ddl = str(CreateTable(table).compile(dialect=engine.dialect))
            connection.exec_driver_sql(
                ddl.replace("CREATE TABLE", "CREATE TEMPORARY TABLE", 1)
            )
            connection.commit()
            with Session(connection) as session:
                client = Mock()
                client.search_videos.return_value = SearchPage(("video1", "bad"), None)
                bad = metadata("bad")
                bad.status.embeddable = False
                client.iter_video_batches.side_effect = lambda ids: iter([
                    VideoBatch((metadata(), bad), ()),
                ])
                first = catalog.collect_catalog(client, session, ["ASMR"])
                stored = session.execute(select(Video.__table__)).mappings().one()
                client.iter_video_batches.side_effect = lambda ids: iter([
                    VideoBatch((metadata(title="ASMR updated"), bad), ()),
                ])
                second = catalog.collect_catalog(client, session, ["ASMR"])
                updated = session.execute(select(Video.__table__)).mappings().one()
                assert (first.inserted, first.updated, first.rejected) == (1, 0, 1)
                assert (second.inserted, second.updated, second.rejected) == (0, 1, 1)
                assert updated["id"] == stored["id"]
                assert updated["created_at"] == stored["created_at"]
                assert updated["title"] == "ASMR updated"
                assert updated["last_synced_at"] >= stored["last_synced_at"]
    finally:
        engine.dispose()
