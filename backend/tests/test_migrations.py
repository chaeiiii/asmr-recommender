"""Real PostgreSQL validation, isolated in a unique schema (never public)."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models as m
from app.database import Base


@pytest.fixture
def records(db):
    now = datetime.now(timezone.utc)
    user_id = uuid4()
    db.execute(
        sa.insert(m.User).values(id=user_id, created_at=now, taxonomy_version="test")
    )
    trigger_id = db.scalar(
        sa.insert(m.Trigger)
        .values(key="fixture_only", display_name="Fixture", family="sound")
        .returning(m.Trigger.id)
    )
    video_id = db.scalar(
        sa.insert(m.Video)
        .values(
            youtube_video_id="fixture_only",
            title="Fixture",
            channel_id="fixture",
            channel_name="Fixture",
            last_synced_at=now,
        )
        .returning(m.Video.id)
    )
    sample_id = db.scalar(
        sa.insert(m.TriggerSample)
        .values(
            primary_trigger_id=trigger_id,
            video_id=video_id,
            start_sec=0,
            end_sec=10,
            created_at=now,
        )
        .returning(m.TriggerSample.id)
    )
    assignment_id = db.scalar(
        sa.insert(m.InitialTestAssignment)
        .values(
            user_id=user_id,
            sample_id=sample_id,
            phase="base",
            position=1,
            test_version="fixture",
            created_at=now,
        )
        .returning(m.InitialTestAssignment.id)
    )
    return dict(
        user_id=user_id,
        trigger_id=trigger_id,
        video_id=video_id,
        sample_id=sample_id,
        assignment_id=assignment_id,
        now=now,
    )


def test_schema_matches_models_and_has_all_indexes(db):
    inspector = sa.inspect(db)
    assert set(inspector.get_table_names()) == set(Base.metadata.tables) | {
        "alembic_version"
    }
    context = MigrationContext.configure(db, opts={"compare_server_default": True})
    assert compare_metadata(context, Base.metadata) == []
    indexes = [
        index
        for table in Base.metadata.tables
        for index in inspector.get_indexes(table)
        if not index.get("duplicates_constraint")
    ]
    assert len(indexes) == 9
    for table in Base.metadata.sorted_tables:
        assert len(inspector.get_foreign_keys(table.name)) == len(
            table.foreign_key_constraints
        )
        assert len(inspector.get_check_constraints(table.name)) == len(
            [c for c in table.constraints if isinstance(c, sa.CheckConstraint)]
        )


def test_defaults_and_postgresql_types_round_trip(db, records):
    with Session(db, join_transaction_mode="create_savepoint") as session:
        user = session.get(m.User, records["user_id"])
        assert user.voice_mode is None
        assert user.onboarding_completed is False
        assert user.language_no_preference is False
        assert user.created_at.utcoffset() is not None
        video = session.get(m.Video, records["video_id"])
        assert video.embeddable and video.availability_status == "active"
        assert video.created_at is not None
        trigger = session.get(m.Trigger, records["trigger_id"])
        assert trigger.active and not trigger.is_core
        assert not session.get(m.TriggerSample, records["sample_id"]).verified
        pref = m.UserPreference(
            user_id=user.id,
            trigger_id=trigger.id,
            score=Decimal("-1"),
            updated_at=records["now"],
        )
        impression = m.RecommendationImpression(
            user_id=user.id,
            video_id=video.id,
            surface="home",
            algorithm_version="fixture",
            reason_json={"reasons": ["fixture"]},
            score=Decimal("0.123456"),
            created_at=records["now"],
        )
        session.add_all([pref, impression])
        session.flush()
        session.refresh(impression)
        assert pref.evidence_count == 0
        assert impression.reason_json == {"reasons": ["fixture"]}
        assert impression.score == Decimal("0.123456")


@pytest.mark.parametrize(
    "model,field,value",
    [
        (m.Trigger, "family", "unknown"),
        (m.InitialTestAssignment, "phase", "unknown"),
    ],
)
def test_declared_value_sets_rejected(db, records, model, field, value):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(sa.update(model).values({field: value}))


@pytest.mark.parametrize("start,end", [(-1, 10), (10, 10), (10, 9), (0, 31)])
def test_invalid_sample_ranges_rejected(db, records, start, end):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            sa.insert(m.TriggerSample).values(
                primary_trigger_id=records["trigger_id"],
                video_id=records["video_id"],
                start_sec=start,
                end_sec=end,
                created_at=records["now"],
            )
        )


@pytest.mark.parametrize("score", ["-1.0001", "1.0001"])
def test_invalid_scores_rejected(db, records, score):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            sa.insert(m.UserPreference).values(
                user_id=records["user_id"],
                trigger_id=records["trigger_id"],
                score=Decimal(score),
                updated_at=records["now"],
            )
        )


@pytest.mark.parametrize(
    "field,value", [("voice_mode", "invalid"), ("taxonomy_version", None)]
)
def test_invalid_user_values_rejected(db, records, field, value):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            sa.update(m.User)
            .where(m.User.id == records["user_id"])
            .values({field: value})
        )


def test_foreign_keys_and_uniqueness(db, records):
    now = records["now"]
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            sa.insert(m.Favorite).values(
                user_id=uuid4(),
                video_id=records["video_id"],
                created_at=now,
            )
        )
    favorite = dict(
        user_id=records["user_id"], video_id=records["video_id"], created_at=now
    )
    db.execute(sa.insert(m.Favorite).values(**favorite))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(sa.insert(m.Favorite).values(**favorite))
    response = dict(
        assignment_id=records["assignment_id"],
        response="skip",
        created_at=now,
        updated_at=now,
    )
    db.execute(sa.insert(m.TestResponse).values(**response))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(sa.insert(m.TestResponse).values(**response))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            sa.insert(m.InitialTestAssignment).values(
                user_id=records["user_id"],
                sample_id=records["sample_id"],
                phase="optional",
                position=2,
                test_version="fixture",
                created_at=now,
            )
        )
    other_sample = db.scalar(
        sa.insert(m.TriggerSample)
        .values(
            primary_trigger_id=records["trigger_id"],
            video_id=records["video_id"],
            start_sec=0,
            end_sec=30,
            created_at=now,
        )
        .returning(m.TriggerSample.id)
    )
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            sa.insert(m.InitialTestAssignment).values(
                user_id=records["user_id"],
                sample_id=other_sample,
                phase="optional",
                position=1,
                test_version="fixture",
                created_at=now,
            )
        )


def test_downgrade_and_reupgrade(migrated):
    connection, config = migrated
    command.downgrade(config, "base")
    assert sa.inspect(connection).get_table_names() == ["alembic_version"]
    command.upgrade(config, "head")
    command.upgrade(config, "head")  # Already-current migration is a no-op.
    assert set(sa.inspect(connection).get_table_names()) == set(
        Base.metadata.tables
    ) | {"alembic_version"}
