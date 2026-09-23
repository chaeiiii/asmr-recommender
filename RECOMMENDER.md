# Recommendation Design — content_v1 Final

## 1. Principle
Use a deterministic, explainable content-based recommender. Collaborative filtering is out of scope until real multi-user data exists.

## 2. Vectors
Video feature `v_i` = `video_triggers.confidence` in [0,1].
User feature `u_i` = aggregate `user_preferences.score` in [-1,1].
Unknown feature = 0.

## 3. Onboarding evidence
### Short-test response
- like: +1.0
- neutral: 0.0
- dislike: -1.0
- skip: no feature update

For the curated primary Sound trigger only:
`new = (1-alpha) * old + alpha * observation`

`alpha_sample = 0.45`.

Do not update secondary tags from a short sample.

### Checkbox self-report
Selected eligible feature with no stronger evidence starts at `+0.35` and records source `self_report`. Omitted items remain unknown.

## 4. Voice/language soft priors
Voice mode:
- talking: +0.12 to whisper/soft_spoken candidates;
- no_talking: +0.12 to no_talking candidates;
- both: no adjustment;
- mismatch penalty at most -0.05; never hard exclude solely from onboarding mode.

Language:
- only applies to spoken candidates;
- preferred language match +0.08;
- unknown/nonpreferred language no penalty in v1;
- no_preference or no_talking -> no language adjustment.

## 5. Video-feedback update
Like = +1.0; Dislike = -1.0.
For video features with confidence >= 0.60:
`effective_alpha = 0.20 * confidence`
`new = (1-effective_alpha)*old + effective_alpha*observation`

Save alone does not update taste.
Skip on Home/Discover does **not** update all video features; it only de-prioritizes that exact video for a cooling period.

## 6. Base ranking
`base_score = sum(u_i * v_i * w_family(i)) / max(sum(v_i * w_family(i)), epsilon)`

Initial weights:
- Sound 1.00
- Voice 0.65
- Visual 0.40
- Format 0.35
- Speed 0.45
- Intensity 0.30

Then add voice/language soft adjustments.

## 7. Candidate filters
Exclude:
- unavailable/private/deleted/non-embeddable;
- exact videos explicitly disliked;
- exact videos under recent-skip cooldown;
- videos with no usable taxonomy features.

Optional strong-dislike guard: if user score <= -0.80 and video confidence >= 0.80 for a feature, exclude candidate.

## 8. Home post-processing
- sort by score;
- max 2 videos per channel in first 20;
- avoid recent duplicate impressions;
- when positive evidence exists, require at least one positive feature match;
- record impression + reasons;
- do not use popularity boost in v1.

Recommendation reason = top 1–2 positive contribution features.

## 9. Discover v1
Goal: exploration.

Prefer candidates containing:
- unknown feature;
- low-evidence feature;
- previously skipped onboarding feature;
- an unknown feature plus at least one known-liked feature when possible.

Support Sound, Visual, and Format discovery using normal YouTube videos. Do not interpret unchecked onboarding boxes as dislikes.

## 10. Search
Search is user-directed, not recommender-directed.
- explicit requested filters are hard filters for the query;
- preference scores may be used only as a secondary tie-breaker after filter matching;
- merely searching or clicking a filter does not update taste;
- explicit feedback on a search result uses normal video-feedback rules.

## 11. My Taste display states
Suggested display mapping (tunable, not scientific):
- Love: score >= 0.65 with positive evidence;
- Like: 0.25 to <0.65;
- Neutral: >-0.25 to <0.25 with evidence;
- Dislike: <= -0.25;
- Not tried: no evidence.

Do not call these probabilities.

## 12. Evaluation
Technical regression tests:
- direct test evidence stronger than checkbox prior;
- omission remains unknown;
- dislikes lower matching ranking;
- skip does not globally penalize features;
- voice/language adjustments are soft;
- Search filter behavior is independent from preference updates;
- ranking deterministic for fixed fixtures;
- channel diversity and availability guards work.

Product metrics to log later:
- onboarding completion and skip rate;
- Home play/like/dislike/save/skip rate;
- Discover acceptance rate;
- Search use and result engagement;
- returning-session rate.

Do not optimize on watch time alone.

## 13. Version
Algorithm identifier: `content_v1`. Increment for material scoring changes.
