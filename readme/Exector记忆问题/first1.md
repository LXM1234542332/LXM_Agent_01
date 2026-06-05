当前 Executor 的问题不只是"看不到前序结果"，而是：

  1. 参数来源不明确：Executor 需要"payment-service"这个名字，但它不知道这是从 get_alerts() 结果里拿到的
  2. 重复调用浪费：如果 Executor 拿不到上下文，可能会重新调用 get_alerts() 来获取服务名
  3. 混淆风险：如果把所有数据堆在一起注入给 LLM，LLM 可能混用数据

  你提到的关键点是：结构化 + 语义明确 才能发挥作用，否则适得其反。

  ---
  工作记忆设计方案

  核心思想：提取"可复用的参数池"

  不是把整个工具输出存储，而是从每次工具调用的结果中，提取出具名的、有语义的参数，形成一个参数池供后续工具调用直接取用。

  数据结构设计
```
  class WorkingMemory:
      """单次诊断的工作记忆"""

      # 1. 原始执行轨迹（保留完整结果，供最终报告用）
      execution_trace: List[StepRecord]

      # 2. 参数池（可复用的结构化参数，供后续工具调用直接取用）
      param_pool: ParameterPool

      # 3. 诊断上下文（当前诊断的关键摘要）
      diagnosis_context: DiagnosisContext
```

```
  class StepRecord:
      """执行记录"""
      step_index: int
      step_description: str
      tool_name: str           # 调用的工具名
      tool_args: Dict          # 实际传入的参数
      raw_result: str          # 工具原始返回
      extracted_params: Dict   # 从结果中提取出的可复用参数
```
```
  class ParameterPool:
      """
      结构化参数池 - 语义明确的可复用参数

      每个字段都有明确的来源说明，避免歧义
      """
      # 服务相关
      affected_services: List[str]         # 受影响的服务名列表，来源: get_alerts()
      root_cause_service: Optional[str]    # 初步判断的根因服务，来源: get_alerts()/分析

      # 时间相关
      incident_start_time: Optional[str]   # 事故开始时间，来源: get_alerts()
      incident_end_time: Optional[str]     # 事故结束/当前时间

      # 告警相关
      active_alert_ids: List[str]          # 活跃告警ID列表，来源: get_alerts()
      alert_severity: Optional[str]        # 最高告警级别 (critical/warning)

      # 指标相关
      anomalous_metrics: List[str]         # 异常指标名列表，来源: get_metrics_anomalies()
      anomalous_services_from_metrics: List[str]  # 指标层面发现的异常服务

      # 部署相关
      recent_deployment: Optional[str]     # 最近部署的服务/版本，来源: get_deployment_events()
      deployment_time: Optional[str]       # 部署时间
```

```
  class DiagnosisContext:
      """当前诊断的全局摘要"""
      fault_type: Optional[str]            # 故障类型 (如: 高延迟/连接泄漏/部署缺陷)
      fault_description: Optional[str]     # 一句话描述当前问题
      confidence: float                    # 诊断置信度 0-1
```

  ---
  运作流程

  Executor 执行 get_alerts()
    ↓ 原始结果
    ↓
  [自动提取] → 写入 param_pool:
    - affected_services: ["payment-service"]
    - incident_start_time: "2026-06-02 14:30:00"
    - alert_severity: "critical"
    - active_alert_ids: ["alert-001"]
    ↓
  下一步: 调用 get_logs_by_service(service=???)
    ↓
  Executor 查 param_pool → service = "payment-service" ✓
    不需要重新调用 get_alerts()

  ---
  关键设计决策

  1. 谁来提取参数？

  有两个选择：
  - 选择 A：LLM 提取（每次 Executor 执行完后，让 LLM 从结果中提取结构化参数）
  - 选择 B：规则提取（写固定的解析逻辑，按字段名提取）

  我推荐选择 A，原因是：
  - 工具返回的 JSON 结构可能变化
  - LLM 能理解语义而不是只匹配字段名
  - 配合明确的 Pydantic schema，提取结果是可控的

  2. 如何避免歧义？

  每个参数都必须有：
  - 明确的字段名（affected_services 而不是 services）
  - 来源标注（是从哪个工具的结果中提取的）
  - 覆盖策略（新值覆盖旧值，还是追加？）

  例如：
  - affected_services → 追加（多次工具调用可能发现更多受影响服务）
  - root_cause_service → 覆盖（最新的判断更准确）
  - incident_start_time → 首次写入后不覆盖（第一次发现的时间最准确）

  3. 注入给 Executor 的格式

  不是把整个 param_pool 塞给 LLM，而是生成一段简洁的提示：

  ## 已知可用参数（无需重复调用工具获取）
  - 受影响服务：payment-service（来源：第1步 get_alerts）
  - 事故开始时间：2026-06-02 14:30:00（来源：第1步 get_alerts）
  - 异常指标：error_rate, latency_p99（来源：第2步 get_metrics_anomalies）

  ## 当前任务
  请执行以下步骤：调用 get_logs_by_service(service=...) - 查询受影响服务的错误日志

  ---
  方案评估

  ┌──────────────┬──────┬──────────────────────────────────┐
  │     维度     │ 评分 │               说明                │
  ├──────────────┼──────┼──────────────────────────────────┤
  │ 减少重复调用 │ ✓✓   │ 参数池直接复用，不再重复调用工具     │
  ├──────────────┼──────┼──────────────────────────────────┤
  │ 语义清晰     │ ✓✓   │ 每个字段有明确来源和含义            │
  ├──────────────┼──────┼──────────────────────────────────┤
  │ 防歧义       │ ✓    │ 字段名设计严格，覆盖策略明确        │
  ├──────────────┼──────┼──────────────────────────────────┤
  │ 实现复杂度   │ 中   │ 需要新增提取逻辑，但可控            │
  ├──────────────┼──────┼──────────────────────────────────┤
  │ LLM 幻觉风险 │ 低   │ 参数来源可追溯，不是凭空生成         │
  └──────────────┴──────┴──────────────────────────────────┘

  ---
  问题

  在你确认这个方向可行之后，我需要你明确几点：

  1. 参数池字段范围：我上面列的字段是否够用？还是有你的业务场景中特别常见的参数需要补充？
  2. 提取时机：是每次 Executor 执行完后立即提取（同步），还是 Replanner 决策时再提取？
    - 我倾向于立即提取，这样下一步的 Executor 就能马上用上
  3. param_pool 存在哪里：
    - 选项 A：放入 PlanExecuteState（LangGraph 状态，持久化）
    - 选项 B：放入 working_memory 对象（内存，单次诊断生命周期）
    - 我倾向于 选项 A，因为 LangGraph 状态天然支持跨节点共享
  4. Triage 节点的关系：Triage 节点强制调用 get_alerts() 的结果，是否直接写入 param_pool？这样 Planner 也能用上这些参数？