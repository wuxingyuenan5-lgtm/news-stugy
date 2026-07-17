# 最小数据结构 V0.2

第一阶段不设计复杂数据库模型。本文件只定义信息整理和报告生成真正需要的最小字段。

这些字段可以先保存为 YAML、JSON、CSV 或 Markdown；只有在数据量和自动化需求出现后，再映射为数据库表。

## 1. Source：信息源

```yaml
id: string
name: string
url: string | null
source_level: A | B | C
source_type: official | media | research | newsletter | social | manual
markets: [string]
content_types: [string]
language: string
frequency: realtime | daily | weekly | irregular
enabled: boolean
notes: string | null
```

说明：

- A级主要是一手官方来源和原始公告；
- B级主要是专业媒体、数据平台和高质量机构；
- C级主要是观点、Newsletter和社交媒体线索；
- `source_level`用于理解来源性质，不直接决定信息是否重要。

## 2. Item：候选信息

一篇文章、公告、数据发布、研报、社交媒体内容或手工记录，都可以先作为一条Item保存。

```yaml
id: string
published_at: datetime | null
collected_at: datetime
source_id: string
source_name: string
title: string
url: string | null
markets: [string]
content_type: data | policy | company | industry | market | research | calendar
summary: string
importance: high | medium | low
status: inbox | selected | ignored | published
analyst_note: string | null
report_date: date | null
```

第一阶段必须字段：

- 来源
- 标题
- 发布时间
- 链接
- 市场分类
- 摘要
- 重要性
- 状态

第一阶段不强制字段：

- 市场预期
- 预期差
- 跨资产影响
- 传导机制
- 影响期限
- 置信度
- 失效条件

这些内容可以写入`analyst_note`，但不要求结构化。

## 3. Report：报告

```yaml
id: string
report_type: daily | weekly
report_date: date
title: string
status: draft | published
content_path: string
item_ids: [string]
created_at: datetime
updated_at: datetime
```

报告正文采用Markdown保存。第一阶段只需要知道报告引用了哪些候选信息。

## 4. WatchTopic：持续跟踪主题（可选）

当某个主题连续多日出现时，可以使用一个非常轻量的记录：

```yaml
id: string
title: string
markets: [string]
status: active | paused | closed
latest_note: string
related_item_ids: [string]
updated_at: datetime
```

此对象不是第一阶段必选项。只有当日报出现大量重复背景时再引入。

## 5. 最小关系

```text
Source
  └─ Item
       └─ Report
```

一条Item只需要对应一个主要来源；同一事件的多篇报道可以暂时分别保存，由人工选择质量最高的一篇进入报告。

第一阶段不建立Event、AssetImpact、TransmissionLink、View和Evaluation等实体。

## 6. 存储建议

优先级如下：

1. Markdown或YAML：便于直接阅读和修改；
2. JSON或CSV：便于脚本处理；
3. SQLite：当候选信息数量明显增加、需要搜索和去重时再加入；
4. PostgreSQL：只有需要多人协作、网页后端或并发任务时再考虑。

## 7. 增加字段的原则

只有当一个字段满足以下任一条件时才加入：

- 每天都需要填写；
- 能明显改善筛选或报告质量；
- 后续自动化确实需要；
- 在两周试运行中反复出现同类需求。

否则先保留在自由文本备注中。
