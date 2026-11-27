"""AI infrastructure: unified call audit and result version linkage.

Revision ID: 0012_ai_infrastructure
Revises: 0011_auth_accounts
Create Date: 2026-11-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_ai_infrastructure"
down_revision: Union[str, None] = "0011_auth_accounts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_call_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("llm_mode", sa.String(length=16), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "llm_mode IN ('mock', 'real')", name="ck_ai_call_log_mode"
        ),
        sa.CheckConstraint(
            "status IN ('succeeded', 'failed', 'cached')",
            name="ck_ai_call_log_status",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name="fk_ai_call_log_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_call_log_user_created",
        "ai_call_log",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_ai_call_log_source",
        "ai_call_log",
        ["source_type", "source_id"],
    )

    op.add_column(
        "profile_analysis",
        sa.Column(
            "prompt_version",
            sa.String(length=64),
            nullable=False,
            server_default="profile_analysis@v1",
        ),
    )
    op.add_column(
        "profile_analysis",
        sa.Column("source_revision_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "profile_analysis", sa.Column("resume_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "profile_analysis", sa.Column("duration_ms", sa.Integer(), nullable=True)
    )
    op.add_column(
        "profile_analysis", sa.Column("total_tokens", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_profile_analysis_resume",
        "profile_analysis",
        "resume_parse",
        ["resume_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_profile_analysis_resume", "profile_analysis", ["resume_id"]
    )

    op.add_column(
        "resume_parse",
        sa.Column("content_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "resume_parse",
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "resume_parse", sa.Column("duration_ms", sa.Integer(), nullable=True)
    )
    op.add_column(
        "resume_parse", sa.Column("total_tokens", sa.Integer(), nullable=True)
    )
    op.create_index(
        "uq_resume_parse_user_hash",
        "resume_parse",
        ["user_id", "content_hash"],
        unique=True,
        postgresql_where=sa.text("content_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_resume_parse_user_hash", table_name="resume_parse")
    op.drop_column("resume_parse", "total_tokens")
    op.drop_column("resume_parse", "duration_ms")
    op.drop_column("resume_parse", "prompt_version")
    op.drop_column("resume_parse", "content_hash")

    op.drop_index("ix_profile_analysis_resume", table_name="profile_analysis")
    op.drop_constraint(
        "fk_profile_analysis_resume", "profile_analysis", type_="foreignkey"
    )
    op.drop_column("profile_analysis", "total_tokens")
    op.drop_column("profile_analysis", "duration_ms")
    op.drop_column("profile_analysis", "resume_id")
    op.drop_column("profile_analysis", "source_revision_version")
    op.drop_column("profile_analysis", "prompt_version")

    op.drop_index("ix_ai_call_log_source", table_name="ai_call_log")
    op.drop_index("ix_ai_call_log_user_created", table_name="ai_call_log")
    op.drop_table("ai_call_log")
