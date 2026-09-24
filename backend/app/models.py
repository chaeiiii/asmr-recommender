"""Final MVP schema from DATABASE.md. No seed data or product behavior."""

from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Uuid, primary_key=True, default=uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False)
    initial_test_completed_at = Column(DateTime(timezone=True))
    voice_mode = Column(String(16))
    language_no_preference = Column(Boolean, nullable=False, server_default=false())
    onboarding_completed = Column(Boolean, nullable=False, server_default=false())
    taxonomy_version = Column(String(20), nullable=False)
    __table_args__ = (
        CheckConstraint(
            "voice_mode IN ('talking', 'no_talking', 'both')", name="voice_mode"
        ),
    )


class Trigger(Base):
    __tablename__ = "triggers"
    id = Column(Integer, primary_key=True)
    key = Column(String(64), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)
    family = Column(String(32), nullable=False)
    description = Column(Text)
    is_core = Column(Boolean, nullable=False, server_default=false())
    active = Column(Boolean, nullable=False, server_default=true())
    __table_args__ = (
        CheckConstraint(
            "family IN ('sound', 'voice', 'visual', 'format', 'speed', 'intensity')",
            name="family",
        ),
    )


class Video(Base):
    __tablename__ = "videos"
    id = Column(BigInteger, primary_key=True)
    youtube_video_id = Column(String(20), nullable=False, unique=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    channel_id = Column(String(64), nullable=False)
    channel_name = Column(Text, nullable=False)
    thumbnail_url = Column(Text)
    duration_sec = Column(Integer)
    language = Column(String(16))
    published_at = Column(DateTime(timezone=True))
    embeddable = Column(Boolean, nullable=False, server_default=true())
    availability_status = Column(String(32), nullable=False, server_default="active")
    last_synced_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    __table_args__ = (
        Index(
            "ix_videos_availability_status_embeddable",
            "availability_status",
            "embeddable",
        ),
        Index("ix_videos_language", "language"),
        Index("ix_videos_channel_id", "channel_id"),
    )


class VideoTrigger(Base):
    __tablename__ = "video_triggers"
    video_id = Column(BigInteger, ForeignKey("videos.id"), primary_key=True)
    trigger_id = Column(Integer, ForeignKey("triggers.id"), primary_key=True)
    confidence = Column(Numeric(4, 3), nullable=False)
    source = Column(String(20), nullable=False)
    tagger_version = Column(String(30), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        Index("ix_video_triggers_trigger_id_confidence", "trigger_id", "confidence"),
    )


class TriggerSample(Base):
    __tablename__ = "trigger_samples"
    id = Column(Integer, primary_key=True)
    primary_trigger_id = Column(Integer, ForeignKey("triggers.id"), nullable=False)
    video_id = Column(BigInteger, ForeignKey("videos.id"), nullable=False)
    start_sec = Column(Integer, nullable=False)
    end_sec = Column(Integer, nullable=False)
    verified = Column(Boolean, nullable=False, server_default=false())
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        CheckConstraint("start_sec >= 0", name="start_nonnegative"),
        CheckConstraint("end_sec > start_sec", name="end_after_start"),
        CheckConstraint("end_sec - start_sec <= 30", name="duration_max_30"),
    )


class InitialTestAssignment(Base):
    __tablename__ = "initial_test_assignments"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    sample_id = Column(Integer, ForeignKey("trigger_samples.id"), nullable=False)
    phase = Column(String(16), nullable=False)
    position = Column(SmallInteger, nullable=False)
    test_version = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("user_id", "sample_id", name="uq_assignments_user_sample"),
        UniqueConstraint("user_id", "position", name="uq_assignments_user_position"),
        CheckConstraint("phase IN ('base', 'optional')", name="phase"),
    )


class TestResponse(Base):
    __tablename__ = "test_responses"
    id = Column(BigInteger, primary_key=True)
    assignment_id = Column(
        BigInteger,
        ForeignKey("initial_test_assignments.id"),
        nullable=False,
        unique=True,
    )
    response = Column(String(16), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        CheckConstraint(
            "response IN ('like', 'neutral', 'dislike', 'skip')", name="response"
        ),
    )


class UserLanguagePreference(Base):
    __tablename__ = "user_language_preferences"
    user_id = Column(Uuid, ForeignKey("users.id"), primary_key=True)
    language = Column(String(16), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False)


class UserPreference(Base):
    __tablename__ = "user_preferences"
    user_id = Column(Uuid, ForeignKey("users.id"), primary_key=True)
    trigger_id = Column(Integer, ForeignKey("triggers.id"), primary_key=True)
    score = Column(Numeric(5, 4), nullable=False)
    evidence_count = Column(Integer, nullable=False, server_default="0")
    last_evidence_source = Column(String(32))
    updated_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        CheckConstraint("score >= -1 AND score <= 1", name="score_range"),
        Index("ix_user_preferences_user_id_score", "user_id", "score"),
    )


class PreferenceEvent(Base):
    __tablename__ = "preference_events"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    trigger_id = Column(Integer, ForeignKey("triggers.id"), nullable=False)
    source = Column(String(32), nullable=False)
    observation = Column(Numeric(4, 3), nullable=False)
    reference_type = Column(String(24))
    reference_id = Column(String(64))
    created_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        CheckConstraint(
            "source IN ('test', 'self_report', 'video_like', 'video_dislike', "
            "'discover_like', 'discover_dislike')",
            name="source",
        ),
    )


class Interaction(Base):
    __tablename__ = "interactions"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    video_id = Column(BigInteger, ForeignKey("videos.id"), nullable=False)
    type = Column(String(16), nullable=False)
    watch_duration_sec = Column(Integer)
    created_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        CheckConstraint("type IN ('play', 'like', 'dislike', 'skip')", name="type"),
        Index("ix_interactions_user_id_created_at", user_id, created_at.desc()),
        Index("ix_interactions_user_id_video_id_type", "user_id", "video_id", "type"),
    )


class Favorite(Base):
    __tablename__ = "favorites"
    user_id = Column(Uuid, ForeignKey("users.id"), primary_key=True)
    video_id = Column(BigInteger, ForeignKey("videos.id"), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        Index("ix_favorites_user_id_created_at", user_id, created_at.desc()),
    )


class RecommendationImpression(Base):
    __tablename__ = "recommendation_impressions"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    video_id = Column(BigInteger, ForeignKey("videos.id"), nullable=False)
    surface = Column(String(16), nullable=False)
    algorithm_version = Column(String(32), nullable=False)
    score = Column(Numeric(8, 6))
    reason_json = Column(JSONB)
    created_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        CheckConstraint("surface IN ('home', 'discover')", name="surface"),
        Index(
            "ix_recommendation_impressions_user_id_created_at",
            user_id,
            created_at.desc(),
        ),
    )
