# ✅ 依赖已安装 - 现在可以启动应用了！

## 🎉 问题已解决

依赖已在你的 Python 环境中成功安装。诊断 MCP Server 已验证可以正常启动。

---

## 🚀 现在启动应用（3 个终端）

### 第 1 步：启动诊断 MCP Server

**在终端 1 中运行：**

```bash
cd /e/agent/vscode/Oncall-Agent
python mcp_servers/diagnostic_server.py
```

**预期输出：**
```
2026-05-21 16:23:55,154 - Diagnostic_MCP_Server - INFO - 启动诊断工具 MCP Server...
2026-05-21 16:23:55,154 - Diagnostic_MCP_Server - INFO - 服务器名称: Diagnostic
2026-05-21 16:23:55,154 - Diagnostic_MCP_Server - INFO - 可用工具数: 12

+-----------------------------------------------------------------------------+
|                                                                             |
|                        FastMCP 3.3.1                                        |
|                            https://gofastmcp.com                            |
|                                                                             |
|                 🖥  Server:      Diagnostic, 3.3.1                           |
|                 🚀 Deploy free: https://horizon.prefect.io                  |
|                                                                             |
+-----------------------------------------------------------------------------+

[05/21/26 16:23:57] INFO     Starting MCP server 'Diagnostic'  transport.py:209
                             with transport 'stdio'
```

✅ **MCP Server 已启动！** 保持这个终端运行。

---

### 第 2 步：启动主应用

**在终端 2 中运行：**

```bash
cd /e/agent/vscode/Oncall-Agent
python -m uvicorn app.main:app --host 0.0.0.0 --port 9900
```

**预期输出：**
```
INFO:     Uvicorn running on http://0.0.0.0:9900
INFO:     Application startup complete
```

✅ **主应用已启动！** 保持这个终端运行。

---

### 第 3 步：触发诊断

**在终端 3 中运行：**

```bash
curl -X POST "http://localhost:9900/api/aiops" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-session"}' \
  --no-buffer
```

**预期输出：**
```
data: {"type":"status","stage":"fetching_alerts","message":"正在获取系统告警信息..."}
data: {"type":"plan","stage":"plan_created","message":"诊断计划已制定，共 7 个步骤","plan":[...]}
data: {"type":"step_complete","stage":"step_executed","message":"步骤执行完成 (1/7)","current_step":"获取所有告警事件"}
data: {"type":"step_complete","stage":"step_executed","message":"步骤执行完成 (2/7)","current_step":"获取错误日志"}
...
data: {"type":"report","stage":"final_report","message":"最终诊断报告已生成","report":"# 系统诊断报告\n..."}
data: {"type":"complete","stage":"diagnosis_complete","message":"诊断流程完成"}
```

✅ **诊断完成！** 查看诊断报告。

---

## 📊 诊断报告示例

诊断完成后，你会看到类似的报告：

```markdown
# 系统诊断报告

## 📋 诊断摘要
- 诊断时间：2026-05-21 16:24:00
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
```

---

## 🧪 运行测试（可选）

### 诊断流程测试
```bash
python test_diagnostic_flow.py
```

### 集成测试
```bash
python test_integration.py
```

### 性能测试
```bash
python test_performance.py
```

---

## 📝 日志位置

所有日志都保存在 `logs/` 目录下：

```bash
# 查看应用日志
tail -f logs/app_*.log

# 查看诊断流程测试日志
tail -f logs/test_diagnostic_*.log
```

---

## ✅ 验收清单

启动后，检查以下内容：

- ✅ MCP Server 已启动（终端 1 显示 "Starting MCP server"）
- ✅ 主应用已启动（终端 2 显示 "Application startup complete"）
- ✅ 诊断流程能完整执行（收到所有事件）
- ✅ 诊断报告能正确生成（收到 "report" 事件）
- ✅ 修复建议能正确给出（报告中包含建议）

---

## 🎯 总结

| 步骤 | 状态 | 命令 |
|------|------|------|
| 安装依赖 | ✅ 完成 | `pip install -e .` |
| 启动 MCP Server | ⏳ 待做 | `python mcp_servers/diagnostic_server.py` |
| 启动主应用 | ⏳ 待做 | `python -m uvicorn app.main:app --host 0.0.0.0 --port 9900` |
| 触发诊断 | ⏳ 待做 | `curl -X POST "http://localhost:9900/api/aiops" ...` |

---

## 💡 提示

- 保持所有 3 个终端运行
- 诊断流程通常需要 9-13 秒
- 查看 `logs/` 目录了解详细信息
- 如有问题，检查日志文件

**现在就可以开始使用 AI Ops 诊断功能！** 🚀

