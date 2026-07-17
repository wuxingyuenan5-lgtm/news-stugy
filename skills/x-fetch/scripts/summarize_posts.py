from __future__ import annotations

import argparse
from pathlib import Path

from common import dump_json, is_low_signal, load_json, render_card, render_grouped, render_timeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Render low-token X creator summaries from normalized JSON.")
    parser.add_argument("--input", required=True, help="Path to normalized fetch JSON")
    parser.add_argument("--mode", choices=["timeline", "grouped", "card"], default="timeline")
    parser.add_argument("--include-low-signal", action="store_true", help="Keep low-signal posts in the rendered output")
    parser.add_argument("--output", help="Optional output path. Defaults to stdout.")
    parser.add_argument("--output-json", help="Optional filtered JSON output path.")
    args = parser.parse_args()

    payload = load_json(Path(args.input))
    posts = payload.get("posts", [])
    if not args.include_low_signal:
        posts = [post for post in posts if not post.get("low_signal", False) and not is_low_signal(post.get("text", ""))]
    payload["posts"] = posts

    if args.output_json:
        dump_json(Path(args.output_json), payload)

    if args.mode == "timeline":
        rendered = render_timeline(payload)
    elif args.mode == "grouped":
        rendered = render_grouped(payload)
    else:
        rendered = render_card(payload)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8-sig")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
