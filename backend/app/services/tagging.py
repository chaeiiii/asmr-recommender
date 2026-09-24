"""Deterministic metadata-only tagging; callers own the database transaction."""

import json
import re
import unicodedata
from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Trigger, Video, VideoTrigger
from app.taxonomy import TRIGGERS

TAGGER_VERSION = "keyword_v1"
KEYWORDS = json.loads(
    (Path(__file__).resolve().parents[1] / "config" / "trigger_keywords.json")
    .read_text(encoding="utf-8")
)
if set(KEYWORDS) != {trigger.key for trigger in TRIGGERS}:
    raise ValueError("Keyword dictionary must match the canonical taxonomy")


def normalize(text: str) -> str:
    """Preserve sentence boundaries for negation while folding phrase separators."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.replace("\n", ";").replace("\r", ";")
    text = re.sub(r"[_/\-\u2010-\u2015]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _negated(text: str, start: int, end: int) -> bool:
    # Negation covers coordinated lists, but stops at sentences/contrast clauses.
    prefix = re.split(r"[.!?;:\n]|\b(?:but|however|with)\b", text[:start])[-1]
    before = re.search(r"\b(?:no|not|without|never|excluding|exclude)\b", prefix)
    suffix = text[end:]
    after = re.match(r"\s+(?:(?:is|are)\s+)?(?:absent|excluded|free)\b", suffix)
    return bool(before or after)


def tag_metadata(
    title: str, description: str | None = None, youtube_tags: Iterable[str] = ()
) -> dict[str, Decimal]:
    """Return strongest evidence per key; explicit negation vetoes that key.

    Each YouTube tag is a separate evidence field, so phrases cannot be assembled
    across tags. Strong synonyms use source confidence; weak synonyms use 0.60.
    No language inference or metadata mutation is performed.
    """
    fields = [(normalize(title), Decimal("0.95"))]
    fields.extend((normalize(tag), Decimal("0.90")) for tag in youtube_tags)
    fields.append((normalize(description or ""), Decimal("0.75")))
    result = {}
    for key, phrases in KEYWORDS.items():
        confidence = Decimal("0")
        veto = False
        for strength, aliases in phrases.items():
            for phrase in aliases:
                pattern = r"(?<!\w)" + re.escape(normalize(phrase)) + r"(?!\w)"
                for text, source_confidence in fields:
                    for match in re.finditer(pattern, text):
                        if _negated(text, match.start(), match.end()):
                            veto = True
                        else:
                            confidence = max(
                                confidence,
                                Decimal("0.60") if strength == "weak"
                                else source_confidence,
                            )
        if confidence and not veto:
            result[key] = confidence
    return result


def tag_video(
    session: Session, video: Video, youtube_tags: Iterable[str] = ()
) -> dict[str, int]:
    """Synchronize only keyword-owned rows; preserve manual/other sources.

    Lock the catalog row to serialize keyword runs for the same video. Existing
    timestamps remain unchanged on reruns. Missing taxonomy seeds fail clearly.
    """
    session.execute(select(Video.id).where(Video.id == video.id).with_for_update())
    matches = tag_metadata(video.title, video.description, youtube_tags)
    triggers = {row.key: row.id for row in session.scalars(select(Trigger))}
    missing = matches.keys() - triggers.keys()
    if missing:
        raise ValueError(f"Missing seeded triggers: {', '.join(sorted(missing))}")
    desired = {triggers[key]: confidence for key, confidence in matches.items()}
    existing = {
        row.trigger_id: row
        for row in session.scalars(
            select(VideoTrigger).where(VideoTrigger.video_id == video.id)
        )
    }
    counts = {"created": 0, "updated": 0, "deleted": 0}
    for trigger_id, row in existing.items():
        if row.source == "keyword" and trigger_id not in desired:
            session.delete(row)
            counts["deleted"] += 1
    for trigger_id, confidence in desired.items():
        row = existing.get(trigger_id)
        if row is None:
            session.add(VideoTrigger(
                video_id=video.id, trigger_id=trigger_id, confidence=confidence,
                source="keyword", tagger_version=TAGGER_VERSION,
                created_at=datetime.now(timezone.utc),
            ))
            counts["created"] += 1
        elif row.source == "keyword" and (
            row.confidence != confidence or row.tagger_version != TAGGER_VERSION
        ):
            row.confidence = confidence
            row.tagger_version = TAGGER_VERSION
            counts["updated"] += 1
    session.flush()
    return counts
