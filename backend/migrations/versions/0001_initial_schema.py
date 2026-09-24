"""Create final MVP schema.

Revision ID: 0001
Revises: None
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "triggers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("family", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_core", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.CheckConstraint(
            "family IN ('sound', 'voice', 'visual', 'format', 'speed', 'intensity')",
            name=op.f("ck_triggers_family"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_triggers")),
        sa.UniqueConstraint("key", name=op.f("uq_triggers_key")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "initial_test_completed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("voice_mode", sa.String(length=16), nullable=True),
        sa.Column(
            "language_no_preference",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "onboarding_completed",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("taxonomy_version", sa.String(length=20), nullable=False),
        sa.CheckConstraint(
            "voice_mode IN ('talking', 'no_talking', 'both')",
            name=op.f("ck_users_voice_mode"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_table(
        "videos",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("youtube_video_id", sa.String(length=20), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("channel_id", sa.String(length=64), nullable=False),
        sa.Column("channel_name", sa.Text(), nullable=False),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "embeddable", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column(
            "availability_status",
            sa.String(length=32),
            server_default="active",
            nullable=False,
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_videos")),
        sa.UniqueConstraint(
            "youtube_video_id", name=op.f("uq_videos_youtube_video_id")
        ),
    )
    op.create_index(
        "ix_videos_availability_status_embeddable",
        "videos",
        ["availability_status", "embeddable"],
        unique=False,
    )
    op.create_index("ix_videos_channel_id", "videos", ["channel_id"], unique=False)
    op.create_index("ix_videos_language", "videos", ["language"], unique=False)
    op.create_table(
        "favorites",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_favorites_user_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["video_id"], ["videos.id"], name=op.f("fk_favorites_video_id_videos")
        ),
        sa.PrimaryKeyConstraint("user_id", "video_id", name=op.f("pk_favorites")),
    )
    op.create_index(
        "ix_favorites_user_id_created_at",
        "favorites",
        ["user_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_table(
        "interactions",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("watch_duration_sec", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "type IN ('play', 'like', 'dislike', 'skip')",
            name=op.f("ck_interactions_type"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_interactions_user_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["video_id"], ["videos.id"], name=op.f("fk_interactions_video_id_videos")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interactions")),
    )
    op.create_index(
        "ix_interactions_user_id_created_at",
        "interactions",
        ["user_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_interactions_user_id_video_id_type",
        "interactions",
        ["user_id", "video_id", "type"],
        unique=False,
    )
    op.create_table(
        "preference_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("trigger_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("observation", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("reference_type", sa.String(length=24), nullable=True),
        sa.Column("reference_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source IN ('test', 'self_report', 'video_like', 'video_dislike', "
            "'discover_like', 'discover_dislike')",
            name=op.f("ck_preference_events_source"),
        ),
        sa.ForeignKeyConstraint(
            ["trigger_id"],
            ["triggers.id"],
            name=op.f("fk_preference_events_trigger_id_triggers"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_preference_events_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_preference_events")),
    )
    op.create_table(
        "recommendation_impressions",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("surface", sa.String(length=16), nullable=False),
        sa.Column("algorithm_version", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Numeric(precision=8, scale=6), nullable=True),
        sa.Column("reason_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "surface IN ('home', 'discover')",
            name=op.f("ck_recommendation_impressions_surface"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_recommendation_impressions_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["videos.id"],
            name=op.f("fk_recommendation_impressions_video_id_videos"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendation_impressions")),
    )
    op.create_index(
        "ix_recommendation_impressions_user_id_created_at",
        "recommendation_impressions",
        ["user_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_table(
        "trigger_samples",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("primary_trigger_id", sa.Integer(), nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("start_sec", sa.Integer(), nullable=False),
        sa.Column("end_sec", sa.Integer(), nullable=False),
        sa.Column(
            "verified", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "end_sec - start_sec <= 30", name=op.f("ck_trigger_samples_duration_max_30")
        ),
        sa.CheckConstraint(
            "end_sec > start_sec", name=op.f("ck_trigger_samples_end_after_start")
        ),
        sa.CheckConstraint(
            "start_sec >= 0", name=op.f("ck_trigger_samples_start_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["primary_trigger_id"],
            ["triggers.id"],
            name=op.f("fk_trigger_samples_primary_trigger_id_triggers"),
        ),
        sa.ForeignKeyConstraint(
            ["video_id"], ["videos.id"], name=op.f("fk_trigger_samples_video_id_videos")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trigger_samples")),
    )
    op.create_table(
        "user_language_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_language_preferences_user_id_users"),
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "language", name=op.f("pk_user_language_preferences")
        ),
    )
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("trigger_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("evidence_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_evidence_source", sa.String(length=32), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "score >= -1 AND score <= 1", name=op.f("ck_user_preferences_score_range")
        ),
        sa.ForeignKeyConstraint(
            ["trigger_id"],
            ["triggers.id"],
            name=op.f("fk_user_preferences_trigger_id_triggers"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_preferences_user_id_users")
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "trigger_id", name=op.f("pk_user_preferences")
        ),
    )
    op.create_index(
        "ix_user_preferences_user_id_score",
        "user_preferences",
        ["user_id", "score"],
        unique=False,
    )
    op.create_table(
        "video_triggers",
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("trigger_id", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("tagger_version", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["trigger_id"],
            ["triggers.id"],
            name=op.f("fk_video_triggers_trigger_id_triggers"),
        ),
        sa.ForeignKeyConstraint(
            ["video_id"], ["videos.id"], name=op.f("fk_video_triggers_video_id_videos")
        ),
        sa.PrimaryKeyConstraint(
            "video_id", "trigger_id", name=op.f("pk_video_triggers")
        ),
    )
    op.create_index(
        "ix_video_triggers_trigger_id_confidence",
        "video_triggers",
        ["trigger_id", "confidence"],
        unique=False,
    )
    op.create_table(
        "initial_test_assignments",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("sample_id", sa.Integer(), nullable=False),
        sa.Column("phase", sa.String(length=16), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("test_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "phase IN ('base', 'optional')",
            name=op.f("ck_initial_test_assignments_phase"),
        ),
        sa.ForeignKeyConstraint(
            ["sample_id"],
            ["trigger_samples.id"],
            name=op.f("fk_initial_test_assignments_sample_id_trigger_samples"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_initial_test_assignments_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_initial_test_assignments")),
        sa.UniqueConstraint("user_id", "position", name="uq_assignments_user_position"),
        sa.UniqueConstraint("user_id", "sample_id", name="uq_assignments_user_sample"),
    )
    op.create_table(
        "test_responses",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("assignment_id", sa.BigInteger(), nullable=False),
        sa.Column("response", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "response IN ('like', 'neutral', 'dislike', 'skip')",
            name=op.f("ck_test_responses_response"),
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["initial_test_assignments.id"],
            name=op.f("fk_test_responses_assignment_id_initial_test_assignments"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test_responses")),
        sa.UniqueConstraint(
            "assignment_id", name=op.f("uq_test_responses_assignment_id")
        ),
    )


def downgrade() -> None:
    op.drop_table("test_responses")
    op.drop_table("initial_test_assignments")
    op.drop_index(
        "ix_video_triggers_trigger_id_confidence", table_name="video_triggers"
    )
    op.drop_table("video_triggers")
    op.drop_index("ix_user_preferences_user_id_score", table_name="user_preferences")
    op.drop_table("user_preferences")
    op.drop_table("user_language_preferences")
    op.drop_table("trigger_samples")
    op.drop_index(
        "ix_recommendation_impressions_user_id_created_at",
        table_name="recommendation_impressions",
    )
    op.drop_table("recommendation_impressions")
    op.drop_table("preference_events")
    op.drop_index("ix_interactions_user_id_video_id_type", table_name="interactions")
    op.drop_index("ix_interactions_user_id_created_at", table_name="interactions")
    op.drop_table("interactions")
    op.drop_index("ix_favorites_user_id_created_at", table_name="favorites")
    op.drop_table("favorites")
    op.drop_index("ix_videos_language", table_name="videos")
    op.drop_index("ix_videos_channel_id", table_name="videos")
    op.drop_index("ix_videos_availability_status_embeddable", table_name="videos")
    op.drop_table("videos")
    op.drop_table("users")
    op.drop_table("triggers")
