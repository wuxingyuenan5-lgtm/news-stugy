from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from common import (
    TimeWindow,
    build_time_window,
    classify_asset,
    dump_json,
    filter_posts,
    is_low_signal,
    load_json,
    parse_post_time,
    signal_score,
)


DEFAULT_SOURCE_DIR = Path(r"C:\Users\jiuxi\Desktop\codex\AI投研和skills\x-tweet-fetcher\scripts")


def _search_index_query(user: str) -> str:
    return f"from:{user} site:x.com/{user}/status"


def _extract_status_url_from_search(content: str, user: str) -> str:
    direct = re.search(
        rf"\(https://x\.com/{re.escape(user)}/status/(\d+)\)",
        content,
        flags=re.IGNORECASE,
    )
    if direct:
        return f"https://x.com/{user}/status/{direct.group(1)}"
    breadcrumb = re.search(
        rf"https://x\.com›{re.escape(user)}\s*›\s*status\s*›\s*(\d+)",
        content,
        flags=re.IGNORECASE,
    )
    if breadcrumb:
        return f"https://x.com/{user}/status/{breadcrumb.group(1)}"
    return ""


def _recover_status_url(user: str, text: str) -> str:
    core = re.split(r"[。！？!?]", (text or "").strip())[0].strip()
    if not core:
        return ""
    query = f"site:x.com/{user}/status {core[:28]}"
    url = "https://r.jina.ai/http://duckduckgo.com/?" + urllib.parse.urlencode({"q": query, "df": "w"})
    request = urllib.request.Request(url, headers={"User-Agent": "x-fetch/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            content = response.read().decode("utf-8", errors="replace")
    except Exception:
        return ""
    return _extract_status_url_from_search(content, user)


def _load_nitter_client(source_dir: Path):
    sys.path.insert(0, str(source_dir))
    try:
        import nitter_client  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(f"Failed to import nitter_client from {source_dir}: {exc}")
    return nitter_client


def _resolve_users(args: argparse.Namespace) -> List[str]:
    users: List[str] = []
    if args.users:
        users.extend([part.strip().lstrip("@") for part in args.users.split(",") if part.strip()])
    if args.targets:
        payload = load_json(Path(args.targets))
        users.extend([str(user).strip().lstrip("@") for user in payload.get("users", []) if str(user).strip()])
    deduped: List[str] = []
    seen = set()
    for user in users:
        if user and user not in seen:
            deduped.append(user)
            seen.add(user)
    if not deduped:
        raise SystemExit("No users provided. Use --users or --targets.")
    return deduped


def _normalize_tweet(user: str, tweet: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    raw_time = tweet.get("time", "") or tweet.get("published_at", "") or tweet.get("time_ago", "")
    parsed = parse_post_time(raw_time, now=now)
    text = (tweet.get("text") or "").strip()
    post_id = tweet.get("tweet_id", "")
    post_url = tweet.get("url") or (f"https://x.com/{user}/status/{post_id}" if post_id else "")
    return {
        "author": user,
        "post_id": post_id,
        "post_url": post_url,
        "published_at": parsed.astimezone(timezone.utc).isoformat() if parsed else None,
        "published_at_raw": raw_time,
        "text": text,
        "asset_class": classify_asset(text),
        "signal_score": signal_score(text),
        "low_signal": is_low_signal(text),
    }


def _fetch_via_search_index(user: str, now: datetime) -> List[Dict[str, Any]]:
    query = _search_index_query(user)
    url = "https://r.jina.ai/http://duckduckgo.com/?" + urllib.parse.urlencode({"q": query, "df": "w"})
    request = urllib.request.Request(url, headers={"User-Agent": "x-fetch/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            content = response.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    lines = content.splitlines()
    results: List[Dict[str, Any]] = []
    for line in lines:
        stripped = line.strip()
        if not re.match(r"^\d+\.\s+x\.com\b", stripped, flags=re.IGNORECASE):
            continue
        time_match = re.search(r"(\d+\s+(?:second|minute|hour|day|week|month|year)s?\s+ago)", stripped, flags=re.IGNORECASE)
        text_match = re.search(rf"@(?:\*\*)?{re.escape(user)}(?:\*\*)?\)\.\s+(.*)", stripped, flags=re.IGNORECASE)
        snippet = text_match.group(1).strip() if text_match else stripped
        snippet = re.sub(
            r"^\d+\s+likes?(?:\s+\d+\s+replies?)?(?:\s+\d+\s+views?)?\.\s*",
            "",
            snippet,
            flags=re.IGNORECASE,
        )
        snippet = re.sub(r"^\d+\s+views?\.\s*", "", snippet, flags=re.IGNORECASE)
        results.append(
            {
                "tweet_id": "",
                "url": "",
                "time": time_match.group(1) if time_match else "",
                "text": snippet,
            }
        )
    return results


def fetch_posts(users: List[str], window: TimeWindow, limit: int, source_dir: Path) -> Dict[str, Any]:
    nitter_client = _load_nitter_client(source_dir)
    now = datetime.now(timezone.utc)
    all_posts: List[Dict[str, Any]] = []

    for user in users:
        raw_tweets = nitter_client.fetch_timeline(user, count=limit)
        if not raw_tweets:
            raw_tweets = _fetch_via_search_index(user, now)
        for tweet in raw_tweets:
            all_posts.append(_normalize_tweet(user, tweet, now))

    recover_budget = 5
    for post in all_posts:
        if recover_budget <= 0:
            break
        if post.get("post_url") or post.get("low_signal"):
            continue
        recovered = _recover_status_url(post["author"], post.get("text", ""))
        if recovered:
            post["post_url"] = recovered
            post["post_id"] = recovered.rstrip("/").split("/")[-1]
        recover_budget -= 1

    filtered = filter_posts(all_posts, window)
    unknown_time_count = sum(1 for post in all_posts if not post.get("published_at"))
    return {
        "generated_at": now.isoformat(),
        "window": {
            "start": window.start.isoformat(),
            "end": window.end.isoformat(),
        },
        "users": users,
        "total_fetched": len(all_posts),
        "unknown_time_count": unknown_time_count,
        "posts": filtered,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch recent X posts for one or more users with a light, deterministic pipeline.")
    parser.add_argument("--users", help="Comma-separated usernames without @")
    parser.add_argument("--targets", help="Path to a targets JSON file")
    parser.add_argument("--hours", type=int, help="Window length in hours")
    parser.add_argument("--days", type=int, help="Window length in days")
    parser.add_argument("--start", help="Window start in ISO format")
    parser.add_argument("--end", help="Window end in ISO format")
    parser.add_argument("--limit", type=int, default=40, help="Timeline fetch limit per user")
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR), help="Directory containing nitter_client.py")
    parser.add_argument("--output", help="Optional output JSON path")
    args = parser.parse_args()

    users = _resolve_users(args)
    window = build_time_window(hours=args.hours, days=args.days, start=args.start, end=args.end)
    payload = fetch_posts(users, window, args.limit, Path(args.source_dir))

    if args.output:
        dump_json(Path(args.output), payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
