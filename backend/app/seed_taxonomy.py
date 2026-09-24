"""Run with python -m app.seed_taxonomy after alembic upgrade head."""

import argparse
import sys
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_engine
from app.models import Trigger
from app.taxonomy import TAXONOMY_VERSION, TRIGGERS


class TaxonomyConflict(ValueError):
    """Existing canonical keys must not be silently redefined."""


def seed_taxonomy(connection: Connection) -> int:
    """Insert missing keys atomically; return the count without committing."""
    table = Trigger.__table__
    # A savepoint also makes this safe for callers that catch a conflict and continue.
    with connection.begin_nested():
        inserted = connection.execute(
            insert(table)
            .values([asdict(trigger) for trigger in TRIGGERS])
            .on_conflict_do_nothing(index_elements=[table.c.key])
            .returning(table.c.id)
        ).all()
        expected = {trigger.key: trigger for trigger in TRIGGERS}
        rows = connection.execute(
            select(table.c.key, table.c.family, table.c.is_core)
            .where(table.c.key.in_(expected))
            .with_for_update()
        ).all()
        for row in rows:
            trigger = expected[row.key]
            if (row.family, row.is_core) != (trigger.family, trigger.is_core):
                raise TaxonomyConflict(
                    f"Canonical key '{row.key}' conflicts with taxonomy "
                    f"{TAXONOMY_VERSION}; expected family={trigger.family}, "
                    f"is_core={trigger.is_core}. Resolve explicitly before seeding."
                )
        if len(rows) != len(TRIGGERS):
            raise TaxonomyConflict("Canonical keys changed during seeding; retry.")
    return len(inserted)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed canonical ASMR taxonomy v2.0.")
    parser.parse_args()
    try:
        engine = get_engine()
        with engine.begin() as connection:
            inserted = seed_taxonomy(connection)
    except TaxonomyConflict as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (SQLAlchemyError, ValueError):
        print(
            "Taxonomy seed failed. Check DATABASE_URL, PostgreSQL availability, "
            "and run 'python -m alembic upgrade head' first.",
            file=sys.stderr,
        )
        return 1
    print(
        f"Taxonomy {TAXONOMY_VERSION}: inserted {inserted}; "
        f"{len(TRIGGERS)} canonical keys present."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
