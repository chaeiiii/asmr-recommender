"""Run from backend: python -m app.scripts.import_trigger_samples reviewed.csv."""

import argparse
from dataclasses import asdict
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import get_engine
from app.services.trigger_sample_import import (
    SampleValidationError,
    import_trigger_samples,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    args = parser.parse_args()
    try:
        with args.csv_path.open(encoding="utf-8-sig", newline="") as source:
            with Session(get_engine()) as session:
                result = import_trigger_samples(session, source)
    except (SampleValidationError, OSError, UnicodeError) as exc:
        parser.exit(2, f"Import failed: {exc}\n")
    print(asdict(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
