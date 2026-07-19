from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.main import (
    analyze_item,
    analyze_pending,
    cluster_items,
    connect,
    dedupe_sentences,
    import_items,
    init_db,
    load_events,
    load_inputs,
    render_report,
    resolve_input_item_ids,
    similarity,
    title_features,
)


ROOT = Path(__file__).resolve().parents[1]


class MvpSmokeTest(unittest.TestCase):
    def test_chinese_title_similarity(self) -> None:
        left = title_features("美联储官员称降息前需要更多通胀证据")
        right = title_features("美联储官员：通胀改善后再考虑降息")
        self.assertGreaterEqual(similarity(left, right), 0.34)

    def test_analyzer_separates_facts_and_opinion(self) -> None:
        fact = analyze_item("美国公布铜贸易调查安排", "最终税率尚未公布。后续程序已经披露。", "official")
        opinion = analyze_item("策略师看多黄金", "策略师认为金价可能继续上涨。", "research")
        self.assertEqual(fact["nature"], "fact")
        self.assertIn("最终税率尚未公布。", fact["facts"])
        self.assertEqual(opinion["nature"], "opinion")
        self.assertIn("黄金", opinion["assets"])

    def test_fact_deduplication(self) -> None:
        facts = dedupe_sentences([
            "美国6月CPI同比增长2.4%。",
            "美国6月CPI同比增长2.4%。",
            "核心CPI同比增长2.8%。",
        ])
        self.assertEqual(len(facts), 2)

    def test_pipeline_fuses_sources_and_isolates_report_date(self) -> None:
        payload = [
            {
                "source": "Federal Reserve",
                "platform": "official",
                "published_at": "2026-07-18T01:00:00Z",
                "title": "美联储官员称通胀回落仍需更多证据",
                "content": "近期通胀数据有所改善。调整政策利率前仍需要更多持续证据。",
                "url": "https://example.com/fed",
            },
            {
                "source": "Market Wire",
                "platform": "media",
                "published_at": "2026-07-18T01:10:00Z",
                "title": "美联储官员：降息前需要更多通胀改善证据",
                "content": "通胀正在改善。官员未承诺具体降息时间。",
                "url": "https://example.com/fed-wire",
            },
            {
                "source": "US Trade Office",
                "platform": "official",
                "published_at": "2026-07-18T02:00:00Z",
                "title": "美国公布铜相关贸易调查后续安排",
                "content": "文件涉及精炼铜及部分铜制品。最终税率仍待后续决定。",
                "url": "https://example.com/copper",
            },
            {
                "source": "Macro Calendar",
                "platform": "data",
                "published_at": "2026-07-18T03:00:00Z",
                "title": "今晚将公布美国消费者信心数据",
                "content": "今晚将公布美国消费者信心数据。",
                "url": "https://example.com/calendar",
            },
            {
                "source": "Headline Feed",
                "platform": "metadata",
                "published_at": "2026-07-18T04:00:00Z",
                "title": "某大型科技公司或将调整资本开支计划",
                "content": "",
                "url": "https://example.com/headline",
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "input.json"
            input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with connect(root / "test.db") as conn:
                init_db(conn)
                inputs = load_inputs(input_path)
                inserted, duplicates = import_items(conn, inputs)
                self.assertEqual((inserted, duplicates), (5, 0))
                ids = resolve_input_item_ids(conn, inputs)
                analyze_pending(conn, ids)
                count = cluster_items(conn, ids, "2026-07-18")
                self.assertEqual(count, 4)

                events = load_events(conn, "2026-07-18")
                fed = next(event for event in events if "美联储" in event.title)
                self.assertEqual(fed.source_count, 2)
                self.assertGreaterEqual(len(fed.facts), 2)

                report = render_report(conn, "2026-07-18")
                self.assertIn("## 今日重点", report)
                self.assertIn("## 接下来关注", report)
                self.assertIn("来源（2）", report)
                self.assertIn("今晚将公布美国消费者信心数据", report)
                self.assertIn("仅获取到标题", report)

                cluster_items(conn, ids[:1], "2026-07-19")
                next_day = load_events(conn, "2026-07-19")
                self.assertEqual(len(next_day), 1)
                self.assertEqual(len(load_events(conn, "2026-07-18")), 4)

    def test_market_day_regression(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with connect(root / "market.db") as conn:
                init_db(conn)
                inputs = load_inputs(ROOT / "examples" / "market_day_items.json")
                inserted, duplicates = import_items(conn, inputs)
                self.assertEqual((inserted, duplicates), (17, 1))

                item_ids = resolve_input_item_ids(conn, inputs)
                analyze_pending(conn, item_ids)
                self.assertEqual(cluster_items(conn, item_ids, "2026-07-18"), 13)

                events = load_events(conn, "2026-07-18")
                copper = next(event for event in events if event.title == "美国公布铜相关贸易调查后续安排")
                fed = next(event for event in events if event.title == "美联储官员称通胀回落仍需更多证据")
                china = next(event for event in events if event.title == "有关部门发布扩大内需支持措施")
                gold = next(event for event in events if event.title == "黄金在美元回落后走强")

                self.assertEqual(copper.source_count, 3)
                self.assertEqual(fed.source_count, 2)
                self.assertEqual(china.source_count, 2)
                self.assertEqual(gold.topic, "贵金属")

                report = render_report(conn, "2026-07-18")
                self.assertIn("### 1. 美国公布铜相关贸易调查后续安排", report)
                self.assertIn("## 待补充线索", report)
                self.assertIn("## 接下来关注", report)


if __name__ == "__main__":
    unittest.main()
