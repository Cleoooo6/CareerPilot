"""auth accounts, sessions and one-time tokens

Revision ID: 0011_auth_accounts
Revises: 0010_taxonomy_write_safety
Create Date: 2026-11-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_auth_accounts"
down_revision: Union[str, None] = "0010_taxonomy_write_safety"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("email", sa.String(length=320), nullable=True))
    op.add_column(
        "app_user",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "app_user",
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column(
        "app_user",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "app_user",
        sa.Column(
            "is_demo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "app_user",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.execute(
        "UPDATE app_user SET is_demo=true, status='active' "
        "WHERE external_id='demo-user'"
    )
    op.create_index(
        "uq_app_user_email_lower",
        "app_user",
        [sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )

    op.create_table(
        "auth_session",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_auth_session_user_expires",
        "auth_session",
        ["user_id", "expires_at"],
    )
    op.create_index(
        "ix_auth_session_token_hash",
        "auth_session",
        ["token_hash"],
    )

    op.create_table(
        "auth_token",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_auth_token_user_purpose",
        "auth_token",
        ["user_id", "purpose", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_auth_token_user_purpose", table_name="auth_token")
    op.drop_table("auth_token")
    op.drop_index("ix_auth_session_token_hash", table_name="auth_session")
    op.drop_index("ix_auth_session_user_expires", table_name="auth_session")
    op.drop_table("auth_session")
    op.drop_index("uq_app_user_email_lower", table_name="app_user")
    op.drop_column("app_user", "updated_at")
    op.drop_column("app_user", "is_demo")
    op.drop_column("app_user", "email_verified_at")
    op.drop_column("app_user", "status")
    op.drop_column("app_user", "password_hash")
    op.drop_column("app_user", "email")