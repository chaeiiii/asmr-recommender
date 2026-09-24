"""Offline fixtures for keyword evidence and persistence ownership."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Trigger, Video, VideoTrigger
from app.services.tagging import TAGGER_VERSION, tag_metadata, tag_video
from app.taxonomy import TRIGGERS


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Mic scratching, page turning, keyboard, water sounds",
         {"scratching", "paper_crinkling", "typing_writing", "water_liquid"}),
        ("Fast Aggressive Mic Scratching No Talking",
         {"fast", "aggressive", "scratching", "no_talking"}),
        ("Korean Whisper Ear Cleaning Roleplay",
         {"whisper", "ear_cleaning", "roleplay"}),
        ("Hair brushing and camera brushing", {"camera_brushing"}),
        ("ＭＩＣ ＢＲＵＳＨＩＮＧ", {"mic_brushing"}),
        ("soft-spoken personal_attention", {"soft_spoken", "personal_attention"}),
        ("breakfast normally", set()),
        ("Relaxing ASMR", set()),
    ],
)
def test_fixture_labels(title, expected):
    assert set(tag_metadata(title)) == expected


@pytest.mark.parametrize(
    ("title", "description", "tags", "confidence"),
    [
        ("tapping", "tapping", ["tapping"], "0.95"),
        ("ASMR", "tapping", ["tapping"], "0.90"),
        ("ASMR", "tapping", [], "0.75"),
        ("finger taps", None, [], "0.60"),
    ],
)
def test_confidence(title, description, tags, confidence):
    assert tag_metadata(title, description, tags)["tapping"] == Decimal(confidence)


@pytest.mark.parametrize(
    "negation",
    ["no mouth sounds", "without mouth sounds", "mouth sounds free",
     "mouth sounds are excluded", "not mouth sounds"],
)
def test_negation_vetoes_other_sources(negation):
    assert "mouth_sounds" not in tag_metadata(
        negation, "mouth sounds", ["mouth sounds"]
    )


def test_negation_scope_and_tag_boundaries():
    assert set(tag_metadata("No mouth sounds or tapping; keyboard")) == {
        "typing_writing"
    }
    assert set(tag_metadata("No mouth sounds\nMic brushing")) == {"mic_brushing"}
    assert tag_metadata("ASMR", youtube_tags=["mic", "brushing"]) == {}


def test_keyword_rerun_and_manual_precedence():
    engine = create_engine("sqlite://")
    for table in (Trigger.__table__, Video.__table__, VideoTrigger.__table__):
        table.create(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        for index, definition in enumerate(TRIGGERS, start=1):
            session.add(Trigger(
                id=index, key=definition.key, display_name=definition.display_name,
                family=definition.family,
            ))
        video = Video(
            id=1, youtube_video_id="fixture", title="tapping scratching",
            channel_id="channel", channel_name="Fixture", last_synced_at=now,
            language="unknown",
        )
        session.add(video)
        session.flush()
        tapping_id = session.scalar(select(Trigger.id).where(Trigger.key == "tapping"))
        manual = VideoTrigger(
            video_id=1, trigger_id=tapping_id, confidence=Decimal("0.123"),
            source="manual", tagger_version="reviewed", created_at=now,
        )
        session.add(manual)
        session.flush()
        assert tag_video(session, video) == {"created": 1, "updated": 0, "deleted": 0}
        keyword = session.scalar(
            select(VideoTrigger).where(VideoTrigger.source == "keyword")
        )
        created_at = keyword.created_at
        assert keyword.tagger_version == TAGGER_VERSION
        assert tag_video(session, video) == {"created": 0, "updated": 0, "deleted": 0}
        assert keyword.created_at == created_at
        video.title = "ASMR"
        video.description = "scratching"
        assert tag_video(session, video)["updated"] == 1
        assert keyword.confidence == Decimal("0.75")
        video.description = "no scratching"
        assert tag_video(session, video)["deleted"] == 1
        assert list(session.scalars(select(VideoTrigger))) == [manual]
        assert manual.confidence == Decimal("0.123")
        assert manual.tagger_version == "reviewed"
        assert manual.created_at == now
        assert video.language == "unknown"
    engine.dispose()
