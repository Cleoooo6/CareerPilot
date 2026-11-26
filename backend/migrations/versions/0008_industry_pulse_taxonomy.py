"""industry pulse multi-industry, region and content policy

Revision ID: 0008_industry_pulse_taxonomy
Revises: 0007_industry_pulse
Create Date: 2026-11-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_industry_pulse_taxonomy"
down_revision: Union[str, None] = "0007_industry_pulse"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDUSTRIES = (
    "internet_telecom",
    "ai_digital",
    "finance_insurance",
    "manufacturing_industry",
    "energy_new_energy",
    "auto_transport",
    "healthcare_biopharma",
    "education_research",
    "consumer_retail",
    "real_estate_construction",
    "logistics_supply_chain",
    "agriculture_food",
    "culture_media_tourism",
    "professional_services",
)


def _in_clause(column: str) -> str:
    return f"{column} IN ({', '.join(repr(item) for item in INDUSTRIES)})"


def upgrade() -> None:
    op.alter_column(
        "industry_feed_source",
        "industry",
        existing_type=sa.String(length=20),
        type_=sa.String(length=40),
        existing_nullable=False,
    )
    op.alter_column(
        "industry_pulse_article",
        "industry",
        existing_type=sa.String(length=20),
        type_=sa.String(length=40),
        existing_nullable=False,
    )
    op.add_column(
        "industry_feed_source",
        sa.Column(
            "industries",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "industry_feed_source",
        sa.Column("region", sa.String(length=8), server_default="INTL", nullable=False),
    )
    op.add_column(
        "industry_feed_source",
        sa.Column(
            "content_policy",
            sa.String(length=20),
            server_default="metadata_only",
            nullable=False,
        ),
    )
    op.add_column(
        "industry_pulse_article",
        sa.Column(
            "industries",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "industry_pulse_article",
        sa.Column(
            "primary_industry",
            sa.String(length=40),
            server_default="professional_services",
            nullable=False,
        ),
    )
    op.add_column(
        "industry_pulse_article",
        sa.Column("region", sa.String(length=8), server_default="INTL", nullable=False),
    )
    op.add_column(
        "industry_pulse_article",
        sa.Column(
            "content_policy",
            sa.String(length=20),
            server_default="metadata_only",
            nullable=False,
        ),
    )

    op.drop_constraint(
        "ck_industry_feed_source_industry", "industry_feed_source", type_="check"
    )
    op.drop_constraint(
        "ck_industry_pulse_article_industry", "industry_pulse_article", type_="check"
    )
    op.execute(
        """
        UPDATE industry_feed_source
        SET industry = CASE industry
            WHEN 'internet' THEN 'internet_telecom'
            WHEN 'ai' THEN 'ai_digital'
            WHEN 'finance' THEN 'finance_insurance'
            WHEN 'energy' THEN 'energy_new_energy'
            ELSE industry END
        """
    )
    op.execute(
        """
        UPDATE industry_pulse_article
        SET industry = CASE industry
            WHEN 'internet' THEN 'internet_telecom'
            WHEN 'ai' THEN 'ai_digital'
            WHEN 'finance' THEN 'finance_insurance'
            WHEN 'energy' THEN 'energy_new_energy'
            ELSE industry END
        """
    )
    op.execute(
        """
        UPDATE industry_feed_source
        SET industries = jsonb_build_array(industry)
        WHERE industries = '[]'::jsonb
        """
    )
    op.execute(
        """
        UPDATE industry_pulse_article
        SET industries = jsonb_build_array(industry),
            primary_industry = industry
        WHERE industries = '[]'::jsonb
        """
    )
    op.execute(
        """
        UPDATE industry_pulse_article a
        SET region = s.region,
            content_policy = s.content_policy
        FROM industry_feed_source s
        WHERE a.source_id = s.id
        """
    )

    op.create_check_constraint(
        "ck_industry_feed_source_industry", "industry_feed_source", _in_clause("industry")
    )
    op.create_check_constraint(
        "ck_industry_pulse_article_industry", "industry_pulse_article", _in_clause("industry")
    )
    op.create_check_constraint(
        "ck_industry_pulse_article_primary_industry",
        "industry_pulse_article",
        _in_clause("primary_industry"),
    )
    op.create_check_constraint(
        "ck_industry_feed_source_region",
        "industry_feed_source",
        "region IN ('CN', 'INTL')",
    )
    op.create_check_constraint(
        "ck_industry_pulse_article_region",
        "industry_pulse_article",
        "region IN ('CN', 'INTL')",
    )
    op.create_check_constraint(
        "ck_industry_feed_source_content_policy",
        "industry_feed_source",
        "content_policy IN ('feed_excerpt', 'metadata_only', 'blocked')",
    )
    op.create_check_constraint(
        "ck_industry_pulse_article_content_policy",
        "industry_pulse_article",
        "content_policy IN ('feed_excerpt', 'metadata_only', 'blocked')",
    )
    op.create_index(
        "ix_industry_feed_source_region_enabled",
        "industry_feed_source",
        ["region", "enabled"],
    )
    op.create_index(
        "ix_industry_pulse_article_region_published",
        "industry_pulse_article",
        ["region", "published_at"],
    )
    op.create_index(
        "ix_industry_pulse_article_industries",
        "industry_pulse_article",
        ["industries"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_industry_feed_source_industries",
        "industry_feed_source",
        ["industries"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_industry_feed_source_industries", table_name="industry_feed_source")
    op.drop_index("ix_industry_pulse_article_industries", table_name="industry_pulse_article")
    op.drop_index(
        "ix_industry_pulse_article_region_published",
        table_name="industry_pulse_article",
    )
    op.drop_index(
        "ix_industry_feed_source_region_enabled",
        table_name="industry_feed_source",
    )
    for table, names in (
        (
            "industry_feed_source",
            (
                "ck_industry_feed_source_content_policy",
                "ck_industry_feed_source_region",
                "ck_industry_feed_source_industry",
            ),
        ),
        (
            "industry_pulse_article",
            (
                "ck_industry_pulse_article_content_policy",
                "ck_industry_pulse_article_region",
                "ck_industry_pulse_article_primary_industry",
                "ck_industry_pulse_article_industry",
            ),
        ),
    ):
        for name in names:
            op.drop_constraint(name, table, type_="check")
    op.drop_column("industry_pulse_article", "content_policy")
    op.drop_column("industry_pulse_article", "region")
    op.drop_column("industry_pulse_article", "primary_industry")
    op.drop_column("industry_pulse_article", "industries")
    op.drop_column("industry_feed_source", "content_policy")
    op.drop_column("industry_feed_source", "region")
    op.drop_column("industry_feed_source", "industries")
    op.create_check_constraint(
        "ck_industry_feed_source_industry",
        "industry_feed_source",
        "industry IN ('internet', 'finance', 'ai', 'energy')",
    )
    op.create_check_constraint(
        "ck_industry_pulse_article_industry",
        "industry_pulse_article",
        "industry IN ('internet', 'finance', 'ai', 'energy')",
    )