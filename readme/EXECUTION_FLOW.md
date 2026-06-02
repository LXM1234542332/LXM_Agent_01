# 运维 Agent 完整执行流程

## 【第一阶段】用户输入 → API 路由

### 1. 用户发送 HTTP 请求
```
POST /api/aiops
{
  "session_id": "session-123",
  "scenario_id": "scenario2"
}
```

### 2. API 路由处理 (app/api/aiops.py)
```python
# 第 124-130 行
session_id = request.session_id or "default"
scenario_id = request.scenario_id
logger.info(f"[会话 {session_id}] 收到 AIOps 诊断请求，场景: {scenario_id}")

async for event in aiops_service.diagnose(session_id=session_id, scenario_id=scenario_id):
    yield {"event": "message", "data": json.dumps(event, ensure_ascii=False)}
```

**作用**：
- 解析请求参数
- 提取 session_id 和 scenario_id
- 调用诊断服务

---

## 【第二阶段】诊断服务初始化

### 3. aiops_service.diagnose() 方法 (app/services/aiops_service.py)
```python
# 第 218-236 行
async def diagnose(self, session_id: str = "default", scenario_id: Optional[str] = None):
    # 生成诊断任务描述
    aiops_task = "诊断当前系统是否存在告警，如果存在告警请详细分析告警原因并生成诊断报告"
    
    # 调用 execute 方法
    async for event in self.execute(aiops_task, session_id, scenario_id or ""):
        # 处理事件
        if event.get("type") == "complete":
            report = event.get("response", "")
            # 保存报告到文件
            if scenario_id:
                saved_path = self._save_report(report, scenario_id)
            yield event
```

**作用**：
- 生成诊断任务描述
- 调用 execute() 方法执行 Plan-Execute-Replan 流程
- 保存诊断报告

---

## 【第三阶段】场景初始化（关键！）

### 4. execute() 方法 - 第一步：初始化场景 (app/services/aiops_service.py)
```python
# 第 111-155 行
async def execute(self, user_input: str, session_id: str = "default", scenario_id: str = ""):
    # 如果指定了场景ID，先初始化场景数据
    if scenario_id:
        logger.info(f"[会话 {session_id}] 初始化场景: {scenario_id}")
        try:
            # 导入全局 diagnostic_tools 实例
            import diagnostic_tools as dt_module
            
            # 切换场景
            dt_module.diagnostic_tools.switch_scenario(scenario_id)
            logger.info(f"[会话 {session_id}] 场景初始化完成: {scenario_id}")
        except Exception as e:
            logger.error(f"[会话 {session_id}] 场景初始化失败: {e}")
```

**关键点**：
- 导入全局 diagnostic_tools 实例
- 调用 switch_scenario() 切换场景
- 重新加载该场景的所有数据

### 5. diagnostic_tools.switch_scenario() (diagnostic_tools.py)
```python
# 第 380-387 行
def switch_scenario(self, scenario_id: str):
    """动态切换场景"""
    self.scenario_id = scenario_id
    self.scenario_dir = self.data_dir / scenario_id
    
    # 重新加载新场景的数据
    self.logs = self._load_logs()           # 加载 data/scenario2/logs.json
    self.metrics = self._load_metrics()     # 加载 data/scenario2/metrics.json
    self.events = self._load_events()       # 加载 data/scenario2/events.json
    self.traces = self._load_traces()       # 加载 data/scenario2/traces.json
```

**作用**：
- 更新 scenario_id
- 更新 scenario_dir 路径
- 重新加载该场景的所有 JSON 数据到内存

---

## 【第四阶段】初始化状态

### 6. execute() 方法 - 第二步：初始化状态
```python
# 第 157-165 行
initial_state: PlanExecuteState = {
    "input": "诊断当前系统是否存在告警...",
    "scenario_id": "scenario2",
    "plan": [],
    "past_steps": [],
    "response": ""
}

config_dict = {
    "configurable": {
        "thread_id": "session-123"
    }
}
```

**作用**：
- 创建初始状态对象
- 配置工作流参数（session_id）

---

## 【第五阶段】Planner 节点执行

### 7. Planner 节点 (app/agent/aiops/planner.py)
```python
# 第 27-115 行
async def planner(state: PlanExecuteState) -> Dict[str, Any]:
    logger.info("=== Planner：制定执行计划 ===")
    
    input_text = state.get("input", "")
    logger.info(f"用户输入: {input_text}")
    
    # 第一步：获取 MCP 工具列表
    mcp_client = await get_mcp_client_with_retry()
    mcp_tools = await mcp_client.get_tools()
    tools_description = format_tools_description(mcp_tools)
    logger.info(f"获取到 {len(mcp_tools)} 个 MCP 工具")
    
    # 第二步：构建 Planner 提示词
    prompt = ChatPromptTemplate.from_messages([
        ("system", PLANNER_SYSTEM_PROMPT),
        ("placeholder", "{messages}"),
    ])
    
    # 第三步：调用 LLM 制定计划
    llm = ChatQwen(model="qwen-max", temperature=0)
    planner_chain = prompt | llm.with_structured_output(Plan, include_raw=True)
    
    raw_result = await planner_chain.ainvoke({
        "messages": [("user", input_text)],
        "tools_description": tools_description,
    })
    
    # 第四步：解析 LLM 返回的计划
    plan_result = raw_result.get("parsed")
    plan_steps = plan_result.steps
    
    logger.info(f"计划已生成，共 {len(plan_steps)} 个步骤")
    for i, step in enumerate(plan_steps, 1):
        logger.info(f"  步骤 {i}: {step}")
    
    return {"plan": plan_steps}
```

**关键点**：
- 获取 MCP 工具列表（此时工具已连接到 MCP 服务器）
- 构建 Planner 提示词，注入工具描述
- 调用 LLM（Qwen）制定诊断计划
- LLM 返回步骤列表

**LLM 生成的计划示例**：
```
[
  "调用 get_alerts() - 获取当前系统中的所有告警",
  "调用 get_error_logs(limit=30) - 获取最近的错误日志",
  "调用 get_metrics_anomalies() - 获取异常指标",
  "调用 get_logs_by_service(service=根据告警确定的服务名, level=ERROR) - 深入分析受影响服务的错误日志",
  ...
]
```

---

## 【第六阶段】Executor 节点执行（循环）

### 8. Executor 节点 (app/agent/aiops/executor.py)
```python
# 第 27-120 行
async def executor(state: PlanExecuteState) -> Dict[str, Any]:
    logger.info("=== Executor：执行诊断步骤 ===")
    
    # 第一步：获取当前步骤
    plan = state.get("plan", [])
    past_steps = state.get("past_steps", [])
    current_step_index = len(past_steps)
    
    if current_step_index >= len(plan):
        logger.info("所有步骤已执行")
        return {"past_steps": past_steps}
    
    current_step = plan[current_step_index]
    logger.info(f"执行步骤 {current_step_index + 1}/{len(plan)}: {current_step}")
    
    # 第二步：构建 Executor 提示词
    prompt = ChatPromptTemplate.from_messages([
        ("system", EXECUTOR_SYSTEM_PROMPT),
        ("placeholder", "{messages}"),
    ])
    
    # 第三步：调用 LLM 执行步骤
    llm = ChatQwen(model="qwen-max", temperature=0)
    mcp_client = await get_mcp_client_with_retry()
    mcp_tools = await mcp_client.get_tools()
    
    # 绑定 MCP 工具
    llm_with_tools = llm.bind_tools(mcp_tools)
    
    executor_chain = prompt | llm_with_tools
    
    # 构建消息
    messages = [
        ("user", f"当前步骤: {current_step}\n\n已执行步骤结果:\n{format_past_steps(past_steps)}")
    ]
    
    # 调用 LLM
    result = await executor_chain.ainvoke({"messages": messages})
    
    # 第四步：处理 LLM 的工具调用
    if result.tool_calls:
        tool_call = result.tool_calls[0]
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        
        logger.info(f"LLM 调用工具: {tool_name}({tool_args})")
        
        # 第五步：调用 MCP 工具
        tool_result = await mcp_client.call_tool(tool_name, tool_args)
        
        logger.info(f"工具返回结果: {tool_result}")
        
        # 第六步：记录执行结果
        past_steps.append((current_step, tool_result))
    
    return {"past_steps": past_steps}
```

**关键点**：
- 获取当前步骤
- 构建 Executor 提示词
- 调用 LLM，绑定 MCP 工具
- LLM 通过 Function Calling 调用工具
- 调用 MCP 工具获取数据
- 记录执行结果

### 9. MCP 工具执行 (mcp_servers/diagnostic_server.py)
```python
# 第 96-124 行
@mcp.tool()
@log_tool_call
def get_alerts() -> Dict[str, Any]:
    """获取所有告警事件。用于发现系统中存在的问题。"""
    try:
        # 调用 diagnostic_tools 实例的方法
        result = diagnostic_tools.get_alerts()
        return result
    except Exception as e:
        return {
            "status": "error",
            "message": f"获取告警失败: {str(e)}"
        }
```

### 10. diagnostic_tools.get_alerts() (diagnostic_tools.py)
```python
# 第 389-398 行
def get_alerts(self) -> Dict[str, Any]:
    """获取所有告警事件"""
    # 从 self.events 中过滤告警
    # self.events 是 scenario2 的数据（在第 5 步中加载）
    alerts = [e for e in self.events if e.get("event_type") == "alert"]
    alerts = sorted(alerts, key=lambda x: x["timestamp"], reverse=True)
    
    return {
        "status": "success",
        "count": len(alerts),
        "data": alerts
    }
```

**返回结果示例**：
```json
{
  "status": "success",
  "count": 3,
  "data": [
    {
      "event_type": "alert",
      "service": "user-service",
      "message": "内存使用率超过 90%",
      "timestamp": "2026-05-31T10:30:00Z"
    },
    {
      "event_type": "alert",
      "service": "api-gateway",
      "message": "请求延迟超过 5s",
      "timestamp": "2026-05-31T10:29:00Z"
    },
    ...
  ]
}
```

---

## 【第七阶段】Replanner 节点执行

### 11. Replanner 节点 (app/agent/aiops/replanner.py)
```python
# 第 27-120 行
async def replanner(state: PlanExecuteState) -> Dict[str, Any]:
    logger.info("=== Replanner：决策下一步 ===")
    
    # 第一步：分析已执行步骤的结果
    past_steps = state.get("past_steps", [])
    plan = state.get("plan", [])
    
    logger.info(f"已执行步骤数: {len(past_steps)}")
    logger.info(f"剩余步骤数: {len(plan) - len(past_steps)}")
    
    # 第二步：构建 Replanner 提示词
    prompt = ChatPromptTemplate.from_messages([
        ("system", REPLANNER_SYSTEM_PROMPT),
        ("placeholder", "{messages}"),
    ])
    
    # 第三步：调用 LLM 做出决策
    llm = ChatQwen(model="qwen-max", temperature=0)
    replanner_chain = prompt | llm.with_structured_output(Decision, include_raw=True)
    
    messages = [
        ("user", f"已执行步骤:\n{format_past_steps(past_steps)}\n\n剩余计划:\n{format_plan(plan[len(past_steps):])}")
    ]
    
    result = await replanner_chain.ainvoke({"messages": messages})
    decision = result.get("parsed")
    
    logger.info(f"Replanner 决策: {decision.action}")
    
    # 第四步：根据决策返回结果
    if decision.action == "respond":
        logger.info("决策：结束诊断，生成最终报告")
        return {"action": "respond"}
    
    elif decision.action == "continue":
        logger.info("决策：继续执行下一个步骤")
        return {"action": "continue"}
    
    elif decision.action == "replan":
        logger.info("决策：重新规划")
        new_plan = decision.new_plan
        return {"action": "replan", "plan": new_plan}
```

**Replanner 的三种决策**：
1. **respond**：结束诊断，生成最终报告
   - 触发条件：已找到根本原因 OR 已执行步骤数 >= 5 OR 剩余计划为空
   
2. **continue**：继续执行下一个步骤
   - 触发条件：尚未找到根本原因 AND 剩余计划中的下一步能提供关键信息 AND 已执行步骤数 < 5
   
3. **replan**：重新规划
   - 触发条件：原计划明显不适合当前情况 AND 新计划步骤数 <= 剩余步骤数

---

## 【第八阶段】循环控制

### 12. 根据 Replanner 的决策进行循环
```
如果 continue：
  └─ 回到第六阶段，Executor 执行下一个步骤

如果 replan：
  └─ 回到第五阶段，Planner 重新制定计划

如果 respond：
  └─ 进入第九阶段，生成最终报告
```

---

## 【第九阶段】生成最终报告

### 13. 报告生成 (app/agent/aiops/reporter.py)
```python
# 第 27-120 行
async def reporter(state: PlanExecuteState) -> Dict[str, Any]:
    logger.info("=== Reporter：生成最终报告 ===")
    
    # 第一步：收集所有执行结果
    past_steps = state.get("past_steps", [])
    
    logger.info(f"收集 {len(past_steps)} 个步骤的执行结果")
    
    # 第二步：构建报告生成提示词
    prompt = ChatPromptTemplate.from_messages([
        ("system", REPORT_SYSTEM_PROMPT),
        ("placeholder", "{messages}"),
    ])
    
    # 第三步：调用 LLM 生成报告
    llm = ChatQwen(model="qwen-max", temperature=0)
    reporter_chain = prompt | llm
    
    messages = [
        ("user", f"根据以下诊断数据生成最终报告:\n\n{format_past_steps(past_steps)}")
    ]
    
    result = await reporter_chain.ainvoke({"messages": messages})
    report = result.content
    
    logger.info("报告生成完成")
    
    return {"response": report}
```

**LLM 生成的报告示例**：
```markdown
# 系统诊断报告

**诊断时间**：2026-05-31 10:30:00
**诊断状态**：已完成

## 一、告警概览

| 告警名称 | 级别 | 受影响服务 | 触发时间 |
|---------|------|----------|---------|
| 内存使用率超过 90% | HIGH | user-service | 2026-05-31T10:30:00Z |
| 请求延迟超过 5s | MEDIUM | api-gateway | 2026-05-31T10:29:00Z |

共发现 2 个告警。

## 二、根因分析

### 2.1 问题描述
user-service 内存泄漏导致内存使用率持续上升，最终超过 90% 触发告警。

### 2.2 问题链条
```
部署新版本 → 内存泄漏 → 内存使用率上升 → 超过 90% → 触发告警
```

### 2.3 关键证据

**日志证据：**
- ERROR: java.lang.OutOfMemoryError: Java heap space
- ERROR: Failed to allocate memory for object

**指标证据：**
| 指标名称 | 异常值 | 正常值 | 异常时间 |
|---------|-------|-------|---------|
| memory_usage | 92% | 60% | 2026-05-31T10:30:00Z |
| gc_time | 5000ms | 100ms | 2026-05-31T10:30:00Z |

**事件证据：**
- 2026-05-31T10:00:00Z: 部署新版本 v2.1.0
- 2026-05-31T10:15:00Z: 内存使用率开始上升
- 2026-05-31T10:30:00Z: 内存使用率超过 90%，触发告警

## 三、处理建议

### 3.1 立即处理
1. 回滚到上一个版本 v2.0.9
2. 重启 user-service
3. 监控内存使用率恢复情况

### 3.2 短期处理（24小时内）
1. 修复内存泄漏问题
2. 增加内存监控告警阈值
3. 进行压力测试

### 3.3 长期优化
1. 实施代码审查流程
2. 增加内存泄漏检测工具
3. 定期进行性能优化

## 四、风险评估

| 评估项 | 结果 |
|-------|------|
| 当前风险等级 | 高 |
| 受影响服务 | user-service |
| 是否已恢复 | 否 |
| 建议处理优先级 | 立即 |
```

---

## 【第十阶段】保存报告并返回

### 14. 保存报告到文件
```python
# app/services/aiops_service.py
saved_path = self._save_report(report, scenario_id)
# 报告路径：reports/scenario2/report_<timestamp>.md
```

### 15. API 返回响应给用户
```python
# 通过 SSE 流式返回事件
yield {
    "type": "complete",
    "stage": "diagnosis_complete",
    "message": "诊断流程完成",
    "diagnosis": {
        "status": "completed",
        "report": report,
        "saved_path": saved_path
    }
}
```

---

## 完整的数据流总结

```
输入：scenario_id = "scenario2"
  ↓
【第三阶段】场景初始化
  diagnostic_tools.switch_scenario("scenario2")
  ├─ 加载 data/scenario2/logs.json
  ├─ 加载 data/scenario2/metrics.json
  ├─ 加载 data/scenario2/events.json
  └─ 加载 data/scenario2/traces.json
  ↓
【第五阶段】Planner 制定计划
  使用 scenario2 的数据作为上下文
  ├─ 看到 scenario2 的告警
  ├─ 看到 scenario2 的错误日志
  └─ 制定针对 scenario2 的诊断计划
  ↓
【第六阶段】Executor 执行计划（循环）
  所有工具调用都使用 scenario2 的数据
  ├─ get_alerts() → scenario2 的告警
  ├─ get_error_logs() → scenario2 的错误日志
  ├─ get_metrics_by_name() → scenario2 的指标
  └─ ...
  ↓
【第七阶段】Replanner 决策
  根据已执行步骤的结果决定下一步
  ├─ continue → 回到第六阶段
  ├─ replan → 回到第五阶段
  └─ respond → 进入第九阶段
  ↓
【第九阶段】生成最终报告
  基于 scenario2 的完整数据生成诊断报告
  ↓
输出：诊断报告（Markdown 格式）
```

---

## 关键文件和函数对应关系

| 阶段 | 文件 | 函数 | 作用 |
|-----|------|------|------|
| 第一阶段 | app/api/aiops.py | diagnose_stream() | API 路由，解析请求 |
| 第二阶段 | app/services/aiops_service.py | diagnose() | 诊断接口 |
| 第三阶段 | app/services/aiops_service.py | execute() | 初始化场景 |
| 第三阶段 | diagnostic_tools.py | switch_scenario() | 切换场景，加载数据 |
| 第五阶段 | app/agent/aiops/planner.py | planner() | 制定计划 |
| 第六阶段 | app/agent/aiops/executor.py | executor() | 执行步骤 |
| 第六阶段 | mcp_servers/diagnostic_server.py | get_alerts() 等 | MCP 工具实现 |
| 第六阶段 | diagnostic_tools.py | get_alerts() 等 | 数据访问逻辑 |
| 第七阶段 | app/agent/aiops/replanner.py | replanner() | 决策下一步 |
| 第九阶段 | app/agent/aiops/reporter.py | reporter() | 生成报告 |

---

## 核心概念

### 1. 全局实例 (diagnostic_tools)
- 在 diagnostic_tools.py 末尾创建
- 被 MCP 服务器导入使用
- 被 execute() 方法修改（切换场景）
- 所有工具调用都通过它

### 2. 场景切换
- 在 Planner 执行之前完成
- 通过 switch_scenario() 方法
- 重新加载该场景的所有数据
- 确保后续工具调用使用正确的数据

### 3. Plan-Execute-Replan 循环
- Planner：制定诊断计划
- Executor：执行单个步骤
- Replanner：决策下一步（continue/replan/respond）
- 循环直到 Replanner 决策 respond

### 4. MCP 工具
- 由 MCP 服务器提供
- 通过 Function Calling 被 LLM 调用
- 实现在 diagnostic_tools.py 中
- 使用全局 diagnostic_tools 实例的数据
