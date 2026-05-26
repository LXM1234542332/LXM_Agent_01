"""
诊断分析脚本：使用模拟数据进行故障诊断
演示如何从日志、指标、事件中提取信息并进行根因分析
"""

import json
from datetime import datetime, timedelta
from collections import defaultdict

# ============================================================================
# 1. 数据加载器
# ============================================================================

class DataLoader:
    @staticmethod
    def load_logs(filename="logs.json"):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def load_metrics(filename="metrics.json"):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def load_events(filename="events.json"):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)


# ============================================================================
# 2. 日志分析器
# ============================================================================

class LogAnalyzer:
    def __init__(self, logs):
        self.logs = logs

    def get_error_logs(self):
        """获取所有错误日志"""
        return [log for log in self.logs if log.get("level") == "ERROR"]

    def get_warning_logs(self):
        """获取所有警告日志"""
        return [log for log in self.logs if log.get("level") == "WARN"]

    def get_logs_by_service(self, service):
        """按服务过滤日志"""
        return [log for log in self.logs if log.get("service") == service]

    def get_logs_by_time_range(self, start_time, end_time):
        """按时间范围过滤日志"""
        result = []
        for log in self.logs:
            log_time = datetime.fromisoformat(log["timestamp"].replace("Z", "+00:00"))
            if start_time <= log_time <= end_time:
                result.append(log)
        return result

    def analyze_error_patterns(self):
        """分析错误模式"""
        error_logs = self.get_error_logs()
        patterns = defaultdict(int)

        for log in error_logs:
            error_msg = log.get("error", log.get("message", "Unknown"))
            patterns[error_msg] += 1

        return sorted(patterns.items(), key=lambda x: x[1], reverse=True)

    def get_error_timeline(self):
        """获取错误发生的时间线"""
        error_logs = self.get_error_logs()
        timeline = []

        for log in error_logs:
            timeline.append({
                "time": log["timestamp"],
                "service": log.get("service"),
                "error": log.get("error", log.get("message")),
                "details": log.get("details", {})
            })

        return sorted(timeline, key=lambda x: x["time"])


# ============================================================================
# 3. 指标分析器
# ============================================================================

class MetricsAnalyzer:
    def __init__(self, metrics):
        self.metrics = metrics

    def get_metric_by_name(self, metric_name):
        """获取指定名称的所有指标"""
        return [m for m in self.metrics if m.get("metric") == metric_name]

    def get_metric_by_service(self, service):
        """按服务获取指标"""
        return [m for m in self.metrics if m.get("service") == service]

    def get_metric_by_time_range(self, start_time, end_time):
        """按时间范围获取指标"""
        result = []
        for metric in self.metrics:
            metric_time = datetime.fromisoformat(metric["timestamp"].replace("Z", "+00:00"))
            if start_time <= metric_time <= end_time:
                result.append(metric)
        return result

    def analyze_metric_anomalies(self, metric_name, threshold):
        """分析指标异常"""
        metrics = self.get_metric_by_name(metric_name)
        anomalies = []

        for metric in metrics:
            if metric["value"] > threshold:
                anomalies.append({
                    "time": metric["timestamp"],
                    "value": metric["value"],
                    "threshold": threshold,
                    "severity": "critical" if metric["value"] > threshold * 1.5 else "warning"
                })

        return anomalies

    def get_metric_statistics(self, metric_name):
        """获取指标统计信息"""
        metrics = self.get_metric_by_name(metric_name)
        values = [m["value"] for m in metrics]

        if not values:
            return None

        return {
            "metric": metric_name,
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "samples": [m["timestamp"] for m in metrics[:3]]
        }


# ============================================================================
# 4. 事件分析器
# ============================================================================

class EventAnalyzer:
    def __init__(self, events):
        self.events = events

    def get_events_by_type(self, event_type):
        """按类型获取事件"""
        return [e for e in self.events if e.get("type") == event_type]

    def get_events_by_severity(self, severity):
        """按严重程度获取事件"""
        return [e for e in self.events if e.get("severity") == severity]

    def get_events_timeline(self):
        """获取事件时间线"""
        return sorted(self.events, key=lambda x: x["timestamp"])

    def find_deployment_events(self):
        """查找部署事件"""
        return self.get_events_by_type("deployment")

    def find_alert_events(self):
        """查找告警事件"""
        return self.get_events_by_type("alert")


# ============================================================================
# 5. 根因分析器
# ============================================================================

class RootCauseAnalyzer:
    def __init__(self, logs, metrics, events):
        self.log_analyzer = LogAnalyzer(logs)
        self.metrics_analyzer = MetricsAnalyzer(metrics)
        self.event_analyzer = EventAnalyzer(events)

    def analyze(self):
        """执行完整的根因分析"""
        print("\n" + "=" * 80)
        print("故障诊断分析报告")
        print("=" * 80)

        # 1. 事件时间线
        print("\n[1] 事件时间线")
        print("-" * 80)
        self._print_event_timeline()

        # 2. 错误分析
        print("\n[2] 错误分析")
        print("-" * 80)
        self._print_error_analysis()

        # 3. 指标异常
        print("\n[3] 指标异常分析")
        print("-" * 80)
        self._print_metrics_anomalies()

        # 4. 关联分析
        print("\n[4] 多维度关联分析")
        print("-" * 80)
        self._print_correlation_analysis()

        # 5. 根因诊断
        print("\n[5] 根因诊断")
        print("-" * 80)
        self._print_root_cause_diagnosis()

    def _print_event_timeline(self):
        """打印事件时间线"""
        events = self.event_analyzer.get_events_timeline()
        for event in events:
            print(f"  {event['timestamp']} [{event['severity'].upper()}] {event['type']}: {event['message']}")

    def _print_error_analysis(self):
        """打印错误分析"""
        patterns = self.log_analyzer.analyze_error_patterns()
        print(f"  发现 {len(patterns)} 种错误模式:")
        for error, count in patterns[:5]:
            print(f"    - {error}: {count} 次")

        error_timeline = self.log_analyzer.get_error_timeline()
        if error_timeline:
            print(f"\n  首次错误: {error_timeline[0]['time']}")
            print(f"  最后错误: {error_timeline[-1]['time']}")
            print(f"  总错误数: {len(error_timeline)}")

    def _print_metrics_anomalies(self):
        """打印指标异常"""
        # 分析数据库连接数
        db_conn_stats = self.metrics_analyzer.get_metric_statistics("db_connections")
        if db_conn_stats:
            print(f"  数据库连接数:")
            print(f"    - 最小值: {db_conn_stats['min']}")
            print(f"    - 最大值: {db_conn_stats['max']}")
            print(f"    - 平均值: {db_conn_stats['avg']:.1f}")

        # 分析请求延迟
        latency_stats = self.metrics_analyzer.get_metric_statistics("request_latency_ms")
        if latency_stats:
            print(f"\n  请求延迟:")
            print(f"    - 最小值: {latency_stats['min']}ms")
            print(f"    - 最大值: {latency_stats['max']}ms")
            print(f"    - 平均值: {latency_stats['avg']:.1f}ms")

        # 分析错误率
        error_rate_stats = self.metrics_analyzer.get_metric_statistics("error_rate_percent")
        if error_rate_stats:
            print(f"\n  错误率:")
            print(f"    - 最小值: {error_rate_stats['min']:.2f}%")
            print(f"    - 最大值: {error_rate_stats['max']:.2f}%")
            print(f"    - 平均值: {error_rate_stats['avg']:.2f}%")

    def _print_correlation_analysis(self):
        """打印关联分析"""
        # 找到部署事件
        deployments = self.event_analyzer.find_deployment_events()
        if deployments:
            deploy_time = datetime.fromisoformat(deployments[0]["timestamp"].replace("Z", "+00:00"))
            print(f"  部署事件: {deployments[0]['timestamp']}")
            print(f"    版本: {deployments[0]['details']['previous_version']} -> {deployments[0]['details']['new_version']}")

            # 部署后的错误
            error_timeline = self.log_analyzer.get_error_timeline()
            errors_after_deploy = [e for e in error_timeline
                                  if datetime.fromisoformat(e['time'].replace("Z", "+00:00")) > deploy_time]
            print(f"    部署后错误数: {len(errors_after_deploy)}")

        # 找到告警事件
        alerts = self.event_analyzer.find_alert_events()
        if alerts:
            print(f"\n  告警事件: {len(alerts)} 个")
            for alert in alerts:
                print(f"    - {alert['timestamp']}: {alert['message']}")

    def _print_root_cause_diagnosis(self):
        """打印根因诊断"""
        print("  根因分析:")
        print()

        # 分析部署和错误的时间关系
        deployments = self.event_analyzer.find_deployment_events()
        error_timeline = self.log_analyzer.get_error_timeline()

        if deployments and error_timeline:
            deploy_time = datetime.fromisoformat(deployments[0]["timestamp"].replace("Z", "+00:00"))
            first_error_time = datetime.fromisoformat(error_timeline[0]['time'].replace("Z", "+00:00"))
            time_diff = (first_error_time - deploy_time).total_seconds() / 60

            print(f"  1. 时间关联:")
            print(f"     - 部署时间: {deployments[0]['timestamp']}")
            print(f"     - 首个错误: {error_timeline[0]['time']}")
            print(f"     - 时间差: {time_diff:.1f} 分钟")
            print(f"     - 结论: 部署后 {time_diff:.1f} 分钟出现错误，强烈怀疑与部署相关")

        # 分析错误类型
        patterns = self.log_analyzer.analyze_error_patterns()
        if patterns:
            print(f"\n  2. 错误模式:")
            print(f"     - 主要错误: {patterns[0][0]}")
            print(f"     - 发生次数: {patterns[0][1]}")
            print(f"     - 结论: 数据库连接池耗尽是主要问题")

        # 分析指标
        db_conn_stats = self.metrics_analyzer.get_metric_statistics("db_connections")
        latency_stats = self.metrics_analyzer.get_metric_statistics("request_latency_ms")

        if db_conn_stats and latency_stats:
            print(f"\n  3. 指标关联:")
            print(f"     - 数据库连接数峰值: {db_conn_stats['max']}")
            print(f"     - 请求延迟峰值: {latency_stats['max']}ms")
            print(f"     - 结论: 连接数达到上限导致请求延迟增加")

        # 最终诊断
        print(f"\n  4. 最终诊断:")
        print(f"     根本原因: 新版本 (v2.3.1) 中存在数据库连接泄漏")
        print(f"     表现症状:")
        print(f"       - 数据库连接数逐渐增加")
        print(f"       - 连接池耗尽，新请求无法获取连接")
        print(f"       - 请求超时，错误率上升")
        print(f"     建议措施:")
        print(f"       - 立即回滚到 v2.3.0")
        print(f"       - 检查新版本中的数据库连接管理代码")
        print(f"       - 确保所有连接都被正确释放")
        print(f"       - 添加连接泄漏检测告警")


# ============================================================================
# 6. 主程序
# ============================================================================

def main():
    print("\n" + "=" * 80)
    print("模拟数据诊断演示")
    print("=" * 80)

    # 加载数据
    print("\n[加载数据]")
    loader = DataLoader()
    logs = loader.load_logs()
    metrics = loader.load_metrics()
    events = loader.load_events()
    print(f"  OK 加载了 {len(logs)} 条日志")
    print(f"  OK 加载了 {len(metrics)} 个指标")
    print(f"  OK 加载了 {len(events)} 个事件")

    # 执行根因分析
    analyzer = RootCauseAnalyzer(logs, metrics, events)
    analyzer.analyze()

    print("\n" + "=" * 80)
    print("诊断完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
