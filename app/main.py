from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "app.db"
DEFAULT_INPUT = ROOT / "examples" / "sample_items.json"
DEFAULT_REPORT_DIR = ROOT / "data" / "reports"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")

ASSET_KEYWORDS = {
    "黄金": ["黄金", "金价", "gold", "xau"],
    "美股": ["标普", "纳指", "美股", "s&p", "nasdaq"],
    "A股": ["a股", "沪深300", "上证", "创业板"],
    "港股": ["港股", "恒生"],
    "加密": ["btc", "bitcoin", "比特币", "eth", "ethereum", "以太坊"],
    "铜": ["铜", "copper", "comex", "lme"],
    "利率": ["美联储", "降息", "加息", "利率", "国债收益率", "fed"],
}

TOPIC_KEYWORDS = {
    "货币政策": ["美联储", "降息", "加息", "利率", "央行"],
    "中国资产": ["a股", "港股", "中国", "沪深300", "恒生"],
    "贵金属": ["黄金", "白银", "金价"],
    "加密市场": ["btc", "bitcoin", "比特币", "eth", "以太坊"],
    "工业金属": ["铜", "铝", "锂", "comex", "lme"],
    "科技与AI": ["ai", "人工智能", "半导体", "芯片", "数据中心"],
}


@dataclass(slots=True)
class ItemInput:
    source: str
    title: str
    content: str
    url: str | None = None
    published_at: str | None = None
    platform: str = "manual"


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def make_hash(title: str, content: str) -> str:
    raw = f"{normalize_text(title).lower()}\n{normalize_text(content).lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_inputs(path: Path) -> list[ItemInput]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Input JSON must be a list of items")
    result: list[ItemInput] = []
    for index, row in enumerate(payload, start=1):
        if not isinstance(row, dict) or not row.get("title"):
            raise ValueError(f"Item {index} must contain a title")
        result.append(
            ItemInput(
                source=str(row.get("source") or "Unknown"),
                title=normalize_text(str(row["title"])),
                content=normalize_text(str(row.get("content") or "")),
                url=row.get("url"),
                published_at=row.get("published_at"),
                platform=str(row.get("platform") or "manual"),
            )
        )
    return result


def import_items(conn: sqlite3.Connection, inputs: list[ItemInput]) -> tuple[int, int]:
    inserted = 0
    duplicates = 0
    for item in inputs:
        conn.execute(
            "INSERT OR IGNORE INTO sources(name, platform) VALUES (?, ?)",
            (item.source, item.platform),
        )
        source_id = conn.execute(
            "SELECT id FROM sources WHERE name = ? AND platform = ?",
            (item.source, item.platform),
        ).fetchone()["id"]
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO items(
                source_id, title, content, url, published_at, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                item.title,
                item.content,
                item.url,
                item.published_at,
                make_hash(item.title, item.content),
            ),
        )
        if cursor.rowcount:
            inserted += 1
        else:
            duplicates += 1
    conn.commit()
    return inserted, duplicates


def find_labels(text: str, mapping: dict[str, list[str]]) -> list[str]:
    lowered = text.lower()
    return [label for label, keywords in mapping.items() if any(k.lower() in lowered for k in keywords)]


def analyze_item(title: str, content: str) -> dict[str, Any]:
    text = f"{title} {content}"
    topics = find_labels(text, TOPIC_KEYWORDS) or ["其他"]
    assets = find_labels(text, ASSET_KEYWORDS)
    lowered = text.lower()
    opinion_markers = ["认为", "预计", "判断", "观点", "可能", "看多", "看空"]
    nature = "opinion" if any(marker in lowered for marker in opinion_markers) else "fact"
    importance = 3
    if any(marker in lowered for marker in ["央行", "美联储", "关税", "监管", "正式宣布", "突发"]):
        importance += 1
    if len(assets) >= 2 or len(topics) >= 2:
        importance += 1
    importance = min(importance, 5)
    summary_source = content or title
    summary = summary_source[:220] + ("…" if len(summary_source) > 220 else "")
    return {
        "summary": summary,
        "nature": nature,
        "topics": topics,
        "assets": assets,
        "importance": importance,
    }


def analyze_pending(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT i.id, i.title, i.content
        FROM items i
        LEFT JOIN analyses a ON a.item_id = i.id
        WHERE a.item_id IS NULL
        ORDER BY i.id
        """
    ).fetchall()
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
                json.dumps(result["topics"], ensure_ascii=False),
                json.dumps(result["assets"], ensure_ascii=False),
                result["importance"],
            ),
        )
    conn.commit()
    return len(rows)


def title_tokens(title: str) -> set[str]:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", " ", title.lower())
    return {token for token in cleaned.split() if len(token) >= 2}


def cluster_items(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM clusters")
    rows = conn.execute(
        """
        SELECT i.id, i.title, a.summary, a.topics_json, a.importance
        FROM items i JOIN analyses a ON a.item_id = i.id
        ORDER BY a.importance DESC, i.id
        """
    ).fetchall()
    clusters: list[dict[str, Any]] = []
    for row in rows:
        topics = json.loads(row["topics_json"])
        topic_key = topics[0] if topics else "其他"
        tokens = title_tokens(row["title"])
        target = None
        for cluster in clusters:
            overlap = tokens & cluster["tokens"]
            if cluster["topic_key"] == topic_key and (len(overlap) >= 2 or row["title"] == cluster["title"]):
                target = cluster
                break
        if target is None:
            clusters.append(
                {
                    "title": row["title"],
                    "topic_key": topic_key,
                    "summary": row["summary"],
                    "importance": row["importance"],
                    "item_ids": [row["id"]],
                    "tokens": tokens,
                }
            )
        else:
            target["item_ids"].append(row["id"])
            target["importance"] = max(target["importance"], row["importance"])
            target["tokens"].update(tokens)
    for cluster in clusters:
        conn.execute(
            """
            INSERT INTO clusters(title, topic_key, summary, importance, item_ids_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                cluster["title"],
                cluster["topic_key"],
                cluster["summary"],
                cluster["importance"],
                json.dumps(cluster["item_ids"]),
            ),
        )
    conn.commit()
    return len(clusters)


def render_report(conn: sqlite3.Connection, report_date: str) -> str:
    clusters = conn.execute(
        "SELECT * FROM clusters WHERE importance >= 3 ORDER BY importance DESC, id"
    ).fetchall()
    sections: dict[str, list[sqlite3.Row]] = {}
    for cluster in clusters:
        sections.setdefault(cluster["topic_key"], []).append(cluster)

    lines = [f"# 跨资产晚报｜{report_date}", "", "## 一、核心结论", ""]
    core = [cluster for cluster in clusters if cluster["importance"] >= 4][:5]
    if core:
        for cluster in core:
            lines.append(f"- **{cluster['title']}**：{cluster['summary']}")
    else:
        lines.append("- 今日暂无达到核心级别的新信息。")

    lines.extend(["", "## 二、重点内容", ""])
    for topic, topic_clusters in sections.items():
        lines.extend([f"### {topic}", ""])
        for cluster in topic_clusters:
            item_ids = json.loads(cluster["item_ids_json"])
            placeholders = ",".join("?" for _ in item_ids)
            sources = conn.execute(
                f"""
                SELECT s.name, i.url FROM items i
                LEFT JOIN sources s ON s.id = i.source_id
                WHERE i.id IN ({placeholders})
                """,
                item_ids,
            ).fetchall()
            source_text = "；".join(
                f"[{row['name']}]({row['url']})" if row["url"] else row["name"]
                for row in sources
            )
            lines.extend(
                [
                    f"#### {cluster['title']}",
                    "",
                    cluster["summary"],
                    "",
                    f"来源：{source_text}",
                    "",
                ]
            )

    lines.extend(
        [
            "## 三、数据完整性说明",
            "",
            "- 本报告由最小MVP流程生成，目前采用规则分析和简化聚类。",
            "- 报告只基于已导入内容，不补写输入中不存在的事实。",
            "- 重要内容仍建议在正式发布前人工复核。",
            "",
        ]
    )
    return "\n".join(lines)


def save_report(conn: sqlite3.Connection, report_date: str, markdown: str, output_dir: Path) -> Path:
    conn.execute(
        """
        INSERT INTO reports(report_date, report_type, markdown)
        VALUES (?, 'evening', ?)
        ON CONFLICT(report_date, report_type)
        DO UPDATE SET markdown = excluded.markdown, created_at = CURRENT_TIMESTAMP
        """,
        (report_date, markdown),
    )
    conn.commit()
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"evening-{report_date}.md"
    path.write_text(markdown, encoding="utf-8")
    return path


def run(input_path: Path, db_path: Path, output_dir: Path, report_date: str) -> Path:
    with connect(db_path) as conn:
        init_db(conn)
        inserted, duplicates = import_items(conn, load_inputs(input_path))
        analyzed = analyze_pending(conn)
        cluster_count = cluster_items(conn)
        markdown = render_report(conn, report_date)
        report_path = save_report(conn, report_date, markdown, output_dir)
    print(
        f"Imported={inserted}, duplicates={duplicates}, analyzed={analyzed}, "
        f"clusters={cluster_count}, report={report_path}"
    )
    return report_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a minimal cross-asset evening report")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--date", default=date.today().isoformat())
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run(args.input, args.db, args.output_dir, args.date)


if __name__ == "__main__":
    main()
