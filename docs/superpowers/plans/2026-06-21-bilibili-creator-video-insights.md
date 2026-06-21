# B站博主与视频洞察系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前“让 AI 替你看 B站”工作区升级成只读的 B站内容情报系统，可以管理 AI 博主、按关键词找视频、抓取关键数据、分析评论关注点，并生成可导入 Obsidian 的日报/资料。

**Architecture:** 保持安全边界，所有工具只读取 B站公开数据，不自动点赞、投币、评论、关注、私信。新增功能放在 `tools/` 和 `data/config/`，复用现有 `collect_bilibili_ai_creators.py`、`collect_creator_daily_videos.py`、`export_bilisummary_to_obsidian.py` 的输出习惯，统一产出 CSV 和 Markdown。

**Tech Stack:** Python 标准库、B站公开 Web API、现有 MiniMax M3/BiliSummary 总结能力、Markdown/CSV、Obsidian 本地知识库。

---

## 目标边界

本目标不再叫“刷 B站”，而是“B站内容情报/选题研究系统”。

允许：
- 添加和维护 AI 博主名单。
- 按关键词搜索 AI 视频和 UP 主。
- 抓取公开视频标题、简介、发布时间、播放、弹幕、点赞、投币、收藏、分享、评论数等指标。
- 读取公开视频评论，用 AI 总结用户关心的问题。
- 生成日报、周报、选题池、知识库笔记。

不允许：
- 自动点赞。
- 自动投币。
- 自动评论。
- 自动私信。
- 自动关注。
- 使用主号做高频操作。
- 把 Cookie、Token、API Key 写入日志、公开文档或 Git。

## 文件结构

- Create: `data/config/bilibili_creators.csv`
  - 人工维护的长期博主名单，字段固定，便于后续日报稳定运行。
- Create: `tools/add_bilibili_creator.py`
  - 从 UID、空间链接或名称参数添加/更新一个博主到 `data/config/bilibili_creators.csv`。
- Create: `tools/search_bilibili_keywords.py`
  - 按关键词搜索公开视频，输出搜索结果 CSV/Markdown。
- Modify: `tools/collect_creator_daily_videos.py`
  - 支持优先读取 `data/config/bilibili_creators.csv`，补齐点赞、投币、分享、弹幕等指标字段。
- Create: `tools/collect_bilibili_comments.py`
  - 只读抓取某个 BV 视频的热门/最新评论，输出 CSV/Markdown。
- Create: `tools/summarize_bilibili_comment_focus.py`
  - 汇总评论文本，生成“用户关心什么”的 Markdown 分析稿。
- Create: `tools/build_bilibili_daily_report.py`
  - 把博主视频、关键词视频、评论分析合并成每日洞察报告。
- Modify: `README.md`
  - 增加新工作流命令。
- Modify: `docs/00-项目总说明.md`
  - 更新项目定位和模块说明。
- Modify: `docs/04-测试记录.md`
  - 记录验证命令和输出结果。

## 数据格式约定

`data/config/bilibili_creators.csv` 字段：

```csv
mid,name,profile_url,priority,tags,reason,source,created_at,updated_at,enabled
```

视频指标字段：

```csv
date,published_at,creator_priority,creator_name,creator_mid,bvid,aid,title,url,category,value,talks_about,play,danmaku,like,coin,favorite,share,reply,duration,description
```

评论字段：

```csv
bvid,rpid,ctime,uname,mid,like_count,message,parent_rpid,root_rpid
```

评论关注点分类：

```text
价格/费用、上手难度、部署安装、效果质疑、替代工具、Bug/报错、使用场景、资料需求、购买意向、正反馈、负反馈、其他
```

## Task 1: 建立长期博主管理文件

**Files:**
- Create: `data/config/bilibili_creators.csv`
- Create: `tools/add_bilibili_creator.py`

- [x] **Step 1: 创建默认博主 CSV**

Create `data/config/bilibili_creators.csv` with header only:

```csv
mid,name,profile_url,priority,tags,reason,source,created_at,updated_at,enabled
```

- [x] **Step 2: 创建添加博主脚本**

Implement `tools/add_bilibili_creator.py`:

```python
from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "data" / "config" / "bilibili_creators.csv"
FIELDS = ["mid", "name", "profile_url", "priority", "tags", "reason", "source", "created_at", "updated_at", "enabled"]


def now_text() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


def extract_mid(value: str) -> str:
    match = re.search(r"space\.bilibili\.com/(\d+)", value)
    if match:
        return match.group(1)
    if re.fullmatch(r"\d{2,}", value.strip()):
        return value.strip()
    raise SystemExit("无法识别 UID。请传 UID 或 https://space.bilibili.com/<uid>")


def read_rows() -> list[dict[str, str]]:
    if not CONFIG.exists():
        return []
    with CONFIG.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(rows: list[dict[str, str]]) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})


def upsert(args: argparse.Namespace) -> Path:
    mid = extract_mid(args.mid_or_url)
    rows = read_rows()
    stamp = now_text()
    found = False
    for row in rows:
        if row.get("mid") == mid:
            row.update({
                "name": args.name or row.get("name", ""),
                "profile_url": f"https://space.bilibili.com/{mid}",
                "priority": args.priority,
                "tags": args.tags,
                "reason": args.reason,
                "source": args.source,
                "updated_at": stamp,
                "enabled": "1",
            })
            found = True
            break
    if not found:
        rows.append({
            "mid": mid,
            "name": args.name or "",
            "profile_url": f"https://space.bilibili.com/{mid}",
            "priority": args.priority,
            "tags": args.tags,
            "reason": args.reason,
            "source": args.source,
            "created_at": stamp,
            "updated_at": stamp,
            "enabled": "1",
        })
    write_rows(rows)
    return CONFIG


def main() -> None:
    parser = argparse.ArgumentParser(description="添加或更新一个 B站博主到长期监控名单")
    parser.add_argument("mid_or_url", help="UP 主 UID 或空间链接")
    parser.add_argument("--name", default="", help="UP 主名称")
    parser.add_argument("--priority", default="P1", choices=["P0", "P1", "P2"], help="监控优先级")
    parser.add_argument("--tags", default="AI", help="标签，多个标签用逗号分隔")
    parser.add_argument("--reason", default="人工添加", help="为什么关注这个博主")
    parser.add_argument("--source", default="manual", help="来源")
    args = parser.parse_args()
    path = upsert(args)
    print(f"SAVED={path}")


if __name__ == "__main__":
    main()
```

- [x] **Step 3: 验证脚本**

Run:

```powershell
python -m py_compile tools\add_bilibili_creator.py
python tools\add_bilibili_creator.py 123456 --name 测试博主 --priority P2 --tags AI测试 --reason 功能验证
```

Expected:

```text
SAVED=C:\Users\龙城\Documents\让 AI 替你刷 B 站\data\config\bilibili_creators.csv
```

- [x] **Step 4: 删除测试行或保留为 disabled**

如果 UID `123456` 只是测试数据，把 `enabled` 改成 `0`，避免后续真实日报读取它。

## Task 2: 支持关键词搜索视频

**Files:**
- Create: `tools/search_bilibili_keywords.py`

- [x] **Step 1: 实现关键词搜索脚本**

Create `tools/search_bilibili_keywords.py` to search public videos and write CSV/Markdown:

```python
from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "data" / "exports"
TOPIC_DIR = ROOT / "data" / "topics"
FIELDS = ["keyword", "rank", "title", "bvid", "author", "mid", "url", "play", "danmaku", "duration", "pubdate", "description"]


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Referer": "https://search.bilibili.com/",
        "Accept": "application/json,text/plain,*/*",
    })
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8", "ignore"))


def clean_html(value: str) -> str:
    return value.replace("<em class=\"keyword\">", "").replace("</em>", "").replace("\n", " ").strip()


def search_keyword(keyword: str, pages: int, sleep: float) -> list[dict[str, object]]:
    rows = []
    for page in range(1, pages + 1):
        query = urllib.parse.urlencode({"search_type": "video", "keyword": keyword, "page": page})
        payload = fetch_json(f"https://api.bilibili.com/x/web-interface/search/type?{query}")
        results = ((payload.get("data") or {}).get("result") or [])
        for item in results:
            rows.append({
                "keyword": keyword,
                "rank": len(rows) + 1,
                "title": clean_html(str(item.get("title") or "")),
                "bvid": item.get("bvid", ""),
                "author": item.get("author", ""),
                "mid": item.get("mid", ""),
                "url": f"https://www.bilibili.com/video/{item.get('bvid', '')}/",
                "play": item.get("play", ""),
                "danmaku": item.get("danmaku", ""),
                "duration": item.get("duration", ""),
                "pubdate": item.get("pubdate", ""),
                "description": clean_html(str(item.get("description") or "")),
            })
        time.sleep(sleep)
    return rows


def write_outputs(rows: list[dict[str, object]], keywords: list[str]) -> tuple[Path, Path]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    TOPIC_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d-%H%M")
    label = "-".join(keywords)[:60].replace(" ", "-")
    csv_path = EXPORT_DIR / f"{stamp}-bilibili-keyword-search-{label}.csv"
    md_path = TOPIC_DIR / f"{stamp}-B站关键词搜索-{label}.md"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})
    lines = ["# B站关键词搜索", "", f"- 关键词：{'、'.join(keywords)}", f"- 结果数：{len(rows)}", "", "| 关键词 | 标题 | UP主 | 播放 | 链接 |", "|---|---|---|---:|---|"]
    for row in rows[:80]:
        lines.append(f"| {row['keyword']} | {row['title']} | {row['author']} | {row['play']} | [打开]({row['url']}) |")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return csv_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="按关键词搜索 B站公开视频")
    parser.add_argument("keywords", nargs="+", help="关键词，可以传多个")
    parser.add_argument("--pages", type=int, default=1, help="每个关键词搜索页数")
    parser.add_argument("--sleep", type=float, default=0.8, help="请求间隔秒数")
    args = parser.parse_args()
    rows = []
    for keyword in args.keywords:
        rows.extend(search_keyword(keyword, args.pages, args.sleep))
    csv_path, md_path = write_outputs(rows, args.keywords)
    print(f"COUNT={len(rows)}")
    print(f"CSV={csv_path}")
    print(f"MD={md_path}")


if __name__ == "__main__":
    main()
```

- [x] **Step 2: 验证关键词搜索**

Run:

```powershell
python -m py_compile tools\search_bilibili_keywords.py
python tools\search_bilibili_keywords.py AI工具 Cursor教程 --pages 1
```

Expected:

```text
COUNT=<大于0>
CSV=<data\exports\...bilibili-keyword-search...csv>
MD=<data\topics\...B站关键词搜索...md>
```

## Task 3: 补齐视频指标采集

**Files:**
- Modify: `tools/collect_creator_daily_videos.py`

- [x] **Step 1: 支持长期博主名单**

Modify `latest_curated_csv()` and `load_creators()` usage so the script checks `data/config/bilibili_creators.csv` first. If it exists and has enabled rows, use it; otherwise fall back to the latest curated CSV.

- [x] **Step 2: 补齐指标字段**

In `collect_creator_daily_videos.py`, map B站返回字段:

```python
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
```

Update CSV fields to include:

```python
"play", "danmaku", "like", "coin", "favorite", "share", "reply", "duration"
```

- [x] **Step 3: 验证日报脚本**

Run:

```powershell
python -m py_compile tools\collect_creator_daily_videos.py
python tools\collect_creator_daily_videos.py --creator-limit 5 --days 7 --page-size 5 --sleep 1.2
```

Expected:

```text
COUNT=<数字>
CSV=<data\exports\...bilibili-ai-creator-daily-videos.csv>
MD=<data\topics\...B站AI博主每日更新分析...md>
```

## Task 4: 只读抓取评论

**Files:**
- Create: `tools/collect_bilibili_comments.py`

- [x] **Step 1: 实现评论抓取**

Create script that accepts `BV` or video URL, resolves `aid` with `x/web-interface/view`, then calls:

```text
https://api.bilibili.com/x/v2/reply/wbi/main
```

Output CSV/Markdown with fields:

```csv
bvid,rpid,ctime,uname,mid,like_count,message,parent_rpid,root_rpid
```

- [x] **Step 2: 控制频率和数量**

Add CLI options:

```text
--limit 80
--mode hot
--sleep 0.8
```

Default only fetch first 80 comments to reduce risk control and keep analysis readable.

- [x] **Step 3: 验证评论抓取**

Run:

```powershell
python -m py_compile tools\collect_bilibili_comments.py
python tools\collect_bilibili_comments.py BV1vezvBsEzV --limit 20
```

Expected:

```text
COUNT=<数字>
CSV=<data\exports\...bilibili-comments-BV1vezvBsEzV.csv>
MD=<data\topics\...B站评论样本-BV1vezvBsEzV.md>
```

## Task 5: 评论关注点总结

**Files:**
- Create: `tools/summarize_bilibili_comment_focus.py`

- [x] **Step 1: 实现无模型本地分类**

Read latest or specified comment CSV, classify comments into:

```text
价格/费用、上手难度、部署安装、效果质疑、替代工具、Bug/报错、使用场景、资料需求、购买意向、正反馈、负反馈、其他
```

Use keyword rules first, so even模型不可用也能出报告。

- [x] **Step 2: 输出 Markdown 分析**

Markdown must include:

```text
# B站评论关注点分析
## 用户最关心的事
## 高频问题
## 适合做成选题的角度
## 可以沉淀到知识库的资料
## 不建议自动回复的原因
```

- [x] **Step 3: 验证总结**

Run:

```powershell
python -m py_compile tools\summarize_bilibili_comment_focus.py
python tools\summarize_bilibili_comment_focus.py --comments-csv data\exports\<comments-file>.csv
```

Expected:

```text
MD=<data\topics\...B站评论关注点分析...md>
```

## Task 6: 生成每日总报告

**Files:**
- Create: `tools/build_bilibili_daily_report.py`

- [x] **Step 1: 汇总当天输出**

Read latest files from:

```text
data/exports/*bilibili-ai-creator-daily-videos.csv
data/exports/*bilibili-keyword-search*.csv
data/topics/*B站评论关注点分析*.md
```

- [x] **Step 2: 生成日报 Markdown**

Output:

```text
data/topics/YYYY-MM-DD-B站AI内容洞察日报.md
```

Sections:

```text
# B站 AI 内容洞察日报
## 今日值得看的视频
## 今日高互动视频
## 关键词趋势
## 评论里用户真正关心什么
## 可做成知识库资料
## 可做成视频/文章选题
## 明天继续监控什么
```

- [x] **Step 3: 验证日报**

Run:

```powershell
python -m py_compile tools\build_bilibili_daily_report.py
python tools\build_bilibili_daily_report.py
```

Expected:

```text
MD=<data\topics\YYYY-MM-DD-B站AI内容洞察日报.md>
```

## Task 7: 文档和知识库同步

**Files:**
- Modify: `README.md`
- Modify: `docs/00-项目总说明.md`
- Modify: `docs/04-测试记录.md`
- Modify: `C:\Users\龙城\Documents\Obsidian\个人知识库\03-项目库\项目机会\让AI替你看B站项目.md`
- Modify: `C:\Users\龙城\Documents\Obsidian\个人知识库\05-工作记录\项目进度\任务进度池.md`

- [x] **Step 1: 更新 README 常用命令**

Add commands:

```powershell
python tools\add_bilibili_creator.py <UID或空间链接> --name <博主名> --priority P1 --tags AI工具
python tools\search_bilibili_keywords.py AI工具 Cursor教程 --pages 1
python tools\collect_creator_daily_videos.py --creator-limit 30 --days 1
python tools\collect_bilibili_comments.py <BV号> --limit 80
python tools\summarize_bilibili_comment_focus.py --comments-csv <评论CSV>
python tools\build_bilibili_daily_report.py
```

- [x] **Step 2: 更新项目说明**

Record the new pipeline:

```text
添加博主/关键词 -> 抓公开视频 -> 抓关键指标 -> 抓评论 -> 总结用户关注点 -> 生成日报/知识库资料
```

- [x] **Step 3: 更新测试记录**

Append all verification commands and outputs. Do not include Cookie, Token, API Key, `.env.local` contents, or raw sensitive logs.

- [x] **Step 4: 同步 Obsidian 项目页和任务进度池**

Update project page with:

```text
当前目标：B站博主与视频洞察系统
阶段：计划已制定，准备实现
安全边界：只读，不自动互动
下一步：先实现博主管理和关键词搜索，再补评论关注点总结
```

Update task pool with the same next action and status.

## Verification Checklist

- [x] `python -m py_compile tools\add_bilibili_creator.py`
- [x] `python -m py_compile tools\search_bilibili_keywords.py`
- [x] `python -m py_compile tools\collect_creator_daily_videos.py`
- [x] `python -m py_compile tools\collect_bilibili_comments.py`
- [x] `python -m py_compile tools\summarize_bilibili_comment_focus.py`
- [x] `python -m py_compile tools\build_bilibili_daily_report.py`
- [x] Run one small keyword search. Current B站接口 returned `412`, script handled it and generated CSV/Markdown with 0 rows.
- [x] Run one small creator daily collection. Current B站 space API returned `412` / 风控, script handled it and generated CSV/Markdown with 0 rows.
- [x] Run one small comment collection.
- [x] Generate one comment focus report.
- [x] Generate one daily report.
- [x] Confirm no secrets are printed.
- [x] Confirm generated Markdown can be imported into Obsidian manually or by existing export workflow.

## Implementation Order

1. Task 1: 博主管理。
2. Task 2: 关键词搜索。
3. Task 3: 视频指标补齐。
4. Task 4: 评论抓取。
5. Task 5: 评论关注点总结。
6. Task 6: 每日总报告。
7. Task 7: 文档和知识库同步。

## Self Review

- Spec coverage: 已覆盖添加博主、关键词搜索、视频关键指标、评论关注点总结、知识库/日报输出。
- Placeholder scan: 计划中没有留给实现者自行猜测的 TBD；评论 API 的 WBI 签名可复用现有 `collect_creator_daily_videos.py` 的 `signed_params()` 和 `get_mixin_key()`。
- Type consistency: CSV 字段在数据格式、任务描述和验证命令中保持一致。
