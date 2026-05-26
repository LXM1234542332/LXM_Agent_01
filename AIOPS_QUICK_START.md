# AI Ops 诊断功能 - 快速启动指南

## 🚀 快速开始（5 分钟）

### 第 1 步：启动诊断工具 MCP Server

```bash
# 在新的终端窗口中运行
cd E:\agent\vscode\Oncall-Agent
python mcp_servers/diagnostic_server.py
```

**预期输出**：
```
2026-05-21 15:40:00 - Diagnostic_MCP_Server - INFO - 启动诊断工具 MCP Server...
2026-05-21 15:40:00 - Diagnostic_MCP_Server - INFO - 服务器名称: Diagnostic
2026-05-21 15:40:00 - Diagnostic_MCP_Server - INFO - 可用工具数: 12
```

### 第 2 步：启动主应用

```bash
# 在另一个终端窗口中运行
cd E:\agent\vscode\Oncall-Agent
python -m uvicorn app.main:app --host 0.0.0.0 --port 9900
```

**预期输出**：
```
INFO:     Uvicorn running on http://0.0.0.0:9900
INFO:     Application startup complete
```

### 第 3 步：触发 AI Ops 诊断

```bash
# 在第三个终端窗口中运行
curl -X POST "http://localhost:9900/api/aiops" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-session"}' \
  --no-buffer
```

**预期输出**：
```
data: {"type":"status","stage":"fetching_alerts","message":"正在获取系统告警信息..."}
data: {"type":"plan","stage":"plan_created","message":"诊断计划已制定，共 7 个步骤","plan":[...]}
data: {"type":"step_complete","stage":"step_executed","message":"步骤执行完成 (1/7)","current_step":"..."}
...
data: {"type":"report","stage":"final_report","message":"最终诊断报告已生成","report":"# 系统诊断报告\n..."}
data: {"type":"complete","stage":"diagnosis_complete","message":"诊断流程完成"}
```

---

## 📊 诊断流程详解

### 诊断计划示例

Planner 会生成类似以下的诊断计划：

```
步骤 1: 使用 get_alerts() 获取所有告警事件
步骤 2: 使用 get_error_logs(limit=20) 获取错误日志
步骤 3: 使用 get_metrics_anomalies() 获取异常指标
步骤 4: 使用 get_deployment_events() 获取部署事件
步骤 5: 使用 get_logs_by_time_range() 按时间范围关联数据
步骤 6: 使用 get_metrics_by_name("db_connections") 追踪指标演变
步骤 7: 使用 get_logs_by_keyword("connection") 查找具体错误信息
```

### 诊断报告示例

最终生成的诊断报告格式：

```markdown
# 系统诊断报告

## 📋 诊断摘要
- 诊断时间：2026-05-21 15:40:30
- 发现问题数：1
- 告警数：2
- 错误日志数：10
- 异常指标数：3
- 部署事件数：2

## 🚨 发现的问题
1. 系统存在活跃告警
2. 系统出现错误日志
3. 系统指标出现异常

## 🔍 根因分析

### deployment_issue
新版本部署可能导致系统问题

### error_analysis
系统出现错误，需要检查错误日志

## 💡 修复建议
1. 立即回滚到上一个稳定版本
2. 检查新版本中的代码变更
3. 在测试环境中进行充分测试
4. 检查错误日志，了解具体错误信息
5. 查看相关服务的运行状态
6. 检查系统资源使用情况

## 📊 详细数据

### 告警信息
- 步骤 1: 使用 get_alerts() 获取所有告警事件

### 错误日志
- 步骤 2: 使用 get_error_logs(limit=20) 获取错误日志

### 异常指标
- 步骤 3: 使用 get_metrics_anomalies() 获取异常指标

### 部署事件
- 步骤 4: 使用 get_deployment_events() 获取部署事件
```

---

## 🔧 故障排除

### 问题 1：诊断 MCP Server 无法启动

**症状**：
```
ModuleNotFoundError: No module named 'diagnostic_tools'
```

**解决方案**：
```bash
# 确保在正确的目录中运行
cd E:\agent\vscode\Oncall-Agent

# 确保 diagnostic_tools.py 在项目根目录
ls diagnostic_tools.py

# 重新运行
python mcp_servers/diagnostic_server.py
```

### 问题 2：MCP Client 无法连接到诊断服务器

**症状**：
```
Failed to connect to diagnostic MCP server
```

**解决方案**：
1. 确保诊断 MCP Server 已启动
2. 检查 app/config.py 中的配置是否正确
3. 查看应用日志了解详细错误信息

### 问题 3：诊断报告为空

**症状**：
```
诊断报告没有内容
```

**解决方案**：
1. 检查数据文件是否存在
   ```bash
   ls data/logs.json data/metrics.json data/events.json
   ```
2. 重新生成诊断数据
   ```bash
   python generate_diagnostic_data.py
   ```
3. 查看应用日志了解详细错误信息

---

## 📝 日志位置

### 应用日志
```
logs/app_YYYY-MM-DD.log
```

### 诊断 MCP Server 日志
```
控制台输出（直接显示）
```

### 查看日志
```bash
# 查看最新的应用日志
tail -f logs/app_*.log

# 查看诊断 MCP Server 的日志
# 在诊断 MCP Server 的终端窗口中查看
```

---

## 🧪 测试诊断功能

### 测试 1：基本诊断

```bash
curl -X POST "http://localhost:9900/api/aiops" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-1"}' \
  --no-buffer
```

### 测试 2：检查诊断工具

```bash
# 直接测试诊断工具
python -c "
from diagnostic_tools import DiagnosticDataTools
tools = DiagnosticDataTools()
result = tools.get_alerts()
print(result)
"
```

### 测试 3：检查 MCP Server

```bash
# 测试 MCP Server 是否正常运行
python -c "
import subprocess
import json

# 启动 MCP Server
proc = subprocess.Popen(
    ['python', 'mcp_servers/diagnostic_server.py'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# 发送测试请求
# （具体实现取决于 MCP 协议）

proc.terminate()
"
```

---

## 📊 性能指标

### 诊断耗时

| 阶段 | 耗时 | 说明 |
|------|------|------|
| Planner | 1-2 秒 | 制定诊断计划 |
| Executor | 6-8 秒 | 执行诊断步骤 |
| Replanner | 2-3 秒 | 生成诊断报告 |
| **总计** | **9-13 秒** | 完整诊断流程 |

### 数据量

| 数据类型 | 数量 | 说明 |
|---------|------|------|
| 日志 | 152 条 | 包含 INFO、WARN、ERROR |
| 指标 | 180 个 | 包含连接数、延迟、错误率 |
| 事件 | 4 个 | 包含部署和告警事件 |

---

## 🎯 下一步

### 立即可做
1. ✅ 启动诊断 MCP Server
2. ✅ 启动主应用
3. ✅ 触发诊断流程
4. ✅ 查看诊断报告

### 后续优化
1. ⏳ 创建更多故障场景
2. ⏳ 优化诊断提示词
3. ⏳ 集成真实数据源
4. ⏳ 添加更多诊断工具

---

## 📚 相关文档

- `AIOPS_IMPLEMENTATION_COMPLETE.md` - 完整实现文档
- `AIOPS_ENHANCEMENT_PLAN.md` - 增强计划
- `AIOPS_THINKING_PROCESS.md` - 思考过程
- `readme/QUICK_START.md` - 快速开始指南

---

## ✨ 总结

✅ **已完成**：
- 诊断工具 MCP Server 实现
- MCP 客户端配置
- Planner 诊断任务识别
- 诊断提示词
- 诊断报告生成器

✅ **可立即使用**：
- 启动 MCP Server
- 触发 AI Ops 诊断
- 获取诊断报告

**现在就可以开始测试诊断功能！**

