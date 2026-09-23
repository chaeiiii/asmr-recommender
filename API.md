# Backend API Contract — Final MVP

## 1. Conventions
- FastAPI; base prefix `/api/v1`.
- Anonymous identity from backend-issued HttpOnly cookie.
- Client never supplies arbitrary user IDs.
- Active catalog endpoints return only available/embeddable videos.

## 2. Session
### `POST /session`
Create/return anonymous session.

Response includes:
```json
{
  "initial_test_completed": false,
  "onboarding_completed": false,
  "next_route": "/test"
}
```
For completed users, `next_route` is `/home`.

## 3. Taxonomy
### `GET /triggers`
Optional query: `family`, `core`, `active`.

## 4. Sound-first test
### `GET /test/samples`
Return stable 6-sample base assignment and any already-created optional assignment. Do not return app primary-trigger labels for unanswered samples.

### `POST /test/samples/{sample_id}/response`
Body: `{"response":"like|neutral|dislike|skip"}`.
Idempotently create/update response and preference evidence.

### `POST /test/extend`
Available after all six base samples have responses. Creates the same stable optional assignment on repeated calls; max 2 samples; never >8 total.

### `POST /test/complete`
Requires all created assignments to have responses. Returns next route `/onboarding/voice`.

## 5. Voice/language onboarding
### `GET /onboarding/voice`
### `POST /onboarding/voice`
Body: `{"voice_mode":"talking|no_talking|both"}`.
- no_talking -> clear languages -> extra preferences;
- talking/both -> language step.

### `GET /onboarding/languages`
### `POST /onboarding/languages`
Body examples:
```json
{"languages":["ko","en"],"no_preference":false}
```
```json
{"languages":[],"no_preference":true}
```

## 6. Checkbox extra preferences
### `GET /onboarding/extra-preferences`
Return grouped checkboxes:
- Sound: only unpresented core Sound triggers;
- Visual: all active MVP Visual;
- Format: all active MVP Format.

No media fields.

### `POST /onboarding/extra-preferences`
Body:
```json
{"liked_features":["paper_crinkling","hand_movements","roleplay"]}
```
Zero selections is valid Skip. Selected items create weak positive self-report evidence. Successful submit completes onboarding and returns `/my-taste?first=1`.

## 7. My Taste
### `GET /me/preferences`
Return:
- taxonomy version;
- voice mode;
- languages/no-preference;
- feature items with score, evidence count, display state;
- recently discovered items;
- unknown/low-evidence items.

Display state is derived server-side: e.g. love/like/neutral/dislike/not_tried. UI should not present score as probability.

## 8. Home recommendations
### `GET /recommendations?limit=20`
Requires completed onboarding.

Returns active video metadata, feature chips, ranking score, and 1–2 reason features. Records Home impressions.

## 9. Discover
### `GET /discover?limit=10`
Return exploration candidates emphasizing unknown/low-evidence/skipped features while remaining reasonably adjacent to known likes. Records Discover impressions.

## 10. Search
### `GET /search`
Supported query params:
- `q` optional text query;
- repeated `sound` keys;
- `voice` key;
- `speed` key;
- repeated `language` values;
- repeated `format` keys;
- `min_duration_sec`, `max_duration_sec`;
- `limit`, `cursor` or page.

Search filters are request-level hard filters. Search behavior does not update preference scores by itself.

## 11. Video interactions
### `POST /videos/{video_id}/interactions`
Body:
```json
{"type":"play|like|dislike|skip","watch_duration_sec":null}
```
Rules:
- like/dislike update confidently tagged features;
- dislike suppresses exact video from Home;
- skip de-prioritizes exact video temporarily and does not update all feature scores;
- play alone does not strongly update preference in v1.

## 12. Saved
### `POST /videos/{video_id}/favorite`
### `DELETE /videos/{video_id}/favorite`
### `GET /favorites`
Idempotent. Removing favorite is not dislike.

## 13. Internal/admin commands
Not public HTTP endpoints in MVP:
- collect YouTube catalog;
- keyword tag videos;
- refresh YouTube metadata;
- import reviewed trigger-sample CSV.

## 14. Error format
```json
{"detail":{"code":"VIDEO_UNAVAILABLE","message":"This video is no longer available."}}
```
Use stable application codes.

## 15. Minimum API tests
- anonymous session + next-route behavior;
- stable base/optional assignments;
- max 8 onboarding samples;
- response idempotency;
- No Talking language clearing;
- language no-preference exclusivity;
- extra checkbox validation and empty Skip;
- onboarding guards;
- recommendations exclude unavailable/non-embeddable/disliked exact videos;
- skip does not create feature dislike;
- favorite idempotency;
- Search filters work independently and in combination;
- completed returning session routes to Home.
