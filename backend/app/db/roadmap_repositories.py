from typing import Any, Sequence
from uuid import UUID, uuid4

from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.db.pool import get_pool


class RoadmapConflictError(RuntimeError):
    """并发路线竞争或唯一约束冲突。"""


class RoadmapUserNotFoundError(RuntimeError):
    """路线所属用户不存在。"""

ROADMAP_COLUMNS = (
    "id, user_id, target_role, status, version, title, summary, gap_snapshot, "
    "generation_mode, provider, model, created_at, updated_at, confirmed_at"
)
STAGE_COLUMNS = (
    "id, roadmap_id, position, title, goal, duration, priority, created_at"
)
TASK_COLUMNS = (
    "id, stage_id, position, title, description, task_type, priority, "
    "estimated_time, acceptance_criteria, status, completed_at, outcome, "
    "created_at, updated_at"
)


class RoadmapRepository:
    def create_or_reuse(
        self,
        user_id: UUID,
        *,
        target_role: str,
        title: str,
        summary: str,
        stages: list[dict[str, Any]],
        gap_snapshot: dict[str, Any],
        generation_mode: str,
        provider: str,
        model: str,
        fingerprint: str,
        regenerate: bool = False,
    ) -> tuple[UUID, bool]:
        roadmap_id = uuid4()
        snapshot = dict(gap_snapshot)
        snapshot["input_fingerprint"] = fingerprint
        try:
            with get_pool().connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        "SELECT id FROM app_user WHERE id = %s FOR UPDATE",
                        (user_id,),
                    )
                    if cur.fetchone() is None:
                        raise RoadmapUserNotFoundError("路线所属用户不存在")

                    if not regenerate:
                        cur.execute(
                            """
                            SELECT id, gap_snapshot
                            FROM career_roadmap
                            WHERE user_id = %s AND status = 'draft'
                            ORDER BY version DESC
                            LIMIT 1
                            """,
                            (user_id,),
                        )
                        existing = cur.fetchone()
                        if existing is not None:
                            existing_snapshot = (
                                existing.get("gap_snapshot") or {}
                            )
                            if (
                                existing_snapshot.get("input_fingerprint")
                                == fingerprint
                            ):
                                return existing["id"], True

                    cur.execute(
                        """
                        UPDATE career_roadmap
                        SET status = 'discarded', updated_at = NOW()
                        WHERE user_id = %s AND status = 'draft'
                        """,
                        (user_id,),
                    )
                    cur.execute(
                        """
                        SELECT COALESCE(MAX(version), 0) + 1 AS version
                        FROM career_roadmap
                        WHERE user_id = %s
                        """,
                        (user_id,),
                    )
                    version = cur.fetchone()["version"]
                    cur.execute(
                        f"""
                        INSERT INTO career_roadmap
                            (id, user_id, target_role, status, version, title, summary,
                             gap_snapshot, generation_mode, provider, model)
                        VALUES (%s, %s, %s, 'draft', %s, %s, %s, %s, %s, %s, %s)
                        RETURNING {ROADMAP_COLUMNS}
                        """,
                        (
                            roadmap_id,
                            user_id,
                            target_role,
                            version,
                            title,
                            summary,
                            Jsonb(snapshot),
                            generation_mode,
                            provider,
                            model,
                        ),
                    )
                    for stage_position, stage in enumerate(stages, start=1):
                        stage_id = uuid4()
                        cur.execute(
                            """
                            INSERT INTO roadmap_stage
                                (id, roadmap_id, position, title, goal, duration, priority)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                stage_id,
                                roadmap_id,
                                stage_position,
                                stage["title"],
                                stage.get("goal") or "",
                                stage.get("duration") or "",
                                stage.get("priority") or "medium",
                            ),
                        )
                        for task_position, task in enumerate(
                            stage.get("tasks", []), start=1
                        ):
                            cur.execute(
                                """
                                INSERT INTO roadmap_task
                                    (id, roadmap_id, stage_id, position, title,
                                     description, task_type, priority, estimated_time,
                                     acceptance_criteria, status)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                                """,
                                (
                                    uuid4(),
                                    roadmap_id,
                                    stage_id,
                                    task_position,
                                    task["title"],
                                    task.get("description") or "",
                                    task.get("task_type") or "learning",
                                    task.get("priority") or "medium",
                                    task.get("estimated_time") or "",
                                    task.get("acceptance_criteria") or "",
                                ),
                            )
        except UniqueViolation as exc:
            raise RoadmapConflictError("路线版本或草稿唯一约束冲突") from exc
        return roadmap_id, False

    def get(self, roadmap_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return self._load(cur, roadmap_id, user_id)

    def get_active(self, user_id: UUID) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    SELECT {ROADMAP_COLUMNS}
                    FROM career_roadmap
                    WHERE user_id = %s AND status = 'active'
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return self._load(cur, row["id"], user_id)

    def get_latest_draft(self, user_id: UUID) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    SELECT {ROADMAP_COLUMNS}
                    FROM career_roadmap
                    WHERE user_id = %s AND status = 'draft'
                    ORDER BY version DESC
                    LIMIT 1
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return self._load(cur, row["id"], user_id)

    def list_summaries(
        self,
        user_id: UUID,
        statuses: Sequence[str],
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT r.id, r.target_role, r.status, r.version, r.title,
                           r.generation_mode, r.created_at, r.updated_at,
                           r.confirmed_at,
                           count(t.id)::int AS task_total,
                           count(t.id) FILTER (WHERE t.status = 'completed')::int
                               AS task_completed
                    FROM career_roadmap r
                    LEFT JOIN roadmap_task t ON t.roadmap_id = r.id
                    WHERE r.user_id = %s AND r.status = ANY(%s)
                    GROUP BY r.id
                    ORDER BY r.version DESC
                    LIMIT %s
                    """,
                    (user_id, list(statuses), limit),
                )
                return list(cur.fetchall())

    def confirm(self, roadmap_id: UUID, user_id: UUID) -> bool:
        try:
            with get_pool().connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        "SELECT id FROM app_user WHERE id = %s FOR UPDATE",
                        (user_id,),
                    )
                    if cur.fetchone() is None:
                        return False
                    cur.execute(
                        """
                        SELECT id FROM career_roadmap
                        WHERE id = %s AND user_id = %s AND status = 'draft'
                        FOR UPDATE
                        """,
                        (roadmap_id, user_id),
                    )
                    if cur.fetchone() is None:
                        return False
                    cur.execute(
                        """
                        UPDATE career_roadmap
                        SET status = 'archived', updated_at = NOW()
                        WHERE user_id = %s AND status = 'active'
                        """,
                        (user_id,),
                    )
                    cur.execute(
                        """
                        UPDATE career_roadmap
                        SET status = 'active', confirmed_at = NOW(), updated_at = NOW()
                        WHERE id = %s AND user_id = %s AND status = 'draft'
                        """,
                        (roadmap_id, user_id),
                    )
                    return cur.rowcount == 1
        except UniqueViolation:
            return False

    def discard(self, roadmap_id: UUID, user_id: UUID) -> bool:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM app_user WHERE id = %s FOR UPDATE",
                    (user_id,),
                )
                if cur.fetchone() is None:
                    return False
                cur.execute(
                    """
                    UPDATE career_roadmap
                    SET status = 'discarded', updated_at = NOW()
                    WHERE id = %s AND user_id = %s AND status = 'draft'
                    """,
                    (roadmap_id, user_id),
                )
                return cur.rowcount == 1

    def update_task(
        self,
        task_id: UUID,
        user_id: UUID,
        *,
        status: str,
        outcome: str | None,
    ) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE roadmap_task t
                    SET status = %s,
                        outcome = COALESCE(%s, t.outcome),
                        completed_at = CASE
                            WHEN %s = 'completed' THEN NOW()
                            ELSE NULL
                        END,
                        updated_at = NOW()
                    FROM career_roadmap r
                    WHERE t.id = %s
                      AND t.roadmap_id = r.id
                      AND r.user_id = %s
                      AND r.status = 'active'
                    RETURNING t.id, t.stage_id, t.position, t.title, t.description,
                              t.task_type, t.priority, t.estimated_time,
                              t.acceptance_criteria, t.status, t.completed_at,
                              t.outcome, t.created_at, t.updated_at,
                              r.id AS roadmap_id, r.version AS roadmap_version
                    """,
                    (status, outcome, status, task_id, user_id),
                )
                return cur.fetchone()

    def task_state(self, task_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT t.id, t.status, r.id AS roadmap_id, r.status AS roadmap_status
                    FROM roadmap_task t
                    JOIN career_roadmap r ON r.id = t.roadmap_id
                    WHERE t.id = %s AND r.user_id = %s
                    """,
                    (task_id, user_id),
                )
                return cur.fetchone()

    def _load(self, cur, roadmap_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        cur.execute(
            f"""
            SELECT {ROADMAP_COLUMNS}
            FROM career_roadmap
            WHERE id = %s AND user_id = %s
            """,
            (roadmap_id, user_id),
        )
        roadmap = cur.fetchone()
        if roadmap is None:
            return None
        cur.execute(
            f"""
            SELECT {STAGE_COLUMNS}
            FROM roadmap_stage
            WHERE roadmap_id = %s
            ORDER BY position
            """,
            (roadmap_id,),
        )
        stages = list(cur.fetchall())
        cur.execute(
            f"""
            SELECT {TASK_COLUMNS}
            FROM roadmap_task
            WHERE roadmap_id = %s
            ORDER BY position
            """,
            (roadmap_id,),
        )
        tasks = list(cur.fetchall())
        tasks_by_stage: dict[UUID, list[dict[str, Any]]] = {}
        for task in tasks:
            tasks_by_stage.setdefault(task["stage_id"], []).append(task)
        for stage in stages:
            stage["tasks"] = tasks_by_stage.get(stage["id"], [])
        roadmap["stages"] = stages
        return roadmap


roadmap_repository = RoadmapRepository()
