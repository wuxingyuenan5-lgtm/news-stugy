# 跨资产研究系统架构 V0.1

## 1. 系统定位

本项目是一套面向个人研究者的跨资产信息处理与研究操作系统，而不是普通新闻聚合器。

系统需要回答四个问题：

1. 过去 24 小时或一周发生了什么？
2. 哪些变化超出了市场原有预期？
3. 这些变化通过什么路径影响不同资产？
4. 是否需要修改原有观点、风险判断或观察重点？

## 2. 总体工作流

```text
信息源
  ↓
采集 Ingestion
  ↓
原始资料库 Raw Store
  ↓
清洗、去重、实体识别 Normalization
  ↓
事件结构化 Event Extraction
  ↓
分类、评分、关联 Enrichment
  ↓
人工审核 Review
  ↓
研究判断 Research Notes
  ↓
日报 / 周报 / 专题报告 Publishing
  ↓
历史验证与复盘 Evaluation
```

核心原则：原始事实、机器提取、分析判断和最终观点必须分层保存，不能覆盖彼此。

## 3. 六层架构

### 3.1 Source Layer：信息源层

负责定义信息从哪里来，不负责解释信息。

主要来源：

- 官方机构：央行、统计局、财政部、监管机构、交易所
- 公司与产业：公司公告、财报、电话会、产业协会
- 专业媒体：Reuters、Bloomberg、FT、WSJ 等
- 数据平台：FRED、CME、CFTC、EIA、SEC、交易所行情及资金流数据
- 研究机构：投行、资管、智库和行业研究
- 社交媒体：仅作为线索、情绪与非共识观点来源

每个来源必须登记：来源等级、主题覆盖、更新频率、抓取方式、版权限制、可信度和延迟。

### 3.2 Ingestion Layer：采集层

负责将不同格式内容转为统一输入。

输入类型：

- RSS / Atom
- REST API
- HTML 页面
- PDF / 研究报告
- 邮件与Newsletter
- 手工录入
- 社交媒体链接

采集层只做：获取、时间戳、来源记录、内容哈希和失败重试。

### 3.3 Data Layer：数据层

采用分层存储：

#### Raw

原始文本、原始响应、附件、抓取时间和来源 URL。原则上不可修改。

#### Normalized

统一后的标题、正文、作者、发布时间、语言、实体、主题和重复组。

#### Research

事件卡片、研究笔记、跨资产传导关系、观点与验证结果。

#### Output

日报、周报、图表、导出文件和发布版本。

MVP 阶段建议：

- 结构化数据：SQLite 或 PostgreSQL
- 原始文本与附件：本地文件系统 / 对象存储
- 配置：YAML
- 报告：Markdown

在数据规模和多人协作出现之前，优先 SQLite；需要定时任务、网页后端和并发访问时再迁移 PostgreSQL。

### 3.4 Intelligence Layer：智能处理层

该层负责把“文章”变成“可研究事件”。

主要模块：

1. 文本清洗与语言识别
2. 近重复和同事件聚类
3. 实体识别：国家、机构、公司、人物、资产、商品
4. 主题分类：宏观、美股、A股、贵金属、加密、能源、AI科技
5. 状态变量分类：增长、通胀、流动性、货币政策、财政、风险偏好、资金仓位、供给冲击
6. 事件提取：发生了什么、时间、数值、前值、预期值
7. 预期差判断
8. 跨资产影响候选
9. 重要性评分
10. 摘要与报告草稿

AI 的输出必须保留模型版本、提示词版本、置信度和引用来源，并允许人工修改。

### 3.5 Research Layer：研究层

这是整个系统的核心，不应被自动化替代。

每个重要事件形成统一事件卡片：

```yaml
event_id: EVT-YYYYMMDD-XXXX
headline:
event_time:
source_ids: []
facts:
market_expectation:
surprise:
state_variables: []
asset_classes: []
transmission_chain: []
direction:
impact_horizon:
confidence:
invalidators: []
follow_up_indicators: []
view_changed: false
analyst_note:
```

研究层还需要维护：

- 当前市场状态 Market Regime
- 主题与叙事 Narrative
- 资产观点 View
- 观察清单 Watchlist
- 观点失效条件 Invalidation
- 历史预测与复盘 Evaluation

### 3.6 Publishing Layer：输出层

#### 日报

回答“与昨天相比发生了什么变化”。

建议结构：

1. 隔夜跨资产表现
2. 今日核心判断
3. 5 条关键事件及传导
4. 5 条快速信息
5. 资金流、仓位与波动率
6. 今日事件日历
7. 待验证问题

#### 周报

回答“这些变化是否构成趋势或状态切换”。

建议结构：

1. 本周市场状态
2. 资产表现与归因
3. 核心变量变化
4. 资金流、仓位与市场宽度
5. 原有观点验证
6. 下周事件与风险
7. 三情景推演
8. 重点观察资产及触发条件

## 4. 核心领域模型

```text
Source
  └─ Document
       └─ Event
            ├─ Entity
            ├─ StateVariable
            ├─ AssetImpact
            ├─ TransmissionLink
            ├─ ResearchNote
            └─ ViewUpdate

Report
  ├─ EventSnapshot
  ├─ MarketSnapshot
  ├─ ViewSnapshot
  └─ CalendarItem
```

### Source

定义来源属性和可信度。

### Document

一篇文章、公告、报告、数据发布或社交媒体内容。

### Event

从一个或多个 Document 中抽象出的同一事实事件。

### AssetImpact

记录事件对某项资产的方向、期限、逻辑和置信度。

### View

记录研究者对宏观变量、主题或资产的当前判断，并保留版本历史。

## 5. 重要性评分

初版使用 0–100 分规则评分：

```text
重要性 =
  市场影响 25%
+ 预期差 20%
+ 跨资产广度 15%
+ 持续时间 15%
+ 来源可信度 10%
+ 新颖性 10%
+ 可验证性 5%
```

评分用途：

- 80–100：日报核心分析
- 60–79：日报快速信息或周报候选
- 40–59：数据库留存，通常不进入报告
- 0–39：噪音或弱相关内容

评分只用于排序，不替代人工判断。

## 6. 去重与事件聚类

必须区分：

- 文本重复：同一篇内容被转载
- 事实重复：不同媒体报道同一事件
- 叙事重复：多个事件围绕同一主题

建议为每个事件维护：

- 主来源
- 佐证来源
- 首次出现时间
- 最新更新时间
- 事件状态：新发生 / 更新 / 纠正 / 结束

日报只展示“新增信息”，避免重复讲述已知事件。

## 7. 目录设计

```text
news-stugy/
├─ README.md
├─ docs/
│  ├─ architecture.md
│  ├─ roadmap.md
│  ├─ data-model.md
│  └─ report-spec.md
├─ config/
│  ├─ taxonomy.yaml
│  ├─ sources.yaml
│  └─ scoring.yaml
├─ app/
│  ├─ ingestion/
│  ├─ normalization/
│  ├─ enrichment/
│  ├─ research/
│  ├─ reporting/
│  └─ api/
├─ prompts/
│  ├─ event_extraction/
│  ├─ classification/
│  ├─ impact_analysis/
│  └─ report_generation/
├─ templates/
│  ├─ daily_report.md.j2
│  ├─ weekly_report.md.j2
│  └─ event_card.md.j2
├─ data/
│  ├─ raw/
│  ├─ processed/
│  └─ exports/
├─ tests/
├─ scripts/
└─ pyproject.toml
```

`data/` 中的原始数据、数据库文件和私有报告默认不提交 GitHub。

## 8. 模块边界

### ingestion

只负责采集，不做观点判断。

### normalization

统一格式、时间、正文和实体名称。

### enrichment

分类、聚类、评分和模型提取。

### research

事件卡片、传导链、观点和复盘。

### reporting

按模板生成日报、周报和专题。

### api

为未来网页前端、搜索和人工审核提供接口。

## 9. MVP 技术建议

第一版建议采用：

- Python 3.12+
- Pydantic：数据模型与校验
- SQLAlchemy / SQLModel：数据库访问
- SQLite：本地数据库
- Typer：命令行入口
- APScheduler 或 GitHub Actions：定时任务
- Jinja2：报告模板
- Polars / Pandas：数据处理
- FastAPI：第二阶段再加入
- Streamlit 或轻量 Web 前端：人工审核界面原型

不建议第一版直接引入 Kafka、微服务、向量数据库或复杂多代理系统。

## 10. 人机分工

### 自动化负责

- 抓取
- 清洗
- 去重
- 分类
- 数值与实体提取
- 初步摘要
- 初步传导候选
- 报告排版

### 人工负责

- 事实核验
- 重要性终审
- 预期差判断
- 传导逻辑
- 观点更新
- 情景推演
- 最终发布

## 11. 质量控制

每条进入正式报告的信息必须满足：

1. 至少一个可追溯来源
2. 事实和观点明确分离
3. 发布时间与事件发生时间明确
4. AI 提取结果可回溯原文
5. 重大结论尽量有第二来源佐证
6. 修改后保留历史版本
7. 报告生成后保留引用清单

## 12. 当前决策

V0.1 先完成以下闭环：

```text
人工添加来源
→ 自动/半自动采集
→ 生成标准事件卡
→ 人工审核
→ 生成 Markdown 日报
→ 一周后进行观点复盘
```

只有该闭环稳定后，再扩展实时行情、量化指标、邮件推送和网页端。
