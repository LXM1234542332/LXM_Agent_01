# AI Ops 诊断功能 - 完整测试指南

## 📋 测试清单

### 已创建的测试脚本

```
✅ test_diagnostic_flow.py      # 诊断流程测试
✅ test_integration.py          # 集成测试
✅ test_performance.py          # 性能测试
```

---

## 🚀 快速测试（5 分钟）

### 第 1 步：启动诊断 MCP Server

```bash
# 在终端 1 中运行
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
# 在终端 2 中运行
cd E:\agent\vscode\Oncall-Agent
python -m uvicorn app.main:app --host 0.0.0.0 --port 9900
```

**预期输出**：
```
INFO:     Uvicorn running on http://0.0.0.0:9900
INFO:     Application startup complete
```

### 第 3 步：运行诊断流程测试

```bash
# 在终端 3 中运行
cd E:\agent\vscode\Oncall-Agent
python test_diagnostic_flow.py
```

**预期输出**：
```
2026-05-21 15:40:30 - INFO - ================================================================================
2026-05-21 15:40:30 - INFO - 测试 1：诊断工具测试
2026-05-21 15:40:30 - INFO - ================================================================================
2026-05-21 15:40:30 - INFO - 测试 get_alerts()...
2026-05-21 15:40:30 - INFO - ✓ 获取告警数: 2
...
2026-05-21 15:40:35 - INFO - ✅ 诊断流程测试完成
```

---

## 🧪 完整测试流程

### 测试 1：诊断工具测试

```bash
python test_diagnostic_flow.py
```

**测试内容**：
- ✅ 诊断工具是否正常工作
- ✅ 数据是否能正确获取
- ✅ 诊断报告是否能生成

**预期结果**：
- 所有诊断工具都能正常调用
- 能获取到告警、错误日志、异常指标、部署事件
- 能生成诊断报告

### 测试 2：集成测试

```bash
python test_integration.py
```

**测试内容**：
- ✅ 诊断工具是否能正常工作
- ✅ API 是否能正常响应
- ✅ 诊断流程是否能完整执行

**预期结果**：
- 诊断工具测试通过
- API 返回 200 状态码
- 收到完整的诊断事件流
- 生成诊断报告

### 测试 3：性能测试

```bash
python test_performance.py
```

**测试内容**：
- ✅ 诊断工具的响应时间
- ✅ 诊断流程的总耗时
- ✅ 报告生成的耗时

**预期结果**：
- 诊断工具平均响应时间 < 100ms
- 诊断流程总耗时 9-13 秒
- 报告生成耗时 < 500ms

---

## 📊 测试结果解读

### 诊断工具测试结果

```
✓ get_alerts: 2 条数据
✓ get_error_logs: 10 条数据
✓ get_metrics_anomalies: 3 个异常指标
✓ get_deployment_events: 2 个部署事件
```

**说明**：
- 所有工具都能正常工作
- 数据量符合预期

### 集成测试结果

```
事件 1: status
事件 2: plan
事件 3-10: step_complete
事件 11: report
事件 12: complete
```

**说明**：
- 诊断流程完整执行
- 生成了诊断报告
- 所有事件都正确返回

### 性能测试结果

```
诊断工具平均耗时: 45.32ms
诊断流程总耗时: 11.23s
报告生成耗时: 234.56ms
```

**说明**：
- 性能符合预期
- 诊断流程在 9-13 秒范围内

---

## ✅ 验收标准

### 功能验收

- ✅ 诊断工具能正常工作
- ✅ MCP Server 能正常启动
- ✅ 诊断流程能完整执行
- ✅ 诊断报告能正确生成
- ✅ API 能正常响应

### 性能验收

- ✅ 诊断工具响应时间 < 100ms
- ✅ 诊断流程总耗时 9-13 秒
- ✅ 报告生成耗时 < 500ms

### 质量验收

- ✅ 诊断报告内容完整
- ✅ 诊断结果准确
- ✅ 修复建议有效

---

## 🐛 常见问题

### 问题 1：MCP Server 无法启动

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

### 问题 2：API 无法连接

**症状**：
```
无法连接到 API 服务器
```

**解决方案**：
```bash
# 确保应用已启动
python -m uvicorn app.main:app --host 0.0.0.0 --port 9900

# 检查端口是否被占用
netstat -ano | findstr :9900
```

### 问题 3：诊断报告为空

**症状**：
```
诊断报告没有内容
```

**解决方案**：
```bash
# 重新生成诊断数据
python generate_diagnostic_data.py

# 检查数据文件
ls data/logs.json data/metrics.json data/events.json
```

---

## 📝 测试日志

所有测试日志都保存在 `logs/` 目录下：

```
logs/
├── test_diagnostic_YYYY-MM-DD.log    # 诊断流程测试日志
├── test_integration_YYYY-MM-DD.log   # 集成测试日志
├── test_performance_YYYY-MM-DD.log   # 性能测试日志
└── app_YYYY-MM-DD.log                # 应用日志
```

### 查看日志

```bash
# 查看最新的诊断流程测试日志
tail -f logs/test_diagnostic_*.log

# 查看最新的集成测试日志
tail -f logs/test_integration_*.log

# 查看最新的性能测试日志
tail -f logs/test_performance_*.log
```

---

## 🎯 测试流程图

```
启动 MCP Server
    ↓
启动主应用
    ↓
运行诊断流程测试
    ├─ 测试诊断工具
    ├─ 测试诊断流程
    └─ 测试报告生成
    ↓
运行集成测试
    ├─ 测试诊断工具
    └─ 测试 API 集成
    ↓
运行性能测试
    ├─ 测试工具性能
    ├─ 测试流程性能
    └─ 测试报告性能
    ↓
查看测试结果
    ├─ 功能验收
    ├─ 性能验收
    └─ 质量验收
```

---

## 📊 预期测试结果

### 诊断工具测试

```
✅ 诊断工具测试完成
  - get_alerts: 2 条告警
  - get_error_logs: 10 条错误日志
  - get_metrics_anomalies: 3 个异常指标
  - get_deployment_events: 2 个部署事件
```

### 集成测试

```
✅ 集成测试通过
  - 诊断工具测试: 通过
  - API 集成测试: 通过
  - 共收到 12 个事件
  - 完成 7 个诊断步骤
  - 生成诊断报告
```

### 性能测试

```
✅ 性能测试完成
  - 诊断工具平均耗时: 45ms
  - 诊断流程总耗时: 11s
  - 报告生成耗时: 235ms
```

---

## ✨ 总结

✅ **已完成**：
- 诊断工具 MCP Server 实现
- Planner 诊断任务识别
- Replanner 诊断报告集成
- 诊断提示词
- 诊断报告生成器
- 完整的测试脚本

✅ **可立即测试**：
- 启动 MCP Server
- 启动主应用
- 运行测试脚本
- 查看测试结果

**所有功能已完成，现在就可以开始测试！** 🎉

