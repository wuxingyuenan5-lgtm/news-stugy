# 内容整理系统 MVP 实施范围 V2（极简版）

> 核心目标：先把内容整理出来，而不是先建设完整平台。
>
> 第一版只验证一件事：输入一批内容后，系统能否去重、归纳、分组并生成一份可读报告。

## 1. 第一版只做这一条链路

```text
内容输入
→ 基础清洗
→ AI分析
→ 简单去重与分组
→ 挑选重要内容
→ 生成Markdown报告
```

第一版不要求所有环节都自动化。采集不稳定的来源可以先手工导入。

## 2. 极简技术形态

只使用：

```text
一个Python项目
一个SQLite数据库
一个配置文件
三到四个Prompt
一个命令行入口
```

不拆微服务，不引入消息队列、向量数据库、知识图谱或Web后台。

推荐目录：

```text
news-study/
├─ app/
│  ├─ import_items.py
│  ├─ analyze.py
│  ├─ cluster.py
│  ├─ report.py
│  └─ main.py
├─ prompts/
│  ├─ analyze-item.md
│  ├─ compare-items.md
│  └─ write-report.md
├─ config.yaml
├─ data/
│  ├─ input/
│  ├─ reports/
│  └─ app.db
└─ tests/
   └─ cases.yaml
```

## 3. 第一版只保留五个核心对象

### Source

记录来源名称、平台和链接。

### Item

记录单条原始内容：

```yaml
id:
source:
title:
content:
published_at:
url:
```

### Analysis

记录AI对Item的结构化结果：

```yaml
summary:
facts: []
opinions: []
assets: []
topics: []
importance: 1-5
```

### Cluster

把同一事件、同一观点或同一研究主题的Item放在一起。

第一版只保存：

```yaml
id:
title:
type: event | opinion | research
item_ids: []
summary:
importance: 1-5
```

### Report

保存报告日期、类型和Markdown路径。

第一版不单独建设Event、Evidence Packet、ReportStatement、ReportRevision等复杂对象。需要的信息先放在JSON字段中，后续确有需要再拆表。

## 4. 数据库只建五张表

```text
sources
items
analyses
clusters
reports
```

其中：

- `items.analysis_json`可以暂时直接保存分析结果；
- `clusters.item_ids_json`可以暂时保存成员关系；
- `reports.content`可以直接保存Markdown；
- 不做复杂外键和版本关系；
- 不做历史修订系统；
- 不做完整审计链。

如果后续数据量增长或查询困难，再拆表。

## 5. 去重与分组只做两层

### 第一层：确定性去重

直接判重：

- URL相同；
- 正文哈希相同；
- 标题高度一致且来源内容相同。

### 第二层：AI判断

对候选内容只问一个问题：

> 这两条内容是否在讲同一件事或同一个明确命题？

输出：

```yaml
same_cluster: true | false
reason:
```

不做向量数据库，不做复杂相似度服务，不做长期事件图谱。

## 6. 内容选择只用简单等级

每个Cluster只评1到5分：

```text
5 = 必须进入核心结论
4 = 进入重点内容
3 = 进入其他值得浏览
2 = 通常不进入报告
1 = 忽略
```

评分依据只看：

- 是否影响主要市场；
- 是否有明确新增信息；
- 是否与用户重点关注领域相关；
- 是否来源可靠。

第一版不计算复杂综合分，不做多维权重模型。

## 7. 报告结构也保持简单

第一版只生成一种报告：晚报。

```markdown
# 市场晚报｜YYYY-MM-DD

## 一、今日核心结论

## 二、重要事件与市场主线

## 三、重点观点与分歧

## 四、其他值得关注

## 五、明日关注

## 六、来源与数据说明
```

没有内容的栏目直接省略。

每个条目只写：

```text
发生了什么
为什么重要
目前还有什么不确定
来源
```

## 8. Prompt只保留三个

```text
analyze-item.md
compare-items.md
write-report.md
```

暂时不拆：

- novelty prompt；
- cluster synthesis prompt；
- report entry prompt；
- final report prompt；
- quality control prompt。

所有报告整理先由`write-report.md`一次完成。

## 9. 质量控制只检查四件事

生成报告前后只检查：

- 重大事实是否有来源；
- 观点是否注明是谁的观点；
- 同一事件是否重复出现；
- AI是否扩写了输入中不存在的事实。

其他问题先人工看，不建设自动QC流水线。

## 10. 采集不是第一阶段重点

开发顺序：

```text
手工准备20至50条真实内容
→ 跑通分析、去重、分组和报告
→ 接入3至5个稳定来源
→ 再增加来源
```

X、公众号、YouTube等平台可以先手工导入，不让采集技术问题阻塞内容整理。

## 11. 轻量评测的定位

`evaluation/cases.yaml`只作为回归样例，不做独立评测系统。

每次重要修改后人工检查：

- 是否错误合并；
- 是否明显重复；
- 是否遗漏重大内容；
- 是否出现无依据扩写。

不做Dashboard、排行榜、CI阻断和历史Replay。

## 12. 明确暂缓

以下内容全部延期：

- 多Provider自动切换；
- ProviderAttempt完整运行审计；
- Event生命周期；
- Novelty状态机；
- Evidence Packet；
- Structured Draft；
- Report Revision；
- Report Statement；
- Claim Support Map；
- 复杂评分体系；
- 自动质量修复；
- 早报和周报；
- 市场看板自动计算；
- 宏观日历自动整合；
- Web管理后台；
- 多用户和权限；
- 全量历史回放；
- 自动评测平台。

这些设计文档可以保留作为未来参考，但不进入第一版代码。

## 13. 第一阶段完成标准

满足以下条件即可停止继续设计，进入实际使用：

- 可导入一批新闻、观点和研究内容；
- 可以自动生成结构化摘要；
- 明显重复内容可以合并；
- 事实和观点基本分开；
- 可以按重要性整理；
- 可以生成一份可读的Markdown晚报；
- 报告保留来源链接；
- 人工只需要少量修改。

## 14. 下一步只做代码

```text
1. 建立五张SQLite表
2. 建立Item导入脚本
3. 编写analyze-item Prompt
4. 编写简单判重与分组逻辑
5. 编写write-report Prompt
6. 生成第一份晚报
```

在第一份真实晚报生成之前，不再增加新的架构模块。