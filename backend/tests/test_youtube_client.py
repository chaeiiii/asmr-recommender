from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest

from app.services.youtube_client import (
    YouTubeClient,
    YouTubeConfig,
    YouTubeError,
    YouTubeForbiddenError,
)


def video_item(video_id: str) -> dict:
    return {
        "id": video_id,
        "snippet": {
            "title": f"Title {video_id}",
            "description": "desc",
            "channelId": "channel-1",
            "channelTitle": "Channel",
            "publishedAt": "2026-09-01T00:00:00Z",
            "thumbnails": {"default": {"url": "https://example.test/t.jpg"}},
            "tags": ["asmr", "tapping"],
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "contentDetails": {"duration": "PT10M"},
        "status": {
            "privacyStatus": "public",
            "embeddable": True,
            "uploadStatus": "processed",
        },
    }


def client_for(handler, *, max_retries: int = 2, sleep=lambda _: None) -> YouTubeClient:
    return YouTubeClient(
        YouTubeConfig(api_key="test-key", max_retries=max_retries),
        transport=httpx.MockTransport(handler),
        sleep=sleep,
    )


def test_search_videos_returns_deduplicated_page_and_pagination_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/search")
        assert request.headers["X-Goog-Api-Key"] == "test-key"
        params = request.url.params
        assert params["part"] == "snippet"
        assert params["type"] == "video"
        assert params["videoEmbeddable"] == "true"
        assert params["q"] == "asmr tapping"
        assert params["maxResults"] == "25"
        assert params["pageToken"] == "NEXT"
        return httpx.Response(
            200,
            json={
                "items": [
                    {"id": {"videoId": "a"}},
                    {"id": {"videoId": "b"}},
                    {"id": {"videoId": "a"}},
                ],
                "nextPageToken": "MORE",
            },
        )

    with client_for(handler) as client:
        page = client.search_videos("asmr tapping", page_token="NEXT", max_results=25)

    assert page.video_ids == ("a", "b")
    assert page.next_page_token == "MORE"


@pytest.mark.parametrize(
    "query,max_results", [("", 10), ("   ", 10), ("x", 0), ("x", 51)]
)
def test_search_videos_validates_inputs(query: str, max_results: int) -> None:
    with client_for(
        lambda request: pytest.fail("network should not be called")
    ) as client:
        with pytest.raises(ValueError):
            client.search_videos(query, max_results=max_results)


def test_get_videos_batches_deduplicates_preserves_order_and_reports_missing() -> None:
    requested: list[tuple[str, ...]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/videos")
        ids = tuple(request.url.params["id"].split(","))
        requested.append(ids)
        assert request.url.params["part"] == "snippet,contentDetails,status"
        returned = [video_item(value) for value in ids if value != "missing"]
        # Reverse API response order to ensure the client restores input order.
        return httpx.Response(200, json={"items": list(reversed(returned))})

    ids = [f"v{i}" for i in range(51)] + ["missing", "v0"]
    with client_for(handler) as client:
        result = client.get_videos(ids)

    assert len(requested) == 2
    assert len(requested[0]) == 50
    assert requested[1] == ("v50", "missing")
    assert tuple(video.id for video in result.videos) == tuple(
        f"v{i}" for i in range(51)
    )
    assert result.missing_ids == ("missing",)


def test_iter_video_batches_rejects_invalid_ids_without_network() -> None:
    with client_for(
        lambda request: pytest.fail("network should not be called")
    ) as client:
        with pytest.raises(ValueError):
            list(client.iter_video_batches(["ok", "bad,id"]))
        with pytest.raises(ValueError):
            list(client.iter_video_batches([" spaced "]))
        with pytest.raises(ValueError):
            list(client.iter_video_batches([""]))


def test_403_stops_immediately_without_retry() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(403, json={"error": {"message": "quota"}})

    with client_for(handler, max_retries=2, sleep=sleeps.append) as client:
        with pytest.raises(YouTubeForbiddenError) as exc:
            client.search_videos("asmr")

    assert exc.value.status_code == 403
    assert calls == 1
    assert sleeps == []
    assert "test-key" not in str(exc.value)


def test_5xx_retries_then_succeeds() -> None:
    statuses: Iterator[int] = iter([500, 502, 200])
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        status = next(statuses)
        if status == 200:
            return httpx.Response(200, json={"items": []})
        return httpx.Response(status, json={"error": "temporary"})

    with client_for(handler, max_retries=2, sleep=sleeps.append) as client:
        page = client.search_videos("asmr")

    assert page.video_ids == ()
    assert sleeps == [1, 2]


def test_transport_error_retries_then_raises_safe_error() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("network details", request=request)

    with client_for(handler, max_retries=1, sleep=sleeps.append) as client:
        with pytest.raises(YouTubeError) as exc:
            client.search_videos("asmr")

    assert calls == 2
    assert sleeps == [1]
    assert exc.value.reason == "network"
    assert "network details" not in str(exc.value)
    assert "test-key" not in str(exc.value)


def test_invalid_json_or_schema_is_safe_error() -> None:
    responses = iter(
        [
            httpx.Response(200, content=b"not-json"),
            httpx.Response(200, json={"items": [{"id": {}}]}),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return next(responses)

    with client_for(handler) as client:
        with pytest.raises(YouTubeError, match="invalid_response"):
            client.search_videos("asmr")
        with pytest.raises(YouTubeError, match="invalid_response"):
            client.search_videos("asmr")


def test_empty_video_id_list_returns_empty_result_without_network() -> None:
    with client_for(
        lambda request: pytest.fail("network should not be called")
    ) as client:
        result = client.get_videos([])

    assert result.videos == ()
    assert result.missing_ids == ()
