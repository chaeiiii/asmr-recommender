"""Import owner-reviewed segment timestamps; never derive media timestamps."""

import csv
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TextIO

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Trigger, TriggerSample, Video
from app.taxonomy import TRIGGERS

CORE_SOUND_KEYS = frozenset(
    trigger.key for trigger in TRIGGERS if trigger.family == "sound" and trigger.is_core
)
COLUMNS = ("trigger_key", "youtube_video_id", "start_sec", "end_sec", "notes")


class SampleValidationError(ValueError):
    """A CSV header or row fails reviewed-sample validation."""


@dataclass
class ImportResult:
    inserted: int = 0
    updated: int = 0


def import_trigger_samples(session: Session, source: TextIO) -> ImportResult:
    """Atomic import using a dedicated session; repeats update notes/verification.

    Serialize PostgreSQL imports because the existing schema has no natural-key
    unique constraint. No schema changes or migration are needed.
    """
    result = ImportResult()
    try:
        reader = csv.DictReader(source, strict=True)
        if reader.fieldnames != list(COLUMNS):
            raise SampleValidationError("CSV header must be: " + ",".join(COLUMNS))
        if session.get_bind().dialect.name == "postgresql":
            session.execute(
                text("LOCK TABLE trigger_samples IN SHARE ROW EXCLUSIVE MODE")
            )
        for row in reader:
            prefix = f"CSV line {reader.line_num}: "
            if None in row or any(value is None for value in row.values()):
                raise SampleValidationError(prefix + "expected exactly five columns")
            key = row["trigger_key"].strip()
            if key not in CORE_SOUND_KEYS:
                raise SampleValidationError(
                    prefix + "trigger_key must be a canonical core Sound key"
                )
            seconds = []
            for column in ("start_sec", "end_sec"):
                value = row[column].strip()
                if not re.fullmatch(r"[0-9]{1,10}", value) or int(value) > 2147483647:
                    raise SampleValidationError(
                        prefix + column + " must be a nonnegative integer"
                    )
                seconds.append(int(value))
            start, end = seconds
            if end <= start or end - start > 30:
                raise SampleValidationError(
                    prefix + "require end_sec > start_sec and duration <= 30 seconds"
                )
            trigger = session.scalar(
                select(Trigger).where(
                    Trigger.key == key,
                    Trigger.family == "sound",
                    Trigger.is_core.is_(True),
                )
            )
            if trigger is None:
                raise SampleValidationError(
                    prefix + "core Sound trigger is not seeded: " + key
                )
            video_id = row["youtube_video_id"].strip()
            video = session.scalar(
                select(Video).where(Video.youtube_video_id == video_id)
            )
            if video is None:
                raise SampleValidationError(
                    prefix + "video does not exist: " + video_id
                )
            sample = session.scalar(
                select(TriggerSample)
                .where(
                    TriggerSample.primary_trigger_id == trigger.id,
                    TriggerSample.video_id == video.id,
                    TriggerSample.start_sec == start,
                    TriggerSample.end_sec == end,
                )
                .order_by(TriggerSample.id)
            )
            if sample is None:
                sample = TriggerSample(
                    primary_trigger_id=trigger.id,
                    video_id=video.id,
                    start_sec=start,
                    end_sec=end,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(sample)
                result.inserted += 1
            else:
                result.updated += 1
            sample.verified = True
            sample.notes = row["notes"] or None
            session.flush()
        session.commit()
    except csv.Error as exc:
        session.rollback()
        raise SampleValidationError(f"CSV line {reader.line_num}: {exc}") from exc
    except Exception:
        session.rollback()
        raise
    return result
