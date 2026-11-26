from typing import Any, Literal

from app.core.errors import AppError
from app.db.market_repositories import MarketRepository, market_repository
from app.schemas.market import (
    DistributionOut,
    MarketCountItem,
    MarketImportRequest,
    MarketImportResult,
    MarketMeta,
    MarketOverviewOut,
    MarketRoleSkill,
    MarketSourceOut,
    RolesOut,
    SkillDemandItem,
    SkillDemandOut,
    SourcesOut,
    TrendOut,
    TrendPoint,
)
from app.services.market_cleaner import clean_job

MIN_SAMPLE = 5


class MarketService:
    def __init__(self, repository: MarketRepository | None = None) -> None:
        self.repository = repository or market_repository

    def import_jobs(self, request: MarketImportRequest) -> MarketImportResult:
        source = self.repository.upsert_source(
            name=request.source.name,
            source_type=request.source.source_type,
            dataset_kind=request.source.dataset_kind,
            license_note=request.source.license_note,
            base_url=request.source.base_url,
        )
        batch = self.repository.create_batch(source["id"], len(request.jobs))
        imported = duplicates = failed = 0
        try:
            for item in request.jobs:
                try:
                    clean = clean_job(item)
                    duplicate_of = self.repository.find_duplicate(clean["dedupe_hash"])
                    if duplicate_of:
                        self.repository.insert_job(
                            source_id=source["id"],
                            batch_id=batch["id"],
                            clean=clean,
                            status="duplicate",
                            error_message="重复岗位",
                            duplicate_of=duplicate_of,
                        )
                        duplicates += 1
                    else:
                        self.repository.insert_job(
                            source_id=source["id"],
                            batch_id=batch["id"],
                            clean=clean,
                        )
                        imported += 1
                except Exception:
                    failed += 1
            self.repository.finish_batch(
                batch["id"],
                status="completed",
                imported=imported,
                duplicates=duplicates,
                failed=failed,
            )
        except Exception as exc:
            self.repository.finish_batch(
                batch["id"],
                status="failed",
                imported=imported,
                duplicates=duplicates,
                failed=failed,
                error_message=str(exc)[:500],
            )
            raise AppError("MARKET_IMPORT_FAILED", "市场数据导入失败", status_code=500) from exc
        return MarketImportResult(
            batch_id=str(batch["id"]),
            source=MarketSourceOut.model_validate(source),
            total=len(request.jobs),
            imported=imported,
            duplicates=duplicates,
            failed=failed,
        )

    def overview(
        self,
        *,
        role: str | None = None,
        location: str | None = None,
        dataset_kind: Literal["all", "real", "synthetic"] = "all",
        industry: str | None = None,
        months: int | None = None,
    ) -> MarketOverviewOut:
        effective_kind, synthetic_excluded = self._resolve_dataset_kind(
            role, location, dataset_kind, industry, months
        )
        meta = self._meta(
            role,
            location,
            effective_kind,
            industry,
            months,
            synthetic_excluded=synthetic_excluded,
        )
        aggregate = self.repository.aggregate(
            role, location, effective_kind, industry=industry, months=months
        )
        total = aggregate["total_jobs"]
        top_roles = self._counts(
            self.repository.top_counts(
                "title",
                role,
                location,
                effective_kind,
                8,
                industry=industry,
                months=months,
            ),
            total,
        )
        top_skills = self._skills(
            self.repository.top_skills(
                role,
                location,
                effective_kind,
                12,
                industry=industry,
                months=months,
            ),
            total,
        )
        role_names = [item.name for item in top_roles[:5]]
        role_skills_map = self.repository.role_skills(
            role_names,
            location,
            effective_kind,
            industry=industry,
            months=months,
        )
        role_skills = [
            MarketRoleSkill(
                role=role_name,
                skills=self._skills(items, self.repository.aggregate(
                    role_name,
                    location,
                    effective_kind,
                    industry=industry,
                    months=months,
                )["total_jobs"]),
            )
            for role_name, items in role_skills_map.items()
        ]
        return MarketOverviewOut(
            total_jobs=total,
            total_companies=aggregate["total_companies"],
            total_roles=aggregate["total_roles"],
            total_locations=aggregate["total_locations"],
            top_roles=top_roles,
            top_skills=top_skills,
            role_skills=role_skills,
            meta=meta,
        )

    def skills(
        self,
        *,
        role: str | None = None,
        location: str | None = None,
        dataset_kind: Literal["all", "real", "synthetic"] = "all",
        limit: int = 20,
        industry: str | None = None,
        months: int | None = None,
    ) -> SkillDemandOut:
        effective_kind, synthetic_excluded = self._resolve_dataset_kind(
            role, location, dataset_kind, industry, months
        )
        meta = self._meta(
            role,
            location,
            effective_kind,
            industry,
            months,
            synthetic_excluded=synthetic_excluded,
        )
        aggregate = self.repository.aggregate(
            role, location, effective_kind, industry=industry, months=months
        )
        return SkillDemandOut(
            items=self._skills(
                self.repository.top_skills(
                    role,
                    location,
                    effective_kind,
                    limit,
                    industry=industry,
                    months=months,
                ),
                aggregate["total_jobs"],
            ),
            meta=meta,
        )

    def distribution(
        self,
        dimension: Literal["education", "experience", "location"],
        *,
        role: str | None = None,
        location: str | None = None,
        dataset_kind: Literal["all", "real", "synthetic"] = "all",
        industry: str | None = None,
        months: int | None = None,
    ) -> DistributionOut:
        effective_kind, synthetic_excluded = self._resolve_dataset_kind(
            role, location, dataset_kind, industry, months
        )
        meta = self._meta(
            role,
            location,
            effective_kind,
            industry,
            months,
            synthetic_excluded=synthetic_excluded,
        )
        aggregate = self.repository.aggregate(
            role, location, effective_kind, industry=industry, months=months
        )
        items = self._counts(
            self.repository.distribution(
                dimension,
                role,
                location,
                effective_kind,
                industry=industry,
                months=months,
            ),
            aggregate["total_jobs"],
        )
        return DistributionOut(dimension=dimension, items=items, meta=meta)

    def trends(
        self,
        *,
        role: str | None = None,
        location: str | None = None,
        dataset_kind: Literal["all", "real", "synthetic"] = "all",
        months: int = 6,
        industry: str | None = None,
    ) -> TrendOut:
        effective_kind, synthetic_excluded = self._resolve_dataset_kind(
            role, location, dataset_kind, industry, months
        )
        meta = self._meta(
            role,
            location,
            effective_kind,
            industry,
            months,
            synthetic_excluded=synthetic_excluded,
        )
        points = self.repository.trends(
            role, location, effective_kind, months, industry=industry
        )
        insufficient = meta.sample_size < MIN_SAMPLE or len(points) < 3
        return TrendOut(
            points=[] if insufficient else [TrendPoint(**point) for point in points],
            insufficient_data=insufficient,
            meta=meta,
        )

    def roles(
        self,
        dataset_kind: Literal["all", "real", "synthetic"] = "all",
        *,
        industry: str | None = None,
        months: int | None = None,
    ) -> RolesOut:
        effective_kind, synthetic_excluded = self._resolve_dataset_kind(
            None, None, dataset_kind, industry, months
        )
        meta = self._meta(
            None,
            None,
            effective_kind,
            industry,
            months,
            synthetic_excluded=synthetic_excluded,
        )
        return RolesOut(
            items=self.repository.roles(
                effective_kind, industry=industry, months=months
            ),
            meta=meta,
        )

    def sources(self) -> SourcesOut:
        return SourcesOut(
            items=[
                MarketSourceOut.model_validate(source)
                for source in self.repository.sources()
            ]
        )

    def get_market_insights(
        self,
        role: str | None = None,
        location: str | None = None,
        industry: str | None = None,
        months: int | None = None,
    ) -> dict[str, Any]:
        overview = self.overview(
            role=role, location=location, industry=industry, months=months
        )
        return overview.model_dump(mode="json")

    def get_skill_demand(
        self, role: str | None = None, limit: int = 12
    ) -> dict[str, Any]:
        return self.skills(role=role, limit=limit).model_dump(mode="json")

    def get_career_market_requirements(self, role: str | None = None) -> dict[str, Any]:
        overview = self.overview(role=role)
        education = self.distribution("education", role=role)
        experience = self.distribution("experience", role=role)
        return {
            "role": role,
            "overview": overview.model_dump(mode="json"),
            "education": education.model_dump(mode="json"),
            "experience": experience.model_dump(mode="json"),
        }

    def _resolve_dataset_kind(
        self,
        role: str | None,
        location: str | None,
        dataset_kind: str,
        industry: str | None,
        months: int | None,
    ) -> tuple[str, bool]:
        """Resolve `all` to a clean real-first dataset.

        Real and synthetic rows must never be summed into one market sample.
        If any matching real rows exist, use real only and report that the
        synthetic demo rows were excluded. If no real rows exist, keep the
        existing synthetic demo path.
        """
        if dataset_kind in {"real", "synthetic"}:
            return dataset_kind, False
        real_count = self.repository.aggregate(
            role, location, "real", industry=industry, months=months
        )["total_jobs"]
        if real_count:
            synthetic_count = self.repository.aggregate(
                role, location, "synthetic", industry=industry, months=months
            )["total_jobs"]
            return "real", synthetic_count > 0
        return "synthetic", False

    def _meta(
        self,
        role: str | None,
        location: str | None,
        dataset_kind: str,
        industry: str | None = None,
        months: int | None = None,
        *,
        synthetic_excluded: bool = False,
    ) -> MarketMeta:
        aggregate = self.repository.aggregate(
            role, location, dataset_kind, industry=industry, months=months
        )
        sources = self.repository.matching_sources(
            role, location, dataset_kind, industry=industry, months=months
        )
        sample_size = aggregate["total_jobs"]
        kinds = sorted({source["dataset_kind"] for source in sources})
        warnings = []
        if sample_size == 0:
            warnings.append("暂无匹配市场数据")
        elif sample_size < MIN_SAMPLE:
            warnings.append("样本量不足 5 条，不得视为全国市场结论")
        if synthetic_excluded:
            warnings.append(
                "已优先使用真实岗位数据；synthetic 演示数据未混入真实统计。"
            )
        if "synthetic" in kinds:
            warnings.append("包含合成测试数据，仅用于链路验证，不代表真实招聘市场")
        return MarketMeta(
            sample_size=sample_size,
            sample_sufficient=sample_size >= MIN_SAMPLE,
            period_start=aggregate["period_start"],
            period_end=aggregate["period_end"],
            updated_at=aggregate["updated_at"],
            dataset_kinds=kinds,
            sources=[MarketSourceOut.model_validate(source) for source in sources],
            warnings=warnings,
        )

    @staticmethod
    def _counts(items: list[dict[str, Any]], total: int) -> list[MarketCountItem]:
        return [
            MarketCountItem(
                name=str(item["name"]),
                count=item["count"],
                share=round(item["count"] / total, 4) if total else 0.0,
            )
            for item in items
        ]

    @staticmethod
    def _skills(items: list[dict[str, Any]], total: int) -> list[SkillDemandItem]:
        return [
            SkillDemandItem(
                skill=str(item["name"]),
                count=item["count"],
                share=round(item["count"] / total, 4) if total else 0.0,
                rank=index,
            )
            for index, item in enumerate(items, start=1)
        ]


_market_service: MarketService | None = None


def get_market_service() -> MarketService:
    global _market_service
    if _market_service is None:
        _market_service = MarketService()
    return _market_service


def reset_market_service() -> None:
    global _market_service
    _market_service = None
