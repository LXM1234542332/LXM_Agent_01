"""诊断工具 MCP Server

本地实现的诊断工具 MCP Server，提供系统诊断功能。
包括日志查询、指标分析、事件查询等功能。
"""

import logging
import functools
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
# from fastmcp import FastMCP
from mcp.server.fastmcp import FastMCP  # 严格匹配官方 cli 期待的类型

# 导入诊断工具
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 确保工作目录是项目根目录
os.chdir(project_root)

from diagnostic_tools import DiagnosticDataTools

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Diagnostic_MCP_Server")

# 创建 FastMCP 实例
mcp = FastMCP("Diagnostic", host="127.0.0.1", port=8005)

# 初始化诊断工具
diagnostic_tools = DiagnosticDataTools()


def log_tool_call(func):
    """装饰器：记录工具调用的日志"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        method_name = func.__name__

        # 记录调用信息
        logger.info(f"=" * 80)
        logger.info(f"调用方法: {method_name}")

        # 记录参数
        if kwargs:
            try:
                params_str = json.dumps(kwargs, ensure_ascii=False, indent=2)
            except (TypeError, ValueError):
                params_str = str(kwargs)
            logger.info(f"参数信息:\n{params_str}")
        else:
            logger.info("参数信息: 无")

        # 执行方法
        try:
            result = func(*args, **kwargs)

            # 记录返回状态
            logger.info(f"返回状态: SUCCESS")

            # 记录返回结果摘要
            if isinstance(result, dict):
                summary = {k: v if not isinstance(v, (list, dict)) else f"<{type(v).__name__} with {len(v)} items>"
                          for k, v in list(result.items())[:5]}
                logger.info(f"返回结果摘要: {json.dumps(summary, ensure_ascii=False)}")
            else:
                logger.info(f"返回结果: {result}")

            logger.info(f"=" * 80)
            return result

        except Exception as e:
            # 记录错误状态
            logger.error(f"返回状态: ERROR")
            logger.error(f"错误信息: {str(e)}")
            logger.error(f"=" * 80)
            raise

    return wrapper


# ============================================================================
# 日志工具
# ============================================================================

@mcp.tool()
@log_tool_call
def get_error_logs(limit: int = 20) -> Dict[str, Any]:
    """获取所有错误日志。

    用于了解系统中发生了什么错误。

    Args:
        limit: 返回的最大日志条数，默认 20

    Returns:
        Dict: 包含错误日志的字典
            - status: 状态（success/error）
            - count: 日志条数
            - data: 日志列表
    """
    return diagnostic_tools.get_error_logs(limit=limit)


@mcp.tool()
@log_tool_call
def get_logs_by_time_range(
    start_time: str,
    end_time: str,
    limit: int = 50
) -> Dict[str, Any]:
    """按时间范围获取日志。

    用于查看特定时间段内发生了什么。

    Args:
        start_time: 开始时间，格式: 2026-05-19T10:20:00Z
        end_time: 结束时间，格式: 2026-05-19T10:30:00Z
        limit: 返回的最大日志条数，默认 50

    Returns:
        Dict: 包含日志的字典
            - status: 状态
            - count: 日志条数
            - time_range: 时间范围
            - data: 日志列表
    """
    return diagnostic_tools.get_logs_by_time_range(
        start_time=start_time,
        end_time=end_time,
        limit=limit
    )


@mcp.tool()
@log_tool_call
def get_logs_by_service(
    service: str,
    level: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """按服务名称获取日志。

    用于查看特定服务的日志。

    Args:
        service: 服务名称，如 'user-service' 或 'api-gateway'
        level: 日志级别，如 'ERROR', 'WARN', 'INFO'，可选
        limit: 返回的最大日志条数，默认 20

    Returns:
        Dict: 包含日志的字典
            - status: 状态
            - count: 日志条数
            - filter: 过滤条件
            - data: 日志列表
    """
    return diagnostic_tools.get_logs_by_service(
        service=service,
        level=level,
        limit=limit
    )


@mcp.tool()
@log_tool_call
def get_logs_by_keyword(
    keyword: str,
    limit: int = 20
) -> Dict[str, Any]:
    """按关键字搜索日志。

    用于查找包含特定内容的日志。

    Args:
        keyword: 搜索关键字，如 'connection', 'timeout'
        limit: 返回的最大日志条数，默认 20

    Returns:
        Dict: 包含日志的字典
            - status: 状态
            - count: 日志条数
            - keyword: 搜索关键字
            - data: 日志列表
    """
    return diagnostic_tools.get_logs_by_keyword(
        keyword=keyword,
        limit=limit
    )


# ============================================================================
# 指标工具
# ============================================================================

@mcp.tool()
@log_tool_call
def get_metrics_by_name(
    metric_name: str,
    limit: int = 60
) -> Dict[str, Any]:
    """按指标名称获取指标数据。

    用于查看特定指标的时间序列。

    Args:
        metric_name: 指标名称，如 'db_connections', 'request_latency_ms', 'error_rate_percent'
        limit: 返回的最大数据点数，默认 60

    Returns:
        Dict: 包含指标数据的字典
            - status: 状态
            - count: 数据点数
            - metric_name: 指标名称
            - statistics: 统计信息（min, max, avg）
            - data: 指标数据列表
    """
    return diagnostic_tools.get_metrics_by_name(
        metric_name=metric_name,
        limit=limit
    )


@mcp.tool()
@log_tool_call
def get_metrics_by_time_range(
    start_time: str,
    end_time: str,
    metric_name: Optional[str] = None
) -> Dict[str, Any]:
    """按时间范围获取指标数据。

    用于查看特定时间段内的指标变化。

    Args:
        start_time: 开始时间，格式: 2026-05-19T10:20:00Z
        end_time: 结束时间，格式: 2026-05-19T10:30:00Z
        metric_name: 指标名称，可选。如果不指定，返回所有指标

    Returns:
        Dict: 包含指标数据的字典
            - status: 状态
            - count: 数据点数
            - time_range: 时间范围
            - metric_name: 指标名称
            - data: 指标数据列表
    """
    return diagnostic_tools.get_metrics_by_time_range(
        start_time=start_time,
        end_time=end_time,
        metric_name=metric_name
    )


@mcp.tool()
@log_tool_call
def get_metrics_anomalies(
    threshold_percentile: float = 0.8
) -> Dict[str, Any]:
    """获取异常指标。

    用于快速发现哪些指标出现了异常。

    Args:
        threshold_percentile: 异常阈值百分位数，默认 0.8（即超过 80% 的值为异常）

    Returns:
        Dict: 包含异常指标的字典
            - status: 状态
            - threshold_percentile: 阈值百分位数
            - anomalies: 异常指标字典
    """
    return diagnostic_tools.get_metrics_anomalies(
        threshold_percentile=threshold_percentile
    )


# ============================================================================
# 事件工具
# ============================================================================

@mcp.tool()
@log_tool_call
def get_alerts() -> Dict[str, Any]:
    """获取所有告警事件。

    用于发现系统中存在的问题。

    Returns:
        Dict: 包含告警事件的字典
            - status: 状态
            - count: 告警数
            - data: 告警列表
    """
    return diagnostic_tools.get_alerts()


@mcp.tool()
@log_tool_call
def get_events(limit: int = 20) -> Dict[str, Any]:
    """获取所有事件。

    用于了解系统中发生的重要事件。

    Args:
        limit: 返回的最大事件数，默认 20

    Returns:
        Dict: 包含事件的字典
            - status: 状态
            - count: 事件数
            - data: 事件列表
    """
    return diagnostic_tools.get_events(limit=limit)


@mcp.tool()
@log_tool_call
def get_events_by_type(
    event_type: str,
    limit: int = 20
) -> Dict[str, Any]:
    """按事件类型获取事件。

    用于查看特定类型的事件。

    Args:
        event_type: 事件类型，如 'deployment', 'alert'
        limit: 返回的最大事件数，默认 20

    Returns:
        Dict: 包含事件的字典
            - status: 状态
            - count: 事件数
            - event_type: 事件类型
            - data: 事件列表
    """
    return diagnostic_tools.get_events_by_type(
        event_type=event_type,
        limit=limit
    )


@mcp.tool()
@log_tool_call
def get_events_by_time_range(
    start_time: str,
    end_time: str
) -> Dict[str, Any]:
    """按时间范围获取事件。

    用于查看特定时间段内发生的事件。

    Args:
        start_time: 开始时间，格式: 2026-05-19T10:20:00Z
        end_time: 结束时间，格式: 2026-05-19T10:30:00Z

    Returns:
        Dict: 包含事件的字典
            - status: 状态
            - count: 事件数
            - time_range: 时间范围
            - data: 事件列表
    """
    return diagnostic_tools.get_events_by_time_range(
        start_time=start_time,
        end_time=end_time
    )


@mcp.tool()
@log_tool_call
def get_deployment_events(limit: int = 10) -> Dict[str, Any]:
    """获取所有部署事件。

    用于了解系统的部署历史。

    Args:
        limit: 返回的最大事件数，默认 10

    Returns:
        Dict: 包含部署事件的字典
            - status: 状态
            - count: 事件数
            - data: 事件列表
    """
    return diagnostic_tools.get_deployment_events(limit=limit)


# ============================================================================
# 时间工具
# ============================================================================

@mcp.tool()
def get_current_time(timezone: str = "Asia/Shanghai") -> str:
    """获取当前时间。

    用于在诊断报告中记录诊断时间，或判断告警的时间范围。

    Args:
        timezone: 时区，默认为 Asia/Shanghai（北京时间）

    Returns:
        str: 格式化的当前时间，格式为 YYYY-MM-DD HH:MM:SS
    """
    try:
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)
        return now.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        logger.error(f"获取时间失败: {e}")
        return f"获取时间失败: {str(e)}"


# ============================================================================
# 服务启动
# ============================================================================

if __name__ == "__main__":
    logger.info("启动诊断工具 MCP Server...")
    logger.info(f"服务器名称: {mcp.name}")
    logger.info(f"可用工具数: 12")

    mcp.run(transport="streamable-http")
