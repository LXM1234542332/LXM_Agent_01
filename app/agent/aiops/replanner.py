"""
Replanner 节点：根据已执行步骤的结果，决定继续、重新规划还是生成最终报告
"""

from datetime import datetime
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_qwq import ChatQwen
from pydantic import BaseModel, Field
from loguru import logger

from app.config import config
from app.agent.mcp_client import get_mcp_client_with_retry
from .state import PlanExecuteState
from .prompts import REPLANNER_SYSTEM_PROMPT, REPORT_SYSTEM_PROMPT


MAX_STEPS = 8  # 最大执行步骤数，超过后强制结束


class Act(BaseModel):
    """Replanner 的决策输出"""
    action: str = Field(
        description="下一步行动，必须是 'continue'、'replan'、'respond' 之一"
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
    - replan：替换剩余计划，重新规划
    - respond：结束诊断，生成最终报告
    """
    logger.info("=== Replanner：决策 ===")

    input_text = state.get("input", "")
    plan = state.get("plan", [])
    past_steps = state.get("past_steps", [])

    logger.info(f"已执行步骤数: {len(past_steps)}, 剩余步骤数: {len(plan)}")

    llm = ChatQwen(
        model=config.rag_model,
        api_key=config.dashscope_api_key,
        temperature=0
    )

    # 超出最大步骤数，强制生成报告
    if len(past_steps) >= MAX_STEPS:
        logger.warning(f"已执行 {len(past_steps)} 步，达到上限 {MAX_STEPS}，强制生成报告")
        return await _generate_report(state, llm, forced=True)

    # 计划已全部执行完，生成报告
    if not plan:
        logger.info("计划已全部执行完毕，生成最终报告")
        return await _generate_report(state, llm, forced=False)

    # 格式化已执行步骤摘要
    steps_summary = "\n".join([
        f"步骤 {i+1}：{step}\n结果：{result[:400]}{'...' if len(result) > 400 else ''}"
        for i, (step, result) in enumerate(past_steps)
    ])

    # 通过 bind_tools() 绑定工具（让 Replanner 知道有哪些工具可用于重新规划）
    try:
        mcp_client = await get_mcp_client_with_retry()
        mcp_tools = await mcp_client.get_tools()
        llm_with_tools = llm.bind_tools(mcp_tools)
    except Exception as e:
        logger.warning(f"获取 MCP 工具失败: {e}，使用不绑定工具的 LLM")
        llm_with_tools = llm

    replanner_chain = ChatPromptTemplate.from_messages([
        ("system", REPLANNER_SYSTEM_PROMPT),
        ("placeholder", "{messages}"),
    ]) | llm_with_tools.with_structured_output(Act)

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
        new_steps = act.new_steps if isinstance(act, Act) else act.get("new_steps", [])  # type: ignore

        logger.info(f"Replanner 决策: {action}")

        if action == "respond":
            return await _generate_report(state, llm, forced=False)

        elif action == "replan":
            # 防止 replan 无限扩展步骤
            if len(past_steps) >= 3:
                logger.warning(f"已执行 {len(past_steps)} 步，禁止 replan，强制生成报告")
                return await _generate_report(state, llm, forced=False)

            if not new_steps:
                logger.warning("replan 但未提供新步骤，继续执行原计划")
                return {}

            # 新步骤数不能超过剩余步骤数
            if len(new_steps) > len(plan):
                new_steps = new_steps[:len(plan)]
                logger.warning(f"新步骤数超过剩余步骤数，截断为 {len(new_steps)} 步")

            logger.info(f"重新规划，新步骤数: {len(new_steps)}")
            return {"plan": new_steps}

        else:  # continue
            logger.info("继续执行下一个步骤")
            return {}

    except Exception as e:
        logger.error(f"Replanner 决策失败: {e}，继续执行原计划")
        return {}


async def _generate_report(state: PlanExecuteState, llm: ChatQwen, forced: bool) -> Dict[str, Any]:
    """生成最终诊断报告"""
    logger.info(f"生成最终诊断报告（强制结束: {forced}）")

    input_text = state.get("input", "")
    past_steps = state.get("past_steps", [])

    # 格式化执行历史
    execution_history = "\n\n".join([
        f"**步骤 {i+1}**：{step}\n**结果**：\n{result}"
        for i, (step, result) in enumerate(past_steps)
    ])

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = f"强制结束（已执行 {len(past_steps)} 步，达到上限 {MAX_STEPS}）" if forced else "正常完成"

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
        logger.error(f"生成报告失败: {e}")
        fallback = f"""# 🔍 系统诊断报告

**诊断时间**：{now}
**诊断状态**：{status}

## 执行历史

{execution_history}

## 说明

报告生成过程中发生异常，以上为原始执行数据，请人工分析。
"""
        return {"response": fallback}
