from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from app.rss_collector import (
    RssSource,
    dedupe_items,
    filter_recent,
    load_sources,
    parse_feed,
    strip_html,
)


RSS_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>FRB: Press Release - Monetary Policy</title>
    <item>
      <title>Federal Reserve issues FOMC statement</title>
      <link>https://www.federalreserve.gov/newsevents/pressreleases/monetary20260617a.htm</link>
      <description><![CDATA[<p>The Federal Open Market Committee released its statement.</p>]]></description>
      <pubDate>Wed, 17 Jun 2026 18:00:00 GMT</pubDate>
      <guid isPermaLink="true">https://www.federalreserve.gov/newsevents/pressreleases/monetary20260617a.htm</guid>
    </item>
  </channel>
</rss>
"""

ATOM_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Official speeches</title>
  <entry>
    <title>Speech on the economic outlook</title>
    <link rel="alternate" href="/newsevents/speech/example.htm" />
    <summary type="html">&lt;p&gt;Remarks on inflation and employment.&lt;/p&gt;</summary>
    <updated>2026-07-16T16:00:00Z</updated>
  </entry>
</feed>
"""


class RssCollectorTest(unittest.TestCase):
    def test_strip_html(self) -> None:
        self.assertEqual(strip_html("<p>Policy &amp; rates</p>"), "Policy & rates")

    def test_parse_federal_reserve_rss(self) -> None:
        source = RssSource("Federal Reserve", "https://www.federalreserve.gov/feeds/press_monetary.xml", "official")
        items = parse_feed(RSS_SAMPLE, source)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["source"], "Federal Reserve")
        self.assertEqual(item["platform"], "official")
        self.assertEqual(item["published_at"], "2026-06-17T18:00:00Z")
        self.assertIn("Federal Open Market Committee", item["content"])

    def test_parse_atom_and_resolve_relative_link(self) -> None:
        source = RssSource("Official Source", "https://example.com/feed.xml", "official")
        item = parse_feed(ATOM_SAMPLE, source)[0]
        self.assertEqual(item["url"], "https://example.com/newsevents/speech/example.htm")
        self.assertEqual(item["content"], "Remarks on inflation and employment.")

    def test_filter_recent_keeps_unknown_dates(self) -> None:
        items = [
            {"title": "new", "published_at": "2026-07-18T10:00:00Z"},
            {"title": "old", "published_at": "2026-07-10T10:00:00Z"},
            {"title": "unknown", "published_at": None},
        ]
        recent = filter_recent(items, 72, now=datetime(2026, 7, 19, 0, 0, tzinfo=UTC))
        self.assertEqual([item["title"] for item in recent], ["new", "unknown"])

    def test_dedupe_prefers_first_url_occurrence(self) -> None:
        items = [
            {"title": "A", "content": "first", "url": "https://example.com/a"},
            {"title": "A copy", "content": "second", "url": "https://example.com/a"},
        ]
        self.assertEqual(dedupe_items(items), [items[0]])

    def test_load_sources_ignores_disabled_entries(self) -> None:
        payload = [
            {"name": "Enabled", "url": "https://example.com/a.xml", "platform": "official"},
            {"name": "Disabled", "url": "https://example.com/b.xml", "enabled": False},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            sources = load_sources(path)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].name, "Enabled")


if __name__ == "__main__":
    unittest.main()
