import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


CHINA_TZ = timezone(timedelta(hours=8))
MOBILE_WECHAT_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
    "MicroMessenger/8.0.48(0x18003031) NetType/WIFI Language/zh_CN"
)
WATCH_DIR = Path("watch_targets")
REPORT_DIR = Path("reports")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def fetch_text(url: str, *, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> str:
    body = None
    headers = {
        "User-Agent": MOBILE_WECHAT_UA,
        "Referer": "https://mp.weixin.qq.com/",
    }
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def search_one(text: str, pattern: str) -> Optional[str]:
    match = re.search(pattern, text, re.S)
    return match.group(1) if match else None


def slugify(name: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", name).strip("_")
    return slug or "wx_public_account"


def china_time_str(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=CHINA_TZ).strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class ArticleMeta:
    title: str
    url: str
    biz: str
    nickname: str
    user_name: str
    msgid: str
    idx: str
    sn: str
    publish_ts: int
    publish_time_cn: str
    author: str
    profile_signature: str
    cover_image: str
    round_head_img: str
    album_ids: List[str]


def parse_article(url: str) -> ArticleMeta:
    text = fetch_text(url)
    biz = search_one(text, r'var biz = "([^"]+)"') or search_one(text, r'biz:\s*"([^"]+)"') or ""
    nickname = search_one(text, r'var nickname = htmlDecode\("([^"]+)"\);') or ""
    user_name = search_one(text, r'var user_name = "([^"]+)";') or ""
    msgid = search_one(text, r'var appmsgid = "([^"]+)"') or search_one(text, r'mid:\s*"([^"]+)"') or ""
    idx = search_one(text, r'idx:\s*"([^"]+)"') or ""
    sn = search_one(text, r'sn:\s*"([^"]+)"') or ""
    title = search_one(text, r"var msg_title = '(.+?)'\.html\(false\);") or ""
    publish_ts_raw = search_one(text, r'var ct = "(\d+)";') or search_one(text, r'var createTimestamp = \'(\d+)\';') or "0"
    publish_ts = int(publish_ts_raw)
    author = search_one(text, r'var author = "([^"]*)";') or ""
    profile_signature = search_one(text, r'var profile_signature = "([^"]*)";') or ""
    cover_image = search_one(text, r'var msg_cdn_url = "([^"]+)";') or ""
    round_head_img = search_one(text, r'var round_head_img = "([^"]+)";') or ""
    album_ids = sorted(
        set(
            re.findall(
                r"appmsgalbum\?__biz=" + re.escape(biz) + r'[^"\']*?album_id=([0-9]+)',
                text,
            )
        )
    )
    if not title or not nickname or not biz or publish_ts <= 0:
        raise RuntimeError("Unable to parse enough metadata from the article page.")
    return ArticleMeta(
        title=title,
        url=url,
        biz=biz,
        nickname=nickname,
        user_name=user_name,
        msgid=msgid,
        idx=idx,
        sn=sn,
        publish_ts=publish_ts,
        publish_time_cn=china_time_str(publish_ts),
        author=author,
        profile_signature=profile_signature.replace("\\x0a", "\n"),
        cover_image=cover_image,
        round_head_img=round_head_img,
        album_ids=album_ids,
    )


def parse_album_items(biz: str, album_id: str) -> List[Dict[str, Any]]:
    url = (
        "https://mp.weixin.qq.com/mp/appmsgalbum?"
        + urllib.parse.urlencode({"__biz": biz, "action": "getalbum", "album_id": album_id})
    )
    text = fetch_text(url)
    item_pattern = re.compile(
        r'data-msgid="(?P<msgid>\d+)"[^>]*?'
        r'data-itemidx="(?P<idx>\d+)"[^>]*?'
        r'data-link="(?P<link>[^"]+)"[^>]*?'
        r'data-title="(?P<title>[^"]+)"[\s\S]*?'
        r'<span class="js_article_create_time album__item-info-item">(?P<create_ts>\d+)</span>',
        re.S,
    )
    items: List[Dict[str, Any]] = []
    for match in item_pattern.finditer(text):
        create_ts = int(match.group("create_ts"))
        items.append(
            {
                "msgid": match.group("msgid"),
                "idx": match.group("idx"),
                "title": match.group("title"),
                "url": match.group("link").replace("&amp;", "&"),
                "publish_ts": create_ts,
                "publish_time_cn": china_time_str(create_ts),
                "album_id": album_id,
            }
        )
    items.sort(key=lambda item: item["publish_ts"], reverse=True)
    return items


def fetch_urls_from_wxpublic_api(name: str, start_date: str, end_date: str) -> List[str]:
    app_id = os.getenv("WXPUBLIC_APP_ID", "").strip()
    secure_key = os.getenv("WXPUBLIC_SECURE_KEY", "").strip()
    if not app_id or not secure_key:
        raise RuntimeError("Missing WXPUBLIC_APP_ID or WXPUBLIC_SECURE_KEY.")
    payload = {
        "app_id": app_id,
        "secure_key": secure_key,
        "name": name,
        "startDate": start_date,
        "endDate": end_date,
    }
    try:
        text = fetch_text(
            "https://www.xiongweixp.tech/wxpublic_fetch/fetch",
            method="POST",
            data=payload,
        )
        data = json.loads(text)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"wxpublic API HTTP error: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("wxpublic API returned invalid JSON.") from exc
    if "error" in data:
        raise RuntimeError(str(data["error"]))
    return list(dict.fromkeys(data.get("urls", [])))


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def bootstrap(args: argparse.Namespace) -> int:
    article = parse_article(args.url)
    slug = slugify(article.nickname)
    watch_path = WATCH_DIR / f"{slug}.json"
    album_observations = []
    for album_id in article.album_ids:
        try:
            items = parse_album_items(article.biz, album_id)
            album_observations.append(
                {
                    "album_id": album_id,
                    "items_found": len(items),
                    "contains_seed_msgid": any(item["msgid"] == article.msgid for item in items),
                    "top_3_titles": [item["title"] for item in items[:3]],
                }
            )
        except Exception as exc:  # pragma: no cover
            album_observations.append({"album_id": album_id, "error": str(exc)})

    payload = {
        "account": {
            "nickname": article.nickname,
            "biz": article.biz,
            "user_name": article.user_name,
            "profile_signature": article.profile_signature,
            "round_head_img": article.round_head_img,
        },
        "seed_article": asdict(article),
        "discovery": {
            "bootstrapped_at_cn": china_time_str(int(datetime.now(tz=CHINA_TZ).timestamp())),
            "album_observations": album_observations,
            "note": (
                "Seed article parsing is available immediately. "
                "Automatic article-list discovery works best with WXPUBLIC_APP_ID/WXPUBLIC_SECURE_KEY."
            ),
        },
    }
    save_json(watch_path, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\nSAVED_WATCH:{watch_path.resolve()}")
    return 0


def check_latest(args: argparse.Namespace) -> int:
    watch_path = Path(args.watch_file)
    data = json.loads(watch_path.read_text(encoding="utf-8"))
    account = data["account"]
    urls = fetch_urls_from_wxpublic_api(account["nickname"], args.start_date, args.end_date)
    articles: List[Dict[str, Any]] = []
    for url in urls:
        try:
            meta = parse_article(url)
        except Exception as exc:
            articles.append({"url": url, "error": str(exc)})
            continue
        if meta.biz != account["biz"]:
            continue
        articles.append(asdict(meta))

    clean_articles = [item for item in articles if "publish_ts" in item]
    clean_articles.sort(key=lambda item: item["publish_ts"], reverse=True)
    latest_actual = clean_articles[0] if clean_articles else None
    report = {
        "account": account,
        "query_range": {"start_date": args.start_date, "end_date": args.end_date},
        "total_urls_from_api": len(urls),
        "matched_articles": len(clean_articles),
        "latest_actual_by_publish_time": latest_actual,
        "articles_sorted_by_publish_time": clean_articles,
        "raw_failures": [item for item in articles if "error" in item],
        "generated_at_cn": china_time_str(int(datetime.now(tz=CHINA_TZ).timestamp())),
    }
    slug = slugify(account["nickname"])
    report_path = REPORT_DIR / f"{slug}_{args.end_date}.json"
    save_json(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nSAVED_REPORT:{report_path.resolve()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WeChat public account watcher.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_bootstrap = subparsers.add_parser("bootstrap", help="Locate an account from a seed article URL.")
    p_bootstrap.add_argument("url")
    p_bootstrap.set_defaults(func=bootstrap)

    p_check = subparsers.add_parser(
        "check-latest",
        help="Query recent article URLs and reorder them by actual publish time.",
    )
    p_check.add_argument("watch_file")
    p_check.add_argument("start_date")
    p_check.add_argument("end_date")
    p_check.set_defaults(func=check_latest)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
