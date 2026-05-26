"""
模拟数据生成器：数据库连接池耗尽故障场景
场景：用户服务部署新版本后，数据库连接没有正确释放，导致连接池耗尽
"""

import json
from datetime import datetime, timedelta
import random
import math

# ============================================================================
# 1. 日志生成器
# ============================================================================

class LogSimulator:
    def __init__(self):
        self.services = ["api-gateway", "user-service", "order-service"]
        self.log_id = 0

    def generate_logs(self, start_time, duration_minutes=60):
        """生成指定时间范围内的日志"""
        logs = []
        current_time = start_time
        end_time = start_time + timedelta(minutes=duration_minutes)

        # 时间段定义
        normal_end = start_time + timedelta(minutes=15)  # 10:00-10:15 正常
        degradation_start = start_time + timedelta(minutes=15)  # 10:15 部署
        degradation_end = start_time + timedelta(minutes=25)  # 10:15-10:25 逐渐恶化
        critical_start = start_time + timedelta(minutes=25)  # 10:25-10:40 严重故障
        critical_end = start_time + timedelta(minutes=40)
        recovery_start = start_time + timedelta(minutes=40)  # 10:40+ 恢复

        while current_time < end_time:
            # 根据时间段生成不同的日志
            if current_time < normal_end:
                # 正常阶段：偶尔的日志
                if random.random() < 0.3:
                    logs.append(self._create_normal_log(current_time))

            elif current_time < degradation_end:
                # 恶化阶段：开始出现连接警告
                if random.random() < 0.5:
                    logs.append(self._create_warning_log(current_time))
                if random.random() < 0.2:
                    logs.append(self._create_normal_log(current_time))

            elif current_time < critical_end:
                # 严重故障阶段：大量错误
                if random.random() < 0.8:
                    logs.append(self._create_error_log(current_time))
                if random.random() < 0.3:
                    logs.append(self._create_timeout_log(current_time))

            else:
                # 恢复阶段：错误减少
                if random.random() < 0.2:
                    logs.append(self._create_error_log(current_time))
                if random.random() < 0.5:
                    logs.append(self._create_normal_log(current_time))

            current_time += timedelta(seconds=random.randint(5, 30))

        return logs

    def _create_normal_log(self, timestamp):
        self.log_id += 1
        return {
            "log_id": self.log_id,
            "timestamp": timestamp.isoformat() + "Z",
            "service": random.choice(["api-gateway", "user-service"]),
            "level": "INFO",
            "message": random.choice([
                "Request processed successfully",
                "User profile retrieved",
                "Order created",
                "Payment processed"
            ]),
            "trace_id": f"trace_{random.randint(1000, 9999)}",
            "duration_ms": random.randint(50, 200)
        }

    def _create_warning_log(self, timestamp):
        self.log_id += 1
        return {
            "log_id": self.log_id,
            "timestamp": timestamp.isoformat() + "Z",
            "service": "user-service",
            "level": "WARN",
            "message": "Database connection pool usage high: 85/100",
            "trace_id": f"trace_{random.randint(1000, 9999)}",
            "details": {
                "pool_size": 100,
                "active_connections": 85,
                "waiting_requests": 5
            }
        }

    def _create_error_log(self, timestamp):
        self.log_id += 1
        return {
            "log_id": self.log_id,
            "timestamp": timestamp.isoformat() + "Z",
            "service": "user-service",
            "level": "ERROR",
            "message": "Failed to acquire database connection",
            "trace_id": f"trace_{random.randint(1000, 9999)}",
            "error": "Connection pool exhausted",
            "details": {
                "pool_size": 100,
                "active_connections": 100,
                "timeout_ms": 5000
            }
        }

    def _create_timeout_log(self, timestamp):
        self.log_id += 1
        return {
            "log_id": self.log_id,
            "timestamp": timestamp.isoformat() + "Z",
            "service": "api-gateway",
            "level": "ERROR",
            "message": "Request timeout calling user-service",
            "trace_id": f"trace_{random.randint(1000, 9999)}",
            "error": "Timeout after 30000ms",
            "endpoint": "/api/users/profile",
            "duration_ms": 30000
        }


# ============================================================================
# 2. 指标生成器
# ============================================================================

class MetricsSimulator:
    def __init__(self):
        self.metric_id = 0

    def generate_metrics(self, start_time, duration_minutes=60):
        """生成指定时间范围内的指标"""
        metrics = []
        current_time = start_time
        end_time = start_time + timedelta(minutes=duration_minutes)

        # 时间段定义
        normal_end = start_time + timedelta(minutes=15)
        degradation_end = start_time + timedelta(minutes=25)
        critical_end = start_time + timedelta(minutes=40)

        minute = 0
        while current_time < end_time:
            # 数据库连接数指标
            if current_time < normal_end:
                # 正常：30-50 个连接
                db_connections = 30 + random.randint(0, 20)
            elif current_time < degradation_end:
                # 恶化：50-90 个连接，逐渐增加
                progress = (current_time - normal_end).total_seconds() / ((degradation_end - normal_end).total_seconds())
                db_connections = int(50 + progress * 40 + random.randint(-5, 5))
            elif current_time < critical_end:
                # 严重：95-100 个连接（耗尽）
                db_connections = 95 + random.randint(0, 5)
            else:
                # 恢复：逐渐下降
                progress = (current_time - critical_end).total_seconds() / ((end_time - critical_end).total_seconds())
                db_connections = int(100 - progress * 70 + random.randint(-5, 5))

            metrics.append(self._create_metric(
                current_time, "db_connections", db_connections, "user-service"
            ))

            # 请求延迟指标
            if current_time < normal_end:
                latency = 100 + random.randint(-20, 20)
            elif current_time < degradation_end:
                progress = (current_time - normal_end).total_seconds() / ((degradation_end - normal_end).total_seconds())
                latency = int(100 + progress * 4000 + random.randint(-100, 100))
            elif current_time < critical_end:
                latency = 5000 + random.randint(-500, 500)
            else:
                progress = (current_time - critical_end).total_seconds() / ((end_time - critical_end).total_seconds())
                latency = int(5000 - progress * 4900 + random.randint(-100, 100))

            metrics.append(self._create_metric(
                current_time, "request_latency_ms", latency, "user-service"
            ))

            # 错误率指标
            if current_time < normal_end:
                error_rate = 0.1 + random.uniform(-0.05, 0.05)
            elif current_time < degradation_end:
                progress = (current_time - normal_end).total_seconds() / ((degradation_end - normal_end).total_seconds())
                error_rate = 0.1 + progress * 15 + random.uniform(-0.5, 0.5)
            elif current_time < critical_end:
                error_rate = 15 + random.uniform(-2, 2)
            else:
                progress = (current_time - critical_end).total_seconds() / ((end_time - critical_end).total_seconds())
                error_rate = max(0.1, 15 - progress * 14.9 + random.uniform(-0.5, 0.5))

            metrics.append(self._create_metric(
                current_time, "error_rate_percent", error_rate, "user-service"
            ))

            current_time += timedelta(minutes=1)
            minute += 1

        return metrics

    def _create_metric(self, timestamp, metric_name, value, service):
        self.metric_id += 1
        return {
            "metric_id": self.metric_id,
            "timestamp": timestamp.isoformat() + "Z",
            "metric": metric_name,
            "value": round(value, 2),
            "service": service,
            "tags": {
                "instance": f"pod-{random.randint(1, 3)}",
                "region": "us-east-1"
            }
        }


# ============================================================================
# 3. 事件生成器
# ============================================================================

class EventSimulator:
    def __init__(self):
        self.event_id = 0

    def generate_events(self, start_time):
        """生成故障场景中的关键事件"""
        events = []

        # 事件1：部署新版本（10:15）
        deploy_time = start_time + timedelta(minutes=15)
        self.event_id += 1
        events.append({
            "event_id": self.event_id,
            "timestamp": deploy_time.isoformat() + "Z",
            "type": "deployment",
            "service": "user-service",
            "severity": "info",
            "message": "Deployed new version v2.3.1",
            "details": {
                "previous_version": "v2.3.0",
                "new_version": "v2.3.1",
                "duration_seconds": 45,
                "status": "success",
                "replicas_updated": 3
            }
        })

        # 事件2：告警触发 - 数据库连接池高使用率（10:25）
        alert_time = start_time + timedelta(minutes=25)
        self.event_id += 1
        events.append({
            "event_id": self.event_id,
            "timestamp": alert_time.isoformat() + "Z",
            "type": "alert",
            "service": "user-service",
            "severity": "warning",
            "message": "Database connection pool usage > 90%",
            "details": {
                "metric": "db_connections",
                "threshold": 90,
                "current_value": 95,
                "alert_rule": "db_pool_high_usage"
            }
        })

        # 事件3：告警升级 - 请求超时（10:30）
        timeout_alert_time = start_time + timedelta(minutes=30)
        self.event_id += 1
        events.append({
            "event_id": self.event_id,
            "timestamp": timeout_alert_time.isoformat() + "Z",
            "type": "alert",
            "service": "user-service",
            "severity": "critical",
            "message": "High error rate detected: 15%",
            "details": {
                "metric": "error_rate_percent",
                "threshold": 5,
                "current_value": 15,
                "alert_rule": "high_error_rate"
            }
        })

        # 事件4：回滚部署（10:40）
        rollback_time = start_time + timedelta(minutes=40)
        self.event_id += 1
        events.append({
            "event_id": self.event_id,
            "timestamp": rollback_time.isoformat() + "Z",
            "type": "deployment",
            "service": "user-service",
            "severity": "warning",
            "message": "Rolled back to previous version v2.3.0",
            "details": {
                "reason": "High error rate after deployment",
                "previous_version": "v2.3.1",
                "rollback_version": "v2.3.0",
                "duration_seconds": 30,
                "status": "success"
            }
        })

        return events


# ============================================================================
# 4. 主程序：生成完整的模拟数据
# ============================================================================

def main():
    # 定义故障场景的起始时间
    start_time = datetime(2026, 5, 19, 10, 0, 0)

    print("=" * 80)
    print("模拟数据生成：数据库连接池耗尽故障场景")
    print("=" * 80)
    print(f"场景开始时间: {start_time.isoformat()}")
    print()

    # 生成日志
    print("[LOG] 生成日志数据...")
    log_sim = LogSimulator()
    logs = log_sim.generate_logs(start_time, duration_minutes=60)
    print(f"   OK 生成了 {len(logs)} 条日志")

    # 生成指标
    print("[METRICS] 生成指标数据...")
    metrics_sim = MetricsSimulator()
    metrics = metrics_sim.generate_metrics(start_time, duration_minutes=60)
    print(f"   OK 生成了 {len(metrics)} 个指标数据点")

    # 生成事件
    print("[EVENTS] 生成事件数据...")
    event_sim = EventSimulator()
    events = event_sim.generate_events(start_time)
    print(f"   OK 生成了 {len(events)} 个事件")

    print()
    print("=" * 80)
    print("数据样本展示")
    print("=" * 80)

    # 展示日志样本
    print("\n【日志样本】")
    print("-" * 80)
    for log in logs[::len(logs)//3]:  # 展示3个样本
        print(json.dumps(log, indent=2, ensure_ascii=False))
        print()

    # 展示指标样本
    print("\n【指标样本】")
    print("-" * 80)
    for metric in metrics[::len(metrics)//3]:  # 展示3个样本
        print(json.dumps(metric, indent=2, ensure_ascii=False))
        print()

    # 展示事件
    print("\n【事件样本】")
    print("-" * 80)
    for event in events:
        print(json.dumps(event, indent=2, ensure_ascii=False))
        print()

    # 保存到文件
    print("=" * 80)
    print("保存数据到文件...")
    print("=" * 80)

    with open("logs.json", "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)
    print(f"OK 日志已保存到 logs.json ({len(logs)} 条)")

    with open("metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(f"OK 指标已保存到 metrics.json ({len(metrics)} 个数据点)")

    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2, ensure_ascii=False)
    print(f"OK 事件已保存到 events.json ({len(events)} 个事件)")

    print()
    print("=" * 80)
    print("故障场景时间线")
    print("=" * 80)
    print("10:00 - 系统正常运行")
    print("10:15 - 部署新版本 v2.3.1 (事件)")
    print("10:20 - 数据库连接数开始上升 (指标)")
    print("10:25 - 连接池使用率 > 90% (告警事件)")
    print("10:30 - 请求延迟飙升，错误率 15% (告警事件)")
    print("10:40 - 回滚到 v2.3.0 (事件)")
    print("10:45 - 系统恢复正常")
    print()


if __name__ == "__main__":
    main()
