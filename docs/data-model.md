# 跨资产信息简报系统数据模型 V1

## 1. 设计目标

第一版采用SQLite保存运行状态和结构化数据，同时使用JSON、文本和Markdown保存原始内容与报告成品。

数据模型必须支持：

- 多平台来源管理；
- 增量采集与失败重试；
- 事实、观点、数据和研究内容统一入库；
- 精确去重与近似重复识别；
- 事件簇和观点簇合并；
- 早报、晚报和周报跨期去重；
- 行情快照与宏观日历；
- 全自动报告生成和运行审计。

核心对象：

```text
Source
Item
Cluster
Event
MarketSnapshot
CalendarEvent
Report
Run
```

## 2. Source：信息源

```yaml
id: string
name: string
platform: official | media | data_platform | x | wechat | youtube | api
url: string | null
external_id: string | null
source_level: A | B | C
priority: core | supplementary | observe | disabled
markets: [string]
topics: [string]
language: en | zh | multilingual
enabled: boolean
collector: string
fetch_cadence_minutes: integer | null
include_replies: boolean | null
include_reposts: boolean | null
include_quotes: boolean | null
notes: string | null
created_at: datetime
updated_at: datetime
```

说明：

- `source_level`表示事实可靠性和原始程度；
- `priority`表示运行与筛选策略；
- 来源等级和优先级都不保证内容自动入选；
- 同一创作者在不同平台保留独立Source，可通过`creator_group_id`扩展关联。

## 3. Item：原始内容标准化记录

一篇文章、帖子、视频、公告、数据发布或研究内容统一保存为Item。

```yaml
id: string
source_id: string
platform: string
external_id: string | null
canonical_url: string | null
title: string | null
raw_text: string | null
normalized_text: string | null
summary: string | null
published_at: datetime | null
published_at_raw: string | null
published_at_precision: exact | approximate | unknown
collected_at: datetime
language: string
primary_market: string | null
markets: [string]
topics: [string]
content_type: data | policy | company | industry | market | research | calendar
content_nature: fact | data | analysis | opinion | forecast | trading_view | education
content_access: full | partial | metadata_only | failed
transcript_source: official | auto_caption | audio_asr | none | null
visual_analysis: boolean
content_hash: string | null
raw_path: string | null
status: discovered | fetched | normalized | filtered | clustered | scored | selected | reported | archived | failed
error_code: string | null
error_message: string | null
created_at: datetime
updated_at: datetime
```

### 3.1 去重键优先级

```text
1. platform + source_id + external_id
2. canonical_url
3. content_hash
4. source_id + published_at + normalized_title
5. source_id + normalized_content_hash
```

原始记录不因报告去重而删除。

## 4. Cluster：信息簇

报告主要处理Cluster，而不是逐条处理Item。

```yaml
id: string
cluster_type: event | opinion | research
title: string
primary_market: string
markets: [string]
topics: [string]
entities: [string]
canonical_item_id: string
item_ids: [string]
first_seen_at: datetime
last_updated_at: datetime
merged_summary: string
novel_points: [string]
source_count: integer
independent_source_count: integer
content_nature: string
importance_score: number
candidate_band: core | attention | browse | archive
impact_confidence: confirmed | likely | unclear
status: active | closed | archived
created_at: datetime
updated_at: datetime
```

### 4.1 ClusterItemRelation

Item与Cluster之间单独保存关系：

```yaml
cluster_id: string
item_id: string
relation: duplicate | corroboration | new_detail | update | market_reaction | industry_impact | commentary | contradiction
novel_information: string | null
is_independent_source: boolean
created_at: datetime
```

### 4.2 聚类原则

- 转载和改写不重复展示；
- 新增数字、范围、时间表和执行细节应保留；
- 同一事件的市场反应和产业影响可并入同一簇；
- 相似观点可归纳共同结论；
- 相反观点使用`contradiction`并列展示；
- `source_count`与`independent_source_count`必须分开。

## 5. Event：持续事件状态

政策、监管、产业和突发风险可能持续数日或数月，Event用于跟踪其阶段变化。

```yaml
id: string
title: string
category: string
jurisdiction: string | null
status: rumor | proposal | consultation | review | approved | enacted | effective | implementation | enforcement | reversed
scheduled_at: datetime | null
first_seen_at: datetime
last_updated_at: datetime
affected_markets: [string]
affected_assets: [string]
importance: high | medium | low | not_recommended
official_source_item_id: string | null
cluster_ids: [string]
material_update: boolean
update_type: no_change | minor_detail | material_update | reversal | market_confirmation
created_at: datetime
updated_at: datetime
```

事件推荐逻辑见`docs/event-monitoring-guide.md`，实际运行类别见`config/event-monitoring.yaml`。

## 6. MarketSnapshot：跨资产市场快照

```yaml
id: string
symbol: string
asset_name: string
market: string
provider: string
observed_at: datetime
price: number | null
yield_value: number | null
change_value: number | null
change_percent: number | null
change_basis_points: number | null
previous_close: number | null
currency: string | null
data_frequency: realtime | delayed | daily
quality_status: complete | stale | missing
raw_payload_path: string | null
created_at: datetime
```

第一版重点标的包括：

- 标普500、纳斯达克100、沪深300、恒生指数；
- SMH半导体ETF作为AI基础设施代理；
- 美债2Y、10Y、30Y；
- 中债2Y、10Y、30Y；
- 美元指数、美元兑人民币；
- 黄金、白银、铜、碳酸锂、原油；
- BTC、ETH。

收益率和价格字段不可混用。债券部分展示收益率及BP变化。

## 7. CalendarEvent：宏观和预定事件

```yaml
id: string
provider: string
external_id: string | null
country_or_region: string
category: macro_data | central_bank | auction | earnings | policy | regulation | industry
name: string
scheduled_at: datetime
importance: high | medium | low
previous_value: string | null
forecast_value: string | null
actual_value: string | null
revised_value: string | null
unit: string | null
official_source_url: string | null
status: scheduled | released | revised | cancelled
surprise_direction: positive | negative | neutral | not_applicable | unknown
impact_confidence: confirmed | likely | unclear | null
affected_markets: [string]
created_at: datetime
updated_at: datetime
```

宏观事件的“影响”不是直接由API返回，应结合实际与预期差异、公布后资产反应和高质量新闻解释生成。

## 8. Report：报告

```yaml
id: string
report_type: morning | evening | weekly
window_start: datetime
window_end: datetime
scheduled_at: datetime
report_date: date
title: string
status: generating | generated | partial | failed
content_path: string
cluster_ids: [string]
market_snapshot_ids: [string]
calendar_event_ids: [string]
source_success_count: integer
source_failure_count: integer
created_at: datetime
updated_at: datetime
```

### 8.1 ReportCluster

```yaml
report_id: string
cluster_id: string
section: string
position: integer
first_reported_at: datetime
is_repeat: boolean
update_type: string | null
```

此关系用于跨早报、晚报和周报判断是否重复报道。

## 9. Run：运行记录

```yaml
id: string
run_type: collect | normalize | cluster | score | morning_report | evening_report | weekly_report
started_at: datetime
finished_at: datetime | null
status: running | success | partial | failed
sources_attempted: integer
sources_succeeded: integer
sources_failed: integer
items_discovered: integer
items_new: integer
clusters_created: integer
clusters_updated: integer
error_summary: string | null
log_path: string | null
created_at: datetime
```

单个来源失败时，Run可标记为`partial`，报告仍应继续生成。

## 10. 对象关系

```text
Source
  └─ Item
       ├─ ClusterItemRelation ─ Cluster ─ ReportCluster ─ Report
       └─ Event

MarketSnapshot ─ Report
CalendarEvent  ─ Report
Run            ─ 采集、处理和报告任务
```

## 11. 文件与数据库分工

### SQLite

保存：

- 来源配置镜像；
- Item元数据和状态；
- 去重键和信息簇关系；
- Event状态；
- 市场快照和宏观事件；
- 报告引用关系；
- 运行记录和错误。

### 原始文件

保存：

- 网页正文；
- X原始帖和线程；
- 公众号正文和图片解析结果；
- YouTube字幕、转写和关键画面说明；
- API原始响应。

### Markdown

保存最终早报、晚报和周报。

## 12. 字段增加原则

只有满足以下条件的字段才进入正式模型：

- 能明显改善自动筛选、聚类或报告质量；
- 在多个来源或多个报告周期中重复出现；
- 能够自动生成或可靠取得；
- 不依赖人工必填；
- 能解释具体业务问题或支持运行审计。
