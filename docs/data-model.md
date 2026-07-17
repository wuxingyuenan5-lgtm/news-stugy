# 第一版最小数据结构

第一版不设计复杂数据库模型，只定义信息整理和报告生成需要的三个对象：`Source`、`Item`和`Report`。

数据可以保存为Markdown、YAML、JSON或CSV。

## 1. Source：信息源

```yaml
id: string
name: string
url: string | null
source_level: A | B | C
source_type: official | media | data_platform | research | newsletter | social | manual
markets: [string]
content_types: [string]
language: string
frequency: realtime | daily | weekly | irregular
review_cadence: realtime | daily | weekly | on_demand
priority: core | supplementary | experimental
enabled: boolean
use_in_report: string
notes: string | null
```

说明：

- A级：官方、一手公告和原始数据；
- B级：专业媒体、数据平台和高质量研究机构；
- C级：Newsletter、博主、社交媒体和其他线索来源；
- `source_level`用于理解来源性质，不直接决定信息是否重要；
- `priority`用于控制日常阅读频率；
- `use_in_report`说明该来源主要用于事实、日历、背景或周报主题。

## 2. Item：候选信息

一篇文章、公告、数据发布、研报、社交媒体内容或手工记录，统一保存为一条Item。

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

第一版必须字段：

- 来源；
- 标题；
- 发布时间；
- 原文链接；
- 市场分类；
- 内容类型；
- 事实摘要；
- 重要性；
- 状态。

`analyst_note`为可选自由文本，不要求填写固定研究字段。

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

报告正文使用Markdown保存。第一版只需要记录报告引用了哪些Item。

## 4. 最小关系

```text
Source
  └─ Item
       └─ Report
```

一条Item只对应一个主要来源。同一事实存在多篇报道时，可以分别保存，由人工选择原始来源或质量最高的一篇进入报告。

## 5. 字段增加规则

第一版运行期间，只有满足以下条件的字段才允许加入：

- 日常整理中高频使用；
- 能明显改善筛选或报告质量；
- 不增加不必要的填写负担；
- 已在试运行中反复出现同类需求。

其他字段、对象、数据库和搜索能力统一记录在[第二版优化指南](v2-optimization-guide.md)，不在第一版提前设计。