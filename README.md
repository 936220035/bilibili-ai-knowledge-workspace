# 让 AI 替你看 B站

这是一个基于 BiliSummary 和 bilibili-ai-bot 二次整理的 B站 AI 内容研究工作区。

目标不是“全自动刷号”，而是把 B站公开内容变成可复用的知识、选题和本地资料：

```text
关键词 / 博主 -> 公开视频采集 -> 指标整理 -> 评论关注点分析 -> 视频总结 -> 本地知识库 / Obsidian
```

默认只读 / 草稿模式，不自动点赞、投币、评论、私信、关注或发动态。

## 目录

```text
bilibili-summary/  # 视频总结工具，本仓库包含本地二开的知识库页面
bilibili-ai-bot/   # B站 Agent 实验项目，默认只做研究参考和 dry-run
data/              # 本地配置示例；运行产物默认不提交
docs/              # 部署记录、使用规则、测试记录
tools/             # 只读采集、评论分析、Obsidian 导入等脚本
```

## 当前状态

- `bilibili-summary`：已二开本地网页，增加关键词搜索、最新总结、知识库页、导入 Obsidian 按钮。
- `bilibili-ai-bot`：作为研究参考保留，默认不启动真实互动主循环。
- 已跑通不登录的公开视频只读草稿流程。
- `bilibili-summary` 支持 Anthropic-compatible API，可配置 MiniMax M3 等模型。
- 已新增 B站 AI 博主收集和精选脚本，可输出 CSV / Markdown 清单。
- 已新增 B站内容洞察脚本，可维护博主名单、关键词搜索、抓取公开视频指标、分析评论关注点并生成日报。
- 已新增 BiliSummary 到 Obsidian 的导入脚本，可把有效视频总结整理为知识库学习笔记。
- 未启动任何真实互动动作。

## 快速开始

### 1. BiliSummary

```powershell
cd bilibili-summary
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
Copy-Item .env.example .env.local
```

编辑 `bilibili-summary/.env.local`，填入自己的模型 API 配置。不要提交这个文件。

启动网页服务：

```powershell
.\.venv\Scripts\python.exe server.py
```

访问：

```text
http://127.0.0.1:18520
```

### 2. 工作区脚本

在项目根目录运行：

```powershell
python tools\search_bilibili_keywords.py AI工具 Cursor教程 --pages 1
python tools\collect_bilibili_comments.py <BV号或视频链接> --limit 80 --mode new
python tools\summarize_bilibili_comment_focus.py --comments-csv <评论CSV>
python tools\build_bilibili_daily_report.py
```

## 常用命令

```powershell
# 只读拉取公开视频信息，生成总结/选题/评论草稿
python tools\fetch_bilibili_video_draft.py "https://www.bilibili.com/video/BV1vezvBsEzV/"

# BiliSummary 环境检查
python tools\check_bilisummary.py

# bilibili-ai-bot dry-run 草稿检查
python tools\bilibili_ai_dry_run.py

# 收集 B站 AI 博主候选
python tools\collect_bilibili_ai_creators.py --pages 2 --limit 120

# 合并最近收集结果，生成精选行动清单
python tools\curate_bilibili_ai_creators.py

# 收集精选 AI 博主最近更新视频，并生成每日分析
python tools\collect_creator_daily_videos.py --creator-limit 50 --days 7

# 添加或更新一个长期监控博主
python tools\add_bilibili_creator.py <UID或空间链接> --name <博主名> --priority P1 --tags AI工具

# 按关键词搜索 B站公开视频
python tools\search_bilibili_keywords.py AI工具 Cursor教程 --pages 1

# 抓取某个视频的公开评论样本
python tools\collect_bilibili_comments.py <BV号或视频链接> --limit 80

# 分析评论里用户真正关心什么
python tools\summarize_bilibili_comment_focus.py --comments-csv <评论CSV>

# 生成 B站 AI 内容洞察日报
python tools\build_bilibili_daily_report.py

# 把 bilibili-summary 已生成的视频总结导入 Obsidian 知识库
python tools\export_bilisummary_to_obsidian.py
```

## 安全边界

- 默认不登录 B站；如需登录，只建议用于收藏夹读取和字幕/总结能力。
- 默认不填真实 Cookie。
- 默认不启用自动点赞、投币、评论、私信、关注、发动态。
- 所有草稿和采集结果先落到本地，人工审核后再决定是否使用。
- `.env`、Cookie、Token、`config.json`、总结资料、字幕缓存、日志、虚拟环境都不提交 Git。
- 请遵守 B站平台规则、版权规则和当地法律法规。

## 公开仓库说明

本仓库适合作为长期二开主仓库维护。公开上传前请确认：

- `git status` 中没有 `.env.local`、Cookie、Token、日志、个人总结资料。
- `bilibili-summary/summary/`、`bilibili-summary/ass/`、`data/exports/`、`data/topics/` 等运行产物未被提交。
- `bilibili-ai-bot/config.json` 未被提交。
- 已保留上游项目协议和来源说明，见 `NOTICE.md`。

## 上游来源与协议

- `bilibili-summary`：上游 README 标注 MIT License。
- `bilibili-ai-bot`：MIT License，详见 `bilibili-ai-bot/LICENSE`。
- 本仓库新增脚本、文档和二开代码按 MIT License 发布；原项目版权归原作者所有。

## 下一步

1. 先用 `python tools\add_bilibili_creator.py ...` 建立长期监控名单。
2. 用 `python tools\search_bilibili_keywords.py ...` 找选题和竞品视频。
3. 对高价值视频抓评论并运行关注点总结，再生成日报。
4. 继续用 `bilibili-summary` 生成有效视频总结，并定期运行 `python tools\export_bilisummary_to_obsidian.py` 导入知识库。
