# 来源注册表与 Provider 健康管理 V1

> 文档性质：来源与采集运行管理设计规范，不代表已经开始代码实现  
> 当前版本：0.1  
> 当前阶段：需求与架构设计

## 1. 设计目标

免费内容与数据来源不可避免地存在限流、网页结构变化、搜索索引延迟、IP差异和偶发不可用。系统需要在不购买商业数据服务的前提下：

- 区分“来源没有发布新内容”和“Provider没有成功抓到内容”；
- 自动在同类免费Provider之间降级；
- 避免一次网络错误就停用核心来源；
- 避免Provider已经失效却持续生成空结果；
- 记录覆盖率、完整度和失败原因；
- 支持Windows、WSL2和未来Linux服务器之间切换Provider；
- 单个来源或Provider失败时不阻塞整份报告。

第一版不建立复杂监控平台，也不依赖单一综合健康分数。采用“明确状态 + 滚动指标 + 状态机”的方式管理。

---

## 2. 三个必须分开的对象

```text
Source
  具体内容来源，例如某个X账号、公众号、YouTube频道、媒体栏目或官方数据集

Provider
  一种技术获取方式，例如参考项目X链路、Nitter兼容实例、RSS、yt-dlp或官方公开接口

SourceProviderBinding
  某个Source通过某个Provider抓取时的具体配置、能力和健康状态
```

健康状态主要记录在`SourceProviderBinding`，而不是只记录在Source或Provider上。

原因：

- 同一个Provider可能能抓取A账号但抓不到B账号；
- 同一个来源可以通过多个Provider取得；
- Provider整体正常，不代表每个来源绑定都正常；
- 来源近期没有更新，不应误判为Provider失败。

---

## 3. Source Registry：来源注册表

每个来源建议记录：

```yaml
id: x_example
name: Example Creator
platform: x
url: https://x.com/example
external_id: example
creator_group_id: example_creator
source_level: C
priority: core
markets: [macro, us_equity]
topics: [liquidity, financial_conditions]
language: en
enabled: true
expected_activity: daily
fetch_cadence_minutes: 30
report_usage: [analysis, opinion]
notes: null
```

### 3.1 `source_level`

表示来源性质和事实可靠性：

- `A`：官方机构、交易所、公司公告和原始数据；
- `B`：专业媒体、数据平台和高质量研究机构；
- `C`：创作者、社交媒体、Newsletter和线索来源。

不表示内容一定重要，也不直接决定抓取频率。

### 3.2 `priority`

表示运行优先级：

- `core`：每个对应周期都应尝试；
- `supplementary`：正常采集，资源紧张时可延后；
- `observe`：低频采集或试验性保留；
- `disabled`：不采集，但保留停用原因和历史记录。

### 3.3 `expected_activity`

用于判断“空结果是否可疑”，建议使用：

- `realtime`：通常每天多次更新；
- `daily`：通常每天或交易日更新；
- `weekly`：通常每周更新；
- `irregular`：不定期发布；
- `scheduled`：按已知发布时间发布；
- `event_driven`：只有事件发生时更新。

空结果本身不是失败。只有当来源历史活跃度、其他Provider结果和同类来源表现共同显示异常时，才标记为`suspicious_empty`。

---

## 4. Provider Registry：Provider注册表

每个Provider建议记录：

```yaml
id: reference_x_provider
platform: x
provider_type: reference_project
cost_type: free
enabled: true
environments: [windows, wsl2]
capabilities:
  discovery: true
  full_content: true
  exact_timestamp: partial
  external_id: partial
  replies: partial
  reposts: partial
  quotes: partial
  threads: false
  backfill: limited
rate_limit_policy: conservative
terms_note: 仅用于个人研究，遵守来源条款
```

### 4.1 Provider能力不能只写“支持/不支持”

建议允许：

- `true`：稳定支持；
- `false`：不支持；
- `partial`：部分支持或字段不稳定；
- `limited`：能力存在但范围有限。

尤其需要记录：

- 是否能发现新内容；
- 是否能取得完整正文或字幕；
- 是否有精确发布时间；
- 是否有稳定外部ID和原始链接；
- 是否支持历史回补；
- 是否能识别回复、引用、转发和线程；
- 是否依赖Windows、Cookie、浏览器或特定IP。

---

## 5. SourceProviderBinding：来源与Provider绑定

```yaml
source_id: x_example
provider_id: reference_x_provider
role: primary
priority_order: 1
enabled: true
config:
  username: example
  include_replies: false
  include_reposts: true
  include_quotes: true
health_status: unverified
last_attempt_at: null
last_success_at: null
last_content_at: null
consecutive_failures: 0
cooldown_until: null
```

同一来源可以绑定多个Provider：

```text
x_example
├─ reference_x_provider      primary
├─ nitter_compatible         fallback_1
├─ public_search             fallback_2
└─ webpage                   fallback_3
```

Provider顺序应配置化，不写死在Collector代码中。

---

## 6. 健康状态

第一版建议使用以下状态：

| 状态 | 含义 | 是否正常调用 |
|---|---|---|
| `unverified` | 尚未经过真实运行验证 | 是，低风险试跑 |
| `healthy` | 最近运行稳定、字段质量符合预期 | 是 |
| `degraded` | 可以使用，但成功率、完整度或时效下降 | 是，同时允许更早回退 |
| `unstable` | 频繁失败或结果明显异常 | 仅有限尝试，优先备用Provider |
| `cooling_down` | 触发限流、封禁或持续故障，进入冷却期 | 否，冷却期后探测 |
| `disabled` | 明确停用、永久失效或不再符合项目规则 | 否 |

来源本身另有运行状态：

- `active`；
- `inactive`；
- `possibly_inactive`；
- `removed`；
- `disabled`。

“来源长期不更新”应改变Source状态，而不是直接把Provider标记为故障。

---

## 7. 单次采集结果状态

每次Provider尝试应记录一个明确结果：

```text
success_with_items
success_empty
partial_success
suspicious_empty
failed_retryable
failed_rate_limited
failed_blocked
failed_parser_changed
failed_auth_or_config
failed_source_removed
failed_final
```

### 7.1 空结果的处理

`success_empty`适用于：

- 来源确实没有发布内容；
- 查询窗口很短；
- 来源属于`irregular`或`event_driven`；
- 其他Provider也没有发现新内容。

`suspicious_empty`适用于：

- 核心高频来源连续多个窗口返回空；
- 同一来源的备用Provider发现了内容；
- Provider的多个活跃测试来源同时返回空；
- 返回页面明显是验证页、空壳页或结构异常。

空结果不能直接计入技术失败率，但可单独计入“可疑空结果率”。

---

## 8. 错误分类

建议统一错误码，避免只保存自由文本：

```text
network_timeout
network_dns
http_4xx
http_5xx
rate_limited
blocked_or_captcha
login_required
invalid_credentials
config_missing
provider_unavailable
parser_changed
invalid_payload
content_incomplete
external_id_missing
timestamp_missing
source_removed
source_private
unsupported_content
unknown_error
```

错误记录同时保留：

- `error_code`；
- `error_message`；
- HTTP状态；
- Provider原始响应文件位置；
- 是否允许重试；
- 建议下次重试时间。

---

## 9. 健康指标

V1不使用单一0至100综合健康分，而记录以下滚动指标：

### 9.1 技术稳定性

- 最近10次和最近20次尝试成功率；
- 连续失败次数；
- 超时率；
- 限流率；
- 解析失败率；
- 平均和P95响应时间。

### 9.2 内容质量

- 完整正文或字幕取得率；
- 精确时间取得率；
- 外部ID取得率；
- 原始链接取得率；
- `metadata_only`比例；
- 可疑空结果率。

### 9.3 时效和覆盖

- 发现延迟：`collected_at - published_at`；
- 报告窗口覆盖状态；
- 最早可回补时间；
- 回补成功率；
- 与备用Provider相比的漏项率。

不同Provider不能使用完全相同的期望值。例如公共搜索Provider天然具有延迟和漏项，不应按官方公开接口的标准评价。

---

## 10. 状态转换建议

以下为第一版建议值，可在试运行后调整。

### 10.1 进入`degraded`

满足任一条件：

- 连续3次技术失败；
- 最近10次技术成功率低于80%；
- 最近10次`partial`或`metadata_only`比例明显高于能力基线；
- 精确时间、外部ID或原始链接字段突然大面积缺失；
- 可疑空结果连续出现。

### 10.2 进入`unstable`

满足任一条件：

- 连续5次技术失败；
- 最近20次技术成功率低于50%；
- 解析结构持续变化；
- 同一来源的备用Provider持续发现主Provider漏掉的内容；
- 结果质量已经不足以支持报告使用。

### 10.3 进入`cooling_down`

适用于：

- 429限流；
- 验证码或临时封禁；
- 短期集中请求导致的阻断；
- 已知Provider服务临时故障。

冷却时间使用递增策略，例如：

```text
第一次：30分钟
第二次：2小时
第三次：6小时
第四次及以后：24小时
```

### 10.4 进入`disabled`

只在以下情况自动或人工确认后使用：

- Provider明确永久关闭；
- 来源删除、转为私密且长期无法访问；
- 违反项目零付费内容策略；
- 依赖已经不可恢复；
- 连续较长时间无法取得任何可用结果并完成复核。

不能因为一次或几次失败自动永久停用。

### 10.5 恢复

从`degraded`、`unstable`或`cooling_down`恢复时应使用滞后机制：

- 冷却结束后先进行小范围探测；
- 至少连续2次成功后恢复为`degraded`；
- 至少连续3次成功且字段质量恢复后变为`healthy`。

避免状态在健康和故障之间频繁抖动。

---

## 11. Provider回退规则

Collector按绑定优先级依次调用：

```text
Primary Provider
  ↓ 技术失败、被阻断或结果可疑
Fallback Provider 1
  ↓ 仍失败
Fallback Provider 2
  ↓
记录覆盖不足并继续其他来源
```

### 11.1 允许立即回退

- 网络或服务失败；
- 限流或阻断；
- 页面结构解析失败；
- 返回无效载荷；
- 关键字段大面积缺失；
- `suspicious_empty`。

### 11.2 不应立即回退

- 正常`success_empty`；
- 来源本身近期不活跃；
- 当前窗口外没有内容；
- 已经取得完整内容，只是没有足够重要性。

### 11.3 避免多Provider无意义重复调用

V1默认串行回退，不同时请求所有Provider。只有在以下情况允许影子验证：

- 新Provider试运行；
- 主Provider质量下降；
- 评估漏项率；
- 服务器迁移前后对比；
- 每两至四周的来源复盘。

影子结果用于评估，不直接重复入库。

---

## 12. Provider级测试来源

为避免“所有目标来源恰好没更新”被误判为Provider正常，部分Provider应配置少量测试来源或公开测试端点。

例如：

- X Provider：选择2至3个通常高频更新的公开账号；
- RSS Provider：选择稳定公开Feed；
- YouTube Provider：选择活跃公开频道；
- 行情Provider：选择交易日通常有数据的代表性标的；
- 官方数据Provider：检查公开端点和更新时间。

测试来源仅用于判断Provider整体可用性，不进入正式报告。

---

## 13. 来源优先级与回退资源

不同来源使用不同回退力度：

### `core`

- 可尝试全部已启用免费Provider；
- 报告前允许额外补抓；
- 连续失败需要进入完整性说明和内部告警；
- 优先进行恢复测试。

### `supplementary`

- 主Provider失败后尝试1至2个备用Provider；
- 不因单个来源失败延迟报告。

### `observe`

- 通常只使用主Provider；
- 失败后记录，不进行高成本回退；
- 连续失败可自动降低采集频率。

---

## 14. 报告中的完整性披露

内部运行记录始终保存详细健康数据，但成品报告不应每天堆积技术日志。

只有以下情况需要在报告中说明：

- 某一核心平台整体覆盖明显不足；
- 多个核心来源未成功采集；
- 关键行情或宏观数据缺失；
- 某类内容只能取得标题或元数据；
- 覆盖不足可能明显影响结论完整性。

建议简短表述：

```text
数据完整性：本期X核心账号覆盖部分缺失，相关观点栏目可能不完整；官方数据与主要媒体采集正常。
```

不得因为免费Provider失败而伪装成完整覆盖。

---

## 15. 本地与服务器环境切换

每个Provider需要记录适用环境：

```yaml
environments:
  windows: supported
  wsl2: supported
  linux_server: unverified
```

迁移服务器前应进行影子测试：

- 本机和服务器对同一来源、同一窗口同时采集；
- 对比成功率、漏项率、正文完整率和延迟；
- 服务器结果达到要求后再切换主Provider；
- 如果X或公众号在服务器IP下明显退化，可保留本机采集节点，将RawItem同步至服务器处理。

第一版不预设一定需要混合架构，只保留可选能力。

---

## 16. 维护与复盘

建议每两至四周复盘：

- Provider成功率和连续失败；
- 可疑空结果率；
- 正文、字幕和关键字段完整率；
- 主Provider与备用Provider漏项差异；
- 哪些来源已经长期不活跃；
- 哪些Provider应升级、降级、暂停或删除；
- 是否存在更成熟的免费开源替代项目。

调整流程：

```text
观察指标
→ 识别问题属于Source还是Provider
→ 影子验证备用方案
→ 修改Provider顺序或状态
→ 观察两至四周
→ 复盘结果
```

---

## 17. 第一版暂不包含

- 实时可视化健康监控网页；
- 短信、电话或付费告警服务；
- 复杂机器学习异常检测；
- 单一综合健康分驱动全部决策；
- 自动安装未知第三方爬虫；
- 免费Provider失败后自动购买或调用付费服务。

---

## 18. 当前定稿

第一版采用：

```text
来源配置决定抓谁
Provider配置决定怎么抓
SourceProviderBinding记录每条获取链的能力和健康
Collector根据状态和优先级执行免费回退
报告引擎只读取可追溯、完整度明确的结果
```

健康管理的核心不是追求所有来源永远成功，而是：知道哪里失败、失败到什么程度、是否有备用路径，以及失败是否会影响本期报告结论。