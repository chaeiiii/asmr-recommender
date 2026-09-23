# YouTube Content Pipeline — Final MVP

## 1. Goal
Maintain a small, high-quality catalog of public, embeddable ASMR YouTube videos without downloading/re-hosting media.

Initial target: 300–500 unique videos.

## 2. Discovery
Use YouTube Data API v3.

Flow:
`query seeds -> search.list(type=video, videoEmbeddable=true) -> IDs -> videos.list -> eligibility -> upsert -> tag -> catalog`

Deduplicate by `youtube_video_id`. Batch metadata lookups. Treat quota as limited.

## 3. Seed queries
Version-control a compact seed list covering:
- all 10 core Sound triggers;
- Whisper / Soft Spoken / No Talking;
- Visual and Format discovery terms;
- Korean/English/Japanese variants when useful.

Queries are discovery mechanisms, not taxonomy classes.

## 4. Eligibility
Keep only candidates with:
- retrievable public metadata;
- embeddable status true at sync time;
- reasonable ASMR evidence in title/description/tags;
- valid duration;
- no duplicate ID.

No mandatory view-count threshold.

## 5. Stored metadata
Store only what product needs:
- YouTube ID;
- title/description;
- channel ID/name;
- thumbnail;
- duration;
- published date;
- conservative normalized language;
- embed/availability state;
- last sync timestamp.

## 6. Keyword tagging v1
Input: normalized title + description + YouTube tags.

Process:
1. lowercase + Unicode normalization;
2. canonical phrase/synonym dictionary;
3. explicit negation rules;
4. deterministic confidence;
5. upsert `video_triggers` with `tagger_version=keyword_v1`.

Suggested confidence:
- title exact phrase 0.95;
- YouTube tag exact phrase 0.90;
- description exact phrase 0.75;
- weak synonym 0.60.

Manual override takes precedence. Do not infer Speed/Intensity/Language without evidence.

## 7. Search readiness
Catalog tagging must support MVP Search filters: Sound, Voice, Speed, Language, Format. A filter should only be exposed in UI if catalog coverage/quality is sufficient.

## 8. Listening-test sample curation
Separate from bulk tagging.

For each core Sound trigger:
1. collect strong candidates;
2. project owner manually listens/watches;
3. choose representative 5–15 sec segment;
4. record video ID/start/end/trigger/notes;
5. verify embed;
6. mark verified.

Target pool: 20–30 samples across 10 Sound triggers.

Codex may build scripts/forms but **must not invent timestamps**.

Seed CSV:
```csv
trigger_key,youtube_video_id,start_sec,end_sec,notes
tapping,abc123,105,114,slow glass tapping
```

## 9. Refresh job
Refresh stored YouTube API metadata at least within applicable policy windows; target <=30 days for active catalog.

Flow:
`stale rows -> videos.list batch -> update metadata/status -> mark missing/private/deleted/non-embeddable -> remove from active recommendation/search candidates`

## 10. Failure handling
- quota/403: stop cleanly, preserve progress;
- transient network/5xx: bounded retries;
- invalid video: mark unavailable;
- missing description/tags: allow title-only tagging;
- runtime embed failure: frontend offers another result and does not record dislike automatically.

## 11. Observability
Log per ingestion/refresh run:
- queries/API calls;
- candidates;
- inserted/updated/duplicate/rejected counts;
- tags created/updated;
- unavailable videos;
- failures by reason.

## 12. Suggested modules
```text
backend/app/services/youtube_client.py
backend/app/services/tagging.py
backend/app/scripts/collect_youtube.py
backend/app/scripts/tag_videos.py
backend/app/scripts/refresh_youtube.py
backend/app/scripts/import_trigger_samples.py
backend/app/config/trigger_keywords.json
```

## 13. Official references
- https://developers.google.com/youtube/v3/docs/search/list
- https://developers.google.com/youtube/v3/docs/videos/list
- https://developers.google.com/youtube/iframe_api_reference
- https://developers.google.com/youtube/terms/developer-policies
