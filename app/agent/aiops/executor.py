"""
Executor 节点：执行计划中的单个步骤

流程：
1. 取出 plan[0] 作为当前步骤
2. 构建注入 WorkingMemory + ExactValuePool + past_steps 摘要的 messages
3. LLM 通过 Function Calling 决定调用哪个工具及参数
4. ToolNode 执行工具调用，获取结果
5. 调用规则提取器更新 ExactValuePool
6. 调用 LLM 摘要器生成分层去噪摘要
7. 返回 StepRecord 三元组
"""

import json
from typing import Dict, Any, List

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import ToolNode
from loguru import logger
import os

from app.config import config
from app.core.llm_factory import llm_factory
from app.agent.mcp_client import get_mcp_client_with_retry
from .state import PlanExecuteState, StepRecord, WorkingMemory, ExactValuePool
from .prompts import EXECUTOR_SYSTEM_PROMPT
from .memory import update_exact_value_pool, summarize_step


def _format_working_memory(wm: WorkingMemory) -> str:
    """将 WorkingMemory 格式化为可注入的文本"""
    if not wm:
        return "（无诊断锚点）"
    lines = []
    if wm.get("analysis_start_time") and wm.get("analysis_end_time"):
        lines.append(f"- 分析时间窗口：{wm['analysis_start_time']} ~ {wm['analysis_end_time']}")
    if wm.get("alert_first_trigger_time"):
        lines.append(f"- 告警触发时间：{wm['alert_first_trigger_time']}")
    if wm.get("highest_severity"):
        lines.append(f"- 最高告警级别：{wm['highest_severity']}")
    if wm.get("alert_count") is not None:
        lines.append(f"- 告警总数：{wm['alert_count']}")
    if wm.get("scenario_id"):
        lines.append(f"- 场景ID：{wm['scenario_id']}")
    return "\n".join(lines) if lines else "（无诊断锚点）"


def _format_exact_value_pool(pool: ExactValuePool) -> str:
    """将 ExactValuePool 格式化为可注入的文本"""
    if not pool:
        return "（尚无已知精确值）"
    lines = []
    if pool.get("known_services"):
        lines.append(f"- 已知服务名（可直接用作 service 参数）：{', '.join(pool['known_services'])}")
    if pool.get("known_metric_names"):
        lines.append(f"- 已知指标名（可直接用作 metric_name 参数）：{', '.join(pool['known_metric_names'])}")
    if pool.get("known_trace_ids"):
        lines.append(f"- 已知 trace_id：{', '.join(pool['known_trace_ids'])}")
    if pool.get("known_event_types"):
        lines.append(f"- 已知事件类型：{', '.join(pool['known_event_types'])}")
    if pool.get("known_severities"):
        lines.append(f"- 已知告警级别：{', '.join(pool['known_severities'])}")
    if pool.get("known_timestamps"):
        lines.append(f"- 近期关键时间戳：{', '.join(pool['known_timestamps'][-5:])}")
    return "\n".join(lines) if lines else "（尚无已知精确值）"


def _format_past_steps(past_steps: List[StepRecord]) -> str:
    """将 past_steps 的摘要格式化为可注入的文本"""
    if not past_steps:
        return "（无前序步骤）"
    parts = []
    for i, record in enumerate(past_steps, 1):
        step_desc = record.get("step", "")
        summary = record.get("summary", record.get("raw_result", ""))
        parts.append(f"步骤{i}：{step_desc}\n{summary}")
    return "\n\n".join(parts)


def _extract_tool_name_from_calls(tool_calls) -> str | None:
    """从 LLM tool_calls 中提取第一个工具名"""
    if not tool_calls:
        return None
    first = tool_calls[0]
    if isinstance(first, dict):
        return first.get("name")
    return getattr(first, "name", None)


async def executor(state: PlanExecuteState) -> Dict[str, Any]:
    """
    Executor 节点：执行计划中的下一个步骤，注入完整上下文。
    """
    logger.info("=== Executor：执行步骤 ===")

    plan = state.get("plan", [])
    if not plan:
        logger.info("计划为空，跳过执行")
        return {}

    task = plan[0]
    logger.info(f"当前步骤: {task}")

    working_memory: WorkingMemory = state.get("working_memory", {})
    exact_value_pool: ExactValuePool = state.get("exact_value_pool", {})
    past_steps: List[StepRecord] = state.get("past_steps", [])

    try:
        mcp_client = await get_mcp_client_with_retry()
        all_tools = await mcp_client.get_tools()
        # 排除场景管理工具：set_scenario/get_current_scenario 仅在 Triage 前使用，
        # 不应出现在 Plan-Execute-Replan 流程中，否则 LLM 会自作主张插入调用
        _EXCLUDED = {"set_scenario", "get_current_scenario"}
        mcp_tools = [t for t in all_tools if t.name not in _EXCLUDED]
        logger.info(f"获取到 {len(mcp_tools)} 个 MCP 工具（已排除场景管理工具）")

        llm = llm_factory.create_chat_model(
            temperature=0,
            provider=os.getenv("LLM_PROVIDER", "dashscope")
        )
        llm_with_tools = llm.bind_tools(mcp_tools)
        tool_node = ToolNode(mcp_tools)

        # ----------------------------------------------------------------
        # 构建注入完整上下文的 messages
        # ----------------------------------------------------------------
        messages = [
            SystemMessage(content=EXECUTOR_SYSTEM_PROMPT),
            HumanMessage(content=f"诊断锚点（WorkingMemory）：\n{_format_working_memory(working_memory)}"),
            HumanMessage(content=f"已知精确值（ExactValuePool）：\n{_format_exact_value_pool(exact_value_pool)}"),
            HumanMessage(content=f"前序步骤摘要：\n{_format_past_steps(past_steps)}"),
            HumanMessage(content=f"请执行以下步骤：{task}"),
        ]

        llm_response = await llm_with_tools.ainvoke(messages)
        logger.info(f"LLM 输出内容: {llm_response.content}")
        logger.info(f"LLM 工具调用: {llm_response.tool_calls if hasattr(llm_response, 'tool_calls') else '无'}")

        called_tool_name: str | None = None
        tool_messages: Dict[str, Any] = {}

        if hasattr(llm_response, "tool_calls") and llm_response.tool_calls:
            called_tool_name = _extract_tool_name_from_calls(llm_response.tool_calls)
            logger.info(f"检测到工具调用: {called_tool_name}")

            messages.append(llm_response)
            tool_messages = await tool_node.ainvoke({"messages": messages})

            if "messages" in tool_messages:
                # 一次遍历同时提取 raw_result 和 tool_result_json
                # 不再二次调用 LLM：原先的 llm_with_tools.ainvoke 会因 messages 末尾仍是
                # "请执行步骤：xxx" 而再次触发工具调用，且其输出与 summarize_step 完全重叠
                tool_result_msgs = tool_messages["messages"]
                raw_parts = []
                tool_result_json: Dict[str, Any] = {}
                for msg in tool_result_msgs:
                    content = getattr(msg, "content", "")
                    if isinstance(content, str) and content:
                        raw_parts.append(content)
                        if not tool_result_json:
                            try:
                                tool_result_json = json.loads(content)
                            except (json.JSONDecodeError, ValueError):
                                pass
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text = block.get("text", "")
                                if text:
                                    raw_parts.append(text)
                                    if not tool_result_json:
                                        try:
                                            tool_result_json = json.loads(text)
                                        except (json.JSONDecodeError, ValueError):
                                            pass
                raw_result = "\n".join(raw_parts) if raw_parts else str(tool_result_msgs)
                if called_tool_name and tool_result_json:
                    exact_value_pool = update_exact_value_pool(exact_value_pool, called_tool_name, tool_result_json)
                    logger.debug(f"ExactValuePool 已更新，触发工具: {called_tool_name}")
            elif "error" in tool_messages:
                logger.error(f"工具执行出错: {tool_messages['error']}")
                raw_result = f"工具执行失败: {tool_messages['error']}"
                summary = await summarize_step(task, raw_result)
                record: StepRecord = {"step": task, "raw_result": raw_result, "summary": summary}
                return {"plan": plan[1:], "past_steps": [record], "exact_value_pool": exact_value_pool}
            else:
                logger.warning(f"ToolNode 返回未知结构: {tool_messages}")
                raw_result = f"工具执行返回未知结构: {tool_messages}"
                summary = await summarize_step(task, raw_result)
                record = {"step": task, "raw_result": raw_result, "summary": summary}
                return {"plan": plan[1:], "past_steps": [record], "exact_value_pool": exact_value_pool}
        else:
            logger.info("LLM 未调用工具，直接返回结果")
            raw_result = llm_response.content if hasattr(llm_response, "content") else str(llm_response)

        logger.info(f"步骤执行完成，结果长度: {len(raw_result)}")

        # ----------------------------------------------------------------
        # 生成分层去噪摘要
        # ----------------------------------------------------------------
        summary = await summarize_step(task, raw_result)

        record = {"step": task, "raw_result": raw_result, "summary": summary}
        return {
            "plan": plan[1:],
            "past_steps": [record],
            "exact_value_pool": exact_value_pool,
        }

    except Exception as e:
        logger.exception("执行步骤失败")
        raw_result = f"执行失败: {str(e)}"
        try:
            summary = await summarize_step(task, raw_result)
        except Exception:
            summary = raw_result
        record = {"step": task, "raw_result": raw_result, "summary": summary}
        return {
            "plan": plan[1:],
            "past_steps": [record],
            "exact_value_pool": exact_value_pool,
        }
