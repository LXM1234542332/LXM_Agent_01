"""
Executor 节点：执行计划中的单个步骤
目标：根据当前步骤描述，通过 Function Calling 调用 MCP 工具，返回执行结果
"""

from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_qwq import ChatQwen
from langgraph.prebuilt import ToolNode
from loguru import logger

from app.config import config
from app.agent.mcp_client import get_mcp_client_with_retry
from .state import PlanExecuteState
from .prompts import EXECUTOR_SYSTEM_PROMPT


async def executor(state: PlanExecuteState) -> Dict[str, Any]:
    """
    Executor 节点：执行计划中的下一个步骤

    流程：
    1. 取出 PlanList[0] 作为当前步骤
    2. 从 MCP 获取所有工具，通过 bind_tools() 绑定到 LLM
    3. LLM 通过 Function Calling 决定调用哪个工具及参数
    4. ToolNode 执行工具调用，获取结果
    5. LLM 整理结果，返回清晰的执行摘要
    """
    logger.info("=== Executor：执行步骤 ===")

    plan = state.get("plan", [])

    if not plan:
        logger.info("计划为空，跳过执行")
        return {}

    task = plan[0]
    logger.info(f"当前步骤: {task}")

    try:
        # 从 MCP 获取所有工具，通过 bind_tools() 绑定（Function Calling）
        mcp_client = await get_mcp_client_with_retry()
        mcp_tools = await mcp_client.get_tools()
        logger.info(f"获取到 {len(mcp_tools)} 个 MCP 工具")

        llm = ChatQwen(
            model=config.rag_model,
            api_key=config.dashscope_api_key,
            temperature=0
        )
        llm_with_tools = llm.bind_tools(mcp_tools)
        tool_node = ToolNode(mcp_tools)

        messages = [
            SystemMessage(content=EXECUTOR_SYSTEM_PROMPT),
            HumanMessage(content=f"请执行以下步骤：{task}")
        ]

        # LLM 通过 Function Calling 决定调用哪个工具
        llm_response = await llm_with_tools.ainvoke(messages)
        logger.info(f"LLM 输出内容: {llm_response.content}")
        logger.info(f"LLM 工具调用: {llm_response.tool_calls if hasattr(llm_response, 'tool_calls') else '无'}")

        if hasattr(llm_response, "tool_calls") and llm_response.tool_calls:
            logger.info(f"检测到 {len(llm_response.tool_calls)} 个工具调用")

            # ToolNode 执行工具调用
            messages.append(llm_response)
            tool_messages = await tool_node.ainvoke({"messages": messages})

            # 将工具结果返回给 LLM，生成清晰的执行摘要
            messages.extend(tool_messages["messages"])
            final_response = await llm_with_tools.ainvoke(messages)
            result = final_response.content if hasattr(final_response, "content") else str(final_response)
        else:
            logger.info("LLM 未调用工具，直接返回结果")
            result = llm_response.content if hasattr(llm_response, "content") else str(llm_response)

        logger.info(f"步骤执行完成，结果长度: {len(result)}")

        return {
            "plan": plan[1:],           # 移除已执行的步骤
            "past_steps": [(task, result)],  # 追加到执行历史
        }

    except Exception as e:
        logger.error(f"执行步骤失败: {e}", exc_info=True)
        return {
            "plan": plan[1:],
            "past_steps": [(task, f"执行失败: {str(e)}")],
        }
