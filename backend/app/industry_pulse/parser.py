import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.industry_pulse.canonical import article_hash, canonicalize_url
from app.industry_pulse.sources import FeedSource

MAX_TITLE = 500
MAX_SUMMARY = 2000
MAX_URL = 1500
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


class FeedParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedEntry:
    title: str
    url: str
    canonical_url: str
    summary: str
    published_at: datetime | None
    content_hash: str


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return "".join(node.itertext())


def _clean(value: str, limit: int) -> str:
    text = html.unescape(TAG_RE.sub(" ", value or ""))
    text = SPACE_RE.sub(" ", text).strip()
    return text[:limit]


def _child(node: ET.Element, names: tuple[str, ...]) -> ET.Element | None:
    for child in list(node):
        if _local(child.tag) in names:
            return child
    return None


def _entry_link(node: ET.Element) -> str:
    link = _child(node, ("link",))
    if link is not None:
        href = link.attrib.get("href", "").strip()
        if href:
            return href
        text = _text(link).strip()
        if text:
            return text
    for child in list(node):
        if _local(child.tag) == "link" and child.attrib.get("rel") in (None, "", "alternate"):
            href = child.attrib.get("href", "").strip()
            if href:
                return href
    for name in ("guid", "id"):
        value = _text(_child(node, (name,))).strip()
        if value.startswith(("http://", "https://")):
            return value
    return ""


def _entry_summary(node: ET.Element) -> str:
    for names in (
        ("description",),
        ("summary",),
        ("content",),
        ("encoded",),
    ):
        child = _child(node, names)
        text = _clean(_text(child), MAX_SUMMARY)
        if text:
            return text
    return ""


def _resolve_timezone(name: str | None) -> timezone | ZoneInfo:
    """Resolve the wall-clock timezone assumed for timezone-less feed dates.

    RFC 822 / ISO dates with an explicit offset or GMT are always honored.
    Only timezone-less values use this source-level default.
    """
    candidate = (name or "UTC").strip() or "UTC"
    try:
        return ZoneInfo(candidate)
    except (ZoneInfoNotFoundError, ValueError):
        # Keep the ingestion path deterministic on hosts without tzdata.
        if candidate.lower() in {"asia/shanghai", "prc", "cst"}:
            return timezone(timedelta(hours=8), "Asia/Shanghai")
        return UTC


def _parse_date(
    value: str,
    default_timezone: str = "UTC",
    force_timezone: str = "",
) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    forced = bool((force_timezone or "").strip())
    source_tz = _resolve_timezone(force_timezone or default_timezone)
    try:
        parsed = parsedate_to_datetime(text)
        if forced:
            parsed = parsed.replace(tzinfo=None).replace(tzinfo=source_tz)
        elif parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=source_tz)
        return parsed.astimezone(UTC)
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if forced:
            parsed = parsed.replace(tzinfo=None).replace(tzinfo=source_tz)
        elif parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=source_tz)
        return parsed.astimezone(UTC)
    except ValueError:
        return None


def _entry_date(
    node: ET.Element,
    default_timezone: str = "UTC",
    force_timezone: str = "",
) -> datetime | None:
    for name in ("pubdate", "published", "updated", "date", "created"):
        child = _child(node, (name,))
        if child is not None:
            parsed = _parse_date(
                _text(child), default_timezone, force_timezone
            )
            if parsed is not None:
                return parsed
    return None


def parse_feed(data: bytes, source: FeedSource, max_items: int = 20) -> list[ParsedEntry]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise FeedParseError(f"XML 解析失败: {exc}") from exc

    entries: list[ParsedEntry] = []
    seen: set[str] = set()
    for node in root.iter():
        if _local(node.tag) not in {"item", "entry"}:
            continue
        title = _clean(_text(_child(node, ("title",))), MAX_TITLE)
        url = _entry_link(node)[:MAX_URL]
        canonical = canonicalize_url(url)
        if not title or not canonical or canonical in seen:
            continue
        seen.add(canonical)
        entries.append(
            ParsedEntry(
                title=title,
                url=url,
                canonical_url=canonical,
                summary=_entry_summary(node),
                published_at=_entry_date(
                    node, source.default_timezone, source.force_timezone
                ),
                content_hash=article_hash(canonical, title),
            )
        )
        if len(entries) >= max_items:
            break
    return entries
