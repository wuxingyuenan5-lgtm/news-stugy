from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


UTC = timezone.utc
CST = timezone(timedelta(hours=8))

ASSET_KEYWORDS = {
    "crypto": [
        "crypto", "btc", "bitcoin", "eth", "ethereum", "sol", "solana", "meme coin",
        "stablecoin", "defi", "onchain", "on-chain", "airdrop", "token", "山寨",
        "加密", "比特币", "以太坊", "链上"
    ],
    "us-stocks": [
        "美股", "纳指", "标普", "道指", "nasdaq", "s&p", "dow", "earnings", "spy",
        "qqq", "nvidia", "tesla", "apple", "microsoft", "semis", "chip stock", "芯片股",
        "财报", "罗素2000"
    ],
    "a-shares": [
        "a股", "沪深", "上证", "深证", "创业板", "科创板", "北证", "两市", "涨停", "中证",
        "白酒", "券商", "游资"
    ],
    "macro": [
        "fed", "fomc", "cpi", "ppi", "nfp", "inflation", "recession", "treasury",
        "yield", "yields", "rates", "rate cut", "rate hike", "macro", "通胀", "非农",
        "降息", "加息", "利率", "汇率", "收益率", "国债", "美债", "衰退", "财政"
    ],
    "ai": [
        "ai", "人工智能", "大模型", "llm", "gpu", "inference", "training", "agent",
        "openai", "anthropic", "grok", "chatgpt", "tokens", "cuda", "推理", "训练",
        "模型", "算力"
    ],
}

ASSET_ORDER = ["crypto", "us-stocks", "a-shares", "macro", "ai", "other"]

LOW_SIGNAL_PATTERNS = [
    r"^@[\w_]+",
    r"^(哈哈|lol|lmao|nice|牛|是的|对|嗯|ok)[。.!！?？]*$",
]


@dataclass
class TimeWindow:
    start: datetime
    end: datetime


def parse_iso_datetime(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def build_time_window(
    *,
    hours: Optional[int] = None,
    days: Optional[int] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    now: Optional[datetime] = None,
) -> TimeWindow:
    now = (now or datetime.now(UTC)).astimezone(UTC)
    if end:
        window_end = parse_iso_datetime(end)
    else:
        window_end = now
    if start:
        window_start = parse_iso_datetime(start)
    elif hours is not None:
        window_start = window_end - timedelta(hours=hours)
    else:
        window_start = window_end - timedelta(days=days or 1)
    return TimeWindow(start=window_start, end=window_end)


def parse_post_time(raw: str, *, now: Optional[datetime] = None) -> Optional[datetime]:
    raw = (raw or "").strip()
    if not raw:
        return None

    now = (now or datetime.now(UTC)).astimezone(UTC)
    normalized = " ".join(raw.replace("·", " ").replace(",", ", ").split())
    normalized = re.sub(r"\s+", " ", normalized).strip()

    relative_match = re.fullmatch(r"(\d+)([smhdw])", normalized.lower())
    if relative_match:
        amount = int(relative_match.group(1))
        unit = relative_match.group(2)
        delta = {
            "s": timedelta(seconds=amount),
            "m": timedelta(minutes=amount),
            "h": timedelta(hours=amount),
            "d": timedelta(days=amount),
            "w": timedelta(weeks=amount),
        }[unit]
        return now - delta

    ago_match = re.fullmatch(r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago", normalized.lower())
    if ago_match:
        amount = int(ago_match.group(1))
        unit = ago_match.group(2)
        delta = {
            "second": timedelta(seconds=amount),
            "minute": timedelta(minutes=amount),
            "hour": timedelta(hours=amount),
            "day": timedelta(days=amount),
            "week": timedelta(weeks=amount),
            "month": timedelta(days=amount * 30),
            "year": timedelta(days=amount * 365),
        }[unit]
        return now - delta

    patterns = [
        ("%b %d %Y %I:%M %p UTC", UTC),
        ("%b %d, %Y %I:%M %p UTC", UTC),
        ("%b %d %Y %H:%M UTC", UTC),
        ("%Y-%m-%d %H:%M:%S%z", None),
        ("%Y-%m-%d %H:%M:%S", UTC),
        ("%Y-%m-%d %H:%M", UTC),
    ]
    for fmt, assumed_tz in patterns:
        try:
            dt = datetime.strptime(normalized, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=assumed_tz or UTC)
            return dt.astimezone(UTC)
        except ValueError:
            continue

    month_day_match = re.fullmatch(r"([A-Z][a-z]{2}) (\d{1,2})", normalized)
    if month_day_match:
        candidate = f"{month_day_match.group(1)} {month_day_match.group(2)} {now.year}"
        try:
            dt = datetime.strptime(candidate, "%b %d %Y").replace(tzinfo=UTC)
            if dt > now + timedelta(days=1):
                dt = dt.replace(year=dt.year - 1)
            return dt
        except ValueError:
            return None

    return None


def classify_asset(text: str) -> str:
    lowered = (text or "").lower()
    scores: Dict[str, int] = {}
    for asset_class, keywords in ASSET_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword.lower() in lowered:
                score += 1
        scores[asset_class] = score

    best = "other"
    best_score = 0
    for asset_class in ASSET_ORDER:
        score = scores.get(asset_class, 0)
        if score > best_score:
            best = asset_class
            best_score = score
    return best if best_score > 0 else "other"


def signal_score(text: str) -> int:
    text = (text or "").strip()
    score = 0
    if len(text) >= 20:
        score += 1
    if any(mark in text for mark in ["。", "！", "?", "？", ":", "："]):
        score += 1
    if len(text) >= 80:
        score += 1
    return score


def is_low_signal(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return True
    if len(text) < 8:
        return True
    for pattern in LOW_SIGNAL_PATTERNS:
        if re.match(pattern, text, flags=re.IGNORECASE):
            return True
    return False


def compact_summary(text: str, max_len: int = 120) -> str:
    text = " ".join((text or "").split())
    if not text:
        return ""
    first = re.split(r"[。！？!?]\s*|\n+", text)[0].strip()
    summary = first or text
    return summary if len(summary) <= max_len else summary[: max_len - 1] + "…"


def filter_posts(posts: Sequence[Dict[str, Any]], window: TimeWindow) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    for post in posts:
        published_at = post.get("published_at")
        if not published_at:
            continue
        dt = parse_iso_datetime(published_at)
        if window.start <= dt <= window.end:
            kept.append(post)
    kept.sort(key=lambda item: item["published_at"], reverse=True)
    return kept


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def format_cst(value: str) -> str:
    dt = parse_iso_datetime(value).astimezone(CST)
    return dt.strftime("%Y-%m-%d %H:%M CST")


def render_timeline(payload: Dict[str, Any]) -> str:
    lines = ["# X Timeline Summary", ""]
    window = payload.get("window", {})
    lines.append(f"- Window: {window.get('start', '')} -> {window.get('end', '')}")
    lines.append(f"- Users: {', '.join(payload.get('users', []))}")
    lines.append(f"- Posts kept: {len(payload.get('posts', []))}")
    lines.append("")

    by_author: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for post in payload.get("posts", []):
        by_author[post.get("author", "unknown")].append(post)

    for author in sorted(by_author):
        lines.append(f"## @{author}")
        lines.append("")
        for post in sorted(by_author[author], key=lambda item: item.get("published_at", ""), reverse=True):
            time_label = format_cst(post["published_at"]) if post.get("published_at") else post.get("published_at_raw", "unknown time")
            lines.append(f"- {time_label} | {post.get('asset_class', 'other')}")
            lines.append(f"  - {compact_summary(post.get('text', ''))}")
            lines.append(f"  - Source: {post.get('post_url', '')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_grouped(payload: Dict[str, Any]) -> str:
    lines = ["# X Grouped Summary", ""]
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for post in payload.get("posts", []):
        grouped[post.get("asset_class", "other")].append(post)

    for asset_class in ASSET_ORDER:
        posts = grouped.get(asset_class, [])
        if not posts:
            continue
        lines.append(f"## {asset_class}")
        lines.append("")
        for post in sorted(posts, key=lambda item: item.get("published_at", ""), reverse=True):
            lines.append(f"- @{post.get('author', '')}: {compact_summary(post.get('text', ''))}")
            lines.append(f"  - {post.get('post_url', '')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_card(payload: Dict[str, Any]) -> str:
    posts = payload.get("posts", [])
    top_posts = posts[:5]
    asset_mix = defaultdict(int)
    for post in posts:
        asset_mix[post.get("asset_class", "other")] += 1

    lines = ["# X Research Card", ""]
    lines.append(f"- Users: {', '.join(payload.get('users', []))}")
    lines.append(f"- Window: {payload.get('window', {}).get('start', '')} -> {payload.get('window', {}).get('end', '')}")
    lines.append(f"- Coverage: {len(posts)} posts")
    lines.append("")
    lines.append("## Asset Mix")
    lines.append("")
    for asset_class in ASSET_ORDER:
        if asset_mix.get(asset_class):
            lines.append(f"- {asset_class}: {asset_mix[asset_class]}")
    lines.append("")
    lines.append("## Key Posts")
    lines.append("")
    for post in top_posts:
        lines.append(f"- @{post.get('author', '')} | {post.get('asset_class', 'other')} | {compact_summary(post.get('text', ''))}")
        lines.append(f"  - {post.get('post_url', '')}")
    lines.append("")
    return "\n".join(lines)
