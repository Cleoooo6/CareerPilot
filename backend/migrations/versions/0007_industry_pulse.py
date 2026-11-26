"""industry pulse rss ingestion

Revision ID: 0007_industry_pulse
Revises: 0006_roadmap_concurrency
Create Date: 2026-11-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_industry_pulse"
down_revision: Union[str, None] = "0006_roadmap_concurrency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "industry_feed_source",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("industry", sa.String(length=20), nullable=False),
        sa.Column("feed_url", sa.String(length=1000), nullable=False),
        sa.Column("homepage_url", sa.String(length=1000), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("blocked_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("last_status", sa.String(length=20), nullable=False, server_default="never"),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "industry IN ('internet', 'finance', 'ai', 'energy')",
            name="ck_industry_feed_source_industry",
        ),
        sa.CheckConstraint(
            "last_status IN ('never', 'ok', 'failed', 'blocked')",
            name="ck_industry_feed_source_last_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_industry_feed_source_key"),
    )
    op.create_index(
        "ix_industry_feed_source_industry_enabled",
        "industry_feed_source",
        ["industry", "enabled"],
    )

    op.create_table(
        "industry_pulse_article",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("industry", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=1500), nullable=False),
        sa.Column("canonical_url", sa.String(length=1500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("ai_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("career_impact", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "analysis_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("analysis_error", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "analysis_details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("analysis_model", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "industry IN ('internet', 'finance', 'ai', 'energy')",
            name="ck_industry_pulse_article_industry",
        ),
        sa.CheckConstraint(
            "analysis_status IN ('pending', 'analyzed', 'failed', 'disabled')",
            name="ck_industry_pulse_article_analysis_status",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["industry_feed_source.id"],
            name="fk_industry_pulse_article_source",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "canonical_url", name="uq_industry_pulse_article_canonical_url"
        ),
    )
    op.create_index(
        "ix_industry_pulse_article_industry_published",
        "industry_pulse_article",
        ["industry", "published_at"],
    )
    op.create_index(
        "ix_industry_pulse_article_analysis_status",
        "industry_pulse_article",
        ["analysis_status"],
    )
    op.create_index(
        "ix_industry_pulse_article_source",
        "industry_pulse_article",
        ["source_id"],
    )

    op.create_table(
        "industry_pulse_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sources_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sources_ok", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sources_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("articles_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("articles_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("articles_duplicates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'partial', 'failed')",
            name="ck_industry_pulse_run_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_industry_pulse_run_started_at",
        "industry_pulse_run",
        ["started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_industry_pulse_run_started_at", table_name="industry_pulse_run")
    op.drop_table("industry_pulse_run")
    op.drop_index(
        "ix_industry_pulse_article_source", table_name="industry_pulse_article"
    )
    op.drop_index(
        "ix_industry_pulse_article_analysis_status",
        table_name="industry_pulse_article",
    )
    op.drop_index(
        "ix_industry_pulse_article_industry_published",
        table_name="industry_pulse_article",
    )
    op.drop_table("industry_pulse_article")
    op.drop_index(
        "ix_industry_feed_source_industry_enabled",
        table_name="industry_feed_source",
    )
    op.drop_table("industry_feed_source")