from datetime import datetime, timedelta, timezone

from app.services.industry_trends_service import IndustryTrendsService


def _dt(days_ago: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


def _news(article_id: str, industry: str, source: str, days_ago: int) -> dict:
    return {
        "id": article_id,
        "title": f"{industry} news {article_id}",
        "url": f"https://example.invalid/{article_id}",
        "source_name": source,
        "observed_at": _dt(days_ago),
        "industries": [industry],
    }


def _job(
    job_id: str,
    industry: str,
    title: str,
    location: str,
    skills: list[str],
    days_ago: int,
    dataset_kind: str = "real",
) -> dict:
    return {
        "id": job_id,
        "title": title,
        "industry": industry,
        "location": location,
        "education": "本科",
        "experience": "1-3年",
        "skills": skills,
        "observed_at": _dt(days_ago),
        "dataset_kind": dataset_kind,
        "source_name": "test-source",
    }


class FakeRepository:
    def __init__(self, news: list[dict], jobs: list[dict]) -> None:
        self.news = news
        self.jobs = jobs

    def news_rows(self, since):
        return [row for row in self.news if row["observed_at"] >= since]

    def job_rows(self, since):
        return [row for row in self.jobs if row["observed_at"] >= since]


def _jobs_for_digital(
    count: int = 12, dataset_kind: str = "real"
) -> list[dict]:
    jobs = []
    for index in range(count):
        jobs.append(
            _job(
                f"digital-{index}",
                "互联网",
                "数据分析师",
                "上海",
                ["Python", "SQL", "Tableau"],
                days_ago=150 - index * 10,
                dataset_kind=dataset_kind,
            )
        )
    return jobs


def _news_for_digital() -> list[dict]:
    return [
        _news("d1", "digital_tech_comms", "source-a", 120),
        _news("d2", "digital_tech_comms", "source-b", 60),
        _news("d3", "digital_tech_comms", "source-c", 20),
    ]


def test_overall_combines_market_and_cross_source_news():
    jobs = _jobs_for_digital()
    jobs.extend(
        [
            _job("consumer-1", "新零售", "数据分析师", "深圳", ["SQL", "Excel"], 90),
            _job("consumer-2", "新零售", "数据分析师", "成都", ["SQL", "Excel"], 60),
            _job("consumer-3", "新零售", "前端工程师", "上海", ["Vue"], 30),
            _job("consumer-4", "新零售", "前端工程师", "上海", ["Vue"], 20),
            _job("consumer-5", "新零售", "算法工程师", "北京", ["Python"], 10),
            _job("consumer-6", "新零售", "后端工程师", "杭州", ["Java"], 5),
        ]
    )
    repo = FakeRepository(
        _news_for_digital()
        + [
            _news("c1", "consumer_retail_services", "source-a", 70),
            _news("c2", "consumer_retail_services", "source-b", 10),
        ],
        jobs,
    )
    result = IndustryTrendsService(repo).overall(months=24)
    ids = {item.industry_id for item in result.items}
    assert {"digital_tech_comms", "consumer_retail_services"} <= ids
    digital = next(item for item in result.items if item.industry_id == "digital_tech_comms")
    assert digital.job_count == 12
    assert digital.news_count == 3
    assert digital.news_source_count == 3
    assert digital.evidence_level in {"strong", "medium"}
    assert digital.direction in {"rising", "stable", "cooling", "unclear"}
    assert any(item.industry_id == "health_life_sciences" for item in result.insufficient_industries)


def test_duplicate_job_rows_do_not_inflate_demand():
    jobs = _jobs_for_digital(6)
    jobs.append(dict(jobs[0]))
    result = IndustryTrendsService(
        FakeRepository(_news_for_digital(), jobs)
    ).overall(months=24)
    digital = next(item for item in result.items if item.industry_id == "digital_tech_comms")
    assert digital.job_count == 6


def test_real_jobs_take_precedence_over_synthetic_for_same_industry():
    real_jobs = _jobs_for_digital(6)
    synthetic_jobs = [
        dict(job, id=f"synthetic-{job['id']}", dataset_kind="synthetic")
        for job in _jobs_for_digital(12)
    ]
    result = IndustryTrendsService(
        FakeRepository(_news_for_digital(), real_jobs + synthetic_jobs)
    ).overall(months=24)
    digital = next(
        item for item in result.items if item.industry_id == "digital_tech_comms"
    )
    assert digital.job_count == 6
    assert digital.evidence.synthetic is False
    assert digital.evidence.dataset_kinds == ["real"]
    assert any("优先使用真实数据" in warning for warning in result.warnings)


def test_synthetic_only_remains_explicit_demo_evidence():
    result = IndustryTrendsService(
        FakeRepository(
            _news_for_digital(),
            _jobs_for_digital(12, dataset_kind="synthetic"),
        )
    ).overall(months=24)
    digital = next(
        item for item in result.items if item.industry_id == "digital_tech_comms"
    )
    assert digital.job_count == 12
    assert digital.evidence.synthetic is True
    assert digital.evidence.dataset_kinds == ["synthetic"]
    assert any("synthetic" in gap for gap in digital.data_gaps)
    assert any("synthetic" in warning for warning in result.warnings)


def test_synthetic_fills_only_industries_without_real_samples():
    real_jobs = [
        _job("consumer-1", "新零售", "数据分析师", "上海", ["SQL"], 30),
        _job("consumer-2", "新零售", "数据分析师", "上海", ["SQL"], 60),
        _job("consumer-3", "新零售", "数据分析师", "上海", ["SQL"], 90),
        _job("consumer-4", "新零售", "数据分析师", "上海", ["SQL"], 120),
        _job("consumer-5", "新零售", "数据分析师", "上海", ["SQL"], 150),
    ]
    synthetic_jobs = _jobs_for_digital(12, dataset_kind="synthetic")
    news = _news_for_digital() + [
        _news("c1", "consumer_retail_services", "source-a", 70),
        _news("c2", "consumer_retail_services", "source-b", 10),
    ]
    result = IndustryTrendsService(
        FakeRepository(news, real_jobs + synthetic_jobs)
    ).overall(months=24)
    digital = next(
        item for item in result.items if item.industry_id == "digital_tech_comms"
    )
    consumer = next(
        item
        for item in result.items
        if item.industry_id == "consumer_retail_services"
    )
    assert digital.job_count == 12
    assert digital.evidence.synthetic is True
    assert consumer.job_count == 5
    assert consumer.evidence.synthetic is False
    assert any("优先使用真实数据" in warning for warning in result.warnings)


def test_short_news_only_span_is_insufficient():
    news = [
        _news("short-1", "finance_insurance", "a", 3),
        _news("short-2", "finance_insurance", "b", 1),
    ]
    result = IndustryTrendsService(FakeRepository(news, [])).overall(months=24)
    assert all(item.industry_id != "finance_insurance" for item in result.items)
    gap = next(
        item for item in result.insufficient_industries
        if item.industry_id == "finance_insurance"
    )
    assert "新闻时间跨度不足 30 天" in gap.reason


def test_personalized_trend_uses_profile_and_does_not_fabricate_skills():
    jobs = _jobs_for_digital(12)
    repo = FakeRepository(_news_for_digital(), jobs)
    service = IndustryTrendsService(repo)
    profile = {
        "basic": {"location": "上海", "education_level": "本科"},
        "goals": {"target_role": "数据分析师", "target_industry": "互联网"},
        "skills": [
            {"name": "Python", "evidence": "课程项目", "verification": "confirmed"},
            {"name": "SQL", "evidence": "", "verification": "confirmed"},
        ],
    }
    result = service.personal(profile, months=24)
    assert result.profile_sufficient is True
    assert result.target_industry_label == "数字科技与通信"
    digital = next(
        item for item in result.items if item.trend.industry_id == "digital_tech_comms"
    )
    assert digital.relevance_confidence == "high"
    assert set(digital.matched_skills) == {"Python", "SQL"}
    assert "Tableau" in digital.missing_skills
    assert digital.roadmap_suggestion.requires_confirmation is True
    assert digital.roadmap_suggestion.confirm_url == "/roadmap"
    assert any("未记录" in gap.evidence_note or "不等于" in gap.evidence_note for gap in digital.skill_gaps)
    assert not any("已具备" in risk for risk in digital.risks)


def test_different_profiles_receive_different_personal_results():
    jobs = _jobs_for_digital(12)
    service = IndustryTrendsService(FakeRepository(_news_for_digital(), jobs))
    profile_analyst = {
        "basic": {"location": "上海"},
        "goals": {"target_role": "数据分析师", "target_industry": "互联网"},
        "skills": [{"name": "Python", "evidence": "项目", "verification": "confirmed"}],
    }
    profile_nurse = {
        "basic": {"location": "北京"},
        "goals": {"target_role": "护士", "target_industry": "医疗健康"},
        "skills": [{"name": "护理", "evidence": "实习", "verification": "confirmed"}],
    }
    analyst = service.personal(profile_analyst, months=24)
    nurse = service.personal(profile_nurse, months=24)
    assert analyst.items
    assert nurse.items == []
    assert nurse.insufficient_reason
    assert analyst.target_industry_label != nurse.target_industry_label


def test_missing_profile_does_not_generate_matches():
    result = IndustryTrendsService(FakeRepository([], [])).personal(
        {"basic": {}, "goals": {}, "skills": []}, months=24
    )
    assert result.profile_sufficient is False
    assert result.items == []
    assert "目标岗位" in result.profile_missing
    assert "不会凭空推断" in result.insufficient_reason


def test_personal_filter_returns_no_fake_industry():
    service = IndustryTrendsService(
        FakeRepository(_news_for_digital(), _jobs_for_digital())
    )
    result = service.personal(
        {"goals": {"target_role": "数据分析师", "target_industry": "互联网"}},
        industry="arts_design",
        months=24,
    )
    assert result.items == []
    assert result.insufficient_reason
