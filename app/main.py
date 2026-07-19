from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

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
    "宏观与政策": ["美联储", "降息", "加息", "利率", "央行", "国债收益率", "通胀", "就业", "cpi", "非农"],
    "中国资产": ["a股", "港股", "中国", "沪深300", "恒生", "上证", "内需"],
    "美股": ["标普", "纳指", "美股", "s&p", "nasdaq", "道指"],
    "贵金属": ["黄金", "白银", "金价", "gold"],
    "工业金属": ["铜", "铝", "锂", "comex", "lme"],
    "加密市场": ["btc", "bitcoin", "比特币", "eth", "ethereum", "以太坊", "资金费率"],
    "AI与科技": ["ai", "人工智能", "半导体", "芯片", "数据中心", "服务器", "科技公司"],
    "事件日历": ["今晚关注", "即将公布", "将公布", "经济日历", "会议日程"],
}

TOPIC_ORDER = ["宏观与政策", "中国资产", "美股", "贵金属", "工业金属", "加密市场", "AI与科技", "其他"]
OPINION_MARKERS = ("认为", "预计", "判断", "观点", "可能", "看多", "看空", "建议", "情景分析")
FORWARD_MARKERS = ("今晚", "明日", "本周", "即将", "将公布", "将举行", "后续关注", "日程")
HIGH_IMPACT_MARKERS = (
    "美联储", "央行", "利率决议", "关税", "监管", "正式宣布", "突发", "撤回", "下调", "上调", "政策", "调查", "cpi", "非农"
)
OFFICIAL_PLATFORMS = {"official"}
SOURCE_WEIGHTS = {"official": 4, "data": 3, "media": 2, "research": 2, "social": 1, "metadata": 0, "manual": 1}
EVENT_ANCHOR_KEYWORDS = (
    "美联储", "通胀", "降息", "加息", "利率", "扩大内需", "设备更新", "消费",
    "铜", "贸易调查", "精炼铜", "关税", "税率", "黄金", "央行购金", "美元",
    "实际利率", "比特币", "btc", "资金费率", "etf", "ai", "人工智能",
    "服务器", "芯片", "数据中心", "港股", "a股", "互联网", "消费者信心", "非农", "cpi",
)
CORRECTION_MARKERS = ("更正", "此前报道", "修正")
NOVELTY_MARKERS = ("盘中", "上涨", "下跌", "成交", "流入", "流出", "订单", "交付")
SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?；;])\s*|\n+")


@dataclass(slots=True)
class ItemInput:
    source: str
    title: str
    content: str
    url: str | None = None
    published_at: str | None = None
    platform: str = "manual"


@dataclass(slots=True)
class EventView:
    id: int
    title: str
    topic: str
    nature: str
    facts: list[str]
    summary: str
    importance: int
    source_count: int
    sources: list[tuple[str, str | None]]
    item_ids: list[int]
    is_forward: bool
    has_full_text: bool


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    if "facts_json" not in _column_names(conn, "analyses"):
        conn.execute("ALTER TABLE analyses ADD COLUMN facts_json TEXT NOT NULL DEFAULT '[]'")
    if "report_date" not in _column_names(conn, "clusters"):
        conn.execute("ALTER TABLE clusters ADD COLUMN report_date TEXT")
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
        result.append(ItemInput(
            source=str(row.get("source") or "Unknown"),
            title=normalize_text(str(row["title"])),
            content=normalize_text(str(row.get("content") or "")),
            url=row.get("url"),
            published_at=row.get("published_at"),
            platform=str(row.get("platform") or "manual"),
        ))
    return result


def import_items(conn: sqlite3.Connection, inputs: list[ItemInput]) -> tuple[int, int]:
    inserted = 0
    duplicates = 0
    for item in inputs:
        conn.execute("INSERT OR IGNORE INTO sources(name, platform) VALUES (?, ?)", (item.source, item.platform))
        source_id = conn.execute(
            "SELECT id FROM sources WHERE name = ? AND platform = ?", (item.source, item.platform)
        ).fetchone()["id"]
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO items(source_id, title, content, url, published_at, content_hash)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source_id, item.title, item.content, item.url, item.published_at, make_hash(item.title, item.content)),
        )
        if cursor.rowcount:
            inserted += 1
        else:
            duplicates += 1
    conn.commit()
    return inserted, duplicates


def resolve_input_item_ids(conn: sqlite3.Connection, inputs: Iterable[ItemInput]) -> list[int]:
    hashes = {make_hash(item.title, item.content) for item in inputs}
    if not hashes:
        return []
    placeholders = ",".join("?" for _ in hashes)
    rows = conn.execute(
        f"SELECT id FROM items WHERE content_hash IN ({placeholders}) ORDER BY id", tuple(hashes)
    ).fetchall()
    return [row["id"] for row in rows]


def find_labels(text: str, mapping: dict[str, list[str]]) -> list[str]:
    lowered = text.lower()
    return [label for label, keywords in mapping.items() if any(keyword.lower() in lowered for keyword in keywords)]


def rank_topics(title: str, content: str) -> list[str]:
    title_lower = title.lower()
    content_lower = content.lower()
    scores: list[tuple[int, int, str]] = []
    for order, (label, keywords) in enumerate(TOPIC_KEYWORDS.items()):
        score = 0
        for keyword in keywords:
            key = keyword.lower()
            score += title_lower.count(key) * 3
            score += content_lower.count(key)
        if score:
            scores.append((score, -order, label))
    scores.sort(reverse=True)
    return [label for _, _, label in scores] or ["其他"]


def title_features(title: str) -> set[str]:
    """Return English words plus Chinese bigrams for lightweight matching."""
    lowered = title.lower()
    features = set(re.findall(r"[a-z0-9][a-z0-9._%-]+", lowered))
    for chunk in re.findall(r"[\u4e00-\u9fff]+", lowered):
        if len(chunk) == 1:
            features.add(chunk)
        else:
            features.update(chunk[index:index + 2] for index in range(len(chunk) - 1))
    return features


def similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def event_anchors(text: str) -> set[str]:
    lowered = text.lower()
    return {keyword for keyword in EVENT_ANCHOR_KEYWORDS if keyword.lower() in lowered}


def _clean_sentence(sentence: str) -> str:
    return normalize_text(sentence).strip("•-—· ")


def _sentence_signature(sentence: str) -> set[str]:
    return title_features(re.sub(r"[，。；：、“”‘’（）()]", "", sentence))


def dedupe_sentences(sentences: Iterable[str], threshold: float = 0.55) -> list[str]:
    kept: list[str] = []
    signatures: list[set[str]] = []
    anchors_list: list[set[str]] = []
    for raw in sentences:
        sentence = _clean_sentence(raw)
        if len(sentence) < 8:
            continue
        signature = _sentence_signature(sentence)
        anchors = event_anchors(sentence)
        correction = any(marker in sentence for marker in CORRECTION_MARKERS)
        duplicate = False
        for existing_sentence, existing_signature, existing_anchors in zip(kept, signatures, anchors_list):
            numbers = set(re.findall(r"\d+(?:\.\d+)?%?", sentence))
            existing_numbers = set(re.findall(r"\d+(?:\.\d+)?%?", existing_sentence))
            if numbers and existing_numbers and numbers != existing_numbers:
                continue
            if similarity(signature, existing_signature) >= threshold:
                duplicate = True
                break
            overlap = anchors & existing_anchors
            adds_market_detail = any(marker in sentence for marker in NOVELTY_MARKERS) and not any(
                marker in existing_sentence for marker in NOVELTY_MARKERS
            )
            if len(overlap) >= 3 and not correction and not adds_market_detail:
                duplicate = True
                break
        if duplicate:
            continue
        kept.append(sentence)
        signatures.append(signature)
        anchors_list.append(anchors)
    return kept


def extract_facts(title: str, content: str, nature: str) -> list[str]:
    if not content:
        return []
    sentences = [_clean_sentence(part) for part in SENTENCE_SPLIT.split(content) if _clean_sentence(part)]
    if nature == "fact":
        candidates = [sentence for sentence in sentences if not any(marker in sentence for marker in OPINION_MARKERS)]
        if not candidates:
            candidates = sentences
    else:
        candidates = sentences
    return dedupe_sentences(candidates)[:4]


def _base_importance(text: str, topics: list[str], assets: list[str], platform: str) -> int:
    score = 2
    lowered = text.lower()
    if any(marker.lower() in lowered for marker in HIGH_IMPACT_MARKERS):
        score += 1
    if platform in OFFICIAL_PLATFORMS:
        score += 1
    if len(assets) >= 2 or len(topics) >= 2:
        score += 1
    if platform == "metadata":
        score -= 1
    return max(1, min(score, 5))


def analyze_item(title: str, content: str, platform: str = "manual") -> dict[str, Any]:
    text = f"{title} {content}"
    topics = rank_topics(title, content)
    assets = find_labels(text, ASSET_KEYWORDS)
    nature = "opinion" if any(marker in text.lower() for marker in OPINION_MARKERS) else "fact"
    facts = extract_facts(title, content, nature)
    summary_source = facts[0] if facts else (content or title)
    summary = summary_source[:220] + ("…" if len(summary_source) > 220 else "")
    return {
        "summary": summary,
        "facts": facts,
        "nature": nature,
        "topics": topics,
        "assets": assets,
        "importance": _base_importance(text, topics, assets, platform),
    }


def analyze_pending(conn: sqlite3.Connection, item_ids: list[int] | None = None) -> int:
    params: list[Any] = []
    where = "a.item_id IS NULL"
    if item_ids is not None:
        if not item_ids:
            return 0
        placeholders = ",".join("?" for _ in item_ids)
        where += f" AND i.id IN ({placeholders})"
        params.extend(item_ids)
    rows = conn.execute(
        f"""
        SELECT i.id, i.title, i.content, s.platform
        FROM items i
        JOIN sources s ON s.id = i.source_id
        LEFT JOIN analyses a ON a.item_id = i.id
        WHERE {where}
        ORDER BY i.id
        """,
        params,
    ).fetchall()
    for row in rows:
        result = analyze_item(row["title"], row["content"], row["platform"])
        conn.execute(
            """
            INSERT INTO analyses(item_id, summary, facts_json, nature, topics_json, assets_json, importance)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"], result["summary"], json.dumps(result["facts"], ensure_ascii=False),
                result["nature"], json.dumps(result["topics"], ensure_ascii=False),
                json.dumps(result["assets"], ensure_ascii=False), result["importance"],
            ),
        )
    conn.commit()
    return len(rows)


def _event_features(title: str, facts: list[str]) -> set[str]:
    return title_features(f"{title} {' '.join(facts[:2])}")


def _choose_event_title(items: list[sqlite3.Row]) -> str:
    def score(row: sqlite3.Row) -> tuple[int, int, int]:
        return SOURCE_WEIGHTS.get(row["platform"], 1), 1 if row["content"] else 0, -abs(len(row["title"]) - 22)
    return max(items, key=score)["title"]


def _cluster_score(items: list[sqlite3.Row], base_importance: int, topic: str) -> int:
    platforms = {row["platform"] for row in items}
    sources = {row["source_name"] for row in items}
    has_body = any(bool(row["content"]) for row in items)
    score = base_importance
    if len(sources) >= 2:
        score += 1
    if platforms & OFFICIAL_PLATFORMS:
        score += 1
    if topic == "事件日历":
        score = min(score, 3)
    if not has_body:
        score -= 1
    return max(1, min(score, 5))


def cluster_items(conn: sqlite3.Connection, item_ids: list[int] | None = None, report_date: str | None = None) -> int:
    if report_date is None:
        conn.execute("DELETE FROM clusters")
    else:
        conn.execute("DELETE FROM clusters WHERE report_date = ?", (report_date,))
    params: list[Any] = []
    where = ""
    if item_ids is not None:
        if not item_ids:
            conn.commit()
            return 0
        placeholders = ",".join("?" for _ in item_ids)
        where = f"WHERE i.id IN ({placeholders})"
        params.extend(item_ids)
    rows = conn.execute(
        f"""
        SELECT i.id, i.title, i.content, i.url, i.published_at,
               a.summary, a.facts_json, a.nature, a.topics_json, a.importance,
               s.name AS source_name, s.platform
        FROM items i
        JOIN analyses a ON a.item_id = i.id
        JOIN sources s ON s.id = i.source_id
        {where}
        ORDER BY a.importance DESC, i.id
        """,
        params,
    ).fetchall()
    clusters: list[dict[str, Any]] = []
    for row in rows:
        topics = json.loads(row["topics_json"])
        topic_key = topics[0] if topics else "其他"
        facts = json.loads(row["facts_json"])
        features = _event_features(row["title"], facts)
        target = None
        for cluster in clusters:
            same_topic = cluster["topic_key"] == topic_key
            same_kind = cluster["nature"] == row["nature"]
            title_close = similarity(title_features(row["title"]), cluster["title_features"]) >= 0.22
            event_close = similarity(features, cluster["features"]) >= 0.32
            anchors = event_anchors(f"{row['title']} {' '.join(facts)}")
            anchor_overlap = anchors & cluster["anchors"]
            correction = any(marker in row["title"] for marker in CORRECTION_MARKERS)
            anchor_close = len(anchor_overlap) >= 3 or (correction and len(anchor_overlap) >= 2)
            if same_topic and same_kind and (title_close or event_close or anchor_close):
                target = cluster
                break
        if target is None:
            clusters.append({
                "topic_key": topic_key,
                "nature": row["nature"],
                "items": [row],
                "features": set(features),
                "title_features": title_features(row["title"]),
                "anchors": event_anchors(f"{row['title']} {' '.join(facts)}"),
            })
        else:
            target["items"].append(row)
            target["features"].update(features)
            target["title_features"].update(title_features(row["title"]))
            target["anchors"].update(event_anchors(f"{row['title']} {' '.join(facts)}"))
    for cluster in clusters:
        items = cluster["items"]
        event_facts = dedupe_sentences(fact for item in items for fact in json.loads(item["facts_json"]))[:4]
        title = _choose_event_title(items)
        summary = event_facts[0] if event_facts else next((item["summary"] for item in items if item["summary"]), title)
        importance = _cluster_score(items, max(item["importance"] for item in items), cluster["topic_key"])
        conn.execute(
            """
            INSERT INTO clusters(title, topic_key, summary, importance, item_ids_json, report_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, cluster["topic_key"], summary, importance, json.dumps([item["id"] for item in items]), report_date),
        )
    conn.commit()
    return len(clusters)


def _cluster_rows(conn: sqlite3.Connection, report_date: str | None) -> list[sqlite3.Row]:
    if report_date is None:
        return conn.execute("SELECT * FROM clusters ORDER BY importance DESC, id").fetchall()
    return conn.execute(
        "SELECT * FROM clusters WHERE report_date = ? ORDER BY importance DESC, id", (report_date,)
    ).fetchall()


def _load_event(conn: sqlite3.Connection, cluster: sqlite3.Row) -> EventView:
    item_ids = json.loads(cluster["item_ids_json"])
    placeholders = ",".join("?" for _ in item_ids)
    rows = conn.execute(
        f"""
        SELECT i.id, i.title, i.content, i.url, i.published_at, a.facts_json, a.nature,
               s.name AS source_name, s.platform
        FROM items i
        JOIN analyses a ON a.item_id = i.id
        JOIN sources s ON s.id = i.source_id
        WHERE i.id IN ({placeholders})
        ORDER BY CASE s.platform WHEN 'official' THEN 0 WHEN 'data' THEN 1 WHEN 'media' THEN 2
                 WHEN 'research' THEN 3 WHEN 'social' THEN 4 ELSE 5 END, i.id
        """,
        item_ids,
    ).fetchall()
    facts = dedupe_sentences(fact for row in rows for fact in json.loads(row["facts_json"]))[:4]
    nature_counts: dict[str, int] = {}
    for row in rows:
        nature_counts[row["nature"]] = nature_counts.get(row["nature"], 0) + 1
    nature = max(nature_counts, key=nature_counts.get) if nature_counts else "fact"
    seen_sources: set[tuple[str, str | None]] = set()
    sources: list[tuple[str, str | None]] = []
    for row in rows:
        source = (row["source_name"], row["url"])
        if source not in seen_sources:
            seen_sources.add(source)
            sources.append(source)
    searchable = f"{cluster['title']} {' '.join(facts)}"
    is_forward = cluster["topic_key"] == "事件日历" or any(marker in searchable for marker in FORWARD_MARKERS)
    return EventView(
        id=cluster["id"], title=cluster["title"], topic=cluster["topic_key"], nature=nature,
        facts=facts, summary=cluster["summary"], importance=cluster["importance"],
        source_count=len(sources), sources=sources, item_ids=item_ids, is_forward=is_forward,
        has_full_text=any(bool(row["content"]) for row in rows),
    )


def load_events(conn: sqlite3.Connection, report_date: str | None) -> list[EventView]:
    return [_load_event(conn, cluster) for cluster in _cluster_rows(conn, report_date)]


def _event_sort_key(event: EventView) -> tuple[int, int, int, int]:
    return event.importance, event.source_count, 1 if event.nature == "fact" else 0, 1 if event.has_full_text else 0


def _source_text(event: EventView) -> str:
    return "；".join(f"[{name}]({url})" if url else name for name, url in event.sources)


def _render_event(event: EventView, heading_level: int = 3, number: int | None = None) -> list[str]:
    prefix = f"{number}. " if number is not None else ""
    lines = [f"{'#' * heading_level} {prefix}{event.title}", ""]
    if event.nature == "opinion":
        lines.extend(["**原文观点**", ""])
    if event.facts:
        lines.extend(f"- {fact}" for fact in event.facts)
    elif event.has_full_text:
        lines.append(event.summary)
    else:
        lines.append("- 仅获取到标题，正文与关键事实仍待补充。")
    lines.extend(["", f"来源（{event.source_count}）：{_source_text(event)}", ""])
    return lines


def render_report(conn: sqlite3.Connection, report_date: str) -> str:
    events = load_events(conn, report_date)
    forward_events = sorted([event for event in events if event.is_forward], key=_event_sort_key, reverse=True)
    ranked = sorted([event for event in events if not event.is_forward], key=_event_sort_key, reverse=True)
    top_events = ranked[:5]
    top_ids = {event.id for event in top_events}
    remaining = [event for event in ranked if event.id not in top_ids and event.importance >= 2]
    low_confidence = [event for event in ranked if event.id not in top_ids and (event.importance < 2 or not event.has_full_text)]
    item_count = sum(len(event.item_ids) for event in events)
    lines = [
        f"# 今日跨资产日报｜{report_date}", "",
        f"> 本期整理 {item_count} 条有效内容，合并为 {len(events)} 个事件。", "",
        "## 今日重点", "",
    ]
    if top_events:
        for index, event in enumerate(top_events, start=1):
            lines.extend(_render_event(event, heading_level=3, number=index))
    else:
        lines.extend(["- 今日暂无达到重点级别的完整事件。", ""])
    lines.extend(["## 分类浏览", ""])
    sections: dict[str, list[EventView]] = {}
    for event in remaining:
        sections.setdefault(event.topic, []).append(event)
    rendered_section = False
    for topic in TOPIC_ORDER:
        topic_events = sections.get(topic, [])
        if not topic_events:
            continue
        rendered_section = True
        lines.extend([f"### {topic}", ""])
        for event in topic_events:
            lines.extend(_render_event(event, heading_level=4))
    if not rendered_section:
        lines.extend(["- 今日其他信息已全部纳入“今日重点”。", ""])
    if low_confidence:
        lines.extend(["## 待补充线索", ""])
        for event in low_confidence:
            lines.extend(_render_event(event, heading_level=3))

    lines.extend(["## 接下来关注", ""])
    if forward_events:
        for event in forward_events:
            lines.extend(_render_event(event, heading_level=3))
    else:
        lines.extend(["- 当前输入中没有明确的后续日程信息。", ""])
    lines.extend([
        "## 编辑说明", "",
        "- 本报告只整理输入中明确出现的事实与原文观点，不补写未经来源支持的解释。",
        "- 仅有标题、缺少正文的内容会明确标注，不进入高优先级事实摘要。", "",
    ])
    return "\n".join(lines)


def save_report(conn: sqlite3.Connection, report_date: str, markdown: str, output_dir: Path) -> Path:
    conn.execute(
        """
        INSERT INTO reports(report_date, report_type, markdown) VALUES (?, 'evening', ?)
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
    inputs = load_inputs(input_path)
    with connect(db_path) as conn:
        init_db(conn)
        inserted, duplicates = import_items(conn, inputs)
        current_item_ids = resolve_input_item_ids(conn, inputs)
        analyzed = analyze_pending(conn, current_item_ids)
        cluster_count = cluster_items(conn, current_item_ids, report_date)
        markdown = render_report(conn, report_date)
        report_path = save_report(conn, report_date, markdown, output_dir)
    print(
        f"Imported={inserted}, duplicates={duplicates}, analyzed={analyzed}, "
        f"clusters={cluster_count}, report={report_path}"
    )
    return report_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a curated cross-asset daily report")
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
