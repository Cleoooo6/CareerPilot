from dataclasses import dataclass

RSS_LICENSE_NOTE = (
    "公开 RSS 来源；默认仅保存标题、来源、发布时间、原文链接，"
    "不保存正文摘要；保留来源署名和原文链接。"
)

CONTENT_POLICIES = ("feed_excerpt", "metadata_only", "blocked")


@dataclass(frozen=True)
class FeedSource:
    key: str
    name: str
    industry: str
    feed_url: str
    homepage_url: str
    industries: tuple[str, ...] = ()
    region: str = "CN"
    default_timezone: str = "UTC"
    # Some publishers label Beijing wall-clock as GMT in their RSS. Only set
    # this when the source has been verified against its article page metadata.
    force_timezone: str = ""
    content_policy: str = "metadata_only"
    max_items: int = 20
    license_note: str = RSS_LICENSE_NOTE
    enabled: bool = True
    blocked_reason: str = ""


FEED_SOURCES: tuple[FeedSource, ...] = (
    # China-first sources. Comprehensive feeds keep industries=() and must not
    # imply a default industry for their articles.
    FeedSource(
        key="chinanews-scroll",
        name="中国新闻网·滚动",
        industry="enterprise_professional_services",
        feed_url="https://www.chinanews.com.cn/rss/scroll-news.xml",
        homepage_url="https://www.chinanews.com.cn/",
        industries=(),
        region="CN",
    ),
    FeedSource(
        key="chinanews-china",
        name="中国新闻网·国内",
        industry="enterprise_professional_services",
        feed_url="https://www.chinanews.com.cn/rss/china.xml",
        homepage_url="https://www.chinanews.com.cn/",
        industries=(),
        region="CN",
    ),
    FeedSource(
        key="chinanews-society",
        name="中国新闻网·社会",
        industry="enterprise_professional_services",
        feed_url="https://www.chinanews.com.cn/rss/society.xml",
        homepage_url="https://www.chinanews.com.cn/",
        industries=(),
        region="CN",
    ),
    FeedSource(
        key="chinanews-finance",
        name="中国新闻网·财经",
        industry="finance_insurance",
        feed_url="https://www.chinanews.com.cn/rss/finance.xml",
        homepage_url="https://www.chinanews.com.cn/",
        industries=("finance_insurance",),
        region="CN",
    ),
    FeedSource(
        key="chinanews-culture",
        name="中国新闻网·文化",
        industry="culture_media_content",
        feed_url="https://www.chinanews.com.cn/rss/culture.xml",
        homepage_url="https://www.chinanews.com.cn/",
        industries=("culture_media_content",),
        region="CN",
    ),
    FeedSource(
        key="chinanews-health",
        name="中国新闻网·健康",
        industry="health_life_sciences",
        feed_url="https://www.chinanews.com.cn/rss/health.xml",
        homepage_url="https://www.chinanews.com.cn/",
        industries=("health_life_sciences",),
        region="CN",
    ),
    FeedSource(
        key="chinanews-edu",
        name="中国新闻网·教育",
        industry="education_research",
        feed_url="https://www.chinanews.com.cn/rss/edu.xml",
        homepage_url="https://www.chinanews.com.cn/",
        industries=("education_research",),
        region="CN",
    ),
    FeedSource(
        key="chinanews-world",
        name="中国新闻网·国际",
        industry="enterprise_professional_services",
        feed_url="https://www.chinanews.com.cn/rss/world.xml",
        homepage_url="https://www.chinanews.com.cn/",
        industries=(),
        region="CN",
    ),
    FeedSource(
        key="qbitai",
        name="量子位",
        industry="digital_tech_comms",
        feed_url="https://www.qbitai.com/feed",
        homepage_url="https://www.qbitai.com/",
        industries=("digital_tech_comms",),
        region="CN",
    ),
    FeedSource(
        key="infoq-cn",
        name="InfoQ 中文",
        industry="digital_tech_comms",
        feed_url="https://www.infoq.cn/feed",
        homepage_url="https://www.infoq.cn/",
        industries=("digital_tech_comms",),
        region="CN",
        # InfoQ CN labels Beijing wall-clock as GMT in its RSS. Verified
        # against article publish_time (e.g. 2026-11-26 15:35 GMT in RSS =
        # 07:35 UTC in page metadata).
        default_timezone="Asia/Shanghai",
        force_timezone="Asia/Shanghai",
    ),
    FeedSource(
        key="tmtpost",
        name="钛媒体",
        industry="digital_tech_comms",
        feed_url="https://www.tmtpost.com/rss",
        homepage_url="https://www.tmtpost.com/",
        industries=("digital_tech_comms", "consumer_retail_services"),
        region="CN",
    ),
    FeedSource(
        key="ifanr",
        name="爱范儿",
        industry="consumer_retail_services",
        feed_url="https://www.ifanr.com/feed",
        homepage_url="https://www.ifanr.com/",
        industries=("consumer_retail_services", "digital_tech_comms"),
        region="CN",
    ),
    FeedSource(
        key="leiphone",
        name="雷锋网",
        industry="digital_tech_comms",
        feed_url="https://www.leiphone.com/feed",
        homepage_url="https://www.leiphone.com/",
        industries=("digital_tech_comms",),
        region="CN",
    ),
    FeedSource(
        key="sspai",
        name="少数派",
        industry="consumer_retail_services",
        feed_url="https://sspai.com/feed",
        homepage_url="https://sspai.com/",
        industries=("consumer_retail_services", "digital_tech_comms"),
        region="CN",
    ),
    # International supplementary sources, capped at 2 items per feed.
    FeedSource(
        key="techcrunch",
        name="TechCrunch",
        industry="digital_tech_comms",
        feed_url="https://techcrunch.com/feed/",
        homepage_url="https://techcrunch.com/",
        industries=("digital_tech_comms",),
        region="INTL",
        max_items=2,
    ),
    FeedSource(
        key="the-verge",
        name="The Verge",
        industry="digital_tech_comms",
        feed_url="https://www.theverge.com/rss/index.xml",
        homepage_url="https://www.theverge.com/",
        industries=("digital_tech_comms", "consumer_retail_services"),
        region="INTL",
        max_items=2,
    ),
    FeedSource(
        key="mit-technology-review",
        name="MIT Technology Review",
        industry="digital_tech_comms",
        feed_url="https://www.technologyreview.com/feed/",
        homepage_url="https://www.technologyreview.com/",
        industries=("digital_tech_comms", "education_research"),
        region="INTL",
        max_items=2,
    ),
    FeedSource(
        key="federal-reserve",
        name="Federal Reserve",
        industry="finance_insurance",
        feed_url="https://www.federalreserve.gov/feeds/press_all.xml",
        homepage_url="https://www.federalreserve.gov/",
        industries=("finance_insurance",),
        region="INTL",
        max_items=2,
    ),
    FeedSource(
        key="sec",
        name="U.S. SEC",
        industry="finance_insurance",
        feed_url="https://www.sec.gov/news/pressreleases.rss",
        homepage_url="https://www.sec.gov/",
        industries=("finance_insurance",),
        region="INTL",
        max_items=2,
    ),
    FeedSource(
        key="openai",
        name="OpenAI",
        industry="digital_tech_comms",
        feed_url="https://openai.com/news/rss.xml",
        homepage_url="https://openai.com/news/",
        industries=("digital_tech_comms",),
        region="INTL",
        max_items=2,
    ),
    FeedSource(
        key="hugging-face",
        name="Hugging Face",
        industry="digital_tech_comms",
        feed_url="https://huggingface.co/blog/feed.xml",
        homepage_url="https://huggingface.co/blog",
        industries=("digital_tech_comms",),
        region="INTL",
        max_items=2,
    ),
    FeedSource(
        key="google-deepmind",
        name="Google DeepMind",
        industry="digital_tech_comms",
        feed_url="https://deepmind.google/blog/rss.xml",
        homepage_url="https://deepmind.google/discover/blog/",
        industries=("digital_tech_comms", "education_research"),
        region="INTL",
        max_items=2,
    ),
    FeedSource(
        key="cleantechnica",
        name="CleanTechnica",
        industry="energy_environment",
        feed_url="https://cleantechnica.com/feed/",
        homepage_url="https://cleantechnica.com/",
        industries=("energy_environment", "auto_smart_mobility"),
        region="INTL",
        max_items=2,
    ),
    FeedSource(
        key="us-doe",
        name="U.S. Department of Energy",
        industry="energy_environment",
        feed_url="https://www.energy.gov/rss/news",
        homepage_url="https://www.energy.gov/news",
        industries=("energy_environment",),
        region="INTL",
        max_items=2,
    ),
    FeedSource(
        key="electrek",
        name="Electrek",
        industry="auto_smart_mobility",
        feed_url="https://electrek.co/feed/",
        homepage_url="https://electrek.co/",
        industries=("auto_smart_mobility", "energy_environment"),
        region="INTL",
        max_items=2,
    ),
    FeedSource(
        key="fierce-healthcare",
        name="Fierce Healthcare",
        industry="health_life_sciences",
        feed_url="https://www.fiercehealthcare.com/rss/xml",
        homepage_url="https://www.fiercehealthcare.com/",
        industries=("health_life_sciences",),
        region="INTL",
        max_items=2,
    ),
    FeedSource(
        key="edsurge",
        name="EdSurge",
        industry="education_research",
        feed_url="https://www.edsurge.com/articles_rss",
        homepage_url="https://www.edsurge.com/",
        industries=("education_research",),
        region="INTL",
        max_items=2,
    ),
    FeedSource(
        key="retail-dive",
        name="Retail Dive",
        industry="consumer_retail_services",
        feed_url="https://www.retaildive.com/feeds/news/",
        homepage_url="https://www.retaildive.com/",
        industries=("consumer_retail_services",),
        region="INTL",
        max_items=2,
    ),
    FeedSource(
        key="housingwire",
        name="HousingWire",
        industry="real_estate_construction",
        feed_url="https://www.housingwire.com/feed/",
        homepage_url="https://www.housingwire.com/",
        industries=("real_estate_construction", "finance_insurance"),
        region="INTL",
        max_items=2,
    ),
    FeedSource(
        key="supply-chain-dive",
        name="Supply Chain Dive",
        industry="transport_logistics",
        feed_url="https://www.supplychaindive.com/feeds/news/",
        homepage_url="https://www.supplychaindive.com/",
        industries=("transport_logistics",),
        region="INTL",
        max_items=2,
    ),
    FeedSource(
        key="usda",
        name="U.S. Department of Agriculture",
        industry="agriculture_food",
        feed_url="https://www.usda.gov/rss/home.xml",
        homepage_url="https://www.usda.gov/",
        industries=("agriculture_food",),
        region="INTL",
        max_items=2,
    ),
    FeedSource(
        key="variety",
        name="Variety",
        industry="culture_media_content",
        feed_url="https://variety.com/feed/",
        homepage_url="https://variety.com/",
        industries=("culture_media_content",),
        region="INTL",
        max_items=2,
    ),
    FeedSource(
        key="hr-dive",
        name="HR Dive",
        industry="enterprise_professional_services",
        feed_url="https://www.hrdive.com/feeds/news/",
        homepage_url="https://www.hrdive.com/",
        industries=("enterprise_professional_services",),
        region="INTL",
        max_items=2,
    ),
    FeedSource(
        key="cgtn-china",
        name="CGTN 中国",
        industry="enterprise_professional_services",
        feed_url="https://www.cgtn.com/subscribe/rss/section/china.xml",
        homepage_url="https://www.cgtn.com/",
        industries=(),
        region="CN",
    ),
    # Official/industry candidates verified as non-Feed or invalid XML.
    FeedSource(
        key="cnautonews", name="中国汽车报", industry="auto_smart_mobility",
        feed_url="https://www.cnautonews.com/rss", homepage_url="https://www.cnautonews.com/",
        enabled=False, blocked_reason="TLS 证书主机名不匹配/未确认可用 Feed；未启用",
    ),
    FeedSource(
        key="china5e", name="中国能源网", industry="energy_environment",
        feed_url="https://www.china5e.com/rss/", homepage_url="https://www.china5e.com/",
        enabled=False, blocked_reason="候选地址非 RSS/XML 解析失败；未启用",
    ),
    FeedSource(
        key="mot", name="交通运输部", industry="transport_logistics",
        feed_url="https://www.mot.gov.cn/rss/", homepage_url="https://www.mot.gov.cn/",
        enabled=False, blocked_reason="候选地址非有效 RSS；未启用",
    ),
    FeedSource(
        key="moa", name="农业农村部", industry="agriculture_food",
        feed_url="http://www.moa.gov.cn/rss/", homepage_url="http://www.moa.gov.cn/",
        enabled=False, blocked_reason="候选 XML mismatched tag；未启用",
    ),
    FeedSource(
        key="mohurd", name="住房和城乡建设部", industry="real_estate_construction",
        feed_url="https://www.mohurd.gov.cn/rss/", homepage_url="https://www.mohurd.gov.cn/",
        enabled=False, blocked_reason="候选 XML mismatched tag；未启用",
    ),
    FeedSource(
        key="nhc", name="国家卫生健康委", industry="health_life_sciences",
        feed_url="http://www.nhc.gov.cn/rss/", homepage_url="http://www.nhc.gov.cn/",
        enabled=False, blocked_reason="候选 XML mismatched tag；未启用",
    ),
    FeedSource(
        key="moe", name="教育部", industry="education_research",
        feed_url="http://www.moe.gov.cn/rss/", homepage_url="http://www.moe.gov.cn/",
        enabled=False, blocked_reason="候选 XML 非法；未启用",
    ),
    FeedSource(
        key="mct", name="文化和旅游部", industry="tourism_hospitality_events",
        feed_url="https://www.mct.gov.cn/rss/", homepage_url="https://www.mct.gov.cn/",
        enabled=False, blocked_reason="候选 XML 非法；未启用",
    ),
    FeedSource(
        key="casb-agri", name="中国农学通报", industry="agriculture_food",
        feed_url="http://www.casb.org.cn/rss/", homepage_url="http://www.casb.org.cn/",
        enabled=False, blocked_reason="候选 XML mismatched tag；未启用",
    ),
    FeedSource(
        key="fujian-agri", name="福建省农业农村厅", industry="agriculture_food",
        feed_url="http://nynct.fujian.gov.cn/rss/", homepage_url="http://nynct.fujian.gov.cn/",
        enabled=False, blocked_reason="候选 XML mismatched tag；未启用",
    ),
    FeedSource(
        key="shenzhen-housing", name="深圳市住房和建设局", industry="real_estate_construction",
        feed_url="http://zjj.sz.gov.cn/rss/", homepage_url="http://zjj.sz.gov.cn/",
        enabled=False, blocked_reason="候选 XML mismatched tag；未启用",
    ),
    # Verified failures / unverified official candidates: never fetched.
    FeedSource(
        key="36kr",
        name="36氪",
        industry="digital_tech_comms",
        feed_url="https://36kr.com/feed",
        homepage_url="https://36kr.com/",
        enabled=False,
        blocked_reason="Feed XML 非法，无法解析；未启用",
    ),
    FeedSource(
        key="jiqizhixin",
        name="机器之心",
        industry="digital_tech_comms",
        feed_url="https://www.jiqizhixin.com/rss",
        homepage_url="https://www.jiqizhixin.com/",
        enabled=False,
        blocked_reason="Feed XML mismatched tag；未启用",
    ),
    FeedSource(
        key="cctv-news",
        name="央视新闻",
        industry="enterprise_professional_services",
        feed_url="https://news.cctv.com/rss/china.xml",
        homepage_url="https://news.cctv.com/",
        enabled=False,
        blocked_reason="候选 Feed XML 非法；未启用",
    ),
    FeedSource(
        key="miit",
        name="工业和信息化部",
        industry="manufacturing_industry",
        feed_url="https://www.miit.gov.cn/rss/",
        homepage_url="https://www.miit.gov.cn/",
        enabled=False,
        blocked_reason="未验证到可用 RSS Feed；未启用",
    ),
    FeedSource(
        key="stats",
        name="国家统计局",
        industry="enterprise_professional_services",
        feed_url="https://www.stats.gov.cn/sj/zxfb/rss.xml",
        homepage_url="https://www.stats.gov.cn/",
        enabled=False,
        blocked_reason="候选 Feed 超时/不可确认；未启用",
    ),
    FeedSource(
        key="mohrss",
        name="人力资源和社会保障部",
        industry="enterprise_professional_services",
        feed_url="http://www.mohrss.gov.cn/rss/",
        homepage_url="http://www.mohrss.gov.cn/",
        enabled=False,
        blocked_reason="候选 Feed XML 非法；未启用",
    ),
    FeedSource(
        key="arxiv-cs-ai",
        name="arXiv cs.AI",
        industry="digital_tech_comms",
        feed_url="https://rss.arxiv.org/rss/cs.AI",
        homepage_url="https://arxiv.org/list/cs.AI/recent",
        enabled=False,
        blocked_reason="Feed 返回 0 条 entry；未启用",
    ),
)


def enabled_sources() -> tuple[FeedSource, ...]:
    return tuple(source for source in FEED_SOURCES if source.enabled)


def source_by_key(key: str) -> FeedSource | None:
    return next((source for source in FEED_SOURCES if source.key == key), None)
