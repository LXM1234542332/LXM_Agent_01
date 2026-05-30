"""
通用 Plan-Execute-Replan 服务
基于 LangGraph 官方教程实现
"""

from typing import AsyncGenerator, Dict, Any, Optional
from pathlib import Path
from langgraph.graph import StateGraph, END
from loguru import logger

from app.agent.aiops import PlanExecuteState, planner, executor, replanner


# 节点名称常量
NODE_PLANNER = "planner"
NODE_EXECUTOR = "executor"
NODE_REPLANNER = "replanner"


class AIOpsService:
    """通用 Plan-Execute-Replan 服务"""

    def __init__(self):
        """初始化服务"""
        self.graph = self._build_graph()
        logger.info("Plan-Execute-Replan Service 初始化完成")

    def _save_report(self, report: str, scenario_id: Optional[str] = None) -> Optional[str]:
        """
        保存诊断报告到文件

        Args:
            report: 诊断报告内容
            scenario_id: 场景ID（如 scenario1），用于确定保存路径

        Returns:
            保存的文件路径，如果保存失败则返回 None
        """
        if not scenario_id or not report:
            return None

        try:
            # 构建保存路径：/data/{scenario_id}/运维agent报告.md
            report_dir = Path("data") / scenario_id
            report_dir.mkdir(parents=True, exist_ok=True)

            report_file = report_dir / "运维agent报告.md"

            # 写入报告
            report_file.write_text(report, encoding="utf-8")

            logger.info(f"诊断报告已保存到: {report_file.absolute()}")
            return str(report_file.absolute())

        except Exception as e:
            logger.error(f"保存诊断报告失败: {e}", exc_info=True)
            return None

    def _build_graph(self):
        """构建 Plan-Execute-Replan 工作流"""
        logger.info("构建工作流图...")

        # 创建状态图
        workflow = StateGraph(PlanExecuteState)

        # 添加节点
        workflow.add_node(NODE_PLANNER, planner)      # 制定计划
        workflow.add_node(NODE_EXECUTOR, executor)  # 执行步骤
        workflow.add_node(NODE_REPLANNER, replanner)  # 重新规划

        # 设置入口点
        workflow.set_entry_point(NODE_PLANNER)

        # 定义边
        workflow.add_edge(NODE_PLANNER, NODE_EXECUTOR)     # planner -> executor
        workflow.add_edge(NODE_EXECUTOR, NODE_REPLANNER)   # executor -> replanner

        # replanner 的条件边
        def should_continue(state: PlanExecuteState) -> str:
            """判断是否继续执行"""
            # 如果已经生成了最终响应，结束
            if state.get("response"):
                logger.info("已生成最终响应，结束流程")
                return END

            # 如果还有计划步骤，继续执行
            plan = state.get("plan", [])
            if plan:
                logger.info(f"继续执行，剩余 {len(plan)} 个步骤")
                return NODE_EXECUTOR

            # 计划为空但没有响应，返回 replanner 生成响应
            logger.info("计划执行完毕，生成最终响应")
            return END

        workflow.add_conditional_edges(
            NODE_REPLANNER,
            should_continue,
            {
                NODE_EXECUTOR: NODE_EXECUTOR,
                END: END
            }
        )

        # 编译工作流
        compiled_graph = workflow.compile()

        logger.info("工作流图构建完成")
        return compiled_graph

    async def execute(
        self,
        user_input: str,
        session_id: str = "default"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        执行 Plan-Execute-Replan 流程

        Args:
            user_input: 用户的任务描述
            session_id: 会话ID

        Yields:
            Dict[str, Any]: 流式事件
        """
        logger.info(f"[会话 {session_id}] 开始执行任务: {user_input}")

        try:
            # 初始化状态
            initial_state: PlanExecuteState = {
                "input": user_input,
                "plan": [],
                "past_steps": [],
                "response": ""
            }

            # 流式执行工作流
            config_dict = {
                "configurable": {
                    "thread_id": session_id
                }
            }

            final_response = ""

            async for event in self.graph.astream(
                input=initial_state,
                config=config_dict,
                stream_mode="updates"
            ):
                # 解析事件
                for node_name, node_output in event.items():
                    logger.info(f"节点 '{node_name}' 输出事件")

                    # 根据节点类型生成不同的事件
                    if node_name == NODE_PLANNER:
                        yield self._format_planner_event(node_output)

                    elif node_name == NODE_EXECUTOR:
                        yield self._format_executor_event(node_output)

                    elif node_name == NODE_REPLANNER:
                        # 从 replanner 节点获取最终响应
                        if node_output and node_output.get("response"):
                            final_response = node_output.get("response", "")
                        yield self._format_replanner_event(node_output)

            # 发送完成事件
            yield {
                "type": "complete",
                "stage": "complete",
                "message": "任务执行完成",
                "response": final_response
            }

            logger.info(f"[会话 {session_id}] 任务执行完成")

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"[会话 {session_id}] 任务执行失败: {e}\n{tb}")
            yield {
                "type": "error",
                "stage": "error",
                "message": f"任务执行出错: {str(e)}",
                "traceback": tb
            }

    async def diagnose(
        self,
        session_id: str = "default",
        scenario_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        AIOps 诊断接口（兼容旧接口）

        Args:
            session_id: 会话ID
            scenario_id: 场景ID，用于保存报告到对应目录

        Yields:
            Dict[str, Any]: 诊断过程的流式事件
        """
        # 诊断请求：简洁描述任务，由 Planner 自行制定计划
        aiops_task = "诊断当前系统是否存在告警，如果存在告警请详细分析告警原因并生成诊断报告"

        async for event in self.execute(aiops_task, session_id):
            # 转换事件格式以兼容旧的 API
            if event.get("type") == "complete":
                report = event.get("response", "")

                # 保存报告到文件
                saved_path = None
                if scenario_id:
                    saved_path = self._save_report(report, scenario_id)
                    if saved_path:
                        logger.info(f"[场景 {scenario_id}] 诊断报告已保存到: {saved_path}")

                # 将 response 包装为 diagnosis 格式
                yield {
                    "type": "complete",
                    "stage": "diagnosis_complete",
                    "message": "诊断流程完成",
                    "diagnosis": {
                        "status": "completed",
                        "report": report,
                        "saved_path": saved_path
                    }
                }
            else:
                yield event

    def _format_planner_event(self, state: Dict | None) -> Dict:
        """格式化 Planner 节点事件"""
        if not state:
            return {
                "type": "status",
                "stage": "planner",
                "message": "规划节点执行中"
            }

        plan = state.get("plan", [])

        return {
            "type": "plan",
            "stage": "plan_created",
            "message": f"执行计划已制定，共 {len(plan)} 个步骤",
            "plan": plan
        }

    def _format_executor_event(self, state: Dict | None) -> Dict:
        """格式化 Executor 节点事件"""
        if not state:
            return {
                "type": "status",
                "stage": "executor",
                "message": "执行节点运行中"
            }

        plan = state.get("plan", [])
        past_steps = state.get("past_steps", [])

        if past_steps:
            last_step, _ = past_steps[-1]
            return {
                "type": "step_complete",
                "stage": "step_executed",
                "message": f"步骤执行完成 ({len(past_steps)}/{len(past_steps) + len(plan)})",
                "current_step": last_step,
                "remaining_steps": len(plan)
            }
        else:
            return {
                "type": "status",
                "stage": "executor",
                "message": "开始执行步骤"
            }

    def _format_replanner_event(self, state: Dict | None) -> Dict:
        """格式化 Replanner 节点事件"""
        if not state:
            return {
                "type": "status",
                "stage": "replanner",
                "message": "评估节点运行中"
            }

        response = state.get("response", "")
        plan = state.get("plan", [])

        if response:
            # 已生成最终响应
            return {
                "type": "report",
                "stage": "final_report",
                "message": "最终报告已生成",
                "report": response
            }
        else:
            # 重新规划
            return {
                "type": "status",
                "stage": "replanner",
                "message": f"评估完成，{'继续执行剩余步骤' if plan else '准备生成最终响应'}",
                "remaining_steps": len(plan)
            }


# 全局单例
aiops_service = AIOpsService()

# 导出 graph 供 LangGraph Studio 使用
graph = aiops_service.graph
