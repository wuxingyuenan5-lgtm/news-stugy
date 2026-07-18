# News Study Reference Project

这是一个用于采集和整理研究型内容源的参考项目。目前新增了一条尽量简单、可直接运行的内容整理MVP。

## 当前最小主链路

```text
JSON内容输入
→ SQLite存储
→ 规则分析
→ 简单去重与分组
→ Markdown晚报
```

该主链路的目标不是一次完成全部架构，而是先验证内容整理结果是否可用。

## 快速运行MVP

运行环境：Python 3.11+。当前不需要第三方依赖，也不需要API密钥。

```bash
python -m app.main
```

默认读取：

```text
examples/sample_items.json
```

默认生成：

```text
data/app.db
data/reports/evening-YYYY-MM-DD.md
```

指定参数：

```bash
python -m app.main \
  --input examples/sample_items.json \
  --db data/app.db \
  --output-dir data/reports \
  --date 2026-07-18
```

输入文件必须是JSON数组：

```json
[
  {
    "source": "来源名称",
    "platform": "web",
    "title": "标题",
    "content": "正文或摘要",
    "url": "https://example.com/item",
    "published_at": "2026-07-18T10:00:00+09:00"
  }
]
```

只有`title`是强制字段。正文缺失时，系统不会根据标题扩写事实。

## MVP代码

```text
app/
├─ __init__.py
├─ main.py
└─ schema.sql
```

SQLite当前只保留五张表：

- `sources`
- `items`
- `analyses`
- `clusters`
- `reports`

当前分析和聚类使用确定性规则。后续优先替换`analyze_item()`和聚类判断，再接入模型，不扩张其他架构。

## 仓库现有参考能力

- `skills/x-fetch/`：抓取X/Twitter时间线与帖子，并做规则化分类、去重和摘要排版。
- `wx_public_monitor.py`：基于公众号文章线索与第三方接口，跟踪公众号最新文章。
- `feishu_channel_bot.py` / `feishu_bot.py`：飞书机器人接入OpenAI，对话式分发与交互。
- `meitoujun_recent5.json`：YouTube方向的历史样例数据，当前不构成完整抓取链路。

这些旧模块暂时作为参考，不强行并入MVP主链。

## 当前限制

- 尚未接入真实统一采集器；
- 尚未接入LLM；
- 尚未生成市场行情看板；
- 规则聚类只适合初步验证；
- 正式发布前仍需人工复核。

## 下一步

1. 使用20至50条真实内容替换示例数据；
2. 检查首份晚报的去重、分类和可读性；
3. 接入一个模型完成结构化分析；
4. 再接入5至10个稳定真实来源。

在第一份真实晚报验证完成前，不新增复杂架构模块。
