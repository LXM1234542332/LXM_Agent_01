# MCP 服务故障排查与修复记录

## 一、问题描述

### 现象

在 Oncall-Agent 项目中，用户在前端输入任何问题（如"你是谁"），系统返回错误：

```
错误: unhandled errors in a TaskGroup (1 sub-exception)
```

前端浏览器控制台输出：

```json
{
  "code": 500,
  "message": "error",
  "data": {
    "success": false,
    "answer": null,
    "errorMessage": "unhandled errors in a TaskGroup (1 sub-exception)"
  }
}
```

### 环境信息

- 操作系统：Ubuntu (WSL2 on Windows 11)
- Python：3.13
- 框架：FastAPI + LangGraph + LangChain
- LLM：阿里云千问（ChatQwen）
- 向量数据库：Milvus
- MCP 框架：FastMCP 3.2.4

---

## 二、排查过程

### 第一步：查看后端日志

```bash
tail -f logs/app_$(date +%Y-%m-%d).log
```

日志输出：

```
2026-05-12 20:02:46 | ERROR | rag_agent_service.query:232 | [会话 session_xxx] RAG Agent 查询失败（非流式）: unhandled errors in a TaskGroup (1 sub-exception)
2026-05-12 20:02:53 | ERROR | rag_agent_service.query_stream:299 | [会话 session_xxx] RAG Agent 查询失败（流式）: unhandled errors in a TaskGroup (1 sub-exception)
```

**发现**：错误发生在 `rag_agent_service` 中，但没有完整的堆栈跟踪。

---

### 第二步：增加详细日志

修改 `app/services/rag_agent_service.py`，在 except 块中添加 `exc_info=True`：

```python
except Exception as e:
    logger.error(f"RAG Agent 查询失败: {e}", exc_info=True)
    raise
```

同时，用 `try-except` 包装 MCP 工具加载逻辑：

```python
async def _initialize_agent(self):
    try:
        mcp_client = await get_mcp_client_with_retry()
        mcp_tools = await mcp_client.get_tools()
        logger.info(f"成功加载 {len(mcp_tools)} 个 MCP 工具")
        self.mcp_tools = mcp_tools
    except Exception as e:
        logger.warning(f"MCP 工具加载失败: {e}", exc_info=True)
        self.mcp_tools = []  # 降级为只使用本地工具
```

**效果**：系统恢复正常（使用本地工具），同时日志中出现了关键信息：

```
2026-05-12 21:38:20 | WARNING | rag_agent_service._initialize_agent:130 | MCP 工具加载失败: unhandled errors in a TaskGroup (1 sub-exception)
2026-05-12 21:38:20 | INFO    | rag_agent_service._initialize_agent:147 | 可用工具列表: retrieve_knowledge, get_current_time
```

**结论**：问题根源是 **MCP 工具加载失败**，而不是 LLM 或 RAG 本身的问题。

---

### 第三步：排查 MCP 服务状态

```bash
# 检查 MCP 进程
ps aux | grep mcp
# 结果：没有 MCP 进程

# 检查 MCP 日志
tail -f logs/mcp_*.log
# 结果：No such file or directory

# 检查端口
ss -tlnp | grep -E "8003|8004"
# 结果：无输出（端口未监听）
```

**发现**：MCP 服务根本没有启动，但 `make start` 输出显示"已经在运行中"。

---

### 第四步：分析 Makefile 的启动逻辑

查看 Makefile 中 MCP 服务的启动命令：

```makefile
start-cls:
    @if pgrep -f "mcp_servers/cls_server.py" > /dev/null 2>&1; then \
        echo "✅ CLS MCP 服务已经在运行中"; \
    else \
        nohup .venv/bin/python mcp_servers/cls_server.py > mcp_cls.log 2>&1 & \
        echo $$! > mcp_cls.pid; \
        sleep 2; \
        if pgrep -f "mcp_servers/cls_server.py" > /dev/null 2>&1; then \
            echo "✅ CLS MCP 服务启动成功"; \
        else \
            echo "❌ CLS MCP 服务启动失败"; \
        fi; \
    fi
```

**问题分析**：
- `nohup` 命令在某些 Shell 环境下（尤其是 WSL2）不可靠
- `sleep 2` 等待时间不够，服务还没完全启动就检查了
- 日志文件 `mcp_cls.log` 没有生成，说明 `nohup` 没有正确执行

---

### 第五步：验证 MCP 服务本身是否正常

创建诊断脚本 `test_mcp.py`：

```python
from mcp_servers import cls_server
from mcp_servers import monitor_server
print("✅ MCP 服务导入成功")
```

运行结果：

```
✅ CLS MCP 导入成功
✅ Monitor MCP 导入成功
```

手动前台启动 MCP 服务：

```bash
.venv/bin/python mcp_servers/cls_server.py
```

输出：

```
INFO:     Started server process [15227]
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8003 (Press CTRL+C to quit)
```

**结论**：MCP 服务本身完全正常，问题出在 **Makefile 的启动脚本**上。

---

### 第六步：修复启动脚本

创建新的启动脚本 `start_mcp.sh`，使用更可靠的后台启动方式：

```bash
#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# 启动 CLS MCP 服务
if pgrep -f "mcp_servers/cls_server.py" > /dev/null 2>&1; then
    echo "✅ CLS MCP 服务已经在运行中"
else
    .venv/bin/python mcp_servers/cls_server.py > mcp_cls.log 2>&1 &
    CLS_PID=$!
    echo $CLS_PID > mcp_cls.pid
    sleep 3

    if ps -p $CLS_PID > /dev/null 2>&1; then
        echo "✅ CLS MCP 服务启动成功 (PID: $CLS_PID)"
    else
        echo "❌ CLS MCP 服务启动失败"
        tail -n 20 mcp_cls.log
        exit 1
    fi
fi

# 启动 Monitor MCP 服务（同上）
...
```

**关键改动**：
1. 去掉 `nohup`，直接使用 `&` 后台运行
2. 等待时间从 2 秒增加到 3 秒
3. 使用 `ps -p $PID` 检查具体进程，而不是 `pgrep`
4. 启动失败时显示日志内容

---

### 第七步：验证修复结果

```bash
bash start_mcp.sh
make status-mcp
```

输出：

```
CLS MCP 服务:
  状态: 运行中
  PID: 15600
  URL: http://127.0.0.1:8003/mcp
  连接: ✅ 正常

Monitor MCP 服务:
  状态: 运行中
  PID: 15604
  URL: http://127.0.0.1:8004/mcp
  连接: ✅ 正常
```

重启 FastAPI 服务后，日志显示：

```
2026-05-13 22:05:26 | INFO | mcp_client.get_mcp_client:125 | 全局 MCP 客户端初始化完成
2026-05-13 22:05:26 | INFO | rag_agent_service._initialize_agent:123 | 成功加载 7 个 MCP 工具
2026-05-13 22:05:26 | INFO | rag_agent_service._initialize_agent:147 | 可用工具列表: retrieve_knowledge, get_current_time, get_current_timestamp, get_region_code_by_name, get_topic_info_by_name, search_topic_by_service_name, search_log, query_cpu_metrics, query_memory_metrics
```

**问题完全解决！**

---

## 三、根本原因分析

### 直接原因

`nohup` 命令在 WSL2 环境下行为不稳定，导致 MCP 服务进程无法正常启动并保持运行。

### 深层原因

| 问题 | 说明 |
|------|------|
| `nohup` 不可靠 | 在 WSL2 的某些 Shell 环境中，`nohup` 无法正确将进程与终端分离 |
| 等待时间不足 | `sleep 2` 不够，FastMCP 服务启动需要约 3 秒 |
| 错误检测不完善 | 启动失败时没有显示日志内容，难以诊断 |
| 错误处理缺失 | 后端代码没有对 MCP 加载失败做降级处理，导致整个 Agent 崩溃 |

---

## 四、解决方案

### 方案一：修复启动脚本（根本解决）

创建 `start_mcp.sh`，替换 Makefile 中不可靠的 `nohup` 启动方式：

- 使用 `&` 直接后台运行
- 增加等待时间到 3 秒
- 启动失败时输出日志内容

### 方案二：增加降级处理（防御性编程）

在 `rag_agent_service.py` 中对 MCP 加载失败做降级处理：

```python
try:
    mcp_client = await get_mcp_client_with_retry()
    mcp_tools = await mcp_client.get_tools()
    self.mcp_tools = mcp_tools
except Exception as e:
    logger.warning(f"MCP 工具加载失败: {e}，继续使用本地工具")
    self.mcp_tools = []  # 降级为只使用本地工具
```

**好处**：即使 MCP 服务不可用，系统仍然可以正常工作，只是少了 MCP 工具。

---

## 五、经验总结

### 排查思路

```
前端报错
  ↓
查看后端日志（定位错误层级）
  ↓
增加详细日志（获取完整堆栈）
  ↓
缩小问题范围（MCP 加载失败）
  ↓
检查 MCP 服务状态（进程、端口、日志）
  ↓
验证 MCP 服务本身（手动启动）
  ↓
分析启动脚本（找到根本原因）
  ↓
修复并验证
```

### 关键教训

1. **日志要有堆栈跟踪**：`logger.error(msg, exc_info=True)` 比 `logger.error(str(e))` 更有价值

2. **关键依赖要有降级处理**：MCP 服务不可用时，系统不应该完全崩溃，应该降级为只使用本地工具

3. **启动脚本要有验证**：启动后要检查进程是否真的在运行，而不是只检查命令是否执行成功

4. **环境差异要注意**：`nohup` 在不同环境（macOS、Linux、WSL2）下行为可能不同，要做充分测试

5. **分层排查**：从前端 → 后端 API → 服务层 → 依赖服务，逐层缩小问题范围

### 面试要点

- **问题定位能力**：通过日志逐步缩小问题范围，从"系统报错"定位到"MCP 启动脚本的 nohup 问题"
- **防御性编程**：对外部依赖（MCP 服务）做降级处理，提高系统健壮性
- **工具使用**：`ps`、`ss`、`lsof`、`pgrep` 等 Linux 工具的综合运用
- **根因分析**：不只是修复表象，而是找到根本原因（nohup 在 WSL2 下不可靠）

---

## 六、最终系统状态

| 组件 | 状态 | 说明 |
|------|------|------|
| FastAPI 服务 | ✅ 正常 | http://localhost:9900 |
| Milvus 向量数据库 | ✅ 正常 | 向量检索正常 |
| CLS MCP 服务 | ✅ 正常 | http://127.0.0.1:8003/mcp |
| Monitor MCP 服务 | ✅ 正常 | http://127.0.0.1:8004/mcp |
| 本地工具 | ✅ 正常 | retrieve_knowledge, get_current_time |
| MCP 工具 | ✅ 正常 | 7 个工具全部加载成功 |
| **总工具数** | **9 个** | 2 个本地 + 7 个 MCP |
