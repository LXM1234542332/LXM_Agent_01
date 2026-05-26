# AI Ops 运维功能完善计划

## 📋 需求分析

### 用户需求
当点击 AI Ops 之后，可以进行诊断，在必要的时候调用工具，最终给出当前系统存在的问题以及修复的建议。

### 现有架构分析

**已有的组件**：
1. ✅ FastAPI 应用框架
2. ✅ Plan-Execute-Replan 工作流（LangGraph）
3. ✅ Planner、Executor、Replanner 节点
4. ✅ MCP 客户端（用于调用工具）
5. ✅ 12 个诊断工具（Function Calling 格式）
6. ✅ 模拟数据（JSON 格式）

**缺失的部分**：
1. ❌ 诊断工具与 MCP 客户端的集成
2. ❌ 诊断工具的 MCP 服务器实现
3. ❌ Executor 中调用诊断工具的逻辑
4. ❌ 诊断结果的聚合和报告生成

---

## 🎯 实现方案

### 方案概述

```
用户点击 AI Ops
    ↓
Planner 制定诊断计划
    ↓
Executor 执行诊断步骤
    ├─ 调用诊断工具获取数据
    ├─ 分析数据
    └─ 记录结果
    ↓
Replanner 评估结果
    ├─ 判断是否需要继续诊断
    └─ 生成最终报告
    ↓
返回诊断结果和建议
```

### 实现步骤

#### 第 1 步：创建诊断工具的 MCP 服务器
**文件**：`mcp_servers/diagnostic_server.py`

**功能**：
- 将 12 个诊断工具暴露为 MCP 工具
- 支持 Executor 调用

**工具列表**：
- get_alerts
- get_error_logs
- get_logs_by_time_range
- get_logs_by_service
- get_logs_by_keyword
- get_metrics_by_name
- get_metrics_by_time_range
- get_metrics_anomalies
- get_events
- get_events_by_type
- get_events_by_time_range
- get_deployment_events

#### 第 2 步：修改 MCP 客户端
**文件**：`app/agent/mcp_client.py`

**修改内容**：
- 添加诊断工具的 MCP 服务器配置
- 支持动态加载诊断工具

#### 第 3 步：增强 Executor 节点
**文件**：`app/agent/aiops/executor.py`

**修改内容**：
- 调用诊断工具获取数据
- 处理工具返回结果
- 记录诊断过程

#### 第 4 步：优化 Replanner 节点
**文件**：`app/agent/aiops/replanner.py`

**修改内容**：
- 评估诊断结果
- 生成最终诊断报告
- 给出修复建议

#### 第 5 步：创建诊断提示词
**文件**：`app/agent/aiops/prompts.py`（新建）

**内容**：
- Planner 的诊断计划提示词
- Executor 的诊断执行提示词
- Replanner 的诊断报告提示词

#### 第 6 步：创建诊断报告生成器
**文件**：`app/services/diagnosis_report_generator.py`（新建）

**功能**：
- 聚合诊断数据
- 生成结构化报告
- 给出修复建议

---

## 📊 工作流详解

### Planner 阶段
**输入**：用户的诊断请求
**输出**：诊断计划（6-8 个步骤）

**示例计划**：
```
1. 获取所有告警事件
2. 获取错误日志并分析错误模式
3. 获取异常指标
4. 按时间范围获取日志，关联部署和错误
5. 获取部署事件，了解系统变化
6. 获取特定指标的时间序列，追踪问题演变
7. 按关键字搜索日志，查找具体错误信息
8. 综合分析，生成诊断报告
```

### Executor 阶段
**输入**：诊断计划
**输出**：诊断数据和分析结果

**执行流程**：
```
对于每个计划步骤：
  1. 调用相应的诊断工具
  2. 获取工具返回的数据
  3. 分析数据
  4. 记录结果
  5. 返回步骤完成事件
```

### Replanner 阶段
**输入**：诊断数据和分析结果
**输出**：最终诊断报告和建议

**生成流程**：
```
1. 聚合所有诊断数据
2. 分析数据之间的关联关系
3. 识别问题根源
4. 生成诊断报告
5. 给出修复建议
6. 返回完成事件
```

---

## 🔧 技术细节

### 诊断工具的 MCP 服务器实现

```python
# mcp_servers/diagnostic_server.py

from diagnostic_tools import DiagnosticDataTools, DIAGNOSTIC_TOOLS

class DiagnosticMCPServer:
    def __init__(self):
        self.tools = DiagnosticDataTools()
    
    def get_tools(self):
        """返回所有诊断工具定义"""
        return DIAGNOSTIC_TOOLS
    
    async def call_tool(self, tool_name: str, **kwargs):
        """调用诊断工具"""
        return self.tools.call_tool(tool_name, **kwargs)
```

### Executor 中的工具调用

```python
# app/agent/aiops/executor.py

async def executor(state: PlanExecuteState):
    """执行诊断步骤"""
    
    # 获取当前步骤
    current_step = state["plan"][0]
    
    # 调用 MCP 工具
    tool_result = await mcp_client.call_tool(
        tool_name=extract_tool_name(current_step),
        **extract_tool_params(current_step)
    )
    
    # 记录结果
    state["past_steps"].append({
        "step": current_step,
        "result": tool_result
    })
    
    # 移除已执行的步骤
    state["plan"] = state["plan"][1:]
    
    return state
```

### 诊断报告生成

```python
# app/services/diagnosis_report_generator.py

class DiagnosisReportGenerator:
    def generate_report(self, diagnosis_data):
        """生成诊断报告"""
        
        report = {
            "title": "系统诊断报告",
            "timestamp": datetime.now().isoformat(),
            "summary": self._generate_summary(diagnosis_data),
            "issues": self._identify_issues(diagnosis_data),
            "root_causes": self._analyze_root_causes(diagnosis_data),
            "recommendations": self._generate_recommendations(diagnosis_data)
        }
        
        return report
```

---

## 📈 预期效果

### 诊断流程
```
用户点击 AI Ops
    ↓ (1秒)
Planner 制定计划
    ↓ (显示计划)
Executor 执行诊断
    ├─ 获取告警 (1秒)
    ├─ 获取错误日志 (1秒)
    ├─ 获取异常指标 (1秒)
    ├─ 获取部署事件 (1秒)
    ├─ 关联数据 (1秒)
    └─ 分析结果 (1秒)
    ↓ (显示进度)
Replanner 生成报告
    ↓ (2秒)
返回诊断结果
```

### 诊断报告示例
```
# 系统诊断报告

## 📋 诊断摘要
- 发现问题数：1
- 严重程度：严重
- 诊断耗时：8秒

## 🚨 发现的问题

### 问题 1：数据库连接池耗尽
- **严重程度**：严重
- **影响服务**：user-service
- **首次发现**：2026-05-19T10:25:00Z
- **持续时间**：15 分钟

## 🔍 根因分析

### 根本原因
新版本 (v2.3.1) 中存在数据库连接泄漏

### 症状
- 数据库连接数从 30 增加到 101
- 连接池耗尽，新请求无法获取连接
- 请求延迟从 100ms 增加到 5000ms
- 错误率从 0.1% 增加到 15%

### 证据
- 部署时间：2026-05-19T10:15:00Z
- 首个错误：2026-05-19T10:25:12Z
- 时间差：10 分钟

## 💡 修复建议

### 立即措施
1. 回滚到 v2.3.0 ✓ (已执行)
2. 监控系统恢复情况

### 长期措施
1. 检查新版本中的数据库连接管理代码
2. 确保所有连接都被正确释放
3. 添加连接泄漏检测告警
4. 在测试环境中进行压力测试
```

---

## ⚠️ 注意事项

### 1. 工具调用的可靠性
- 需要处理工具调用失败的情况
- 需要实现重试机制
- 需要记录工具调用的日志

### 2. 数据的准确性
- 诊断工具返回的数据必须准确
- 需要验证数据的有效性
- 需要处理数据缺失的情况

### 3. 性能考虑
- 诊断过程可能比较耗时
- 需要优化工具调用的效率
- 需要实现缓存机制

### 4. 用户体验
- 需要实时显示诊断进度
- 需要清晰的诊断报告
- 需要易于理解的建议

---

## 📅 实现时间表

| 步骤 | 任务 | 预计时间 |
|------|------|---------|
| 1 | 创建诊断工具的 MCP 服务器 | 1-2 小时 |
| 2 | 修改 MCP 客户端 | 30 分钟 |
| 3 | 增强 Executor 节点 | 1-2 小时 |
| 4 | 优化 Replanner 节点 | 1-2 小时 |
| 5 | 创建诊断提示词 | 1 小时 |
| 6 | 创建诊断报告生成器 | 1-2 小时 |
| 7 | 测试和调试 | 2-3 小时 |
| **总计** | | **8-14 小时** |

---

## ✅ 验收标准

1. ✅ 点击 AI Ops 后能够进行诊断
2. ✅ 诊断过程中能够调用工具
3. ✅ 能够给出系统存在的问题
4. ✅ 能够给出修复的建议
5. ✅ 诊断报告清晰易懂
6. ✅ 诊断过程流畅无错误

---

## 🚀 开始实现

现在开始按照这个计划实现 AI Ops 运维功能的完善。

