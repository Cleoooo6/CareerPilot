from dataclasses import dataclass

RELEVANCE_INDUSTRY_RELEVANT = "industry_relevant"
RELEVANCE_MACRO_SIGNAL = "macro_signal"
RELEVANCE_NEEDS_REVIEW = "needs_review"
RELEVANCE_IRRELEVANT = "irrelevant"
RELEVANCE_STATUSES = (
    RELEVANCE_INDUSTRY_RELEVANT,
    RELEVANCE_MACRO_SIGNAL,
    RELEVANCE_NEEDS_REVIEW,
    RELEVANCE_IRRELEVANT,
)

TAXONOMY_VERSION_LEGACY = 1
TAXONOMY_VERSION_CURRENT = 2

MAJORS_NOTE = (
    "以上专业为相关方向示例，并非限定范围。跨学科专业也可能对应多个行业，"
    "专业与行业并非一一对应关系。"
)


@dataclass(frozen=True)
class IndustryMeta:
    id: str
    name: str
    scope: str
    majors: tuple[str, ...]


INDUSTRIES: tuple[IndustryMeta, ...] = (
    IndustryMeta(
        id="digital_tech_comms",
        name="数字科技与通信",
        scope="人工智能、互联网、软件、云计算、大数据、网络安全、通信与物联网。",
        majors=(
            "计算机科学与技术", "软件工程", "人工智能", "数据科学与大数据技术",
            "网络空间安全", "通信工程", "电子信息工程", "物联网工程",
        ),
    ),
    IndustryMeta(
        id="finance_insurance",
        name="金融与保险",
        scope="银行、证券、基金、保险、支付、投资与金融科技。",
        majors=(
            "金融学", "金融工程", "保险学", "投资学", "经济学", "金融科技", "精算学",
        ),
    ),
    IndustryMeta(
        id="manufacturing_industry",
        name="制造业与工业科技",
        scope="半导体、智能制造、机器人、工业设备、新材料与电子制造。",
        majors=(
            "机械工程", "机械设计制造及其自动化", "智能制造工程", "自动化",
            "机器人工程", "材料科学与工程", "微电子科学与工程",
        ),
    ),
    IndustryMeta(
        id="energy_environment",
        name="能源与环境",
        scope="新能源、电力、电网、储能、油气、环保与碳管理。",
        majors=(
            "能源与动力工程", "新能源科学与工程", "电气工程及其自动化",
            "储能科学与工程", "环境科学与工程", "环境工程",
        ),
    ),
    IndustryMeta(
        id="auto_smart_mobility",
        name="汽车与智能出行",
        scope="汽车制造、汽车零部件、智能驾驶、汽车服务与智能出行。",
        majors=(
            "车辆工程", "智能车辆工程", "汽车服务工程", "机械工程",
            "自动化", "交通设备与控制工程",
        ),
    ),
    IndustryMeta(
        id="transport_logistics",
        name="交通运输与物流",
        scope="航空、铁路、航运、快递、物流与供应链。",
        majors=(
            "交通运输", "交通工程", "物流管理", "物流工程",
            "供应链管理", "航海技术", "轮机工程",
        ),
    ),
    IndustryMeta(
        id="health_life_sciences",
        name="医疗健康与生命科学",
        scope="医药、生物技术、医疗器械、医院、医疗服务与公共卫生。",
        majors=(
            "临床医学", "口腔医学", "药学", "生物技术", "生物医学工程",
            "护理学", "预防医学", "医学检验技术",
        ),
    ),
    IndustryMeta(
        id="education_research",
        name="教育与科研",
        scope="基础教育、高等教育、职业教育、科研机构与教育科技。",
        majors=(
            "教育学", "教育技术学", "学前教育", "小学教育", "科学教育",
            "数学与应用数学", "物理学", "化学", "生物科学", "各学科师范类专业",
        ),
    ),
    IndustryMeta(
        id="agriculture_food",
        name="农业与食品",
        scope="现代农业、农产品、食品加工、食品安全与农业科技。",
        majors=(
            "农学", "智慧农业", "园艺", "植物保护", "动物科学",
            "动物医学", "食品科学与工程", "食品质量与安全",
        ),
    ),
    IndustryMeta(
        id="consumer_retail_services",
        name="消费、零售与生活服务",
        scope="电商、零售、消费品牌、餐饮、美妆、家居与生活服务。",
        majors=(
            "电子商务", "市场营销", "工商管理", "国际经济与贸易",
            "零售业管理", "物流管理",
        ),
    ),
    IndustryMeta(
        id="real_estate_construction",
        name="房地产与建筑",
        scope="房地产、建筑工程、城市建设、工程设计、基础设施。",
        majors=(
            "土木工程", "建筑学", "城乡规划", "工程管理", "工程造价",
            "建筑环境与能源应用工程", "给排水科学与工程",
        ),
    ),
    IndustryMeta(
        id="culture_media_content",
        name="文化传媒与内容产业",
        scope="影视、出版、新闻传媒、音乐产业、游戏、数字内容与广告传媒。",
        majors=(
            "新闻学", "传播学", "广播电视学", "网络与新媒体", "广告学",
            "数字媒体技术", "戏剧影视文学", "广播电视编导", "出版学",
        ),
    ),
    IndustryMeta(
        id="arts_design",
        name="艺术与设计产业",
        scope="美术、绘画、雕塑、表演艺术、展览、视觉设计、产品设计与服装设计。",
        majors=(
            "美术学", "绘画", "雕塑", "视觉传达设计", "环境设计",
            "产品设计", "服装与服饰设计", "数字媒体艺术", "工艺美术",
        ),
    ),
    IndustryMeta(
        id="sports_industry",
        name="体育产业",
        scope="体育赛事、职业俱乐部、健身、体育用品、体育科技与体育商业。",
        majors=(
            "体育教育", "运动训练", "社会体育指导与管理", "运动人体科学",
            "运动康复", "休闲体育", "体育经济与管理",
        ),
    ),
    IndustryMeta(
        id="tourism_hospitality_events",
        name="旅游、酒店与会展",
        scope="旅游、酒店、景区、旅行服务、会展、度假与休闲旅游。",
        majors=(
            "旅游管理", "酒店管理", "会展经济与管理", "文化产业管理",
            "旅游管理与服务教育", "会展策划与管理",
        ),
    ),
    IndustryMeta(
        id="enterprise_professional_services",
        name="企业专业服务",
        scope="管理咨询、法律、会计、审计、人力资源、企业营销、检测认证与商务服务。",
        majors=(
            "法学", "知识产权", "会计学", "审计学", "财务管理",
            "人力资源管理", "工商管理", "行政管理", "信用管理",
            "标准化工程", "质量管理工程",
        ),
    ),
)

INDUSTRY_LABELS = {item.id: item.name for item in INDUSTRIES}
INDUSTRY_ORDER = tuple(item.id for item in INDUSTRIES)
INDUSTRY_BY_ID = {item.id: item for item in INDUSTRIES}
NEW_INDUSTRY_IDS = frozenset(INDUSTRY_ORDER)

LEGACY_INDUSTRY_IDS = (
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

LEGACY_INDUSTRY_MAP: dict[str, str | None] = {
    "internet_telecom": "digital_tech_comms",
    "ai_digital": "digital_tech_comms",
    "finance_insurance": "finance_insurance",
    "manufacturing_industry": "manufacturing_industry",
    "energy_new_energy": "energy_environment",
    "auto_transport": "auto_smart_mobility",
    "healthcare_biopharma": "health_life_sciences",
    "education_research": "education_research",
    "consumer_retail": "consumer_retail_services",
    "real_estate_construction": "real_estate_construction",
    "logistics_supply_chain": "transport_logistics",
    "agriculture_food": "agriculture_food",
    "culture_media_tourism": None,
    "professional_services": None,
}

DB_INDUSTRY_IDS = tuple(dict.fromkeys((*LEGACY_INDUSTRY_IDS, *INDUSTRY_ORDER)))


def industry_payload() -> list[dict[str, object]]:
    return [
        {
            "id": item.id,
            "name": item.name,
            "scope": item.scope,
            "majors": list(item.majors),
        }
        for item in INDUSTRIES
    ]