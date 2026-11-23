"""stage-five personalized career roadmap

Revision ID: 0005_roadmap
Revises: 0004_profile_revision
Create Date: 2026-11-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_roadmap"
down_revision: Union[str, None] = "0004_profile_revision"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "career_roadmap",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("target_role", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "gap_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("generation_mode", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
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
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'archived', 'discarded')",
            name="ck_career_roadmap_status",
        ),
        sa.CheckConstraint(
            "generation_mode IN ('mock', 'real')",
            name="ck_career_roadmap_generation_mode",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name="fk_career_roadmap_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "version", name="uq_career_roadmap_user_version"
        ),
    )
    op.create_index(
        "ix_career_roadmap_user_created",
        "career_roadmap",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_career_roadmap_user_status",
        "career_roadmap",
        ["user_id", "status"],
    )
    op.create_index(
        "uq_career_roadmap_active",
        "career_roadmap",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "roadmap_stage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("roadmap_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("duration", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "priority IN ('high', 'medium', 'low')",
            name="ck_roadmap_stage_priority",
        ),
        sa.ForeignKeyConstraint(
            ["roadmap_id"],
            ["career_roadmap.id"],
            name="fk_roadmap_stage_roadmap",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "roadmap_id", "position", name="uq_roadmap_stage_position"
        ),
    )
    op.create_index(
        "ix_roadmap_stage_roadmap", "roadmap_stage", ["roadmap_id"]
    )

    op.create_table(
        "roadmap_task",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("roadmap_id", sa.Uuid(), nullable=False),
        sa.Column("stage_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("task_type", sa.String(length=20), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column(
            "estimated_time", sa.String(length=100), nullable=False, server_default=""
        ),
        sa.Column(
            "acceptance_criteria", sa.Text(), nullable=False, server_default=""
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=False, server_default=""),
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
            "task_type IN ('learning', 'practice', 'review')",
            name="ck_roadmap_task_type",
        ),
        sa.CheckConstraint(
            "priority IN ('high', 'medium', 'low')",
            name="ck_roadmap_task_priority",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'abandoned')",
            name="ck_roadmap_task_status",
        ),
        sa.ForeignKeyConstraint(
            ["roadmap_id"],
            ["career_roadmap.id"],
            name="fk_roadmap_task_roadmap",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["stage_id"],
            ["roadmap_stage.id"],
            name="fk_roadmap_task_stage",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "stage_id", "position", name="uq_roadmap_task_position"
        ),
    )
    op.create_index(
        "ix_roadmap_task_roadmap_status",
        "roadmap_task",
        ["roadmap_id", "status"],
    )
    op.create_index("ix_roadmap_task_stage", "roadmap_task", ["stage_id"])


def downgrade() -> None:
    op.drop_index("ix_roadmap_task_stage", table_name="roadmap_task")
    op.drop_index("ix_roadmap_task_roadmap_status", table_name="roadmap_task")
    op.drop_table("roadmap_task")
    op.drop_index("ix_roadmap_stage_roadmap", table_name="roadmap_stage")
    op.drop_table("roadmap_stage")
    op.drop_index("uq_career_roadmap_active", table_name="career_roadmap")
    op.drop_index("ix_career_roadmap_user_status", table_name="career_roadmap")
    op.drop_index("ix_career_roadmap_user_created", table_name="career_roadmap")
    op.drop_table("career_roadmap")
