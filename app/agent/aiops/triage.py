"""
Triage 节点：故障画像建立

职责：
1. 强制调用 get_alerts()
2. 强制调用 get_metrics_anomalies()
3. 提取 WorkingMemory 的 6 个锚点参数
4. 初始化 ExactValuePool
5. 生成故障签名（fault_signature），注入 state["input"] 供 Planner 使用
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any

from loguru import logger

from app.agent.mcp_client import get_mcp_client_with_retry
from .state import PlanExecuteState, WorkingMemory, ExactValuePool
from .memory import update_exact_value_pool


def _parse_tool_result(raw: Any) -> Dict[str, Any]:
    """
    统一解析 MCP 工具 ainvoke 的返回值。

    langchain-mcp-adapters 工具使用 response_format="content_and_artifact"，
    ainvoke 返回 tuple(content, artifact)，content 是 JSON 字符串。
    也兼容直接返回 str 或 dict 的情况。
    """
    # tuple(content, artifact) — 正常返回格式
    if isinstance(raw, tuple):
        raw = raw[0]

    # list[ContentBlock] — langchain-mcp-adapters 的实际返回格式
    # 每个文本块形如 {"type": "text", "text": "<json>", "id": "..."}
    if isinstance(raw, list):
        for block in raw:
            text = None
            if isinstance(block, dict):
                text = block.get("text")
            else:
                text = getattr(block, "text", None)
            if isinstance(text, str):
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    continue
        return {}

    # 字符串 — 尝试 JSON 解析
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    # dict — 直接使用
    if isinstance(raw, dict):
        return raw

    # ToolMessage 或其他对象 — 取 content 属性
    content = getattr(raw, "content", None)
    if isinstance(content, str):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}
    if isinstance(content, dict):
        return content

    return {}


def _parse_trigger_time(alerts_result: Dict[str, Any]):
    """从 get_alerts 结果中找最早的告警触发时间"""
    data = alerts_result.get("data", [])
    if not data:
        return None
    times = []
    for item in data:
        t = item.get("trigger_time") or item.get("timestamp")
        if t:
            times.append(str(t))
    return min(times) if times else None


def _calc_analysis_start(trigger_time: str) -> str:
    """告警触发时间前推 15 分钟，作为分析窗口开始，返回 ISO 8601 格式"""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(trigger_time, fmt)
            return (dt - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    # 无法解析则直接返回原值
    return trigger_time


def _get_highest_severity(alerts_result: Dict[str, Any]) -> str:
    """从 get_alerts 结果中提取最高告警级别"""
    priority = {"critical": 3, "warning": 2, "info": 1}
    data = alerts_result.get("data", [])
    highest = "info"
    for item in data:
        sev = str(item.get("severity", "info")).lower()
        if priority.get(sev, 0) > priority.get(highest, 0):
            highest = sev
    return highest


def _build_fault_signature(
    working_memory: WorkingMemory,
    exact_value_pool: ExactValuePool,
) -> str:
    """生成故障签名字符串，供 Planner prompt 使用"""
    lines = ["【当前故障画像（由 Triage 节点收集，请基于此制定诊断计划）】"]
    lines.append(f"- 告警数量：{working_memory.get('alert_count', 0)} 个，最高级别：{working_memory.get('highest_severity', '未知')}")

    services = exact_value_pool.get("known_services", [])
    if services:
        lines.append(f"- 受影响服务：{', '.join(services)}")

    metrics = exact_value_pool.get("known_metric_names", [])
    if metrics:
        lines.append(f"- 异常指标：{', '.join(metrics)}")

    lines.append(f"- 告警触发时间：{working_memory.get('alert_first_trigger_time', '未知')}")
    lines.append(f"- 分析时间窗口：{working_memory.get('analysis_start_time', '未知')} ~ {working_memory.get('analysis_end_time', '当前')}")
    lines.append(f"- 场景ID：{working_memory.get('scenario_id', '未知')}")

    return "\n".join(lines)


async def triage(state: PlanExecuteState) -> Dict[str, Any]:
    """
    Triage 节点：建立故障画像，初始化 WorkingMemory 和 ExactValuePool。

    强制调用 get_alerts + get_metrics_anomalies，提取锚点参数和精确值，
    然后将故障签名注入 state["input"]，供 Planner 生成有针对性的计划。
    """
    logger.info("=== Triage：建立故障画像 ===")

    scenario_id = state.get("scenario_id", "")
    working_memory: WorkingMemory = {}
    exact_value_pool: ExactValuePool = {}

    try:
        mcp_client = await get_mcp_client_with_retry()
        mcp_tools = await mcp_client.get_tools()

        # 构建工具名 → 工具对象映射，方便直接调用
        tool_map = {t.name: t for t in mcp_tools}

        # ----------------------------------------------------------------
        # 1. 强制调用 get_alerts
        # ----------------------------------------------------------------
        alerts_result: Dict[str, Any] = {}
        if "get_alerts" in tool_map:
            logger.info("Triage: 调用 get_alerts()")
            raw = await tool_map["get_alerts"].ainvoke({})
            alerts_result = _parse_tool_result(raw)
            logger.info(f"get_alerts 结果: count={alerts_result.get('count', 0)}, data长度={len(alerts_result.get('data', []))}")
            exact_value_pool = update_exact_value_pool(exact_value_pool, "get_alerts", alerts_result)
        else:
            logger.warning("Triage: get_alerts 工具不可用")

        # ----------------------------------------------------------------
        # 2. 强制调用 get_metrics_anomalies
        # ----------------------------------------------------------------
        metrics_result: Dict[str, Any] = {}
        if "get_metrics_anomalies" in tool_map:
            logger.info("Triage: 调用 get_metrics_anomalies()")
            raw = await tool_map["get_metrics_anomalies"].ainvoke({})
            metrics_result = _parse_tool_result(raw)
            logger.info(f"get_metrics_anomalies 结果: anomalies count={len(metrics_result.get('anomalies', {}))}")
            exact_value_pool = update_exact_value_pool(exact_value_pool, "get_metrics_anomalies", metrics_result)
        else:
            logger.warning("Triage: get_metrics_anomalies 工具不可用")

        # ----------------------------------------------------------------
        # 3. 提取 WorkingMemory 6 个锚点参数
        # ----------------------------------------------------------------
        trigger_time = _parse_trigger_time(alerts_result)
        analysis_end = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

        working_memory = {
            "scenario_id": scenario_id,
            "alert_count": int(alerts_result.get("count", len(alerts_result.get("data", [])))),
            "highest_severity": _get_highest_severity(alerts_result),
            "analysis_end_time": analysis_end,
        }

        if trigger_time:
            working_memory["alert_first_trigger_time"] = trigger_time
            working_memory["analysis_start_time"] = _calc_analysis_start(trigger_time)
        else:
            # 无告警时，默认分析窗口为当前时间往前 30 分钟
            fallback_start = (datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            working_memory["alert_first_trigger_time"] = analysis_end
            working_memory["analysis_start_time"] = fallback_start

        logger.info(f"WorkingMemory 初始化完成: {working_memory}")
        logger.info(f"ExactValuePool 初始化完成: services={exact_value_pool.get('known_services', [])}")

    except Exception as e:
        logger.exception(f"Triage 阶段异常: {e}")
        # 降级：用默认值，不中断流程
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        fallback_start = (datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        working_memory = {
            "scenario_id": scenario_id,
            "alert_count": 0,
            "highest_severity": "unknown",
            "alert_first_trigger_time": now,
            "analysis_start_time": fallback_start,
            "analysis_end_time": now,
        }

    # ----------------------------------------------------------------
    # 4. 生成故障签名，注入到 input 供 Planner 使用
    # ----------------------------------------------------------------
    fault_signature = _build_fault_signature(working_memory, exact_value_pool)
    original_input = state.get("input", "")
    enriched_input = f"{original_input}\n\n{fault_signature}"

    logger.info(f"Triage 完成，故障签名:\n{fault_signature}")

    return {
        "input": enriched_input,
        "working_memory": working_memory,
        "exact_value_pool": exact_value_pool,
        "triage_results": {
            "alerts": alerts_result,
            "metrics_anomalies": metrics_result,
        },
    }
