#!/bin/bash
# 在 WSL 中启动主应用

PYTHON_PATH="C:/Users/Administrator/.conda/envs/Oncall-Agent/python.exe"

echo "启动主应用..."
echo "Python: $PYTHON_PATH"
echo ""

"$PYTHON_PATH" -m uvicorn app.main:app --host 0.0.0.0 --port 9900
