"""Legacy V2 classifier kept only for V2 -> V2.1 preview comparison."""

import re
from dataclasses import dataclass, field
from typing import Any

from app.industry_pulse.sources import FeedSource
from app.industry_pulse.taxonomy import (
    INDUSTRY_ORDER,
    RELEVANCE_INDUSTRY_RELEVANT,
    RELEVANCE_IRRELEVANT,
    RELEVANCE_MACRO_SIGNAL,
    RELEVANCE_NEEDS_REVIEW,
)

RULE_VERSION = "industry-v2.0-legacy"

INDUSTRY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "digital_tech_comms": (
        "人工智能", "生成式ai", "大模型", "机器学习", "深度学习", "算法", "智能体",
        "互联网", "软件", "云计算", "大数据", "数据中心", "网络安全", "通信",
        "5g", "6g", "宽带", "运营商", "光纤", "物联网", "智能硬件", "可穿戴",
        "传感器", "开源模型", "数字技术", "ai",
    ),
    "finance_insurance": (
        "金融", "银行", "证券", "基金", "保险", "支付", "信贷", "风控", "资本市场",
        "新股", "招股", "股票", "债券", "券商", "资管", "理财", "精算", "金融科技",
    ),
    "manufacturing_industry": (
        "半导体", "集成电路", "芯片", "智能制造", "工业机器人", "机器人", "新材料",
        "电子制造", "制造", "工厂", "生产线", "装备", "机械", "钢铁", "化工",
    ),
    "energy_environment": (
        "新能源", "光伏", "风电", "储能", "电池", "电力", "电网", "氢能", "核电",
        "油气", "石油", "天然气", "环保", "碳管理", "碳排放", "碳中和", "节能",
    ),
    "auto_smart_mobility": (
        "汽车", "智能驾驶", "自动驾驶", "新能源车", "车企", "车载", "整车",
        "汽车零部件", "汽车服务", "智能出行", "充电桩",
    ),
    "transport_logistics": (
        "航空", "铁路", "航运", "港口", "快递", "物流", "供应链", "货运", "运输",
        "机场", "地铁", "高铁", "仓储", "配送", "客运", "列车",
    ),
    "health_life_sciences": (
        "医药", "生物技术", "医疗器械", "医院", "医疗服务", "公共卫生", "药物",
        "临床", "疫苗", "诊断", "生物医药", "基因", "细胞治疗", "医保", "治疗",
    ),
    "education_research": (
        "教育", "高校", "大学", "科研", "学术", "学生", "课程", "招生", "职业教育",
        "教育科技", "学校", "教师", "学科", "实验室", "论文",
    ),
    "agriculture_food": (
        "农业", "农产品", "食品加工", "食品安全", "种植", "养殖", "农学", "智慧农业",
        "粮食", "农资", "农机", "园艺", "畜牧",
    ),
    "consumer_retail_services": (
        "电商", "零售", "消费品牌", "餐饮", "美妆", "家居", "生活服务", "消费者",
        "购物", "门店", "直播带货", "新消费", "连锁", "消费",
    ),
    "real_estate_construction": (
        "房地产", "楼市", "建筑工程", "城市建设", "工程设计", "基础设施", "住房",
        "物业", "土木", "施工", "建材", "城市更新", "基建", "建筑",
    ),
    "culture_media_content": (
        "影视", "出版", "新闻传媒", "音乐产业", "游戏", "数字内容", "广告传媒",
        "电影", "电视剧", "综艺", "动漫", "版权", "内容产业", "媒体", "文化传媒",
        "文化活动", "文娱",
    ),
    "arts_design": (
        "美术", "绘画", "雕塑", "表演艺术", "展览", "视觉设计", "产品设计",
        "服装设计", "艺术", "设计产业", "工业设计", "时装", "画廊", "艺术品",
        "设计",
    ),
    "sports_industry": (
        "体育", "体育赛事", "职业俱乐部", "健身", "体育用品", "体育科技",
        "体育商业", "运动监测", "运动员", "球队", "联赛", "运动",
    ),
    "tourism_hospitality_events": (
        "旅游", "酒店", "景区", "旅行服务", "会展", "度假", "休闲旅游", "游客",
        "文旅", "温泉", "冰雪", "民宿", "旅行社",
    ),
    "enterprise_professional_services": (
        "管理咨询", "法律", "会计", "审计", "人力资源", "企业营销", "检测认证",
        "商务服务", "咨询", "律所", "会计师事务所", "猎头", "企业服务",
        "专业服务", "质量管理", "标准化",
    ),
}

INDUSTRY_SIGNALS: tuple[str, ...] = (
    "产业", "产业链", "产能", "投产", "扩产", "项目", "建设", "研发", "专利",
    "技术突破", "突破", "发布", "上市", "融资", "投资", "并购", "营收", "利润",
    "订单", "采购", "中标", "合作", "布局", "商业化", "商业", "落地", "应用",
    "市场", "需求", "销量", "市占", "出口", "进口", "政策", "规划", "标准",
    "监管", "许可", "牌照", "招聘", "岗位", "人才", "技能", "培训", "企业",
    "公司", "工厂", "生产线", "园区", "基地", "平台", "整合", "培育", "开通",
    "实施", "推出", "产品", "制度", "改革", "试点", "集采", "医保谈判",
)

MACRO_TERMS: tuple[str, ...] = (
    "出生人口", "人口", "未婚", "结婚率", "生育率", "老龄化", "人口结构",
    "gdp", "cpi", "ppi", "失业率", "就业率", "货币政策", "汇率", "财政",
    "税收", "居民收入", "经济增速", "社融", "m2", "宏观", "同比",
)

CULTURE_EVENT_TERMS: tuple[str, ...] = (
    "民俗", "庙会", "灯会", "庆典", "展演", "节庆", "文化旅游节", "艺术节",
    "盘王节", "那达慕", "泼水节",
)

TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "AI": ("人工智能", "ai", "大模型", "智能体", "agent", "机器学习", "生成式ai"),
    "政策": ("政策", "监管", "规划", "部委", "国务院", "政府", "条例"),
    "招聘": ("招聘", "岗位", "就业", "人才", "用工", "技能"),
    "投融资": ("融资", "投资", "并购", "ipo", "上市", "估值"),
    "技术突破": ("突破", "首次", "发布", "开源", "专利", "创新"),
}


@dataclass(frozen=True)
class Classification:
    relevance: str
    primary_industry: str | None
    industries: tuple[str, ...]
    tags: tuple[str, ...] = ()
    basis: dict[str, Any] = field(default_factory=dict)


def _matches(text: str, keywords: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    matched: list[str] = []
    for keyword in sorted(keywords, key=len, reverse=True):
        token = keyword.lower()
        if token.isascii():
            if re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", lowered):
                matched.append(keyword)
        elif token in lowered:
            matched.append(keyword)
    return [
        keyword
        for keyword in matched
        if not any(
            keyword != other and keyword.lower() in other.lower()
            for other in matched
        )
    ]


def _score(industry: str, title_terms: list[str], text_terms: list[str], hint: set[str]) -> int:
    score = len(title_terms) * 3 + len(text_terms)
    if industry in hint and title_terms:
        score += 1
    return score


def classify_article_v2(source: FeedSource, title: str, summary: str) -> Classification:
    text = f"{title}\n{summary}"
    text_terms = {industry: _matches(text, keywords) for industry, keywords in INDUSTRY_KEYWORDS.items()}
    title_terms = {industry: _matches(title, keywords) for industry, keywords in INDUSTRY_KEYWORDS.items()}
    hits = [industry for industry in INDUSTRY_ORDER if text_terms[industry]]
    signals = _matches(text, INDUSTRY_SIGNALS)
    macro = _matches(text, MACRO_TERMS)
    events = _matches(title, CULTURE_EVENT_TERMS)
    hint = set(source.industries) & set(INDUSTRY_ORDER)

    if macro and not hits:
        relevance = RELEVANCE_MACRO_SIGNAL
    elif not hits:
        relevance = RELEVANCE_NEEDS_REVIEW if events else RELEVANCE_IRRELEVANT
    elif signals or any(title_terms[industry] for industry in hint):
        relevance = RELEVANCE_INDUSTRY_RELEVANT
    else:
        relevance = RELEVANCE_NEEDS_REVIEW

    industries: tuple[str, ...] = ()
    primary: str | None = None
    if relevance == RELEVANCE_INDUSTRY_RELEVANT:
        ranked = sorted(
            hits,
            key=lambda industry: (
                -_score(industry, title_terms[industry], text_terms[industry], hint),
                INDUSTRY_ORDER.index(industry),
            ),
        )
        industries = tuple(ranked[:3])
        primary = industries[0]

    tags = tuple(
        label for label, keywords in TOPIC_KEYWORDS.items() if _matches(text, keywords)
    )
    basis = {
        "rule_version": RULE_VERSION,
        "matched_terms": {industry: text_terms[industry] for industry in hits},
        "signals": signals,
        "macro_terms": macro,
        "event_terms": events,
        "source_hint": list(source.industries),
        "source_hint_used": bool(hint and any(title_terms[i] for i in hint)),
        "scores": {
            industry: _score(industry, title_terms[industry], text_terms[industry], hint)
            for industry in hits
        },
    }
    return Classification(
        relevance=relevance,
        primary_industry=primary,
        industries=industries,
        tags=tags,
        basis=basis,
    )