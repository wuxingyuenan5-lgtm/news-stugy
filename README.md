# News Study

这是一个面向跨资产研究的信息整理项目。V1只解决两个问题：

1. 今天发生了什么；
2. 接下来有哪些事件值得关注。

V1不解释市场涨跌，不提供交易建议，也不补写来源中没有明确给出的因果关系。

## 当前主链路

```text
RSS / JSON内容输入
→ SQLite存储
→ 规则分析与事实抽取
→ 精确去重
→ 多来源事件融合
→ 重要性排序
→ Markdown日报
```

当前版本不需要第三方依赖，也不需要API密钥。RSS采集、日报生成和测试均可仅使用Python标准库运行。

## 真实RSS日报

首批真实来源为美联储官方RSS：

- Monetary Policy Press Releases；
- Speeches。

源配置位于：

```text
config/rss_sources.json
```

第一步，采集最近72小时内容：

```bash
python -m app.rss_collector \
  --config config/rss_sources.json \
  --output data/inbox/rss-items.json \
  --since-hours 72
```

第二步，生成日报：

```bash
python -m app.main \
  --input data/inbox/rss-items.json \
  --db data/app.db \
  --output-dir data/reports \
  --date 2026-07-19
```

安装项目后也可使用命令：

```bash
news-study-rss --config config/rss_sources.json --output data/inbox/rss-items.json
news-study --input data/inbox/rss-items.json --date 2026-07-19
```

RSS采集参数：

- `--since-hours 72`：只保留最近72小时；传入负数可关闭时间过滤；
- `--limit-per-feed 30`：每个Feed最多读取30条；
- `--timeout 20`：单个来源请求超时秒数；
- 单个来源失败时继续处理其他来源；所有来源均失败时返回非零退出码；
- 输出文件采用临时文件替换，避免中途失败留下不完整JSON。

## 使用本地样例

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

使用更完整的跨资产样例：

```bash
python -m app.main \
  --input examples/market_day_items.json \
  --db data/market-day.db \
  --output-dir data/reports \
  --date 2026-07-18
```

## 输入格式

采集器和手工输入统一输出JSON数组：

```json
[
  {
    "source": "来源名称",
    "platform": "media",
    "title": "标题",
    "content": "正文或摘要",
    "url": "https://example.com/item",
    "published_at": "2026-07-18T10:00:00Z"
  }
]
```

只有`title`是强制字段。正文缺失时，系统不会根据标题扩写事实，而是将其标为待补充线索。

建议的`platform`值：

- `official`：政府、央行、监管机构、公司公告；
- `data`：经济日历或结构化数据源；
- `media`：新闻媒体；
- `research`：研究机构；
- `social`：社交媒体或个人观点；
- `metadata`：只有标题或元数据的线索。

## 日报结构

当前日报分为：

```text
今日重点
分类浏览
待补充线索
接下来关注
编辑说明
```

核心规则：

- 多个来源报道同一事件时，只输出一个事件条目；
- 官方来源优先决定标题和事实表达；
- 相同事实不重复书写；
- 观点明确标注，不改写为事实；
- 未来日程进入“接下来关注”；
- 报告按本次输入和报告日期生成，避免旧新闻混入新日报。

详细规范见：

```text
docs/editorial-guidelines.md
```

## 数据库

SQLite仍只保留五张表：

- `sources`
- `items`
- `analyses`
- `clusters`
- `reports`

`analyses.facts_json`用于保存从单条内容中抽取的明确事实；`clusters.report_date`用于隔离不同日期生成的事件集合。已有MVP数据库会在启动时自动补充这两个字段。

## 测试

运行全部测试：

```bash
python -m unittest discover -s tests -v
```

当前覆盖：

- 中文标题相似度；
- 事实与观点区分；
- 重复事实删除；
- 多来源事件融合；
- 不同报告日期隔离；
- RSS 2.0解析；
- Atom解析与相对链接补全；
- HTML摘要清洗；
- 发布时间过滤；
- 跨Feed URL去重。

GitHub Actions会在每次push和pull request时自动运行测试。

## 当前限制

- 当前真实采集仅接入首批美联储官方RSS；
- RSS通常只提供摘要，尚未抓取新闻页面完整正文；
- 尚未接入LLM；
- 规则聚类仍需通过更多真实新闻持续校准；
- 正式发布前仍建议人工复核Top 5和事件合并结果。

## 下一步

1. 验证美联储真实Feed输出及日报质量；
2. 增加正文页面抓取，但继续严格限制为来源原文；
3. 接入第二类官方来源并观察跨来源事件融合；
4. 在规则版本稳定后接入第一个LLM Analyzer。

在首份真实日报达到稳定可读前，不新增行情解释、交易建议或复杂研究平台模块。
