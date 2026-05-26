"""MCP 服务器主模块 - 支持 python -m mcp_servers.diagnostic_server 运行"""

from .diagnostic_server import mcp
from loguru import logger

if __name__ == "__main__":
    logger.info("启动诊断工具 MCP Server...")
    logger.info(f"服务器名称: {mcp.name}")
    logger.info(f"可用工具数: 12")

    # 启动 MCP 服务器
    # FastMCP 会自动处理 stdio 通信
    mcp.run()
