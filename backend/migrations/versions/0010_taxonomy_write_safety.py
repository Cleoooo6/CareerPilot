"""taxonomy write safety: no fallback defaults and legacy snapshots

Revision ID: 0010_taxonomy_write_safety
Revises: 0009_industry_taxonomy_v2
Create Date: 2026-11-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_taxonomy_write_safety"
down_revision: Union[str, None] = "0009_industry_taxonomy_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "industry_pulse_article",
        "primary_industry",
        existing_type=sa.String(length=40),
        server_default=None,
    )
    op.alter_column(
        "industry_pulse_article",
        "industry",
        existing_type=sa.String(length=40),
        server_default=None,
    )
    op.add_column(
        "industry_pulse_article",
        sa.Column("legacy_primary_industry", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "industry_pulse_article",
        sa.Column(
            "legacy_industries",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE industry_pulse_article SET "
        "legacy_primary_industry = primary_industry, "
        "legacy_industries = industries "
        "WHERE legacy_primary_industry IS NULL OR legacy_industries IS NULL"
    )
    op.create_check_constraint(
        "ck_industry_pulse_article_industries_array",
        "industry_pulse_article",
        "jsonb_typeof(industries) = 'array'",
    )
    op.create_check_constraint(
        "ck_industry_pulse_article_primary_in_industries",
        "industry_pulse_article",
        "primary_industry IS NULL OR "
        "industries @> jsonb_build_array(primary_industry)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_industry_pulse_article_primary_in_industries",
        "industry_pulse_article",
        type_="check",
    )
    op.drop_constraint(
        "ck_industry_pulse_article_industries_array",
        "industry_pulse_article",
        type_="check",
    )
    op.alter_column(
        "industry_pulse_article",
        "primary_industry",
        existing_type=sa.String(length=40),
        server_default="professional_services",
    )
    op.drop_column("industry_pulse_article", "legacy_industries")
    op.drop_column("industry_pulse_article", "legacy_primary_industry")