"""
AI Ops 诊断功能测试脚本

测试诊断流程的完整工作
"""

import asyncio
import json
from datetime import datetime
from loguru import logger

# 配置日志
logger.remove()
logger.add(
    "logs/test_diagnostic_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    rotation="500 MB"
)

# 导入诊断工具
from diagnostic_tools import DiagnosticDataTools

# 导入 AI Ops 服务
from app.services.aiops_service import aiops_service
from app.services.diagnosis_report_generator import diagnosis_report_generator


async def test_diagnostic_tools():
    """测试诊断工具"""
    logger.info("=" * 80)
    logger.info("测试 1：诊断工具测试")
    logger.info("=" * 80)

    tools = DiagnosticDataTools()

    # 测试 get_alerts
    logger.info("测试 get_alerts()...")
    alerts = tools.get_alerts()
    logger.info(f"✓ 获取告警数: {alerts.get('count', 0)}")

    # 测试 get_error_logs
    logger.info("测试 get_error_logs()...")
    errors = tools.get_error_logs(limit=5)
    logger.info(f"✓ 获取错误日志数: {errors.get('count', 0)}")

    # 测试 get_metrics_anomalies
    logger.info("测试 get_metrics_anomalies()...")
    anomalies = tools.get_metrics_anomalies()
    logger.info(f"✓ 获取异常指标数: {len(anomalies.get('anomalies', {}))}")

    # 测试 get_deployment_events
    logger.info("测试 get_deployment_events()...")
    deployments = tools.get_deployment_events()
    logger.info(f"✓ 获取部署事件数: {deployments.get('count', 0)}")

    logger.info("✅ 诊断工具测试完成\n")


async def test_diagnostic_flow():
    """测试诊断流程"""
    logger.info("=" * 80)
    logger.info("测试 2：诊断流程测试")
    logger.info("=" * 80)

    session_id = f"test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    logger.info(f"启动诊断，会话 ID: {session_id}")

    try:
        # 收集诊断事件
        events = []
        step_count = 0

        async for event in aiops_service.diagnose(session_id=session_id):
            event_type = event.get("type", "unknown")
            logger.info(f"收到事件: {event_type}")

            # 记录事件
            events.append(event)

            # 统计步骤
            if event_type == "step_complete":
                step_count += 1
                current_step = event.get("current_step", "未知")
                logger.info(f"  - 步骤 {step_count} 完成: {current_step[:50]}...")

            # 如果是完成事件，显示诊断报告预览
            if event_type == "report":
                report = event.get("report", "")
                logger.info(f"诊断报告长度: {len(report)} 字符")
                logger.info(f"报告预览:\n{report[:500]}...")

            # 如果是完成事件，停止收集
            if event_type == "complete":
                logger.info("诊断完成")
                break

        logger.info(f"✓ 诊断流程完成，共收到 {len(events)} 个事件，完成 {step_count} 个步骤")
        logger.info("✅ 诊断流程测试完成\n")

        return events

    except Exception as e:
        logger.error(f"❌ 诊断流程测试失败: {e}", exc_info=True)
        return []


async def test_diagnosis_report_generation():
    """测试诊断报告生成"""
    logger.info("=" * 80)
    logger.info("测试 3：诊断报告生成测试")
    logger.info("=" * 80)

    # 模拟诊断数据
    tools = DiagnosticDataTools()

    # 收集诊断数据
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

    try:
        # 生成诊断报告
        logger.info("生成诊断报告...")
        report = diagnosis_report_generator.generate_report({}, past_steps)

        logger.info(f"✓ 诊断报告生成完成，长度: {len(report)} 字符")

        # 保存报告到文件
        report_file = f"logs/test_diagnosis_report_{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info(f"✓ 诊断报告已保存到: {report_file}")

        # 显示报告预览
        logger.info(f"报告预览:\n{report[:500]}...")

        logger.info("✅ 诊断报告生成测试完成\n")

    except Exception as e:
        logger.error(f"❌ 诊断报告生成测试失败: {e}", exc_info=True)


async def test_mcp_server():
    """测试 MCP Server"""
    logger.info("=" * 80)
    logger.info("测试 4：MCP Server 测试")
    logger.info("=" * 80)

    try:
        from app.agent.mcp_client import get_mcp_client_with_retry

        # 获取 MCP 客户端
        logger.info("获取 MCP 客户端...")
        mcp_client = await get_mcp_client_with_retry()

        # 获取诊断工具
        logger.info("获取诊断工具...")
        tools = await mcp_client.get_tools()

        # 过滤诊断工具
        diagnostic_tools = [t for t in tools if "get_" in t.get("name", "")]
        logger.info(f"✓ 获取诊断工具数: {len(diagnostic_tools)}")

        # 列出工具
        for tool in diagnostic_tools[:5]:
            tool_name = tool.get("name", "未知")
            logger.info(f"  - {tool_name}")

        logger.info("✅ MCP Server 测试完成\n")

    except Exception as e:
        logger.error(f"❌ MCP Server 测试失败: {e}", exc_info=True)


async def main():
    """运行所有测试"""
    logger.info("=" * 80)
    logger.info("AI Ops 诊断功能测试")
    logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    logger.info("")

    # 测试 1：诊断工具
    try:
        await test_diagnostic_tools()
    except Exception as e:
        logger.error(f"测试 1 失败: {e}", exc_info=True)

    # 测试 2：诊断流程
    try:
        await test_diagnostic_flow()
    except Exception as e:
        logger.error(f"测试 2 失败: {e}", exc_info=True)

    # 测试 3：诊断报告生成
    try:
        await test_diagnosis_report_generation()
    except Exception as e:
        logger.error(f"测试 3 失败: {e}", exc_info=True)

    # 测试 4：MCP Server（可选，需要启动 MCP Server）
    try:
        await test_mcp_server()
    except Exception as e:
        logger.warning(f"测试 4 失败（可能是 MCP Server 未启动）: {e}")

    logger.info("=" * 80)
    logger.info(f"所有测试完成！结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
