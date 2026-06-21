from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "data" / "exports"
TOPIC_DIR = ROOT / "data" / "topics"


def latest(pattern: str) -> Path | None:
    paths = sorted(EXPORT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return paths[0] if paths else None


def latest_topic(pattern: str) -> Path | None:
    paths = sorted(TOPIC_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return paths[0] if paths else None


def read_csv(path: Path | None) -> list[dict[str, str]]:
    if not path or not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def as_int(value: object) -> int:
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def score_video(row: dict[str, str]) -> int:
    return as_int(row.get("play")) + as_int(row.get("like")) * 8 + as_int(row.get("favorite")) * 10 + as_int(row.get("reply")) * 12


def excerpt_comment_focus(path: Path | None) -> list[str]:
    if not path or not path.exists():
        return ["- 暂无评论关注点分析。"]
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = []
    capture = False
    for line in text.splitlines():
        if line.startswith("## 用户最关心的事"):
            capture = True
            continue
        if capture and line.startswith("## "):
            break
        if capture and line.strip():
            lines.append(line)
    return lines[:12] or [f"- 已生成评论关注点分析：`{path.name}`"]


def write_report(args: argparse.Namespace) -> Path:
    TOPIC_DIR.mkdir(parents=True, exist_ok=True)
    creator_csv = Path(args.creator_csv) if args.creator_csv else latest("*bilibili-ai-creator-daily-videos.csv")
    keyword_csv = Path(args.keyword_csv) if args.keyword_csv else latest("*bilibili-keyword-search*.csv")
    comment_md = Path(args.comment_focus_md) if args.comment_focus_md else latest_topic("*B站评论关注点分析*.md")
    creator_rows = read_csv(creator_csv)
    keyword_rows = read_csv(keyword_csv)
    hot_creator = sorted(creator_rows, key=score_video, reverse=True)[:12]
    hot_keyword = sorted(keyword_rows, key=lambda row: as_int(row.get("play")), reverse=True)[:12]

    today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    md_path = TOPIC_DIR / f"{today}-B站AI内容洞察日报.md"
    lines = [
        "# B站 AI 内容洞察日报",
        "",
        f"- 生成时间：{datetime.now(timezone(timedelta(hours=8))):%Y-%m-%d %H:%M:%S}",
        f"- 博主更新来源：`{creator_csv.name if creator_csv else '无'}`",
        f"- 关键词来源：`{keyword_csv.name if keyword_csv else '无'}`",
        f"- 评论分析来源：`{comment_md.name if comment_md else '无'}`",
        "- 安全边界：只读公开数据，不自动互动。",
        "",
        "## 今日值得看的视频",
        "",
    ]
    if hot_creator:
        for row in hot_creator[:8]:
            lines.append(f"- [{row.get('title', '')}]({row.get('url', '')})｜{row.get('creator_name', '')}｜{row.get('category', '')}｜{row.get('talks_about', '')}")
    else:
        lines.append("- 暂无博主更新数据。")

    lines.extend(["", "## 今日高互动视频", ""])
    pool = hot_creator or hot_keyword
    if pool:
        lines.append("| 视频 | UP主 | 播放 | 点赞 | 收藏 | 评论 |")
        lines.append("|---|---|---:|---:|---:|---:|")
        for row in pool[:10]:
            lines.append(
                f"| [{row.get('title', '')}]({row.get('url', '')}) | {row.get('creator_name') or row.get('author', '')} | "
                f"{row.get('play', '')} | {row.get('like', '')} | {row.get('favorite', '')} | {row.get('reply', row.get('danmaku', ''))} |"
            )
    else:
        lines.append("- 暂无可排序视频。")

    lines.extend(["", "## 关键词趋势", ""])
    if hot_keyword:
        for row in hot_keyword[:10]:
            lines.append(f"- {row.get('keyword', '')}：[{row.get('title', '')}]({row.get('url', '')})，UP主 {row.get('author', '')}，播放 {row.get('play', '')}")
    else:
        lines.append("- 暂无关键词搜索数据。")

    lines.extend(["", "## 评论里用户真正关心什么", ""])
    lines.extend(excerpt_comment_focus(comment_md))

    lines.extend(
        [
            "",
            "## 可做成知识库资料",
            "",
            "- 高价值视频总结。",
            "- 评论中的真实问题分类。",
            "- 工具对比、部署报错、使用场景资料卡。",
            "",
            "## 可做成视频/文章选题",
            "",
            "- 把播放和评论都高的视频拆成同主题选题。",
            "- 把评论里的疑问做成答疑型内容。",
            "- 把同关键词下多个视频合并成趋势观察。",
            "",
            "## 明天继续监控什么",
            "",
            "- P0/P1 博主当天更新。",
            "- AI工具、Cursor教程、Agent工作流、知识库/RAG 等关键词。",
            "- 高评论视频的用户关注点变化。",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 B站 AI 内容洞察日报")
    parser.add_argument("--creator-csv", default="", help="博主视频 CSV，默认最新")
    parser.add_argument("--keyword-csv", default="", help="关键词搜索 CSV，默认最新")
    parser.add_argument("--comment-focus-md", default="", help="评论关注点 Markdown，默认最新")
    args = parser.parse_args()
    md_path = write_report(args)
    print(f"MD={md_path}")


if __name__ == "__main__":
    main()
