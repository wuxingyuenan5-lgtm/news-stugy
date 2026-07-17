# News Study Reference Project

这是一个用于采集和整理研究型内容源的参考项目，不是生产环境成品。

当前仓库主要包含四块能力：

- `skills/x-fetch/`：抓取 X/Twitter 时间线与帖子，并做规则化分类、去重和摘要排版。
- `wx_public_monitor.py`：基于公众号文章线索与第三方接口，跟踪公众号最新文章。
- `feishu_channel_bot.py` / `feishu_bot.py`：飞书机器人接入 OpenAI，对话式分发与交互。
- `meitoujun_recent5.json`：YouTube 方向的历史样例数据，当前不构成完整抓取链路。

## 仓库定位

- 这是参考项目：保留可运行脚本、样例输出和部分实验痕迹，方便后续拆分、重构和二次开发。
- 这不是完整闭环系统：目前没有统一任务编排、统一数据模型和稳定的生产级调度。
- 这不是即插即用模板：部分脚本依赖本地环境、第三方接口或人工维护的目标列表。

## 目录说明

```text
.
├─ skills/x-fetch/          X 信息抓取与日报样例
├─ watch_targets/           公众号监控目标
├─ docs/                    补充文档
├─ feishu_bot.py            飞书 webhook 版机器人
├─ feishu_channel_bot.py    飞书长连接版机器人
├─ wx_public_monitor.py     公众号监控脚本
├─ meitoujun_recent5.json   YouTube 样例数据
└─ requirements.txt         Python 依赖
```

## 快速开始

1. 安装依赖

```powershell
python -m pip install -r requirements.txt
```

2. 复制环境变量模板并补齐配置

```powershell
Copy-Item .env.example .env
```

3. 按模块运行

- 飞书长连接机器人：`python feishu_channel_bot.py`
- 飞书 webhook 机器人：`python feishu_bot.py`
- 公众号监控：`python wx_public_monitor.py`
- X 抓取能力：见 `skills/x-fetch/SKILL.md` 与 `skills/x-fetch/scripts/`

## 已知限制

- X 抓取链路对外部站点可用性较敏感。
- 公众号链路依赖第三方接口，不适合视为长期稳定底座。
- 飞书对话历史默认仅驻留内存，服务重启后丢失。
- YouTube 部分目前只有样例数据，没有完整自动化抓取脚本。

## 后续建议

- 先抽象统一内容模型：`source / author / published_at / title / body / url / tags`
- 再补 YouTube 抓取器和统一状态存储
- 最后接飞书日报、告警和任务调度，形成闭环
