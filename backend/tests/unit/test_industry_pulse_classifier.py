import pytest

from app.industry_pulse.classify import classify_article
from app.industry_pulse.sources import FeedSource

CASES = {
    "digital_tech_comms": "5G通信与数据中心建设",
    "finance_insurance": "银行保险业发布新监管政策",
    "manufacturing_industry": "智能制造工厂生产线投产",
    "energy_environment": "光伏储能与电网项目投产",
    "auto_smart_mobility": "新能源汽车与智能驾驶技术发布",
    "transport_logistics": "物流供应链与港口航运合作",
    "health_life_sciences": "医院临床药物与疫苗研发",
    "education_research": "高校科研与职业教育课程发布",
    "agriculture_food": "农业粮食与食品加工项目投产",
    "consumer_retail_services": "零售电商与消费品牌合作",
    "real_estate_construction": "房地产建筑工程项目建设",
    "culture_media_content": "影视传媒与游戏内容发布",
    "arts_design": "艺术设计展览与产品设计发布",
    "sports_industry": "体育赛事与健身产业合作",
    "tourism_hospitality_events": "旅游酒店景区项目合作",
    "enterprise_professional_services": "管理咨询与会计审计服务合作",
}


def _source(industry: str, industries: tuple[str, ...] | None = None) -> FeedSource:
    return FeedSource(
        key=f"test-{industry}",
        name=f"Test {industry}",
        industry=industry,
        feed_url="https://example.invalid/rss",
        homepage_url="https://example.invalid/",
        industries=industries if industries is not None else (industry,),
        region="CN",
    )


def _general() -> FeedSource:
    return FeedSource(
        key="general",
        name="General",
        industry="enterprise_professional_services",
        feed_url="https://example.invalid/rss",
        homepage_url="https://example.invalid/",
        industries=(),
        region="CN",
    )


@pytest.mark.parametrize("industry,title", sorted(CASES.items()))
def test_all_16_industries_have_positive_examples(industry, title):
    result = classify_article(_source(industry), title, "")
    assert result.relevance == "industry_relevant"
    assert result.primary_industry == industry
    assert industry in result.industries
    assert result.primary_industry in result.industries


@pytest.mark.parametrize(
    "title,relevance,primary,industries",
    [
        ("香港无纸证券制度实施后迎来首只新股上市", "industry_relevant", "finance_insurance", ("finance_insurance",)),
        ("长期左侧卧睡，真的会压迫损伤心脏吗？", "irrelevant", None, ()),
        ("广西龙胜县举行盘王节，展瑶家民俗", "needs_review", None, ()),
        ("日本今年1至9月出生人口同比减少0.3%", "macro_signal", None, ()),
        ("哈尔滨宾县整合冰雪温泉民俗资源 培育三大特色冰雪体验", "industry_relevant", "tourism_hospitality_events", ("tourism_hospitality_events",)),
        ("体育科技企业推出新型运动监测产品", "industry_relevant", "sports_industry", None),
        ("生成式AI设计工具进入商业设计流程", "industry_relevant", None, None),
    ],
)
def test_real_news_cases(title, relevance, primary, industries):
    result = classify_article(_general(), title, "")
    assert result.relevance == relevance
    if primary is not None:
        assert result.primary_industry == primary
    if industries is not None:
        assert result.industries == industries
    if relevance != "industry_relevant":
        assert result.primary_industry is None
        assert result.industries == ()


def test_multi_industry_requires_explicit_evidence():
    sports = classify_article(_general(), "体育科技企业推出新型运动监测产品", "")
    assert sports.primary_industry == "sports_industry"
    assert sports.primary_industry in sports.industries

    design = classify_article(_general(), "生成式AI设计工具进入商业设计流程", "")
    assert {"digital_tech_comms", "arts_design"}.issubset(set(design.industries))
    assert design.primary_industry in design.industries
    assert design.basis["rule_version"] == "industry-v2.1"
    assert design.basis["matched_terms"]


def test_general_source_never_defaults_to_enterprise_services():
    result = classify_article(_general(), "今天天气很好", "")
    assert result.relevance == "irrelevant"
    assert result.primary_industry is None
    assert result.industries == ()


def test_source_hint_alone_does_not_classify_generic_content():
    result = classify_article(_source("health_life_sciences"), "今天天气很好", "")
    assert result.relevance == "irrelevant"
    assert result.industries == ()


def test_keyword_without_industry_value_goes_to_review():
    result = classify_article(_general(), "某医院里的新装修", "")
    assert result.relevance == "needs_review"
    assert result.primary_industry is None
    assert result.industries == ()


def test_health_lecture_is_not_industry_news():
    result = classify_article(_general(), "某医院举办健康讲座", "")
    assert result.relevance == "irrelevant"
    assert result.primary_industry is None
    assert result.industries == ()


def test_ascii_token_boundaries_do_not_match_inside_words():
    result = classify_article(_general(), "Retail detail and daily operations", "")
    assert "digital_tech_comms" not in result.industries


def test_broad_words_do_not_trigger_specific_industries():
    result = classify_article(_general(), "品牌研究显示健康生活方式受到关注", "")
    assert set(result.industries).isdisjoint(
        {"consumer_retail_services", "education_research", "health_life_sciences"}
    )


def test_primary_is_always_member_of_industries():
    result = classify_article(_general(), "医院临床药物与疫苗研发项目", "")
    assert result.relevance == "industry_relevant"
    assert result.primary_industry in result.industries