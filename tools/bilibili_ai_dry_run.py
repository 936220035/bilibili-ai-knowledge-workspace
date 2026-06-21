from __future__ import annotations

from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "comment-drafts"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / f"{datetime.now():%Y-%m-%d}-bilibili-ai-bot-dry-run.md"
    target.write_text(
        "\n".join(
            [
                "# bilibili-ai-bot dry-run 草稿",
                "",
                f"- 时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
                "- 模式：只读 / 草稿模式",
                "- 真实点赞：关闭",
                "- 真实投币：关闭",
                "- 真实评论：关闭",
                "- 真实私信：关闭",
                "- 真实关注：关闭",
                "",
                "## 示例视频分析草稿",
                "",
                "- 视频主题：待填入真实 B站链接后分析",
                "- 可复用观点：先总结，再人工审核",
                "- 评论草稿：这个流程适合先收藏，照着跑一遍再决定要不要深用。",
                "",
                "## 说明",
                "",
                "这个文件由安全 dry-run 脚本生成，没有调用 B站写入接口。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(target)


if __name__ == "__main__":
    main()
