"""
Planner 节点：制定执行计划
目标：根据用户请求和可用工具，生成有序的诊断计划列表（PlanList）
"""

import json
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
    analysis: str = Field(
        description="基于 Triage 数据的分析过程，说明问题特征、可能的根因方向、为什么会采用这个诊断策略"
    )
    steps: List[str] = Field(
        description="诊断计划步骤列表，每个步骤描述要调用的工具和目的，按顺序执行。"
    )


def _build_triage_context(triage_results: Dict[str, Any], working_memory: Dict[str, Any]) -> str:
    """把 Triage 阶段的原始结果和 WorkingMemory 整合成 Planner 可读的文本"""
    lines = []

    # WorkingMemory 锚点 - 时间参数单独强调
    if working_memory:
        lines.append("【诊断锚点】")

        # 时间窗口 - 用更清晰的格式，强调不要修改
        start_time = working_memory.get('analysis_start_time', '未知')
        end_time = working_memory.get('analysis_end_time', '未知')
        lines.append(f"【重要】查询时间范围参数（直接用于工具调用，不要修改）：")
        lines.append(f"  start_time = {start_time}")
        lines.append(f"  end_time = {end_time}")
        lines.append("")

        lines.append("【其他诊断信息】")
        lines.append(f"- 告警触发时间：{working_memory.get('alert_first_trigger_time', '未知')}")
        lines.append(f"- 告警总数：{working_memory.get('alert_count', 0)} 个，最高级别：{working_memory.get('highest_severity', '未知')}")
        lines.append(f"- 场景ID：{working_memory.get('scenario_id', '未知')}")
        lines.append("")

    # get_alerts 结果
    alerts = triage_results.get("alerts", {})
    alerts_data = alerts.get("data", [])
    if alerts_data:
        lines.append("【get_alerts() 执行结果】")
        for alert in alerts_data:
            lines.append(
                f"- 服务：{alert.get('service', '未知')}，"
                f"级别：{alert.get('severity', '未知')}，"
                f"指标：{alert.get('metric_name', '未知')}，"
                f"触发时间：{alert.get('trigger_time') or alert.get('timestamp', '未知')}，"
                f"当前值：{alert.get('current_value', '未知')}，"
                f"阈值：{alert.get('threshold', '未知')}"
            )
        lines.append("")
    else:
        lines.append("【get_alerts() 执行结果】：未发现告警")
        lines.append("")

    # get_metrics_anomalies 结果
    anomalies = triage_results.get("metrics_anomalies", {}).get("anomalies", {})
    if anomalies:
        lines.append("【get_metrics_anomalies() 执行结果】")
        for metric_name, info in anomalies.items():
            if isinstance(info, dict):
                points = info.get("anomaly_points", [])
                threshold = info.get("threshold", "未知")
                latest = points[0] if points else {}
                lines.append(
                    f"- 指标：{metric_name}，"
                    f"阈值：{threshold}，"
                    f"最新异常值：{latest.get('value', '未知')}（{latest.get('timestamp', '未知')}）"
                )
        lines.append("")
    else:
        lines.append("【get_metrics_anomalies() 执行结果】：未发现指标异常")
        lines.append("")

    # 新增：get_deployment_events 结果
    deployment_events = working_memory.get("deployment_events", [])
    if deployment_events:
        lines.append("【get_deployment_events() 执行结果】")
        for event in deployment_events:
            if isinstance(event, dict):
                event_type = event.get("event_type", "unknown")
                service = event.get("service", "unknown")
                timestamp = event.get("timestamp", "unknown")
                related = event.get("related_to_fault", True)

                if event_type == "deployment":
                    version = event.get("version", "unknown")
                    status = event.get("status", "unknown")
                    related_mark = "✓关联" if related else "✗无关"
                    lines.append(f"- 发版：{service} v{version} 于 {timestamp} ({status}) [{related_mark}]")
                elif event_type == "config_change":
                    related_mark = "✓关联" if related else "✗无关"
                    lines.append(f"- 配置变更：{service} 于 {timestamp} [{related_mark}]")
                elif event_type in ["alert", "jvm_heap_warning", "gc_storm_start", "thread_pool_saturation"]:
                    lines.append(f"- {event_type}: {service} 于 {timestamp}")
        lines.append("")
    else:
        lines.append("【get_deployment_events() 执行结果】：未发现部署/配置变更事件")
        lines.append("")

    return "\n".join(lines)


async def planner(state: PlanExecuteState) -> Dict[str, Any]:
    """
    Planner 节点：根据 Triage 结果和可用工具，生成针对性的诊断计划列表（PlanList）
    """
    logger.info("=== Planner：制定执行计划 ===")

    input_text = state.get("input", "")
    triage_results = state.get("triage_results", {})
    working_memory = state.get("working_memory", {})

    # 构建 Triage 上下文：把两个工具的原始结果和 WorkingMemory 整合成可读文本
    triage_context = _build_triage_context(triage_results, working_memory)
    logger.info(f"Triage 上下文:\n{triage_context}")

    try:
        # 从 MCP 获取所有可用工具，排除场景管理工具后格式化为文本描述注入提示词
        mcp_client = await get_mcp_client_with_retry()
        all_tools = await mcp_client.get_tools()
        _EXCLUDED = {"set_scenario", "get_current_scenario"}
        mcp_tools = [t for t in all_tools if t.name not in _EXCLUDED]
        tools_description = format_tools_description(mcp_tools)
        logger.info(f"获取到 {len(mcp_tools)} 个 MCP 工具（已排除场景管理工具）")

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
            "triage_context": triage_context,
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
                    plan_result = Plan(
                        analysis=parsed_dict.get("analysis", ""),
                        steps=parsed_dict.get("steps", [])
                    )
                    logger.info(f"修复成功，步骤数: {len(plan_result.steps)}")
                except Exception as parse_err:
                    logger.error(f"修复 JSON 失败: {parse_err}")
                    raise ValueError(f"LLM 输出无法解析: {parse_err}")
            else:
                raise ValueError("LLM 返回 None 且无 invalid_tool_calls 可用于修复")

        # 返回Plan实例或字典格式的计划步骤列表
        if isinstance(plan_result, Plan):
            logger.info(f"返回的Plan实例")
            plan_analysis = plan_result.analysis
            plan_steps = plan_result.steps
        # 返回字典（某些模型或版本会返回 dict）
        else:
            logger.info(f"返回的字典格式结果")
            plan_analysis = plan_result.get("analysis", "")  # type: ignore
            plan_steps = plan_result.get("steps", [])  # type: ignore

        # 输出分析过程
        if plan_analysis:
            logger.info("=== Planner 分析过程 ===")
            logger.info(plan_analysis)
            logger.info("=== 分析完成，开始制定计划 ===")

        logger.info(f"计划已生成，共 {len(plan_steps)} 个步骤")
        for i, step in enumerate(plan_steps, 1):
            logger.info(f"  步骤 {i}: {step}")

        return {"plan": plan_steps}

    except Exception as e:
        logger.exception("生成计划失败")
        return {
            "plan": [
                "调用 get_error_logs(limit=30) - 获取最近的错误日志，了解错误类型",
                "调用 get_deployment_events(limit=10) - 检查是否有近期部署操作",
                "调用 get_events(limit=20) - 获取系统事件，寻找异常变化",
            ]
        }
