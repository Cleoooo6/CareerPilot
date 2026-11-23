"""stage-three career profile, resume parse, and analysis tables

Revision ID: 0002_profile
Revises: 0001_initial
Create Date: 2026-11-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_profile"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "career_profile",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], name="fk_career_profile_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_career_profile_user"),
    )
    op.create_index("ix_career_profile_user", "career_profile", ["user_id"])

    op.create_table(
        "resume_parse",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=80), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("parse_mode", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column(
            "parsed_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("text_length", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_type", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
            "status IN ('processing', 'pending_review', 'confirmed', 'discarded', 'failed')",
            name="ck_resume_parse_status",
        ),
        sa.CheckConstraint(
            "parse_mode IN ('mock', 'real')",
            name="ck_resume_parse_mode",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], name="fk_resume_parse_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_resume_parse_user_created", "resume_parse", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_resume_parse_user_status", "resume_parse", ["user_id", "status"]
    )

    op.create_table(
        "profile_analysis",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("llm_mode", sa.String(length=16), nullable=False),
        sa.Column(
            "analysis",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "llm_mode IN ('mock', 'real')", name="ck_profile_analysis_mode"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], name="fk_profile_analysis_user", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["career_profile.id"],
            name="fk_profile_analysis_profile",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_profile_analysis_user_created",
        "profile_analysis",
        ["user_id", "created_at"],
    )
    op.create_index("ix_profile_analysis_profile", "profile_analysis", ["profile_id"])


def downgrade() -> None:
    op.drop_index("ix_profile_analysis_profile", table_name="profile_analysis")
    op.drop_index("ix_profile_analysis_user_created", table_name="profile_analysis")
    op.drop_table("profile_analysis")
    op.drop_index("ix_resume_parse_user_status", table_name="resume_parse")
    op.drop_index("ix_resume_parse_user_created", table_name="resume_parse")
    op.drop_table("resume_parse")
    op.drop_index("ix_career_profile_user", table_name="career_profile")
    op.drop_table("career_profile")
