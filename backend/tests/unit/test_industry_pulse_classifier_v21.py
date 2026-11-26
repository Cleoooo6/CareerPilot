import pytest

from app.industry_pulse.classify import classify_article
from app.industry_pulse.sources import FeedSource


def _source(industries: tuple[str, ...] = ()) -> FeedSource:
    return FeedSource(
        key="v21-test",
        name="V2.1 test",
        industry="enterprise_professional_services",
        feed_url="https://example.invalid/rss",
        homepage_url="https://example.invalid/",
        industries=industries,
    )


POSITIVE_CASES = [
    ("香港无纸证券制度实施后迎来首只新股上市", "finance_insurance", {"finance_insurance"}),
    ("文心 5.5 Flash Preview正式开源，采用 Apache 2.0 协议", "digital_tech_comms", {"digital_tech_comms"}),
    ("18.79 万元起！比亚迪唐 EV 正式上市，砍掉七座换来 850km 续航", "auto_smart_mobility", {"auto_smart_mobility"}),
    ("SEC Charges Indianapolis-Based Backward Hat Capital With $560 Million Offering Fraud", "finance_insurance", {"finance_insurance"}),
    ("蚂蚁开源医疗健康预测模型，根据睡眠数据可预测未来六年150种疾病风险", "health_life_sciences", {"health_life_sciences", "digital_tech_comms"}),
    ("Data centers are getting their own natural gas power plants", "energy_environment", {"energy_environment", "digital_tech_comms"}),
    ("AR sports attract global players in Shanghai", "sports_industry", {"sports_industry", "digital_tech_comms"}),
    ("黄仁勋重返英伟达！董事会全票通过，盘前大涨 30%", "digital_tech_comms", {"digital_tech_comms"}),
    ("Black Friday, Cyber Monday shopping projected to slip", "consumer_retail_services", {"consumer_retail_services"}),
    ("驭电飞驰，向车而行 | 光跃投资走进2026中国大学生方程式大赛合肥赛场", "auto_smart_mobility", {"auto_smart_mobility", "education_research"}),
    ("2026航空航天产业生态大会在成都开幕", "manufacturing_industry", {"manufacturing_industry"}),
    ("民航首个“一网统管”数字化转型方案在海南机场试点落地", "transport_logistics", {"transport_logistics", "digital_tech_comms"}),
    ("华金证券接入千问办公，73个技能重塑投研风控全流程", "finance_insurance", {"finance_insurance", "digital_tech_comms"}),
    ("哈尔滨宾县整合冰雪温泉民俗资源 培育三大特色冰雪体验", "tourism_hospitality_events", {"tourism_hospitality_events"}),
    ("体育科技企业推出新型运动监测产品", "sports_industry", {"sports_industry", "digital_tech_comms"}),
    ("生成式AI设计工具进入商业设计流程", "arts_design", {"arts_design", "digital_tech_comms"}),
    ("高海拔跨域5G远程机器人肾癌根治手术完成 辽藏协同助力高原医疗", "health_life_sciences", {"health_life_sciences", "digital_tech_comms", "manufacturing_industry"}),
    ("今年前十月广州实物商品网上零售额超3100亿元", "consumer_retail_services", {"consumer_retail_services"}),
    ("第十届“艺术长沙”举行 尹朝阳、马轲双个展亮相美仑美术馆", "arts_design", {"arts_design"}),
    ("2026年海丝国际文旅节非遗体验与展演系列活动将启 全域联动启新篇", "culture_media_content", {"culture_media_content", "tourism_hospitality_events"}),
    ("珠肇高铁江机段5标无砟轨道施工转入铺轨阶段", "transport_logistics", {"transport_logistics"}),
    ("菲律宾维萨亚斯电网再拉响红色警报 电力供应持续趋紧", "energy_environment", {"energy_environment"}),
    ("艾为电子落子电源芯片业务，钰泰半导体八年资本路迎新局 | 并购一线", "manufacturing_industry", {"manufacturing_industry"}),
    ("工程设计项目发布，建筑方案进入施工图阶段", "real_estate_construction", {"real_estate_construction"}),
]


@pytest.mark.parametrize("title,primary,industries", POSITIVE_CASES)
def test_v21_positive_recall_and_primary(title, primary, industries):
    result = classify_article(_source(), title, "")
    assert result.relevance == "industry_relevant"
    assert result.primary_industry == primary
    assert industries.issubset(set(result.industries))
    assert result.primary_industry in result.industries
    assert len(result.industries) <= 3


NEGATIVE_CASES = [
    "长期左侧卧睡，真的会压迫损伤心脏吗？",
    "奖助学金陆续到账 学生需提防这五种诈骗套路",
    "为了明年少些“毛毛虫” 北京大学生冬季忙挖蛹",
    "伊媒：伊朗法院已裁定，美国须支付2900亿美元赔偿金",
    "中新健康｜海绵洗碗磨损1克释放650万个微塑料？论文作者回应、院士发声",
    "印尼糖果厂火灾已致26人死亡 警方展开刑事调查",
    "特朗普停下脚步鼓掌，普京听到熟悉的歌：深圳APEC晚宴乐章曲目大有深意",
    "一杯奶茶一束光！唐山这家特殊小店，藏着8名残障青年的甜蜜事业",
    "大学课堂评价需要什么样的标尺？——从高校课堂“抬头率”说起",
    "某医院举办健康讲座",
]


@pytest.mark.parametrize("title", NEGATIVE_CASES)
def test_v21_negative_filters_do_not_enter_industry(title):
    result = classify_article(_source(), title, "")
    assert result.relevance == "irrelevant"
    assert result.primary_industry is None
    assert result.industries == ()


REVIEW_CASES = [
    "广西龙胜县举行盘王节 展瑶家民俗",
    "九三学社全国传统教育基地九广合作陈列中心揭牌仪式举行",
    "早报｜黄仁勋回归，英伟达股价一夜暴涨31%/《复仇者联盟5》发布终极预告/3399起，荣耀700系列发布",
    "华为星芒 O1 Pro 评测：一台真正为 AI 而生的鸿蒙手机",
    "报名从速｜来MEET2027！听AI前沿实践者交出“判断”",
    "超越试点：销售管理者的 AI 转型行动指南",
    "某医院里的新装修",
]


@pytest.mark.parametrize("title", REVIEW_CASES)
def test_v21_uncertain_goes_to_review_without_industry(title):
    result = classify_article(_source(), title, "")
    assert result.relevance == "needs_review"
    assert result.primary_industry is None
    assert result.industries == ()


MACRO_CASES = [
    "日本今年1至9月出生人口同比减少0.3%",
    "韩国30至39岁人群未婚比例升至53.1%",
    "今年前10个月新疆进出口值同比增超13%",
    "老挝正式退出联合国最不发达国家行列",
]


@pytest.mark.parametrize("title", MACRO_CASES)
def test_v21_macro_signals_are_not_forced_into_industry(title):
    result = classify_article(_source(), title, "")
    assert result.relevance == "macro_signal"
    assert result.primary_industry is None
    assert result.industries == ()


def test_v21_source_hint_never_creates_industry_or_relevance():
    generic = classify_article(_source(("health_life_sciences",)), "今天天气很好", "")
    assert generic.relevance == "irrelevant"
    assert generic.industries == ()

    phone = classify_article(
        _source(("health_life_sciences",)), "苹果发布新款手机", ""
    )
    assert phone.relevance == "industry_relevant"
    assert "health_life_sciences" not in phone.industries
    assert "digital_tech_comms" in phone.industries


def test_v21_boundary_aerospace_manufacturing_is_not_civil_aviation():
    result = classify_article(_source(), "L-15E教练机完成首次出口交付", "")
    assert result.relevance == "industry_relevant"
    assert result.primary_industry == "manufacturing_industry"
    assert "transport_logistics" not in result.industries


def test_v21_boundary_civil_aviation_is_not_manufacturing():
    result = classify_article(_source(), "民航机场航班量创新高", "")
    assert result.relevance == "industry_relevant"
    assert result.primary_industry == "transport_logistics"
    assert "manufacturing_industry" not in result.industries


def test_v21_boundary_auto_is_not_forced_into_logistics():
    result = classify_article(_source(), "新能源汽车整车销量发布", "")
    assert result.relevance == "industry_relevant"
    assert "auto_smart_mobility" in result.industries
    assert "transport_logistics" not in result.industries


def test_v21_boundary_engineering_design_is_not_art():
    result = classify_article(_source(), "建筑设计施工图完成审查", "")
    assert result.relevance == "industry_relevant"
    assert "real_estate_construction" in result.industries
    assert "arts_design" not in result.industries


def test_v21_ai_health_and_ai_finance_keep_two_industries():
    health = classify_article(_source(), "AI医疗辅助诊断系统进入医院临床", "")
    assert health.relevance == "industry_relevant"
    assert {"health_life_sciences", "digital_tech_comms"}.issubset(set(health.industries))

    finance = classify_article(_source(), "AI金融智能风控系统接入证券投研", "")
    assert finance.relevance == "industry_relevant"
    assert {"finance_insurance", "digital_tech_comms"}.issubset(set(finance.industries))


def test_v21_no_default_enterprise_fallback():
    result = classify_article(_source(), "今天天气很好", "")
    assert result.primary_industry is None
    assert "enterprise_professional_services" not in result.industries


def test_v21_basis_is_auditable_and_title_only():
    result = classify_article(_source(), "比亚迪唐 EV 正式上市", "")
    assert result.basis["rule_version"] == "industry-v2.1"
    assert result.basis["title_terms"]
    assert result.basis["entity_hits"]
    assert result.basis["strong_signals"]

@pytest.mark.parametrize(
    "title",
    [
        "银行",
        "世卫组织宣布向古巴提供200万美元医疗援助",
        "哥伦比亚旅游城市发生人质劫持事件",
    ],
)
def test_v21_low_confidence_is_not_forced_into_industry(title):
    result = classify_article(_source(), title, "")
    assert result.relevance == "needs_review"
    assert result.primary_industry is None
    assert result.industries == ()
    assert result.confidence == "low"


def test_v21_body_only_entity_mentions_cannot_create_industry_labels():
    result = classify_article(
        _source(),
        "外籍航天员首次进入中国空间站",
        "相关企业提到阿里与东风。",
    )
    assert result.relevance != "industry_relevant"
    assert result.industries == ()


def test_v21_it_diagnostics_boundary_suppresses_health_label():
    result = classify_article(
        _source(),
        "谷歌开源环境质量智能体 AQuA，用于诊断生产环境 AI 智能体故障",
        "",
    )
    assert result.relevance == "industry_relevant"
    assert "digital_tech_comms" in result.industries
    assert "health_life_sciences" not in result.industries


def test_v21_broad_legal_and_advertising_terms_do_not_add_enterprise_label():
    lawsuit = classify_article(
        _source(("enterprise_professional_services",)),
        "Fox TV fired news host with facial disability because viewers mocked her appearance, lawsuit alleges",
        "",
    )
    assert "enterprise_professional_services" not in lawsuit.industries

    advertising = classify_article(
        _source(),
        "WebMD Ignite brings OpenAI's ChatGPT to platform for healthcare advertising",
        "",
    )
    assert "enterprise_professional_services" not in advertising.industries
    assert "health_life_sciences" in advertising.industries


def test_v21_regulatory_audit_trail_is_not_professional_services():
    result = classify_article(
        _source(),
        "SEC Issues Proposal to Restructure the Consolidated Audit Trail",
        "",
    )
    assert "finance_insurance" in result.industries
    assert "enterprise_professional_services" not in result.industries


def test_v21_secondary_entity_only_allowed_for_explicit_product():
    netflix = classify_article(
        _source(),
        "Netflix 基于运维数据打造知识图谱，实现 AI 可观测性",
        "",
    )
    assert "digital_tech_comms" in netflix.industries
    assert "culture_media_content" not in netflix.industries

    qwen = classify_article(
        _source(),
        "华金证券接入千问办公，73个技能重塑投研风控全流程",
        "",
    )
    assert {"finance_insurance", "digital_tech_comms"} <= set(qwen.industries)
