from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "data" / "config" / "bilibili_creators.csv"
FIELDS = ["mid", "name", "profile_url", "priority", "tags", "reason", "source", "created_at", "updated_at", "enabled"]


def now_text() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


def extract_mid(value: str) -> str:
    value = value.strip()
    match = re.search(r"space\.bilibili\.com/(\d+)", value)
    if match:
        return match.group(1)
    if re.fullmatch(r"\d{2,}", value):
        return value
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
    for row in rows:
        if row.get("mid") == mid:
            row.update(
                {
                    "name": args.name or row.get("name", ""),
                    "profile_url": f"https://space.bilibili.com/{mid}",
                    "priority": args.priority,
                    "tags": args.tags,
                    "reason": args.reason,
                    "source": args.source,
                    "updated_at": stamp,
                    "enabled": "1",
                }
            )
            write_rows(rows)
            return CONFIG

    rows.append(
        {
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
        }
    )
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
