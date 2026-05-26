"""
诊断报告生成器

用于聚合诊断数据、生成结构化报告、给出修复建议
"""

from typing import Dict, Any, List
from datetime import datetime
from loguru import logger


class DiagnosisReportGenerator:
    """诊断报告生成器"""

    def __init__(self):
        self.logger = logger

    def generate_report(
        self,
        diagnosis_data: Dict[str, Any],
        past_steps: List[tuple]
    ) -> str:
        """
        生成诊断报告

        Args:
            diagnosis_data: 诊断数据字典
            past_steps: 已执行步骤列表

        Returns:
            str: 诊断报告（Markdown 格式）
        """
        self.logger.info("生成诊断报告...")

        # 提取关键信息
        alerts = self._extract_alerts(past_steps)
        errors = self._extract_errors(past_steps)
        anomalies = self._extract_anomalies(past_steps)
        deployments = self._extract_deployments(past_steps)

        # 分析问题
        issues = self._identify_issues(alerts, errors, anomalies)
        root_causes = self._analyze_root_causes(issues, deployments, errors)
        recommendations = self._generate_recommendations(root_causes)

        # 生成报告
        report = self._format_report(
            alerts=alerts,
            errors=errors,
            anomalies=anomalies,
            deployments=deployments,
            issues=issues,
            root_causes=root_causes,
            recommendations=recommendations
        )

        self.logger.info("诊断报告生成完成")
        return report

    def _extract_alerts(self, past_steps: List[tuple]) -> List[Dict[str, Any]]:
        """从执行步骤中提取告警信息"""
        alerts = []
        for step, result in past_steps:
            if "get_alerts" in step.lower() and isinstance(result, str):
                try:
                    # 尝试从结果中提取告警信息
                    if "data" in result.lower():
                        alerts.append({"step": step, "result": result})
                except Exception as e:
                    self.logger.warning(f"提取告警信息失败: {e}")
        return alerts

    def _extract_errors(self, past_steps: List[tuple]) -> List[Dict[str, Any]]:
        """从执行步骤中提取错误日志"""
        errors = []
        for step, result in past_steps:
            if "error" in step.lower() and isinstance(result, str):
                try:
                    errors.append({"step": step, "result": result})
                except Exception as e:
                    self.logger.warning(f"提取错误日志失败: {e}")
        return errors

    def _extract_anomalies(self, past_steps: List[tuple]) -> List[Dict[str, Any]]:
        """从执行步骤中提取异常指标"""
        anomalies = []
        for step, result in past_steps:
            if "anomal" in step.lower() and isinstance(result, str):
                try:
                    anomalies.append({"step": step, "result": result})
                except Exception as e:
                    self.logger.warning(f"提取异常指标失败: {e}")
        return anomalies

    def _extract_deployments(self, past_steps: List[tuple]) -> List[Dict[str, Any]]:
        """从执行步骤中提取部署事件"""
        deployments = []
        for step, result in past_steps:
            if "deployment" in step.lower() and isinstance(result, str):
                try:
                    deployments.append({"step": step, "result": result})
                except Exception as e:
                    self.logger.warning(f"提取部署事件失败: {e}")
        return deployments

    def _identify_issues(
        self,
        alerts: List[Dict],
        errors: List[Dict],
        anomalies: List[Dict]
    ) -> List[str]:
        """识别系统中存在的问题"""
        issues = []

        # 从告警中识别问题
        if alerts:
            issues.append("系统存在活跃告警")

        # 从错误日志中识别问题
        if errors:
            issues.append("系统出现错误日志")

        # 从异常指标中识别问题
        if anomalies:
            issues.append("系统指标出现异常")

        return issues if issues else ["未发现明显问题"]

    def _analyze_root_causes(
        self,
        issues: List[str],
        deployments: List[Dict],
        errors: List[Dict]
    ) -> Dict[str, str]:
        """分析问题的根本原因"""
        root_causes = {}

        # 如果有部署事件和错误，可能是部署导致的问题
        if deployments and errors:
            root_causes["deployment_issue"] = "新版本部署可能导致系统问题"

        # 如果有错误日志，分析错误类型
        if errors:
            root_causes["error_analysis"] = "系统出现错误，需要检查错误日志"

        return root_causes if root_causes else {"unknown": "无法确定根本原因"}

    def _generate_recommendations(self, root_causes: Dict[str, str]) -> List[str]:
        """生成修复建议"""
        recommendations = []

        for cause, description in root_causes.items():
            if "deployment" in cause:
                recommendations.extend([
                    "立即回滚到上一个稳定版本",
                    "检查新版本中的代码变更",
                    "在测试环境中进行充分测试"
                ])
            elif "error" in cause:
                recommendations.extend([
                    "检查错误日志，了解具体错误信息",
                    "查看相关服务的运行状态",
                    "检查系统资源使用情况"
                ])

        if not recommendations:
            recommendations.append("继续监控系统状态")

        return recommendations

    def _format_report(
        self,
        alerts: List[Dict],
        errors: List[Dict],
        anomalies: List[Dict],
        deployments: List[Dict],
        issues: List[str],
        root_causes: Dict[str, str],
        recommendations: List[str]
    ) -> str:
        """格式化诊断报告"""
        report = []

        # 标题
        report.append("# 系统诊断报告\n")

        # 诊断摘要
        report.append("## 📋 诊断摘要\n")
        report.append(f"- **诊断时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"- **发现问题数**：{len(issues)}")
        report.append(f"- **告警数**：{len(alerts)}")
        report.append(f"- **错误日志数**：{len(errors)}")
        report.append(f"- **异常指标数**：{len(anomalies)}")
        report.append(f"- **部署事件数**：{len(deployments)}\n")

        # 发现的问题
        if issues:
            report.append("## 🚨 发现的问题\n")
            for i, issue in enumerate(issues, 1):
                report.append(f"{i}. {issue}")
            report.append("")

        # 根因分析
        if root_causes:
            report.append("## 🔍 根因分析\n")
            for cause, description in root_causes.items():
                report.append(f"### {cause}")
                report.append(f"{description}\n")

        # 修复建议
        if recommendations:
            report.append("## 💡 修复建议\n")
            for i, rec in enumerate(recommendations, 1):
                report.append(f"{i}. {rec}")
            report.append("")

        # 详细数据
        report.append("## 📊 详细数据\n")

        if alerts:
            report.append("### 告警信息")
            for alert in alerts[:3]:  # 只显示前 3 个
                report.append(f"- {alert['step']}")
            report.append("")

        if errors:
            report.append("### 错误日志")
            for error in errors[:3]:  # 只显示前 3 个
                report.append(f"- {error['step']}")
            report.append("")

        if anomalies:
            report.append("### 异常指标")
            for anomaly in anomalies[:3]:  # 只显示前 3 个
                report.append(f"- {anomaly['step']}")
            report.append("")

        if deployments:
            report.append("### 部署事件")
            for deployment in deployments[:3]:  # 只显示前 3 个
                report.append(f"- {deployment['step']}")
            report.append("")

        return "\n".join(report)


# 全局实例
diagnosis_report_generator = DiagnosisReportGenerator()
