"""stage-five-point-one roadmap concurrency safety

Revision ID: 0006_roadmap_concurrency
Revises: 0005_roadmap
Create Date: 2026-11-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_roadmap_concurrency"
down_revision: Union[str, None] = "0005_roadmap"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 迁移前清理历史并发可能产生的重复草稿：每用户保留版本号最大的一条，
    # 其余标记为 discarded（不删除数据）。
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY user_id
                       ORDER BY version DESC, created_at DESC, id
                   ) AS rn
            FROM career_roadmap
            WHERE status = 'draft'
        )
        UPDATE career_roadmap AS r
        SET status = 'discarded', updated_at = NOW()
        FROM ranked
        WHERE r.id = ranked.id AND ranked.rn > 1
        """
    )
    op.create_index(
        "uq_career_roadmap_draft",
        "career_roadmap",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'draft'"),
    )


def downgrade() -> None:
    op.drop_index("uq_career_roadmap_draft", table_name="career_roadmap")
