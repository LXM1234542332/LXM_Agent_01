#!/usr/bin/env python3
"""详细测试 FastMCP 运行"""

import sys
import asyncio
import traceback

print("=" * 80)
print("详细测试 FastMCP 运行")
print("=" * 80)

# 测试 FastMCP 库
print("\n【测试 FastMCP 库】")
try:
    from fastmcp import FastMCP
    print("✅ FastMCP 导入成功")

    # 创建一个简单的 MCP 实例
    mcp = FastMCP("Test")
    print("✅ FastMCP 实例创建成功")

    # 添加一个简单的工具
    @mcp.tool()
    def test_tool() -> str:
        """测试工具"""
        return "Hello from test tool"

    print("✅ 工具注册成功")

except Exception as e:
    print(f"❌ FastMCP 测试失败: {e}")
    traceback.print_exc()

# 测试 CLS MCP 的具体内容
print("\n【测试 CLS MCP 的工具】")
try:
    from mcp_servers.cls_server import mcp as cls_mcp
    print(f"✅ CLS MCP 实例获取成功")
    print(f"   MCP 名称: {cls_mcp.name if hasattr(cls_mcp, 'name') else 'N/A'}")

except Exception as e:
    print(f"❌ CLS MCP 工具测试失败: {e}")
    traceback.print_exc()

# 测试 Monitor MCP 的具体内容
print("\n【测试 Monitor MCP 的工具】")
try:
    from mcp_servers.monitor_server import mcp as monitor_mcp
    print(f"✅ Monitor MCP 实例获取成功")
    print(f"   MCP 名称: {monitor_mcp.name if hasattr(monitor_mcp, 'name') else 'N/A'}")

except Exception as e:
    print(f"❌ Monitor MCP 工具测试失败: {e}")
    traceback.print_exc()

print("\n" + "=" * 80)
print("测试完成")
print("=" * 80)
