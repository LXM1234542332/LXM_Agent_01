# LangSmith 开启与使用指南

## 一、Trace（云端追踪）

**作用**：记录每次 LLM 调用、工具调用的完整链路，在 LangSmith 网站上查看历史执行记录。

### 配置（一次配置永久生效）

在 `.env` 里加入以下变量：

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT= Oncall-Agent-Study
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

> **注意**：`LANGCHAIN_PROJECT` 的值前面有一个空格（` Oncall-Agent-Study`），这是因为 LangSmith 上已存在一个带前导空格的项目，保持一致才能正确归档。

### 启动方式

正常启动 uvicorn 即可，trace 会自动上报：

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 9900
```

`app/main.py` 里的 `load_dotenv()` 会自动读取 `.env`，无需额外操作。

### 查看

打开 https://smith.langchain.com → 进入项目 `Oncall-Agent-Study` → 查看 Runs。

---

## 二、Studio（调试）

**作用**：在 LangSmith 网站上可视化调试本地的 LangGraph 工作流，可以直接输入测试数据、查看每个节点的输入输出。

### 启动方式

每次启动都必须用这条命令（带 `export`）：

```bash
export $(grep -v '^#' .env | xargs) && ./.venv/bin/langgraph dev --port 8123
```

**为什么必须加 `export`**：`langgraph dev` 是独立进程，不会自动读取 `.env`。如果不提前导出环境变量，`DASHSCOPE_API_KEY` 等配置就是空的，调用阿里云 API 时会报 401 错误。

### 打开 Studio

WSL 无法自动打开浏览器，需要手动在 Windows 浏览器里粘贴以下链接：

```
https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:8123
```

### 可以忽略的报错

启动时会出现以下两个报错，**不影响功能**，直接忽略：

- `volumes/etcd Permission denied` — 文件监听器无法监听 Docker 目录，只影响热重载
- `gio: Operation not supported` — WSL 无法自动打开浏览器

---

## 三、两种方式对比

| | Trace | Studio |
|--|-------|--------|
| 用途 | 监控生产环境执行历史 | 本地开发调试 |
| 启动命令 | `uvicorn` | `langgraph dev` |
| 查看入口 | LangSmith 网站 → Runs | LangSmith 网站 → Studio |
| 环境变量读取 | `load_dotenv()` 自动读取 | 需要手动 `export` |
| 端口 | 9900 | 8123 |

两个服务可以同时运行，互不影响。Studio 里的执行也会上报到 LangSmith 的 Trace。

---

## 四、验证 LangSmith 连接是否正常

```bash
python - <<'PY'
from dotenv import load_dotenv
load_dotenv()
from langsmith import Client
c = Client()
print(list(c.list_projects(limit=5)))
PY
```

- 能打印出项目列表：key 有效，网络正常
- 报 401 Invalid token：key 不对或 workspace 不匹配，需要在 LangSmith 控制台重新生成 key
