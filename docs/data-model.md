# 核心数据模型 V0.1

本文件定义 MVP 阶段需要稳定下来的核心实体。字段名称后续可直接映射到 Pydantic 模型和数据库表。

## 1. Source

```yaml
id: string
name: string
tier: tier_1 | tier_2 | tier_3 | tier_4
source_type: rss | api | html | pdf | email | manual | social
language: string
region: string
topics: [string]
url: string | null
enabled: boolean
trust_score: integer
copyright_mode: string
created_at: datetime
updated_at: datetime
```

## 2. Document

一篇原始文章、公告、数据发布、PDF 或手工输入。

```yaml
id: string
source_id: string
external_id: string | null
url: string | null
title: string
author: string | null
published_at: datetime | null
fetched_at: datetime
language: string
raw_content_path: string | null
normalized_text: string | null
content_hash: string
metadata: object
duplicate_group_id: string | null
processing_status: pending | processed | failed
```

## 3. Event

从一个或多个 Document 中抽象出的同一事实事件。

```yaml
id: string
headline: string
event_time: datetime | null
first_seen_at: datetime
last_updated_at: datetime
status: new | developing | updated | corrected | resolved
primary_document_id: string
document_ids: [string]
facts: [string]
market_expectation: string | null
actual_value: number | string | null
consensus_value: number | string | null
previous_value: number | string | null
surprise_description: string | null
asset_classes: [string]
state_variables: [string]
regions: [string]
entities: [string]
importance_score_model: number
importance_score_final: number
review_status: pending | accepted | revised | rejected
model_confidence: number | null
created_at: datetime
updated_at: datetime
```

## 4. AssetImpact

同一个事件可以对不同资产产生方向、期限和逻辑不同的影响。

```yaml
id: string
event_id: string
asset_or_factor: string
direction: strongly_bullish | bullish | neutral | bearish | strongly_bearish | mixed | uncertain
horizon: intraday | days | weeks | months | structural
mechanism: string
confidence: number
conditions: [string]
invalidators: [string]
follow_up_indicators: [string]
analyst_override: boolean
```

## 5. TransmissionLink

用于表达跨资产传导链，而不是把分析压缩成单个方向标签。

```yaml
id: string
event_id: string
sequence: integer
from_node: string
to_node: string
relationship: string
direction: positive | negative | conditional
confidence: number
condition: string | null
```

示例：

```text
原油上涨
→ 通胀预期上升
→ 降息概率下降
→ 实际利率上升
→ 长久期成长股估值承压
```

## 6. ResearchNote

```yaml
id: string
event_id: string | null
title: string
note_type: event_analysis | theme | asset | macro_regime | review
content_markdown: string
analyst: string
created_at: datetime
updated_at: datetime
version: integer
```

## 7. View

观点必须是可版本化、可证伪的对象。

```yaml
id: string
subject_type: macro | asset | sector | theme
subject: string
stance: bullish | neutral | bearish | mixed
horizon: days | weeks | months | structural
thesis: string
supporting_event_ids: [string]
key_indicators: [string]
invalidators: [string]
confidence: number
status: active | weakened | invalidated | closed
valid_from: datetime
valid_to: datetime | null
version: integer
supersedes_view_id: string | null
```

## 8. Report

```yaml
id: string
report_type: daily | weekly | thematic
report_date: date
title: string
status: draft | reviewed | published
content_path: string
event_ids: [string]
view_ids: [string]
source_document_ids: [string]
generated_at: datetime
reviewed_at: datetime | null
published_at: datetime | null
```

## 9. Evaluation

```yaml
id: string
view_id: string
evaluation_date: date
evaluation_horizon: string
expected_outcome: string
actual_outcome: string
result: correct | partially_correct | wrong | unresolved
error_type: fact | logic | timing | horizon | unknown
notes: string
```

## 10. 关系约束

- 一个 Source 对应多个 Document。
- 一个 Event 至少对应一个 Document。
- 一个 Document 可以参与多个 Event，但 MVP 阶段默认一对一或多文档归一事件。
- 一个 Event 可以对应多个 AssetImpact 和 TransmissionLink。
- 一个 View 可以由多个 Event 支撑。
- Report 保存事件和观点的快照引用，发布后不得静默覆盖。
- Evaluation 只能评估已经存在的 View 版本。

## 11. MVP 必选表

第一阶段只实现：

1. sources
2. documents
3. events
4. asset_impacts
5. research_notes
6. reports

`views`、`transmission_links` 和 `evaluations` 在日报流程跑通后加入，但字段从现在开始保持兼容。
