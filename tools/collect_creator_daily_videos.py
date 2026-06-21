from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import string
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.cookiejar import CookieJar
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "bilibili-summary" / ".env.local"
CONFIG_CREATOR_CSV = ROOT / "data" / "config" / "bilibili_creators.csv"
EXPORT_DIR = ROOT / "data" / "exports"
TOPIC_DIR = ROOT / "data" / "topics"

BILI_MIXIN_KEY_ENC_TAB = [
    46,
    47,
    18,
    2,
    53,
    8,
    23,
    32,
    15,
    50,
    10,
    31,
    58,
    3,
    45,
    35,
    27,
    43,
    5,
    49,
    33,
    9,
    42,
    19,
    29,
    28,
    14,
    39,
    12,
    38,
    41,
    13,
    37,
    48,
    7,
    16,
    24,
    55,
    40,
    61,
    26,
    17,
    0,
    1,
    60,
    51,
    30,
    4,
    22,
    25,
    54,
    21,
    56,
    59,
    6,
    63,
    57,
    62,
    11,
    36,
    20,
    34,
    44,
    52,
]

CATEGORY_RULES = [
    ("AI编程", ["cursor", "codex", "claude code", "ai编程", "编程", "代码", "开发", "vibe", "软件"]),
    ("智能体/工作流", ["agent", "智能体", "工作流", "coze", "dify", "langgraph", "mcp", "自动化"]),
    ("知识库/RAG", ["rag", "知识库", "obsidian", "向量", "检索", "文档", "资料库"]),
    ("AI工具/效率", ["工具箱", "ai工具", "效率", "办公", "ppt", "excel", "自动办公"]),
    ("大模型/行业", ["大模型", "llm", "openai", "deepseek", "qwen", "kimi", "minimax", "模型"]),
    ("AI绘图/视频", ["comfyui", "绘图", "生图", "视频生成", "stable diffusion", "midjourney", "剪辑"]),
    ("AI副业/内容", ["副业", "变现", "自媒体", "起号", "流量", "赚钱", "矩阵"]),
]

VALUE_RULES = [
    ("可拆教程", ["教程", "手把手", "实战", "搭建", "部署", "从零", "入门", "保姆级"]),
    ("可做工具评测", ["工具", "测评", "对比", "免费", "开源", "替代", "推荐"]),
    ("可做选题跟进", ["最新", "发布", "升级", "爆火", "首发", "更新", "上线"]),
    ("可做案例拆解", ["案例", "复盘", "商业", "落地", "项目", "工作流", "自动化"]),
]


@dataclass
class Creator:
    priority: str
    name: str
    mid: str
    reason: str
    fans: int


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


class BiliClient:
    def __init__(self, cookie: str) -> None:
        # Space video list is less likely to trigger risk control with fresh
        # browser cookies than with a partial login cookie copied from env.
        self.cookie = ""
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def open_text(self, url: str, referer: str = "https://www.bilibili.com/") -> str:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Referer": referer,
            "Accept": "application/json,text/plain,*/*",
        }
        if self.cookie:
            headers["Cookie"] = self.cookie
        req = urllib.request.Request(url, headers=headers)
        with self.opener.open(req, timeout=25) as response:
            return response.read().decode("utf-8", "ignore")

    def json(self, url: str, referer: str = "https://www.bilibili.com/") -> dict:
        return json.loads(self.open_text(url, referer))

    def prime(self, mid: str = "") -> None:
        self.open_text("https://www.bilibili.com/")
        if mid:
            self.open_text(f"https://space.bilibili.com/{mid}/video", "https://www.bilibili.com/")


def get_mixin_key(client: BiliClient) -> str:
    payload = client.json("https://api.bilibili.com/x/web-interface/nav")
    data = payload.get("data") or {}
    wbi_img = data.get("wbi_img") or {}
    img_key = Path(urllib.parse.urlparse(wbi_img.get("img_url", "")).path).stem
    sub_key = Path(urllib.parse.urlparse(wbi_img.get("sub_url", "")).path).stem
    raw = img_key + sub_key
    if len(raw) < 64:
        raise RuntimeError("Cannot get Bilibili WBI key.")
    return "".join(raw[i] for i in BILI_MIXIN_KEY_ENC_TAB)[:32]


def signed_params(params: dict[str, object], mixin_key: str) -> str:
    safe = string.ascii_letters + string.digits + "!'()*"
    params = {**params, "wts": int(time.time())}
    cleaned = {}
    for key, value in params.items():
        cleaned[key] = re.sub(r"[!'()*]", "", str(value))
    query = urllib.parse.urlencode(sorted(cleaned.items()), safe=safe)
    w_rid = hashlib.md5((query + mixin_key).encode("utf-8")).hexdigest()
    return query + "&w_rid=" + w_rid


def latest_curated_csv() -> Path:
    if CONFIG_CREATOR_CSV.exists() and has_enabled_config_creators(CONFIG_CREATOR_CSV):
        return CONFIG_CREATOR_CSV
    paths = sorted(EXPORT_DIR.glob("*bilibili-ai-creators-curated.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not paths:
        raise FileNotFoundError("No curated creator CSV found. Run tools\\curate_bilibili_ai_creators.py first.")
    return paths[0]


def has_enabled_config_creators(path: Path) -> bool:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return any((row.get("mid") or "").strip() and (row.get("enabled") or "1").strip() != "0" for row in csv.DictReader(f))


def as_int(value: object) -> int:
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def load_creators(path: Path, limit: int, priorities: set[str]) -> list[Creator]:
    creators: list[Creator] = []
    seen: set[str] = set()
    is_config = path.resolve() == CONFIG_CREATOR_CSV.resolve()
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            mid = (row.get("mid") or "").strip()
            priority = (row.get("priority") or "").strip()
            enabled = (row.get("enabled") or "1").strip()
            if not mid or mid in seen or enabled == "0":
                continue
            if not is_config and priority not in priorities:
                continue
            creators.append(
                Creator(
                    priority=priority,
                    name=row.get("name", ""),
                    mid=mid,
                    reason=row.get("reason", ""),
                    fans=as_int(row.get("fans", "0")),
                )
            )
            seen.add(mid)
            if len(creators) >= limit:
                break
    return creators


def fetch_creator_videos(creator: Creator, mixin_key: str, client: BiliClient, page_size: int) -> list[dict]:
    params = signed_params(
        {
            "mid": creator.mid,
            "pn": 1,
            "ps": page_size,
            "order": "pubdate",
            "platform": "web",
            "web_location": "1550101",
        },
        mixin_key,
    )
    url = f"https://api.bilibili.com/x/space/wbi/arc/search?{params}"
    client.prime(creator.mid)
    payload = client.json(url, f"https://space.bilibili.com/{creator.mid}/video")
    if payload.get("code") != 0:
        raise RuntimeError(str(payload.get("message") or payload.get("code")))
    return (((payload.get("data") or {}).get("list") or {}).get("vlist") or [])


def classify(text: str, rules: list[tuple[str, list[str]]], fallback: str) -> str:
    lowered = text.lower()
    hits = [name for name, terms in rules if any(term.lower() in lowered for term in terms)]
    return "、".join(hits[:3]) if hits else fallback


def extract_points(title: str, desc: str) -> str:
    text = f"{title}。{desc}".replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "暂无简介，只能从标题判断。"
    text = re.sub(r"(关注|点赞|投币|收藏|三连|私信|加微|领取资料).{0,30}", "", text)
    return text[:170] + ("..." if len(text) > 170 else "")


def value_for(text: str) -> str:
    return classify(text, VALUE_RULES, "先观察")


def safe_name(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', "-", value)
    return value[:80].strip(" .") or "untitled"


def collect(args: argparse.Namespace) -> tuple[list[dict], Path]:
    source = Path(args.creators_csv) if args.creators_csv else latest_curated_csv()
    creators = load_creators(source, args.creator_limit, set(args.priorities.split(",")))
    client = BiliClient(load_cookie())
    first_mid = creators[0].mid if creators else ""
    client.prime(first_mid)
    mixin_key = get_mixin_key(client)
    tz = timezone(timedelta(hours=8))
    target_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else datetime.now(tz).date()
    start = datetime.combine(target_date - timedelta(days=args.days - 1), datetime.min.time(), tz)
    end = datetime.combine(target_date + timedelta(days=1), datetime.min.time(), tz)

    items: list[dict] = []
    for index, creator in enumerate(creators, 1):
        try:
            videos = fetch_creator_videos(creator, mixin_key, client, args.page_size)
        except Exception as exc:
            print(f"WARN creator={creator.name} mid={creator.mid}: {exc}")
            continue
        for video in videos:
            pub_at = datetime.fromtimestamp(as_int(video.get("created")), tz)
            if not (start <= pub_at < end):
                continue
            title = str(video.get("title") or "").strip()
            desc = str(video.get("description") or "").strip()
            text = f"{title} {desc}"
            stat = {
                "play": as_int(video.get("play")),
                "danmaku": as_int(video.get("video_review")),
                "like": as_int(video.get("like")),
                "coin": as_int(video.get("coin")),
                "favorite": as_int(video.get("favorites")),
                "share": as_int(video.get("share")),
                "reply": as_int(video.get("comment")),
                "duration": video.get("length", ""),
            }
            items.append(
                {
                    "date": pub_at.strftime("%Y-%m-%d"),
                    "published_at": pub_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "creator_priority": creator.priority,
                    "creator_name": creator.name,
                    "creator_mid": creator.mid,
                    "creator_reason": creator.reason,
                    "creator_fans": creator.fans,
                    "bvid": video.get("bvid", ""),
                    "aid": video.get("aid", ""),
                    "title": title,
                    "url": f"https://www.bilibili.com/video/{video.get('bvid', '')}/",
                    "description": desc,
                    "category": classify(text, CATEGORY_RULES, "其他AI"),
                    "value": value_for(text),
                    "talks_about": extract_points(title, desc),
                    **stat,
                }
            )
        if index < len(creators):
            time.sleep(args.sleep)
    items.sort(key=lambda item: (item["published_at"], item["play"]), reverse=True)
    return items, source


def write_outputs(items: list[dict], source: Path, args: argparse.Namespace) -> tuple[Path, Path]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    TOPIC_DIR.mkdir(parents=True, exist_ok=True)
    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz).strftime("%Y-%m-%d-%H%M")
    label = args.date or datetime.now(tz).strftime("%Y-%m-%d")
    csv_path = EXPORT_DIR / f"{today}-bilibili-ai-creator-daily-videos.csv"
    md_path = TOPIC_DIR / f"{today}-B站AI博主每日更新分析-{safe_name(label)}.md"

    fields = [
        "date",
        "published_at",
        "creator_priority",
        "creator_name",
        "creator_mid",
        "creator_reason",
        "creator_fans",
        "bvid",
        "title",
        "url",
        "category",
        "value",
        "talks_about",
        "play",
        "danmaku",
        "like",
        "coin",
        "favorite",
        "share",
        "reply",
        "duration",
        "description",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for item in items:
            writer.writerow({field: item.get(field, "") for field in fields})

    by_category: dict[str, list[dict]] = {}
    for item in items:
        by_category.setdefault(item["category"], []).append(item)
    hot = sorted(items, key=lambda item: (as_int(item.get("play")), as_int(item.get("comment"))), reverse=True)[:12]

    lines = [
        "# B站 AI 博主每日更新分析",
        "",
        f"- 生成时间：{datetime.now(tz):%Y-%m-%d %H:%M:%S}",
        f"- 统计范围：{args.days} 天，截止日期 {label}",
        f"- 监控博主数：{args.creator_limit} 个，优先级：{args.priorities}",
        f"- 新视频数：{len(items)}",
        f"- 博主来源：`{source.name}`",
        "- 说明：当前版本基于公开视频标题、简介、分区和互动数据做初筛分析；不是完整字幕级总结。",
        "",
        "## 今日重点",
        "",
    ]
    if not hot:
        lines.append("今天在监控名单里暂时没有抓到新视频。可以把 `--days` 调大到 3 或 7 看最近更新。")
    else:
        lines.append("| 时间 | UP主 | 视频 | 方向 | 价值 | 播放 | 讲了什么 |")
        lines.append("|---|---|---|---|---|---:|---|")
        for item in hot:
            lines.append(
                f"| {item['published_at']} | {item['creator_name']} | [{item['title']}]({item['url']}) | "
                f"{item['category']} | {item['value']} | {item['play']} | {item['talks_about']} |"
            )

    lines.extend(["", "## 按方向分组", ""])
    for category, group in sorted(by_category.items(), key=lambda kv: len(kv[1]), reverse=True):
        lines.append(f"### {category}（{len(group)} 条）")
        lines.append("")
        for item in group[:20]:
            lines.append(
                f"- {item['published_at']} [{item['creator_name']}]({f'https://space.bilibili.com/{item['creator_mid']}'})："
                f"[{item['title']}]({item['url']})。{item['value']}。{item['talks_about']}"
            )
        lines.append("")

    lines.extend(["## 给龙城 AI 工具箱的选题提示", ""])
    if items:
        value_groups: dict[str, int] = {}
        for item in items:
            value_groups[item["value"]] = value_groups.get(item["value"], 0) + 1
        for value, count in sorted(value_groups.items(), key=lambda kv: kv[1], reverse=True):
            lines.append(f"- {value}：{count} 条，可以优先从这里挑标题做二次拆解。")
    else:
        lines.append("- 暂无新视频，建议先跑最近 7 天作为基线。")
    lines.extend(
        [
            "",
            "## 下一步",
            "",
            "1. 对高价值视频再用 `bilibili-summary` 做字幕/内容级总结。",
            "2. 把同方向视频合并成“今日 AI 工具/智能体/编程趋势”。",
            "3. 只做人工审核后的选题复刻，不自动评论、关注、点赞或投币。",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return csv_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="收集精选 B站 AI 博主的每日更新视频并做初步分析")
    parser.add_argument("--creators-csv", default="", help="精选博主 CSV，默认使用最新 curated CSV")
    parser.add_argument("--creator-limit", type=int, default=50, help="监控前 N 个精选博主，默认 50")
    parser.add_argument("--priorities", default="P0,P1", help="监控优先级，默认 P0,P1")
    parser.add_argument("--date", default="", help="截止日期，格式 YYYY-MM-DD，默认今天")
    parser.add_argument("--days", type=int, default=1, help="向前统计天数，默认 1")
    parser.add_argument("--page-size", type=int, default=20, help="每个博主拉取最近视频数，默认 20")
    parser.add_argument("--sleep", type=float, default=0.8, help="请求间隔秒数")
    args = parser.parse_args()

    items, source = collect(args)
    csv_path, md_path = write_outputs(items, source, args)
    print(f"COUNT={len(items)}")
    print(f"CSV={csv_path}")
    print(f"MD={md_path}")


if __name__ == "__main__":
    main()
