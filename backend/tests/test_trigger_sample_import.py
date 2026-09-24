from datetime import datetime, timezone
from io import StringIO

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Trigger, TriggerSample, Video
from app.services.trigger_sample_import import (
    SampleValidationError,
    import_trigger_samples,
)

HEADER = "trigger_key,youtube_video_id,start_sec,end_sec,notes\n"


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    for table in (Trigger.__table__, Video.__table__, TriggerSample.__table__):
        table.create(engine)
    with Session(engine) as session:
        session.add(
            Trigger(
                id=1,
                key="tapping",
                display_name="Tapping",
                family="sound",
                is_core=True,
            )
        )
        session.add(
            Video(
                id=1,
                youtube_video_id="existing",
                title="ASMR",
                channel_id="channel",
                channel_name="Channel",
                last_synced_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
        yield session
    engine.dispose()


def test_verified_idempotent_import_and_notes_update(session):
    data = HEADER + "tapping,existing,0,10,reviewed\n" * 2
    assert import_trigger_samples(session, StringIO(data)).inserted == 1
    sample = session.scalar(select(TriggerSample))
    original_id = sample.id
    sample.verified = False
    session.commit()
    result = import_trigger_samples(
        session, StringIO(HEADER + "tapping,existing,0,10,revised notes\n")
    )
    assert result.inserted == 0
    samples = list(session.scalars(select(TriggerSample)))
    assert len(samples) == 1
    assert samples[0].id == original_id
    assert samples[0].verified and samples[0].notes == "revised notes"


@pytest.mark.parametrize("duration", [1, 5, 15, 16, 30])
def test_target_duration_is_not_a_hard_constraint(session, duration):
    result = import_trigger_samples(
        session, StringIO(HEADER + f"tapping,existing,0,{duration},reviewed\n")
    )
    assert result.inserted == 1


@pytest.mark.parametrize(
    "row,error",
    [
        ("whisper,existing,0,10,n", "canonical core Sound"),
        ("brushing,existing,0,10,n", "canonical core Sound"),
        ("tapping,missing,0,10,n", "video does not exist"),
        ("tapping,existing,-1,10,n", "start_sec"),
        ("tapping,existing,1.5,10,n", "start_sec"),
        ("tapping,existing,10,10,n", "end_sec > start_sec"),
        ("tapping,existing,11,10,n", "end_sec > start_sec"),
        ("tapping,existing,0,31,n", "duration <= 30"),
        ("tapping,existing,0,10", "five columns"),
        ("tapping,existing,0,10,n,extra", "five columns"),
        ("scratching,existing,0,10,n", "not seeded"),
    ],
)
def test_invalid_row_reports_line_and_rolls_back_entire_file(session, row, error):
    with pytest.raises(SampleValidationError, match="CSV line 3: .*" + error):
        import_trigger_samples(
            session, StringIO(HEADER + "tapping,existing,0,10,valid\n" + row + "\n")
        )
    assert list(session.scalars(select(TriggerSample))) == []


def test_invalid_header(session):
    with pytest.raises(SampleValidationError, match="CSV header"):
        import_trigger_samples(session, StringIO("wrong,columns\n"))
