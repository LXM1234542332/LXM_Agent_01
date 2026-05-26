"""
诊断数据工具 - JSON 版本
使用 function calling 格式定义工具
支持 Agent 按需调用获取数据
"""

import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

# 使用相对于本文件的路径，兼容 Windows 和 WSL
DATA_DIR = str(Path(__file__).parent / "data")
LOGS_FILE = os.path.join(DATA_DIR, "logs.json")
METRICS_FILE = os.path.join(DATA_DIR, "metrics.json")
EVENTS_FILE = os.path.join(DATA_DIR, "events.json")

# ============================================================================
# Function Calling 工具定义
# ============================================================================

DIAGNOSTIC_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_alerts",
            "description": "获取所有告警事件。用于发现系统中存在的问题。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_error_logs",
            "description": "获取所有错误日志。用于了解系统中发生了什么错误。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "返回的最大日志条数，默认 20"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_logs_by_time_range",
            "description": "按时间范围获取日志。用于查看特定时间段内发生了什么。",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_time": {
                        "type": "string",
                        "description": "开始时间，格式: 2026-05-19T10:20:00Z"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "结束时间，格式: 2026-05-19T10:30:00Z"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回的最大日志条数，默认 50"
                    }
                },
                "required": ["start_time", "end_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_logs_by_service",
            "description": "按服务名称获取日志。用于查看特定服务的日志。",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "服务名称，如 'user-service' 或 'api-gateway'"
                    },
                    "level": {
                        "type": "string",
                        "description": "日志级别，如 'ERROR', 'WARN', 'INFO'，可选"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回的最大日志条数，默认 20"
                    }
                },
                "required": ["service"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_logs_by_keyword",
            "description": "按关键字搜索日志。用于查找包含特定内容的日志。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键字，如 'connection', 'timeout'"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回的最大日志条数，默认 20"
                    }
                },
                "required": ["keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_metrics_by_name",
            "description": "按指标名称获取指标数据。用于查看特定指标的时间序列。",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric_name": {
                        "type": "string",
                        "description": "指标名称，如 'db_connections', 'request_latency_ms', 'error_rate_percent'"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回的最大数据点数，默认 60"
                    }
                },
                "required": ["metric_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_metrics_by_time_range",
            "description": "按时间范围获取指标数据。用于查看特定时间段内的指标变化。",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_time": {
                        "type": "string",
                        "description": "开始时间，格式: 2026-05-19T10:20:00Z"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "结束时间，格式: 2026-05-19T10:30:00Z"
                    },
                    "metric_name": {
                        "type": "string",
                        "description": "指标名称，可选。如果不指定，返回所有指标"
                    }
                },
                "required": ["start_time", "end_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_metrics_anomalies",
            "description": "获取异常指标。用于快速发现哪些指标出现了异常。",
            "parameters": {
                "type": "object",
                "properties": {
                    "threshold_percentile": {
                        "type": "number",
                        "description": "异常阈值百分位数，默认 0.8（即超过 80% 的值为异常）"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_events",
            "description": "获取所有事件。用于了解系统中发生的重要事件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "返回的最大事件数，默认 20"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_events_by_type",
            "description": "按事件类型获取事件。用于查看特定类型的事件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_type": {
                        "type": "string",
                        "description": "事件类型，如 'deployment', 'alert'"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回的最大事件数，默认 20"
                    }
                },
                "required": ["event_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_events_by_time_range",
            "description": "按时间范围获取事件。用于查看特定时间段内发生的事件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_time": {
                        "type": "string",
                        "description": "开始时间，格式: 2026-05-19T10:20:00Z"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "结束时间，格式: 2026-05-19T10:30:00Z"
                    }
                },
                "required": ["start_time", "end_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_deployment_events",
            "description": "获取所有部署事件。用于了解系统的部署历史。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "返回的最大事件数，默认 10"
                    }
                },
                "required": []
            }
        }
    }
]

# ============================================================================
# 数据工具实现
# ============================================================================

class DiagnosticDataTools:
    def __init__(self):
        self.logs = self._load_logs()
        self.metrics = self._load_metrics()
        self.events = self._load_events()

    def _load_logs(self) -> List[Dict]:
        """加载日志数据"""
        try:
            with open(LOGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def _load_metrics(self) -> List[Dict]:
        """加载指标数据"""
        try:
            with open(METRICS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def _load_events(self) -> List[Dict]:
        """加载事件数据"""
        try:
            with open(EVENTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def get_alerts(self) -> Dict[str, Any]:
        """获取所有告警事件"""
        alerts = [e for e in self.events if e.get("event_type") == "alert"]
        alerts = sorted(alerts, key=lambda x: x["timestamp"], reverse=True)

        return {
            "status": "success",
            "count": len(alerts),
            "data": alerts
        }

    def get_error_logs(self, limit: int = 20) -> Dict[str, Any]:
        """获取所有错误日志"""
        error_logs = [log for log in self.logs if log.get("level") == "ERROR"]
        error_logs = sorted(error_logs, key=lambda x: x["timestamp"], reverse=True)[:limit]

        return {
            "status": "success",
            "count": len(error_logs),
            "data": error_logs
        }

    def get_logs_by_time_range(self, start_time: str, end_time: str, limit: int = 50) -> Dict[str, Any]:
        """按时间范围获取日志"""
        logs = [log for log in self.logs
                if start_time <= log["timestamp"] <= end_time]
        logs = sorted(logs, key=lambda x: x["timestamp"])[:limit]

        return {
            "status": "success",
            "count": len(logs),
            "time_range": {"start": start_time, "end": end_time},
            "data": logs
        }

    def get_logs_by_service(self, service: str, level: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        """按服务获取日志"""
        logs = [log for log in self.logs if log.get("service") == service]

        if level:
            logs = [log for log in logs if log.get("level") == level]

        logs = sorted(logs, key=lambda x: x["timestamp"], reverse=True)[:limit]

        return {
            "status": "success",
            "count": len(logs),
            "filter": {"service": service, "level": level},
            "data": logs
        }

    def get_logs_by_keyword(self, keyword: str, limit: int = 20) -> Dict[str, Any]:
        """按关键字搜索日志"""
        keyword_lower = keyword.lower()
        logs = [log for log in self.logs
                if keyword_lower in log.get("message", "").lower()
                or keyword_lower in log.get("error", "").lower()]
        logs = sorted(logs, key=lambda x: x["timestamp"], reverse=True)[:limit]

        return {
            "status": "success",
            "count": len(logs),
            "keyword": keyword,
            "data": logs
        }

    def get_metrics_by_name(self, metric_name: str, limit: int = 60) -> Dict[str, Any]:
        """按指标名称获取指标"""
        metrics = [m for m in self.metrics if m.get("metric_name") == metric_name]
        metrics = sorted(metrics, key=lambda x: x["timestamp"])[:limit]

        # 计算统计信息
        if metrics:
            values = [m["value"] for m in metrics]
            stats = {
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values)
            }
        else:
            stats = {}

        return {
            "status": "success",
            "count": len(metrics),
            "metric_name": metric_name,
            "statistics": stats,
            "data": metrics
        }

    def get_metrics_by_time_range(self, start_time: str, end_time: str, metric_name: Optional[str] = None) -> Dict[str, Any]:
        """按时间范围获取指标"""
        metrics = [m for m in self.metrics
                   if start_time <= m["timestamp"] <= end_time]

        if metric_name:
            metrics = [m for m in metrics if m.get("metric_name") == metric_name]

        metrics = sorted(metrics, key=lambda x: x["timestamp"])

        return {
            "status": "success",
            "count": len(metrics),
            "time_range": {"start": start_time, "end": end_time},
            "metric_name": metric_name,
            "data": metrics
        }

    def get_metrics_anomalies(self, threshold_percentile: float = 0.8) -> Dict[str, Any]:
        """获取异常指标"""
        metric_names = set(m["metric_name"] for m in self.metrics)
        anomalies = {}

        for metric_name in metric_names:
            metrics = [m for m in self.metrics if m.get("metric_name") == metric_name]
            values = [m["value"] for m in metrics]

            if values:
                # 计算阈值
                sorted_values = sorted(values)
                threshold_index = int(len(sorted_values) * threshold_percentile)
                threshold = sorted_values[threshold_index]

                # 找出异常值
                anomaly_points = []
                for m in sorted(metrics, key=lambda x: x["timestamp"], reverse=True):
                    if m["value"] > threshold:
                        anomaly_points.append({
                            "timestamp": m["timestamp"],
                            "value": m["value"]
                        })
                    if len(anomaly_points) >= 5:
                        break

                if anomaly_points:
                    anomalies[metric_name] = {
                        "threshold": threshold,
                        "anomaly_points": anomaly_points
                    }

        return {
            "status": "success",
            "threshold_percentile": threshold_percentile,
            "anomalies": anomalies
        }

    def get_events(self, limit: int = 20) -> Dict[str, Any]:
        """获取所有事件"""
        events = sorted(self.events, key=lambda x: x["timestamp"], reverse=True)[:limit]

        return {
            "status": "success",
            "count": len(events),
            "data": events
        }

    def get_events_by_type(self, event_type: str, limit: int = 20) -> Dict[str, Any]:
        """按事件类型获取事件"""
        events = [e for e in self.events if e.get("event_type") == event_type]
        events = sorted(events, key=lambda x: x["timestamp"], reverse=True)[:limit]

        return {
            "status": "success",
            "count": len(events),
            "event_type": event_type,
            "data": events
        }

    def get_events_by_time_range(self, start_time: str, end_time: str) -> Dict[str, Any]:
        """按时间范围获取事件"""
        events = [e for e in self.events
                  if start_time <= e["timestamp"] <= end_time]
        events = sorted(events, key=lambda x: x["timestamp"])

        return {
            "status": "success",
            "count": len(events),
            "time_range": {"start": start_time, "end": end_time},
            "data": events
        }

    def get_deployment_events(self, limit: int = 10) -> Dict[str, Any]:
        """获取所有部署事件"""
        events = [e for e in self.events if e.get("event_type") == "deployment"]
        events = sorted(events, key=lambda x: x["timestamp"], reverse=True)[:limit]

        return {
            "status": "success",
            "count": len(events),
            "data": events
        }

    def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """通用工具调用接口"""
        if tool_name == "get_alerts":
            return self.get_alerts()
        elif tool_name == "get_error_logs":
            return self.get_error_logs(limit=kwargs.get("limit", 20))
        elif tool_name == "get_logs_by_time_range":
            return self.get_logs_by_time_range(
                start_time=kwargs.get("start_time"),
                end_time=kwargs.get("end_time"),
                limit=kwargs.get("limit", 50)
            )
        elif tool_name == "get_logs_by_service":
            return self.get_logs_by_service(
                service=kwargs.get("service"),
                level=kwargs.get("level"),
                limit=kwargs.get("limit", 20)
            )
        elif tool_name == "get_logs_by_keyword":
            return self.get_logs_by_keyword(
                keyword=kwargs.get("keyword"),
                limit=kwargs.get("limit", 20)
            )
        elif tool_name == "get_metrics_by_name":
            return self.get_metrics_by_name(
                metric_name=kwargs.get("metric_name"),
                limit=kwargs.get("limit", 60)
            )
        elif tool_name == "get_metrics_by_time_range":
            return self.get_metrics_by_time_range(
                start_time=kwargs.get("start_time"),
                end_time=kwargs.get("end_time"),
                metric_name=kwargs.get("metric_name")
            )
        elif tool_name == "get_metrics_anomalies":
            return self.get_metrics_anomalies(
                threshold_percentile=kwargs.get("threshold_percentile", 0.8)
            )
        elif tool_name == "get_events":
            return self.get_events(limit=kwargs.get("limit", 20))
        elif tool_name == "get_events_by_type":
            return self.get_events_by_type(
                event_type=kwargs.get("event_type"),
                limit=kwargs.get("limit", 20)
            )
        elif tool_name == "get_events_by_time_range":
            return self.get_events_by_time_range(
                start_time=kwargs.get("start_time"),
                end_time=kwargs.get("end_time")
            )
        elif tool_name == "get_deployment_events":
            return self.get_deployment_events(limit=kwargs.get("limit", 10))
        else:
            return {
                "status": "error",
                "message": f"Unknown tool: {tool_name}"
            }


if __name__ == "__main__":
    # 测试工具
    tools = DiagnosticDataTools()

    print("=" * 80)
    print("测试诊断数据工具")
    print("=" * 80)

    # 测试 get_alerts
    print("\n[1] 获取告警")
    print("-" * 80)
    result = tools.get_alerts()
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 测试 get_error_logs
    print("\n[2] 获取错误日志")
    print("-" * 80)
    result = tools.get_error_logs(limit=3)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 测试 get_metrics_by_name
    print("\n[3] 获取数据库连接数指标")
    print("-" * 80)
    result = tools.get_metrics_by_name("db_connections", limit=10)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 测试 get_events
    print("\n[4] 获取所有事件")
    print("-" * 80)
    result = tools.get_events()
    print(json.dumps(result, indent=2, ensure_ascii=False))

    print("\n" + "=" * 80)
    print("工具测试完成")
    print("=" * 80)
