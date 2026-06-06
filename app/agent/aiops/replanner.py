"""
Replanner 节点：根据已执行步骤的结果，决定继续、重新规划还是生成最终报告
"""

from datetime import datetime
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from loguru import logger
import os, re

from app.config import config
from app.core.llm_factory import llm_factory
from app.agent.mcp_client import get_mcp_client_with_retry
from .state import PlanExecuteState, StepRecord
from .prompts import REPLANNER_SYSTEM_PROMPT, REPORT_SYSTEM_PROMPT


class RootCauseVerification:
    """根因完整性检验"""

    @staticmethod
    def verify_before_respond(
        execution_history: List[str], fault_categories: List[str], has_deployment: bool
    ) -> Dict[str, Any]:
        """
        respond前必做的检查清单。

        返回格式：
        {
            "missing_checks": ["未查询错误日志", ...],
            "severity": "critical" | "warning" | "info",
            "can_respond": bool,
            "critical_missing": [...]
        }
        """
        missing_checks = []
        severity = "info"

        # 1. 通用检查
        if not any("logs" in step.lower() for step in execution_history):
            missing_checks.append("未查询错误日志（关键！）")
            severity = "critical"

        if not any("deployment" in step.lower() for step in execution_history):
            if has_deployment:
                missing_checks.append("未查询部署事件（已有发版，必查！）")
                severity = "critical"

        if not any("metrics" in step.lower() for step in execution_history):
            missing_checks.append("未查询详细指标时序")

        # 2. JVM故障特殊检查
        if "jvm" in fault_categories:
            if not any("gc" in step.lower() for step in execution_history):
                missing_checks.append("【JVM故障】未查询GC日志（必查！）")
                severity = "critical"

            if not any("heap" in step.lower() for step in execution_history):
                missing_checks.append("【JVM故障】未分析heap增长曲线")

            if not any(
                "cache" in step.lower() or "session" in step.lower()
                for step in execution_history
            ):
                missing_checks.append("【JVM故障】未检查缓存/session增长")

            if not any("pool" in step.lower() for step in execution_history):
                missing_checks.append("【JVM故障】未查询连接池状态")

        # 3. 多服务故障特殊检查
        service_error_keywords = ["error", "timeout", "5xx", "exception"]
        if (
            sum(
                1
                for c in fault_categories
                if any(k in c.lower() for k in service_error_keywords)
            )
            >= 2
        ):
            if not any(
                "upstream" in step.lower() or "depend" in step.lower()
                for step in execution_history
            ):
                missing_checks.append(
                    "【多服务故障】未确认上游-下游依赖关系"
                )
                severity = "critical"

            if not any(
                "propagat" in step.lower() for step in execution_history
            ):
                missing_checks.append("【多服务故障】未追踪故障传播链")

        # 4. 版本关联检查
        if has_deployment:
            if not any(
                "version" in step.lower() or "changelog" in step.lower()
                for step in execution_history
            ):
                missing_checks.append("【发版关联】未检查新版本的关键改动")
                severity = "critical"

        return {
            "missing_checks": missing_checks,
            "severity": severity,
            "can_respond": len(missing_checks) == 0,
            "critical_missing": [c for c in missing_checks if "必查" in c],
        }


HARD_LIMIT = 20  # 兜底上限，防止极端情况的无限循环


def _detect_loop(past_steps: List[StepRecord]) -> bool:
    """
    检测工具调用是否陷入循环。
    判断逻辑：过去 WINDOW 步内，同一个工具+关键参数组合出现超过 REPEAT 次则认定为循环。
    这比硬编码步数更准确——排除假设的多步查询不是循环，重复调用同一工具才是。
    """
    WINDOW = 6   # 检测窗口：看最近 6 步
    REPEAT = 3   # 同一组合出现 3 次触发

    recent = past_steps[-WINDOW:]
    call_counts: Dict[str, int] = {}

    for record in recent:
        step = record.get("step", "")
        # 从步骤描述里提取工具名作为去重 key
        # 步骤格式通常是 "调用 get_logs_by_keyword(keyword=connection) - ..."
        import re
        match = re.search(r'(\w+)\(([^)]*)\)', step)
        if match:
            tool_name = match.group(1)
            # 取第一个参数作为关键参数（区分 get_logs_by_keyword("connection") vs get_logs_by_keyword("timeout")）
            first_param = match.group(2).split(",")[0].strip()
            key = f"{tool_name}|{first_param}"
        else:
            key = step[:60]  # 无法解析时用步骤描述前60字符

        call_counts[key] = call_counts.get(key, 0) + 1
        if call_counts[key] >= REPEAT:
            return True

    return False


class Act(BaseModel):
    """Replanner 的决策输出"""
    action: str = Field(
        description="下一步行动，必须是 'continue'、'replan'、'respond' 之一"
    )
    reasoning: str = Field(
        description="决策的推理过程和依据"
    )
    new_steps: List[str] = Field(
        default_factory=list,
        description="当 action 为 'replan' 时，提供新的步骤列表替换剩余计划"
    )


async def replanner(state: PlanExecuteState) -> Dict[str, Any]:
    """
    Replanner 节点：分析已执行步骤的结果，做出决策

    三种决策：
    - continue：继续执行 PlanList 中的下一个步骤
    - replan：替换剩余计划，重新规划（步骤数不受限制）
    - respond：结束诊断，生成最终报告
    """
    logger.info("=== Replanner：决策 ===")

    input_text = state.get("input", "")
    plan = state.get("plan", [])
    past_steps = state.get("past_steps", [])

    logger.info(f"已执行步骤数: {len(past_steps)}, 剩余步骤数: {len(plan)}")

    llm = llm_factory.create_chat_model(
        temperature=0,
        provider=os.getenv("LLM_PROVIDER", "dashscope")
    )

    # 兜底硬上限：防止极端情况
    if len(past_steps) >= HARD_LIMIT:
        logger.warning(f"已执行 {len(past_steps)} 步，达到兜底上限 {HARD_LIMIT}，强制生成报告")
        return await _generate_report(state, llm, forced=True, forced_reason=f"达到兜底上限 {HARD_LIMIT} 步")

    # 循环检测：工具调用重复则强制结束
    if _detect_loop(past_steps):
        logger.warning("检测到工具调用循环（相同工具+参数在近期步骤中重复出现），强制生成报告")
        return await _generate_report(state, llm, forced=True, forced_reason="检测到重复工具调用循环")

    # 计划已全部执行完，生成报告
    if not plan:
        logger.info("计划已全部执行完毕，生成最终报告")
        return await _generate_report(state, llm, forced=False, forced_reason=None)

    # 格式化已执行步骤摘要
    steps_summary = "\n".join([
        f"步骤 {i+1}：{record.get('step', '')}\n结果：{record.get('summary', '')}"
        for i, record in enumerate(past_steps)
    ])

    # 通过 bind_tools() 绑定工具（让 Replanner 知道有哪些工具可用于重新规划）
    try:
        mcp_client = await get_mcp_client_with_retry()
        all_tools = await mcp_client.get_tools()
        # 排除场景管理工具，与 Executor 保持一致
        _EXCLUDED = {"set_scenario", "get_current_scenario"}
        mcp_tools = [t for t in all_tools if t.name not in _EXCLUDED]
        llm_with_tools = llm.bind_tools(mcp_tools)
    except Exception as e:
        logger.warning(f"获取 MCP 工具失败: {e}，使用不绑定工具的 LLM")
        llm_with_tools = llm

    replanner_chain = ChatPromptTemplate.from_messages([
        ("system", REPLANNER_SYSTEM_PROMPT),
        ("placeholder", "{messages}"),
    ]) | llm_with_tools.with_structured_output(Act, method="json_mode")

    try:
        act = await replanner_chain.ainvoke({
            "messages": [
                ("user", f"原始诊断请求：{input_text}"),
                ("user", f"已执行步骤（共 {len(past_steps)} 步）：\n{steps_summary}"),
                ("user", f"剩余计划步骤：\n" + "\n".join(f"- {s}" for s in plan)),
            ]
        })
        logger.info(f"Replanner LLM 输出: {act}")

        action = act.action if isinstance(act, Act) else act.get("action", "continue")  # type: ignore
        reasoning = act.reasoning if isinstance(act, Act) else act.get("reasoning", "")  # type: ignore
        new_steps = act.new_steps if isinstance(act, Act) else act.get("new_steps", [])  # type: ignore

        logger.info(f"Replanner 决策: {action}")
        logger.info(f"决策推理: {reasoning}")

        if action == "respond":
            return await _generate_report(state, llm, forced=False, forced_reason=None)

        elif action == "replan":
            if not new_steps:
                logger.warning("replan 但未提供新步骤，继续执行原计划")
                return {}
            logger.info(f"重新规划，新步骤数: {len(new_steps)}")
            return {"plan": new_steps}

        else:  # continue
            logger.info("继续执行下一个步骤")
            return {}

    except Exception as e:
        logger.exception("Replanner 决策失败，继续执行原计划")
        return {}


async def _generate_report(
    state: PlanExecuteState,
    llm,
    forced: bool,
    forced_reason: str | None,
) -> Dict[str, Any]:
    """生成最终诊断报告"""
    logger.info(f"生成最终诊断报告（强制结束: {forced}）")

    input_text = state.get("input", "")
    past_steps = state.get("past_steps", [])

    # 格式化执行历史
    execution_history = "\n\n".join([
        f"**步骤 {i+1}**：{record.get('step', '')}\n**结果**：\n{record.get('summary', '')}"
        for i, record in enumerate(past_steps)
    ])

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if forced:
        status = f"强制结束（原因：{forced_reason}，已执行 {len(past_steps)} 步）"
    else:
        status = "正常完成"

    report_chain = ChatPromptTemplate.from_messages([
        ("system", REPORT_SYSTEM_PROMPT),
        ("placeholder", "{messages}"),
    ]) | llm

    try:
        response = await report_chain.ainvoke({
            "messages": [
                ("user", f"诊断请求：{input_text}"),
                ("user", f"诊断时间：{now}"),
                ("user", f"诊断状态：{status}"),
                ("user", f"执行历史（共 {len(past_steps)} 步）：\n\n{execution_history}"),
                ("user", "请根据以上信息，严格按照报告格式生成最终诊断报告。"),
            ]
        })

        final_report = response.content if hasattr(response, "content") else str(response)
        logger.info(f"诊断报告生成完成，长度: {len(final_report)}")
        return {"response": final_report}

    except Exception as e:
        logger.exception("生成报告失败")
        fallback = f"""# 🔍 系统诊断报告

**诊断时间**：{now}
**诊断状态**：{status}

## 执行历史

{execution_history}

## 说明

报告生成过程中发生异常，以上为原始执行数据，请人工分析。
"""
        return {"response": fallback}
