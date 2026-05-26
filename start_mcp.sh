#!/bin/bash
# 启动 MCP 服务的脚本

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "=========================================="
echo "启动 MCP 服务"
echo "=========================================="

# 启动 CLS MCP 服务
echo ""
echo "【启动 CLS MCP 服务】"
if pgrep -f "mcp_servers/cls_server.py" > /dev/null 2>&1; then
    echo "✅ CLS MCP 服务已经在运行中"
else
    echo "📦 正在启动 CLS MCP 服务..."
    # 使用 & 在后台运行，而不是 nohup
    .venv/bin/python mcp_servers/cls_server.py > mcp_cls.log 2>&1 &
    CLS_PID=$!
    echo $CLS_PID > mcp_cls.pid
    echo "   PID: $CLS_PID"

    # 等待服务启动
    sleep 3

    # 检查进程是否还在运行
    if ps -p $CLS_PID > /dev/null 2>&1; then
        echo "✅ CLS MCP 服务启动成功"
        echo "   URL: http://127.0.0.1:8003/mcp"
        echo "   日志: mcp_cls.log"
    else
        echo "❌ CLS MCP 服务启动失败"
        echo "   错误日志："
        tail -n 20 mcp_cls.log
        exit 1
    fi
fi

# 启动 Monitor MCP 服务
echo ""
echo "【启动 Monitor MCP 服务】"
if pgrep -f "mcp_servers/monitor_server.py" > /dev/null 2>&1; then
    echo "✅ Monitor MCP 服务已经在运行中"
else
    echo "📦 正在启动 Monitor MCP 服务..."
    .venv/bin/python mcp_servers/monitor_server.py > mcp_monitor.log 2>&1 &
    MONITOR_PID=$!
    echo $MONITOR_PID > mcp_monitor.pid
    echo "   PID: $MONITOR_PID"

    # 等待服务启动
    sleep 3

    # 检查进程是否还在运行
    if ps -p $MONITOR_PID > /dev/null 2>&1; then
        echo "✅ Monitor MCP 服务启动成功"
        echo "   URL: http://127.0.0.1:8004/mcp"
        echo "   日志: mcp_monitor.log"
    else
        echo "❌ Monitor MCP 服务启动失败"
        echo "   错误日志："
        tail -n 20 mcp_monitor.log
        exit 1
    fi
fi

echo ""
echo "=========================================="
echo "✅ MCP 服务启动完成"
echo "=========================================="
