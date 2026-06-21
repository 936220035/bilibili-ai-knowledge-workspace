from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "data" / "exports"
TOPIC_DIR = ROOT / "data" / "topics"

FOCUS_RULES = [
    ("价格/费用", ["多少钱", "价格", "收费", "免费", "会员", "付费", "订阅", "贵", "便宜"]),
    ("上手难度", ["怎么用", "不会", "小白", "入门", "教程", "看不懂", "门槛", "简单吗"]),
    ("部署安装", ["部署", "安装", "配置", "环境", "docker", "本地", "服务器", "报错"]),
    ("效果质疑", ["真的吗", "有用吗", "效果", "垃圾", "骗人", "不行", "翻车", "靠谱吗"]),
    ("替代工具", ["替代", "哪个好", "对比", "cursor", "claude", "chatgpt", "deepseek", "kimi", "通义", "豆包"]),
    ("Bug/报错", ["bug", "报错", "错误", "打不开", "失败", "卡住", "崩", "闪退"]),
    ("使用场景", ["能不能", "可以用来", "适合", "场景", "工作", "自媒体", "剪辑", "编程", "写作"]),
    ("资料需求", ["资料", "链接", "地址", "求", "发一下", "网盘", "源码", "项目"]),
    ("购买意向", ["想买", "怎么买", "购买", "下单", "哪里买", "求推荐"]),
    ("正反馈", ["厉害", "牛", "感谢", "学到了", "有用", "收藏", "支持", "赞"]),
    ("负反馈", ["没用", "差", "水", "标题党", "取关", "浪费", "不如"]),
]


def latest_comments_csv() -> Path:
    paths = sorted(EXPORT_DIR.glob("*bilibili-comments-*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not paths:
        raise FileNotFoundError("No comments CSV found. Run tools\\collect_bilibili_comments.py first.")
    return paths[0]


def classify(message: str) -> str:
    lower = message.lower()
    hits = [name for name, terms in FOCUS_RULES if any(term.lower() in lower for term in terms)]
    return hits[0] if hits else "其他"


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}|[\u4e00-\u9fff]{2,}", text)
    stop = {"这个", "那个", "可以", "就是", "什么", "一下", "真的", "感觉", "视频", "老师", "哈哈"}
    return [word for word in words if word.lower() not in stop]


def load_comments(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_report(path: Path, rows: list[dict[str, str]]) -> Path:
    TOPIC_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d-%H%M")
    bvid = rows[0].get("bvid", "unknown") if rows else "unknown"
    md_path = TOPIC_DIR / f"{stamp}-B站评论关注点分析-{bvid}.md"

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    words: Counter[str] = Counter()
    for row in rows:
        message = row.get("message", "")
        groups[classify(message)].append(row)
        words.update(tokenize(message))

    ranked_groups = sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)
    lines = [
        "# B站评论关注点分析",
        "",
        f"- 生成时间：{datetime.now(timezone(timedelta(hours=8))):%Y-%m-%d %H:%M:%S}",
        f"- 评论来源：`{path.name}`",
        f"- 样本数：{len(rows)}",
        f"- 视频：{bvid}",
        "- 方法：本地关键词规则分类，适合作为初筛；后续可接 MiniMax M3 做更细归纳。",
        "",
        "## 用户最关心的事",
        "",
    ]
    if ranked_groups:
        for name, items in ranked_groups:
            lines.append(f"- {name}：{len(items)} 条")
    else:
        lines.append("- 暂无评论样本。")

    lines.extend(["", "## 高频问题", ""])
    for word, count in words.most_common(20):
        lines.append(f"- {word}：{count}")
    if not words:
        lines.append("- 暂无可统计关键词。")

    lines.extend(["", "## 典型评论样本", ""])
    for name, items in ranked_groups[:8]:
        lines.append(f"### {name}")
        lines.append("")
        for row in sorted(items, key=lambda item: int(float(item.get("like_count") or 0)), reverse=True)[:5]:
            lines.append(f"- {row.get('message', '')}（赞 {row.get('like_count', '0')}）")
        lines.append("")

    lines.extend(
        [
            "## 适合做成选题的角度",
            "",
            "- 把高频疑问做成“问题解释型”短视频或图文。",
            "- 把替代工具和效果质疑做成对比测评。",
            "- 把部署安装、报错类评论做成保姆级教程。",
            "",
            "## 可以沉淀到知识库的资料",
            "",
            "- 用户真实问题分类。",
            "- 高频工具名和替代方案。",
            "- 适合后续内容复用的评论样本。",
            "",
            "## 不建议自动回复的原因",
            "",
            "- 评论语境复杂，自动回复容易误伤或引战。",
            "- 当前系统定位是只读分析和草稿生产，不直接代替真人互动。",
            "- 更稳妥做法是生成回复草稿，由你人工审核后再决定是否发布。",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="分析 B站评论样本里用户真正关心什么")
    parser.add_argument("--comments-csv", type=Path, default=None, help="评论 CSV，默认使用最新评论采集结果")
    args = parser.parse_args()
    source = args.comments_csv or latest_comments_csv()
    rows = load_comments(source)
    md_path = write_report(source, rows)
    print(f"MD={md_path}")


if __name__ == "__main__":
    main()
