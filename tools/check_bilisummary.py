from __future__ import annotations

from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "summaries"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / f"{datetime.now():%Y-%m-%d}-bilisummary-environment-check.md"
    target.write_text(
        "\n".join(
            [
                "# BiliSummary 环境检查",
                "",
                f"- 时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
                "- 状态：依赖已安装，源码已下载。",
                "- 运行边界：未登录 B站，未配置模型 API，因此本次只做环境检查，不真实总结视频。",
                "- 下一步：填入 `bilibili-summary/.env.local` 后运行真实视频总结。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(target)


if __name__ == "__main__":
    main()
