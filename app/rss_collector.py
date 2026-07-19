from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "rss_sources.json"
DEFAULT_OUTPUT = ROOT / "data" / "inbox" / "rss-items.json"
DEFAULT_USER_AGENT = "NewsStudy/0.1 (+https://github.com/wuxingyuenan5-lgtm/news-stugy)"
MAX_FEED_BYTES = 5 * 1024 * 1024


@dataclass(slots=True)
class RssSource:
    name: str
    url: str
    platform: str = "media"
    enabled: bool = True


class _HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def normalize_text(value: str) -> str:
    return " ".join(value.split())


def strip_html(value: str) -> str:
    parser = _HtmlTextExtractor()
    parser.feed(html.unescape(value or ""))
    parser.close()
    return normalize_text(" ".join(parser.parts))


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _first_child(element: ET.Element, names: Iterable[str]) -> ET.Element | None:
    wanted = {name.lower() for name in names}
    for child in list(element):
        if local_name(child.tag) in wanted:
            return child
    return None


def _element_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    raw = " ".join(part for part in element.itertext() if part)
    return strip_html(raw)


def _entry_link(entry: ET.Element, feed_url: str) -> str | None:
    links = [child for child in list(entry) if local_name(child.tag) == "link"]
    for link in links:
        href = link.attrib.get("href")
        rel = link.attrib.get("rel", "alternate")
        if href and rel in {"alternate", ""}:
            return urljoin(feed_url, href)
    for link in links:
        href = link.attrib.get("href")
        if href:
            return urljoin(feed_url, href)
        text = _element_text(link)
        if text:
            return urljoin(feed_url, text)
    guid = _element_text(_first_child(entry, ("guid", "id")))
    return guid if guid.startswith(("http://", "https://")) else None


def parse_datetime(value: str) -> datetime | None:
    text = normalize_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError, OverflowError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _entry_date(entry: ET.Element) -> datetime | None:
    value = _element_text(_first_child(entry, ("pubdate", "published", "updated", "date", "issued")))
    return parse_datetime(value)


def _entry_content(entry: ET.Element) -> str:
    for name in ("encoded", "description", "summary", "content"):
        value = _element_text(_first_child(entry, (name,)))
        if value:
            return value
    return ""


def parse_feed(xml_bytes: bytes, source: RssSource, limit: int | None = None) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_bytes)
    root_name = local_name(root.tag)
    if root_name in {"rss", "rdf"}:
        entries = [element for element in root.iter() if local_name(element.tag) == "item"]
    elif root_name == "feed":
        entries = [element for element in list(root) if local_name(element.tag) == "entry"]
    else:
        entries = [element for element in root.iter() if local_name(element.tag) in {"item", "entry"}]
    items: list[dict[str, Any]] = []
    for entry in entries:
        title = _element_text(_first_child(entry, ("title",)))
        if not title:
            continue
        items.append(
            {
                "source": source.name,
                "platform": source.platform,
                "title": title,
                "content": _entry_content(entry),
                "url": _entry_link(entry, source.url),
                "published_at": iso_utc(_entry_date(entry)),
            }
        )
        if limit is not None and len(items) >= limit:
            break
    return items


def load_sources(path: Path) -> list[RssSource]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("RSS source config must be a JSON list")
    sources: list[RssSource] = []
    for index, row in enumerate(payload, start=1):
        if not isinstance(row, dict) or not row.get("name") or not row.get("url"):
            raise ValueError(f"RSS source {index} must contain name and url")
        source = RssSource(
            name=str(row["name"]),
            url=str(row["url"]),
            platform=str(row.get("platform") or "media"),
            enabled=bool(row.get("enabled", True)),
        )
        if source.enabled:
            sources.append(source)
    return sources


def fetch_feed(source: RssSource, timeout: float = 20.0, user_agent: str = DEFAULT_USER_AGENT) -> bytes:
    request = urllib.request.Request(
        source.url,
        headers={"User-Agent": user_agent, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(MAX_FEED_BYTES + 1)
    if len(data) > MAX_FEED_BYTES:
        raise ValueError(f"Feed exceeds {MAX_FEED_BYTES} bytes: {source.url}")
    return data


def item_key(item: dict[str, Any]) -> str:
    if item.get("url"):
        return f"url:{item['url']}"
    raw = f"{normalize_text(str(item.get('title') or '')).lower()}\n{normalize_text(str(item.get('content') or '')).lower()}"
    return "hash:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def dedupe_items(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        key = item_key(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def filter_recent(
    items: Iterable[dict[str, Any]],
    since_hours: float | None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    if since_hours is None:
        return list(items)
    current = (now or datetime.now(UTC)).astimezone(UTC)
    cutoff = current - timedelta(hours=since_hours)
    result: list[dict[str, Any]] = []
    for item in items:
        published = parse_datetime(str(item.get("published_at") or ""))
        if published is None or published >= cutoff:
            result.append(item)
    return result


def collect_sources(
    sources: Iterable[RssSource],
    limit_per_feed: int = 30,
    since_hours: float | None = 72.0,
    timeout: float = 20.0,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    for source in sources:
        try:
            xml_bytes = fetch_feed(source, timeout=timeout)
            parsed = parse_feed(xml_bytes, source, limit=limit_per_feed)
            items.extend(filter_recent(parsed, since_hours=since_hours, now=now))
        except Exception as exc:  # keep other sources usable when one feed fails
            errors.append(f"{source.name} ({source.url}): {exc}")
    return dedupe_items(items), errors


def save_items(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect configured RSS/Atom feeds into News Study JSON input")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit-per-feed", type=int, default=30)
    parser.add_argument("--since-hours", type=float, default=72.0)
    parser.add_argument("--timeout", type=float, default=20.0)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    sources = load_sources(args.config)
    items, errors = collect_sources(
        sources,
        limit_per_feed=max(1, args.limit_per_feed),
        since_hours=None if args.since_hours < 0 else args.since_hours,
        timeout=max(1.0, args.timeout),
    )
    save_items(args.output, items)
    for error in errors:
        print(f"RSS warning: {error}", file=sys.stderr)
    print(f"sources={len(sources)}, items={len(items)}, errors={len(errors)}, output={args.output}")
    if sources and not items and len(errors) == len(sources):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
