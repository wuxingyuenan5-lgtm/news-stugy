from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.main import (
    analyze_item,
    cluster_items,
    connect,
    import_items,
    init_db,
    load_inputs,
    similarity,
    title_features,
)


ROOT = Path(__file__).resolve().parents[1]


class MvpSmokeTest(unittest.TestCase):
    def test_chinese_title_similarity(self) -> None:
        left = title_features("美联储官员称降息前需要更多通胀证据")
        right = title_features("美联储官员：通胀改善后再考虑降息")
        self.assertGreaterEqual(similarity(left, right), 0.38)

    def test_opinion_is_labeled(self) -> None:
        result = analyze_item("策略师看多黄金", "策略师认为金价可能继续上涨")
        self.assertEqual(result["nature"], "opinion")
        self.assertIn("黄金", result["assets"])

    def test_sample_pipeline_imports_and_clusters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "test.db"
            with connect(db_path) as conn:
                init_db(conn)
                inserted, duplicates = import_items(
                    conn, load_inputs(ROOT / "examples" / "market_day_items.json")
                )
                self.assertEqual(inserted, 17)
                self.assertEqual(duplicates, 1)

                # Populate analyses with the same lightweight analyzer used by the CLI.
                rows = conn.execute("SELECT id, title, content FROM items ORDER BY id").fetchall()
                for row in rows:
                    result = analyze_item(row["title"], row["content"])
                    conn.execute(
                        """
                        INSERT INTO analyses(item_id, summary, nature, topics_json, assets_json, importance)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row["id"],
                            result["summary"],
                            result["nature"],
                            __import__("json").dumps(result["topics"], ensure_ascii=False),
                            __import__("json").dumps(result["assets"], ensure_ascii=False),
                            result["importance"],
                        ),
                    )
                conn.commit()
                count = cluster_items(conn)
                self.assertGreater(count, 8)
                self.assertLess(count, inserted)


if __name__ == "__main__":
    unittest.main()
