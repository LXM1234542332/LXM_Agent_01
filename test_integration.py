"""
AI Ops 诊断功能集成测试

测试完整的诊断流程，包括 API 调用
"""

import asyncio
import json
import httpx
from datetime import datetime
from loguru import logger

# 配置日志
logger.remove()
logger.add(
    "logs/test_integration_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    rotation="500 MB"
)


async def test_aiops_api():
    """测试 AI Ops API"""
    logger.info("=" * 80)
    logger.info("集成测试：AI Ops API 诊断")
    logger.info("=" * 80)

    api_url = "http://localhost:9900/api/aiops"
    session_id = f"integration-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    logger.info(f"API 地址: {api_url}")
    logger.info(f"会话 ID: {session_id}")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 发送诊断请求
            logger.info("发送诊断请求...")

            async with client.stream(
                "POST",
                api_url,
                json={"session_id": session_id},
                headers={"Content-Type": "application/json"}
            ) as response:
                logger.info(f"响应状态码: {response.status_code}")

                if response.status_code != 200:
                    logger.error(f"❌ API 返回错误: {response.status_code}")
                    return False

                # 处理流式响应
                event_count = 0
                step_count = 0
                report_received = False

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    # 解析 SSE 事件
                    if line.startswith("data: "):
                        try:
                            event_data = json.loads(line[6:])
                            event_type = event_data.get("type", "unknown")
                            event_count += 1

                            logger.info(f"事件 {event_count}: {event_type}")

                            # 处理不同类型的事件
                            if event_type == "status":
                                message = event_data.get("message", "")
                                logger.info(f"  状态: {message}")

                            elif event_type == "plan":
                                plan = event_data.get("plan", [])
                                logger.info(f"  计划步骤数: {len(plan)}")

                            elif event_type == "step_complete":
                                step_count += 1
                                current_step = event_data.get("current_step", "")
                                logger.info(f"  步骤 {step_count}: {current_step[:50]}...")

                            elif event_type == "report":
                                report_received = True
                                report = event_data.get("report", "")
                                logger.info(f"  诊断报告长度: {len(report)} 字符")
                                logger.info(f"  报告预览:\n{report[:300]}...")

                            elif event_type == "complete":
                                logger.info("  诊断完成")

                            elif event_type == "error":
                                message = event_data.get("message", "")
                                logger.error(f"  错误: {message}")

                        except json.JSONDecodeError as e:
                            logger.warning(f"无法解析事件: {e}")

                logger.info(f"✓ 共收到 {event_count} 个事件，完成 {step_count} 个步骤")
                logger.info(f"✓ 诊断报告已生成: {report_received}")

                if report_received and step_count > 0:
                    logger.info("✅ 集成测试通过")
                    return True
                else:
                    logger.error("❌ 集成测试失败：未收到完整的诊断结果")
                    return False

    except httpx.ConnectError:
        logger.error("❌ 无法连接到 API 服务器")
        logger.error("   请确保应用已启动: python -m uvicorn app.main:app --host 0.0.0.0 --port 9900")
        return False

    except Exception as e:
        logger.error(f"❌ 集成测试失败: {e}", exc_info=True)
        return False


async def test_diagnostic_tools_directly():
    """直接测试诊断工具"""
    logger.info("=" * 80)
    logger.info("单元测试：诊断工具")
    logger.info("=" * 80)

    try:
        from diagnostic_tools import DiagnosticDataTools

        tools = DiagnosticDataTools()

        # 测试各个工具
        tests = [
            ("get_alerts", lambda: tools.get_alerts()),
            ("get_error_logs", lambda: tools.get_error_logs(limit=5)),
            ("get_metrics_by_name", lambda: tools.get_metrics_by_name("db_connections", limit=10)),
            ("get_metrics_anomalies", lambda: tools.get_metrics_anomalies()),
            ("get_deployment_events", lambda: tools.get_deployment_events()),
        ]

        passed = 0
        failed = 0

        for tool_name, tool_func in tests:
            try:
                result = tool_func()
                status = result.get("status", "unknown")

                if status == "success":
                    count = result.get("count", 0)
                    logger.info(f"✓ {tool_name}: {count} 条数据")
                    passed += 1
                else:
                    logger.error(f"✗ {tool_name}: 返回错误状态")
                    failed += 1

            except Exception as e:
                logger.error(f"✗ {tool_name}: {e}")
                failed += 1

        logger.info(f"✓ 通过: {passed}/{len(tests)}")
        logger.info(f"✗ 失败: {failed}/{len(tests)}")

        if failed == 0:
            logger.info("✅ 所有诊断工具测试通过")
            return True
        else:
            logger.error("❌ 部分诊断工具测试失败")
            return False

    except Exception as e:
        logger.error(f"❌ 诊断工具测试失败: {e}", exc_info=True)
        return False


async def main():
    """运行所有集成测试"""
    logger.info("=" * 80)
    logger.info("AI Ops 诊断功能集成测试")
    logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    logger.info("")

    results = {}

    # 测试 1：诊断工具
    logger.info("运行测试 1：诊断工具...")
    results["diagnostic_tools"] = await test_diagnostic_tools_directly()
    logger.info("")

    # 测试 2：API 集成
    logger.info("运行测试 2：API 集成...")
    results["api_integration"] = await test_aiops_api()
    logger.info("")

    # 总结
    logger.info("=" * 80)
    logger.info("测试总结")
    logger.info("=" * 80)

    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{test_name}: {status}")

    all_passed = all(results.values())

    if all_passed:
        logger.info("\n✅ 所有集成测试通过！")
    else:
        logger.error("\n❌ 部分集成测试失败")

    logger.info(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
