from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Video
from app.services.youtube_catalog import active_catalog_query
from app.services.youtube_client import YouTubeClient, YouTubeConfig
from app.services.youtube_refresh import refresh_youtube

NOW = datetime(2026, 9, 24, tzinfo=timezone.utc)


def stored(index, *, fresh=False):
    return Video(
        id=index,
        youtube_video_id=f"video{index}",
        title="Old ASMR",
        channel_id="channel",
        channel_name="Old channel",
        last_synced_at=NOW if fresh else NOW - timedelta(days=31),
    )


def metadata(index, *, privacy="public", embeddable=True):
    return {
        "id": f"video{index}",
        "snippet": {
            "title": "Updated ASMR",
            "description": "New description",
            "channelId": "channel",
            "channelTitle": "New channel",
            "publishedAt": "2025-01-01T00:00:00Z",
            "defaultAudioLanguage": "en-US",
        },
        "contentDetails": {"duration": "PT10M"},
        "status": {"privacyStatus": privacy, "embeddable": embeddable},
    }


def test_refresh_status_metadata_history_and_idempotency():
    engine = create_engine("sqlite://")
    Video.__table__.create(engine)
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.path.endswith("/videos")
        assert request.url.params["id"] == "video1,video2,video3,video4"
        return httpx.Response(
            200,
            json={
                "items": [
                    metadata(1),
                    metadata(3, privacy="private"),
                    metadata(4, embeddable=False),
                ]
            },
        )

    with (
        Session(engine) as session,
        YouTubeClient(
            YouTubeConfig("fake"), transport=httpx.MockTransport(handler)
        ) as client,
    ):
        session.add_all([stored(i) for i in range(1, 5)] + [stored(5, fresh=True)])
        session.commit()
        result = refresh_youtube(client, session, now=NOW)
        assert (result.updated, result.unavailable, result.blocked_embed) == (4, 2, 1)
        assert [
            v.id for v in session.scalars(active_catalog_query().order_by(Video.id))
        ] == [1, 5]
        assert len(list(session.scalars(select(Video)))) == 5
        video = session.get(Video, 1)
        assert (video.title, video.duration_sec, video.language) == (
            "Updated ASMR",
            600,
            "en",
        )
        assert video.last_synced_at.replace(tzinfo=timezone.utc) == NOW
        assert session.get(Video, 4).availability_status == "blocked_embed"
        assert refresh_youtube(client, session, now=NOW).updated == 0
        assert len(calls) == 1
    engine.dispose()


def test_quota_preserves_first_batch_and_leaves_failed_batch_untouched():
    engine = create_engine("sqlite://")
    Video.__table__.create(engine)
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 2:
            return httpx.Response(403, json={"error": {"message": "quota"}})
        assert len(request.url.params["id"].split(",")) == 50
        return httpx.Response(200, json={"items": []})

    with (
        Session(engine) as session,
        YouTubeClient(
            YouTubeConfig("fake"), transport=httpx.MockTransport(handler)
        ) as client,
    ):
        session.add_all(stored(i) for i in range(1, 52))
        session.commit()
        result = refresh_youtube(client, session, now=NOW)
        assert result.stopped and result.updated == 50
        assert result.failures["forbidden_or_quota"] == 1
    with Session(engine) as session:
        assert session.get(Video, 1).availability_status == "unavailable"
        assert session.get(Video, 51).availability_status == "active"
        assert session.get(Video, 51).last_synced_at.replace(tzinfo=timezone.utc) < NOW
    engine.dispose()
