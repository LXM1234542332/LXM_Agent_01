# Oncall Agent 改造计划

## 背景与现状

### 当前存在的问题

1. **知识库内容少、类别不足**
   - 目前只有 5 个文档：`cpu_high_usage.md`、`disk_high_usage.md`、`memory_high_usage.md`、`service_unavailable.md`、`slow_response.md`
   - 覆盖的运维场景有限

2. **没有真实的日志和监控数据**
   - `search_log` 只返回固定的 "正在同步元数据……" 日志
   - `query_cpu_metrics` 和 `query_memory_metrics` 返回简单的线性增长数据
   - 缺少告警列表工具，导致 AI Ops 无法正常运行

3. **MCP 工具不足**
   - 只有 7 个 MCP 工具
   - 缺少关键的 `get_active_alerts` 工具，LLM 会产生幻觉调用不存在的工具

4. **缺少对日志、监控数据格式的规定**
   - 日志格式不统一，内容过于简单
   - 监控数据缺少关键字段（进程信息、错误堆栈等）

5. **缺少网络检索能力**
   - LLM 只能依赖知识库和工具数据
   - 无法搜索网络上的相关案例辅助诊断

---

## 改造目标

1. 让 AI Ops 能正常运行并输出有意义的诊断报告
2. 让模拟数据"有剧情"，能支撑完整的诊断流程
3. 让知识库更丰富，RAG 检索效果更好
4. 验证 RAG 性能提升效果

---

## 分阶段改造计划

### 第一阶段：数据层改造（P0）

**目标**：让模拟数据"有剧情"，能支撑完整的诊断流程

#### 1.1 设计故障场景

设计 3 个典型故障场景，每个场景有完整的数据链：**告警 → 监控数据 → 日志**

| 场景 | 告警名称 | 受影响服务 | 现象 |
|------|---------|-----------|------|
| 场景 A | HighCPUUsage | data-sync-service | CPU 飙升到 95%，同时有大量 ERROR 日志 |
| 场景 B | HighMemoryUsage | data-sync-service | 内存使用率超过 70%，有 OOM 日志 |
| 场景 C | ServiceUnavailable | data-sync-service | 服务不可用，有连接超时日志 |

#### 1.2 改造 monitor_server.py

**新增工具**：

- `get_active_alerts`：获取当前活跃告警列表，返回模拟的告警数据
- `query_disk_metrics`：查询磁盘使用率
- `get_service_status`：查询服务运行状态（running/stopped/degraded）
- `get_process_info`：查询进程信息（CPU/内存占用、PID、启动时间）
- `get_alert_history`：查询历史告警记录

**改造现有工具**：

- `query_cpu_metrics`：数据改为有剧情（正常期 → 异常期），包含明确的告警触发信息
- `query_memory_metrics`：同上

#### 1.3 改造 cls_server.py

**新增工具**：

- `query_error_logs`：专门查询 ERROR 级别日志，不需要 topic_id，直接返回错误日志

**改造现有工具**：

- `search_log`：日志内容与故障场景匹配，包含 ERROR 日志、连接超时、OOM 等关键信息

#### 1.4 统一数据格式规范

**日志格式**：
```json
{
  "timestamp": "2026-05-19 10:30:00",
  "level": "ERROR",
  "service": "data-sync-service",
  "trace_id": "abc123",
  "message": "Connection timeout after 30s",
  "stack_trace": "..."
}
```

**监控数据格式**：
```json
{
  "timestamp": "2026-05-19 10:30:00",
  "value": 85.5,
  "unit": "percent",
  "threshold": 80.0,
  "alert_triggered": true
}
```

**告警数据格式**：
```json
{
  "alert_id": "alert-001",
  "alert_name": "HighCPUUsage",
  "severity": "critical",
  "service_name": "data-sync-service",
  "triggered_time": "2026-05-19 10:25:00",
  "duration_minutes": 5,
  "description": "CPU 使用率持续超过 80% 阈值"
}
```

---

### 第二阶段：Agent 层改造（P1）

**目标**：让 Agent 能正确使用工具，做出准确的诊断

#### 2.1 修改诊断任务描述

**文件**：`app/services/aiops_service.py`

修改 `aiops_task` 的内容，明确诊断流程：
1. 先调用 `get_active_alerts` 获取告警列表
2. 根据告警类型调用对应的监控工具
3. 查询相关日志
4. 综合分析生成报告

#### 2.2 增强 Planner 提示词

**文件**：`app/agent/aiops/planner.py`

- 明确告知 Planner：诊断流程的标准步骤
- 告知监控数据中 `alert_info` 字段包含告警信息
- 告知 `search_log` 工具需要整数毫秒时间戳

#### 2.3 增强 Executor 提示词

**文件**：`app/agent/aiops/executor.py`

- 明确工具使用规范（参数格式、注意事项）
- 告知如何从监控数据中提取告警信息
- 告知工具调用失败时的处理方式

---

### 第三阶段：知识库改造（P1）

**目标**：让知识库内容更丰富，覆盖更多场景，并生成测试集验证 RAG 效果

#### 3.1 扩充知识库文档

新增以下运维场景文档：

| 文档名 | 场景 |
|--------|------|
| `network_latency.md` | 网络延迟过高 |
| `database_connection_fail.md` | 数据库连接失败 |
| `container_oom.md` | 容器 OOM 被杀 |
| `service_dependency_timeout.md` | 服务依赖超时 |
| `disk_io_high.md` | 磁盘 IO 过高 |
| `pod_restart_loop.md` | Pod 频繁重启 |
| `gc_pressure.md` | JVM GC 压力过高 |
| `thread_pool_exhausted.md` | 线程池耗尽 |
| `load_balancer_unhealthy.md` | 负载均衡节点异常 |
| `certificate_expired.md` | 证书过期 |

每个文档格式与现有文档保持一致：告警名称、问题描述、排查步骤、常见原因、处理方案、验证步骤。

#### 3.2 生成测试集

生成 `计划/test_cases.md`，包含：

**A 类：在知识库中的问题（20 个）**
- 问题来自知识库文档的核心内容
- 预期：RAG 检索后 LLM 能给出准确答案
- 用于验证 RAG 检索有效性

**B 类：不在知识库中的问题（10 个）**
- 问题涉及知识库未覆盖的场景
- 预期：LLM 回答质量较差或明确说明不知道
- 补充知识库后，这些问题应变为 A 类

测试流程：
1. 测试 A 类问题 → 验证知识库有效
2. 测试 B 类问题 → 记录当前回答质量
3. 补充对应知识库文档
4. 重新测试 B 类问题 → 验证性能提升

---

### 第四阶段：MCP 工具扩展（P2）

**目标**：覆盖更多诊断场景

#### 4.1 新增本地工具

**文件**：`app/tools/`

- `search_web`（可选）：调用搜索 API（Tavily 或 SerpAPI），搜索网络上的相关案例

#### 4.2 新增 MCP 工具汇总

| 工具名 | 所在服务 | 用途 |
|--------|---------|------|
| `get_active_alerts` | monitor_server.py | 获取活跃告警列表（P0 已添加）|
| `query_disk_metrics` | monitor_server.py | 查询磁盘使用率 |
| `get_service_status` | monitor_server.py | 查询服务运行状态 |
| `get_process_info` | monitor_server.py | 查询进程信息 |
| `get_alert_history` | monitor_server.py | 查询历史告警记录 |
| `query_error_logs` | cls_server.py | 专门查询 ERROR 日志（P0 已添加）|
| `query_network_metrics` | monitor_server.py | 查询网络流量指标 |
| `search_web` | 本地工具 | 网络检索相关案例（可选）|

---

## 优先级汇总

| 优先级 | 任务 | 原因 |
|--------|------|------|
| P0 | 添加 `get_active_alerts` 工具 | 解决 AI Ops 无法运行的根本问题 |
| P0 | 添加 `query_error_logs` 工具 | 让日志查询有意义 |
| P0 | 改造模拟数据，让内容有剧情 | 让诊断有据可查 |
| P0 | 修改诊断任务描述和 Planner 提示词 | 让 Agent 正确使用工具 |
| P1 | 扩充知识库文档（10 篇） | 提升 RAG 检索质量 |
| P1 | 生成测试集 | 验证 RAG 性能提升效果 |
| P2 | 添加更多 MCP 工具 | 覆盖更多诊断场景 |
| P3 | 添加网络检索工具 | 锦上添花 |

---

## 执行顺序

```
第一步（P0）：数据层 + Agent 层
  ├─ 添加 get_active_alerts 工具
  ├─ 改造 search_log 日志内容
  ├─ 改造 CPU/内存监控数据
  ├─ 修改诊断任务描述
  └─ 增强 Planner/Executor 提示词
  → 验证：AI Ops 能正常运行并输出有意义的诊断报告

第二步（P1）：知识库层
  ├─ 生成 10 篇知识库文档
  ├─ 上传到向量数据库
  └─ 生成测试集（A 类 + B 类）
  → 验证：A 类问题回答质量高，B 类问题回答质量差

第三步（P1 续）：补充知识库 + 验证
  ├─ 针对 B 类问题补充对应文档
  ├─ 重新上传知识库
  └─ 重新测试 B 类问题
  → 验证：B 类问题回答质量提升

第四步（P2）：工具层扩展
  ├─ 添加更多 MCP 工具
  └─ 测试新工具在 AI Ops 中的效果

第五步（P3，可选）：网络检索
  └─ 添加 search_web 工具
```

---

## 备注

- 所有模拟数据应围绕同一个服务（`data-sync-service`）构建，保持场景一致性
- 知识库文档的排查步骤中，工具名称应与实际 MCP 工具名称一致
- 每个阶段完成后需要测试验证，再进入下一阶段
