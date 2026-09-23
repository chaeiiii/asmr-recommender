# Database Design — Final MVP

## 1. Database
PostgreSQL is the MVP source of truth. Use SQLAlchemy + Alembic migrations.

## 2. Tables
### `users`
- `id UUID PK`
- `created_at timestamptz not null`
- `initial_test_completed_at timestamptz null`
- `voice_mode varchar(16) null` — talking/no_talking/both
- `language_no_preference boolean default false`
- `onboarding_completed boolean default false`
- `taxonomy_version varchar(20) not null`

Anonymous user ID is stored in a secure HttpOnly cookie session.

### `triggers`
- `id serial PK`
- `key varchar(64) unique not null`
- `display_name varchar(100) not null`
- `family varchar(32) not null`
- `description text null`
- `is_core boolean default false`
- `active boolean default true`

Allowed family: sound/voice/visual/format/speed/intensity.

### `videos`
- `id bigserial PK`
- `youtube_video_id varchar(20) unique not null`
- `title text not null`
- `description text null`
- `channel_id varchar(64) not null`
- `channel_name text not null`
- `thumbnail_url text null`
- `duration_sec integer null`
- `language varchar(16) null`
- `published_at timestamptz null`
- `embeddable boolean not null default true`
- `availability_status varchar(32) not null default 'active'`
- `last_synced_at timestamptz not null`
- `created_at timestamptz not null default now()`

### `video_triggers`
- `video_id bigint FK videos`
- `trigger_id int FK triggers`
- `confidence numeric(4,3) not null`
- `source varchar(20) not null` — keyword/manual/future model
- `tagger_version varchar(30) not null`
- `created_at timestamptz not null`

PK `(video_id, trigger_id)`. Manual tag wins over automated tag for same pair.

### `trigger_samples`
- `id serial PK`
- `primary_trigger_id int FK triggers`
- `video_id bigint FK videos`
- `start_sec int not null`
- `end_sec int not null`
- `verified boolean default false`
- `notes text null`
- `created_at timestamptz not null`

Application constraints: start >= 0, end > start, hard max 30 sec; target 8–12 sec.

### `initial_test_assignments`
- `id bigserial PK`
- `user_id UUID FK users`
- `sample_id int FK trigger_samples`
- `phase varchar(16) not null` — base/optional
- `position smallint not null`
- `test_version varchar(32) not null`
- `created_at timestamptz not null`

Unique `(user_id, sample_id)` and `(user_id, position)`.

### `test_responses`
- `id bigserial PK`
- `assignment_id bigint FK initial_test_assignments unique`
- `response varchar(16) not null` — like/neutral/dislike/skip
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

Repeated answer updates the row; it never double-counts evidence.

### `user_language_preferences`
- `user_id UUID FK users`
- `language varchar(16) not null`
- `created_at timestamptz not null`

PK `(user_id, language)`. Must be empty when `language_no_preference=true` or voice mode=no_talking.

### `user_preferences`
Aggregate current feature preference.
- `user_id UUID FK users`
- `trigger_id int FK triggers`
- `score numeric(5,4) not null` in [-1,1]
- `evidence_count int not null default 0`
- `last_evidence_source varchar(32) null`
- `updated_at timestamptz not null`

PK `(user_id, trigger_id)`.

### `preference_events`
Audit/evidence ledger.
- `id bigserial PK`
- `user_id UUID FK users`
- `trigger_id int FK triggers`
- `source varchar(32) not null` — test/self_report/video_like/video_dislike/discover_like/discover_dislike
- `observation numeric(4,3) not null`
- `reference_type varchar(24) null`
- `reference_id varchar(64) null`
- `created_at timestamptz not null`

### `interactions`
Video-level behavior.
- `id bigserial PK`
- `user_id UUID FK users`
- `video_id bigint FK videos`
- `type varchar(16) not null` — play/like/dislike/skip
- `watch_duration_sec int null`
- `created_at timestamptz not null`

Like/dislike can update feature preference. Skip is item-level avoidance only in v1.

### `favorites`
- `user_id UUID FK users`
- `video_id bigint FK videos`
- `created_at timestamptz not null`

PK `(user_id, video_id)`.

### `recommendation_impressions`
- `id bigserial PK`
- `user_id UUID FK users`
- `video_id bigint FK videos`
- `surface varchar(16) not null` — home/discover
- `algorithm_version varchar(32) not null`
- `score numeric(8,6) null`
- `reason_json jsonb null`
- `created_at timestamptz not null`

## 3. Recommended indexes
- `videos(availability_status, embeddable)`
- `videos(language)`
- `videos(channel_id)`
- `video_triggers(trigger_id, confidence)`
- `interactions(user_id, created_at desc)`
- `interactions(user_id, video_id, type)`
- `favorites(user_id, created_at desc)`
- `recommendation_impressions(user_id, created_at desc)`
- `user_preferences(user_id, score)`

## 4. State rules
- new -> test -> voice -> conditional language -> extra preferences -> onboarding complete;
- completed users default to Home on later visits;
- No Talking clears language preferences;
- checkbox omission does not create negative preference evidence;
- unavailable/non-embeddable videos remain in DB for history but are excluded from active surfaces.

## 5. Data ownership/compliance
Never store downloaded YouTube media. Store only allowed metadata, IDs, timestamps, and app-generated data. YouTube metadata must be refreshable and availability changes must propagate to recommendation/search results.
