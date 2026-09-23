# UI / UX Flow — Final MVP

## 1. UX goal
Get first-time users to a useful recommendation quickly, then make repeat visits about listening and discovery rather than retaking a test.

## 2. Route map
```text
/                       landing/session bootstrap
/test                   sound-first test
/onboarding/voice       Talking / No Talking / Both
/onboarding/language    conditional language
/onboarding/extra-preferences  checkbox completion
/my-taste?first=1       first result
/home                   For You
/discover               exploration
/search                 direct filtered search
/favorites              Saved
/my-taste               living profile
```

Completed returning users default to `/home`.

## 3. Persistent mobile navigation
After onboarding, bottom nav:
`Home | Discover | Search | Saved | My Taste`

## 4. Landing
Simple promise: personalized ASMR based on what the user actually likes listening to.
CTA: `Find my ASMR taste`.
No login wall.

## 5. Sound-first test
One sample per screen/card.

Show:
- progress `1 / 6` or optional extension state;
- official visible YouTube player;
- Like / Neutral / Dislike / Skip;
- after response, optional reveal: `That was Tapping`.

After sample 6:
`Want to try 2 more sounds?`
- `Try 2 more`
- `Continue`

## 6. Voice
Prompt: `Which do you usually prefer?`
Three large cards: Talking / No Talking / Both.

## 7. Language
Only Talking/Both.
Prompt: `For ASMR with talking, which languages do you prefer?`
Checkbox/chips: Korean / English / Japanese / Other / No preference.

## 8. Extra preferences
No playback.
Prompt: `Any other ASMR elements you already know you like?`
Subtext: optional; choose any; Skip available.

Sections:
- Sound — only unpresented Sound triggers;
- Visual — Hand Movements, Camera Brushing, Light Triggers, Slow Movements;
- Format — Roleplay, Personal Attention, Trigger Assortment, Single Trigger.

Use clear Korean-friendly descriptions beneath unfamiliar labels.

## 9. First My Taste
The onboarding result should feel useful but not final.

Sections:
- `Your current taste` short summary;
- Favorite Sounds;
- Voice + Languages;
- known Visual/Format likes;
- Not tried yet;
- CTA `See my recommendations`.

Do not emphasize numeric percentages.

## 10. Home / For You
Primary repeat-use screen.

Recommendation card:
- thumbnail;
- title/channel/duration;
- 2–4 feature chips;
- simple reason;
- Play;
- Like / Dislike / Save / Skip.

On Play, use official inline/modal YouTube player.
Feedback should feel lightweight. Do not force forms.

## 11. Discover
Purpose: expand taste.

Suggested sections/cards:
- `Try something new` — unknown Sound/Visual/Format;
- `Near your taste` — known-liked + unknown feature;
- `Try again` — previously skipped low-evidence area.

Normal YouTube video cards are enough; no need for onboarding-style short sample playback for all Discover content.

## 12. Search
Filter-first discovery.

Top/filter sheet:
- Sound Trigger;
- Voice;
- Speed;
- Language;
- Format;
- Duration optional.

Show active applied-filter chips and easy Clear All. Results use normal video cards. Search itself does not alter My Taste.

## 13. Saved
Saved videos newest-first. Empty state links to Home.

## 14. My Taste
A living profile, not a final test result.

Recommended sections:
1. Taste Summary — concise descriptive sentence based only on observed preferences;
2. Favorite Sounds — Love/Like states;
3. Voice / Language;
4. Visual / Format likes;
5. Neutral / Disliked when evidence exists;
6. `Not tried yet` / low-evidence items;
7. `Recently discovered` when available;
8. CTA `Discover new tastes`;
9. CTA `See ASMR for my taste` -> Home.

Avoid radar charts in MVP. Prefer cards/chips/state labels.

## 15. Guard/resume behavior
If onboarding incomplete, route to first unfinished step in order:
`test -> voice -> conditional language -> extra preferences`.

Completed users who open `/` should be sent to Home.

## 16. Loading/error/accessibility
Every data screen: loading, retry, empty, unavailable-video state.
Embed failure -> `Show another`; do not record dislike.
All controls keyboard accessible with visible focus and reasonable tap targets.
