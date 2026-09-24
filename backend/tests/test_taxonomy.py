import re
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa

from app.models import Trigger, User, UserPreference
from app.seed_taxonomy import TaxonomyConflict, seed_taxonomy
from app.taxonomy import TAXONOMY_VERSION, TRIGGERS


def test_canonical_data_matches_spec():
    spec = (Path(__file__).resolve().parents[2] / "TRIGGER_TAXONOMY.md").read_text(
        encoding="utf-8"
    )
    expected = {}
    for number, family in enumerate(
        ("sound", "voice", "visual", "format", "speed", "intensity"), start=3
    ):
        section = spec.split(f"## {number}. ")[1].split("\n## ")[0]
        if number <= 6:
            for key, display in re.findall(
                r"^\| `([^`]+)` \| ([^|]+) \|", section, re.M
            ):
                expected[key] = (family, display.strip())
        else:
            for key in re.findall(r"^- `([^`]+)`$", section, re.M):
                expected[key] = (family, key.replace("_", " ").title())
    assert TAXONOMY_VERSION == "2.0"
    assert len(TRIGGERS) == len(expected) == 27
    assert {t.key: (t.family, t.display_name) for t in TRIGGERS} == expected
    assert Counter(t.family for t in TRIGGERS) == {
        "sound": 10,
        "voice": 3,
        "visual": 4,
        "format": 4,
        "speed": 3,
        "intensity": 3,
    }
    assert all(t.is_core == (t.family == "sound") and t.active for t in TRIGGERS)


def test_seed_inserts_exact_canonical_rows_and_is_repeatable(db):
    assert seed_taxonomy(db) == 27
    rows = (
        db.execute(sa.select(Trigger.__table__).order_by(Trigger.key)).mappings().all()
    )
    assert [{k: v for k, v in row.items() if k != "id"} for row in rows] == [
        asdict(t) for t in sorted(TRIGGERS, key=lambda t: t.key)
    ]
    assert seed_taxonomy(db) == 0
    assert seed_taxonomy(db) == 0
    assert (
        db.execute(sa.select(Trigger.__table__).order_by(Trigger.key)).mappings().all()
        == rows
    )


def test_partial_seed_preserves_ids_references_and_existing_metadata(db):
    trigger_id = db.scalar(
        sa.insert(Trigger)
        .values(
            key="tapping",
            display_name="Custom label",
            family="sound",
            is_core=True,
            active=False,
            description="Reviewed description",
        )
        .returning(Trigger.id)
    )
    extra_id = db.scalar(
        sa.insert(Trigger)
        .values(key="fixture_extra", display_name="Fixture", family="sound")
        .returning(Trigger.id)
    )
    now = datetime.now(timezone.utc)
    user_id = uuid4()
    db.execute(
        sa.insert(User).values(id=user_id, created_at=now, taxonomy_version="2.0")
    )
    db.execute(
        sa.insert(UserPreference).values(
            user_id=user_id, trigger_id=trigger_id, score=0.5, updated_at=now
        )
    )
    before = db.execute(
        sa.select(Trigger.__table__).where(Trigger.id == trigger_id)
    ).one()
    assert seed_taxonomy(db) == 26
    assert seed_taxonomy(db) == 0
    assert (
        db.execute(sa.select(Trigger.__table__).where(Trigger.id == trigger_id)).one()
        == before
    )
    assert db.scalar(sa.select(UserPreference.trigger_id)) == trigger_id
    assert (
        db.scalar(sa.select(Trigger.id).where(Trigger.key == "fixture_extra"))
        == extra_id
    )
    assert db.scalar(sa.select(sa.func.count()).select_from(Trigger)) == 28


@pytest.mark.parametrize("family,is_core", [("visual", True), ("sound", False)])
def test_semantic_conflict_rolls_back_all_new_rows(db, family, is_core):
    db.execute(
        sa.insert(Trigger).values(
            key="tapping", display_name="Existing", family=family, is_core=is_core
        )
    )
    with pytest.raises(TaxonomyConflict, match="tapping"):
        seed_taxonomy(db)
    # Even if the caller catches the exception, no partial taxonomy remains.
    assert db.scalar(sa.select(sa.func.count()).select_from(Trigger)) == 1
    assert db.execute(sa.select(Trigger.family, Trigger.is_core)).one() == (
        family,
        is_core,
    )
