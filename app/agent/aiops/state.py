"""
通用 Plan-Execute-Replan 状态定义
基于 LangGraph 官方教程实现
"""

from typing import List, TypedDict, Annotated, Dict, Any
import operator


class WorkingMemory(TypedDict, total=False):
    """锚点参数：全程稳定，由 Triage 节点初始化"""
    alert_first_trigger_time: str   # 最早告警触发时间（来自 get_alerts）
    analysis_start_time: str        # 查询窗口开始 = fault_start_time - 5min
    analysis_end_time: str          # 查询窗口结束 = 当前时间
    scenario_id: str                # 当前诊断场景
    alert_count: int                # 告警总数
    highest_severity: str           # 最高告警级别 critical/warning/info
    has_deployment_event: bool      # Triage 阶段是否发现与故障相关的发版事件，影响 Planner 策略
    fault_start_time: str           # 最早异常指标时间（来自 get_metrics_anomalies），早于告警触发时间
    affected_service_count: int     # 受影响服务数量（多服务场景关键，影响诊断深度）
    fault_categories: List[str]     # 故障类型初判：可含 "jvm"/"latency"/"error"/"queue"/"resource"/"mixed"


class ExactValuePool(TypedDict, total=False):
    """精确值池：全局累积，解决 LLM 无法精确复现字符串的问题"""
    known_services: List[str]
    known_metric_names: List[str]
    known_trace_ids: List[str]
    known_event_types: List[str]
    known_severities: List[str]
    known_timestamps: List[str]         # 保留最近 10 个
    known_anomaly_services: List[str]   # 已确认有异常的服务（区别于 known_services 泛列表）
    known_deployment_versions: List[str]  # 部署版本号，防止 LLM 幻觉改写


class StepRecord(TypedDict):
    """执行步骤记录：三元组"""
    step: str           # 步骤描述
    raw_result: str     # 工具原始返回（完整保留，供最终报告用）
    summary: str        # LLM 生成的分层去噪摘要（供 Executor 上下文注入用）


class PlanExecuteState(TypedDict):
    """Plan-Execute-Replan 状态"""
    input: str
    scenario_id: str
    plan: List[str]
    past_steps: Annotated[List[StepRecord], operator.add]
    working_memory: WorkingMemory
    exact_value_pool: ExactValuePool
    triage_results: Dict[str, Any]   # Triage 阶段两个工具的原始结果，供 Planner 使用
    retrieved_knowledge: str         # RAG 检索到的历史排查经验，注入 Planner prompt
    response: str
