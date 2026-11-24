import hashlib
import re
from typing import Any

from app.schemas.market import MarketJobIn

SKILL_ALIASES: dict[str, str] = {
    "python": "Python",
    "python开发": "Python",
    "py": "Python",
    "sql": "SQL",
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "excel": "Excel",
    "tableau": "Tableau",
    "power bi": "Power BI",
    "powerbi": "Power BI",
    "spark": "Spark",
    "hadoop": "Hadoop",
    "hive": "Hive",
    "java": "Java",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "vue": "Vue",
    "vue3": "Vue",
    "react": "React",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "git": "Git",
    "linux": "Linux",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "机器学习": "机器学习",
    "深度学习": "深度学习",
    "自然语言处理": "自然语言处理",
    "nlp": "自然语言处理",
    "数据挖掘": "数据挖掘",
    "统计分析": "统计分析",
    "ab测试": "A/B 测试",
    "a/b测试": "A/B 测试",
    "a/b 测试": "A/B 测试",
    "数据可视化": "数据可视化",
    "产品设计": "产品设计",
    "项目管理": "项目管理",
    "沟通": "沟通",
    "用户研究": "用户研究",
    "数据建模": "数据建模",
    "etl": "ETL",
    "airflow": "Airflow",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "scikit-learn": "scikit-learn",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "go": "Go",
    "golang": "Go",
    "c++": "C++",
    "c#": "C#",
}

TITLE_RULES = (
    ("数据分析", "数据分析师"),
    ("data analyst", "数据分析师"),
    ("算法", "算法工程师"),
    ("前端", "前端工程师"),
    ("frontend", "前端工程师"),
    ("后端", "后端工程师"),
    ("backend", "后端工程师"),
    ("产品经理", "产品经理"),
    ("运营", "运营"),
    ("测试", "测试工程师"),
    ("python", "Python开发工程师"),
    ("java", "Java开发工程师"),
)

CITY_SUFFIX = re.compile(r"[·/\-（(].*$")


def normalize_skill(value: str) -> str | None:
    text = value.strip().lower()
    if not text:
        return None
    return SKILL_ALIASES.get(text)


def extract_skills(text: str) -> list[str]:
    lowered = text.lower()
    found = []
    for alias, canonical in SKILL_ALIASES.items():
        if canonical in found:
            continue
        if alias.isascii():
            pattern = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
            if re.search(pattern, lowered):
                found.append(canonical)
        elif alias in lowered:
            found.append(canonical)
    return sorted(found)


def normalize_title(value: str) -> str:
    text = re.sub(r"\s+", " ", value.strip())
    lowered = text.lower()
    for marker, normalized in TITLE_RULES:
        if marker in lowered:
            return normalized
    return text[:200] or "其他"


def normalize_location(value: str) -> str:
    text = CITY_SUFFIX.sub("", value.strip())
    text = text.replace("市", "")
    text = re.sub(r"\s+", "", text)
    return text[:100] or "未说明"


def normalize_education(value: str) -> str:
    text = value.strip().lower()
    if not text or "不限" in text:
        return "不限" if text else "未说明"
    if "博士" in text:
        return "博士"
    if "硕士" in text or "研究生" in text:
        return "硕士"
    if "本科" in text or "学士" in text:
        return "本科"
    if "大专" in text or "专科" in text:
        return "大专"
    return "未说明"


def normalize_experience(value: str) -> str:
    text = value.strip().lower()
    if not text:
        return "未说明"
    if "应届" in text or "在校" in text:
        return "应届"
    if "不限" in text or "经验不限" in text:
        return "不限"
    match = re.search(r"(\d+)\s*[-~至]\s*(\d+)\s*年", text)
    if match:
        return f"{match.group(1)}-{match.group(2)}年"
    match = re.search(r"(\d+)\s*年(?:以上|及以上)", text)
    if match:
        return f"{match.group(1)}年以上"
    return "未说明"


def clean_job(job: MarketJobIn) -> dict[str, Any]:
    title_raw = job.title.strip()
    title = normalize_title(title_raw)
    company = job.company.strip() or "未说明"
    location = normalize_location(job.location)
    education = normalize_education(job.education)
    experience = normalize_experience(job.experience)
    industry = job.industry.strip() or "其他"
    skills = extract_skills(f"{title_raw}\n{job.description}")
    raw = job.model_dump(mode="json")
    posted = job.posted_at.isoformat() if job.posted_at else ""
    identity = job.external_id or f"{title}|{company}|{location}|{job.description[:500]}"
    dedupe_source = f"{identity}|{posted}|{title}|{company}|{location}"
    dedupe_hash = hashlib.sha256(dedupe_source.encode("utf-8")).hexdigest()
    return {
        "title_raw": title_raw,
        "title": title,
        "company": company,
        "industry": industry,
        "location": location,
        "education": education,
        "experience": experience,
        "skills": skills,
        "salary": job.salary,
        "source_url": job.source_url,
        "posted_at": job.posted_at,
        "external_id": job.external_id,
        "raw_payload": raw,
        "dedupe_hash": dedupe_hash,
    }
