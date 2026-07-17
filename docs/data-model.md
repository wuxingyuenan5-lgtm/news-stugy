# 跨资产信息简报系统数据模型 V1

> 当前版本：0.5  
> 当前阶段：需求与架构设计  
> 存储方案：SQLite结构化状态 + JSON/Text原始内容 + Markdown报告

## 1. 设计目标

数据模型必须支持：

- 多平台、多来源和跨平台创作者管理；
- 一个来源绑定多个免费Provider；
- 区分来源没有更新与Provider抓取失败；
- 增量采集、历史回补、限流冷却和失败重试；
- 原始内容、字幕、图片解析和行情数据统一追溯；
- 精确去重、近似重复、事件簇、观点簇和研究簇；
- Cluster合并、拆分、更正、撤回和版本演变；
- 早报、晚报和周报跨期防重复；
- 政策与重要事件生命周期跟踪；
- 行情快照、宏观实际值和未来日历；
- AI摘要、分类、聚类、评分和报告草稿缓存；
- 核心结论与重大陈述的证据映射；
- 自动质量检查、报告修订和完整运行审计。

核心对象：

```text
CreatorGroup
Source
Provider
SourceProviderBinding
ProviderAttempt
Item
ProcessingArtifact
Cluster
ClusterItemRelation
Event
EventClusterRelation
MarketSnapshot
CalendarEvent
Report
ReportRevision
ReportCluster
ReportStatement
ReportStatementEvidence
Run
```

第一版不要求把所有列表字段立即拆成关系表。`markets`、`topics`、`roles`等低频修改字段可以先以SQLite JSON字段保存；去重、聚类、Provider运行、报告引用和证据映射必须使用明确关系。

---

## 2. CreatorGroup：跨平台创作者

同一创作者在X、YouTube、公众号等平台保留独立Source，通过CreatorGroup关联。

```yaml
id: string
display_name: string
aliases: [string]
dedupe_rule: same_creator_same_theme_merge
report_rule: one_core_theme_per_report_unless_independent_major_events
verification_status: unverified | initial_manual_match | verified | rejected
notes: string | null
created_at: datetime
updated_at: datetime
```

CreatorGroup用于跨平台去重和作者级贡献统计，不代替Source。

---

## 3. Source：具体信息源

Source表示“抓谁”，例如一个X账号、YouTube频道、公众号、媒体栏目、官方数据集或行情标的。

```yaml
id: string
creator_group_id: string | null
name: string
aliases: [string]
platform: official | media | data_platform | x | wechat | youtube | weibo | web | api
url: string | null
external_id: string | null
source_level: A | B | C
priority: core | supplementary | observe | disabled
user_importance_signal: high | ambiguous | normal
protected_from_auto_demotion: boolean
markets: [string]
topics: [string]
source_roles: [string]
language: en | zh | multilingual | unknown
expected_activity: realtime | daily | weekly | irregular | scheduled | event_driven
default_fetch_cadence_minutes: integer | null
source_status: active | possibly_inactive | inactive | removed | disabled
enabled: boolean
verification_status: unverified | needs_manual_review | verified | invalid
notes: string | null
created_at: datetime
updated_at: datetime
```

说明：

- `source_level`表示原始程度与事实可靠性，不表示内容一定重要；
- `priority`表示运行和治理优先级，不保证内容进入报告；
- `source_status`描述来源本身是否活跃；
- Provider故障不得直接改变`source_status`；
- 关键官方来源可设置`protected_from_auto_demotion: true`。

---

## 4. Provider：技术获取方式

Provider表示“怎么抓”，例如参考项目X链路、Nitter兼容实例、RSS、公开网页、yt-dlp、官方免费接口或AkShare。

```yaml
id: string
platform: string
provider_type: reference_project | official_api | rss | webpage | search | open_source_library | exchange_api | file_download
cost_type: free | public
enabled: boolean
environments: [windows | wsl2 | linux_server]
capabilities:
  discovery: true | false | partial | limited
  full_content: true | false | partial | limited
  exact_timestamp: true | false | partial | limited
  external_id: true | false | partial | limited
  replies: true | false | partial | limited
  reposts: true | false | partial | limited
  quotes: true | false | partial | limited
  threads: true | false | partial | limited
  images: true | false | partial | limited
  transcript: true | false | partial | limited
  backfill: true | false | partial | limited
rate_limit_policy: conservative | normal | provider_defined
requires_cookie: boolean
requires_browser: boolean
requires_windows: boolean
terms_note: string | null
created_at: datetime
updated_at: datetime
```

Provider只负责获取，不负责重要性评分、跨来源聚类和报告写作。

---

## 5. SourceProviderBinding：来源与Provider绑定

健康状态主要记录在“来源 × Provider”绑定上。

```yaml
id: string
source_id: string
provider_id: string
role: primary | fallback
priority_order: integer
enabled: boolean
config_json: object
health_status: unverified | healthy | degraded | unstable | cooling_down | disabled
last_attempt_at: datetime | null
last_success_at: datetime | null
last_content_at: datetime | null
last_full_content_at: datetime | null
consecutive_failures: integer
consecutive_suspicious_empty: integer
rolling_success_rate_7d: number | null
rolling_full_content_rate_7d: number | null
rolling_latency_seconds_7d: number | null
cooldown_until: datetime | null
last_error_code: string | null
last_error_message: string | null
created_at: datetime
updated_at: datetime
```

唯一约束：

```text
UNIQUE(source_id, provider_id)
```

同一Source可以绑定多个Provider，顺序必须由配置决定，不写死在Collector代码中。

---

## 6. ProviderAttempt：单次抓取尝试

每次Provider调用都保存独立记录，不能只在Run中保留汇总。

```yaml
id: string
run_id: string
binding_id: string
window_start: datetime
window_end: datetime
attempt_number: integer
started_at: datetime
finished_at: datetime | null
result_status: success_with_items | success_empty | partial_success | suspicious_empty | failed_retryable | failed_rate_limited | failed_auth | failed_schema_changed | failed_final
items_found: integer
items_new: integer
items_complete: integer
items_partial: integer
items_metadata_only: integer
coverage_status: complete | partial | unknown | failed
backfill_supported: boolean | null
earliest_available_at: datetime | null
http_status: integer | null
error_code: string | null
error_message: string | null
raw_response_path: string | null
created_at: datetime
```

`success_empty`不等于失败。只有结合来源历史活跃度、其他Provider结果和同类来源表现，才可能升级为`suspicious_empty`。

---

## 7. Item：标准化原始内容

一篇文章、帖子、线程、视频、公告、数据发布或研究内容统一保存为Item。

```yaml
id: string
source_id: string
provider_attempt_id: string | null
platform: string
external_id: string | null
canonical_url: string | null
title: string | null
raw_text: string | null
normalized_text: string | null
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
content_access: complete | partial | metadata_only | unavailable
transcript_source: official | manual_caption | auto_caption | audio_asr | none | null
visual_analysis_status: not_needed | pending | completed | failed
content_hash: string | null
raw_path: string | null
status: discovered | fetched | normalized | filtered | clustered | scored | selected | reported | archived | failed
error_code: string | null
error_message: string | null
created_at: datetime
updated_at: datetime
```

去重键优先级：

```text
1. platform + source_id + external_id
2. canonical_url
3. content_hash
4. source_id + published_at + normalized_title
5. source_id + normalized_content_hash
```

原始Item不因报告去重而删除。

---

## 8. ProcessingArtifact：处理结果与AI缓存

摘要、分类、观点提取、实体识别、证据包、相似度、评分和报告草稿不能只存在内存中。

```yaml
id: string
artifact_type: normalized_text | translation | summary | fact_opinion_split | entity_extraction | classification | embedding | similarity | evidence_packet | cluster_synthesis | novelty | score | report_draft | quality_check | report_render
input_type: item | cluster | event | report | report_revision
input_id: string
input_hash: string
model_provider: string | null
model_name: string | null
prompt_version: string | null
config_hash: string | null
result_json: object | null
result_text: string | null
status: pending | success | failed_retryable | failed_final
error_message: string | null
created_at: datetime
updated_at: datetime
```

唯一性建议：

```text
UNIQUE(artifact_type, input_type, input_id, input_hash, model_name, prompt_version, config_hash)
```

输入未变化时优先复用已有结果，避免重复消耗Token并保证幂等。只保存简洁、结构化判定字段，不保存模型原始长篇思维过程。

---

## 9. Cluster：信息簇

报告主要处理Cluster，而不是逐条处理Item。

```yaml
id: string
cluster_type: event | opinion | research
cluster_identity_json: object
title: string
primary_market: string
markets: [string]
topics: [string]
entities: [string]
canonical_item_id: string
first_seen_at: datetime
last_updated_at: datetime
last_material_update_at: datetime | null
last_reported_at: datetime | null
cluster_version: integer
merged_summary: string
novel_points: [string]
unknowns: [string]
source_count: integer
independent_source_count: integer
content_nature: string
importance_score: number
candidate_band: core | attention | browse | archive
impact_confidence: confirmed | likely | unclear
status: active | closed | merged | split | archived
merged_into_cluster_id: string | null
split_from_cluster_id: string | null
created_at: datetime
updated_at: datetime
```

`cluster_identity_json`按Cluster类型保存事件身份、观点命题或研究问题，例如：

```yaml
event:
  actor:
  action:
  object:
  time_or_state:
  jurisdiction_or_market:
opinion:
  subject:
  stance:
  horizon:
  rationale:
  catalyst:
  invalidation:
research:
  research_question:
  method_or_framework:
```

`merged_into_cluster_id`和`split_from_cluster_id`用于保留修正历史，不能通过删除旧Cluster掩盖错误合并。

### 9.1 ClusterItemRelation

```yaml
cluster_id: string
item_id: string
relation: duplicate | corroboration | new_detail | update | market_reaction | industry_impact | commentary | contradiction | correction | retraction
novel_information: string | null
is_independent_source: boolean
created_at: datetime
```

原则：

- 转载和改写不重复展示；
- 新增数字、范围、时间表和执行细节必须保留；
- 市场反应和产业影响可以并入同一事件簇；
- 相反观点使用`contradiction`并列；
- 更正和撤回必须更新Cluster版本与后续报告判断；
- `source_count`与`independent_source_count`分开。

---

## 10. Event：持续事件状态

Event用于跟踪跨天、跨周的政策、监管、产业和突发风险生命周期。

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
material_update: boolean
update_type: no_change | minor_detail | material_update | reversal | market_confirmation
created_at: datetime
updated_at: datetime
```

Event与Cluster使用独立关系表：

```yaml
EventClusterRelation:
  event_id: string
  cluster_id: string
  relation: initial | update | implementation | market_confirmation | correction | reversal | related
  created_at: datetime
```

---

## 11. MarketSnapshot：跨资产市场快照

```yaml
id: string
symbol: string
asset_name: string
market: string
provider_id: string
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

债券展示收益率与BP变化，收益率字段和价格字段不得混用。

重点标的包括：标普500、纳斯达克100、沪深300、恒生指数、SMH、美债2Y/10Y/30Y、中债2Y/10Y/30Y、美元指数、美元兑人民币、黄金、白银、铜、碳酸锂、原油、BTC和ETH。

---

## 12. CalendarEvent：宏观和预定事件

```yaml
id: string
provider_id: string
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

宏观事件影响不是直接由API字段决定，应结合实际与预期差异、公布后资产反应和可靠报道生成。免费来源没有稳定预期值时允许为空。

---

## 13. Report：报告任务对象

Report代表一个固定窗口和计划时间的报告，不直接代表某一次具体渲染版本。

```yaml
id: string
report_type: morning | evening | weekly
window_start: datetime
window_end: datetime
scheduled_at: datetime
report_date: date
title: string
status: pending | generating | generated | partial | failed
input_snapshot_artifact_id: string | null
current_revision_id: string | null
source_success_count: integer
source_failure_count: integer
source_unknown_coverage_count: integer
created_at: datetime
updated_at: datetime
```

唯一约束：

```text
UNIQUE(report_type, scheduled_at)
```

### 13.1 ReportRevision：报告修订版本

```yaml
id: string
report_id: string
revision_number: integer
draft_artifact_id: string
quality_artifact_id: string | null
content_path: string
status: draft | blocked | generated | partial | superseded
word_count: integer
blocker_count: integer
warning_count: integer
change_reason: string | null
planned_generated_at: datetime
generated_at: datetime
is_current: boolean
created_at: datetime
```

唯一约束：

```text
UNIQUE(report_id, revision_number)
```

历史事实被更正时，不静默覆盖旧版本。需要修订历史成品时，创建新Revision并记录原因。

### 13.2 ReportCluster：报告与Cluster关系

```yaml
report_id: string
report_revision_id: string
cluster_id: string
section: string
position: integer
first_reported_at: datetime
is_repeat: boolean
update_type: no_change | minor_detail | material_update | reversal | market_confirmation | null
change_since_previous: string | null
created_at: datetime
```

重复进入晚报或跨日报告时，`change_since_previous`必须说明新增部分。

### 13.3 ReportStatement：核心结论与重大陈述

V1不要求拆分最终报告中的每一个普通句子，但必须保存：

- 每条核心结论；
- 每个核心条目的重大事实；
- 重要因果或影响判断；
- 关键预测和未知项。

```yaml
id: string
report_revision_id: string
cluster_id: string | null
section: string
position: integer
statement_type: core_conclusion | material_fact | data | interpretation | attributed_opinion | forecast | unknown
statement_text: string
support_status: direct_supported | synthesis_supported | attributed_opinion | inference_labeled | unsupported
impact_confidence: confirmed | likely | unclear | null
citation_required: boolean
created_at: datetime
```

### 13.4 ReportStatementEvidence：陈述证据映射

```yaml
report_statement_id: string
evidence_type: item | cluster | market_snapshot | calendar_event
evidence_id: string
evidence_role: direct | corroboration | context | opinion_source | market_reaction | data_source
created_at: datetime
```

质量控制通过该关系计算事实支持率、引用覆盖率和不受支持陈述数量。最终Markdown不需要展示内部支持图，但必须保留可追溯关系。

Report与MarketSnapshot、CalendarEvent使用独立引用关系表：

```yaml
ReportMarketSnapshot:
  report_revision_id: string
  market_snapshot_id: string

ReportCalendarEvent:
  report_revision_id: string
  calendar_event_id: string
```

---

## 14. Run：任务运行记录

```yaml
id: string
run_type: collect | normalize | process_ai | cluster | score | report_draft | quality_control | publication | morning_report | evening_report | weekly_report | recovery_scan
scheduled_at: datetime | null
window_start: datetime | null
window_end: datetime | null
started_at: datetime
finished_at: datetime | null
status: pending | running | partial_success | success | failed_retryable | failed_final | skipped_duplicate
sources_attempted: integer
sources_succeeded: integer
sources_failed: integer
items_discovered: integer
items_new: integer
clusters_created: integer
clusters_updated: integer
reports_generated: integer
error_summary: string | null
log_path: string | null
created_at: datetime
```

单个来源失败时Run可标记`partial_success`，其他采集和报告仍继续。

---

## 15. 对象关系

```text
CreatorGroup
  └─ Source
       └─ SourceProviderBinding ─ Provider
              └─ ProviderAttempt ─ Run
                     └─ Item
                          ├─ ProcessingArtifact
                          ├─ ClusterItemRelation ─ Cluster ─ EventClusterRelation ─ Event
                          └─ ReportStatementEvidence ─ ReportStatement

Cluster ─ ReportCluster ─ ReportRevision ─ Report
MarketSnapshot ─ ReportMarketSnapshot ─ ReportRevision
CalendarEvent  ─ ReportCalendarEvent  ─ ReportRevision
```

---

## 16. 幂等与唯一性

至少建立以下唯一约束：

```text
Source:                    UNIQUE(platform, external_id) when external_id is not null
SourceProviderBinding:     UNIQUE(source_id, provider_id)
Item:                      UNIQUE(platform, source_id, external_id) when external_id is not null
ClusterItemRelation:       UNIQUE(cluster_id, item_id)
EventClusterRelation:      UNIQUE(event_id, cluster_id)
Report:                    UNIQUE(report_type, scheduled_at)
ReportRevision:            UNIQUE(report_id, revision_number)
ReportCluster:             UNIQUE(report_revision_id, cluster_id)
ReportStatementEvidence:   UNIQUE(report_statement_id, evidence_type, evidence_id, evidence_role)
ProcessingArtifact:        UNIQUE(artifact_type, input_type, input_id, input_hash, model_name, prompt_version, config_hash)
```

重复执行同一任务时：

- 不重复写入已有Item；
- 不重复下载已有字幕和正文；
- 不重复调用输入未变化的AI处理；
- 不生成多个相同窗口的Report；
- 允许生成可追溯的ReportRevision；
- 失败步骤可单独重试，不回滚已成功步骤。

---

## 17. 文件与数据库分工

### SQLite

保存：

- 来源、创作者、Provider和绑定状态；
- ProviderAttempt和Run；
- Item元数据、去重键和状态；
- AI处理结果索引与必要结构化结果；
- Cluster、Event、合并拆分和关系；
- 市场快照和宏观日历；
- Report、ReportRevision和引用关系；
- 核心结论、重大陈述及证据映射。

### 原始文件

保存：

- 网页HTML和清洗正文；
- X原始帖子、引用、转发和线程；
- 公众号正文、图片和长图解析结果；
- YouTube字幕、转写、音频元数据和关键画面说明；
- 行情、宏观和事件接口原始响应；
- 大型AI响应或调试材料；
- 结构化报告草稿和质量检查详情。

### Markdown

保存最终早报、晚报和周报成品及必要修订版本。

---

## 18. 字段增加原则

只有满足以下条件的字段才进入正式模型：

- 能改善自动筛选、聚类、报告质量或故障恢复；
- 在多个来源或报告周期中重复出现；
- 能自动生成或可靠取得；
- 不依赖人工日常必填；
- 能解释具体业务问题或支持运行审计；
- 不与已有对象职责重复。
