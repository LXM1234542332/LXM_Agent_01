#!/usr/bin/env python3
"""
用大模型生成具有问题-原因闭环的场景数据
"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from anthropic import Anthropic

class LLMScenarioDataGenerator:
    def __init__(self):
        self.client = Anthropic()
        self.data_dir = Path("data")
        self.scenarios_config = self._load_scenarios_config()

    def _load_scenarios_config(self):
        """加载场景配置"""
        with open(self.data_dir / "scenarios.json", "r", encoding="utf-8") as f:
            return json.load(f)

    def generate_all_scenarios(self):
        """为所有场景生成数据"""
        print("开始用大模型生成场景数据...\n")

        for scenario in self.scenarios_config:
            scenario_id = scenario["id"]
            print(f"[{scenario_id}] 生成数据...")

            # 生成故障链条
            fault_chain = self._generate_fault_chain(scenario)

            # 基于链条生成 JSON 数据
            events = self._generate_events_from_chain(scenario, fault_chain)
            logs = self._generate_logs_from_chain(scenario, fault_chain)
            metrics = self._generate_metrics_from_chain(scenario, fault_chain)
            traces = self._generate_traces_from_chain(scenario, fault_chain)

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

    def _generate_fault_chain(self, scenario):
        """用大模型生成故障链条"""
        prompt = f"""
你是一个运维专家。根据以下场景描述，生成一个完整的故障链条。

场景ID: {scenario['id']}
场景名称: {scenario['name']}
场景描述: {scenario['description']}
根本原因: {scenario['root_cause']}
受影响的服务: {', '.join(scenario['affected_services'])}

请生成一个JSON格式的故障链条，包含以下内容：

{{
  "timeline": [
    {{
      "time": "2026-05-19T10:15:00Z",
      "event": "deployment",
      "service": "payment-service",
      "description": "部署新版本 v2.3.1"
    }},
    {{
      "time": "2026-05-19T10:15:30Z",
      "event": "error_start",
      "service": "payment-service",
      "description": "第一个支付请求超时"
    }},
    ...
  ],
  "traces": [
    {{
      "trace_id": "trace_001",
      "start_time": "2026-05-19T10:16:00Z",
      "services": ["api-gateway", "order-service", "payment-service"],
      "status": "error",
      "duration_ms": 5000,
      "error_message": "Payment service timeout"
    }},
    ...
  ],
  "key_metrics": {{
    "error_rate_percent": {{"normal": 0.1, "peak": 15}},
    "request_latency_ms": {{"normal": 100, "peak": 5000}},
    "db_connections": {{"normal": 36, "peak": 150}}
  }},
  "key_logs": [
    "payment timeout",
    "connection pool exhausted",
    "GC pause detected"
  ]
}}

要求：
1. 时间线要清晰，从问题开始到持续进行
2. 每条链路都要有唯一的 trace_id
3. 链路中的服务调用要符合服务依赖关系
4. 指标变化要符合问题的严重程度
5. 日志要能反映问题的原因

请只返回JSON，不要其他内容。
"""

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            chain_text = response.content[0].text
            # 提取 JSON
            start = chain_text.find('{')
            end = chain_text.rfind('}') + 1
            chain_json = chain_text[start:end]
            return json.loads(chain_json)
        except Exception as e:
            print(f"解析大模型输出失败: {e}")
            print(f"原始输出: {response.content[0].text}")
            return None

    def _generate_events_from_chain(self, scenario, chain):
        """基于链条生成 events.json"""
        if not chain:
            return []

        events = []
        for timeline_item in chain.get("timeline", []):
            event = {
                "timestamp": timeline_item["time"],
                "event_type": timeline_item["event"],
                "service": timeline_item.get("service", "system"),
                "description": timeline_item.get("description", ""),
            }

            if timeline_item["event"] == "deployment":
                event["version"] = "v2.3.1"
                event["status"] = "success"
            elif timeline_item["event"] == "alert":
                event["severity"] = "critical" if "payment" in timeline_item.get("service", "") else "warning"
                event["message"] = timeline_item.get("description", "")

            events.append(event)

        return events

    def _generate_logs_from_chain(self, scenario, chain):
        """基于链条生成 logs.json"""
        if not chain:
            return []

        logs = []
        base_time = datetime.fromisoformat("2026-05-19T10:00:00")

        # 生成正常状态日志（10:00-10:15）
        for service in scenario["affected_services"]:
            for i in range(20):
                logs.append({
                    "timestamp": (base_time + timedelta(minutes=i)).isoformat() + "Z",
                    "service": service,
                    "level": "INFO",
                    "message": "Request processed successfully",
                    "trace_id": f"trace_normal_{i:03d}",
                    "span_id": f"span_1",
                    "parent_span_id": None,
                    "duration_ms": 100,
                    "status": "success",
                    "error_message": None
                })

        # 基于链条生成问题状态日志
        for trace in chain.get("traces", []):
            trace_id = trace["trace_id"]
            start_time = datetime.fromisoformat(trace["start_time"].replace("Z", "+00:00"))

            # 为链路中的每个服务生成日志
            for idx, service in enumerate(trace.get("services", [])):
                logs.append({
                    "timestamp": start_time.isoformat() + "Z",
                    "service": service,
                    "level": "ERROR" if trace["status"] == "error" else "INFO",
                    "message": trace.get("error_message", "Request processed"),
                    "trace_id": trace_id,
                    "span_id": f"span_{idx + 1}",
                    "parent_span_id": f"span_{idx}" if idx > 0 else None,
                    "duration_ms": trace.get("duration_ms", 100),
                    "status": trace["status"],
                    "error_message": trace.get("error_message") if trace["status"] == "error" else None
                })

        return logs

    def _generate_metrics_from_chain(self, scenario, chain):
        """基于链条生成 metrics.json"""
        if not chain:
            return []

        metrics = []
        base_time = datetime.fromisoformat("2026-05-19T10:00:00")
        key_metrics = chain.get("key_metrics", {})

        # 生成指标数据
        for service in scenario["affected_services"]:
            for minute in range(30):
                current_time = base_time + timedelta(minutes=minute)

                # 根据时间段选择正常或异常值
                is_problem_time = minute >= 15

                for metric_name, values in key_metrics.items():
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

    def _generate_traces_from_chain(self, scenario, chain):
        """基于链条生成 traces.json"""
        if not chain:
            return []

        traces = []

        # 生成正常链路
        for i in range(5):
            trace_id = f"trace_normal_{i:03d}"
            start_time = datetime.fromisoformat("2026-05-19T10:00:00") + timedelta(minutes=i*2)

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
        for trace in chain.get("traces", []):
            trace_id = trace["trace_id"]
            start_time = datetime.fromisoformat(trace["start_time"].replace("Z", "+00:00"))
            duration_ms = trace.get("duration_ms", 1000)

            spans = []
            for idx, service in enumerate(trace.get("services", [])):
                span_duration = duration_ms // len(trace.get("services", [1]))
                spans.append({
                    "span_id": f"span_{idx + 1}",
                    "parent_span_id": f"span_{idx}" if idx > 0 else None,
                    "service": service,
                    "operation": f"operation_{idx}",
                    "start_time": start_time.isoformat() + "Z",
                    "end_time": (start_time + timedelta(milliseconds=span_duration)).isoformat() + "Z",
                    "duration_ms": span_duration,
                    "status": trace["status"],
                    "error_message": trace.get("error_message") if trace["status"] == "error" else None
                })

            traces.append({
                "trace_id": trace_id,
                "start_time": start_time.isoformat() + "Z",
                "end_time": (start_time + timedelta(milliseconds=duration_ms)).isoformat() + "Z",
                "total_duration_ms": duration_ms,
                "status": trace["status"],
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
    generator = LLMScenarioDataGenerator()
    generator.generate_all_scenarios()
