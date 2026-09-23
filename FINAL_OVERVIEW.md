# ASMR Personalized Recommendation Web App — One-Page Final Plan

## What it is
A mobile-first web app that learns a user's ASMR preferences and continuously recommends YouTube ASMR videos. The first taste test is only onboarding; the real product is the recommendation/feedback/discovery loop.

## User flow
**First visit**
`6 short Sound tests -> optional +2 -> Talking/No Talking/Both -> conditional languages -> optional preference checkboxes -> My Taste -> For You`

**Returning visits**
`Home/For You -> listen -> Like/Dislike/Save/Skip -> taste updates -> better recommendations`

**Exploration**
`Discover -> unknown/adjacent Sound/Visual/Format -> feedback -> My Taste expands`

**Direct intent**
`Search -> Sound/Voice/Speed/Language/Format filters -> YouTube results`

## Main navigation
**Home | Discover | Search | Saved | My Taste**

- **Home:** personalized daily-use recommendation feed.
- **Discover:** find new ASMR elements beyond existing favorites.
- **Search:** directly find a desired ASMR combination.
- **Saved:** replay favorite videos.
- **My Taste:** living profile of current learned preferences, not a one-time result.

## Taxonomy
**Sound (10):** Tapping, Scratching, Mic Brushing, Ear Cleaning, Mouth Sounds, Paper/Crinkling, Typing/Writing, Fabric/Soft Object, Water/Liquid, Eating/Chewing.

**Voice:** Whisper, Soft Spoken, No Talking.

**Visual:** Hand Movements, Camera Brushing, Light Triggers, Slow Movements.

**Format:** Roleplay, Personal Attention, Trigger Assortment, Single Trigger.

**Speed:** Slow, Normal, Fast.  **Intensity:** Gentle, Normal, Aggressive.

## Cold-start onboarding
The first six Sound samples prioritize diverse sound qualities: Tapping, Scratching, Mic Brushing, Ear Cleaning, Mouth Sounds, Water/Liquid. The user can optionally try two of the remaining four Sound triggers.

Short segments are manually reviewed YouTube timestamps. Media is never downloaded. After the listening step, Voice and conditional Language are collected. The final optional checkbox step lets users add known likes from untested Sound + Visual + Format without listening again.

## Recommendation model
MVP uses an explainable **content-based recommender**.
- direct listening Like/Dislike = strong evidence;
- checkbox selections = weak positive evidence;
- video Like/Dislike updates confidently tagged features;
- Save is not automatically a preference signal;
- Skip only de-prioritizes that exact video in v1;
- Language and broad Voice choice are soft ranking signals.

Recommendations include a simple reason such as `Because you like Ear Cleaning + No Talking`.

## Content pipeline
`YouTube Data API -> collect 300–500 videos -> dedupe/eligibility -> metadata -> keyword multi-label tagging -> PostgreSQL -> recommendation/search catalog`

Active metadata is periodically refreshed. Unavailable/non-embeddable videos are removed from active recommendations/search. Official YouTube embeds are used for playback.

## Architecture
`Next.js + TypeScript + Tailwind` frontend  
`FastAPI + Python` backend  
`PostgreSQL + SQLAlchemy + Alembic` data layer  
`YouTube Data API + IFrame Player API` content/playback  
`Python content_v1 recommender` personalization

## MVP definition of done
A new anonymous user can complete onboarding, receive personalized recommendations, play YouTube content, give feedback, save videos, search by ASMR attributes, discover new preferences, view an evolving My Taste profile, close the site, return later, and continue directly from Home with the same learned profile.

## Not in MVP
No native app, OAuth/login requirement, social features, AI-generated ASMR, collaborative filtering, creator payments, media downloading, or medical claims.
