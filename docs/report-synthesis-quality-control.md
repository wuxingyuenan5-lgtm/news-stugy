# 报告综合与质量控制 V1

> 文档性质：报告生成层设计规范，不代表已经开始代码实现  
> 当前版本：0.1  
> 当前阶段：需求与架构设计

## 1. 设计目标

报告生成不能把原始文章、帖子和字幕直接交给模型自由写作。第一版采用：

```text
已筛选Cluster、市场快照、宏观事件和来源运行状态
→ 构建证据包
→ 生成结构化Cluster卡片
→ 提炼核心结论
→ 组装报告章节
→ 篇幅压缩
→ 逐项质量检查
→ Markdown渲染与发布
```

目标是：

- 每个重要事实都能回溯到Item、官方数据或可靠来源；
- 事实、解释、观点、预测和未知明确分开；
- 早报、晚报和周报只展示真正的信息增量；
- 模型不得根据标题、残缺摘要或常识补写不可见内容；
- 市场看板与宏观表格尽量由结构化字段确定性生成；
- 生成失败可以从报告阶段重跑，不要求重新采集和聚类；
- 部分来源失败时仍按时生成报告，并透明说明重要缺失。

---

## 2. 输入冻结与可复现性

每次报告开始生成前，先冻结本次输入快照：

```yaml
report_type: morning | evening | weekly
window_start:
window_end:
scheduled_at:
cluster_ids: []
market_snapshot_ids: []
calendar_event_ids: []
source_coverage_snapshot:
config_hashes:
  source_registry:
  provider_config:
  scoring:
  clustering_novelty:
  report_generation:
prompt_versions:
model_versions:
```

输入冻结后，后续新抓到的内容不得混入正在生成的旧窗口报告。需要补充时，应形成新版本或下一报告周期的更新。

---

## 3. 证据包 Evidence Packet

每个候选Cluster先构建标准证据包，报告模型只读取证据包，不直接读取无序原始材料。

### 3.1 通用字段

```yaml
cluster_id:
cluster_type: event | opinion | research
canonical_title:
update_type: no_change | minor_detail | material_update | reversal | market_confirmation
candidate_band: core | attention | browse | archive
importance_score:
impact_confidence: confirmed | likely | unclear
first_seen_at:
last_updated_at:
previous_report_refs: []
representative_sources: []
source_count:
independent_source_count:
content_access_summary:
unknowns: []
```

### 3.2 Event Cluster证据包

```yaml
fact_base: []
current_state:
new_details: []
corrections: []
retractions: []
market_reactions: []
industry_impacts: []
interpretations: []
contradictions: []
affected_assets: []
next_verification_points: []
```

### 3.3 Opinion Cluster证据包

```yaml
proposition:
horizon:
supporting_views: []
opposing_views: []
shared_evidence: []
key_disagreements: []
catalysts: []
invalidation_conditions: []
```

### 3.4 Research Cluster证据包

```yaml
research_question:
method_or_framework:
key_findings: []
supporting_evidence: []
limitations: []
practical_relevance:
```

证据包只包含已完成结构化处理且保留来源引用的内容。`metadata_only`不得进入详细事实和观点字段，只能进入线索或未知项。

---

## 4. 结构化报告草稿

模型先输出机器可校验的结构化草稿，再渲染Markdown。不得直接一次生成最终长文。

```yaml
report_metadata:
core_conclusions: []
sections:
  - section_id:
    title:
    entries: []
market_board:
macro_review:
forward_calendar:
data_integrity:
quality_summary:
```

每个报告条目建议包含：

```yaml
entry_id:
cluster_id:
entry_type: event | opinion | research | market_summary | calendar
headline:
what_happened:
what_changed_since_previous:
impact_or_relevance:
interpretations: []
disagreements_or_unknowns: []
affected_assets: []
impact_confidence:
source_refs: []
claim_support_map: []
word_budget:
```

`claim_support_map`用于保存句子或陈述与证据字段之间的映射，不在最终报告中展示内部判断过程。

---

## 5. 单个Cluster如何写成报告条目

### 5.1 Event Cluster

普通事件建议150至300字，重大政策、关键数据或跨资产事件可扩展至300至500字。

顺序：

```text
发生了什么
→ 相较此前新增了什么
→ 为什么重要或影响哪些资产
→ 主要分歧、未知或后续验证点
→ 代表性来源
```

硬规则：

- 第一段先写事实，不先写评价；
- 晚报重复早报主题时，必须突出`what_changed_since_previous`；
- 有`correction`、`retraction`或`reversal`时，必须说明此前版本与当前版本；
- 无法确认因果时，不写“导致”“引发”，改用“可能是驱动之一”“时间上相符”或“影响尚不明确”；
- 新数字、日期、比例和主体只能来自结构化证据字段。

### 5.2 Opinion Cluster

建议结构：

```text
核心命题
→ 支持观点及依据
→ 反对或条件性观点
→ 主要分歧在哪里
→ 催化剂与失效条件
```

不得把观点包装为事实。作者明确给出交易方向时，应标记为交易观点，并提高入选门槛。

### 5.3 Research Cluster

建议结构：

```text
研究问题
→ 方法或框架
→ 核心发现
→ 对当前市场或研究工作的意义
→ 局限与适用边界
```

日报只提取与当前市场高度相关的结论；完整方法、教育和框架内容优先进入周报。

---

## 6. 核心结论生成

核心结论不是新闻标题列表，而是对报告窗口内市场状态的归纳。

### 6.1 数量

- 早报、晚报通常4至6条；信息不足时可以更少；
- 周报通常6至10条；
- 不设置强制最低数量。

### 6.2 生成顺序

```text
重大官方事件和系统性风险
→ 政策、宏观与流动性变化
→ 跨资产市场定价变化
→ 主要行业与资产主线
→ 重要观点分歧与待验证事项
```

### 6.3 每条结论的要求

- 一句话表达一个主判断，不拼接多个无关事件；
- 至少由一个核心Cluster支持；
- 涉及多个Cluster时，它们必须具有明确共同主线；
- 区分“发生了什么”和“系统如何判断”；
- 结论中的因果强度不得高于证据包的`impact_confidence`；
- 不重复正文中的所有细节，只保留方向、状态和影响。

不允许：

- “美股、黄金、BTC均有变化”一类无信息量概括；
- 将多个低价值条目拼成看似重要的结论；
- 为凑足条数重复同一主线；
- 引入证据包中不存在的新数字、主体或预测。

---

## 7. 市场看板与宏观表格

市场看板、收益率BP变化、宏观前值/预期/实际值和日历时间优先由结构化数据确定性渲染，不交给语言模型重新计算。

模型只负责：

- 在字段完整时生成简短解释；
- 识别跨资产组合是否值得进入核心结论；
- 在无法确认驱动时标记`unclear`；
- 指出值得继续验证的市场反应。

禁止：

- 模型自行计算涨跌幅、BP变化或数据惊喜；
- 收益率与债券价格方向混淆；
- 缺失预期值时自行补全市场一致预期；
- 使用采集时间替代实际观察时间。

---

## 8. 事实、解释、观点、预测与未知

最终报告中的每个重要陈述应归入以下一种：

| 类型 | 含义 | 要求 |
|---|---|---|
| `fact` | 已发生且可核实 | 必须有直接来源支持 |
| `data` | 结构化数值或统计结果 | 保留口径、单位和时间 |
| `interpretation` | 基于事实的影响解释 | 标明置信度，不得伪装成事实 |
| `opinion` | 明确归属于作者或机构的判断 | 必须保留归属 |
| `forecast` | 对未来的预测 | 尽量包含周期、依据和失效条件 |
| `unknown` | 当前无法确认的事项 | 明确写出，不强行补结论 |

推理性陈述可以存在，但必须满足：

- 能指出支持它的事实或数据；
- 使用与置信度匹配的表述；
- 不新增证据包中不存在的事实；
- 重要推断在草稿中标记为`inference_labeled`。

---

## 9. 来源选择与引用

每个核心Cluster原则上显示1至3个代表性来源：

1. 官方文件或原始数据；
2. 最接近一手的专业媒体或研究；
3. 能提供独立细节、重要分歧或完整解释的来源。

不因为来源数量多就罗列全部链接。重复转载不作为代表性来源。

每个重要事实在结构化草稿中必须有来源映射。最终Markdown可以在条目末尾合并展示来源，但内部仍应保存陈述级支持关系。

---

## 10. 篇幅控制与压缩顺序

### 10.1 日报

- 目标阅读时间8至12分钟；
- 建议3000至5000字；
- 普通核心事件150至300字；
- 重大事件300至500字；
- “其他值得浏览”每条尽量控制为一句话。

### 10.2 周报

- 目标阅读时间20至30分钟；
- 建议8000至15000字；
- 重点保留事件演变、市场定价、共识分歧和下周验证点。

### 10.3 超长时的删除顺序

```text
1. archive和低分browse内容
2. 与核心条目重复的背景介绍
3. 无独立增量的补充观点
4. 过多的代表性来源
5. 次要市场的流水账描述
6. 核心条目中的非关键修饰和历史背景
```

不得因压缩删除：

- 重大官方事件；
- `reversal`、`correction`和`retraction`；
- 关键未知与事实边界；
- 重要来源归属；
- 数据口径、单位和发布时间；
- 周报主线的关键演变节点。

报告较短优于填充低价值内容。

---

## 11. 质量控制分级

质量检查分成三类。

### 11.1 硬阻断 Block

出现以下问题时不得发布正式报告：

- 重大事实没有任何可回溯来源；
- 使用标题或不可访问正文推断具体观点；
- 报告窗口、日期或时区错误；
- 同一Cluster无实质更新却被重复作为核心事件；
- 数据单位、正负方向或债券收益率口径明显错误；
- 链接由模型编造，或并非证据包中的原始链接；
- 将观点、传闻或预测写成已经确认的事实；
- `confirmed`因果判断没有相应市场和来源证据；
- 对`retraction`、重大更正或反转仍沿用旧结论；
- 生成内容与证据包发生实质矛盾。

处理方式：回退到结构化草稿修复；无法修复则删除相关条目或将报告标记为`partial`，但不得保留不受支持的事实。

### 11.2 自动修复 Repair

可以自动修复后继续检查：

- 缺少作者或机构归属；
- 同一Cluster在多个章节重复；
- 标题过度结论化；
- 表述置信度高于证据；
- 超出篇幅；
- 名称、符号和中英文口径不一致；
- 来源列表过长；
- 缺少“相较早报”的更新说明；
- `partial`内容没有披露范围限制。

自动修复后必须重新执行相关检查，不允许一次修复后直接发布。

### 11.3 告警 Warning

以下情况可以发布，但应记录或在完整性说明中披露：

- 某个平台覆盖率明显下降；
- 重要来源只能取得部分正文；
- 宏观一致预期缺失；
- 行情数据延迟或个别标的缺失；
- 事件置信度仍为`unclear`；
- 免费Provider无法确认是否完整回补；
- 某个重要观点只有单一来源。

---

## 12. 自动质量指标

每份报告至少记录：

```yaml
material_fact_support_rate:
citation_coverage_rate:
unsupported_claim_count:
partial_content_entry_count:
metadata_only_entry_count:
cross_report_repeat_count:
repeat_without_material_update_count:
duplicate_cluster_display_count:
confirmed_causality_count:
unclear_impact_count:
source_coverage_by_platform:
market_data_missing_count:
word_count:
```

这些指标用于运行审计和后续调参，不直接面向读者展示全部明细。

建议硬目标：

- `unsupported_claim_count = 0`；
- `repeat_without_material_update_count = 0`；
- `duplicate_cluster_display_count = 0`；
- 所有重大事实均有来源；
- 所有`metadata_only`内容均不得生成详细摘要。

---

## 13. 数据完整性说明

报告末尾不展示冗长技术日志，只披露会影响阅读结论的重要缺失：

```markdown
## 数据完整性说明

- X核心来源：成功 31/38；其中4个账号仅获得部分内容。
- 公众号：成功 20/24；2个来源近期文章发现失败。
- YouTube：发现视频完整；1个视频未取得字幕或音频转写。
- 行情：中债30Y数据暂缺；其他核心标的正常。
- 本报告据此省略了无法可靠支持的相关判断。
```

“成功X/Y”应区分调用成功和覆盖完整，不能把空结果或未知覆盖简单记为成功。

---

## 14. 发布与版本

正式发布流程：

```text
结构化草稿成功
→ Block检查为零
→ 自动修复完成并复检
→ 篇幅与章节检查
→ Markdown渲染
→ 保存报告、输入快照和质量摘要
→ 更新ReportCluster及跨报告状态
```

同一`report_type + scheduled_at`只允许一个正式报告。重复运行时：

- 草稿阶段可以产生多个版本；
- 正式报告默认更新同一记录，不新建重复成品；
- 保留生成模型、Prompt版本、配置哈希和修改原因；
- 补生成报告记录计划时间与实际生成时间；
- 旧报告中的事实被后续更正时，不静默篡改历史成品，而是在后续报告中明确更新；若需要修订历史文件，应生成可追溯修订版本。

---

## 15. V1不做的事情

- 不让模型自行访问互联网补充报告事实；
- 不在报告生成阶段重新抓取来源；
- 不保存或展示模型的原始长篇思维过程；
- 不建立复杂人工审核后台；
- 不为每个普通句子渲染脚注式引用；
- 不用综合“可信度分数”替代明确的来源、内容完整度和置信度字段。

V1保存的是简洁、结构化、可审计的判定字段和证据引用，而不是不可控的自由写作过程。
