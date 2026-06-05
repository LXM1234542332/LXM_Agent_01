# RAG 接入 + 数据场景改写计划

> 本文档记录项目当前状态、核心问题、以及后续执行计划。后续开发以此为参照。
> 最后更新：2026-06-05（补充工具层/状态层扩充分析）

---

## 一、项目现状

### 系统架构（已完成）

```
Triage（get_alerts + get_metrics_anomalies）
  ↓ WorkingMemory（锚点参数）+ ExactValuePool（精确值池）
Planner（基于故障画像生成诊断计划）
  ↓
Executor（注入 WorkingMemory + ExactValuePool + past_steps 摘要）
  ↓
Replanner（决策：continue / replan / respond）
  ↓
诊断报告（Markdown，自动保存到 data/{scenario_id}/运维agent报告.md）
```

核心改进（已实现）：Triage 节点、ExactValuePool 精确值池、past_steps 分层摘要、WorkingMemory 锚点参数。

### 当前 8 个场景覆盖的故障类型

| 场景 | 根因服务 | 故障类型 | 核心异常指标 |
|---|---|---|---|
| scenario1 | payment-service | 发版引入超时缺陷，级联故障 | error_rate, request_latency |
| scenario2 | user-service | 发版引入数据库连接泄漏 | db_connections, error_rate |
| scenario3 | order-service | 发版引入内存泄漏 + GC 停顿 | memory_usage, gc_time, latency |
| scenario4 | search-service | 发版引入 CPU 密集型缺陷 | cpu_usage, request_latency |
| scenario5 | cache-service | 发版引入内存异常占用 | memory_usage_percent |
| scenario6 | database-service | 磁盘空间耗尽（无发版） | disk_usage_percent, error_rate |
| scenario7 | notification-service | 发版导致消息队列消费能力丧失 | queue_depth, memory_usage |
| scenario8 | database-service | 数据库进程崩溃（无发版） | error_rate（全服务 100%） |

---

## 二、发现的核心问题与连锁影响

### 问题 1：场景复杂度不够（更关键）

**具体表现：**

8 个场景的告警消息直接揭示了根因：

```
"message": "连接泄漏开始"   ← 根因已在告警里
"message": "内存泄漏开始"   ← 根因已在告警里
"message": "数据库进程崩溃" ← 根因已在告警里
```

Agent 实际上只需要 **2-3 轮工具调用**就能定位根因——因为告警文本本身已经说明了问题。这导致：

- Agent 的存在价值无法体现（规则引擎也能做到）
- Planner 的规划质量差异很小（因为答案几乎显而易见）
- RAG 的增益无法被量化（因为不需要"排查思路"来辅助）
- 8 个场景结构高度相同：都是单一服务、单一指标、发版后 30 秒触发

每个场景涵盖的事件、指标记录、错误信息等等（还有其他的不一一列举）太少了

- 真实场景可能有多个事件
- 系统的指标会更多更复杂
- 错误更多样

**真实生产环境中告警的样子：**

```
"message": "error_rate > 5% for 3 minutes"   ← 只说有问题，不说为什么
"message": "p99 latency > 2000ms"            ← 需要多轮排查才能定根因
```

**问题的根本影响：**
场景复杂度不够 → Agent 不需要 RAG 辅助 → RAG 的价值体现不出来 → 整个项目的技术深度被质疑。

---

### 问题 2：知识文档内容偏少（次要）

因为我们的知识文档最终还是来源于我们的数据，例如：事件部署、警告、指标变化等等单一的或者多重的问题的相关的经验信息

**这是次要问题：解决了问题 1，问题 2 自然有更多素材可写。**

---

### 问题 3：工具覆盖缺口——新指标没有对应查询工具

当前 MCP 工具集面向的指标类型极为有限：

| 工具 | 实际能查的指标类型 |
|---|---|
| get_metrics_by_name | 仅支持已存在于 metrics.json 的固定指标名 |
| get_metrics_anomalies | 只做阈值百分位判断，无法查资源饱和度、连接池状态等结构化指标 |
| get_slow_traces | 只有延迟维度，无错误率、重试次数等维度 |

**如果场景数据扩充了以下指标类型，当前工具无法处理：**

- 连接池状态（active/idle/waiting 连接数分布）
- JVM/运行时指标（heap used/max、GC 频率、线程数）
- 队列状态（queue depth、consumer lag、publish rate vs consume rate）
- 数据库慢查询（query duration 分布、锁等待时间）
- 网络层指标（TCP retransmit、connection timeout rate）
- 饱和度指标（线程池队列等待深度、信号量剩余容量）

工具缺口的后果：Agent 拿到异常告警后，没有工具可以深挖，只能停在表面结论。

---

### 问题 4：状态结构缺口——WorkingMemory 和 ExactValuePool 设计偏窄

**当前 WorkingMemory 只有 6 个锚点：**

```python
class WorkingMemory(TypedDict, total=False):
    alert_first_trigger_time: str
    analysis_start_time: str
    analysis_end_time: str
    scenario_id: str
    alert_count: int
    highest_severity: str
```

新指标引入后，以下信息也应该在 Triage 阶段就固定下来作为锚点，但当前结构没有位置存放：

- 受影响服务的数量和名称列表（目前在 ExactValuePool，但不是锚点级别的稳定参数）
- 是否存在部署事件（影响 Planner 的策略选择）
- 故障传播方向的初步判断（哪个服务先出问题）
- 异常指标的数量和类型分布（几个延迟类、几个资源类、几个错误类）

**当前 ExactValuePool 也有结构性不足：**

```python
class ExactValuePool(TypedDict, total=False):
    known_services: List[str]
    known_metric_names: List[str]
    known_trace_ids: List[str]
    known_event_types: List[str]
    known_severities: List[str]
    known_timestamps: List[str]
```

新指标引入后缺失的字段：
- `known_query_ids`：慢查询 ID（如果加了慢查询工具）
- `known_queue_names`：消息队列名称
- `known_node_ids`：如果是 K8s 场景，Pod/Node 名称
- `known_anomaly_services`：已确认有异常的服务（区别于 known_services 泛列表）
- `known_deployment_versions`：部署的版本号（用于关联发版与故障）

ExactValuePool 不扩充，Executor 从里面取参数时就取不到正确值，仍然会出现参数幻觉问题。

---

### 问题 5：Triage 逻辑和 fault_signature 覆盖不足

**当前 Triage 只强制调用两个工具：**

```python
# 当前强制调用
get_alerts()
get_metrics_anomalies()
```

**当前 fault_signature 只包含：**

```
告警数量 + 最高级别
受影响服务列表
异常指标名列表
告警触发时间
分析时间窗口
场景ID
```

新指标和新工具引入后，以下信息如果在 Triage 阶段不收集，Planner 就看不到，无法制定针对性计划：

- 是否存在部署事件（Planner 需要据此决定是否优先查 deployment）
- 服务间的依赖关系摘要（Planner 需要据此判断传播方向）
- 各服务的异常指标数量分布（决定从哪个服务开始深挖）

**但 Triage 不能无限扩展工具调用数量**，否则每次诊断开始都要调用 5-6 个工具，性能和 token 开销太高。这是一个需要权衡的设计决策。

---

## 三、解决思路

### 优先级：先改数据复杂度，再建知识库

两件事的依赖关系：

```
数据复杂度提升 → Agent 真正需要多轮推理 → RAG 辅助有了价值
                                         → 知识文档有了用武之地
                                         → 评估 A/B 结果有显著差距
```

反过来，如果先建知识库而不改场景，知识库对 planner 没有实际帮助，做了也是虚的。

---

### 方向 A：场景数据复杂度改写

**目标：让 Agent 需要 5-8 轮工具调用才能收敛，而不是 2-3 轮。**

改造的几个维度：

**① 告警消息模糊化（最关键）**

```json
// 改前（直接揭示根因）
{ "message": "连接泄漏开始" }

// 改后（只说现象，不说原因）
{ "message": "error_rate exceeds threshold: 12.3%" }
{ "message": "db_connection_wait_time > 500ms" }
```

**② 多服务同时异常，需判断传播方向**

改前：1 个服务异常 → 根因就是它。

改后：3 个服务都有异常指标，Agent 需要通过时序对比和调用链判断谁是源头、谁是受害者。

**③ 干扰项和噪声**

- 在故障时间窗口内加入不相关的配置变更事件
- 加入正常波动（某服务 CPU 略高但不是根因）
- 加入告警误报（某指标触发告警但实际无影响）

**④ 多指标交叉异常**

```
database-service: db_connections↑ + cpu↑ + latency↑   ← 真正的根因
payment-service:  error_rate↑ + latency↑               ← 级联受害者
order-service:    latency↑                              ← 更远的受害者
```
Agent 需要分析"哪些是因，哪些是果"，而不是只看哪个服务有告警。

**⑤ 根因不在发版（需要更多轮才能定位）**

当前 6/8 的场景都是"发版后 30 秒出问题" → 两步就能定位。

改写部分场景为：没有发版事件，需要查慢查询 + 流量 + 连接数多维度才能收敛。

---

### 方向 C：工具层扩充（与方向A并行推进）

**原则：场景需要什么指标，就补什么工具，不超量。**

按新场景涉及的故障类型，需补充的工具方向：

| 故障类型 | 需要新增的工具 | 对应查询的指标/数据 |
|---|---|---|
| 连接池耗尽 | `get_connection_pool_status(service)` | active/idle/waiting/max 连接数 |
| JVM 内存泄漏 | `get_jvm_metrics(service)` | heap_used, heap_max, gc_count, gc_time, thread_count |
| 消息队列积压 | `get_queue_metrics(queue_name)` | depth, consumer_lag, publish_rate, consume_rate |
| 数据库慢查询 | `get_slow_queries(service, threshold_ms)` | query_text, duration, lock_wait_time, rows_examined |
| 流量突增 | `get_traffic_metrics(service)` | rps, error_rps, p50/p95/p99 latency 趋势 |
| 级联故障溯源 | `get_upstream_error_rate(service)` | 上游服务的 error_rate 时序，用于判断传播方向 |

**每新增一个工具，必须同时完成以下四件事（缺一不可）：**
1. 在 `mcp_servers/diagnostic_server.py` 注册 MCP 工具
2. 在 `diagnostic_tools.py` 实现数据读取逻辑
3. 在 `app/agent/aiops/memory.py` 的 `EXTRACTORS` 中添加对应提取规则
4. 在各场景的 JSON 数据文件中补充对应数据

---

### 方向 D：状态结构同步扩充（配套方向C）

**WorkingMemory 扩充（triage 阶段固定的锚点）：**

```python
class WorkingMemory(TypedDict, total=False):
    # 原有字段（保留）
    alert_first_trigger_time: str
    analysis_start_time: str
    analysis_end_time: str
    scenario_id: str
    alert_count: int
    highest_severity: str
    # 新增字段
    affected_service_count: int       # 受影响服务数量（多服务场景关键）
    has_deployment_event: bool        # 是否存在部署事件（影响 Planner 策略）
    anomaly_metric_count: int         # 异常指标数量（影响诊断深度判断）
    fault_categories: List[str]       # 故障类型分类：["latency", "resource", "error"]
```

**ExactValuePool 扩充（执行过程中动态累积）：**

```python
class ExactValuePool(TypedDict, total=False):
    # 原有字段（保留）
    known_services: List[str]
    known_metric_names: List[str]
    known_trace_ids: List[str]
    known_event_types: List[str]
    known_severities: List[str]
    known_timestamps: List[str]
    # 新增字段（随工具扩充而增加）
    known_anomaly_services: List[str]      # 已确认有异常的服务（区别于泛列表）
    known_deployment_versions: List[str]   # 部署版本号
    known_query_ids: List[str]             # 慢查询 ID
    known_queue_names: List[str]           # 消息队列名称
```

**Triage 节点扩充原则（重要）：**

Triage 强制调用的工具数量控制在 **3 个以内**，目的是快速建立全局画像，不是穷举：

```
必须调用（保留）：get_alerts, get_metrics_anomalies
按需调用（新增）：get_deployment_events（仅当 alerts 中有 deployment 相关信号时）
```

`fault_signature` 增加以下信息段：

```
- 是否有部署事件：是/否
- 故障类型初判：latency / resource / error / mixed
- 受影响服务数：N 个
```

---

### 方向 B：RAG 知识库建设

**知识卡片的核心思想：不绑定具体工具，只描述排查思维。**

格式：`现象 → 可能根因方向 → 排查优先级 → 证据权重 → 常见陷阱`

这样 planner 拿到排查思路后，自己决定调用哪个工具，RAG 赋予的是**排查逻辑**而不是**工具调用脚本**。

**知识来源（三类）：**

1. **手写核心卡片**：覆盖 8 类故障大类的排查思路，20-30 条，质量最高
2. **基于改写后场景蒸馏**：从更复杂的场景反推排查方法论，写成通用卡片
3. **开源 Runbook 翻译整理**：已下载 Scoutflo-SRE-Playbooks（AWS/K8s 英文 playbook），翻译提炼为中文卡片，50-100 条

**知识库规模目标：100-200 条卡片**（面试时说得出口，且超过了"直接塞 prompt"的上限）

**技术实现：**
- 独立 Milvus collection（`aiops_runbook`），不混入现有 `biz` collection
- 在 triage → planner 之间加 `retrieve` 节点
- state 新增 `retrieved_knowledge` 字段
- planner prompt 注入检索结果，加"参考但不照搬"约束

---

## 四、执行计划

### 阶段一：场景数据改写（优先执行）

目标：依次改写8个场景，将 Agent 所需工具调用轮次从 2-3 轮提升到 6 轮以上。

- [ ] 确定改写策略：哪几个场景改，改哪些维度
- [ ] 改写告警消息（去掉直接揭示根因的描述）
- [ ] 增加多服务异常指标的交叉关联
- [ ] 加入干扰项（不相关事件、告警噪声）
- [ ] 更新各场景的 `目标.json`（标准答案对应更新）
- [ ] 验证：跑 Agent 确认需要更多轮次才能收敛

**配套任务（与场景改写同步执行，不可推后）：**

- [ ] 梳理新场景涉及的指标类型，列出工具缺口清单
- [ ] 按缺口清单补充 MCP 工具（`diagnostic_server.py` + `diagnostic_tools.py`）
- [ ] 同步更新 EXTRACTORS 提取规则（`memory.py`）
- [ ] 同步扩充 WorkingMemory 和 ExactValuePool 字段定义（`state.py`）
- [ ] 更新 Triage 的 fault_signature 生成逻辑（`triage.py`）
- [ ] 验证：新工具返回的字段能被正确提取进 ExactValuePool

### 阶段二：RAG 知识库建设

- [ ] 创建 `aiops_runbook` Milvus collection（让向量服务支持指定 collection）
- [ ] 手写 20-30 条核心排查卡片（覆盖 8 类故障大类）
- [ ] 翻译整理 Scoutflo Playbook 中相关内容（50-100 条）
- [ ] 建库脚本：读卡片 → 向量化 → 写入 Milvus

### 阶段三：RAG 接入主流程

- [ ] 新增 `retrieve` 节点（triage 之后、planner 之前）
- [ ] state 新增 `retrieved_knowledge: str` 字段
- [ ] planner prompt 加入检索结果注入段（含"参考不照搬"约束）
- [ ] 检索失败降级处理（空结果时退回纯 LLM 规划）

### 阶段四：A/B 评估验证

- [ ] 对照组：无 RAG 的 planner
- [ ] 实验组：RAG 增强的 planner
- [ ] 用改写后的复杂场景跑评估，对比根因准确率三项指标
- [ ] 在 LangSmith 上记录对比结果

---

## 五、面试时的叙事逻辑

```
"我在做根因准确率评估时发现两个问题：

第一，场景数据过于简单——告警消息直接揭示了根因，Agent 2-3 轮
就能定位，这种难度规则引擎也能做到，体现不出 Agent 的价值。

第二，正因为场景简单，RAG 知识库接进来也没有用武之地——Planner
根本不需要参考排查思路，答案已经在告警里了。

所以我的解法是两步走：
① 先改写场景数据，让告警只描述现象、不揭示根因，同时加入多服务
  交叉异常和干扰项，让 Agent 真正需要 4-6 轮多维度排查才能收敛。
② 在此基础上建 RAG 知识库，内容是'不绑定工具的排查思维卡片'——
  现象 → 根因假设 → 排查优先级 → 证据权重，让 Planner 生成的计划
  从通用模板变成由真实告警 + 领域知识共同驱动的动态计划。

最后用改写后的复杂场景做 A/B 评估，量化 RAG 对根因准确率的实际提升。"
```

---

## 六、关键设计原则（执行时参照）

1. **告警只说现象，不说根因** — 这是提升场景复杂度最重要的一条
2. **知识卡片不绑定工具** — 写排查思维，不写"调用 get_logs()"
3. **RAG 是增强项不是依赖项** — 检索失败时 Agent 退回原有逻辑，不中断流程
4. **先改数据再接 RAG** — 顺序不能反，否则 RAG 的效果无法被验证
5. **知识库用独立 collection** — 不混入 `biz`，便于独立重建和检索
6. **评估公正性** — 知识库只存方法论（SOP），不存具体场景的标准答案
7. **工具、数据、状态同步扩充** — 新增指标必须同时配套：新工具 + EXTRACTORS规则 + ExactValuePool字段，三者缺一则新指标对 Agent 是不可见的
8. **Triage 强制调用工具上限 3 个** — Triage 阶段只建全局画像，不做深度排查；超过 3 个强制调用会导致每次诊断开始就消耗大量 token，且锚点过多反而稀释 Planner 的注意力

---

*执行过程中遇到问题，以此文档为基准调整，不要偏离核心目标：场景复杂度 + 工具/状态配套扩充 + RAG 接入。*
