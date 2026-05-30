#!/usr/bin/env python3
"""
生成具有问题-原因闭环的场景数据
每个场景都有完整的因果链条，确保 trace_id、时间戳等都对应
"""

import json
from pathlib import Path
from datetime import datetime, timedelta

class ClosedLoopScenarioGenerator:
    def __init__(self):
        self.data_dir = Path("data")
        self.scenarios_config = self._load_scenarios_config()

    def _load_scenarios_config(self):
        """加载场景配置"""
        with open(self.data_dir / "scenarios.json", "r", encoding="utf-8") as f:
            return json.load(f)

    def generate_all_scenarios(self):
        """为所有场景生成闭环数据"""
        print("开始生成具有问题-原因闭环的场景数据...\n")

        # 为每个场景生成数据
        for scenario in self.scenarios_config:
            scenario_id = scenario["id"]
            print(f"[{scenario_id}] 生成数据...")

            # 获取该场景的故障链条定义
            fault_chain = self._get_fault_chain_definition(scenario_id)

            if fault_chain:
                # 基于链条生成 JSON 数据
                events = self._generate_events(scenario, fault_chain)
                logs = self._generate_logs(scenario, fault_chain)
                metrics = self._generate_metrics(scenario, fault_chain)
                traces = self._generate_traces(scenario, fault_chain)

                # 保存数据
                scenario_dir = self.data_dir / scenario_id
                scenario_dir.mkdir(parents=True, exist_ok=True)

                self._save_json(scenario_dir / "events.json", events)
                self._save_json(scenario_dir / "logs.json", logs)
                self._save_json(scenario_dir / "metrics.json", metrics)
                self._save_json(scenario_dir / "traces.json", traces)

                print(f"[{scenario_id}] 完成！")
                print(f"  - events.json: {len(events)} 条事件")
                print(f"  - logs.json: {len(logs)} 条日志")
                print(f"  - metrics.json: {len(metrics)} 条指标")
                print(f"  - traces.json: {len(traces)} 条链路\n")

        print("所有场景生成完成！")

    def _get_fault_chain_definition(self, scenario_id):
        """获取每个场景的故障链条定义"""
        chains = {
            "scenario1": self._chain_cascade_failure(),
            "scenario2": self._chain_db_connection_leak(),
            "scenario3": self._chain_memory_leak_gc(),
            "scenario4": self._chain_cpu_high(),
            "scenario5": self._chain_memory_high(),
            "scenario6": self._chain_disk_full(),
            "scenario7": self._chain_queue_backlog(),
            "scenario8": self._chain_db_down(),
        }
        return chains.get(scenario_id)

    def _chain_cascade_failure(self):
        """场景1：级联故障"""
        return {
            "name": "级联故障",
            "root_cause_service": "payment-service",
            "timeline": [
                {"time": "2026-05-19T10:15:00Z", "event": "deployment", "service": "payment-service", "desc": "部署 v2.3.1"},
                {"time": "2026-05-19T10:15:30Z", "event": "error_start", "service": "payment-service", "desc": "支付超时开始"},
                {"time": "2026-05-19T10:16:00Z", "event": "cascade", "service": "order-service", "desc": "订单服务超时"},
                {"time": "2026-05-19T10:17:00Z", "event": "cascade", "service": "api-gateway", "desc": "网关请求堆积"},
            ],
            "traces": [
                {
                    "trace_id": "trace_001",
                    "start_time": "2026-05-19T10:16:00Z",
                    "services": ["api-gateway", "order-service", "payment-service"],
                    "status": "error",
                    "duration_ms": 5000,
                    "error_msg": "Payment service timeout"
                },
                {
                    "trace_id": "trace_002",
                    "start_time": "2026-05-19T10:17:00Z",
                    "services": ["api-gateway", "order-service", "payment-service"],
                    "status": "error",
                    "duration_ms": 5100,
                    "error_msg": "Payment service timeout"
                },
                {
                    "trace_id": "trace_003",
                    "start_time": "2026-05-19T10:18:00Z",
                    "services": ["api-gateway", "order-service", "payment-service"],
                    "status": "error",
                    "duration_ms": 5200,
                    "error_msg": "Payment service timeout"
                },
            ],
            "metrics": {
                "error_rate_percent": {"normal": 0.1, "peak": 15},
                "request_latency_ms": {"normal": 100, "peak": 5000},
            }
        }

    def _chain_db_connection_leak(self):
        """场景2：数据库连接泄漏"""
        return {
            "name": "数据库连接泄漏",
            "root_cause_service": "user-service",
            "timeline": [
                {"time": "2026-05-19T10:15:00Z", "event": "deployment", "service": "user-service", "desc": "部署 v1.5.0"},
                {"time": "2026-05-19T10:15:30Z", "event": "error_start", "service": "user-service", "desc": "连接泄漏开始"},
                {"time": "2026-05-19T10:18:00Z", "event": "cascade", "service": "order-service", "desc": "订单服务变慢"},
            ],
            "traces": [
                {
                    "trace_id": "trace_101",
                    "start_time": "2026-05-19T10:16:00Z",
                    "services": ["api-gateway", "user-service"],
                    "status": "error",
                    "duration_ms": 3000,
                    "error_msg": "Connection timeout: Failed to acquire connection from pool"
                },
                {
                    "trace_id": "trace_102",
                    "start_time": "2026-05-19T10:17:00Z",
                    "services": ["api-gateway", "order-service"],
                    "status": "error",
                    "duration_ms": 2500,
                    "error_msg": "Database connection pool exhausted"
                },
            ],
            "metrics": {
                "db_connections": {"normal": 36, "peak": 150},
                "error_rate_percent": {"normal": 0.1, "peak": 12},
            }
        }

    def _chain_memory_leak_gc(self):
        """场景3：内存泄漏导致 GC 停顿"""
        return {
            "name": "内存泄漏导致 GC 停顿",
            "root_cause_service": "order-service",
            "timeline": [
                {"time": "2026-05-19T10:15:00Z", "event": "deployment", "service": "order-service", "desc": "部署 v3.2.0"},
                {"time": "2026-05-19T10:15:30Z", "event": "error_start", "service": "order-service", "desc": "内存泄漏开始"},
                {"time": "2026-05-19T10:18:00Z", "event": "gc_pause", "service": "order-service", "desc": "GC 停顿增加"},
            ],
            "traces": [
                {
                    "trace_id": "trace_201",
                    "start_time": "2026-05-19T10:16:00Z",
                    "services": ["api-gateway", "order-service"],
                    "status": "error",
                    "duration_ms": 1500,
                    "error_msg": "GC pause detected: 500ms"
                },
                {
                    "trace_id": "trace_202",
                    "start_time": "2026-05-19T10:17:00Z",
                    "services": ["api-gateway", "order-service"],
                    "status": "error",
                    "duration_ms": 2000,
                    "error_msg": "GC pause detected: 600ms"
                },
            ],
            "metrics": {
                "memory_usage_percent": {"normal": 50, "peak": 95},
                "gc_time_ms": {"normal": 50, "peak": 500},
                "request_latency_ms": {"normal": 100, "peak": 2000},
            }
        }

    def _chain_cpu_high(self):
        """场景4：CPU 使用率过高"""
        return {
            "name": "CPU 使用率过高",
            "root_cause_service": "search-service",
            "timeline": [
                {"time": "2026-05-19T10:15:00Z", "event": "deployment", "service": "search-service", "desc": "部署 v2.1.0"},
                {"time": "2026-05-19T10:15:30Z", "event": "error_start", "service": "search-service", "desc": "CPU 使用率上升"},
            ],
            "traces": [
                {
                    "trace_id": "trace_301",
                    "start_time": "2026-05-19T10:16:00Z",
                    "services": ["api-gateway", "search-service"],
                    "status": "error",
                    "duration_ms": 3000,
                    "error_msg": "High CPU usage: 95%"
                },
            ],
            "metrics": {
                "cpu_usage_percent": {"normal": 30, "peak": 95},
                "request_latency_ms": {"normal": 100, "peak": 3000},
            }
        }

    def _chain_memory_high(self):
        """场景5：内存使用率过高"""
        return {
            "name": "内存使用率过高",
            "root_cause_service": "cache-service",
            "timeline": [
                {"time": "2026-05-19T10:15:00Z", "event": "deployment", "service": "cache-service", "desc": "部署 v1.8.0"},
                {"time": "2026-05-19T10:15:30Z", "event": "error_start", "service": "cache-service", "desc": "内存使用率上升"},
            ],
            "traces": [
                {
                    "trace_id": "trace_401",
                    "start_time": "2026-05-19T10:16:00Z",
                    "services": ["api-gateway", "cache-service"],
                    "status": "error",
                    "duration_ms": 1000,
                    "error_msg": "Memory pressure: 98%"
                },
            ],
            "metrics": {
                "memory_usage_percent": {"normal": 60, "peak": 98},
            }
        }

    def _chain_disk_full(self):
        """场景6：磁盘空间不足"""
        return {
            "name": "磁盘空间不足",
            "root_cause_service": "database-service",
            "timeline": [
                {"time": "2026-05-19T10:15:00Z", "event": "error_start", "service": "database-service", "desc": "磁盘空间不足"},
                {"time": "2026-05-19T10:16:00Z", "event": "cascade", "service": "user-service", "desc": "数据库写入失败"},
            ],
            "traces": [
                {
                    "trace_id": "trace_501",
                    "start_time": "2026-05-19T10:16:00Z",
                    "services": ["api-gateway", "user-service", "database-service"],
                    "status": "error",
                    "duration_ms": 2000,
                    "error_msg": "Disk full: write failed"
                },
            ],
            "metrics": {
                "disk_usage_percent": {"normal": 70, "peak": 98},
                "error_rate_percent": {"normal": 0.1, "peak": 100},
            }
        }

    def _chain_queue_backlog(self):
        """场景7：队列堆积"""
        return {
            "name": "队列堆积",
            "root_cause_service": "notification-service",
            "timeline": [
                {"time": "2026-05-19T10:15:00Z", "event": "deployment", "service": "notification-service", "desc": "部署 v1.3.0"},
                {"time": "2026-05-19T10:15:30Z", "event": "error_start", "service": "notification-service", "desc": "队列堆积开始"},
            ],
            "traces": [
                {
                    "trace_id": "trace_601",
                    "start_time": "2026-05-19T10:16:00Z",
                    "services": ["api-gateway", "notification-service"],
                    "status": "error",
                    "duration_ms": 5000,
                    "error_msg": "Queue backlog: 8000 pending tasks"
                },
            ],
            "metrics": {
                "queue_depth": {"normal": 100, "peak": 8000},
                "memory_usage_percent": {"normal": 50, "peak": 85},
            }
        }

    def _chain_db_down(self):
        """场景8：数据库宕机"""
        return {
            "name": "数据库宕机",
            "root_cause_service": "database-service",
            "timeline": [
                {"time": "2026-05-19T10:15:00Z", "event": "error_start", "service": "database-service", "desc": "数据库进程崩溃"},
                {"time": "2026-05-19T10:15:30Z", "event": "cascade", "service": "user-service", "desc": "连接失败"},
                {"time": "2026-05-19T10:15:30Z", "event": "cascade", "service": "order-service", "desc": "连接失败"},
                {"time": "2026-05-19T10:15:30Z", "event": "cascade", "service": "payment-service", "desc": "连接失败"},
            ],
            "traces": [
                {
                    "trace_id": "trace_701",
                    "start_time": "2026-05-19T10:16:00Z",
                    "services": ["api-gateway", "user-service", "database-service"],
                    "status": "error",
                    "duration_ms": 5000,
                    "error_msg": "Database connection refused"
                },
                {
                    "trace_id": "trace_702",
                    "start_time": "2026-05-19T10:16:30Z",
                    "services": ["api-gateway", "order-service", "database-service"],
                    "status": "error",
                    "duration_ms": 5000,
                    "error_msg": "Database connection refused"
                },
                {
                    "trace_id": "trace_703",
                    "start_time": "2026-05-19T10:17:00Z",
                    "services": ["api-gateway", "payment-service", "database-service"],
                    "status": "error",
                    "duration_ms": 5000,
                    "error_msg": "Database connection refused"
                },
            ],
            "metrics": {
                "error_rate_percent": {"normal": 0.1, "peak": 100},
                "request_latency_ms": {"normal": 100, "peak": 5000},
            }
        }

    def _generate_events(self, scenario, chain):
        """基于链条生成 events.json"""
        events = []

        for timeline_item in chain["timeline"]:
            if timeline_item["event"] == "deployment":
                events.append({
                    "timestamp": timeline_item["time"],
                    "event_type": "deployment",
                    "service": timeline_item["service"],
                    "version": "v2.3.1",
                    "status": "success"
                })
            elif timeline_item["event"] in ["error_start", "cascade", "gc_pause"]:
                events.append({
                    "timestamp": timeline_item["time"],
                    "event_type": "alert",
                    "service": timeline_item["service"],
                    "severity": "critical" if timeline_item["event"] == "error_start" else "warning",
                    "message": timeline_item["desc"]
                })

        return events

    def _generate_logs(self, scenario, chain):
        """基于链条生成 logs.json"""
        logs = []
        base_time = datetime.fromisoformat("2026-05-19T10:00:00")

        # 生成正常状态日志（10:00-10:15）
        for service in scenario["affected_services"]:
            for i in range(15):
                logs.append({
                    "timestamp": (base_time + timedelta(minutes=i)).isoformat() + "Z",
                    "service": service,
                    "level": "INFO",
                    "message": "Request processed successfully",
                    "trace_id": f"trace_normal_{i:03d}",
                    "span_id": "span_1",
                    "parent_span_id": None,
                    "duration_ms": 100,
                    "status": "success",
                    "error_message": None
                })

        # 基于链条生成问题状态日志
        for trace in chain["traces"]:
            trace_id = trace["trace_id"]
            start_time = datetime.fromisoformat(trace["start_time"].replace("Z", "+00:00"))

            # 为链路中的每个服务生成日志
            for idx, service in enumerate(trace["services"]):
                logs.append({
                    "timestamp": start_time.isoformat() + "Z",
                    "service": service,
                    "level": "ERROR",
                    "message": trace["error_msg"],
                    "trace_id": trace_id,
                    "span_id": f"span_{idx + 1}",
                    "parent_span_id": f"span_{idx}" if idx > 0 else None,
                    "duration_ms": trace["duration_ms"],
                    "status": "error",
                    "error_message": trace["error_msg"]
                })

        return logs

    def _generate_metrics(self, scenario, chain):
        """基于链条生成 metrics.json"""
        metrics = []
        base_time = datetime.fromisoformat("2026-05-19T10:00:00")

        # 为每个受影响的服务生成指标
        for service in scenario["affected_services"]:
            for minute in range(30):
                current_time = base_time + timedelta(minutes=minute)
                is_problem_time = minute >= 15

                for metric_name, values in chain["metrics"].items():
                    if is_problem_time:
                        value = values.get("peak", values.get("normal", 0))
                    else:
                        value = values.get("normal", 0)

                    metrics.append({
                        "timestamp": current_time.isoformat() + "Z",
                        "service": service,
                        "instance": "pod-1",
                        "metric_name": metric_name,
                        "value": value,
                        "unit": self._get_metric_unit(metric_name)
                    })

        return metrics

    def _generate_traces(self, scenario, chain):
        """基于链条生成 traces.json"""
        traces = []
        base_time = datetime.fromisoformat("2026-05-19T10:00:00")

        # 生成正常链路
        for i in range(5):
            trace_id = f"trace_normal_{i:03d}"
            start_time = base_time + timedelta(minutes=i*2)

            spans = []
            for idx, service in enumerate(scenario["affected_services"][:2]):
                spans.append({
                    "span_id": f"span_{idx + 1}",
                    "parent_span_id": f"span_{idx}" if idx > 0 else None,
                    "service": service,
                    "operation": f"operation_{idx}",
                    "start_time": start_time.isoformat() + "Z",
                    "end_time": (start_time + timedelta(milliseconds=100)).isoformat() + "Z",
                    "duration_ms": 100,
                    "status": "success",
                    "error_message": None
                })

            traces.append({
                "trace_id": trace_id,
                "start_time": start_time.isoformat() + "Z",
                "end_time": (start_time + timedelta(milliseconds=200)).isoformat() + "Z",
                "total_duration_ms": 200,
                "status": "success",
                "spans": spans
            })

        # 基于链条生成问题链路
        for trace in chain["traces"]:
            trace_id = trace["trace_id"]
            start_time = datetime.fromisoformat(trace["start_time"].replace("Z", "+00:00"))
            duration_ms = trace["duration_ms"]

            spans = []
            for idx, service in enumerate(trace["services"]):
                span_duration = duration_ms // len(trace["services"])
                spans.append({
                    "span_id": f"span_{idx + 1}",
                    "parent_span_id": f"span_{idx}" if idx > 0 else None,
                    "service": service,
                    "operation": f"operation_{idx}",
                    "start_time": start_time.isoformat() + "Z",
                    "end_time": (start_time + timedelta(milliseconds=span_duration)).isoformat() + "Z",
                    "duration_ms": span_duration,
                    "status": "error",
                    "error_message": trace["error_msg"]
                })

            traces.append({
                "trace_id": trace_id,
                "start_time": start_time.isoformat() + "Z",
                "end_time": (start_time + timedelta(milliseconds=duration_ms)).isoformat() + "Z",
                "total_duration_ms": duration_ms,
                "status": "error",
                "spans": spans
            })

        return traces

    def _get_metric_unit(self, metric_name):
        """获取指标单位"""
        units = {
            "error_rate_percent": "%",
            "request_latency_ms": "ms",
            "db_connections": "count",
            "cpu_usage_percent": "%",
            "memory_usage_percent": "%",
            "gc_time_ms": "ms",
            "queue_depth": "count",
            "disk_usage_percent": "%"
        }
        return units.get(metric_name, "")

    def _save_json(self, path, data):
        """保存 JSON 文件"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    generator = ClosedLoopScenarioGenerator()
    generator.generate_all_scenarios()
