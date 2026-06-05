"""
WorkingMemory / ExactValuePool 操作模块

- EXTRACTORS：每个工具对应的精确值提取规则
- update_exact_value_pool：从工具返回 JSON 提取精确值并追加到 ExactValuePool
- summarize_step：调用轻量 LLM 生成分层去噪摘要
"""

from typing import Any, Dict, List
import os
from loguru import logger

from .state import ExactValuePool


# ============================================================================
# 规则提取器：每个工具 → 从返回 JSON 中提取哪些字段到 ExactValuePool 哪个 key
# 格式：{ tool_name: { pool_key: extractor_fn } }
# ============================================================================

def _extract_data_field(result: Dict, field: str) -> List[str]:
    """从 data 数组型结果中提取指定字段"""
    items = result.get("data", [])
    return [str(item[field]) for item in items if isinstance(item, dict) and field in item]


def _extract_anomaly_keys(result: Dict) -> List[str]:
    """从 anomalies 字典型结果中提取 key（即指标名）"""
    anomalies = result.get("anomalies", {})
    return list(anomalies.keys()) if isinstance(anomalies, dict) else []


def _extract_anomaly_services(result: Dict) -> List[str]:
    """从 anomalies 字典型结果中提取各指标的 service 字段"""
    anomalies = result.get("anomalies", {})
    services = []
    if isinstance(anomalies, dict):
        for metric_data in anomalies.values():
            if isinstance(metric_data, dict) and "service" in metric_data:
                services.append(str(metric_data["service"]))
    return services


def _extract_spans_field(result: Dict, field: str) -> List[str]:
    """从 spans 嵌套型结果中提取指定字段"""
    spans = result.get("spans", [])
    return [str(span[field]) for span in spans if isinstance(span, dict) and field in span]


EXTRACTORS: Dict[str, Dict[str, Any]] = {
    "get_alerts": {
        "known_services":      lambda r: _extract_data_field(r, "service"),
        "known_severities":    lambda r: _extract_data_field(r, "severity"),
        "known_metric_names":  lambda r: _extract_data_field(r, "metric_name"),
        "known_timestamps":    lambda r: _extract_data_field(r, "trigger_time"),
    },
    "get_error_logs": {
        "known_services":   lambda r: _extract_data_field(r, "service"),
        "known_timestamps": lambda r: _extract_data_field(r, "timestamp"),
        "known_trace_ids":  lambda r: _extract_data_field(r, "trace_id"),
    },
    "get_logs_by_service": {
        "known_trace_ids":  lambda r: _extract_data_field(r, "trace_id"),
        "known_timestamps": lambda r: _extract_data_field(r, "timestamp"),
    },
    "get_logs_by_time_range": {
        "known_services":   lambda r: _extract_data_field(r, "service"),
        "known_trace_ids":  lambda r: _extract_data_field(r, "trace_id"),
    },
    "get_logs_by_keyword": {
        "known_services":   lambda r: _extract_data_field(r, "service"),
        "known_trace_ids":  lambda r: _extract_data_field(r, "trace_id"),
        "known_timestamps": lambda r: _extract_data_field(r, "timestamp"),
    },
    "get_metrics_anomalies": {
        "known_metric_names": lambda r: _extract_anomaly_keys(r),
        "known_services":     lambda r: _extract_anomaly_services(r),
    },
    "get_metrics_by_name": {
        "known_timestamps": lambda r: _extract_data_field(r, "timestamp"),
    },
    "get_metrics_by_time_range": {
        "known_metric_names": lambda r: _extract_data_field(r, "metric_name"),
        "known_services":     lambda r: _extract_data_field(r, "service"),
        "known_timestamps":   lambda r: _extract_data_field(r, "timestamp"),
    },
    "get_deployment_events": {
        "known_services":    lambda r: _extract_data_field(r, "service"),
        "known_timestamps":  lambda r: _extract_data_field(r, "timestamp"),
    },
    "get_events": {
        "known_services":     lambda r: _extract_data_field(r, "service"),
        "known_timestamps":   lambda r: _extract_data_field(r, "timestamp"),
        "known_event_types":  lambda r: _extract_data_field(r, "event_type"),
    },
    "get_events_by_type": {
        "known_services":    lambda r: _extract_data_field(r, "service"),
        "known_timestamps":  lambda r: _extract_data_field(r, "timestamp"),
    },
    "get_events_by_time_range": {
        "known_services":     lambda r: _extract_data_field(r, "service"),
        "known_event_types":  lambda r: _extract_data_field(r, "event_type"),
        "known_timestamps":   lambda r: _extract_data_field(r, "timestamp"),
    },
    "get_slow_traces": {
        "known_trace_ids": lambda r: _extract_data_field(r, "trace_id"),
        "known_services":  lambda r: _extract_data_field(r, "service"),
    },
    "get_trace_details": {
        "known_trace_ids": lambda r: _extract_spans_field(r, "trace_id"),
        "known_services":  lambda r: _extract_spans_field(r, "service"),
    },
    "get_service_dependencies": {
        "known_services": lambda r: (
            [str(s) for s in r.get("upstream", [])]
            + [str(s) for s in r.get("downstream", [])]
        ),
    },
}


# ============================================================================
# update_exact_value_pool：从工具结果提取精确值，追加到 ExactValuePool
# ============================================================================

def update_exact_value_pool(
    pool: ExactValuePool,
    tool_name: str,
    tool_result: Dict[str, Any],
) -> ExactValuePool:
    """
    从工具返回结果中提取精确值，追加到 ExactValuePool（不去重，调用方负责去重）。

    Args:
        pool: 当前 ExactValuePool（会被复制，不会原地修改）
        tool_name: 工具名称，用于查找对应提取规则
        tool_result: 工具返回的原始 JSON 字典

    Returns:
        更新后的新 ExactValuePool
    """
    extractor = EXTRACTORS.get(tool_name)
    if not extractor:
        logger.debug(f"工具 '{tool_name}' 无对应提取规则，跳过")
        return pool

    updated: ExactValuePool = dict(pool)  # type: ignore

    for pool_key, extract_fn in extractor.items():
        try:
            new_values: List[str] = extract_fn(tool_result)
            if not new_values:
                continue

            existing: List[str] = list(updated.get(pool_key, []))  # type: ignore

            # known_timestamps 只保留最近 10 个
            if pool_key == "known_timestamps":
                merged = existing + new_values
                updated[pool_key] = merged[-10:]  # type: ignore
            else:
                # 去重，保持顺序
                seen = set(existing)
                for v in new_values:
                    if v not in seen:
                        existing.append(v)
                        seen.add(v)
                updated[pool_key] = existing  # type: ignore

        except Exception as e:
            logger.warning(f"提取 '{tool_name}.{pool_key}' 失败: {e}")

    return updated


# ============================================================================
# summarize_step：调用轻量 LLM 生成分层去噪摘要
# ============================================================================

SUMMARIZER_PROMPT = """你是一个运维数据摘要专家。将以下工具执行结果按分层去噪策略压缩：

① 异常/错误类记录 → 完整保留所有字段（服务名、时间、错误信息、ID）
② 关键数值 → 保留精确数字和单位
③ 正常/冗余记录 → 折叠为统计描述（"另有 N 条正常日志"）
④ 所有服务名、指标名、ID、时间戳 → 禁止改写，必须保留原文

直接输出摘要内容，不要加任何前缀说明。"""


async def summarize_step(step: str, raw_result: str) -> str:
    """
    调用轻量 LLM 对单步执行结果生成分层去噪摘要。

    Args:
        step: 步骤描述
        raw_result: 工具原始返回内容

    Returns:
        摘要字符串；若调用失败则返回截断后的 raw_result
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    from app.core.llm_factory import llm_factory

    try:
        llm = llm_factory.create_chat_model(
            temperature=0,
            provider=os.getenv("LLM_PROVIDER", "dashscope")
        )
        messages = [
            SystemMessage(content=SUMMARIZER_PROMPT),
            HumanMessage(content=f"步骤：{step}\n\n执行结果：\n{raw_result}"),
        ]
        response = await llm.ainvoke(messages)
        summary = response.content if hasattr(response, "content") else str(response)
        logger.debug(f"摘要生成完成，长度: {len(summary)}")
        return summary
    except Exception as e:
        logger.warning(f"摘要生成失败，使用截断结果: {e}")
        return raw_result[:500] + ("..." if len(raw_result) > 500 else "")
