# ASMR Taxonomy — v2.0 Final

## 1. Purpose
Provide stable canonical feature keys shared by ingestion, tagging, onboarding, recommendation, Search, Discover, and My Taste.

## 2. Families
- `sound`
- `voice`
- `visual`
- `format`
- `speed`
- `intensity`

Language is stored as normalized metadata/preferences, not as a trigger family.

## 3. Core Sound triggers
| key | display | examples |
|---|---|---|
| `tapping` | Tapping | wood/glass/plastic/nail tapping |
| `scratching` | Scratching | surface scratching; mic scratching is a subtype |
| `mic_brushing` | Mic Brushing | fluffy/brush-on-mic sounds |
| `ear_cleaning` | Ear Cleaning | ear picking, cotton swab, ear-focused cleaning |
| `mouth_sounds` | Mouth Sounds | lip/tongue/wet/dry mouth sounds |
| `paper_crinkling` | Paper / Crinkling | page turning, paper, wrapper crinkles |
| `typing_writing` | Typing / Writing | keyboard, pen, pencil writing |
| `fabric_soft_object` | Fabric / Soft Object | cloth/towel/soft-object rubbing |
| `water_liquid` | Water / Liquid | pouring, drops, spray, liquid shaking |
| `eating_chewing` | Eating / Chewing | chewing, crunching, food sounds |

### Merge/removal rules
- generic `Brushing` is not a canonical Sound trigger;
- `Mic Scratching` maps to `scratching` subtype, not a top-level feature;
- `Page Turning` maps to `paper_crinkling`;
- `Keyboard` maps to `typing_writing`;
- `Water Sounds` maps to `water_liquid`.

## 4. Voice
| key | display |
|---|---|
| `whisper` | Whisper |
| `soft_spoken` | Soft Spoken |
| `no_talking` | No Talking |

Onboarding asks high-level `talking / no_talking / both`; fine-grained Whisper vs Soft Spoken is learned later.

## 5. Visual
| key | display |
|---|---|
| `hand_movements` | Hand Movements |
| `camera_brushing` | Camera Brushing |
| `light_triggers` | Light Triggers |
| `slow_movements` | Slow Movements |

## 6. Format
| key | display |
|---|---|
| `roleplay` | Roleplay |
| `personal_attention` | Personal Attention |
| `trigger_assortment` | Trigger Assortment |
| `single_trigger` | Single Trigger |

Roleplay scenes such as medical, salon, spa, makeup, or eye exam are future subtypes, not MVP top-level keys.

## 7. Speed
- `slow`
- `normal`
- `fast`

## 8. Intensity
- `gentle`
- `normal_intensity`
- `aggressive`

## 9. Language
Normalized video/preference values:
- `ko`
- `en`
- `ja`
- `other`
- `unknown`

User setting `no_preference` is stored separately and is not a video language.

## 10. Multi-label rules
A video may have multiple features across and within families.

Example:
`Korean Whisper Ear Cleaning Roleplay`
- sound: `ear_cleaning`
- voice: `whisper`
- format: `roleplay`, potentially `personal_attention`
- language: `ko`

Example:
`Fast Aggressive Mic Scratching No Talking`
- sound: `scratching`
- voice: `no_talking`
- speed: `fast`
- intensity: `aggressive`

Do not force exactly one tag per family unless a field is inherently singular.

## 11. Initial listening-test policy
Base six product-diversity heuristic:
- tapping
- scratching
- mic_brushing
- ear_cleaning
- mouth_sounds
- water_liquid

Optional +2 pool:
- paper_crinkling
- typing_writing
- fabric_soft_object
- eating_chewing

Only core Sound features are primary short-test labels.

## 12. Extra checkbox policy
After Sound/Voice/Language onboarding, show:
- unpresented core Sound features;
- all active Visual features;
- all active Format features.

Do not show Voice, Speed, or Intensity on this checkbox screen.

## 13. Search policy
Search may filter any catalog-backed feature that is reliably tagged, including Sound, Voice, Format, Speed, and Language. Intensity can be exposed after tagging quality is acceptable; it is optional for first MVP UI.

## 14. Versioning
Current version: `2.0`.

Never silently redefine a canonical key. Taxonomy changes that alter semantics require a version bump and migration/update plan.
