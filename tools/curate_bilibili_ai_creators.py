from __future__ import annotations

import csv
import math
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "data" / "exports"
TOPIC_DIR = ROOT / "data" / "topics"

FOCUS_TERMS = {
    "ai工具箱": 22,
    "ai工具": 14,
    "智能体": 20,
    "agent": 18,
    "工作流": 18,
    "自动化": 16,
    "coze": 16,
    "dify": 16,
    "rag": 14,
    "cursor": 18,
    "codex": 18,
    "claude": 16,
    "ai编程": 18,
    "知识库": 14,
    "obsidian": 14,
    "普通人": 10,
}

SPAM_TERMS = {
    "少走99%": 10,
    "七天": 6,
    "就业": 8,
    "变现": 6,
    "免费领取": 5,
    "咨询课程": 8,
    "加我": 5,
    "助理": 4,
    "草履虫": 5,
    "全套教程": 5,
}


def latest_csvs(limit: int = 6) -> list[Path]:
    return sorted(EXPORT_DIR.glob("*bilibili-ai-creators.csv"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def as_int(value: str) -> int:
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def as_float(value: str) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def text_of(row: dict[str, str]) -> str:
    return " ".join(
        [
            row.get("name", ""),
            row.get("category", ""),
            row.get("keywords", ""),
            row.get("sign", ""),
            row.get("sample_video_titles", ""),
        ]
    ).lower()


def focus_score(row: dict[str, str]) -> float:
    text = text_of(row)
    fans = as_int(row.get("fans", "0"))
    videos = as_int(row.get("videos", "0"))
    base = as_float(row.get("score", "0"))
    score = base * 0.45 + math.log10(fans + 10) * 12 + math.log10(videos + 10) * 5
    for term, weight in FOCUS_TERMS.items():
        if term in text:
            score += weight
    for term, weight in SPAM_TERMS.items():
        if term.lower() in text:
            score -= weight
    if 1_000 <= fans <= 80_000:
        score += 8
    if fans > 500_000 and "ai编程" not in text and "智能体" not in text:
        score -= 8
    return round(score, 2)


def compact(value: str, max_len: int = 90) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value if len(value) <= max_len else value[: max_len - 1] + "…"


def reason(row: dict[str, str]) -> str:
    text = text_of(row)
    bits: list[str] = []
    if any(term in text for term in ["cursor", "codex", "claude", "ai编程"]):
        bits.append("AI编程/Agent Coding")
    if any(term in text for term in ["智能体", "agent", "coze", "dify", "工作流"]):
        bits.append("智能体/工作流")
    if any(term in text for term in ["工具箱", "办公", "效率", "自动化"]):
        bits.append("AI工具箱/效率")
    if any(term in text for term in ["知识库", "obsidian", "rag"]):
        bits.append("知识库/RAG")
    if not bits:
        bits.append(row.get("category", "AI"))
    return "、".join(bits[:3])


def priority(row: dict[str, str]) -> str:
    fans = as_int(row.get("fans", "0"))
    score = focus_score(row)
    text = text_of(row)
    if score >= 100 and fans >= 20_000:
        return "P0"
    if any(term in text for term in ["cursor", "codex", "智能体", "工作流", "工具箱"]) and fans >= 1_000:
        return "P1"
    return "P2"


def load_rows(paths: list[Path]) -> list[dict[str, str]]:
    by_mid: dict[str, dict[str, str]] = {}
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                mid = row.get("mid", "").strip()
                if not mid:
                    continue
                old = by_mid.get(mid)
                if old is None or focus_score(row) > focus_score(old):
                    by_mid[mid] = row
    rows = list(by_mid.values())
    rows.sort(key=lambda row: (focus_score(row), as_int(row.get("fans", "0"))), reverse=True)
    return rows


def pick(rows: list[dict[str, str]], predicate, count: int) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        mid = row.get("mid", "")
        if mid in seen or not predicate(row):
            continue
        out.append(row)
        seen.add(mid)
        if len(out) >= count:
            break
    return out


def write_table(lines: list[str], rows: list[dict[str, str]]) -> None:
    lines.append("| 优先级 | 博主 | 方向 | 粉丝 | 视频数 | 为什么看 | 主页 |")
    lines.append("|---|---|---|---:|---:|---|---|")
    for row in rows:
        lines.append(
            "| {priority} | {name} | {category} | {fans} | {videos} | {why} | [主页]({url}) |".format(
                priority=priority(row),
                name=row.get("name", ""),
                category=row.get("category", ""),
                fans=row.get("fans", "0"),
                videos=row.get("videos", "0"),
                why=reason(row),
                url=row.get("url", ""),
            )
        )


def write_outputs(rows: list[dict[str, str]], source_paths: list[Path]) -> tuple[Path, Path]:
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    csv_path = EXPORT_DIR / f"{stamp}-bilibili-ai-creators-curated.csv"
    md_path = TOPIC_DIR / f"{stamp}-B站AI博主精选行动清单.md"

    fieldnames = [
        "priority",
        "focus_score",
        "reason",
        "category",
        "name",
        "mid",
        "url",
        "fans",
        "videos",
        "keywords",
        "sign",
        "sample_video_titles",
        "sample_video_urls",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{key: row.get(key, "") for key in fieldnames},
                    "priority": priority(row),
                    "focus_score": focus_score(row),
                    "reason": reason(row),
                }
            )

    def has(*terms: str):
        return lambda row: any(term in text_of(row) for term in terms)

    long_watch = pick(rows, lambda row: priority(row) in {"P0", "P1"} and as_int(row.get("fans", "0")) >= 5_000, 20)
    topic_mining = pick(rows, has("工具箱", "普通人", "办公", "自动化", "效率", "副业", "变现"), 20)
    peers = pick(rows, has("智能体", "agent", "工作流", "coze", "dify", "ai编程", "cursor", "codex", "claude"), 20)
    collab = pick(
        rows,
        lambda row: 1_000 <= as_int(row.get("fans", "0")) <= 50_000
        and has("智能体", "工作流", "工具箱", "ai编程", "cursor", "codex")(row),
        12,
    )

    lines = [
        "# B站 AI 博主精选行动清单",
        "",
        f"- 生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
        f"- 合并候选：{len(rows)} 个",
        "- 用途：给你后面做 AI 工具箱、AI 自动化、知识库、Agent/Codex/Cursor 相关选题用。",
        "- 说明：这是本地粗筛，不代表账号质量背书；建议先看主页最近 5 条视频再决定是否长期关注。",
        f"- 来源文件：{', '.join(path.name for path in source_paths)}",
        "",
        "## 我建议先看这 20 个",
        "",
    ]
    write_table(lines, long_watch)
    lines.extend(["", "## 适合拆选题", ""])
    write_table(lines, topic_mining)
    lines.extend(["", "## 同行/竞品参考", ""])
    write_table(lines, peers)
    lines.extend(["", "## 适合互动或合作观察", ""])
    write_table(lines, collab)
    lines.extend(["", "## 使用建议", ""])
    lines.extend(
        [
            "1. 先打开“我建议先看这 20 个”，每个账号只看最近 5 条视频标题。",
            "2. 把适合你账号定位的标题丢给本地总结服务，拆成选题、结构、封面关键词。",
            "3. 对“同行/竞品参考”只学习选题和包装，不要照搬脚本。",
            "4. 对“适合互动或合作观察”可以先手动关注和评论，暂时不要让机器人自动操作。",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return csv_path, md_path


def main() -> None:
    paths = latest_csvs()
    if not paths:
        raise SystemExit("No source CSV found.")
    rows = load_rows(paths)
    csv_path, md_path = write_outputs(rows, paths)
    print(f"COUNT={len(rows)}")
    print(f"CSV={csv_path}")
    print(f"MD={md_path}")


if __name__ == "__main__":
    main()
