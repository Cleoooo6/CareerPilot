"""industry taxonomy v2: 16 industries, relevance and audit fields

Revision ID: 0009_industry_taxonomy_v2
Revises: 0008_industry_pulse_taxonomy
Create Date: 2026-11-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_industry_taxonomy_v2"
down_revision: Union[str, None] = "0008_industry_pulse_taxonomy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LEGACY_INDUSTRIES = (
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

NEW_INDUSTRIES = (
    "digital_tech_comms",
    "finance_insurance",
    "manufacturing_industry",
    "energy_environment",
    "auto_smart_mobility",
    "transport_logistics",
    "health_life_sciences",
    "education_research",
    "agriculture_food",
    "consumer_retail_services",
    "real_estate_construction",
    "culture_media_content",
    "arts_design",
    "sports_industry",
    "tourism_hospitality_events",
    "enterprise_professional_services",
)

ALL_INDUSTRIES = tuple(dict.fromkeys((*LEGACY_INDUSTRIES, *NEW_INDUSTRIES)))

RELEVANCE_STATUSES = (
    "industry_relevant",
    "macro_signal",
    "needs_review",
    "irrelevant",
)

DOWNGRADE_MAP = {
    "digital_tech_comms": "ai_digital",
    "energy_environment": "energy_new_energy",
    "auto_smart_mobility": "auto_transport",
    "transport_logistics": "logistics_supply_chain",
    "health_life_sciences": "healthcare_biopharma",
    "consumer_retail_services": "consumer_retail",
    "culture_media_content": "culture_media_tourism",
    "arts_design": "culture_media_tourism",
    "sports_industry": "culture_media_tourism",
    "tourism_hospitality_events": "culture_media_tourism",
    "enterprise_professional_services": "professional_services",
}


def _in_clause(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(item) for item in values)})"


def upgrade() -> None:
    op.add_column(
        "industry_pulse_article",
        sa.Column(
            "relevance_status",
            sa.String(length=20),
            server_default="needs_review",
            nullable=False,
        ),
    )
    op.add_column(
        "industry_pulse_article",
        sa.Column(
            "classification_basis",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "industry_pulse_article",
        sa.Column("legacy_industry", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "industry_pulse_article",
        sa.Column(
            "taxonomy_version", sa.SmallInteger(), server_default="1", nullable=False
        ),
    )
    op.execute(
        "UPDATE industry_pulse_article SET legacy_industry = industry "
        "WHERE legacy_industry IS NULL"
    )
    op.alter_column(
        "industry_pulse_article",
        "industry",
        existing_type=sa.String(length=40),
        nullable=True,
    )
    op.alter_column(
        "industry_pulse_article",
        "primary_industry",
        existing_type=sa.String(length=40),
        nullable=True,
    )
    op.drop_constraint(
        "ck_industry_pulse_article_industry",
        "industry_pulse_article",
        type_="check",
    )
    op.drop_constraint(
        "ck_industry_pulse_article_primary_industry",
        "industry_pulse_article",
        type_="check",
    )
    op.create_check_constraint(
        "ck_industry_pulse_article_industry",
        "industry_pulse_article",
        "industry IS NULL OR " + _in_clause("industry", ALL_INDUSTRIES),
    )
    op.create_check_constraint(
        "ck_industry_pulse_article_primary_industry",
        "industry_pulse_article",
        "primary_industry IS NULL OR "
        + _in_clause("primary_industry", ALL_INDUSTRIES),
    )
    op.create_check_constraint(
        "ck_industry_pulse_article_relevance_status",
        "industry_pulse_article",
        _in_clause("relevance_status", RELEVANCE_STATUSES),
    )
    op.create_index(
        "ix_industry_pulse_article_relevance_region_published",
        "industry_pulse_article",
        ["relevance_status", "region", "published_at"],
    )
    op.create_index(
        "ix_industry_pulse_article_taxonomy_version",
        "industry_pulse_article",
        ["taxonomy_version"],
    )

    op.add_column(
        "industry_feed_source",
        sa.Column("legacy_industry", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "industry_feed_source",
        sa.Column(
            "taxonomy_version", sa.SmallInteger(), server_default="1", nullable=False
        ),
    )
    op.execute(
        "UPDATE industry_feed_source SET legacy_industry = industry "
        "WHERE legacy_industry IS NULL"
    )
    op.drop_constraint(
        "ck_industry_feed_source_industry", "industry_feed_source", type_="check"
    )
    op.create_check_constraint(
        "ck_industry_feed_source_industry",
        "industry_feed_source",
        _in_clause("industry", ALL_INDUSTRIES),
    )
    op.create_index(
        "ix_industry_feed_source_taxonomy_version",
        "industry_feed_source",
        ["taxonomy_version"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_industry_feed_source_taxonomy_version", table_name="industry_feed_source"
    )
    op.drop_constraint(
        "ck_industry_feed_source_industry", "industry_feed_source", type_="check"
    )
    for new_id, old_id in DOWNGRADE_MAP.items():
        op.execute(
            sa.text(
                "UPDATE industry_feed_source SET industry=:old "
                "WHERE industry=:new"
            ).bindparams(old=old_id, new=new_id)
        )
    op.create_check_constraint(
        "ck_industry_feed_source_industry",
        "industry_feed_source",
        _in_clause("industry", LEGACY_INDUSTRIES),
    )
    op.drop_column("industry_feed_source", "taxonomy_version")
    op.drop_column("industry_feed_source", "legacy_industry")

    op.drop_index(
        "ix_industry_pulse_article_taxonomy_version",
        table_name="industry_pulse_article",
    )
    op.drop_index(
        "ix_industry_pulse_article_relevance_region_published",
        table_name="industry_pulse_article",
    )
    op.drop_constraint(
        "ck_industry_pulse_article_relevance_status",
        "industry_pulse_article",
        type_="check",
    )
    op.drop_constraint(
        "ck_industry_pulse_article_primary_industry",
        "industry_pulse_article",
        type_="check",
    )
    op.drop_constraint(
        "ck_industry_pulse_article_industry",
        "industry_pulse_article",
        type_="check",
    )
    for new_id, old_id in DOWNGRADE_MAP.items():
        op.execute(
            sa.text(
                "UPDATE industry_pulse_article SET industry=:old "
                "WHERE industry=:new"
            ).bindparams(old=old_id, new=new_id)
        )
    op.execute(
        "UPDATE industry_pulse_article SET primary_industry = industry "
        "WHERE primary_industry IS NULL"
    )
    op.create_check_constraint(
        "ck_industry_pulse_article_industry",
        "industry_pulse_article",
        _in_clause("industry", LEGACY_INDUSTRIES),
    )
    op.create_check_constraint(
        "ck_industry_pulse_article_primary_industry",
        "industry_pulse_article",
        _in_clause("primary_industry", LEGACY_INDUSTRIES),
    )
    op.alter_column(
        "industry_pulse_article",
        "industry",
        existing_type=sa.String(length=40),
        nullable=False,
    )
    op.alter_column(
        "industry_pulse_article",
        "primary_industry",
        existing_type=sa.String(length=40),
        nullable=False,
    )
    op.drop_column("industry_pulse_article", "taxonomy_version")
    op.drop_column("industry_pulse_article", "legacy_industry")
    op.drop_column("industry_pulse_article", "classification_basis")
    op.drop_column("industry_pulse_article", "relevance_status")