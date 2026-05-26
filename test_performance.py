"""
AI Ops 诊断功能性能测试

测试诊断流程的性能指标
"""

import asyncio
import time
import json
from datetime import datetime
from loguru import logger

# 配置日志
logger.remove()
logger.add(
    "logs/test_performance_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    rotation="500 MB"
)


async def test_diagnostic_tools_performance():
    """测试诊断工具的性能"""
    logger.info("=" * 80)
    logger.info("性能测试 1：诊断工具性能")
    logger.info("=" * 80)

    try:
        from diagnostic_tools import DiagnosticDataTools

        tools = DiagnosticDataTools()

        # 定义测试用例
        test_cases = [
            ("get_alerts", lambda: tools.get_alerts()),
            ("get_error_logs", lambda: tools.get_error_logs(limit=20)),
            ("get_metrics_by_name", lambda: tools.get_metrics_by_name("db_connections", limit=60)),
            ("get_metrics_anomalies", lambda: tools.get_metrics_anomalies()),
            ("get_deployment_events", lambda: tools.get_deployment_events()),
            ("get_logs_by_keyword", lambda: tools.get_logs_by_keyword("connection", limit=20)),
        ]

        results = {}

        for tool_name, tool_func in test_cases:
            # 预热
            tool_func()

            # 测试 10 次
            times = []
            for _ in range(10):
                start = time.time()
                result = tool_func()
                elapsed = time.time() - start
                times.append(elapsed)

            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)

            results[tool_name] = {
                "avg": avg_time,
                "min": min_time,
                "max": max_time
            }

            logger.info(f"{tool_name}:")
            logger.info(f"  平均: {avg_time*1000:.2f}ms")
            logger.info(f"  最小: {min_time*1000:.2f}ms")
            logger.info(f"  最大: {max_time*1000:.2f}ms")

        # 计算总体性能
        total_avg = sum(r["avg"] for r in results.values())
        logger.info(f"\n总体平均耗时: {total_avg*1000:.2f}ms")

        logger.info("✅ 诊断工具性能测试完成\n")

        return results

    except Exception as e:
        logger.error(f"❌ 诊断工具性能测试失败: {e}", exc_info=True)
        return {}


async def test_diagnostic_flow_performance():
    """测试诊断流程的性能"""
    logger.info("=" * 80)
    logger.info("性能测试 2：诊断流程性能")
    logger.info("=" * 80)

    try:
        from app.services.aiops_service import aiops_service

        session_id = f"perf-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        logger.info(f"启动诊断流程，会话 ID: {session_id}")

        # 记录各个阶段的时间
        timings = {
            "total_start": time.time(),
            "planner_start": None,
            "planner_end": None,
            "executor_start": None,
            "executor_end": None,
            "replanner_start": None,
            "replanner_end": None,
            "total_end": None
        }

        step_count = 0
        event_count = 0

        async for event in aiops_service.diagnose(session_id=session_id):
            event_type = event.get("type", "unknown")
            event_count += 1

            # 记录阶段时间
            if event_type == "status" and "planner" in event.get("stage", "").lower():
                if timings["planner_start"] is None:
                    timings["planner_start"] = time.time()

            elif event_type == "plan":
                timings["planner_end"] = time.time()
                timings["executor_start"] = time.time()

            elif event_type == "step_complete":
                step_count += 1

            elif event_type == "report":
                timings["replanner_end"] = time.time()

            elif event_type == "complete":
                timings["total_end"] = time.time()
                break

        # 计算耗时
        logger.info("诊断流程耗时统计:")

        if timings["planner_start"] and timings["planner_end"]:
            planner_time = timings["planner_end"] - timings["planner_start"]
            logger.info(f"  Planner: {planner_time:.2f}s")

        if timings["executor_start"] and timings["replanner_start"]:
            executor_time = timings["replanner_start"] - timings["executor_start"]
            logger.info(f"  Executor: {executor_time:.2f}s ({step_count} 个步骤)")

        if timings["replanner_start"] and timings["replanner_end"]:
            replanner_time = timings["replanner_end"] - timings["replanner_start"]
            logger.info(f"  Replanner: {replanner_time:.2f}s")

        if timings["total_start"] and timings["total_end"]:
            total_time = timings["total_end"] - timings["total_start"]
            logger.info(f"  总耗时: {total_time:.2f}s")

        logger.info(f"  事件数: {event_count}")
        logger.info(f"  步骤数: {step_count}")

        logger.info("✅ 诊断流程性能测试完成\n")

        return timings

    except Exception as e:
        logger.error(f"❌ 诊断流程性能测试失败: {e}", exc_info=True)
        return {}


async def test_report_generation_performance():
    """测试诊断报告生成的性能"""
    logger.info("=" * 80)
    logger.info("性能测试 3：诊断报告生成性能")
    logger.info("=" * 80)

    try:
        from diagnostic_tools import DiagnosticDataTools
        from app.services.diagnosis_report_generator import diagnosis_report_generator

        tools = DiagnosticDataTools()

        # 收集诊断数据
        logger.info("收集诊断数据...")
        alerts = tools.get_alerts()
        errors = tools.get_error_logs()
        anomalies = tools.get_metrics_anomalies()
        deployments = tools.get_deployment_events()

        # 模拟执行步骤
        past_steps = [
            ("获取告警", json.dumps(alerts, ensure_ascii=False, indent=2)),
            ("获取错误日志", json.dumps(errors, ensure_ascii=False, indent=2)),
            ("获取异常指标", json.dumps(anomalies, ensure_ascii=False, indent=2)),
            ("获取部署事件", json.dumps(deployments, ensure_ascii=False, indent=2)),
        ]

        # 测试报告生成性能
        logger.info("生成诊断报告...")

        times = []
        for i in range(5):
            start = time.time()
            report = diagnosis_report_generator.generate_report({}, past_steps)
            elapsed = time.time() - start
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        logger.info(f"报告生成性能:")
        logger.info(f"  平均: {avg_time*1000:.2f}ms")
        logger.info(f"  最小: {min_time*1000:.2f}ms")
        logger.info(f"  最大: {max_time*1000:.2f}ms")
        logger.info(f"  报告大小: {len(report)} 字符")

        logger.info("✅ 诊断报告生成性能测试完成\n")

        return {
            "avg": avg_time,
            "min": min_time,
            "max": max_time,
            "report_size": len(report)
        }

    except Exception as e:
        logger.error(f"❌ 诊断报告生成性能测试失败: {e}", exc_info=True)
        return {}


async def main():
    """运行所有性能测试"""
    logger.info("=" * 80)
    logger.info("AI Ops 诊断功能性能测试")
    logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    logger.info("")

    # 测试 1：诊断工具性能
    logger.info("运行性能测试 1：诊断工具...")
    tools_perf = await test_diagnostic_tools_performance()

    # 测试 2：诊断流程性能
    logger.info("运行性能测试 2：诊断流程...")
    flow_perf = await test_diagnostic_flow_performance()

    # 测试 3：报告生成性能
    logger.info("运行性能测试 3：报告生成...")
    report_perf = await test_report_generation_performance()

    # 总结
    logger.info("=" * 80)
    logger.info("性能测试总结")
    logger.info("=" * 80)

    if tools_perf:
        logger.info("诊断工具性能: ✅")
    if flow_perf:
        logger.info("诊断流程性能: ✅")
    if report_perf:
        logger.info("报告生成性能: ✅")

    logger.info(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
