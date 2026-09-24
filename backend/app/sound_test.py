"""Persisted sound-first assignments and replaceable onboarding evidence."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import (
    InitialTestAssignment,
    PreferenceEvent,
    TestResponse,
    Trigger,
    TriggerSample,
    User,
    UserPreference,
    Video,
)
from app.sessions import get_anonymous_user
from app.taxonomy import TAXONOMY_VERSION

router = APIRouter(prefix="/test")
BASE = (
    "tapping",
    "scratching",
    "mic_brushing",
    "ear_cleaning",
    "mouth_sounds",
    "water_liquid",
)
OPTIONAL = (
    "paper_crinkling",
    "typing_writing",
    "fabric_soft_object",
    "eating_chewing",
)
ALPHA = Decimal("0.45")
OBSERVATIONS = {"like": Decimal(1), "neutral": Decimal(0), "dislike": Decimal(-1)}
Database = Annotated[Session, Depends(get_session)]


def locked_user(
    user: Annotated[User, Depends(get_anonymous_user)],
    db: Database,
) -> User:
    # Lock before reading assignments/evidence, including simultaneous first calls.
    return db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


Identity = Annotated[User, Depends(locked_user)]


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response: Literal["like", "neutral", "dislike", "skip"]


def assignments(db: Session, user: User) -> list[InitialTestAssignment]:
    return list(
        db.scalars(
            select(InitialTestAssignment)
            .where(InitialTestAssignment.user_id == user.id)
            .order_by(InitialTestAssignment.position)
        )
    )


def response_for(db: Session, assignment: InitialTestAssignment) -> TestResponse | None:
    return db.scalar(
        select(TestResponse).where(
            TestResponse.assignment_id == assignment.id,
        )
    )


def create_assignments(db: Session, user: User, phase: str) -> None:
    keys = BASE if phase == "base" else OPTIONAL
    count = 6 if phase == "base" else 2
    chosen = []
    for key in keys:
        sample = db.scalar(
            select(TriggerSample)
            .join(Trigger, Trigger.id == TriggerSample.primary_trigger_id)
            .join(Video, Video.id == TriggerSample.video_id)
            .where(
                Trigger.key == key,
                Trigger.family == "sound",
                TriggerSample.verified.is_(True),
                Video.embeddable.is_(True),
                Video.availability_status == "active",
            )
            .order_by(TriggerSample.id)
            .limit(1)
        )
        if sample is not None:
            chosen.append(sample)
        if len(chosen) == count:
            break
    if len(chosen) != count:
        raise HTTPException(503, "Not enough verified Sound samples available")
    now = datetime.now(timezone.utc)
    for position, sample in enumerate(chosen, start=1 if phase == "base" else 7):
        db.add(
            InitialTestAssignment(
                user_id=user.id,
                sample_id=sample.id,
                phase=phase,
                position=position,
                test_version=f"sound_v1_taxonomy_{TAXONOMY_VERSION}",
                created_at=now,
            )
        )
    db.flush()


def payload(db: Session, user: User) -> dict:
    samples = []
    for assignment in assignments(db, user):
        sample = db.get(TriggerSample, assignment.sample_id)
        video = db.get(Video, sample.video_id)
        answer = response_for(db, assignment)
        item = {
            "sample_id": sample.id,
            "phase": assignment.phase,
            "position": assignment.position,
            "youtube_video_id": video.youtube_video_id,
            "start_sec": sample.start_sec,
            "end_sec": sample.end_sec,
            "response": answer.response if answer else None,
        }
        if answer is not None:
            trigger = db.get(Trigger, sample.primary_trigger_id)
            item["primary_trigger"] = {
                "key": trigger.key,
                "display_name": trigger.display_name,
            }
        samples.append(item)
    return {"samples": samples}


@router.get("/samples")
def get_samples(user: Identity, db: Database) -> dict:
    if not assignments(db, user):
        if user.initial_test_completed_at is not None:
            raise HTTPException(409, "Initial test already completed")
        create_assignments(db, user, "base")
    result = payload(db, user)
    db.commit()
    return result


@router.post("/samples/{sample_id}/response")
def respond(sample_id: int, body: Answer, user: Identity, db: Database) -> dict:
    assignment = db.scalar(
        select(InitialTestAssignment).where(
            InitialTestAssignment.user_id == user.id,
            InitialTestAssignment.sample_id == sample_id,
        )
    )
    if assignment is None:
        raise HTTPException(404, "Sample is not assigned to this session")
    answer = response_for(db, assignment)
    if answer is not None and answer.response == body.response:
        db.commit()
        return {"sample_id": sample_id, "response": body.response}
    if user.initial_test_completed_at is not None:
        raise HTTPException(409, "Initial test already completed")
    sample = db.get(TriggerSample, sample_id)
    trigger = db.get(Trigger, sample.primary_trigger_id)
    if trigger.family != "sound":
        raise HTTPException(409, "Assigned primary trigger must be Sound")
    now = datetime.now(timezone.utc)
    event = db.scalar(
        select(PreferenceEvent).where(
            PreferenceEvent.user_id == user.id,
            PreferenceEvent.source == "test",
            PreferenceEvent.reference_type == "test_assignment",
            PreferenceEvent.reference_id == str(assignment.id),
        )
    )
    preference = db.get(UserPreference, (user.id, trigger.id))
    # Remove the previous observation before applying its replacement. Each
    # trigger is presented once, and completed tests cannot change later evidence.
    old = Decimal(preference.score) if preference is not None else Decimal(0)
    count = preference.evidence_count if preference is not None else 0
    if event is not None:
        old = (old - ALPHA * event.observation) / (1 - ALPHA)
        count -= 1
        if count == 0:
            old = Decimal(0)
    if body.response == "skip":
        if event is not None:
            db.delete(event)
            if count == 0:
                db.delete(preference)
            else:
                previous = db.scalar(
                    select(PreferenceEvent)
                    .where(
                        PreferenceEvent.user_id == user.id,
                        PreferenceEvent.trigger_id == trigger.id,
                        PreferenceEvent.id != event.id,
                    )
                    .order_by(
                        PreferenceEvent.created_at.desc(), PreferenceEvent.id.desc()
                    )
                )
                preference.score = old
                preference.evidence_count = count
                preference.last_evidence_source = previous.source if previous else None
                preference.updated_at = now
    else:
        observation = OBSERVATIONS[body.response]
        if event is None:
            event = PreferenceEvent(
                user_id=user.id,
                trigger_id=trigger.id,
                source="test",
                reference_type="test_assignment",
                reference_id=str(assignment.id),
                created_at=now,
            )
            db.add(event)
        event.observation = observation
        if preference is None:
            preference = UserPreference(user_id=user.id, trigger_id=trigger.id)
            db.add(preference)
        preference.score = (1 - ALPHA) * old + ALPHA * observation
        preference.evidence_count = count + 1
        preference.last_evidence_source = "test"
        preference.updated_at = now
    if answer is None:
        answer = TestResponse(assignment_id=assignment.id, created_at=now)
        db.add(answer)
    answer.response = body.response
    answer.updated_at = now
    db.commit()
    return {"sample_id": sample_id, "response": body.response}


def require_base_responses(db: Session, rows: list[InitialTestAssignment]) -> None:
    base = [row for row in rows if row.phase == "base"]
    if len(base) != 6 or any(response_for(db, row) is None for row in base):
        raise HTTPException(409, "All six base samples require responses")


@router.post("/extend")
def extend(user: Identity, db: Database) -> dict:
    rows = assignments(db, user)
    require_base_responses(db, rows)
    if not any(row.phase == "optional" for row in rows):
        if user.initial_test_completed_at is not None:
            raise HTTPException(409, "Initial test already completed")
        create_assignments(db, user, "optional")
    result = payload(db, user)
    db.commit()
    return result


@router.post("/complete")
def complete(user: Identity, db: Database) -> dict:
    rows = assignments(db, user)
    require_base_responses(db, rows)
    if any(response_for(db, row) is None for row in rows):
        raise HTTPException(409, "Every assigned sample requires a response")
    if user.initial_test_completed_at is None:
        user.initial_test_completed_at = datetime.now(timezone.utc)
    db.commit()
    return {"next_route": "/onboarding/voice"}
