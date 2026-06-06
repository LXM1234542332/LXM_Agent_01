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
    return trigger_time


def _calc_analysis_start_from_fault(fault_start_time: str) -> str:
    """故障最早异常时间前推 5 分钟，作为分析窗口开始"""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(fault_start_time, fmt)
            return (dt - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    return fault_start_time


def _calc_fault_categories(metrics_result: Dict[str, Any], alerts_result: Dict[str, Any]) -> list:
    """根据异常指标名称和告警信息初判故障类型分类"""
    categories = set()
    anomaly_keys = set(metrics_result.get("anomalies", {}).keys())
    alert_metrics = {a.get("metric", "") for a in alerts_result.get("data", []) if isinstance(a, dict)}
    all_metrics = anomaly_keys | alert_metrics

    jvm_keys = {"jvm_heap", "jvm_gc", "jvm_thread", "session_cache"}
    queue_keys = {"queue_depth", "queue_consume", "queue_publish", "consumer_lag"}
    latency_keys = {"latency", "p99", "p95", "p50", "duration"}
    error_keys = {"error_rate", "5xx", "success_rate", "timeout"}
    resource_keys = {"cpu_usage", "memory_usage", "disk_usage"}

    for m in all_metrics:
        m_lower = m.lower()
        if any(k in m_lower for k in jvm_keys):
            categories.add("jvm")
        if any(k in m_lower for k in queue_keys):
            categories.add("queue")
        if any(k in m_lower for k in latency_keys):
            categories.add("latency")
        if any(k in m_lower for k in error_keys):
            categories.add("error")
        if any(k in m_lower for k in resource_keys):
            categories.add("resource")

    if len(categories) > 2:
        categories.add("mixed")
    return sorted(categories)


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


def _extract_fault_start_time(metrics_result: Dict[str, Any]) -> str | None:
    """从 get_metrics_anomalies 结果中找最早的异常时间点"""
    anomalies = metrics_result.get("anomalies", {})
    all_times = []
    for info in anomalies.values():
        if not isinstance(info, dict):
            continue
        for point in info.get("anomaly_points", []):
            t = point.get("timestamp")
            if t:
                all_times.append(str(t))
    return min(all_times) if all_times else None


def _safe_parse_timestamp(timestamp_str: str) -> datetime | None:
    """安全解析时间戳，支持多种格式"""
    if not isinstance(timestamp_str, str):
        return None

    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(timestamp_str.strip(), fmt)
        except (ValueError, AttributeError):
            continue

    logger.warning(f"无法解析时间戳: {timestamp_str}")
    return None


def _calc_time_gap_minutes(time1: str, time2: str) -> int:
    """计算两个时间点的分钟差，返回非负整数"""
    dt1 = _safe_parse_timestamp(time1)
    dt2 = _safe_parse_timestamp(time2)

    if dt1 is None or dt2 is None:
        logger.warning(f"时间戳解析失败: time1={time1}, time2={time2}")
        return 0

    delta = dt2 - dt1
    minutes = int(delta.total_seconds() / 60)
    return max(0, minutes)


def _is_linear_growth(points: list) -> bool:
    """判断是否为线性增长模式（至少需要3个点）"""
    if len(points) < 3:
        return False

    try:
        # 取最后3个点计算增长率
        values = []
        for p in points[-3:]:
            try:
                values.append(float(p.get("value", 0)))
            except (ValueError, TypeError):
                return False

        # 计算相邻两个时间段的增长量
        diff1 = values[1] - values[0]
        diff2 = values[2] - values[1]

        # 如果增长量变化小于30%，认为是线性增长
        if abs(diff1) < 1e-6:
            return abs(diff2) < 1e-6

        ratio = abs(diff2 - diff1) / abs(diff1)
        return ratio < 0.3
    except Exception as e:
        logger.warning(f"线性增长判断出错: {e}")
        return False


def _is_exponential_growth(points: list) -> bool:
    """判断是否为指数增长模式（至少需要3个点）"""
    if len(points) < 3:
        return False

    try:
        values = []
        for p in points[-3:]:
            try:
                values.append(float(p.get("value", 0)))
            except (ValueError, TypeError):
                return False

        # 计算倍数
        if values[1] == 0 or values[0] == 0:
            return False

        ratio1 = values[2] / values[1] if values[1] != 0 else 1
        ratio2 = values[1] / values[0] if values[0] != 0 else 1

        # 如果倍数都 > 1.3，认为是指数增长
        return ratio1 > 1.3 and ratio2 > 1.3
    except Exception as e:
        logger.warning(f"指数增长判断出错: {e}")
        return False


def _detect_early_signals(
    metrics_result: Dict[str, Any],
    alerts_result: Dict[str, Any]
) -> list:
    """
    检测异常时间早于告警的信号。

    返回列表，每个元素是：
    {
        "metric": "metric_name",
        "anomaly_start": "2026-07-02T09:30:00Z",
        "alert_trigger": "2026-07-02T10:06:00Z",
        "time_gap_minutes": 36,
        "growth_pattern": "linear",
        "growth_rate": "0.0148",
        "implication": "持续泄漏..."
    }
    """
    anomalies = metrics_result.get("anomalies", {})
    alerts_data = alerts_result.get("data", [])

    if not anomalies or not alerts_data:
        return []

    # 找出所有告警的最早触发时间，并过滤掉无关告警
    alert_times = []
    for a in alerts_data:
        if not isinstance(a, dict):
            continue
        # 过滤掉marked as unrelated的告警
        if a.get("related_to_fault") is False:
            continue
        t = a.get("trigger_time") or a.get("timestamp")
        if t:
            alert_times.append(str(t))

    if not alert_times:
        logger.info("没有关联的告警事件")
        return []

    earliest_alert = min(alert_times)
    logger.info(f"最早告警时间: {earliest_alert}")

    early_signals = []

    for metric_name, info in anomalies.items():
        if not isinstance(info, dict):
            continue

        points = info.get("anomaly_points", [])

        # 数据质量检查
        if len(points) < 2:
            continue

        # 按时间戳排序（确保顺序）
        try:
            sorted_points = sorted(
                points,
                key=lambda p: _safe_parse_timestamp(p.get("timestamp", "")) or datetime.min,
                reverse=True
            )
        except Exception as e:
            logger.warning(f"排序异常点失败 ({metric_name}): {e}")
            continue

        first_point = sorted_points[-1]  # 最早的异常点
        latest_point = sorted_points[0]  # 最新的异常点

        anomaly_start = first_point.get("timestamp")
        if not anomaly_start:
            continue

        # 计算异常开始与告警的时间差
        alert_gap = _calc_time_gap_minutes(anomaly_start, earliest_alert)

        # 早于告警至少10分钟才算early signal
        if alert_gap < 10:
            continue

        # 计算增长值和增长率
        try:
            first_val = float(first_point.get("value", 0))
            latest_val = float(latest_point.get("value", 0))
            growth = latest_val - first_val

            time_gap = _calc_time_gap_minutes(
                first_point.get("timestamp", ""),
                latest_point.get("timestamp", "")
            )

            if time_gap > 0:
                growth_rate = growth / time_gap
            else:
                growth_rate = 0

            # 判断增长模式
            if _is_linear_growth(points):
                growth_pattern = "linear"
                implication = "持续泄漏或资源缓慢耗尽特征"
            elif _is_exponential_growth(points):
                growth_pattern = "exponential"
                implication = "加速问题恶化特征（如缓存击穿、级联放大）"
            else:
                growth_pattern = "stepwise"
                implication = "阶段性问题出现特征（如定时任务、分批处理）"

            signal = {
                "metric": metric_name,
                "anomaly_start": anomaly_start,
                "alert_trigger": earliest_alert,
                "time_gap_minutes": alert_gap,
                "growth_pattern": growth_pattern,
                "growth_rate": f"{growth_rate:.6f}",
                "implication": implication,
            }

            early_signals.append(signal)
            logger.info(f"检测到早期信号 ({metric_name}): gap={alert_gap}min, pattern={growth_pattern}")

        except (ValueError, TypeError) as e:
            logger.warning(f"计算信号数据失败 ({metric_name}): {e}")
            continue

    logger.info(f"共检测到 {len(early_signals)} 个早期信号")
    return early_signals


def _build_fault_signature(
    working_memory: WorkingMemory,
    exact_value_pool: ExactValuePool,
) -> str:
    """生成故障签名字符串，供 Planner prompt 使用"""
    lines = ["【当前故障画像（由 Triage 节点收集，请基于此制定诊断计划）】"]
    lines.append(f"- 告警数量：{working_memory.get('alert_count', 0)} 个，最高级别：{working_memory.get('highest_severity', '未知')}")

    anomaly_services = exact_value_pool.get("known_anomaly_services", [])
    all_services = exact_value_pool.get("known_services", [])
    services = anomaly_services if anomaly_services else all_services
    if services:
        lines.append(f"- 受影响服务：{', '.join(services)}")

    metrics = exact_value_pool.get("known_metric_names", [])
    if metrics:
        lines.append(f"- 异常指标：{', '.join(metrics)}")

    svc_count = working_memory.get("affected_service_count")
    if svc_count is not None:
        lines.append(f"- 受影响服务数量：{svc_count} 个（多服务时需判断传播方向）")

    fault_cats = working_memory.get("fault_categories", [])
    if fault_cats:
        lines.append(f"- 故障类型初判：{', '.join(fault_cats)}")

    lines.append(f"- 告警触发时间：{working_memory.get('alert_first_trigger_time', '未知')}")
    fault_start = working_memory.get('fault_start_time')
    if fault_start:
        lines.append(f"- 最早异常指标时间：{fault_start}（早于告警，应作为排查起点）")

    # 新增：强调早期信号
    early_signals = working_memory.get('early_signals', [])
    if early_signals:
        lines.append(f"\n【⚠️  关键：早期信号警示（早于告警的异常趋势）】")
        for sig in early_signals:
            lines.append(f"- {sig['metric']}: 异常开始于 {sig['anomaly_start']}")
            lines.append(f"  → 早于告警 {sig['time_gap_minutes']} 分钟")
            lines.append(f"  → 增长模式：{sig['growth_pattern']} (速率: {sig['growth_rate']}/分钟)")
            lines.append(f"  → 含义：{sig['implication']}")

    lines.append(f"- 分析时间窗口：{working_memory.get('analysis_start_time', '未知')} ~ {working_memory.get('analysis_end_time', '当前')}")

    has_deploy = working_memory.get('has_deployment_event')
    if has_deploy is True:
        versions = exact_value_pool.get("known_deployment_versions", [])
        ver_str = f"（版本：{', '.join(versions)}）" if versions else ""
        lines.append(f"- 是否有发版事件：是{ver_str}，建议优先排查发版与故障的关联")

        # 新增：详细列出部署事件信息
        deploy_events = working_memory.get("deployment_events", [])
        if deploy_events:
            lines.append(f"\n【部署事件详情】")
            for event in deploy_events:
                if isinstance(event, dict) and event.get("related_to_fault", True):
                    event_type = event.get("event_type", "unknown")
                    service = event.get("service", "unknown")
                    version = event.get("version", "")
                    timestamp = event.get("timestamp", "unknown")
                    if event_type == "deployment":
                        ver_str = f" v{version}" if version else ""
                        lines.append(f"- {service}{ver_str} 发版于 {timestamp}")
                    elif event_type in ["alert", "config_change"]:
                        lines.append(f"- {event_type}: {service} 于 {timestamp}")
    elif has_deploy is False:
        lines.append(f"- 是否有发版事件：否，根因方向应偏向容量/配置/外部依赖")

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
        # 2.5 新增：检测早期信号（异常开始时间早于告警的信号）
        # ----------------------------------------------------------------
        early_signals = _detect_early_signals(metrics_result, alerts_result)
        logger.info(f"早期信号检测: 发现 {len(early_signals)} 个早期信号")

        # ----------------------------------------------------------------
        # 3. 强制调用 get_deployment_events（决定 Planner 是否查发版方向）
        # ----------------------------------------------------------------
        deploy_result: Dict[str, Any] = {}
        has_deploy = False

        if "get_deployment_events" in tool_map:
            logger.info("Triage: 调用 get_deployment_events()")
            raw = await tool_map["get_deployment_events"].ainvoke({})
            deploy_result = _parse_tool_result(raw)
            # 过滤掉干扰项：related_to_fault=false 意味着与本次故障无关，不应影响 has_deployment_event
            all_deploys = deploy_result.get("data", [])
            logger.debug(f"deploy_result keys: {deploy_result.keys()}")
            logger.debug(f"all_deploys count: {len(all_deploys)}")
            
            related_deploys = [
                d for d in all_deploys
                if d.get("related_to_fault", True) is not False  # 显式检查 False，未设置时默认为 True（关联）
            ]
            has_deploy = bool(related_deploys)
            logger.info(f"get_deployment_events: total={len(all_deploys)}, related={len(related_deploys)}, has_deploy={has_deploy}")
            
            for idx, d in enumerate(related_deploys):
                logger.info(f"  [related deploy #{idx+1}] {d.get('service', 'unknown')} v{d.get('version', 'unknown')} @ {d.get('timestamp', 'unknown')}")

            # 额外检查：是否有事件包含culprit_version（用于识别根因发版）
            has_culprit = any(d.get("culprit_version") for d in all_deploys)
            if has_culprit and not has_deploy:
                logger.info("检测到culprit_version，标记为有关联的发版事件")
                has_deploy = True

            exact_value_pool = update_exact_value_pool(exact_value_pool, "get_deployment_events", deploy_result)
        else:
            logger.warning("Triage: get_deployment_events 工具不可用")
            has_deploy = False

        # ----------------------------------------------------------------
        # 4. 提取 WorkingMemory 锚点参数
        # ----------------------------------------------------------------
        trigger_time = _parse_trigger_time(alerts_result)
        fault_start = _extract_fault_start_time(metrics_result)
        analysis_end = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

        affected_services = list(dict.fromkeys(
            s for s in exact_value_pool.get("known_anomaly_services", [])
            + exact_value_pool.get("known_services", [])
            if s
        ))
        fault_cats = _calc_fault_categories(metrics_result, alerts_result)

        working_memory = {
            "scenario_id": scenario_id,
            "alert_count": int(alerts_result.get("count", len(alerts_result.get("data", [])))),
            "highest_severity": _get_highest_severity(alerts_result),
            "analysis_end_time": analysis_end,
            "has_deployment_event": has_deploy,
            "affected_service_count": len(affected_services),
            "fault_categories": fault_cats,
            "early_signals": early_signals,  # 新增：早期信号
            "deployment_events": deploy_result.get("data", []),  # 新增：部署事件原始数据
        }

        if trigger_time:
            working_memory["alert_first_trigger_time"] = trigger_time

        # analysis_start_time 优先取 fault_start_time - 5min，其次取 alert_time - 15min
        if fault_start:
            working_memory["fault_start_time"] = fault_start
            working_memory["analysis_start_time"] = _calc_analysis_start_from_fault(fault_start)
        elif trigger_time:
            working_memory["analysis_start_time"] = _calc_analysis_start(trigger_time)
        else:
            fallback_start = (datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            working_memory["alert_first_trigger_time"] = analysis_end
            working_memory["analysis_start_time"] = fallback_start

        logger.info(f"WorkingMemory 初始化完成: {working_memory}")
        logger.info(f"ExactValuePool 初始化完成: services={exact_value_pool.get('known_services', [])}")

    except Exception as e:
        logger.exception(f"Triage 阶段异常: {e}")
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        fallback_start = (datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        working_memory = {
            "scenario_id": scenario_id,
            "alert_count": 0,
            "highest_severity": "unknown",
            "alert_first_trigger_time": now,
            "analysis_start_time": fallback_start,
            "analysis_end_time": now,
            "has_deployment_event": False,
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
