"""Metadata-only YouTube Data API v3 adapter; no catalog or media writes."""

import os
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Self

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError


@dataclass(frozen=True)
class YouTubeConfig:
    api_key: str = field(repr=False)
    timeout_seconds: float = 10
    max_retries: int = 2

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("Set YOUTUBE_API_KEY to use the YouTube client")
        if not 0 < self.timeout_seconds <= 120:
            raise ValueError("YouTube timeout must be between 0 and 120 seconds")
        if not 0 <= self.max_retries <= 5:
            raise ValueError("YouTube max retries must be between 0 and 5")

    @classmethod
    def from_env(cls) -> Self:
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
        return cls(
            api_key=os.getenv("YOUTUBE_API_KEY", ""),
            timeout_seconds=float(os.getenv("YOUTUBE_TIMEOUT_SECONDS", "10")),
            max_retries=int(os.getenv("YOUTUBE_MAX_RETRIES", "2")),
        )


class Thumbnail(BaseModel):
    url: str
    width: int | None = None
    height: int | None = None


class VideoSnippet(BaseModel):
    title: str
    description: str = ""
    channel_id: str = Field(alias="channelId")
    channel_title: str = Field(alias="channelTitle")
    published_at: datetime = Field(alias="publishedAt")
    thumbnails: dict[str, Thumbnail] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    default_language: str | None = Field(default=None, alias="defaultLanguage")
    default_audio_language: str | None = Field(
        default=None, alias="defaultAudioLanguage"
    )


class VideoContentDetails(BaseModel):
    # Preserve source duration/language evidence; eligibility belongs to collection.
    duration: str | None = None


class VideoStatus(BaseModel):
    privacy_status: str | None = Field(default=None, alias="privacyStatus")
    embeddable: bool | None = None
    upload_status: str | None = Field(default=None, alias="uploadStatus")


class VideoMetadata(BaseModel):
    id: str
    snippet: VideoSnippet
    content_details: VideoContentDetails = Field(alias="contentDetails")
    status: VideoStatus


class _VideoResponse(BaseModel):
    items: list[VideoMetadata]


class _SearchId(BaseModel):
    video_id: str = Field(alias="videoId")


class _SearchItem(BaseModel):
    id: _SearchId


class _SearchResponse(BaseModel):
    items: list[_SearchItem]
    next_page_token: str | None = Field(default=None, alias="nextPageToken")


@dataclass(frozen=True)
class SearchPage:
    video_ids: tuple[str, ...]
    next_page_token: str | None


@dataclass(frozen=True)
class VideoBatch:
    videos: tuple[VideoMetadata, ...]
    missing_ids: tuple[str, ...]


class YouTubeError(RuntimeError):
    """Safe error without response bodies, URLs, or credentials."""

    def __init__(self, reason: str, status_code: int | None = None):
        self.reason = reason
        self.status_code = status_code
        super().__init__(f"YouTube request failed: {reason} (status={status_code})")


class YouTubeForbiddenError(YouTubeError):
    """403 (including quota exhaustion): caller must stop, not retry."""


class YouTubeClient:
    def __init__(
        self,
        config: YouTubeConfig,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self._sleep = sleep
        self._client = httpx.Client(
            base_url="https://www.googleapis.com/youtube/v3/",
            headers={"X-Goog-Api-Key": config.api_key},
            timeout=config.timeout_seconds,
            transport=transport,
            follow_redirects=False,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _get(self, endpoint: str, params: dict[str, str | int]) -> object:
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self._client.get(endpoint, params=params)
            except httpx.TransportError:
                if attempt == self.config.max_retries:
                    raise YouTubeError("network") from None
            else:
                status = response.status_code
                if status == 403:
                    raise YouTubeForbiddenError("forbidden_or_quota", status)
                if 200 <= status < 300:
                    try:
                        return response.json()
                    except ValueError:
                        raise YouTubeError("invalid_response", status) from None
                if not 500 <= status < 600 or attempt == self.config.max_retries:
                    raise YouTubeError("http", status)
            self._sleep(2 ** attempt)
        raise AssertionError("unreachable")

    def search_videos(
        self, query: str, *, page_token: str | None = None, max_results: int = 50
    ) -> SearchPage:
        """Fetch one page; callers explicitly control search quota/pagination."""
        if not query.strip() or not 1 <= max_results <= 50:
            raise ValueError("Provide a query and max_results between 1 and 50")
        params: dict[str, str | int] = {
            "part": "snippet", "type": "video", "videoEmbeddable": "true",
            "q": query, "maxResults": max_results,
        }
        if page_token:
            params["pageToken"] = page_token
        data = self._get("search", params)
        try:
            page = _SearchResponse.model_validate(data)
        except ValidationError:
            raise YouTubeError("invalid_response") from None
        return SearchPage(
            tuple(dict.fromkeys(item.id.video_id for item in page.items)),
            page.next_page_token,
        )

    def iter_video_batches(self, video_ids: Iterable[str]) -> Iterator[VideoBatch]:
        """Yield successful batches so callers can persist progress before a 403.

        Missing IDs are explicit, never inferred from a failed API request.
        Results retain input order; duplicates are requested only once.
        """
        ids = list(dict.fromkeys(video_ids))
        if any(not value or value.strip() != value or "," in value for value in ids):
            raise ValueError("Video IDs must be nonempty, individual IDs")
        for offset in range(0, len(ids), 50):
            batch = ids[offset:offset + 50]
            data = self._get("videos", {
                "part": "snippet,contentDetails,status", "id": ",".join(batch),
            })
            try:
                response = _VideoResponse.model_validate(data)
            except ValidationError:
                raise YouTubeError("invalid_response") from None
            found = {video.id: video for video in response.items}
            yield VideoBatch(
                tuple(found[value] for value in batch if value in found),
                tuple(value for value in batch if value not in found),
            )

    def get_videos(self, video_ids: Iterable[str]) -> VideoBatch:
        """Convenience aggregate; use iter_video_batches to save partial progress."""
        batches = list(self.iter_video_batches(video_ids))
        return VideoBatch(
            tuple(video for batch in batches for video in batch.videos),
            tuple(value for batch in batches for value in batch.missing_ids),
        )
