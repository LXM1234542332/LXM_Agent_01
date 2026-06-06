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
import re
from typing import Dict, Any, List, Set

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


class ExecutorContext:
    """执行上下文，维护跨步骤的关键发现"""

    def __init__(self):
        self.key_services: Set[str] = set()
        self.key_metrics: Set[str] = set()
        self.error_patterns: Dict[str, int] = {}
        self.upstream_services: Set[str] = set()
        self.deployment_versions: Set[str] = set()

    def extract_from_logs(self, logs_result: Dict[str, Any]):
        """从日志结果中提取关键字段"""
        if not isinstance(logs_result, dict):
            return

        for log_entry in logs_result.get("data", []):
            if not isinstance(log_entry, dict):
                continue

            # 提取服务名
            service = log_entry.get("service")
            if service:
                self.key_services.add(str(service))

            # 提取错误类型并统计
            error_type = log_entry.get("error_type") or log_entry.get("type")
            if error_type:
                error_type_str = str(error_type)
                self.error_patterns[error_type_str] = (
                    self.error_patterns.get(error_type_str, 0) + 1
                )

            # 提取上游服务（从错误信息中）
            message = str(log_entry.get("message", "")).lower()
            if "upstream" in message or "calling" in message:
                matches = re.findall(r"(\w+-service)", message)
                self.upstream_services.update(matches)

    def extract_from_metrics(self, metrics_result: Dict[str, Any]):
        """从指标结果中提取关键字段"""
        if not isinstance(metrics_result, dict):
            return

        for metric_name in metrics_result.get("anomalies", {}).keys():
            self.key_metrics.add(str(metric_name))

    def extract_from_deployment(self, deploy_result: Dict[str, Any]):
        """从部署事件中提取版本信息"""
        if not isinstance(deploy_result, dict):
            return

        for event in deploy_result.get("data", []):
            if isinstance(event, dict):
                version = event.get("version")
                if version:
                    self.deployment_versions.add(str(version))

    def suggest_next_queries(self) -> List[str]:
        """基于已有发现，建议下一步查询"""
        suggestions = []

        # 如果发现了UPSTREAM_TIMEOUT，建议查询上游服务
        if "UPSTREAM_TIMEOUT" in self.error_patterns:
            for svc in self.upstream_services:
                suggestions.append(f"检查上游服务 {svc} 的错误日志和指标状态")

        # 如果发现了GC相关错误，建议查询GC日志和堆增长
        if any("GC" in ep for ep in self.error_patterns.keys()):
            suggestions.append("查询GC日志的heap_before/heap_after，确认是否为泄漏")
            suggestions.append("分析jvm_heap_used_gb的时序增长模式（线性=泄漏，突发=高峰）")

        # 如果发现了连接池相关错误，建议查询缓存和连接池
        if any("POOL" in ep or "CONNECTION" in ep for ep in self.error_patterns.keys()):
            suggestions.append(
                "查询缓存/session增长与heap的关联系数，判断是否为缓存泄漏"
            )

        # 如果有部署版本，建议查询该版本的改动
        if self.deployment_versions:
            for version in self.deployment_versions:
                suggestions.append(
                    f"查询版本{version}的changelog，关键词：cache、session、pool、memory"
                )

        return suggestions


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

    # 新增：部署事件信息
    if wm.get("has_deployment_event"):
        lines.append(f"- 有部署/配置变更事件：是")
        deployment_events = wm.get("deployment_events", [])
        if deployment_events:
            lines.append(f"  相关发版/变更：")
            for event in deployment_events:
                if isinstance(event, dict):
                    if event.get("event_type") == "deployment" and event.get("related_to_fault", True):
                        version = event.get("version", "unknown")
                        timestamp = event.get("timestamp", "unknown")
                        lines.append(f"    - {event.get('service')} v{version} 于 {timestamp}")

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
