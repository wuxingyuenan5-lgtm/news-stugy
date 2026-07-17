from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from common import (  # noqa: E402
    TimeWindow,
    classify_asset,
    filter_posts,
    dump_json,
    load_json,
    parse_post_time,
    render_timeline,
)
from fetch_x_posts import _extract_status_url_from_search, _search_index_query  # noqa: E402
from run_daily_batch import compute_incremental_posts, parse_targets_config  # noqa: E402


class XFetchTests(unittest.TestCase):
    def test_parse_relative_time(self) -> None:
        now = datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc)
        parsed = parse_post_time("3d", now=now)
        self.assertEqual(parsed, datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc))

    def test_parse_absolute_time(self) -> None:
        parsed = parse_post_time("Jun 17, 2026 10:30 PM UTC")
        self.assertEqual(parsed, datetime(2026, 6, 17, 22, 30, tzinfo=timezone.utc))

    def test_classify_asset(self) -> None:
        self.assertEqual(classify_asset("纳指和芯片股昨晚继续走强"), "us-stocks")
        self.assertEqual(classify_asset("BTC 和 ETH 继续吸走流动性"), "crypto")
        self.assertEqual(classify_asset("联储和CPI重新定价利率路径"), "macro")

    def test_filter_posts(self) -> None:
        posts = [
            {"published_at": "2026-06-17T22:30:00+00:00", "text": "A"},
            {"published_at": "2026-06-13T22:30:00+00:00", "text": "B"},
        ]
        window = TimeWindow(
            start=datetime(2026, 6, 15, 0, 0, tzinfo=timezone.utc),
            end=datetime(2026, 6, 18, 0, 0, tzinfo=timezone.utc),
        )
        filtered = filter_posts(posts, window)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["text"], "A")

    def test_render_timeline(self) -> None:
        payload = {
            "window": {
                "start": "2026-06-15T00:00:00+00:00",
                "end": "2026-06-18T00:00:00+00:00",
            },
            "users": ["chenreason"],
            "posts": [
                {
                    "author": "chenreason",
                    "published_at": "2026-06-17T22:30:00+00:00",
                    "text": "纳指和芯片股昨晚继续走强，但广度一般。",
                    "asset_class": "us-stocks",
                    "post_url": "https://x.com/chenreason/status/1",
                }
            ],
        }
        rendered = render_timeline(payload)
        self.assertIn("# X Timeline Summary", rendered)
        self.assertIn("us-stocks", rendered)
        self.assertIn("https://x.com/chenreason/status/1", rendered)

    def test_extract_status_url_from_search(self) -> None:
        content = """
4.   x.com

[https://x.com›chenreason › status › 2065832817968496840](https://x.com/chenreason/status/2065832817968496840)  ## [Ai产业现在有个最大的公开秘密。]
"""
        url = _extract_status_url_from_search(content, "chenreason")
        self.assertEqual(url, "https://x.com/chenreason/status/2065832817968496840")

    def test_search_index_query_shape(self) -> None:
        query = _search_index_query("chenreason")
        self.assertIn("site:x.com/chenreason/status", query)
        self.assertIn("from:chenreason", query)

    def test_parse_targets_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "targets.json"
            dump_json(
                path,
                {
                    "users": [
                        "chenreason",
                        {"username": "farokh", "include_replies": True},
                    ],
                    "limit_per_user": 25,
                    "default_window": {"days": 2},
                    "include_replies": False,
                },
            )
            config = parse_targets_config(path)
            self.assertEqual(config["users"], ["chenreason", "farokh"])
            self.assertEqual(config["limit_per_user"], 25)
            self.assertEqual(config["default_window"]["days"], 2)
            self.assertEqual(config["user_settings"]["farokh"]["include_replies"], True)

    def test_compute_incremental_posts(self) -> None:
        current = {
            "posts": [
                {"author": "chenreason", "post_id": "1", "published_at": "2026-06-17T00:00:00+00:00", "text": "A"},
                {"author": "chenreason", "post_id": "2", "published_at": "2026-06-18T00:00:00+00:00", "text": "B"},
            ]
        }
        state = {
            "seen_keys": ["chenreason|1"]
        }
        incremental = compute_incremental_posts(current, state)
        self.assertEqual(len(incremental), 1)
        self.assertEqual(incremental[0]["post_id"], "2")


if __name__ == "__main__":
    unittest.main()
