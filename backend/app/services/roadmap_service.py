import asyncio
import hashlib
import json
from functools import partial
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.core.errors import AppError, NotFoundError
from app.core.llm import LLMClient, LLMError, get_llm_client
from app.db.profile_repositories import profile_repository
from app.db.roadmap_repositories import (
    RoadmapConflictError,
    RoadmapRepository,
    RoadmapUserNotFoundError,
    roadmap_repository,
)
from app.schemas.roadmap import (
    RoadmapDraftLLM,
    RoadmapOut,
    RoadmapStageOut,
    RoadmapSummaryOut,
    RoadmapTaskOut,
    RoadmapTaskUpdateOut,
    SkillGapOut,
)
from app.services.market_service import MarketService, get_market_service
from app.services.roadmap_gap import compute_skill_gap

ROADMAP_SYSTEM_PROMPT = """你是 CareerPilot AI 的个性化成长路线规划师。
只基于给定的职业画像、技能差距和市场统计生成路线，不得编造用户经历、技能、证书或市场数字。

要求：
- 阶段有合理先后顺序，1-6 个阶段；每阶段 1-8 个任务；总任务 2-30 个。
- 每个任务必须具体、可执行、可验收，给出清晰的验收标准；禁止空泛的“多练习”“多学习”。
- 不得声称任务完成等于技能掌握；不得建议虚报熟练度。
- 用户确认技能资料不等于客观能力验证；没有记录不等于不具备。
- 市场统计来自 CareerPilot Market Radar 数据库，必须注明样本量、数据性质；synthetic 数据必须标注为合成数据，不能当作真实就业市场结论。
- 若 basis=general（没有市场样本），只生成明确标注的通用建议，不得包装成市场需求。
只输出 JSON 对象，字段符合 Schema；不要输出 Markdown、解释或额外字段。"""


def _profile_target_role(profile: dict[str, Any] | None) -> str:
    goals = (profile or {}).get("goals") or {}
    return str(goals.get("target_role") or "").strip()


def _gap_fingerprint(target_role: str, gap: SkillGapOut) -> str:
    payload = {
        "target_role": target_role,
        "basis": gap.basis,
        "reference_only": gap.reference_only,
        "profile_skills": [
            skill.model_dump(mode="json") for skill in gap.profile_skills
        ],
        "matched": [
            [item.name, round(item.market_share, 4)] for item in gap.matched
        ],
        "to_improve": [
            [item.name, round(item.market_share, 4)]
            for item in gap.to_improve
        ],
        "not_recorded": [
            [item.name, round(item.market_share, 4)]
            for item in gap.not_recorded
        ],
        "meta": {
            "sample_size": gap.meta.sample_size,
            "sample_sufficient": gap.meta.sample_sufficient,
            "dataset_kinds": gap.meta.dataset_kinds,
            "updated_at": (
                gap.meta.updated_at.isoformat()
                if gap.meta.updated_at
                else None
            ),
        },
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _snapshot_fingerprint(snapshot: dict[str, Any] | None) -> str | None:
    if not isinstance(snapshot, dict):
        return None
    value = snapshot.get("input_fingerprint")
    return str(value) if value else None


def _profile_summary(profile: dict[str, Any] | None) -> dict[str, Any]:
    data = profile or {}
    basic = data.get("basic") or {}
    goals = data.get("goals") or {}
    skills = []
    for item in data.get("skills", [])[:20]:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        skills.append(
            {
                "name": name,
                "proficiency": str(item.get("proficiency") or ""),
                "evidence": str(item.get("evidence") or ""),
                "source": str(item.get("source") or ""),
                "verification": str(item.get("verification") or ""),
            }
        )
    projects = [
        {
            "name": str(item.get("name") or ""),
            "role": str(item.get("role") or ""),
            "tech_stack": str(item.get("tech_stack") or ""),
            "achievements": str(item.get("achievements") or ""),
        }
        for item in data.get("projects", [])[:5]
    ]
    experiences = [
        {
            "company": str(item.get("company") or ""),
            "position": str(item.get("position") or ""),
        }
        for item in data.get("experiences", [])[:5]
    ]
    return {
        "basic": {
            key: basic.get(key)
            for key in ("education_level", "major", "graduation_year", "location")
            if basic.get(key) not in (None, "")
        },
        "goals": {
            key: goals.get(key)
            for key in ("target_role", "target_industry", "job_status", "desired_direction")
            if goals.get(key) not in (None, "")
        },
        "skills": skills,
        "projects": [item for item in projects if item["name"]],
        "experiences": [
            item for item in experiences if item["company"] or item["position"]
        ],
    }


def _task(
    title: str,
    description: str,
    *,
    task_type: str,
    priority: str,
    estimated_time: str,
    acceptance_criteria: str,
) -> dict[str, Any]:
    return {
        "title": title,
        "description": description,
        "task_type": task_type,
        "priority": priority,
        "estimated_time": estimated_time,
        "acceptance_criteria": acceptance_criteria,
    }


def _mock_roadmap(target_role: str, gap: SkillGapOut) -> dict[str, Any]:
    missing = [item.name for item in gap.not_recorded][:3]
    improve = [item.name for item in gap.to_improve][:3]
    stages: list[dict[str, Any]] = []

    if missing:
        tasks = [
            _task(
                f"完成 {skill} 的基础练习与自测",
                f"围绕 {target_role} 的真实工作场景完成 {skill} 入门练习，"
                "记录遇到的问题、解决方式和仍不确定的点。",
                task_type="learning",
                priority="high" if len(missing) <= 2 else "medium",
                estimated_time="1-2 周",
                acceptance_criteria=(
                    f"提交可检查的练习成果（代码仓库或笔记），并写出 3 个 {skill} "
                    "关键概念及其实际用途"
                ),
            )
            for skill in missing
        ]
        stages.append(
            {
                "title": "补齐目标岗位核心技能",
                "goal": f"先覆盖 {target_role} 市场统计中出现、但画像尚未记录的核心技能。",
                "duration": "2-4 周",
                "priority": "high",
                "tasks": tasks,
            }
        )
    else:
        tasks = [
            _task(
                f"为 {skill} 补充可核验的能力证据",
                "回顾已有项目、课程或工作经历，补充能证明该技能使用过程的证据；"
                "不得虚报熟练度。",
                task_type="review",
                priority="medium",
                estimated_time="3-5 天",
                acceptance_criteria=(
                    "在 Profile 中为该技能补充项目、课程或工作证据，并由本人确认；"
                    "确认资料不等于客观能力验证"
                ),
            )
            for skill in (improve or ["目标岗位核心技能"])
        ]
        stages.append(
            {
                "title": "补全能力证据",
                "goal": "把已有但缺少证据或验证状态的技能整理成可核验记录。",
                "duration": "1-2 周",
                "priority": "medium",
                "tasks": tasks,
            }
        )

    practice_tasks = [
        _task(
            f"完成一个面向 {target_role} 的端到端小项目",
            "项目应覆盖目标岗位的典型工作流程，而不是只做跟练；"
            "明确个人职责、关键取舍与可验证结果。",
            task_type="practice",
            priority="high",
            estimated_time="2-4 周",
            acceptance_criteria=(
                "项目可运行或可展示，README 写清目标、技术栈、个人职责与结果；"
                "附仓库或演示链接"
            ),
        )
    ]
    focus = (missing or improve)[:1]
    if focus:
        practice_tasks.append(
            _task(
                f"在项目中应用 {focus[0]} 并记录取舍",
                f"在端到端项目中实际使用 {focus[0]}，记录选择理由、遇到的问题和替代方案。",
                task_type="practice",
                priority="medium",
                estimated_time="3-5 天",
                acceptance_criteria=(
                    f"项目中存在可检查的 {focus[0]} 使用记录，并提交一段取舍说明"
                ),
            )
        )
    stages.append(
        {
            "title": "完成端到端实践项目",
            "goal": "用可展示的实践成果验证学习内容，而不是停留在课程完成度。",
            "duration": "3-4 周",
            "priority": "high",
            "tasks": practice_tasks,
        }
    )

    stages.append(
        {
            "title": "沉淀证据与复盘",
            "goal": "把实践成果转化为画像证据，并明确下一轮需要验证的能力。",
            "duration": "1 周",
            "priority": "medium",
            "tasks": [
                _task(
                    "把项目成果写入 Profile 技能证据",
                    "在 Profile 中补充项目证据并确认；任务完成不等于技能掌握，"
                    "不得自行提高能力等级。",
                    task_type="review",
                    priority="medium",
                    estimated_time="1-2 天",
                    acceptance_criteria=(
                        "画像中对应技能出现项目证据且由本人确认；不虚报熟练度"
                    ),
                ),
                _task(
                    "复盘技能差距并更新下一阶段目标",
                    "对照本次路线和最新市场统计，列出已改进点、仍待验证点和下一步行动。",
                    task_type="review",
                    priority="low",
                    estimated_time="1 天",
                    acceptance_criteria=(
                        "输出至少 3 条已改进点、2 条待验证点和 3 项下一步行动"
                    ),
                ),
            ],
        }
    )

    if gap.basis == "market":
        quality_note = (
            "样本量不足，当前统计仅作参考；" if gap.reference_only else ""
        )
        summary = (
            f"基于目标岗位「{target_role}」的市场技能统计（样本 "
            f"{gap.meta.sample_size} 条，数据性质 {','.join(gap.meta.dataset_kinds) or '未知'}）"
            f"与当前画像生成。{quality_note}"
            "市场数据不足或为合成数据时只能作为参考。"
        )
    else:
        summary = (
            "当前目标方向没有可用的市场样本；这是一份明确标注的通用建议路线，"
            "不代表真实市场需求，请确认前自行核对。"
        )

    return {
        "title": f"{target_role} 成长路线",
        "summary": summary,
        "stages": stages,
    }


class RoadmapService:
    def __init__(
        self,
        repository: RoadmapRepository | None = None,
        llm_client: LLMClient | None = None,
        market_service: MarketService | None = None,
    ) -> None:
        self.repository = repository or roadmap_repository
        self.llm = llm_client or get_llm_client()
        self.market = market_service or get_market_service()

    async def gap_for_user(
        self, user_id: UUID, target_role: str | None = None
    ) -> SkillGapOut:
        profile = await asyncio.to_thread(profile_repository.get_data, user_id)
        role = (target_role or "").strip() or _profile_target_role(profile)
        if not role:
            raise AppError(
                "ROADMAP_TARGET_REQUIRED",
                "请先在职业画像中设置目标岗位",
                status_code=409,
            )
        demand = await asyncio.to_thread(
            partial(self.market.skills, role=role, limit=15)
        )
        return compute_skill_gap(
            profile_data=profile,
            target_role=role,
            demand=demand,
        )

    async def generate_draft(
        self,
        user_id: UUID,
        target_role: str | None = None,
        regenerate: bool = False,
    ) -> tuple[RoadmapOut, bool]:
        profile = await asyncio.to_thread(profile_repository.get_data, user_id)
        role = (target_role or "").strip() or _profile_target_role(profile)
        if not role:
            raise AppError(
                "ROADMAP_TARGET_REQUIRED",
                "请先在职业画像中设置目标岗位",
                status_code=409,
            )
        gap = await self.gap_for_user(user_id, role)
        fingerprint = _gap_fingerprint(role, gap)
        if not regenerate:
            latest = await asyncio.to_thread(
                self.repository.get_latest_draft, user_id
            )
            if latest is not None and (
                _snapshot_fingerprint(latest.get("gap_snapshot"))
                == fingerprint
            ):
                return self._serialize(latest), True

        prompt = {
            "target_role": role,
            "profile": _profile_summary(profile),
            "skill_gap": gap.model_dump(mode="json"),
        }
        mock_payload = _mock_roadmap(role, gap)
        try:
            result = await asyncio.to_thread(
                self.llm.complete_structured_with_meta,
                ROADMAP_SYSTEM_PROMPT,
                json.dumps(prompt, ensure_ascii=False)[:12000],
                RoadmapDraftLLM,
                mock_payload=mock_payload,
            )
        except LLMError as exc:
            raise AppError(exc.code, exc.message, status_code=exc.status_code) from exc
        except ValidationError as exc:
            raise AppError(
                "ROADMAP_INVALID_OUTPUT",
                "生成路线未通过结构校验，请重试",
                status_code=502,
            ) from exc
        draft = result.value
        try:
            roadmap_id, reused = await asyncio.to_thread(
                self.repository.create_or_reuse,
                user_id,
                target_role=role,
                title=draft.title,
                summary=draft.summary,
                stages=[
                    stage.model_dump(mode="json") for stage in draft.stages
                ],
                gap_snapshot=gap.model_dump(mode="json"),
                generation_mode=self.llm.mode,
                provider=self.llm.settings.llm_provider,
                model=result.model or self.llm.settings.llm_model,
                fingerprint=fingerprint,
                regenerate=regenerate,
            )
        except RoadmapConflictError as exc:
            raise AppError(
                "ROADMAP_GENERATE_CONFLICT",
                "路线生成发生并发冲突，请刷新后重试",
                status_code=409,
            ) from exc
        except RoadmapUserNotFoundError as exc:
            raise NotFoundError("用户不存在") from exc
        return await self._get_or_404(user_id, roadmap_id), reused

    async def get_current(self, user_id: UUID) -> RoadmapOut | None:
        row = await asyncio.to_thread(self.repository.get_active, user_id)
        return self._serialize(row) if row else None

    async def get_latest_draft(self, user_id: UUID) -> RoadmapOut | None:
        row = await asyncio.to_thread(self.repository.get_latest_draft, user_id)
        return self._serialize(row) if row else None

    async def list_drafts(self, user_id: UUID) -> list[RoadmapSummaryOut]:
        rows = await asyncio.to_thread(
            self.repository.list_summaries, user_id, ("draft",)
        )
        return [self._summary(row) for row in rows]

    async def list_history(self, user_id: UUID) -> list[RoadmapSummaryOut]:
        rows = await asyncio.to_thread(
            self.repository.list_summaries, user_id, ("active", "archived")
        )
        return [self._summary(row) for row in rows]

    async def get_roadmap(self, user_id: UUID, roadmap_id: UUID) -> RoadmapOut:
        row = await asyncio.to_thread(
            self.repository.get, roadmap_id, user_id
        )
        if row is None:
            raise NotFoundError("成长路线不存在")
        return self._serialize(row)

    async def confirm(self, user_id: UUID, roadmap_id: UUID) -> RoadmapOut:
        row = await asyncio.to_thread(
            self.repository.get, roadmap_id, user_id
        )
        if row is None:
            raise NotFoundError("成长路线不存在")
        if row["status"] != "draft":
            raise AppError(
                "ROADMAP_NOT_DRAFT",
                "只有草稿路线可以确认启用",
                status_code=409,
            )
        confirmed = await asyncio.to_thread(
            self.repository.confirm, roadmap_id, user_id
        )
        if not confirmed:
            raise AppError(
                "ROADMAP_CONFIRM_CONFLICT",
                "路线状态已变化，请刷新后重试",
                status_code=409,
            )
        return await self._get_or_404(user_id, roadmap_id)

    async def discard(self, user_id: UUID, roadmap_id: UUID) -> RoadmapSummaryOut:
        row = await asyncio.to_thread(
            self.repository.get, roadmap_id, user_id
        )
        if row is None:
            raise NotFoundError("成长路线不存在")
        if row["status"] != "draft":
            raise AppError(
                "ROADMAP_NOT_DRAFT",
                "只有草稿路线可以放弃",
                status_code=409,
            )
        discarded = await asyncio.to_thread(
            self.repository.discard, roadmap_id, user_id
        )
        if not discarded:
            raise AppError(
                "ROADMAP_DISCARD_CONFLICT",
                "路线状态已变化，请刷新后重试",
                status_code=409,
            )
        updated = await asyncio.to_thread(
            self.repository.get, roadmap_id, user_id
        )
        if updated is None:
            raise NotFoundError("成长路线不存在")
        return self._summary(updated)

    async def update_task(
        self,
        user_id: UUID,
        task_id: UUID,
        *,
        status: str,
        outcome: str | None,
    ) -> RoadmapTaskUpdateOut:
        state = await asyncio.to_thread(
            self.repository.task_state, task_id, user_id
        )
        if state is None:
            raise NotFoundError("成长任务不存在")
        if state["roadmap_status"] != "active":
            raise AppError(
                "ROADMAP_NOT_ACTIVE",
                "只有正式启用的路线可以更新任务状态",
                status_code=409,
            )
        row = await asyncio.to_thread(
            self.repository.update_task,
            task_id,
            user_id,
            status=status,
            outcome=outcome,
        )
        if row is None:
            raise AppError(
                "ROADMAP_TASK_CONFLICT",
                "任务状态更新失败，请刷新后重试",
                status_code=409,
            )
        return RoadmapTaskUpdateOut(
            task=RoadmapTaskOut.model_validate(row),
            roadmap_id=row["roadmap_id"],
            roadmap_version=row["roadmap_version"],
        )

    async def active_overview(self, user_id: UUID) -> dict[str, Any]:
        active = await asyncio.to_thread(self.repository.get_active, user_id)
        draft = await asyncio.to_thread(self.repository.get_latest_draft, user_id)
        if active is None:
            return {"roadmap": None, "has_draft": draft is not None}
        data = self._serialize(active)
        return {
            "roadmap": {
                "id": str(data.id),
                "version": data.version,
                "status": data.status,
                "title": data.title,
                "target_role": data.target_role,
                "task_total": data.task_total,
                "task_completed": data.task_completed,
                "stages": [
                    {
                        "title": stage.title,
                        "tasks": [
                            {"title": task.title, "status": task.status}
                            for task in stage.tasks
                        ],
                    }
                    for stage in data.stages
                ],
            },
            "has_draft": draft is not None,
        }

    async def _get_or_404(self, user_id: UUID, roadmap_id: UUID) -> RoadmapOut:
        row = await asyncio.to_thread(
            self.repository.get, roadmap_id, user_id
        )
        if row is None:
            raise NotFoundError("成长路线不存在")
        return self._serialize(row)

    @staticmethod
    def _serialize(row: dict[str, Any]) -> RoadmapOut:
        gap = None
        snapshot = row.get("gap_snapshot") or {}
        if snapshot:
            try:
                gap = SkillGapOut.model_validate(snapshot)
            except ValidationError:
                gap = None
        stages = [
            RoadmapStageOut.model_validate(stage)
            for stage in row.get("stages", [])
        ]
        tasks = [task for stage in stages for task in stage.tasks]
        return RoadmapOut(
            id=row["id"],
            user_id=row["user_id"],
            target_role=row["target_role"],
            status=row["status"],
            version=row["version"],
            title=row["title"],
            summary=row["summary"],
            gap=gap,
            generation_mode=row["generation_mode"],
            provider=row["provider"],
            model=row["model"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            confirmed_at=row["confirmed_at"],
            stages=stages,
            task_total=len(tasks),
            task_completed=sum(
                1 for task in tasks if task.status == "completed"
            ),
        )

    @staticmethod
    def _summary(row: dict[str, Any]) -> RoadmapSummaryOut:
        task_total = row.get("task_total")
        task_completed = row.get("task_completed")
        if task_total is None or task_completed is None:
            tasks = [
                task
                for stage in row.get("stages", [])
                for task in stage.get("tasks", [])
            ]
            task_total = len(tasks)
            task_completed = sum(
                1 for task in tasks if task.get("status") == "completed"
            )
        return RoadmapSummaryOut.model_validate(
            {
                "id": row["id"],
                "target_role": row["target_role"],
                "status": row["status"],
                "version": row["version"],
                "title": row["title"],
                "generation_mode": row["generation_mode"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "confirmed_at": row["confirmed_at"],
                "task_total": task_total,
                "task_completed": task_completed,
            }
        )


_roadmap_service: RoadmapService | None = None


def get_roadmap_service() -> RoadmapService:
    global _roadmap_service
    if _roadmap_service is None:
        _roadmap_service = RoadmapService()
    return _roadmap_service


def reset_roadmap_service() -> None:
    global _roadmap_service
    _roadmap_service = None
