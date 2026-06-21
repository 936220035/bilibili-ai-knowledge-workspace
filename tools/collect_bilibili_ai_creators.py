from __future__ import annotations

import argparse
import csv
import json
import math
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "bilibili-summary" / ".env.local"
EXPORT_DIR = ROOT / "data" / "exports"
TOPIC_DIR = ROOT / "data" / "topics"

DEFAULT_KEYWORDS = [
    "AI工具",
    "AI教程",
    "人工智能",
    "AIGC",
    "ChatGPT",
    "Claude",
    "Cursor",
    "Codex",
    "AI编程",
    "AI办公",
    "AI副业",
    "AI Agent",
    "智能体",
    "大模型",
    "ComfyUI",
]

RELEVANCE_TERMS = [
    "ai",
    "aigc",
    "chatgpt",
    "claude",
    "cursor",
    "codex",
    "agent",
    "智能体",
    "人工智能",
    "大模型",
    "提示词",
    "自动化",
    "工具",
    "办公",
    "编程",
    "副业",
    "comfyui",
    "midjourney",
    "stable diffusion",
]


@dataclass
class Creator:
    mid: str
    name: str
    sign: str = ""
    fans: int = 0
    videos: int = 0
    level: int = 0
    verify_info: str = ""
    keywords: set[str] = field(default_factory=set)
    sample_videos: list[dict] = field(default_factory=list)

    def relevance_hits(self) -> int:
        text = f"{self.name} {self.sign} " + " ".join(v.get("title", "") for v in self.sample_videos)
        lowered = text.lower()
        return sum(1 for term in RELEVANCE_TERMS if term.lower() in lowered)

    def score(self) -> float:
        fan_score = math.log10(max(self.fans, 0) + 10) * 18
        video_score = math.log10(max(self.videos, 0) + 10) * 8
        keyword_score = len(self.keywords) * 7
        relevance_score = self.relevance_hits() * 5
        return round(fan_score + video_score + keyword_score + relevance_score + self.level * 1.5, 2)

    def url(self) -> str:
        return f"https://space.bilibili.com/{self.mid}"


def load_cookie() -> str:
    if not ENV_FILE.exists():
        return ""
    env: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip("'").strip('"')
    sess = env.get("BILIBILI_SESSION_TOKEN", "")
    jct = env.get("BILIBILI_BILI_JCT", "")
    parts = []
    if sess:
        parts.append(f"SESSDATA={sess}")
    if jct:
        parts.append(f"bili_jct={jct}")
    return "; ".join(parts)


def fetch_user_search(keyword: str, page: int, cookie: str) -> dict:
    params = urllib.parse.urlencode(
        {
            "search_type": "bili_user",
            "keyword": keyword,
            "page": page,
        }
    )
    url = f"https://api.bilibili.com/x/web-interface/search/type?{params}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Referer": "https://search.bilibili.com/",
        "Accept": "application/json,text/plain,*/*",
    }
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value or "")
    return value.replace("&amp;", "&").strip()


def as_int(value) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def collect(keywords: list[str], pages: int, sleep: float) -> dict[str, Creator]:
    cookie = load_cookie()
    creators: dict[str, Creator] = {}
    for keyword in keywords:
        for page in range(1, pages + 1):
            try:
                payload = fetch_user_search(keyword, page, cookie)
            except Exception as exc:
                print(f"WARN keyword={keyword} page={page}: {exc}")
                continue
            if payload.get("code") != 0:
                print(f"WARN keyword={keyword} page={page}: {payload.get('message')}")
                continue
            for item in payload.get("data", {}).get("result", []) or []:
                mid = str(item.get("mid", "")).strip()
                if not mid:
                    continue
                creator = creators.get(mid)
                if creator is None:
                    creator = Creator(
                        mid=mid,
                        name=clean_html(item.get("uname", "")),
                        sign=clean_html(item.get("usign", "")),
                        fans=as_int(item.get("fans")),
                        videos=as_int(item.get("videos")),
                        level=as_int(item.get("level")),
                        verify_info=clean_html(item.get("verify_info", "")),
                    )
                    creators[mid] = creator
                creator.keywords.add(keyword)
                for video in item.get("res", []) or []:
                    bvid = video.get("bvid", "")
                    if bvid and all(v.get("bvid") != bvid for v in creator.sample_videos):
                        creator.sample_videos.append(
                            {
                                "bvid": bvid,
                                "title": clean_html(video.get("title", "")),
                                "play": str(video.get("play", "")),
                                "url": f"https://www.bilibili.com/video/{bvid}/",
                            }
                        )
            time.sleep(sleep)
    return creators


def category_for(creator: Creator) -> str:
    text = f"{creator.name} {creator.sign} " + " ".join(v.get("title", "") for v in creator.sample_videos)
    lower = text.lower()
    if any(term in lower for term in ["编程", "cursor", "codex", "代码", "程序员"]):
        return "AI编程/Codex/Cursor"
    if any(term in lower for term in ["comfyui", "midjourney", "stable diffusion", "绘画", "生图"]):
        return "AI绘图/AIGC"
    if any(term in lower for term in ["办公", "ppt", "excel", "效率", "工具箱"]):
        return "AI工具/办公效率"
    if any(term in lower for term in ["副业", "赚钱", "自媒体", "变现"]):
        return "AI副业/自媒体"
    if any(term in lower for term in ["智能体", "agent", "dify", "coze", "工作流"]):
        return "AI Agent/工作流"
    return "综合AI/大模型"


def write_outputs(creators: list[Creator]) -> tuple[Path, Path]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    TOPIC_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    csv_path = EXPORT_DIR / f"{stamp}-bilibili-ai-creators.csv"
    md_path = TOPIC_DIR / f"{stamp}-B站AI博主收集清单.md"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "rank",
                "score",
                "category",
                "name",
                "mid",
                "url",
                "fans",
                "videos",
                "level",
                "keywords",
                "sign",
                "sample_video_titles",
                "sample_video_urls",
            ],
        )
        writer.writeheader()
        for i, creator in enumerate(creators, 1):
            writer.writerow(
                {
                    "rank": i,
                    "score": creator.score(),
                    "category": category_for(creator),
                    "name": creator.name,
                    "mid": creator.mid,
                    "url": creator.url(),
                    "fans": creator.fans,
                    "videos": creator.videos,
                    "level": creator.level,
                    "keywords": "、".join(sorted(creator.keywords)),
                    "sign": creator.sign,
                    "sample_video_titles": " | ".join(v.get("title", "") for v in creator.sample_videos[:3]),
                    "sample_video_urls": " | ".join(v.get("url", "") for v in creator.sample_videos[:3]),
                }
            )

    lines = [
        "# B站 AI 博主收集清单",
        "",
        f"- 生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
        f"- 数量：{len(creators)}",
        "- 来源：B站公开用户搜索结果",
        "- 说明：分数是本地粗排，综合粉丝数、视频数、关键词命中和 AI 相关度；不是官方排名。",
        "",
        "## Top 30",
        "",
        "| 排名 | 博主 | 分类 | 粉丝 | 视频数 | 命中关键词 | 主页 |",
        "|---:|---|---|---:|---:|---|---|",
    ]
    for i, creator in enumerate(creators[:30], 1):
        lines.append(
            f"| {i} | {creator.name} | {category_for(creator)} | {creator.fans} | {creator.videos} | "
            f"{'、'.join(sorted(creator.keywords))} | [主页]({creator.url()}) |"
        )

    lines.extend(["", "## 分组建议", ""])
    categories: dict[str, list[Creator]] = {}
    for creator in creators:
        categories.setdefault(category_for(creator), []).append(creator)
    for category, items in sorted(categories.items(), key=lambda kv: len(kv[1]), reverse=True):
        lines.append(f"### {category}")
        lines.append("")
        for creator in items[:12]:
            sample = creator.sample_videos[0]["title"] if creator.sample_videos else ""
            lines.append(f"- [{creator.name}]({creator.url()})：粉丝 {creator.fans}，视频 {creator.videos}。样例：{sample}")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return csv_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="收集 B站 AI 方向 UP 主")
    parser.add_argument("--pages", type=int, default=2, help="每个关键词抓取页数，默认 2")
    parser.add_argument("--limit", type=int, default=120, help="导出数量上限，默认 120")
    parser.add_argument("--sleep", type=float, default=0.35, help="请求间隔秒数")
    parser.add_argument("--keywords", nargs="*", default=DEFAULT_KEYWORDS, help="自定义关键词")
    args = parser.parse_args()

    creators = collect(args.keywords, args.pages, args.sleep)
    ranked = sorted(
        creators.values(),
        key=lambda c: (c.score(), c.fans, len(c.keywords)),
        reverse=True,
    )
    filtered = [c for c in ranked if c.relevance_hits() >= 1][: args.limit]
    csv_path, md_path = write_outputs(filtered)
    print(f"COUNT={len(filtered)}")
    print(f"CSV={csv_path}")
    print(f"MD={md_path}")


if __name__ == "__main__":
    main()
