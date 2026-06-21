from __future__ import annotations

import argparse
import csv
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "bilibili-summary" / ".env.local"
EXPORT_DIR = ROOT / "data" / "exports"
TOPIC_DIR = ROOT / "data" / "topics"
FIELDS = ["keyword", "rank", "title", "bvid", "author", "mid", "url", "play", "danmaku", "duration", "pubdate", "description"]


def load_cookie() -> str:
    if not ENV_FILE.exists():
        return ""
    values: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    parts = []
    if values.get("BILIBILI_SESSION_TOKEN"):
        parts.append(f"SESSDATA={values['BILIBILI_SESSION_TOKEN']}")
    if values.get("BILIBILI_BILI_JCT"):
        parts.append(f"bili_jct={values['BILIBILI_BILI_JCT']}")
    return "; ".join(parts)


def fetch_json(url: str, cookie: str) -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Referer": "https://search.bilibili.com/",
        "Accept": "application/json,text/plain,*/*",
    }
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(
        url,
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8", "ignore"))


def clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value or "")
    return value.replace("&amp;", "&").replace("\n", " ").strip()


def safe_name(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', "-", value)
    return value[:80].strip(" .") or "keywords"


def search_keyword(keyword: str, pages: int, sleep: float) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    cookie = load_cookie()
    for page in range(1, pages + 1):
        query = urllib.parse.urlencode({"search_type": "video", "keyword": keyword, "page": page})
        try:
            payload = fetch_json(f"https://api.bilibili.com/x/web-interface/search/type?{query}", cookie)
        except Exception as exc:
            print(f"WARN keyword={keyword} page={page}: {exc}")
            continue
        if payload.get("code") != 0:
            print(f"WARN keyword={keyword} page={page}: {payload.get('message') or payload.get('code')}")
            continue
        results = ((payload.get("data") or {}).get("result") or [])
        for item in results:
            bvid = item.get("bvid", "")
            rows.append(
                {
                    "keyword": keyword,
                    "rank": len(rows) + 1,
                    "title": clean_html(str(item.get("title") or "")),
                    "bvid": bvid,
                    "author": clean_html(str(item.get("author") or "")),
                    "mid": item.get("mid", ""),
                    "url": f"https://www.bilibili.com/video/{bvid}/" if bvid else "",
                    "play": item.get("play", ""),
                    "danmaku": item.get("danmaku", ""),
                    "duration": item.get("duration", ""),
                    "pubdate": item.get("pubdate", ""),
                    "description": clean_html(str(item.get("description") or "")),
                }
            )
        time.sleep(sleep)
    return rows


def write_outputs(rows: list[dict[str, object]], keywords: list[str]) -> tuple[Path, Path]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    TOPIC_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d-%H%M")
    label = safe_name("-".join(keywords))
    csv_path = EXPORT_DIR / f"{stamp}-bilibili-keyword-search-{label}.csv"
    md_path = TOPIC_DIR / f"{stamp}-B站关键词搜索-{label}.md"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})

    lines = [
        "# B站关键词搜索",
        "",
        f"- 生成时间：{datetime.now(timezone(timedelta(hours=8))):%Y-%m-%d %H:%M:%S}",
        f"- 关键词：{'、'.join(keywords)}",
        f"- 结果数：{len(rows)}",
        "- 来源：B站公开视频搜索，只读采集。",
        "",
        "| 关键词 | 标题 | UP主 | 播放 | 弹幕 | 链接 |",
        "|---|---|---|---:|---:|---|",
    ]
    for row in rows[:100]:
        lines.append(f"| {row['keyword']} | {row['title']} | {row['author']} | {row['play']} | {row['danmaku']} | [打开]({row['url']}) |")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return csv_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="按关键词搜索 B站公开视频")
    parser.add_argument("keywords", nargs="+", help="关键词，可以传多个")
    parser.add_argument("--pages", type=int, default=1, help="每个关键词搜索页数")
    parser.add_argument("--sleep", type=float, default=0.8, help="请求间隔秒数")
    args = parser.parse_args()

    rows: list[dict[str, object]] = []
    for keyword in args.keywords:
        rows.extend(search_keyword(keyword, args.pages, args.sleep))
    csv_path, md_path = write_outputs(rows, args.keywords)
    print(f"COUNT={len(rows)}")
    print(f"CSV={csv_path}")
    print(f"MD={md_path}")


if __name__ == "__main__":
    main()
