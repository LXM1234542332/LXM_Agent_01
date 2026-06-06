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
from dotenv import load_dotenv

load_dotenv()

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
    },
    {
        "type": "function",
        "function": {
            "name": "get_service_dependencies",
            "description": "获取服务的依赖关系。用于理解服务间的调用关系。",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "服务名称，如 'api-gateway' 或 'user-service'"
                    }
                },
                "required": ["service"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trace_details",
            "description": "获取链路的详细信息。用于查看请求在各个服务中的执行情况。",
            "parameters": {
                "type": "object",
                "properties": {
                    "trace_id": {
                        "type": "string",
                        "description": "链路 ID，如 'trace_12345'"
                    }
                },
                "required": ["trace_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_slow_traces",
            "description": "获取超过阈值的慢链路。用于发现性能问题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "threshold_ms": {
                        "type": "integer",
                        "description": "时间阈值（毫秒），如 1000"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回的最大链路数，默认 10"
                    }
                },
                "required": ["threshold_ms"]
            }
        }
    }
]

# ============================================================================
# 数据工具实现
# ============================================================================

class DiagnosticDataTools:
    def __init__(self, scenario_id: Optional[str] = None):
        self.scenario_id = scenario_id or os.getenv('SCENARIO_ID', 'scenario1')
        self.data_dir = Path(DATA_DIR)
        self.scenario_dir = self.data_dir / self.scenario_id
        self.logs = self._load_logs()
        self.metrics = self._load_metrics()
        self.events = self._load_events()
        self.traces = self._load_traces()
        self.jvm_gc_logs = self._load_jvm_gc_logs()
        self.slow_queries = self._load_slow_queries()
        self.service_dependencies = self._load_service_dependencies()

    def _load_logs(self) -> List[Dict]:
        """加载日志数据"""
        try:
            logs_file = self.scenario_dir / "logs.json"
            with open(logs_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def _load_metrics(self) -> List[Dict]:
        """加载指标数据"""
        try:
            metrics_file = self.scenario_dir / "metrics.json"
            with open(metrics_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def _load_events(self) -> List[Dict]:
        """加载事件数据"""
        try:
            events_file = self.scenario_dir / "events.json"
            with open(events_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def _load_traces(self) -> List[Dict]:
        """加载链路追踪数据"""
        try:
            traces_file = self.scenario_dir / "traces.json"
            with open(traces_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def _load_jvm_gc_logs(self) -> List[Dict]:
        """加载 JVM GC 事件日志（场景专属，不存在时返回空列表）"""
        try:
            f_path = self.scenario_dir / "jvm_gc_logs.json"
            with open(f_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def _load_slow_queries(self) -> List[Dict]:
        """加载慢查询日志（场景专属，不存在时返回空列表）"""
        try:
            f_path = self.scenario_dir / "slow_queries.json"
            with open(f_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def _load_service_dependencies(self) -> Dict[str, List[str]]:
        """加载服务依赖关系"""
        try:
            deps_file = self.data_dir / "service_dependencies.json"
            with open(deps_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def switch_scenario(self, scenario_id: str):
        """动态切换场景"""
        self.scenario_id = scenario_id
        self.scenario_dir = self.data_dir / scenario_id
        self.logs = self._load_logs()
        self.metrics = self._load_metrics()
        self.events = self._load_events()
        self.traces = self._load_traces()
        self.jvm_gc_logs = self._load_jvm_gc_logs()
        self.slow_queries = self._load_slow_queries()

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

                # 找出异常值（保留 service/instance 供 ExactValuePool 提取）
                anomaly_points = []
                for m in sorted(metrics, key=lambda x: x["timestamp"], reverse=True):
                    if m["value"] >= threshold:
                        point = {
                            "timestamp": m["timestamp"],
                            "value": m["value"],
                        }
                        if "service" in m:
                            point["service"] = m["service"]
                        if "instance" in m:
                            point["instance"] = m["instance"]
                        anomaly_points.append(point)
                    if len(anomaly_points) >= 5:
                        break

                if anomaly_points:
                    # 汇总出现在哪些服务
                    services_with_anomaly = list(dict.fromkeys(
                        p["service"] for p in anomaly_points if "service" in p
                    ))
                    anomalies[metric_name] = {
                        "service": services_with_anomaly[0] if len(services_with_anomaly) == 1 else services_with_anomaly,
                        "threshold": threshold,
                        "anomaly_points": anomaly_points,
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

    def get_service_dependencies(self, service: str) -> Dict[str, Any]:
        """获取服务的依赖关系"""
        dependencies = self.service_dependencies.get(service, [])

        return {
            "status": "success",
            "service": service,
            "dependencies": dependencies,
            "count": len(dependencies)
        }

    def get_trace_details(self, trace_id: str) -> Dict[str, Any]:
        """获取链路的详细信息"""
        trace = None
        for t in self.traces:
            if t.get("trace_id") == trace_id:
                trace = t
                break

        if not trace:
            return {
                "status": "error",
                "message": f"Trace {trace_id} not found"
            }

        return {
            "status": "success",
            "trace_id": trace_id,
            "total_duration_ms": trace.get("total_duration_ms"),
            "status_code": trace.get("status"),
            "spans_count": len(trace.get("spans", [])),
            "data": trace
        }

    def get_slow_traces(self, threshold_ms: int, limit: int = 10) -> Dict[str, Any]:
        """获取超过阈值的慢链路"""
        slow_traces = [t for t in self.traces if t.get("total_duration_ms", 0) > threshold_ms]
        slow_traces = sorted(slow_traces, key=lambda x: x.get("total_duration_ms", 0), reverse=True)[:limit]

        return {
            "status": "success",
            "threshold_ms": threshold_ms,
            "count": len(slow_traces),
            "data": slow_traces
        }

    def get_jvm_metrics(self, service: str, instance: Optional[str] = None, limit: int = 60) -> Dict[str, Any]:
        """
        查询指定服务的 JVM 运行时指标时序，包括 heap 使用量、GC 次数/暂停时长、线程数、session 缓存大小。
        可按 instance 过滤单个 pod。返回时序数据和各指标的统计摘要（min/max/avg/trend）。
        适用于排查 JVM 内存泄漏、GC 风暴、线程池饱和等 JVM 层面问题。
        """
        jvm_metric_prefixes = ("jvm_", "session_cache_size")
        records = [
            m for m in self.metrics
            if m.get("service") == service
            and any(m.get("metric_name", "").startswith(p) for p in jvm_metric_prefixes)
            and (instance is None or m.get("instance") == instance)
        ]
        records = sorted(records, key=lambda x: x["timestamp"])[:limit]

        # 按指标名分组统计
        by_metric: Dict[str, list] = {}
        for r in records:
            by_metric.setdefault(r["metric_name"], []).append(r)

        summary = {}
        for metric_name, pts in by_metric.items():
            vals = [p["value"] for p in pts]
            if not vals:
                continue
            trend = "rising" if vals[-1] > vals[0] * 1.1 else ("falling" if vals[-1] < vals[0] * 0.9 else "stable")
            summary[metric_name] = {
                "min": round(min(vals), 3),
                "max": round(max(vals), 3),
                "avg": round(sum(vals) / len(vals), 3),
                "latest": vals[-1],
                "trend": trend,
                "sample_count": len(vals),
            }

        # GC 事件摘要（来自 jvm_gc_logs）
        gc_events = [
            g for g in self.jvm_gc_logs
            if g.get("service") == service
            and (instance is None or g.get("instance") == instance)
        ]
        gc_summary = {}
        if gc_events:
            full_gcs = [g for g in gc_events if g.get("gc_type") == "FullGC"]
            gc_summary = {
                "total_gc_events": len(gc_events),
                "full_gc_count": len(full_gcs),
                "max_pause_ms": max((g.get("pause_ms", 0) for g in gc_events), default=0),
                "promotion_failed_count": sum(1 for g in gc_events if g.get("promotion_failed")),
                "recent_gc_events": sorted(gc_events, key=lambda x: x["timestamp"], reverse=True)[:5],
            }

        return {
            "status": "success",
            "service": service,
            "instance": instance,
            "jvm_metric_summary": summary,
            "gc_event_summary": gc_summary,
            "data": records,
        }

    def get_queue_metrics(self, service: str, limit: int = 60) -> Dict[str, Any]:
        """
        查询消息队列相关指标，包括队列深度、消费速率、发布速率、消费者延迟。
        用于判断队列是否积压、消费能力是否下降，以及上游依赖（如 user-service）是否导致消费阻塞。
        """
        queue_metric_names = ("queue_depth", "queue_consume_rate", "queue_publish_rate", "consumer_lag_ms")
        records = [
            m for m in self.metrics
            if m.get("service") == service
            and m.get("metric_name") in queue_metric_names
        ]
        records = sorted(records, key=lambda x: x["timestamp"])[:limit]

        by_metric: Dict[str, list] = {}
        for r in records:
            by_metric.setdefault(r["metric_name"], []).append(r)

        summary = {}
        for metric_name, pts in by_metric.items():
            vals = [p["value"] for p in pts]
            if not vals:
                continue
            trend = "rising" if vals[-1] > vals[0] * 1.1 else ("falling" if vals[-1] < vals[0] * 0.9 else "stable")
            summary[metric_name] = {
                "min": round(min(vals), 3),
                "max": round(max(vals), 3),
                "avg": round(sum(vals) / len(vals), 3),
                "latest": vals[-1],
                "trend": trend,
            }

        # 计算积压判断
        depth_pts = by_metric.get("queue_depth", [])
        consume_pts = by_metric.get("queue_consume_rate", [])
        publish_pts = by_metric.get("queue_publish_rate", [])
        backlog_analysis = {}
        if depth_pts and consume_pts and publish_pts:
            latest_depth = depth_pts[-1]["value"]
            latest_consume = consume_pts[-1]["value"]
            latest_publish = publish_pts[-1]["value"]
            backlog_analysis = {
                "latest_queue_depth": latest_depth,
                "latest_consume_rate": latest_consume,
                "latest_publish_rate": latest_publish,
                "net_rate": round(latest_publish - latest_consume, 2),
                "is_backlogging": latest_publish > latest_consume * 1.1,
                "estimated_drain_seconds": round(latest_depth / latest_consume, 1) if latest_consume > 0 else None,
            }

        return {
            "status": "success",
            "service": service,
            "queue_metric_summary": summary,
            "backlog_analysis": backlog_analysis,
            "data": records,
        }

    def get_slow_queries(self, service: Optional[str] = None, threshold_ms: int = 100, limit: int = 20) -> Dict[str, Any]:
        """
        查询慢 SQL/数据库查询记录，按执行耗时降序排列。
        可过滤服务名和最小耗时阈值。返回 query_text、duration_ms、rows_examined、index_used 等字段。
        适用于排查数据库层面的性能问题，如全表扫描、缺少索引、表膨胀导致查询变慢等。
        """
        queries = [
            q for q in self.slow_queries
            if q.get("duration_ms", 0) >= threshold_ms
            and (service is None or q.get("service") == service)
        ]
        queries = sorted(queries, key=lambda x: x.get("duration_ms", 0), reverse=True)[:limit]

        no_index = [q for q in queries if not q.get("index_used", True)]
        stats = {}
        if queries:
            durations = [q["duration_ms"] for q in queries]
            rows = [q.get("rows_examined", 0) for q in queries]
            stats = {
                "total_slow_queries": len(queries),
                "no_index_count": len(no_index),
                "max_duration_ms": max(durations),
                "avg_duration_ms": round(sum(durations) / len(durations), 1),
                "max_rows_examined": max(rows) if rows else 0,
            }

        return {
            "status": "success",
            "service": service,
            "threshold_ms": threshold_ms,
            "statistics": stats,
            "no_index_queries": no_index,
            "data": queries,
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
        elif tool_name == "get_service_dependencies":
            return self.get_service_dependencies(service=kwargs.get("service"))
        elif tool_name == "get_trace_details":
            return self.get_trace_details(trace_id=kwargs.get("trace_id"))
        elif tool_name == "get_slow_traces":
            return self.get_slow_traces(
                threshold_ms=kwargs.get("threshold_ms"),
                limit=kwargs.get("limit", 10)
            )
        elif tool_name == "get_jvm_metrics":
            return self.get_jvm_metrics(
                service=kwargs.get("service"),
                instance=kwargs.get("instance"),
                limit=kwargs.get("limit", 60)
            )
        elif tool_name == "get_queue_metrics":
            return self.get_queue_metrics(
                service=kwargs.get("service"),
                limit=kwargs.get("limit", 60)
            )
        elif tool_name == "get_slow_queries":
            return self.get_slow_queries(
                service=kwargs.get("service"),
                threshold_ms=kwargs.get("threshold_ms", 100),
                limit=kwargs.get("limit", 20)
            )
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


# ============================================================================
# 全局实例（供 MCP 服务器和 execute() 方法使用）
# ============================================================================

# 创建全局实例，从环境变量读取初始场景
diagnostic_tools = DiagnosticDataTools(scenario_id=os.getenv('SCENARIO_ID', 'scenario1'))
