"""
诊断数据生成器 - JSON 版本
生成能够支撑诊断闭环的数据
使用 JSON 格式存储，人眼可以直接读
"""

import json
from datetime import datetime, timedelta
import random
import os

# 数据存储路径
DATA_DIR = "E:\\agent\\vscode\\Oncall-Agent\\data"
LOGS_FILE = os.path.join(DATA_DIR, "logs.json")
METRICS_FILE = os.path.join(DATA_DIR, "metrics.json")
EVENTS_FILE = os.path.join(DATA_DIR, "events.json")


class DiagnosticDataGenerator:
    def __init__(self):
        self.logs = []
        self.metrics = []
        self.events = []

    def generate_logs(self, start_time, duration_minutes=60):
        """生成日志数据"""
        print("[LOG] 生成日志数据...")

        current_time = start_time
        end_time = start_time + timedelta(minutes=duration_minutes)

        # 时间段定义
        normal_end = start_time + timedelta(minutes=15)
        degradation_end = start_time + timedelta(minutes=25)
        critical_end = start_time + timedelta(minutes=40)

        log_count = 0

        while current_time < end_time:
            # 根据时间段生成不同的日志
            if current_time < normal_end:
                # 正常阶段
                if random.random() < 0.3:
                    self.logs.append(self._create_normal_log(current_time))
                    log_count += 1

            elif current_time < degradation_end:
                # 恶化阶段：开始出现警告
                if random.random() < 0.5:
                    self.logs.append(self._create_warning_log(current_time))
                    log_count += 1
                if random.random() < 0.2:
                    self.logs.append(self._create_normal_log(current_time))
                    log_count += 1

            elif current_time < critical_end:
                # 严重故障阶段：大量错误
                if random.random() < 0.8:
                    self.logs.append(self._create_error_log(current_time))
                    log_count += 1
                if random.random() < 0.3:
                    self.logs.append(self._create_timeout_log(current_time))
                    log_count += 1

            else:
                # 恢复阶段
                if random.random() < 0.2:
                    self.logs.append(self._create_error_log(current_time))
                    log_count += 1
                if random.random() < 0.5:
                    self.logs.append(self._create_normal_log(current_time))
                    log_count += 1

            current_time += timedelta(seconds=random.randint(5, 30))

        print(f"   OK 生成了 {log_count} 条日志")
        return log_count

    def _create_normal_log(self, timestamp):
        """创建正常日志"""
        return {
            "timestamp": timestamp.isoformat() + "Z",
            "service": random.choice(["api-gateway", "user-service"]),
            "level": "INFO",
            "message": random.choice([
                "Request processed successfully",
                "User profile retrieved",
                "Order created"
            ]),
            "trace_id": f"trace_{random.randint(1000, 9999)}",
            "duration_ms": random.randint(50, 200)
        }

    def _create_warning_log(self, timestamp):
        """创建警告日志"""
        return {
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
        """创建错误日志"""
        return {
            "timestamp": timestamp.isoformat() + "Z",
            "service": "user-service",
            "level": "ERROR",
            "message": "Failed to acquire database connection",
            "error": "Connection pool exhausted",
            "trace_id": f"trace_{random.randint(1000, 9999)}",
            "details": {
                "pool_size": 100,
                "active_connections": 100,
                "timeout_ms": 5000
            }
        }

    def _create_timeout_log(self, timestamp):
        """创建超时日志"""
        return {
            "timestamp": timestamp.isoformat() + "Z",
            "service": "api-gateway",
            "level": "ERROR",
            "message": "Request timeout calling user-service",
            "error": "Timeout after 30000ms",
            "trace_id": f"trace_{random.randint(1000, 9999)}",
            "endpoint": "/api/users/profile",
            "duration_ms": 30000
        }

    def generate_metrics(self, start_time, duration_minutes=60):
        """生成指标数据"""
        print("[METRICS] 生成指标数据...")

        current_time = start_time
        end_time = start_time + timedelta(minutes=duration_minutes)

        # 时间段定义
        normal_end = start_time + timedelta(minutes=15)
        degradation_end = start_time + timedelta(minutes=25)
        critical_end = start_time + timedelta(minutes=40)

        metric_count = 0

        while current_time < end_time:
            # 数据库连接数指标
            if current_time < normal_end:
                db_connections = 30 + random.randint(0, 20)
            elif current_time < degradation_end:
                progress = (current_time - normal_end).total_seconds() / ((degradation_end - normal_end).total_seconds())
                db_connections = int(50 + progress * 40 + random.randint(-5, 5))
            elif current_time < critical_end:
                db_connections = 95 + random.randint(0, 5)
            else:
                progress = (current_time - critical_end).total_seconds() / ((end_time - critical_end).total_seconds())
                db_connections = int(100 - progress * 70 + random.randint(-5, 5))

            self.metrics.append({
                "timestamp": current_time.isoformat() + "Z",
                "metric_name": "db_connections",
                "value": round(db_connections, 2),
                "service": "user-service",
                "instance": f"pod-{random.randint(1, 3)}"
            })
            metric_count += 1

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

            self.metrics.append({
                "timestamp": current_time.isoformat() + "Z",
                "metric_name": "request_latency_ms",
                "value": round(latency, 2),
                "service": "user-service",
                "instance": f"pod-{random.randint(1, 3)}"
            })
            metric_count += 1

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

            self.metrics.append({
                "timestamp": current_time.isoformat() + "Z",
                "metric_name": "error_rate_percent",
                "value": round(error_rate, 2),
                "service": "user-service",
                "instance": f"pod-{random.randint(1, 3)}"
            })
            metric_count += 1

            current_time += timedelta(minutes=1)

        print(f"   OK 生成了 {metric_count} 个指标数据点")
        return metric_count

    def generate_events(self, start_time):
        """生成事件数据"""
        print("[EVENTS] 生成事件数据...")

        # 事件1：部署新版本 (10:15)
        deploy_time = start_time + timedelta(minutes=15)
        self.events.append({
            "timestamp": deploy_time.isoformat() + "Z",
            "event_type": "deployment",
            "service": "user-service",
            "severity": "info",
            "message": "Deployed new version v2.3.1",
            "details": {
                "previous_version": "v2.3.0",
                "new_version": "v2.3.1",
                "duration_seconds": 45,
                "status": "success"
            }
        })

        # 事件2：告警 - 连接池高使用率 (10:25)
        alert_time = start_time + timedelta(minutes=25)
        self.events.append({
            "timestamp": alert_time.isoformat() + "Z",
            "event_type": "alert",
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

        # 事件3：告警 - 高错误率 (10:30)
        error_alert_time = start_time + timedelta(minutes=30)
        self.events.append({
            "timestamp": error_alert_time.isoformat() + "Z",
            "event_type": "alert",
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

        # 事件4：回滚部署 (10:40)
        rollback_time = start_time + timedelta(minutes=40)
        self.events.append({
            "timestamp": rollback_time.isoformat() + "Z",
            "event_type": "deployment",
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

        print(f"   OK 生成了 {len(self.events)} 个事件")
        return len(self.events)

    def save_to_json(self):
        """保存数据到 JSON 文件"""
        print()
        print("[SAVE] 保存数据到 JSON 文件...")

        # 创建数据目录
        os.makedirs(DATA_DIR, exist_ok=True)

        # 保存日志
        with open(LOGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.logs, f, indent=2, ensure_ascii=False)
        print(f"   OK 日志已保存到 {LOGS_FILE}")

        # 保存指标
        with open(METRICS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.metrics, f, indent=2, ensure_ascii=False)
        print(f"   OK 指标已保存到 {METRICS_FILE}")

        # 保存事件
        with open(EVENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.events, f, indent=2, ensure_ascii=False)
        print(f"   OK 事件已保存到 {EVENTS_FILE}")

    def generate_all(self):
        """生成所有数据"""
        print("=" * 80)
        print("生成诊断数据 (JSON 格式)")
        print("=" * 80)
        print()

        start_time = datetime(2026, 5, 19, 10, 0, 0)

        log_count = self.generate_logs(start_time, duration_minutes=60)
        metric_count = self.generate_metrics(start_time, duration_minutes=60)
        event_count = self.generate_events(start_time)

        self.save_to_json()

        print()
        print("=" * 80)
        print("数据生成完成")
        print("=" * 80)
        print(f"日志: {log_count} 条")
        print(f"指标: {metric_count} 个")
        print(f"事件: {event_count} 个")
        print()
        print("数据文件位置:")
        print(f"  - {LOGS_FILE}")
        print(f"  - {METRICS_FILE}")
        print(f"  - {EVENTS_FILE}")
        print()
        print("故障场景时间线:")
        print("  10:00 - 系统正常运行")
        print("  10:15 - 部署新版本 v2.3.1 (事件)")
        print("  10:20 - 数据库连接数开始上升 (指标)")
        print("  10:25 - 连接池使用率 > 90% (告警事件)")
        print("  10:30 - 请求延迟飙升，错误率 15% (告警事件)")
        print("  10:40 - 回滚到 v2.3.0 (事件)")
        print("  10:45 - 系统恢复正常")
        print()


if __name__ == "__main__":
    generator = DiagnosticDataGenerator()
    generator.generate_all()
