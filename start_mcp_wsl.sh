#!/bin/bash
# 在 WSL 中启动诊断 MCP Server

PYTHON_PATH="C:/Users/Administrator/.conda/envs/Oncall-Agent/python.exe"

echo "启动诊断工具 MCP Server..."
echo "Python: $PYTHON_PATH"
echo ""

"$PYTHON_PATH" mcp_servers/diagnostic_server.py
