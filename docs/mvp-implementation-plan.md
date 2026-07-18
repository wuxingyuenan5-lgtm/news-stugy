# 内容整理系统 MVP 实施范围 V1

> 核心目标：先稳定产出一份可读、可追溯的跨资产早报或晚报。  
> 原则：优先打通端到端主链路，暂不追求平台覆盖率、复杂自动评测或精细运营后台。

## 1. MVP成功标准

第一版只要能够完成以下流程，即视为MVP成功：

```text
读取少量稳定来源
→ 拉取报告窗口内的新内容
→ 标准化为Item
→ 去除明显重复
→ AI提取事实、观点、资产和主题
→ 将同一事件或观点整理为Cluster
→ 选择高价值Cluster
→ 生成结构清楚的Markdown报告
→ 保留来源链接和数据缺失说明
```

实际验收标准：

- 每天至少能稳定生成一份报告；
- 核心条目不是简单标题列表；
- 同一事件的转载不会大量重复；
- 事实与观点基本分开；
- 每个核心条目保留可点击来源；
- 单个来源失败不会阻塞整份报告；
- 报告可人工阅读并进行少量修改后使用。

---

## 2. 第一版只做一条主流程

建议开发顺序：

```text
手动运行晚报
→ 自动生成晚报
→ 增加早报
→ 最后增加周报
```

先做晚报的原因：

- 亚洲时段结束后内容较完整；
- A股、港股、中国政策和海外隔夜信息可以同时整理；
- 便于白天观察采集结果并在18:00前排错；
- 早报和周报可以复用同一套处理链。

MVP不需要同时实现三种报告调度。

---

## 3. 来源范围收缩

第一阶段不追求361个来源全部接入。建议只启用约20至40个高质量来源：

### 3.1 必须优先

- 重要官方机构与交易所；
- 少量稳定专业媒体；
- 用户重点关注领域的核心X账号；
- 少量高质量公众号；
- 少量高质量YouTube频道。

### 3.2 平台建议

初始平台顺序：

```text
RSS / 官方网页 / 公开API
→ YouTube字幕
→ X可稳定取得的公开内容
→ 公众号可稳定取得的正文
```

如X或公众号采集不稳定，可以先通过手工导入、浏览器导出或中间文件进入Item层，不阻塞报告主链开发。

### 3.3 暂缓

- 低优先级observe来源；
- 大规模历史回补；
- 实时分钟级抓取；
- 付费墙内容；
- 直播与直播回放；
- YouTube Shorts；
- 图片和长图的全面OCR；
- 所有来源的自动健康升降级。

---

## 4. 最小模块划分

### 4.1 Registry Loader

职责：

- 读取启用来源；
- 返回来源ID、平台、角色、优先级和Provider配置；
- 不修改Git配置。

### 4.2 Collector

职责：

- 按报告窗口抓取内容；
- 保存原始响应；
- 生成ProviderAttempt；
- 单个来源失败后继续执行。

初期每个平台只需要一个可用Collector，不建设复杂Provider自动切换。

### 4.3 Normalizer

职责：

- 统一标题、正文、发布时间、链接和来源；
- 清理明显HTML与无关导航内容；
- 生成内容哈希；
- 标记`complete`、`partial`或`metadata_only`。

### 4.4 Item Analyzer

AI结构化输出至少包含：

```yaml
summary:
facts: []
opinions: []
forecasts: []
entities: []
markets: []
topics: []
content_nature:
quality_flags: []
```

第一版不需要过细的产业链本体和复杂实体图谱。

### 4.5 Deduplicator / Clusterer

第一版采用：

```text
确定性去重
+
标题与实体候选检索
+
AI判断是否属于同一Cluster
```

只支持：

- Event Cluster；
- Opinion Cluster；
- Research Cluster。

错误不确定时宁可暂时拆开，不强行合并。

### 4.6 Selector

使用现有`config/scoring.yaml`进行简化评分。

MVP只需要输出：

- `core`；
- `attention`；
- `browse`；
- `archive`。

不要求评分绝对精确，重点是明显重大内容排在前面、低价值转载被过滤。

### 4.7 Report Builder

职责：

- 读取已选择Cluster；
- 构建证据包；
- 生成结构化草稿；
- 渲染Markdown；
- 附来源和数据完整性说明。

第一版晚报可保留以下栏目：

```markdown
# 跨资产晚报｜YYYY-MM-DD

## 一、日内核心结论
## 二、跨资产市场看板
## 三、A股、港股与中国资产主线
## 四、核心新闻与市场主线
## 五、重点观点与分歧
## 六、今晚及明晨关注
## 七、其他值得浏览
## 八、数据完整性说明
```

没有内容的栏目允许省略。

---

## 5. MVP数据存储

使用SQLite和本地文件即可。

### SQLite第一版必须表

- sources；
- providers；
- source_provider_bindings；
- provider_attempts；
- items；
- processing_artifacts；
- clusters；
- cluster_item_relations；
- market_snapshots；
- calendar_events；
- reports；
- report_revisions；
- report_clusters；
- runs。

### 可以延期的表

- report_statements；
- report_statement_evidence；
- 完整Event生命周期关系；
- 人工Review记录；
- 复杂评测结果表。

重大陈述证据映射在MVP期间可先保存于`ProcessingArtifact.result_json`，等报告稳定后再拆成正式表。

### 文件目录

```text
data/
├─ raw/
├─ normalized/
├─ artifacts/
├─ reports/
└─ app.db
```

Git只保存配置、Prompt、模板和代码，不提交运行数据库与大体量原始内容。

---

## 6. 行情和日历范围

第一版市场看板不必覆盖全部标的，先选择稳定可得的核心标的：

- 标普500或纳斯达克100；
- 沪深300；
- 恒生指数；
- 美债2Y与10Y；
- 美元指数；
- 黄金；
- 铜；
- BTC；
- ETH。

初期若中国国债、碳酸锂或部分海外指数缺少稳定免费接口，可以标记缺失，不阻塞报告。

宏观日历第一版只需要：

- 重要经济数据；
- 央行会议和讲话；
- 重要政策与监管节点；
- 重点财报或产业事件。

没有可靠一致预期时允许`forecast_value=null`。

---

## 7. Prompt最小集合

第一版只建立以下Prompt：

```text
prompts/
├─ item-analysis-v1.md
├─ cluster-relation-v1.md
├─ cluster-synthesis-v1.md
├─ novelty-v1.md
├─ report-entry-v1.md
└─ report-final-v1.md
```

暂不建立复杂Prompt Registry。版本直接体现在文件名和文件头中。

---

## 8. 质量控制最低要求

正式生成前只做以下硬检查：

- 核心事实是否有来源；
- 标题不可见正文是否被扩写；
- 观点是否有作者归属；
- 同一Cluster是否重复出现；
- 数据单位和时间是否存在；
- 链接是否来自输入；
- 报告窗口是否正确。

其他风格、篇幅和覆盖率问题先作为告警，不阻塞报告生成。

---

## 9. 建议实施阶段

### 阶段A：本地样例跑通

使用手工准备的20至50条Item JSON：

- 完成Item Analyzer；
- 完成去重与Cluster；
- 生成第一份Markdown晚报。

这一阶段不需要真实Collector。

### 阶段B：接入少量真实来源

优先接入5至10个最稳定来源：

- 自动抓取；
- 写入SQLite；
- 按窗口生成晚报。

### 阶段C：扩展到20至40个核心来源

- 增加平台适配；
- 增加市场看板和日历；
- 增加早报自动运行。

### 阶段D：稳定后再扩展

- 周报；
- 更多来源；
- Event长期跟踪；
- 完整证据审计；
- 自动评测和历史回放。

---

## 10. 明确延期清单

以下内容不进入第一版开发重点：

- Web管理后台；
- 实时推送；
- 多用户权限；
- 向量数据库；
- 知识图谱；
- Kubernetes；
- 消息队列集群；
- 微服务拆分；
- 复杂模型路由；
- 全自动来源晋升与降级；
- 全量历史重放；
- 完整Benchmark平台；
- 精美可视化Dashboard。

优先使用一个Python项目、一个SQLite数据库和一组清晰模块完成主链路。

---

## 11. 下一步落地顺序

架构设计到此已足够支持开始实现。建议立即进入：

```text
1. 建立Python项目骨架
2. 建立SQLite基础表
3. 准备手工Item样例
4. 实现Item Analyzer
5. 实现确定性去重
6. 实现AI Cluster判断
7. 实现简化评分与选择
8. 生成第一份Markdown晚报
9. 再接入真实Collector
```

第一份可读报告生成后，再根据真实成品暴露的问题调整架构，而不是继续无限扩展设计。