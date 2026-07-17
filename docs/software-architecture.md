# 软件架构与仓库布局 V1

> 文档性质：工程架构设计规范，不代表已开始业务代码实现  
> 当前版本：0.1  
> 当前阶段：软件架构设计

## 1. 架构目标

本项目不是一次性脚本，而是需要长期维护、逐步扩展到更多来源、Provider、AI任务和报告类型的自动化信息系统。

工程设计目标：

- Provider、业务处理、AI、存储、调度和报告相互解耦；
- 业务规则配置化，不散落在Python文件中；
- 每个处理阶段可单独运行、重试和测试；
- 同一输入、模型和Prompt版本下结果可缓存、可复现；
- Windows恢复旧项目、WSL2正式运行、未来Linux迁移时不改业务代码；
- SQLite适合第一版，但领域层不依赖SQLite具体实现；
- 新增一个来源、Provider或AI任务时，不要求修改无关模块；
- 不建立过度复杂的微服务、消息队列和分布式系统。

第一版采用：

```text
模块化单体 Modular Monolith
+ 明确领域边界
+ 端口与适配器 Ports and Adapters
+ SQLite
+ 本地文件存储
+ 进程内任务编排
```

不采用：

- 微服务；
- Kafka、RabbitMQ等消息队列；
- 独立向量数据库；
- Kubernetes；
- 多仓库拆分；
- Provider直接写数据库；
- 各模块自行创建AI客户端。

---

## 2. 目标仓库布局

```text
news-stugy/
├─ pyproject.toml
├─ README.md
├─ .env.example
├─ .gitignore
├─ config/
│  ├─ source-registry.yaml
│  ├─ creator-groups.yaml
│  ├─ provider-health.yaml
│  ├─ content-processing.yaml
│  ├─ clustering-novelty.yaml
│  ├─ scoring.yaml
│  ├─ report-generation.yaml
│  ├─ schedules.yaml
│  ├─ logging.yaml
│  └─ sources/
│     ├─ x.jsonl
│     ├─ youtube-finance.jsonl
│     ├─ youtube-ai.jsonl
│     ├─ wechat.jsonl
│     ├─ official.jsonl
│     └─ media.jsonl
├─ docs/
├─ src/
│  └─ news_stugy/
│     ├─ __init__.py
│     ├─ cli/
│     ├─ application/
│     ├─ domain/
│     ├─ providers/
│     ├─ collectors/
│     ├─ pipeline/
│     ├─ ai/
│     ├─ reports/
│     ├─ storage/
│     ├─ scheduler/
│     ├─ observability/
│     └─ bootstrap/
├─ migrations/
├─ prompts/
├─ templates/
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  ├─ contract/
│  ├─ golden/
│  └─ fixtures/
├─ scripts/
├─ var/
│  ├─ db/
│  ├─ raw/
│  ├─ artifacts/
│  ├─ reports/
│  ├─ snapshots/
│  ├─ logs/
│  └─ tmp/
└─ legacy/
   └─ reference_project/
```

### 2.1 `src/`布局

使用`src/news_stugy`布局，避免本地工作目录中的同名文件意外覆盖已安装包，也有利于测试真实安装结果。

### 2.2 `var/`不是源码

`var/`保存本机运行数据，默认加入`.gitignore`：

- SQLite数据库；
- 原始网页、字幕和API响应；
- AI处理产物；
- 报告文件；
- 日志和临时文件。

Git只保存配置、Prompt、模板、迁移和代码。

### 2.3 `legacy/reference_project/`

恢复后的参考项目代码先隔离放置，不直接混入正式模块。正式Provider只能通过明确适配器调用参考项目能力。

---

## 3. 顶层模块职责

## 3.1 `domain/`：领域模型与纯规则

包含业务概念和不依赖外部系统的规则：

```text
domain/
├─ models/
│  ├─ source.py
│  ├─ provider.py
│  ├─ item.py
│  ├─ cluster.py
│  ├─ event.py
│  ├─ report.py
│  └─ run.py
├─ enums/
├─ value_objects/
├─ policies/
└─ errors.py
```

允许：

- 数据类、枚举、值对象；
- 聚类身份、内容完整度、状态转换等纯规则；
- 不访问网络和数据库的校验。

禁止：

- SQL；
- HTTP请求；
- 文件写入；
- AI API调用；
- 读取环境变量。

`domain`是最内层，不能依赖其他项目模块。

## 3.2 `application/`：用例与任务编排

表示系统“要完成什么”，例如：

```text
application/
├─ commands/
│  ├─ collect_sources.py
│  ├─ process_items.py
│  ├─ build_report.py
│  └─ recover_runs.py
├─ services/
├─ ports/
└─ dto/
```

职责：

- 编排一个完整用例；
- 控制事务边界；
- 调用领域规则；
- 通过接口调用Provider、Repository、AI Runtime和文件存储；
- 决定失败后继续、重试还是中止。

禁止：

- 直接写SQL；
- 直接调用OpenAI、yt-dlp或requests；
- 直接解析平台网页；
- 在用例内写大型Prompt。

## 3.3 `providers/`：外部获取适配器

Provider表示“怎么取得内容或数据”。

```text
providers/
├─ base.py
├─ registry.py
├─ x/
├─ wechat/
├─ youtube/
├─ web/
├─ market/
└─ macro/
```

职责：

- 调用外部网页、公开接口或开源工具；
- 返回统一Provider响应；
- 保留原始响应和平台字段；
- 将技术错误转换成统一错误类型。

Provider不知道：

- Cluster；
- Scoring；
- Report；
- SQLite表结构；
- 是否进入早报或晚报。

Provider不得直接提交数据库事务。

## 3.4 `collectors/`：来源级采集协调

Collector连接Source Registry和Provider。

```text
collectors/
├─ source_collector.py
├─ fallback_policy.py
├─ coverage.py
└─ cursor.py
```

职责：

- 读取一个Source及其Provider绑定；
- 按健康状态和优先级选择Provider；
- 执行主Provider与回退链；
- 生成统一的发现结果和ProviderAttempt结果；
- 计算本次覆盖状态。

Collector不负责正文摘要、聚类、评分和报告。

## 3.5 `pipeline/`：内容处理阶段

```text
pipeline/
├─ discovery/
├─ acquisition/
├─ normalization/
├─ filtering/
├─ deduplication/
├─ analysis/
├─ retrieval/
├─ clustering/
├─ events/
├─ novelty/
├─ scoring/
├─ selection/
└─ orchestration/
```

每个阶段均使用显式输入和输出，不通过全局变量交换状态。

建议统一接口：

```python
class PipelineStage[InputT, OutputT]:
    def run(self, context: StageContext, value: InputT) -> StageResult[OutputT]: ...
```

每个阶段应：

- 可单独测试；
- 可幂等重跑；
- 保存必要ProcessingArtifact；
- 不自行决定调度时间；
- 不直接渲染最终Markdown。

## 3.6 `ai/`：统一AI Runtime

```text
ai/
├─ runtime.py
├─ routing/
├─ clients/
├─ tasks/
├─ schemas/
├─ prompts/
├─ cache/
├─ validation/
└─ errors.py
```

所有AI调用必须经过`AIRuntime`，业务模块不得直接实例化模型客户端。

AI任务按能力拆分：

- 摘要；
- 事实与观点分离；
- 实体与事件身份提取；
- Cluster关系判断；
- Novelty判断；
- 评分；
- 证据包综合；
- 报告草稿；
- 质量修复。

每个任务包含：

```text
task id
input schema
output schema
prompt version
model class
retry policy
validation policy
cache policy
```

Prompt正文放在仓库顶层`prompts/`，任务代码只引用Prompt ID和版本。

## 3.7 `reports/`：报告构建与渲染

```text
reports/
├─ evidence/
├─ builders/
├─ conclusions/
├─ sections/
├─ compression/
├─ quality/
├─ renderers/
└─ publication/
```

职责分离：

- Builder：构建结构化报告草稿；
- Quality：检查硬阻断、修复项和告警；
- Renderer：将合格草稿渲染为Markdown；
- Publication：保存正式版本和修订记录。

Renderer不得重新调用AI，也不得修改事实含义。

## 3.8 `storage/`：持久化适配器

```text
storage/
├─ repositories/
├─ sqlite/
│  ├─ connection.py
│  ├─ unit_of_work.py
│  └─ repositories/
├─ files/
│  ├─ raw_store.py
│  ├─ artifact_store.py
│  ├─ report_store.py
│  └─ snapshot_store.py
└─ migrations/
```

应用层依赖Repository接口，SQLite只是实现。

第一版可以使用同步SQLite访问，避免不必要的异步复杂度。数据库写入通过Unit of Work统一提交。

## 3.9 `scheduler/`：时间与任务触发

Scheduler只负责“何时执行哪个应用用例”：

- 早报、晚报、周报；
- 分平台采集；
- 恢复扫描；
- Provider冷却期探测；
- 来源治理统计。

Scheduler不包含采集、AI和报告业务规则。

## 3.10 `observability/`：日志、指标和审计

```text
observability/
├─ logging.py
├─ metrics.py
├─ tracing.py
├─ audit.py
└─ health.py
```

所有日志至少包含：

```text
run_id
stage
source_id
provider_id
item_id
cluster_id
report_id
attempt_number
error_code
```

没有对应字段时允许为空，但禁止只输出无法关联业务对象的普通文本日志。

## 3.11 `bootstrap/`：依赖装配

唯一允许集中实例化具体实现的位置：

```text
bootstrap/
├─ settings.py
├─ container.py
├─ provider_factory.py
├─ repository_factory.py
└─ app_factory.py
```

负责：

- 读取配置和环境变量；
- 创建数据库连接；
- 注册Provider；
- 创建AI Runtime；
- 将具体适配器注入应用服务。

业务模块不能自行读取`.env`。

---

## 4. 依赖方向

允许的主要依赖：

```text
cli / scheduler
       ↓
application
       ↓
domain + application ports
       ↑
providers / storage / ai / reports adapters
```

更直观地说：

```text
domain
  ↑
application
  ↑
cli, scheduler, bootstrap

providers, storage, ai, reports
  └─ 实现application定义的ports
```

硬规则：

- `domain`不得导入`application`或任何适配器；
- `providers`不得导入`reports`；
- `reports`不得导入具体Provider；
- `ai/tasks`不得直接写SQLite；
- `scheduler`不得直接调用Provider；
- `cli`只调用application用例；
- `bootstrap`可以依赖所有具体适配器，但不得放业务规则。

---

## 5. 跨模块对象

模块之间不传递任意`dict`，应使用明确DTO或领域对象。

第一版建议定义：

```text
SourceSpec
ProviderBindingSpec
CollectionWindow
ProviderRequest
ProviderResponse
DiscoveredItem
AcquiredContent
NormalizedItem
ItemAnalysis
ClusterCandidate
ClusterDecision
NoveltyDecision
ScoreResult
EvidencePacket
StructuredReportDraft
QualityCheckResult
PublicationResult
```

外部原始响应只能存在于Provider适配器和Raw Store中，不应向后续所有模块传播。

---

## 6. 事务边界

建议按应用用例控制事务，而不是一个完整日报使用单个超长事务。

典型边界：

```text
一次ProviderAttempt
一次Item标准化与状态推进
一次Cluster更新
一次Event更新
一次报告输入冻结
一次ReportRevision发布
```

AI调用和外部网络请求不得包在SQLite写事务中，避免长时间占用数据库锁。

推荐模式：

```text
读取当前状态
→ 事务外执行网络或AI任务
→ 校验输入版本未变化
→ 短事务写入结果
```

---

## 7. 同步与异步策略

第一版采用同步业务代码和有限并发：

- 单个Provider调用是同步接口；
- Collector可以在线程池中并发不同来源；
- SQLite写入集中串行或限制并发；
- AI任务可有限并发，但由AIRuntime统一控制；
- 不把整个工程改造成`asyncio`项目。

只有在真实测试证明同步I/O成为瓶颈后，再考虑局部异步适配器。

---

## 8. 错误模型

统一错误大类：

```text
ConfigurationError
ValidationError
ProviderError
RateLimitError
AuthenticationError
SchemaChangedError
ContentUnavailableError
StorageError
AIError
AIOutputValidationError
QualityBlockerError
RetryableError
FinalError
```

底层异常必须转换为项目错误，应用层不应根据第三方库错误字符串做业务判断。

每个错误需包含：

```text
error_code
retryable
stage
public_message
technical_message
context ids
original_exception type
```

---

## 9. 配置边界

配置文件只表达：

- 来源与Provider；
- 阈值和权重；
- 调度时间；
- Prompt版本；
- 模型路由；
- 日志等级；
- 功能开关。

禁止在配置中嵌入任意Python表达式或动态执行代码。

启动时必须完成：

```text
YAML/JSONL读取
→ Schema校验
→ 跨文件引用校验
→ 唯一ID校验
→ 生成配置哈希
→ 构建不可变Settings对象
```

---

## 10. 迁移策略

### Windows阶段

- 恢复旧参考项目；
- 找回`nitter_client.py`；
- 验证旧Provider真实能力；
- 不在Windows旧目录直接发展正式工程。

### WSL2阶段

- 正式仓库运行；
- Python虚拟环境、SQLite、yt-dlp、ffmpeg；
- `var/`使用Linux路径；
- Windows参考项目通过适配器或共享路径调用。

### Linux服务器阶段

保持不变：

- `src/`代码；
- `config/`；
- `prompts/`；
- `templates/`；
- SQLite模型和迁移。

只替换：

- 环境变量；
- `var/`根路径；
- 调度器启动方式；
- 需要Windows能力的Provider绑定。

---

## 11. 第一版工程取舍

第一版坚持：

- 单仓库；
- 单Python包；
- 单SQLite数据库；
- 单进程任务编排，可启动多个独立CLI进程；
- Pydantic或等价Schema进行边界校验；
- 标准logging加结构化JSON输出；
- Alembic或轻量迁移工具维护数据库版本；
- pytest作为测试框架。

暂不实现：

- Web管理后台；
- 分布式Worker；
- 实时流处理；
- 服务发现；
- 复杂权限系统；
- 自动水平扩容。

---

## 12. 实施顺序

```text
1. 建立pyproject与src包骨架
2. 定义domain模型、DTO与错误类型
3. 定义application ports和Repository接口
4. 实现配置加载与Schema校验
5. 实现SQLite连接、迁移和基础Repository
6. 实现Provider统一接口与参考项目适配器
7. 实现Collector与ProviderAttempt
8. 实现AI Runtime骨架和单个简单任务
9. 逐阶段实现Pipeline
10. 实现Report结构化草稿、质量检查与渲染
11. 实现CLI和本地Scheduler
12. 接入Golden Set测试
```

在第1至5步完成前，不应大规模编写具体平台采集逻辑。