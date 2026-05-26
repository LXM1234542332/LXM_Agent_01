# AI Ops 运维功能完善 - 实现完成

## ✅ 已完成的工作

### 第 1 阶段：基础集成（已完成）

#### 1.1 创建诊断工具的 MCP Server ✅
**文件**：`mcp_servers/diagnostic_server.py`

**实现内容**：
- ✅ 使用 FastMCP 框架创建 MCP Server
- ✅ 暴露 12 个诊断工具作为 MCP 工具
- ✅ 实现工具调用日志记录
- ✅ 支持 stdio 通信方式

**工具列表**：
```
日志工具（4 个）：
  - get_error_logs()
  - get_logs_by_time_range()
  - get_logs_by_service()
  - get_logs_by_keyword()

指标工具（3 个）：
  - get_metrics_by_name()
  - get_metrics_by_time_range()
  - get_metrics_anomalies()

事件工具（5 个）：
  - get_alerts()
  - get_events()
  - get_events_by_type()
  - get_events_by_time_range()
  - get_deployment_events()
```

#### 1.2 修改 MCP 客户端配置 ✅
**文件**：`app/config.py`

**修改内容**：
- ✅ 添加诊断工具的 MCP 服务器配置
- ✅ 配置 stdio 传输方式
- ✅ 配置诊断服务器启动命令

**配置示例**：
```python
mcp_diagnostic_transport: str = "stdio"
mcp_diagnostic_command: str = "python mcp_servers/diagnostic_server.py"

# 在 mcp_servers 属性中添加
"diagnostic": {
    "transport": self.mcp_diagnostic_transport,
    "command": self.mcp_diagnostic_command,
}
```

### 第 2 阶段：工作流增强（已完成）

#### 2.1 Executor 节点 ✅
**文件**：`app/agent/aiops/executor.py`

**现有功能**：
- ✅ 已支持 MCP 工具调用
- ✅ 自动执行工具调用
- ✅ 处理工具返回结果
- ✅ 记录执行过程

**无需修改**：Executor 已经支持通过 MCP Client 调用诊断工具

#### 2.2 Planner 节点 ✅
**文件**：`app/agent/aiops/planner.py`

**修改内容**：
- ✅ 添加诊断任务识别逻辑
- ✅ 导入诊断提示词
- ✅ 根据任务类型选择合适的提示词
- ✅ 为诊断任务生成专用计划

**关键改进**：
```python
def _is_diagnostic_task(input_text: str) -> bool:
    """判断是否是诊断任务"""
    diagnostic_keywords = [
        "诊断", "diagnosis", "问题", "issue", "告警", "alert",
        "错误", "error", "故障", "fault", "分析", "analyze",
        "根因", "root cause", "aiops"
    ]
    # ...
```

### 第 3 阶段：报告生成（已完成）

#### 3.1 诊断提示词 ✅
**文件**：`app/agent/aiops/prompts.py`

**包含内容**：
- ✅ Planner 诊断提示词（7-8 个诊断步骤）
- ✅ Executor 诊断执行提示词
- ✅ Replanner 诊断报告提示词
- ✅ 最终响应生成提示词

**诊断步骤**：
```
1. 获取所有告警事件
2. 获取错误日志并分析错误模式
3. 获取异常指标
4. 获取部署事件
5. 按时间范围关联数据
6. 追踪指标演变
7. 查找具体错误信息
8. 综合分析生成报告
```

#### 3.2 诊断报告生成器 ✅
**文件**：`app/services/diagnosis_report_generator.py`

**功能**：
- ✅ 聚合诊断数据
- ✅ 识别系统问题
- ✅ 分析根本原因
- ✅ 生成修复建议
- ✅ 格式化 Markdown 报告

**报告结构**：
```
# 系统诊断报告

## 📋 诊断摘要
- 诊断时间
- 发现问题数
- 告警数、错误数、异常数

## 🚨 发现的问题
- 问题列表

## 🔍 根因分析
- 根本原因分析

## 💡 修复建议
- 立即措施
- 长期措施

## 📊 详细数据
- 告警信息
- 错误日志
- 异常指标
- 部署事件
```

---

## 🏗️ 架构设计

### 诊断流程

```
用户点击 AI Ops
    ↓
Planner 制定诊断计划
    ├─ 识别诊断任务
    ├─ 使用诊断提示词
    └─ 生成 7-8 个诊断步骤
    ↓
Executor 执行诊断步骤
    ├─ 调用 MCP Client
    ├─ MCP Client 调用诊断 MCP Server
    ├─ 诊断 MCP Server 调用诊断工具
    └─ 返回诊断数据
    ↓
Replanner 评估结果
    ├─ 判断是否需要继续诊断
    └─ 生成最终诊断报告
    ↓
返回诊断结果给用户
```

### MCP 架构

```
┌─────────────────────────────────────────┐
│         FastAPI 应用                     │
│  ┌───────────────────────────────────┐  │
│  │      MCP Client                   │  │
│  │  (MultiServerMCPClient)           │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
         ↕ MCP 协议（stdio）
┌─────────────────────────────────────────┐
│    诊断工具 MCP Server                   │
│  (mcp_servers/diagnostic_server.py)     │
│  ┌───────────────────────────────────┐  │
│  │  12 个诊断工具                    │  │
│  │  - 日志工具（4 个）               │  │
│  │  - 指标工具（3 个）               │  │
│  │  - 事件工具（5 个）               │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
         ↕ 本地调用
┌─────────────────────────────────────────┐
│    诊断数据工具                          │
│  (diagnostic_tools.py)                  │
│  ┌───────────────────────────────────┐  │
│  │  JSON 数据文件                    │  │
│  │  - logs.json                      │  │
│  │  - metrics.json                   │  │
│  │  - events.json                    │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

---

## 📁 文件清单

### 新创建的文件

```
mcp_servers/
├── diagnostic_server.py              # 诊断工具 MCP Server

app/agent/aiops/
├── prompts.py                        # 诊断提示词

app/services/
├── diagnosis_report_generator.py     # 诊断报告生成器
```

### 修改的文件

```
app/config.py                         # 添加诊断 MCP 服务器配置
app/agent/aiops/planner.py           # 添加诊断任务识别和诊断提示词
```

### 无需修改的文件

```
app/agent/aiops/executor.py          # 已支持 MCP 工具调用
app/agent/aiops/replanner.py         # 已支持生成最终响应
app/agent/mcp_client.py              # 已支持多服务器 MCP 客户端
```

---

## 🚀 使用方式

### 启动诊断工具 MCP Server

```bash
# 方式 1：直接运行
python mcp_servers/diagnostic_server.py

# 方式 2：通过 MCP Client 自动启动
# MCP Client 会根据配置自动启动诊断服务器
```

### 触发 AI Ops 诊断

```bash
# 通过 API 触发诊断
curl -X POST "http://localhost:9900/api/aiops" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "session-123"}' \
  --no-buffer
```

### 诊断流程示例

```
用户请求：诊断系统中存在的问题

Planner 生成计划：
  1. 获取所有告警事件
  2. 获取错误日志
  3. 获取异常指标
  4. 获取部署事件
  5. 按时间范围关联数据
  6. 追踪指标演变
  7. 查找具体错误信息
  8. 综合分析生成报告

Executor 执行步骤：
  ✓ 步骤 1：发现 2 个告警
  ✓ 步骤 2：发现 10 条错误日志
  ✓ 步骤 3：发现 3 个异常指标
  ✓ 步骤 4：发现 2 个部署事件
  ✓ 步骤 5：关联部署和错误
  ✓ 步骤 6：追踪指标变化
  ✓ 步骤 7：查找具体错误
  ✓ 步骤 8：生成诊断报告

Replanner 生成报告：
  # 系统诊断报告
  
  ## 诊断摘要
  - 发现问题数：1
  - 严重程度：严重
  
  ## 发现的问题
  - 数据库连接池耗尽
  
  ## 根因分析
  - 新版本 v2.3.1 中存在连接泄漏
  
  ## 修复建议
  - 立即回滚到 v2.3.0
  - 检查连接管理代码
```

---

## ✨ 关键特性

### 1. 完整的诊断工具集
- ✅ 12 个诊断工具
- ✅ 覆盖日志、指标、事件三个维度
- ✅ 支持多种查询方式

### 2. 智能诊断流程
- ✅ 自动识别诊断任务
- ✅ 生成专用诊断计划
- ✅ 逐步执行诊断步骤
- ✅ 自动生成诊断报告

### 3. 灵活的 MCP 架构
- ✅ 本地 MCP Server
- ✅ 支持 stdio 通信
- ✅ 易于扩展到远端
- ✅ 与现有系统一致

### 4. 清晰的诊断报告
- ✅ Markdown 格式
- ✅ 结构化内容
- ✅ 包含证据支持
- ✅ 给出具体建议

---

## 🧪 测试建议

### 1. 单元测试
```bash
# 测试诊断工具 MCP Server
python -m pytest tests/test_diagnostic_server.py

# 测试诊断报告生成器
python -m pytest tests/test_diagnosis_report_generator.py
```

### 2. 集成测试
```bash
# 测试完整的诊断流程
python -m pytest tests/test_aiops_diagnostic_flow.py
```

### 3. 手动测试
```bash
# 启动应用
python -m uvicorn app.main:app --host 0.0.0.0 --port 9900

# 触发诊断
curl -X POST "http://localhost:9900/api/aiops" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test"}' \
  --no-buffer
```

---

## 📊 预期效果

### 诊断耗时
```
Planner 制定计划：1-2 秒
Executor 执行诊断：6-8 秒
  ├─ 获取告警：1 秒
  ├─ 获取错误日志：1 秒
  ├─ 获取异常指标：1 秒
  ├─ 获取部署事件：1 秒
  ├─ 关联数据：1 秒
  └─ 分析结果：1 秒
Replanner 生成报告：2-3 秒
总耗时：9-13 秒
```

### 诊断准确性
- ✅ 能够识别系统中的告警
- ✅ 能够找到错误日志
- ✅ 能够发现异常指标
- ✅ 能够关联部署和问题
- ✅ 能够分析根本原因
- ✅ 能够给出修复建议

---

## 🎯 下一步

### 立即可做
1. ✅ 启动诊断工具 MCP Server
2. ✅ 测试诊断流程
3. ✅ 验证诊断报告

### 后续优化
1. ⏳ 添加更多诊断工具
2. ⏳ 创建更多故障场景
3. ⏳ 优化诊断提示词
4. ⏳ 集成真实数据源

---

## 📝 总结

✅ **已完成**：
- 创建诊断工具的 MCP Server
- 修改 MCP 客户端配置
- 增强 Planner 节点
- 创建诊断提示词
- 创建诊断报告生成器

✅ **架构完整**：
- 诊断工具与 MCP 集成
- 诊断流程自动化
- 诊断报告生成

✅ **可立即使用**：
- 启动 MCP Server
- 触发 AI Ops 诊断
- 获取诊断报告

**所有工作已完成，可以立即开始测试！**

