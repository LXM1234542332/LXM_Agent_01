import asyncio
from app.agent.aiops.planner import planner
from app.agent.aiops.state import PlanExecuteState
from loguru import logger

async def test():
    state: PlanExecuteState = {
        "input": "诊断当前系统是否存在告警，如果存在告警请详细分析告警原因并生成诊断报告",
        "plan": [],
        "past_steps": [],
        "response": ""
    }
    
    try:
        logger.info("调用 planner...")
        result = await planner(state)
        logger.info(f"planner 返回: {result}")
    except Exception as e:
        logger.error(f"错误: {e}", exc_info=True)

asyncio.run(test())
