问题本质不是只有"没记住 payment-service"，而是：

  ▎ LLM 不知道"某个工具参数应该从哪里来"。

  这会导致两个层面的失败：

  1. 有数据但不会用
  比如 get_alerts() 已经返回了 service_name=payment-service，但 LLM 不知道后面的 get_logs_by_service(service=...) 应该从这里取。
  2. 没数据时不会补采
  如果当前 memory 里没有 service，LLM 也不知道应该先去调用哪个工具补齐它，是 get_alerts()、get_service_dependencies()，还是别的工具。

  所以，单纯做"结果结构化存储"还不够。
  你还需要一层更关键的东西：

  参数来源知识层

  也就是给 Agent 一份明确的"参数获取地图"。

  ---
  一、为什么这个问题普遍存在

  因为 LLM 本身只知道自然语言，不知道你这套工具生态里的"参数依赖关系"。

  举个例子：

  - get_logs_by_service(service=...)
  - get_logs_by_time_range(start_time=..., end_time=...)
  - get_pod_status(service=...)
  - get_deployment_events(service=...)

  对人来说很自然：

  - service 通常可以从告警、异常指标、部署事件里拿
  - start_time/end_time 通常可以从告警触发时间拿
  - pod_name 可能要先从 service 再查一层

  但对 LLM 来说，这些都不是常识，除非你显式告诉它：

  - 这个参数叫什么
  - 它的候选来源有哪些
  - 优先从哪里取
  - 没取到时应该补调哪个工具

  所以你现在碰到的问题，本质上是：

  不是 memory 缺失，而是"参数获取知识"缺失

  ---
  二、只做结构化 memory 为什么还不够

  假设你已经有了结构化 memory：

  {
    "affected_services": ["payment-service"],
    "incident_start_time": "2026-06-02 14:30:00"
  }

  这只能解决：

  - "如果已经存了，我可以复用"

  但解决不了：

  - "如果没存，我该去哪里找？"
  - "同一个参数有多个候选来源时，优先用哪个？"
  - "不同工具返回的字段名不同，哪个才是我要的 service？"

  也就是说，结构化 memory 解决的是：

  参数复用问题

  但你现在提出的这个更普遍的问题，解决的是：

  参数寻址问题

  这两个要分开设计。

  ---
  三、应该怎么解决：两层机制一起上

  我建议你把方案拆成两层。

  第 1 层：结构化工作记忆

  解决"已经拿到的数据怎么复用"

  第 2 层：参数来源注册表

  解决"还没拿到的数据应该去哪里找"

  这两层结合，Executor 才真的不瞎。

  ---
  四、参数来源注册表怎么设计

  你可以把它理解成一份静态知识表，告诉 Agent：

  - 每个工具需要哪些参数
  - 每个参数优先从 memory 的哪个字段取
  - 如果 memory 没有，就该调用哪个工具去补
  - 补回来后，应该写回 memory 的哪个字段

  示例

  PARAM_SOURCE_REGISTRY = {
      "get_logs_by_service": {
          "service": {
              "memory_keys": ["root_cause_service", "affected_services"],
              "fallback_tools": ["get_alerts", "get_metrics_anomalies"],
              "selection_rule": "优先 root_cause_service；否则取 affected_services[0]"
          }
      },
      "get_logs_by_time_range": {
          "start_time": {
              "memory_keys": ["incident_start_time"],
              "fallback_tools": ["get_alerts"],
              "selection_rule": "使用告警首次触发时间"
          },
          "end_time": {
              "memory_keys": ["incident_end_time", "current_time"],
              "fallback_tools": [],
              "selection_rule": "优先 incident_end_time，否则用当前时间"
          }
      },
      "get_deployment_events": {
          "service": {
              "memory_keys": ["root_cause_service", "affected_services"],
              "fallback_tools": ["get_alerts"],
              "selection_rule": "优先根因服务，否则取主要受影响服务"
          }
      }
  }

  这个表的价值非常大。

  因为它把原来依赖 LLM 猜测的东西，变成了显式知识。

  ---
  五、Executor 应该怎么利用这层知识

  以后 Executor 在执行某一步时，不是直接把任务丢给 LLM，而是先做一轮"参数准备"。

  执行流程应该变成这样

  步骤 1：识别当前要调用的工具和参数

  比如当前任务是：

  "调用 get_logs_by_service(service=根据告警确定的服务名) - 深入分析受影响服务的错误日志"

  识别出：
  - 工具：get_logs_by_service
  - 缺失参数：service

  步骤 2：先查 memory

  根据注册表去查：

  - root_cause_service 有没有？
  - affected_services 有没有？

  如果有，直接填。

  步骤 3：如果 memory 没有，再查注册表里的 fallback_tools

  比如 service 没有，就知道应该补调：

  - get_alerts
  - 或 get_metrics_anomalies

  而不是让 LLM自己瞎猜。

  步骤 4：补齐后写回 memory

  补调结果结构化提取后，写回：
  - affected_services
  - root_cause_service
  - incident_start_time

  然后继续当前主步骤。

  ---
  六、这样就能解决你说的那个核心痛点

  你举的这个例子：

  ▎ Executor 需要 payment-service，但不知道这是从 get_alerts() 结果里拿到的

  在新机制下变成：

  1. 当前工具需要 service
  2. 参数注册表告诉它：
    - 先看 root_cause_service
    - 再看 affected_services
    - 没有就调用 get_alerts
  3. get_alerts 的结构化提取器会把结果写入：
    - affected_services = ["payment-service"]
  4. Executor 再从 memory 里取出 payment-service
  5. 调用 get_logs_by_service(service="payment-service")

  这就不是 LLM "知道"了，而是系统在帮它做参数寻址。

  ---
  七、你这个问题说明当前架构里还缺一个中间层

  你现在的架构大概是：

  步骤描述 → LLM → 工具调用

  这太直接了，导致 LLM 要同时负责：

  - 理解任务
  - 决定工具
  - 决定参数
  - 决定参数来源
  - 决定缺失参数怎么补

  负担太重，也不稳定。

  更合理的架构应该是：

  步骤描述
    ↓
  参数解析 / 参数寻址层
    ↓
  memory 命中 or fallback tool 补采
    ↓
  LLM / Tool Calling
    ↓
  结果结构化提取
    ↓
  写回 memory

  也就是说，你需要在 Executor 前面再加一个轻量的：

  Parameter Resolution 层

  它不一定单独做成 LangGraph 节点，也可以先做成 executor.py 里的内部步骤。

  ---
  八、你应该如何设计"参数来源知识"

  我建议分 3 类参数，不要一开始全做。

  第一类：通用诊断参数

  最值得优先做，因为复用率最高

  - service
  - start_time
  - end_time
  - alert_id
  - severity
  - metric_name

  第二类：拓扑类参数

  需要一层转换

  - pod_name
  - instance_id
  - node_name
  - deployment_name

  这类通常不能直接从初始告警拿到，要二次查询。

  第三类：业务语义参数

  更依赖场景理解

  - root_cause_type
  - suspected_component
  - failure_stage

  这类先不要过早自动化，容易歧义。

  所以第一版你最适合先做的是：

  只解决"工具调用参数"层面的显式参数来源

  不要一下子扩展到抽象诊断结论。

  ---
  九、怎么避免歧义和混淆

  你自己已经意识到这一点了，这很关键。

  要避免反效果，核心有三条：

  1. memory 字段必须强语义命名

  不要用：

  - service
  - time
  - metric

  要用：

  - affected_services
  - root_cause_service
  - incident_start_time
  - anomalous_metrics

  2. 每个字段保留 provenance

  也就是来源信息：

  {
    "affected_services": {
      "value": ["payment-service"],
      "source_tool": "get_alerts",
      "source_step": 1,
      "confidence": 0.95
    }
  }

  这样后续如果冲突，你知道谁覆盖谁。

  3. fallback tool 不要太多

  每个参数最多 1-3 个候选来源就够了。
  来源一多，系统会变复杂，LLM 也容易乱。

  ---
  十、我给你的结论

  你的这个判断非常对，而且可以进一步总结成一句话：

  ▎ "修复 Executor 失忆"不能只靠注入 past_steps，还必须补上"参数来源知识"，否则 LLM 即使看到了历史结果，也不稳定地知道该从哪里取参数。

  所以完整方案应该是：

  A. 工作记忆

  存已经拿到的结构化参数，避免重复调用

  B. 参数来源注册表

  告诉系统：某个参数该从哪里拿，拿不到该补调哪个工具

  C. 结果提取器

  每次工具执行完，把关键字段写回工作记忆

  D. 参数解析层

  在真正调用工具前，先做参数补全和参数寻址

  ---
  十一、最推荐的落地顺序

  我建议你按这个顺序做，而不是一口气全做：

  第一步

  先定义 WorkingMemory 的字段

  第二步

  先定义 5-8 个最常用参数的 PARAM_SOURCE_REGISTRY

  第三步

  先给 3-5 个核心工具写结果提取逻辑
  比如：
  - get_alerts
  - get_metrics_anomalies
  - get_deployment_events
  - get_logs_by_service

  第四步

  在 executor 里加一个简化版参数解析层
  先只支持：
  - memory 命中直接填充
  - miss 时调用 fallback tool

  这个顺序最稳。

  ---
  你这一步实际上已经把问题看得比"修个上下文注入"更深了。你想解决的是 Agent 的参数感知能力，这确实才是根问题。

  下一步我建议我直接给你设计一版：

  1. WorkingMemory 数据结构
  2. PARAM_SOURCE_REGISTRY 结构
  3. executor 内部的参数解析流程

  这样你就能直接评估这套方案是否适合落到你现在这个代码里。