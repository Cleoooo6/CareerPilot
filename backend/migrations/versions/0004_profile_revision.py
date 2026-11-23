"""stage-four-point-five profile revision history

Revision ID: 0004_profile_revision
Revises: 0003_market
Create Date: 2026-11-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_profile_revision"
down_revision: Union[str, None] = "0003_market"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "profile_revision",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("change_source", sa.String(length=24), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "change_source IN ('manual', 'resume')",
            name="ck_profile_revision_source",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name="fk_profile_revision_user",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["career_profile.id"],
            name="fk_profile_revision_profile",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id", "version", name="uq_profile_revision_version"
        ),
    )
    op.create_index(
        "ix_profile_revision_user_version",
        "profile_revision",
        ["user_id", "version"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_profile_revision_user_version", table_name="profile_revision"
    )
    op.drop_table("profile_revision")
