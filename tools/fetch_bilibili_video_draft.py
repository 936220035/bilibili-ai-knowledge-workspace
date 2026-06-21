from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_DIR = ROOT / "data" / "summaries"
TOPIC_DIR = ROOT / "data" / "topics"
COMMENT_DIR = ROOT / "data" / "comment-drafts"


def extract_bvid(value: str) -> str:
    match = re.search(r"BV[0-9A-Za-z]+", value)
    if not match:
        raise SystemExit("未找到 BV 号，请传入 B站视频链接或 BV 号")
    return match.group(0)


def fetch_video(bvid: str) -> dict:
    query = urllib.parse.urlencode({"bvid": bvid})
    url = f"https://api.bilibili.com/x/web-interface/view?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 dry-run-bilibili-summary",
            "Referer": "https://www.bilibili.com/",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("code") != 0:
        raise SystemExit(f"B站接口返回失败：{payload.get('message')}")
    return payload["data"]


def write_outputs(video: dict) -> list[Path]:
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    TOPIC_DIR.mkdir(parents=True, exist_ok=True)
    COMMENT_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    bvid = video["bvid"]
    title = video.get("title", "").strip()
    owner = video.get("owner", {})
    desc = (video.get("desc") or "").strip()
    url = f"https://www.bilibili.com/video/{bvid}/"
    safe = re.sub(r'[\\/:*?"<>|]+', "-", title)[:60] or bvid

    summary = SUMMARY_DIR / f"{now:%Y-%m-%d}-{bvid}-{safe}.md"
    topics = TOPIC_DIR / f"{now:%Y-%m-%d}-{bvid}-选题草稿.md"
    comments = COMMENT_DIR / f"{now:%Y-%m-%d}-{bvid}-评论草稿.md"

    summary.write_text(
        "\n".join(
            [
                f"# {title}",
                "",
                f"- 链接：{url}",
                f"- BV号：{bvid}",
                f"- UP主：{owner.get('name', '')}",
                f"- UP主 UID：{owner.get('mid', '')}",
                f"- 分区：{video.get('tname', '')}",
                f"- 播放：{video.get('stat', {}).get('view', '')}",
                f"- 收藏：{video.get('stat', {}).get('favorite', '')}",
                f"- 投币：{video.get('stat', {}).get('coin', '')}",
                f"- 评论：{video.get('stat', {}).get('reply', '')}",
                "",
                "## 简介",
                "",
                desc or "公开视频信息未提供简介。",
                "",
                "## 可复用观点",
                "",
                "- 这是只读草稿，后续可接模型补充完整总结。",
                "- 适合先人工判断是否进入龙城AI工具箱选题池。",
                "",
            ]
        ),
        encoding="utf-8",
    )

    topics.write_text(
        "\n".join(
            [
                f"# {title} - 选题草稿",
                "",
                f"- 来源：{url}",
                "- 可做选题：把这个视频拆成“普通人能照着做”的教程/避坑清单。",
                "- 适合项目：龙城AI工具箱 / AI工具免费带教。",
                "- 下一步：人工看视频或接 BiliSummary 模型总结后扩写。",
                "",
            ]
        ),
        encoding="utf-8",
    )

    comments.write_text(
        "\n".join(
            [
                f"# {title} - 评论草稿",
                "",
                f"- 来源：{url}",
                "- 草稿 1：这个主题挺适合做成一步步教程，先收藏起来慢慢看。",
                "- 草稿 2：最有价值的是把流程讲清楚，比单纯推荐工具实用多了。",
                "",
                "说明：这是 dry-run 草稿，没有调用 B站评论接口。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return [summary, topics, comments]


def main() -> None:
    parser = argparse.ArgumentParser(description="只读生成 B站视频总结/选题/评论草稿")
    parser.add_argument("video", help="B站视频链接或 BV 号")
    args = parser.parse_args()
    bvid = extract_bvid(args.video)
    video = fetch_video(bvid)
    for path in write_outputs(video):
        print(path)


if __name__ == "__main__":
    main()
