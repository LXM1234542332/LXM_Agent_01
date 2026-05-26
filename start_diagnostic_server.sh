#!/bin/bash
# AI Ops 诊断功能快速启动脚本

echo "=========================================="
echo "AI Ops 诊断功能启动脚本"
echo "=========================================="
echo ""

# 检查依赖
echo "检查依赖..."
python -c "from fastmcp import FastMCP; from diagnostic_tools import DiagnosticDataTools" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "安装依赖..."
    pip install -e . > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "错误：依赖安装失败"
        exit 1
    fi
fi

echo "✓ 依赖检查完成"
echo ""

# 启动 MCP Server
echo "启动诊断工具 MCP Server..."
echo "命令: python mcp_servers/diagnostic_server.py"
echo ""
echo "在另一个终端中运行以下命令启动主应用："
echo "  python -m uvicorn app.main:app --host 0.0.0.0 --port 9900"
echo ""
echo "然后在第三个终端中运行以下命令触发诊断："
echo "  curl -X POST \"http://localhost:9900/api/aiops\" \\"
echo "    -H \"Content-Type: application/json\" \\"
echo "    -d '{\"session_id\": \"test\"}' \\"
echo "    --no-buffer"
echo ""
echo "=========================================="
echo ""

python mcp_servers/diagnostic_server.py
