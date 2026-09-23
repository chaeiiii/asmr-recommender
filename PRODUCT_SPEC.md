# ASMR Personalized Recommendation Web App — Final Product Spec

## 1. Product identity
This is **not** a one-time ASMR taste-test site. It is a mobile-first web app that continuously learns a user's ASMR preferences and recommends embeddable YouTube ASMR videos.

The onboarding test exists only to solve cold start. The core retention loop is:

`For You -> play -> like/dislike/save/skip -> preference update -> better For You`

A second exploration loop is:

`Discover -> try unfamiliar ASMR element -> feedback -> My Taste update -> broader recommendations`

My Taste is a living profile of what the system currently understands about the user, not a fixed personality-test result.

## 2. MVP objective
Prove that a trigger-level preference model can produce useful, explainable YouTube ASMR recommendations while keeping onboarding short.

## 3. MVP scope
- Anonymous browser session; no login required.
- 10 core Sound triggers plus separate Voice / Visual / Format / Speed / Intensity families.
- 20–30 human-reviewed short YouTube test segments.
- Sound-first onboarding: 6 base samples + optional 2 extra samples.
- Voice choice: Talking / No Talking / Both.
- Conditional language preference for Talking/Both.
- Optional checkbox-only preference completion: untested Sound + Visual + Format.
- Initial YouTube catalog: 300–500 active, embeddable videos.
- Content-based recommender only.
- Home / Discover / Search / Saved / My Taste main navigation.
- Like / dislike / save / skip feedback.
- YouTube metadata refresh pipeline.
- Mobile-first responsive web app.

## 4. Explicitly out of scope
- Native mobile apps.
- Social features, comments, friend matching.
- AI-generated ASMR audio/video.
- Downloading, extracting, caching, or re-hosting YouTube media.
- Collaborative filtering before real multi-user data exists.
- Automatic listening-test timestamp detection.
- Creator accounts, payments, subscriptions.
- Full authentication/OAuth.
- Medical, insomnia-treatment, or scientific personality claims.

## 5. Final onboarding flow
### 5.1 Sound-first test
Do not ask users to select favorite trigger names before listening.

Base six:
- `tapping`
- `scratching`
- `mic_brushing`
- `ear_cleaning`
- `mouth_sounds`
- `water_liquid`

For each sample:
- use an official visible YouTube embed;
- play a human-reviewed 5–15 second segment, target 8–12 seconds;
- response choices: Like / Neutral / Dislike / Skip;
- do not show the app's trigger label before response;
- trigger name may be revealed after response.

The flow is called **sound-first**, not blind, because YouTube player metadata may expose title information.

### 5.2 Optional +2
After the six base responses, offer two additional sounds.

If accepted, choose two distinct unpresented triggers from:
- `paper_crinkling`
- `typing_writing`
- `fabric_soft_object`
- `eating_chewing`

The extra two are optional and never block onboarding.

### 5.3 Voice preference
Ask exactly one high-level question:
- Talking
- No Talking
- Both

This is a soft preference. Do not force Whisper vs Soft Spoken during onboarding.

### 5.4 Conditional language preference
Show only when voice mode is Talking or Both.

Options:
- Korean (`ko`)
- English (`en`)
- Japanese (`ja`)
- Other (`other`)
- No preference

Rules:
- multi-select specific languages;
- No preference is mutually exclusive with specific languages;
- language is a soft ranking boost, not a hard filter;
- No Talking videos ignore spoken-language preference.

### 5.5 Optional extra-preference checkboxes
Prompt concept: **“Any other ASMR elements you already know you like?”**

No audio/video plays here. Multi-select checkboxes only; Skip is allowed.

Show:
- Sound: only core Sound triggers never presented in the listening test;
- Visual: Hand Movements, Camera Brushing, Light Triggers, Slow Movements;
- Format: Roleplay, Personal Attention, Trigger Assortment, Single Trigger.

Do not repeat Voice. Do not ask Speed or Intensity during onboarding.

Selected checkboxes create weak positive self-reported priors. Unselected items remain unknown, never negative.

### 5.6 First My Taste
After onboarding, show My Taste once, then CTA to For You. On all later visits, completed users land on Home by default.

## 6. Main product after onboarding
### Home / For You
The primary repeated-use surface.

Each recommendation card shows:
- thumbnail;
- title and channel;
- duration;
- relevant feature chips;
- simple reason, e.g. `Because you like Ear Cleaning + No Talking`;
- Play / Like / Dislike / Save / Skip actions.

Feedback updates future recommendations. Do not instantly reshuffle the entire feed after every action; refresh naturally.

### Discover
Purpose: preference exploration, not more of the same.

Prioritize:
- unknown features;
- low-evidence features;
- previously skipped features;
- adjacent features that co-occur with liked features.

Discover may surface Sound, Visual, or Format preferences through normal YouTube videos. Feedback uses the same profile model as Home.

### Search
Purpose: user-directed discovery when the user already knows what they want.

MVP filters:
- Sound trigger;
- Voice;
- Speed;
- Language;
- Format;
- optional duration range.

Explicit search filters are hard filters for that search request. They do not permanently rewrite the user's taste profile unless the user later gives feedback on a result.

### Saved
Show saved/favorited videos newest-first. Removing a save is not a dislike.

### My Taste
A living preference profile containing:
- favorite/liked Sound triggers;
- neutral/disliked/unknown Sound triggers when evidence exists;
- Voice mode;
- preferred languages when applicable;
- known Visual and Format likes;
- recently discovered preferences;
- unknown/low-evidence elements with CTA to Discover;
- CTA back to For You.

Do not display preference scores as scientific probabilities. MVP should prefer human-readable states such as Love / Like / Neutral / Dislike / Not tried.

## 7. Persistent learning rules
Signals:
- short test Like/Dislike: strong direct evidence for the curated primary Sound trigger;
- checkbox selection: weak positive evidence;
- Home/Discover video Like/Dislike: updates confidently tagged video features;
- Save: storage action only in v1, not a preference update by itself;
- Skip on a normal video: weak item-level negative/avoidance signal only; do not infer dislike of all its features;
- Play/watch duration: log for future analysis, do not heavily optimize on watch time in v1.

Unselected, unknown, and skipped onboarding features are never treated as dislikes.

## 8. Anonymous session behavior
- First visit: create anonymous user in an HttpOnly cookie-backed session.
- Incomplete onboarding: resume first incomplete onboarding step.
- Completed onboarding: default route is `/home`.
- No email/name required for MVP.
- Future login may link an identity to an existing anonymous profile but is not part of MVP.

## 9. Short-sample curation
The project owner approves final timestamps.

For each core Sound trigger:
- prepare 2–3 candidate YouTube videos;
- manually identify a representative 5–15 second segment;
- store only video ID, start second, end second, primary trigger, notes;
- never download or extract the media.

Codex may implement curation/import tooling but must never invent timestamps.

## 10. Success criteria
A fresh browser can:
1. complete the 6-sample test and optionally +2;
2. choose Voice and, when relevant, Language;
3. complete or skip checkbox preferences;
4. see an initial My Taste profile;
5. receive at least 10 personalized Home recommendations;
6. play a YouTube embed;
7. like/dislike/save/skip a recommendation;
8. observe persisted profile/ranking changes after explicit like/dislike feedback;
9. use Discover, Search, Saved, and My Taste;
10. return later and land directly on Home with the same anonymous profile.

## 11. Product principles
- The taste test is onboarding, not the product.
- Trigger-first, not creator-first.
- Sound-first before terminology.
- Do not ask twice for the same initial signal.
- Unknown does not mean dislike.
- Recommendations must remain explainable.
- Prefer a small, clean catalog to a huge noisy catalog for MVP.
- Exploration is a core feature, not an afterthought.
- My Taste must evolve with use.
