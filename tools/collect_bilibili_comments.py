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
from datetime import datetime, timedelta, timezone
from http.cookiejar import CookieJar
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "data" / "exports"
TOPIC_DIR = ROOT / "data" / "topics"
FIELDS = ["bvid", "rpid", "ctime", "uname", "mid", "like_count", "message", "parent_rpid", "root_rpid"]
BILI_MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]


class BiliClient:
    def __init__(self) -> None:
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def open_text(self, url: str, referer: str = "https://www.bilibili.com/") -> str:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
                "Referer": referer,
                "Accept": "application/json,text/plain,*/*",
            },
        )
        with self.opener.open(req, timeout=25) as response:
            return response.read().decode("utf-8", "ignore")

    def json(self, url: str, referer: str = "https://www.bilibili.com/") -> dict:
        return json.loads(self.open_text(url, referer))


def extract_bvid(value: str) -> str:
    value = value.strip()
    match = re.search(r"(BV[0-9A-Za-z]+)", value)
    if match:
        return match.group(1)
    raise SystemExit("无法识别 BV 号。请传 BV 号或视频链接")


def as_int(value: object) -> int:
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def clean_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "")
    return value.strip()


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
    cleaned = {key: re.sub(r"[!'()*]", "", str(value)) for key, value in params.items()}
    query = urllib.parse.urlencode(sorted(cleaned.items()), safe=safe)
    w_rid = hashlib.md5((query + mixin_key).encode("utf-8")).hexdigest()
    return query + "&w_rid=" + w_rid


def fetch_video_info(client: BiliClient, bvid: str) -> dict:
    payload = client.json(f"https://api.bilibili.com/x/web-interface/view?bvid={urllib.parse.quote(bvid)}")
    if payload.get("code") != 0:
        raise RuntimeError(str(payload.get("message") or payload.get("code")))
    return payload.get("data") or {}


def fetch_comments(client: BiliClient, bvid: str, aid: str, mixin_key: str, limit: int, mode: str, sleep: float) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    pagination = ""
    mode_value = 3 if mode == "hot" else 2
    while len(rows) < limit:
        params = {
            "oid": aid,
            "type": 1,
            "mode": mode_value,
            "plat": 1,
            "web_location": "1315875",
        }
        if pagination:
            params["pagination_str"] = pagination
        query = signed_params(params, mixin_key)
        payload = client.json(f"https://api.bilibili.com/x/v2/reply/wbi/main?{query}", f"https://www.bilibili.com/video/{bvid}/")
        if payload.get("code") != 0:
            raise RuntimeError(str(payload.get("message") or payload.get("code")))
        data = payload.get("data") or {}
        replies = data.get("replies") or []
        if not replies:
            break
        for reply in replies:
            member = reply.get("member") or {}
            content = reply.get("content") or {}
            rows.append(
                {
                    "bvid": bvid,
                    "rpid": reply.get("rpid", ""),
                    "ctime": datetime.fromtimestamp(as_int(reply.get("ctime")), timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
                    "uname": clean_text(str(member.get("uname") or "")),
                    "mid": member.get("mid", ""),
                    "like_count": as_int(reply.get("like")),
                    "message": clean_text(str(content.get("message") or "")),
                    "parent_rpid": reply.get("parent", ""),
                    "root_rpid": reply.get("root", ""),
                }
            )
            if len(rows) >= limit:
                break
        cursor = data.get("cursor") or {}
        pagination = json.dumps({"offset": cursor.get("pagination_reply", {}).get("next_offset", "")}, ensure_ascii=False)
        if not pagination or pagination == '{"offset": ""}':
            break
        time.sleep(sleep)
    return rows


def write_outputs(rows: list[dict[str, object]], bvid: str, title: str) -> tuple[Path, Path]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    TOPIC_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d-%H%M")
    csv_path = EXPORT_DIR / f"{stamp}-bilibili-comments-{bvid}.csv"
    md_path = TOPIC_DIR / f"{stamp}-B站评论样本-{bvid}.md"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})
    lines = [
        f"# B站评论样本 - {title or bvid}",
        "",
        f"- 视频：https://www.bilibili.com/video/{bvid}/",
        f"- 评论数：{len(rows)}",
        "- 说明：只读抓取公开评论样本，用于分析用户关注点。",
        "",
        "| 时间 | 用户 | 点赞 | 评论 |",
        "|---|---|---:|---|",
    ]
    for row in rows[:100]:
        lines.append(f"| {row['ctime']} | {row['uname']} | {row['like_count']} | {row['message']} |")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return csv_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="只读抓取 B站公开视频评论样本")
    parser.add_argument("bvid_or_url", help="BV 号或视频链接")
    parser.add_argument("--limit", type=int, default=80, help="最多抓取评论数")
    parser.add_argument("--mode", choices=["hot", "new"], default="hot", help="评论排序")
    parser.add_argument("--sleep", type=float, default=0.8, help="翻页请求间隔秒数")
    args = parser.parse_args()

    bvid = extract_bvid(args.bvid_or_url)
    client = BiliClient()
    info = fetch_video_info(client, bvid)
    mixin_key = get_mixin_key(client)
    rows = fetch_comments(client, bvid, str(info.get("aid", "")), mixin_key, args.limit, args.mode, args.sleep)
    csv_path, md_path = write_outputs(rows, bvid, str(info.get("title") or ""))
    print(f"COUNT={len(rows)}")
    print(f"CSV={csv_path}")
    print(f"MD={md_path}")


if __name__ == "__main__":
    main()
