#!/usr/bin/env python3
"""
数据生成脚本 - 根据场景配置生成模拟数据
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import random

class ScenarioDataGenerator:
    def __init__(self):
        self.data_dir = Path("data")
        self.scenarios = self._load_scenarios()
        self.services = [
            "api-gateway", "user-service", "order-service", "payment-service",
            "database-service", "cache-service", "notification-service", "search-service"
        ]
        self.pods = ["pod-1", "pod-2", "pod-3"]
        self.metrics_types = [
            "error_rate_percent", "request_latency_ms", "db_connections",
            "cpu_usage_percent", "memory_usage_percent", "gc_time_ms",
            "queue_depth", "disk_usage_percent"
        ]

    def _load_scenarios(self):
        """加载场景配置"""
        with open("data/scenarios.json", "r", encoding="utf-8") as f:
            return json.load(f)

    def generate_all_scenarios(self):
        """生成所有场景的数据"""
        print("开始生成场景数据...\n")

        for scenario in self.scenarios:
            scenario_id = scenario["id"]
            scenario_dir = self.data_dir / scenario_id
            scenario_dir.mkdir(parents=True, exist_ok=True)

            print(f"[{scenario_id}] 生成数据...")

            # 生成各类数据
            events = self._generate_events(scenario)
            logs = self._generate_logs(scenario)
            metrics = self._generate_metrics(scenario)
            traces = self._generate_traces(scenario)

            # 保存数据
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

    def _generate_events(self, scenario):
        """生成事件数据"""
        events = []
        base_time = datetime.fromisoformat("2026-05-19T10:00:00")

        # 部署事件
        events.append({
            "timestamp": (base_time + timedelta(minutes=15)).isoformat() + "Z",
            "event_type": "deployment",
            "service": scenario["affected_services"][0],
            "version": "v2.3.1",
            "status": "success"
        })

        # 告警事件
        for i, service in enumerate(scenario["affected_services"]):
            events.append({
                "timestamp": (base_time + timedelta(minutes=15 + i*2)).isoformat() + "Z",
                "event_type": "alert",
                "service": service,
                "severity": "critical" if i == 0 else "warning",
                "message": f"{service} 出现异常"
            })

        return events

    def _generate_logs(self, scenario):
        """生成日志数据"""
        logs = []
        base_time = datetime.fromisoformat("2026-05-19T10:00:00")

        # 为每个受影响的服务生成日志
        for service in scenario["affected_services"]:
            # 正常状态日志（10:00-10:15）
            for i in range(30):
                logs.append({
                    "timestamp": (base_time + timedelta(minutes=random.randint(0, 14), seconds=random.randint(0, 59))).isoformat() + "Z",
                    "service": service,
                    "level": "INFO",
                    "message": "Request processed successfully",
                    "trace_id": f"trace_{random.randint(10000, 99999)}",
                    "span_id": f"span_{random.randint(1, 5)}",
                    "parent_span_id": None if random.random() > 0.7 else f"span_{random.randint(1, 3)}",
                    "duration_ms": random.randint(50, 200),
                    "status": "success",
                    "error_message": None
                })

            # 问题状态日志（10:15-10:30）
            for i in range(40):
                is_error = random.random() > 0.6
                logs.append({
                    "timestamp": (base_time + timedelta(minutes=random.randint(15, 29), seconds=random.randint(0, 59))).isoformat() + "Z",
                    "service": service,
                    "level": "ERROR" if is_error else "WARN",
                    "message": random.choice(scenario["key_logs"]),
                    "trace_id": f"trace_{random.randint(10000, 99999)}",
                    "span_id": f"span_{random.randint(1, 5)}",
                    "parent_span_id": None if random.random() > 0.7 else f"span_{random.randint(1, 3)}",
                    "duration_ms": random.randint(1000, 6000) if is_error else random.randint(200, 1000),
                    "status": "error" if is_error else "timeout",
                    "error_message": random.choice(scenario["key_logs"]) if is_error else None
                })

        return logs

    def _generate_metrics(self, scenario):
        """生成指标数据"""
        metrics = []
        base_time = datetime.fromisoformat("2026-05-19T10:00:00")

        for service in scenario["affected_services"]:
            for metric_type in scenario["key_metrics"]:
                # 正常状态指标
                for minute in range(0, 15):
                    for pod in self.pods:
                        value = self._get_normal_metric_value(metric_type)
                        metrics.append({
                            "timestamp": (base_time + timedelta(minutes=minute)).isoformat() + "Z",
                            "service": service,
                            "instance": pod,
                            "metric_name": metric_type,
                            "value": value,
                            "unit": self._get_metric_unit(metric_type)
                        })

                # 问题状态指标
                for minute in range(15, 30):
                    for pod in self.pods:
                        value = self._get_abnormal_metric_value(metric_type)
                        metrics.append({
                            "timestamp": (base_time + timedelta(minutes=minute)).isoformat() + "Z",
                            "service": service,
                            "instance": pod,
                            "metric_name": metric_type,
                            "value": value,
                            "unit": self._get_metric_unit(metric_type)
                        })

        return metrics

    def _generate_traces(self, scenario):
        """生成链路追踪数据"""
        traces = []
        base_time = datetime.fromisoformat("2026-05-19T10:00:00")

        # 正常链路
        for i in range(5):
            trace_id = f"trace_{10000 + i}"
            start_time = base_time + timedelta(minutes=random.randint(0, 14))
            traces.append(self._create_trace(trace_id, start_time, scenario, is_error=False))

        # 问题链路
        for i in range(13):
            trace_id = f"trace_{20000 + i}"
            start_time = base_time + timedelta(minutes=random.randint(15, 29))
            traces.append(self._create_trace(trace_id, start_time, scenario, is_error=True))

        return traces

    def _create_trace(self, trace_id, start_time, scenario, is_error):
        """创建单条链路"""
        spans = []
        current_time = start_time

        for idx, service in enumerate(scenario["affected_services"][:3]):  # 最多3个服务
            duration = random.randint(5000, 6000) if is_error else random.randint(50, 200)
            span = {
                "span_id": f"span_{idx + 1}",
                "parent_span_id": f"span_{idx}" if idx > 0 else None,
                "service": service,
                "operation": f"operation_{idx}",
                "start_time": current_time.isoformat() + "Z",
                "end_time": (current_time + timedelta(milliseconds=duration)).isoformat() + "Z",
                "duration_ms": duration,
                "status": "error" if is_error else "success",
                "error_message": random.choice(scenario["key_logs"]) if is_error else None
            }
            spans.append(span)
            current_time += timedelta(milliseconds=duration // 2)

        total_duration = sum(s["duration_ms"] for s in spans)
        return {
            "trace_id": trace_id,
            "start_time": start_time.isoformat() + "Z",
            "end_time": (start_time + timedelta(milliseconds=total_duration)).isoformat() + "Z",
            "total_duration_ms": total_duration,
            "status": "error" if is_error else "success",
            "spans": spans
        }

    def _get_normal_metric_value(self, metric_type):
        """获取正常状态的指标值"""
        values = {
            "error_rate_percent": random.uniform(0.1, 0.5),
            "request_latency_ms": random.randint(50, 200),
            "db_connections": random.randint(20, 50),
            "cpu_usage_percent": random.uniform(20, 40),
            "memory_usage_percent": random.uniform(40, 60),
            "gc_time_ms": random.randint(20, 50),
            "queue_depth": random.randint(10, 100),
            "disk_usage_percent": random.uniform(50, 70)
        }
        return values.get(metric_type, 0)

    def _get_abnormal_metric_value(self, metric_type):
        """获取异常状态的指标值"""
        values = {
            "error_rate_percent": random.uniform(10, 20),
            "request_latency_ms": random.randint(3000, 6000),
            "db_connections": random.randint(140, 160),
            "cpu_usage_percent": random.uniform(80, 98),
            "memory_usage_percent": random.uniform(85, 98),
            "gc_time_ms": random.randint(400, 600),
            "queue_depth": random.randint(5000, 8000),
            "disk_usage_percent": random.uniform(90, 99)
        }
        return values.get(metric_type, 0)

    def _get_metric_unit(self, metric_type):
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
        return units.get(metric_type, "")

    def _save_json(self, path, data):
        """保存 JSON 文件"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    generator = ScenarioDataGenerator()
    generator.generate_all_scenarios()
