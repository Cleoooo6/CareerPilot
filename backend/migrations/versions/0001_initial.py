"""stage-one infrastructure tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id", name="uq_app_user_external_id"),
    )

    op.create_table(
        "conversation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
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
            ["user_id"], ["app_user.id"], name="fk_conversation_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_user_updated",
        "conversation",
        ["user_id", "updated_at"],
    )

    op.create_table(
        "message",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant', 'system')", name="ck_message_role"
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversation.id"],
            name="fk_message_conversation",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_message_conversation_created",
        "message",
        ["conversation_id", "created_at"],
    )

    op.create_table(
        "agent_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_type", sa.String(length=64), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'cancelled')",
            name="ck_agent_run_status",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversation.id"],
            name="fk_agent_run_conversation",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], name="fk_agent_run_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_run_conversation_started",
        "agent_run",
        ["conversation_id", "started_at"],
    )
    op.create_index("ix_agent_run_user_started", "agent_run", ["user_id", "started_at"])

    op.create_table(
        "agent_trace",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("node_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_type", sa.String(length=64), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('started', 'completed', 'failed')",
            name="ck_agent_trace_status",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["agent_run.id"], name="fk_agent_trace_run", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], name="fk_agent_trace_user", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversation.id"],
            name="fk_agent_trace_conversation",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_trace_run_started", "agent_trace", ["run_id", "started_at"])
    op.create_index("ix_agent_trace_user_started", "agent_trace", ["user_id", "started_at"])
    op.create_index(
        "ix_agent_trace_conversation", "agent_trace", ["conversation_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_agent_trace_conversation", table_name="agent_trace")
    op.drop_index("ix_agent_trace_user_started", table_name="agent_trace")
    op.drop_index("ix_agent_trace_run_started", table_name="agent_trace")
    op.drop_table("agent_trace")
    op.drop_index("ix_agent_run_user_started", table_name="agent_run")
    op.drop_index("ix_agent_run_conversation_started", table_name="agent_run")
    op.drop_table("agent_run")
    op.drop_index("ix_message_conversation_created", table_name="message")
    op.drop_table("message")
    op.drop_index("ix_conversation_user_updated", table_name="conversation")
    op.drop_table("conversation")
    op.drop_table("app_user")