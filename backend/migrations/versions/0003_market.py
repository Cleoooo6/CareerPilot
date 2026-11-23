"""stage-four market radar tables

Revision ID: 0003_market
Revises: 0002_profile
Create Date: 2026-11-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_market"
down_revision: Union[str, None] = "0002_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_source",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("dataset_kind", sa.String(length=16), nullable=False),
        sa.Column("license_note", sa.Text(), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=True),
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
            "dataset_kind IN ('real', 'synthetic')",
            name="ck_market_source_kind",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_market_source_name"),
    )

    op.create_table(
        "market_import_batch",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('processing', 'completed', 'failed')",
            name="ck_market_batch_status",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["market_source.id"],
            name="fk_market_batch_source",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_market_batch_source_started",
        "market_import_batch",
        ["source_id", "started_at"],
    )

    op.create_table(
        "market_job",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=True),
        sa.Column("external_id", sa.String(length=200), nullable=True),
        sa.Column("dedupe_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duplicate_of", sa.Uuid(), nullable=True),
        sa.Column("title_raw", sa.String(length=300), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=False),
        sa.Column("industry", sa.String(length=100), nullable=False),
        sa.Column("location", sa.String(length=100), nullable=False),
        sa.Column("education", sa.String(length=50), nullable=False),
        sa.Column("experience", sa.String(length=50), nullable=False),
        sa.Column("salary", sa.String(length=100), nullable=True),
        sa.Column(
            "skills",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('processed', 'duplicate', 'failed')",
            name="ck_market_job_status",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["market_source.id"],
            name="fk_market_job_source",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["market_import_batch.id"],
            name="fk_market_job_batch",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_of"],
            ["market_job.id"],
            name="fk_market_job_duplicate",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_job_source_fetched", "market_job", ["source_id", "fetched_at"])
    op.create_index("ix_market_job_title", "market_job", ["title"])
    op.create_index("ix_market_job_location", "market_job", ["location"])
    op.create_index("ix_market_job_education", "market_job", ["education"])
    op.create_index("ix_market_job_experience", "market_job", ["experience"])
    op.create_index("ix_market_job_dedupe", "market_job", ["dedupe_hash"])
    op.create_index(
        "ix_market_job_skills",
        "market_job",
        ["skills"],
        postgresql_using="gin",
        postgresql_ops={"skills": "jsonb_path_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_market_job_skills", table_name="market_job")
    op.drop_index("ix_market_job_dedupe", table_name="market_job")
    op.drop_index("ix_market_job_experience", table_name="market_job")
    op.drop_index("ix_market_job_education", table_name="market_job")
    op.drop_index("ix_market_job_location", table_name="market_job")
    op.drop_index("ix_market_job_title", table_name="market_job")
    op.drop_index("ix_market_job_source_fetched", table_name="market_job")
    op.drop_table("market_job")
    op.drop_index("ix_market_batch_source_started", table_name="market_import_batch")
    op.drop_table("market_import_batch")
    op.drop_table("market_source")
