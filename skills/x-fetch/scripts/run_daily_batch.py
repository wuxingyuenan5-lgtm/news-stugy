from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from common import build_time_window, dump_json, load_json, render_timeline
from fetch_x_posts import DEFAULT_SOURCE_DIR, fetch_posts


def parse_targets_config(path: Path) -> Dict[str, Any]:
    payload = load_json(path)
    raw_users = payload.get("users", [])
    users: List[str] = []
    user_settings: Dict[str, Dict[str, Any]] = {}
    for item in raw_users:
        if isinstance(item, str):
            username = item.strip().lstrip("@")
            if username:
                users.append(username)
        elif isinstance(item, dict):
            username = str(item.get("username", "")).strip().lstrip("@")
            if username:
                users.append(username)
                user_settings[username] = {
                    "include_replies": bool(item.get("include_replies", payload.get("include_replies", False))),
                }
    return {
        "users": users,
        "user_settings": user_settings,
        "limit_per_user": int(payload.get("limit_per_user", 30)),
        "default_window": payload.get("default_window", {"days": 1}),
        "include_replies": bool(payload.get("include_replies", False)),
    }


def post_state_key(post: Dict[str, Any]) -> str:
    return f"{post.get('author','')}|{post.get('post_id') or post.get('published_at_raw') or post.get('text','')[:80]}"


def compute_incremental_posts(current: Dict[str, Any], state: Dict[str, Any]) -> List[Dict[str, Any]]:
    seen = set(state.get("seen_keys", []))
    return [post for post in current.get("posts", []) if post_state_key(post) not in seen]


def update_state(state_path: Path, current: Dict[str, Any]) -> Dict[str, Any]:
    existing = load_json(state_path) if state_path.exists() else {"seen_keys": []}
    seen = set(existing.get("seen_keys", []))
    for post in current.get("posts", []):
        seen.add(post_state_key(post))
    updated = {"seen_keys": sorted(seen)}
    dump_json(state_path, updated)
    return updated


def filter_posts_for_targets(posts: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    user_settings = config.get("user_settings", {})
    default_include_replies = bool(config.get("include_replies", False))
    kept: List[Dict[str, Any]] = []
    for post in posts:
        user = post.get("author", "")
        include_replies = user_settings.get(user, {}).get("include_replies", default_include_replies)
        if not include_replies and str(post.get("text", "")).strip().startswith("@"):
            continue
        kept.append(post)
    return kept


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a light daily batch for tracked X users.")
    parser.add_argument("--targets", required=True, help="Path to targets JSON")
    parser.add_argument("--days", type=int, help="Window length in days")
    parser.add_argument("--limit", type=int, help="Fetch limit per user")
    parser.add_argument("--output-dir", required=True, help="Output directory for batch files")
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR), help="Directory containing nitter_client.py")
    parser.add_argument("--state-file", help="Optional JSON state file for incremental output")
    args = parser.parse_args()

    config = parse_targets_config(Path(args.targets))
    users = config["users"]
    if not users:
        raise SystemExit("No users found in targets file.")

    default_window = config.get("default_window", {"days": 1})
    days = args.days if args.days is not None else int(default_window.get("days", 1))
    limit = args.limit if args.limit is not None else int(config.get("limit_per_user", 30))
    window = build_time_window(days=days)
    result = fetch_posts(users, window, limit, Path(args.source_dir))
    result["posts"] = filter_posts_for_targets(result.get("posts", []), config)

    if args.state_file:
        state_path = Path(args.state_file)
        prior_state = load_json(state_path) if state_path.exists() else {"seen_keys": []}
        incremental_posts = compute_incremental_posts(result, prior_state)
        update_state(state_path, result)
        result["posts"] = incremental_posts
        result["incremental_only"] = True

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"x-fetch-{stamp}.json"
    md_path = output_dir / f"x-fetch-{stamp}.md"

    dump_json(json_path, result)
    md_path.write_text(render_timeline({**result, "posts": [post for post in result["posts"] if not post.get("low_signal", False)]}), encoding="utf-8-sig")

    print(str(json_path))
    print(str(md_path))


if __name__ == "__main__":
    main()
