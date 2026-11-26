from datetime import UTC, datetime

import pytest

from app.industry_pulse.canonical import canonicalize_url
from app.industry_pulse.parser import FeedParseError, parse_feed
from app.industry_pulse.sources import FeedSource


def _source(
    default_timezone: str = "UTC", force_timezone: str = ""
) -> FeedSource:
    return FeedSource(
        key="test-feed",
        name="Test Feed",
        industry="internet",
        feed_url="https://example.invalid/rss",
        homepage_url="https://example.invalid/",
        default_timezone=default_timezone,
        force_timezone=force_timezone,
    )


RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Platform teams tighten data loops</title>
    <link>https://example.invalid/a?utm_source=rss&amp;utm_medium=feed</link>
    <description><![CDATA[<p>Teams <b>connect</b> retention and conversion.</p>]]></description>
    <pubDate>Mon, 24 Nov 2026 09:30:00 GMT</pubDate>
  </item>
  <item>
    <title>Missing date item</title>
    <link>https://example.invalid/b</link>
    <description>No date.</description>
  </item>
  <item>
    <title>Duplicate canonical</title>
    <link>https://example.invalid/a?utm_campaign=dup</link>
    <description>Duplicate.</description>
  </item>
</channel></rss>"""


ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Atom entry</title>
    <link href="https://example.invalid/atom" rel="alternate"/>
    <summary>Atom summary</summary>
    <updated>2026-11-24T10:00:00+08:00</updated>
  </entry>
</feed>"""


def test_parse_rss_deduplicates_canonical_urls_and_cleans_html():
    entries = parse_feed(RSS, _source(), max_items=20)
    assert len(entries) == 2
    first = entries[0]
    assert first.title == "Platform teams tighten data loops"
    assert first.canonical_url == "https://example.invalid/a"
    assert first.summary == "Teams connect retention and conversion."
    assert first.published_at == datetime(2026, 11, 24, 9, 30, tzinfo=UTC)
    assert entries[1].published_at is None


def test_parse_atom_and_timezone():
    entries = parse_feed(ATOM, _source(), max_items=20)
    assert len(entries) == 1
    assert entries[0].url == "https://example.invalid/atom"
    assert entries[0].summary == "Atom summary"
    assert entries[0].published_at == datetime(2026, 11, 24, 2, 0, tzinfo=UTC)


def test_invalid_feed_is_explicit_error():
    with pytest.raises(FeedParseError):
        parse_feed(b"<rss><channel><item>", _source())


def _feed_with_date(date_text: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<rss version=\"2.0\"><channel><item>"
        "<title>Timezone sample</title>"
        "<link>https://example.invalid/tz</link>"
        "<description>Timezone sample summary.</description>"
        f"<pubDate>{date_text}</pubDate>"
        "</item></channel></rss>"
    ).encode()


def test_timezone_less_date_uses_source_timezone_for_infoq():
    entries = parse_feed(
        _feed_with_date("Wed, 25 Nov 2026 14:00:00"),
        _source("Asia/Shanghai"),
    )
    assert entries[0].published_at == datetime(2026, 11, 25, 6, 0, tzinfo=UTC)


def test_explicit_offset_is_not_double_converted():
    entries = parse_feed(
        _feed_with_date("Wed, 25 Nov 2026 14:00:00 +0800"),
        _source("America/New_York"),
    )
    assert entries[0].published_at == datetime(2026, 11, 25, 6, 0, tzinfo=UTC)


def test_forced_source_timezone_overrides_mislabeled_gmt():
    entries = parse_feed(
        _feed_with_date("Thu, 26 Nov 2026 15:35:51 GMT"),
        _source("Asia/Shanghai", "Asia/Shanghai"),
    )
    assert entries[0].published_at == datetime(
        2026, 11, 26, 7, 35, 51, tzinfo=UTC
    )


def test_iso_naive_dst_boundaries_follow_source_timezone():
    summer = parse_feed(
        _feed_with_date("2026-07-01T12:00:00"),
        _source("America/New_York"),
    )
    winter = parse_feed(
        _feed_with_date("2026-01-15T12:00:00"),
        _source("America/New_York"),
    )
    assert summer[0].published_at == datetime(2026, 7, 1, 16, 0, tzinfo=UTC)
    assert winter[0].published_at == datetime(2026, 1, 15, 17, 0, tzinfo=UTC)


def test_naive_date_crosses_utc_day_boundary():
    entries = parse_feed(
        _feed_with_date("2026-11-25T00:30:00"),
        _source("Asia/Shanghai"),
    )
    assert entries[0].published_at == datetime(2026, 11, 24, 16, 30, tzinfo=UTC)


def test_canonical_url_removes_tracking_and_fragments():
    assert (
        canonicalize_url(
            "HTTPS://Example.INVALID/a/?utm_source=x&b=2&a=1#section"
        )
        == "https://example.invalid/a?a=1&b=2"
    )
    assert canonicalize_url("not-a-url") == ""
