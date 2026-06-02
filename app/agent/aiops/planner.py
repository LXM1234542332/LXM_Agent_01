"""
Planner 节点：制定执行计划
目标：根据用户请求和可用工具，生成有序的诊断计划列表（PlanList）
"""

from textwrap import dedent
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from loguru import logger
import os

from app.config import config
from app.core.llm_factory import llm_factory
from app.agent.mcp_client import get_mcp_client_with_retry
from .state import PlanExecuteState
from .utils import format_tools_description
from .prompts import PLANNER_SYSTEM_PROMPT


class Plan(BaseModel):
    """计划的输出格式"""
    steps: List[str] = Field(
        description="诊断计划步骤列表，每个步骤描述要调用的工具和目的，按顺序执行。"
    )


async def planner(state: PlanExecuteState) -> Dict[str, Any]:
    """
    Planner 节点：根据用户输入和可用工具，生成诊断计划列表（PlanList）

    流程：
    1. 从 MCP 获取所有可用工具，格式化为文本描述
    2. 将工具描述注入提示词
    3. 调用 LLM 生成计划列表
    """
    logger.info("=== Planner：制定执行计划 ===")

    input_text = state.get("input", "")
    logger.info(f"用户输入: {input_text}")

    try:
        # 从 MCP 获取所有可用工具，格式化为文本描述注入提示词
        mcp_client = await get_mcp_client_with_retry()
        mcp_tools = await mcp_client.get_tools()
        tools_description = format_tools_description(mcp_tools)
        logger.info(f"获取到 {len(mcp_tools)} 个 MCP 工具")

        # 构建提示词
        prompt = ChatPromptTemplate.from_messages([
            ("system", PLANNER_SYSTEM_PROMPT),
            ("placeholder", "{messages}"),
        ])

        logger.info(f"system: {PLANNER_SYSTEM_PROMPT} ")
        logger.info("placeholder: {messages}")

        llm = llm_factory.create_chat_model(
            temperature=0,
            provider=os.getenv("LLM_PROVIDER", "dashscope")
        )
        logger.info(f"llm加载完毕，提供商: {os.getenv('LLM_PROVIDER', 'dashscope')}")


        planner_chain = prompt | llm.with_structured_output(Plan, method="json_mode", include_raw=True)

        raw_result = await planner_chain.ainvoke({
            "messages": [("user", input_text)],
            "tools_description": tools_description,
        })

        # include_raw=True 时返回 {"raw": AIMessage, "parsed": Plan, "parsing_error": ...}
        # raw_result在langchain框架下固定的结构
        # "raw": AIMessage, LLM 的原始输出，永远有值
        # "parsed": Plan, 解析成功则是 Plan 实例，失败则是 None
        # "parsing_error": 解析成功则是 None，失败则是异常对象
        logger.info(f"LLM 原始输出: {raw_result.get('raw')}")
        logger.info(f"parsed: {raw_result.get('parsed')}")
        logger.info(f"parsing_error: {raw_result.get('parsing_error')}")

        plan_result = raw_result.get("parsed")

        # parsed 为 None 时，从 invalid_tool_calls 里提取原始 args 并修复单引号问题
        if plan_result is None:
            logger.warning("structured_output 解析失败，尝试从 invalid_tool_calls 中修复")
            raw_msg = raw_result.get("raw")
            if raw_msg and hasattr(raw_msg, "invalid_tool_calls") and raw_msg.invalid_tool_calls:
                import json
                raw_args = raw_msg.invalid_tool_calls[0].get("args", "")
                # 将转义的单引号 \' 替换为普通单引号，再让 json.loads 正常解析
                fixed_args = raw_args.replace("\\'", "'")
                try:
                    parsed_dict = json.loads(fixed_args)
                    plan_result = Plan(steps=parsed_dict.get("steps", []))
                    logger.info(f"修复成功，步骤数: {len(plan_result.steps)}")
                except Exception as parse_err:
                    logger.error(f"修复 JSON 失败: {parse_err}")
                    raise ValueError(f"LLM 输出无法解析: {parse_err}")
            else:
                raise ValueError("LLM 返回 None 且无 invalid_tool_calls 可用于修复")

        # 返回Plan实例或字典格式的计划步骤列表
        if isinstance(plan_result, Plan):
            logger.info(f"返回的Plan实例")
            plan_steps = plan_result.steps
        # 返回字典（某些模型或版本会返回 dict）
        else:
            logger.info(f"返回的字典格式结果")
            plan_steps = plan_result.get("steps", [])  # type: ignore
            
        logger.info(f"计划已生成，共 {len(plan_steps)} 个步骤")
        for i, step in enumerate(plan_steps, 1):
            logger.info(f"  步骤 {i}: {step}")

        return {"plan": plan_steps}

    except Exception as e:
        # loguru uses str.format on message strings; exceptions like KeyError("error")
        # render as "{'error': ...}" which would be treated as a format placeholder.
        logger.exception("生成计划失败")
        return {
            "plan": [
                "调用 get_alerts() - 获取当前系统中的所有告警",
                "调用 get_error_logs(limit=30) - 获取最近的错误日志",
                "调用 get_deployment_events(limit=10) - 获取最近的部署事件",
                "调用 get_metrics_anomalies() - 获取异常指标",
            ]
        }
