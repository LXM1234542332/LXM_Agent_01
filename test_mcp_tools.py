import asyncio
from app.agent.mcp_client import get_mcp_client_with_retry
from loguru import logger

async def test():
    try:
        logger.info("获取 MCP 客户端...")
        client = await get_mcp_client_with_retry()
        logger.info(f"客户端类型: {type(client)}")
        
        logger.info("获取工具列表...")
        tools = await client.get_tools()
        logger.info(f"工具数量: {len(tools)}")
        
        if tools:
            logger.info(f"第一个工具类型: {type(tools[0])}")
            logger.info(f"第一个工具内容: {tools[0]}")
            if isinstance(tools[0], dict):
                logger.info(f"工具字典键: {tools[0].keys()}")
    except Exception as e:
        logger.error(f"错误: {e}", exc_info=True)

asyncio.run(test())
