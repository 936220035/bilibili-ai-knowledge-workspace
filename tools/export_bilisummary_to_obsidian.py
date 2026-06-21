#!/usr/bin/env python3
"""Export BiliSummary markdown files into the local Obsidian knowledge base."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path(os.environ.get("BILISUMMARY_SUMMARY_DIR", WORKSPACE_ROOT / "bilibili-summary" / "summary"))
DEFAULT_VAULT = Path(os.environ.get("OBSIDIAN_VAULT_PATH", r"C:\Users\龙城\Documents\Obsidian\个人知识库"))
DEFAULT_DEST = DEFAULT_VAULT / "04-资源库" / "学习笔记" / "B站视频总结"
PROJECT_LINK = "[[03-项目库/项目机会/让AI替你看B站项目]]"

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1F]')
BVID_RE = re.compile(r"\*\*BV号\*\*:\s*(BV[0-9A-Za-z]+)")
TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
URL_RE = re.compile(r"\*\*视频链接\*\*:\s*(\S+)")
AUTHOR_RE = re.compile(r"\*\*作者\*\*:\s*(?:\[)?([^\]\n]+)")
GENERATED_RE = re.compile(r"\*\*生成时间\*\*:\s*([^\n]+)")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def yaml_quote(value: object) -> str:
    if value is None:
        return '""'
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def sanitize_filename(name: str, max_len: int = 100) -> str:
    cleaned = INVALID_FILENAME_CHARS.sub("_", name).strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned[:max_len].rstrip() or "未命名")


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def extract_first(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def is_failed_summary(text: str) -> bool:
    failure_markers = [
        "生成总结失败",
        "Could not resolve authentication method",
        "AuthenticationError",
        "字幕不可用",
    ]
    return any(marker in text for marker in failure_markers)


def load_summary(md_path: Path) -> dict:
    text = md_path.read_text(encoding="utf-8", errors="ignore")
    meta = read_json(md_path.with_suffix(".meta.json"))

    title = meta.get("title") or extract_first(TITLE_RE, text) or md_path.stem
    bvid = meta.get("bvid") or extract_first(BVID_RE, text)
    url = meta.get("url") or extract_first(URL_RE, text)
    author = meta.get("author_name") or extract_first(AUTHOR_RE, text)
    generated_at = meta.get("generated_at") or extract_first(GENERATED_RE, text)

    try:
        relative_source_path = str(md_path.relative_to(WORKSPACE_ROOT))
    except ValueError:
        relative_source_path = str(md_path)

    return {
        "title": str(title).strip(),
        "bvid": str(bvid).strip(),
        "url": str(url).strip(),
        "author": str(author).strip(),
        "author_uid": meta.get("author_uid", ""),
        "duration": meta.get("duration", ""),
        "cover_url": meta.get("cover_url", ""),
        "generated_at": str(generated_at).strip(),
        "source_path": str(md_path),
        "relative_source_path": relative_source_path,
        "content": text.strip() + "\n",
        "failed": is_failed_summary(text),
    }


def existing_note_for_bvid(dest_dir: Path, bvid: str) -> Path | None:
    if not bvid or not dest_dir.exists():
        return None
    matches = sorted(dest_dir.glob(f"{bvid} - *.md"))
    return matches[0] if matches else None


def build_note(summary: dict, imported_at: str) -> str:
    frontmatter = [
        "---",
        "type: 学习笔记",
        "source: B站",
        f"title: {yaml_quote(summary['title'])}",
        f"bvid: {yaml_quote(summary['bvid'])}",
        f"author: {yaml_quote(summary['author'])}",
        f"author_uid: {yaml_quote(summary['author_uid'])}",
        f"url: {yaml_quote(summary['url'])}",
        f"duration: {yaml_quote(summary['duration'])}",
        f"generated_at: {yaml_quote(summary['generated_at'])}",
        f"imported_at: {yaml_quote(imported_at)}",
        f"source_summary_path: {yaml_quote(summary['relative_source_path'])}",
        "tags: [B站, 视频总结, AI总结]",
        "---",
        "",
    ]
    header = [
        f"# {summary['title']}",
        "",
        f"- 关联项目：{PROJECT_LINK}",
        f"- 原始视频：{summary['url'] or summary['bvid']}",
        f"- UP 主：{summary['author'] or '未知'}",
        f"- 本地来源：`{summary['relative_source_path']}`",
        "",
        "---",
        "",
    ]
    return "\n".join(frontmatter + header) + summary["content"]


def parse_frontmatter(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {}
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip('"')
        data[key.strip()] = value
    return data


def write_index(dest_dir: Path, imported_at: str) -> None:
    notes = []
    for note in sorted(dest_dir.glob("*.md")):
        if note.name == "README.md":
            continue
        meta = parse_frontmatter(note)
        notes.append({
            "file": note.name,
            "title": meta.get("title") or note.stem,
            "bvid": meta.get("bvid", ""),
            "author": meta.get("author", ""),
            "generated_at": meta.get("generated_at", ""),
            "url": meta.get("url", ""),
        })

    lines = [
        "---",
        "type: 资源索引",
        "source: B站",
        "status: active",
        f"updated: {datetime.now().strftime('%Y-%m-%d')}",
        "---",
        "# B站视频总结",
        "",
        "#B站 #视频总结 #AI总结 #学习笔记",
        "",
        f"- 关联项目：{PROJECT_LINK}",
        f"- 本地导入脚本：`{Path('tools/export_bilisummary_to_obsidian.py')}`",
        f"- 最近导入时间：{imported_at}",
        "",
        "## 视频清单",
        "",
        "| 视频 | BV号 | UP主 | 生成时间 | 原链接 |",
        "|---|---|---|---|---|",
    ]

    for note in notes:
        link = f"[[04-资源库/学习笔记/B站视频总结/{Path(note['file']).stem}|{note['title']}]]"
        url = f"[打开]({note['url']})" if note["url"] else ""
        lines.append(f"| {link} | {note['bvid']} | {note['author']} | {note['generated_at']} | {url} |")

    lines.extend([
        "",
        f"## 更新记录：{imported_at}",
        "",
        "- 修改人/Agent：Codex / 克劳德",
        "- 发起人：用户",
        "- 用户原始要求：我需要这个可以整理成对应的资料存入我的知识库",
        "- 修改原因：把 BiliSummary 输出从项目临时目录同步为 Obsidian 可检索学习笔记。",
        "- 修改内容：刷新 B站视频总结索引，按 BV 号链接已导入的视频总结笔记。",
        "- 影响范围：04-资源库/学习笔记/B站视频总结",
        "- 验证结果：由导入脚本生成索引；失败总结默认跳过。",
        "- 后续动作：后续可给网页增加“导入知识库”按钮，或把脚本接入定时任务。",
        "",
    ])
    (dest_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def export_summary_files(md_paths: list[Path], dest_dir: Path, include_failed: bool, dry_run: bool) -> dict:
    imported_at = now_text()
    dest_dir.mkdir(parents=True, exist_ok=True)

    stats = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "failed_skipped": 0,
        "missing_bvid": 0,
        "notes": [],
    }

    for md_path in sorted(md_paths):
        summary = load_summary(md_path)
        if not summary["bvid"]:
            stats["missing_bvid"] += 1
            continue
        if summary["failed"] and not include_failed:
            stats["failed_skipped"] += 1
            continue

        filename = f"{summary['bvid']} - {sanitize_filename(summary['title'])}.md"
        existing_target = existing_note_for_bvid(dest_dir, summary["bvid"])
        target = existing_target or (dest_dir / filename)
        note_text = build_note(summary, imported_at)

        if target.exists() and target.read_text(encoding="utf-8", errors="ignore") == note_text:
            stats["skipped"] += 1
            stats["notes"].append({
                "status": "skipped",
                "bvid": summary["bvid"],
                "title": summary["title"],
                "path": str(target),
            })
            continue

        if not dry_run:
            target.write_text(note_text, encoding="utf-8")

        if existing_target:
            stats["updated"] += 1
            status = "updated"
        else:
            stats["created"] += 1
            status = "created"
        stats["notes"].append({
            "status": status,
            "bvid": summary["bvid"],
            "title": summary["title"],
            "path": str(target),
        })

    if not dry_run:
        write_index(dest_dir, imported_at)

    stats["dest_dir"] = str(dest_dir)
    stats["imported_at"] = imported_at
    return stats


def export_summaries(source_dir: Path, dest_dir: Path, include_failed: bool, dry_run: bool) -> dict:
    return export_summary_files(list(source_dir.rglob("*.md")), dest_dir, include_failed, dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export BiliSummary markdown notes to Obsidian.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="BiliSummary summary directory.")
    parser.add_argument("--file", type=Path, action="append", default=[], help="Import a specific summary markdown file. Can be repeated.")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="Obsidian destination directory.")
    parser.add_argument("--include-failed", action="store_true", help="Also import failed summary files.")
    parser.add_argument("--dry-run", action="store_true", help="Scan only; do not write files.")
    args = parser.parse_args()

    if args.file:
        missing = [path for path in args.file if not path.exists()]
        if missing:
            raise SystemExit(f"Summary file not found: {missing[0]}")
        stats = export_summary_files(args.file, args.dest, args.include_failed, args.dry_run)
    elif not args.source.exists():
        raise SystemExit(f"Source directory not found: {args.source}")
    else:
        stats = export_summaries(args.source, args.dest, args.include_failed, args.dry_run)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
