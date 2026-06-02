"""
诊断准确率评估脚本（调试版本）

只评估前两个场景（scenario1 和 scenario2），用于快速调试。
所有评分逻辑与完整版本相同。
"""

import json
import re
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from dotenv import load_dotenv
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.llm_factory import llm_factory


class DiagnosisExtraction(BaseModel):
    """从诊断报告提取的结构化信息"""
    root_cause_service: str = Field(
        description="根因服务名（英文，如 payment-service、user-service 等）"
    )
    root_cause_type: str = Field(
        description="故障类型描述，用自然语言描述故障的核心原因（如超时、内存泄漏、CPU飙升、连接池耗尽等）"
    )


def extract_diagnosis_from_report(report_content: str, llm: ChatOpenAI) -> Optional[DiagnosisExtraction]:
    """
    从诊断报告中提取结构化信息

    Args:
        report_content: Markdown 格式的诊断报告
        llm: LLM 实例

    Returns:
        提取的诊断信息，或 None 如果提取失败
    """

    # 定义工具
    @tool
    def extract_diagnosis(
        root_cause_service: str,
        root_cause_type: str
    ) -> dict:
        """提取诊断信息"""
        return {
            "root_cause_service": root_cause_service,
            "root_cause_type": root_cause_type
        }

    # 绑定工具
    llm_with_tools = llm.bind_tools([extract_diagnosis])

    # 构建 prompt
    prompt = f"""你是一个诊断信息提取专家。请从以下诊断报告中提取结构化信息。

诊断报告：
{report_content}

请提取以下信息：

1. root_cause_service：根因服务名
   **根因服务的定义：直接发生故障的服务（故障源头），而不是因依赖故障而被连锁影响的上游服务或下游服务。**

   **判断标准（按优先级）：**
   - 哪个服务的告警/日志/指标**最先**出现异常？这个服务就是根因
   - 哪个服务的故障导致了上游服务的连锁故障？这个服务就是根因

   **重要：**
   - 在调用链 A → B → C → D 中，如果 C 出了问题，根因服务就是 C（不是 D或者 A）
   - A 和 B 因依赖 C 而被连锁影响，但它们不是根因，只是受影响服务
   - 从告警时序、日志时间戳、指标变化时间点来判断哪个服务首先出现异常

   **必须从以下服务列表中选择一个，不能编造或变形：**
   - payment-service
   - user-service
   - order-service
   - search-service
   - cache-service
   - database-service
   - notification-service
   - api-gateway

   **严格要求：**
   - 必须精确匹配列表中的服务名
   - 不能编造不在列表中的服务名
   - 必须直接来自报告中明确提到的根因服务
   - 如果报告中没有明确指出根因服务，选择最可能的一个

2. root_cause_type：故障类型描述
   **可以是以下形式之一：**
   - 关键词形式：timeout、memory_leak、cpu_spike、connection_pool、queue_backlog、process_crash、disk_full（包括但不限于这些）
   - 一句话描述：如果关键词无法充分表达故障原因，可以用一句话详细描述（如"新版本部署引入内存泄漏，导致内存使用率从 50% 飙升至 95%"）

   **要求：**
   - 必须准确反映报告中描述的故障类型
   - 如果一句话描述，应该简洁但完整，包含关键信息

请调用 extract_diagnosis 工具提交结果。"""

    try:
        response = llm_with_tools.invoke(prompt)

        # 检查是否有工具调用
        if not response.tool_calls:
            print(f"⚠️ LLM 未调用工具，响应：{response.content}")
            return None

        # 提取工具调用参数
        tool_call = response.tool_calls[0]
        args = tool_call["args"]

        # 验证并返回
        extraction = DiagnosisExtraction(**args)
        return extraction

    except Exception as e:
        print(f"❌ 提取失败：{e}")
        return None


def load_ground_truth(scenario_dir: Path) -> dict:
    """加载标准答案"""
    target_file = scenario_dir / "目标.json"
    if not target_file.exists():
        return None

    with open(target_file, "r", encoding="utf-8") as f:
        return json.load(f)


def load_report(scenario_dir: Path) -> str:
    """加载诊断报告"""
    report_file = scenario_dir / "运维agent报告.md"
    if not report_file.exists():
        return None

    with open(report_file, "r", encoding="utf-8") as f:
        return f.read()


def evaluate_root_cause_service(extracted: DiagnosisExtraction, ground_truth: dict) -> float:
    """根因服务定位：精确匹配，1.0 或 0.0"""
    expected = ground_truth.get("root_cause_service", "")
    actual = extracted.root_cause_service
    return 1.0 if expected == actual else 0.0


def evaluate_root_cause_type(extracted: DiagnosisExtraction, ground_truth: dict, llm: ChatOpenAI, n: int = 3) -> tuple[float, list[float]]:
    """用 LLM tool use 语义打分评估根因类型识别准确率，多次打分取平均"""
    expected_type = ground_truth.get("root_cause_type", "")
    actual_type = extracted.root_cause_type

    @tool
    def submit_similarity_score(score: float, reason: str) -> dict:
        """提交语义相似度评分"""
        return {"score": score, "reason": reason}

    llm_with_tools = llm.bind_tools([submit_similarity_score])

    prompt = f"""请评估以下两个故障类型描述的语义相似度，调用 submit_similarity_score 提交分数。

标准答案：{expected_type}
诊断结果：{actual_type}

评分范围：0.0 ~ 1.0 的连续分值，精确到小数点后两位。

参考锚点（可在锚点之间自由插值）：
- 1.0：语义完全等价，如"支付处理超时" 与 "timeout"
- 0.67：同一类故障，但描述粒度或侧重点有差异，如"内存泄漏" 与 "内存异常占用"
- 0.28：有一定关联但根因不同，如"超时" 与 "连接池耗尽"
- 0.0：完全无关"""

    scores = []
    for _ in range(n):
        try:
            response = llm_with_tools.invoke(prompt)
            if not response.tool_calls:
                continue
            args = response.tool_calls[0]["args"]
            score = float(args.get("score", 0.0))
            scores.append(min(1.0, max(0.0, score)))
        except Exception as e:
            print(f"⚠️ 根因类型评分失败：{e}")

    if not scores:
        return 0.0, []
    return round(sum(scores) / len(scores), 2), scores


def evaluate_evidence_completeness(report_content: str, extracted: DiagnosisExtraction, llm: ChatOpenAI, n: int = 3) -> tuple[float, list[float]]:
    """评估报告能否解释清楚「根因服务 发生了 故障类型」，多次打分取平均"""
    root_cause_service = extracted.root_cause_service
    root_cause_type = extracted.root_cause_type

    @tool
    def submit_evidence_score(score: float, reason: str) -> dict:
        """提交证据链完整性评分"""
        return {"score": score, "reason": reason}

    llm_with_tools = llm.bind_tools([submit_evidence_score])

    prompt = f"""请评估以下诊断报告能否解释清楚「{root_cause_service} 发生了 {root_cause_type}」。

诊断报告内容：
{report_content}

评分范围：0.0 ~ 1.0 的连续分值，精确到小数点后两位。

参考锚点（可在锚点之间自由插值）：
- 1.0：证据完整，完整解释了触发原因、故障现象、根因确认的完整链条
- 0.67：主要证据齐全，但有少量细节缺失或表述不够清晰
- 0.28：缺少关键证据，只能部分解释故障
- 0.0：证据严重不足，无法解释该服务发生该故障

请调用 submit_evidence_score 提交评分。"""

    scores = []
    for _ in range(n):
        try:
            response = llm_with_tools.invoke(prompt)
            if not response.tool_calls:
                continue
            args = response.tool_calls[0]["args"]
            score = float(args.get("score", 0.0))
            scores.append(min(1.0, max(0.0, score)))
        except Exception as e:
            print(f"⚠️ 证据链评分失败：{e}")

    if not scores:
        return 0.0, []
    return round(sum(scores) / len(scores), 2), scores


def evaluate_composite_score(
    extracted: DiagnosisExtraction,
    ground_truth: dict,
    service_score: float,
    type_score: float,
    evidence_score: float
) -> float:
    """计算综合评分"""
    composite = (
        0.40 * service_score +
        0.35 * type_score +
        0.25 * evidence_score
    )
    return composite


def evaluate_scenario(scenario_id: str, data_dir: Path, llm: ChatOpenAI) -> dict:
    """评估单个场景"""
    scenario_dir = data_dir / scenario_id

    # 加载数据
    ground_truth = load_ground_truth(scenario_dir)
    report = load_report(scenario_dir)

    if not ground_truth or not report:
        return {
            "scenario_id": scenario_id,
            "status": "failed",
            "error": "缺少数据文件"
        }

    # 提取信息
    extracted = extract_diagnosis_from_report(report, llm)
    if not extracted:
        return {
            "scenario_id": scenario_id,
            "status": "failed",
            "error": "提取失败"
        }

    # 第一步：根因服务定位（精确匹配）
    service_score = evaluate_root_cause_service(extracted, ground_truth)
    if service_score < 1.0:
        type_score, type_scores = 0.0, []
        evidence_score, evidence_scores = 0.0, []
    else:
        # 第二步：根因类型识别（LLM 打分）
        type_score, type_scores = evaluate_root_cause_type(extracted, ground_truth, llm)
        if type_score < 0.6:
            evidence_score, evidence_scores = 0.0, []
        else:
            # 第三步：证据链完整性（LLM 打分）
            evidence_score, evidence_scores = evaluate_evidence_completeness(report, extracted, llm)

    composite_score = 0.40 * service_score + 0.35 * type_score + 0.25 * evidence_score

    return {
        "scenario_id": scenario_id,
        "status": "success",
        "extracted": {
            "root_cause_service": extracted.root_cause_service,
            "root_cause_type": extracted.root_cause_type
        },
        "ground_truth": {
            "root_cause_service": ground_truth.get("root_cause_service"),
            "root_cause_type": ground_truth.get("root_cause_type")
        },
        "scores": {
            "root_cause_service_accuracy": service_score,
            "root_cause_type_accuracy": type_score,
            "evidence_completeness": evidence_score,
            "root_cause_accuracy": composite_score
        },
        "raw_scores": {
            "type_scores": type_scores,
            "evidence_scores": evidence_scores,
        }
    }


def save_to_markdown(results: list, output_file: Path):
    """将评估结果追加到 Markdown 文件，每次运行占两行（指标行 + 提取结果行）"""
    from datetime import datetime

    scenarios = [f"scenario{i}" for i in range(1, 3)]

    # 如果文件不存在，先写表头
    if not output_file.exists():
        header = "| 时间 |"
        separator = "| --- |"
        for s in scenarios:
            header += f" {s}_服务 | {s}_类型(明细) | {s}_证据(明细) | {s}_综合 |"
            separator += " --- | --- | --- | --- |"
        header += " 平均综合 |"
        separator += " --- |"
        with open(output_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(header + "\n" + separator + "\n")

    # 构建本次结果行（指标行）
    now = datetime.now().strftime("%m-%d %H:%M")
    row = f"| {now} |"
    extraction_row = "| 提取 |"

    scores_list = []
    for scenario_id in scenarios:
        result = next((r for r in results if r["scenario_id"] == scenario_id), None)
        if result and result["status"] == "success":
            s = result["scores"]
            raw = result.get("raw_scores", {})
            extracted = result.get("extracted", {})

            # 类型明细：每次打分 + 平均
            type_scores = raw.get("type_scores", [])
            type_detail = "/".join(f"{x:.2f}" for x in type_scores)
            type_cell = f"{type_detail}→{s['root_cause_type_accuracy']:.2f}" if type_scores else f"{s['root_cause_type_accuracy']:.2f}"

            # 证据明细：每次打分 + 平均
            evidence_scores = raw.get("evidence_scores", [])
            evidence_detail = "/".join(f"{x:.2f}" for x in evidence_scores)
            evidence_cell = f"{evidence_detail}→{s['evidence_completeness']:.2f}" if evidence_scores else f"{s['evidence_completeness']:.2f}"

            row += f" {s['root_cause_service_accuracy']:.0%} | {type_cell} | {evidence_cell} | {s['root_cause_accuracy']:.0%} |"
            scores_list.append(s["root_cause_accuracy"])

            # 提取结果行
            service = extracted.get("root_cause_service", "-")
            root_cause_type = extracted.get("root_cause_type", "-")
            extraction_row += f" {service} | {root_cause_type} | - | - |"
        else:
            row += " - | - | - | - |"
            extraction_row += " - | - | - | - |"

    avg = sum(scores_list) / len(scores_list) if scores_list else 0
    row += f" {avg:.0%} |"
    extraction_row += " - |"

    with open(output_file, "a", encoding="utf-8", newline="\n") as f:
        f.write(row + "\n")
        f.write(extraction_row + "\n")


def main():
    """主函数"""
    # 加载 .env 文件中的环境变量
    load_dotenv()

    # 配置
    data_dir = Path(__file__).parent.parent / "data"
    # 调试版本：只评估前两个场景
    # scenarios = [f"scenario{i}" for i in range(1, 3)]
    scenarios = ["scenario7"]

    # 初始化 LLM
    llm = llm_factory.create_chat_model(temperature=0.0, streaming=False, provider="deepseek")

    print("开始评估诊断准确率（调试版本 - 仅前两个场景）...\n")

    results = []
    for scenario_id in scenarios:
        print(f"评估 {scenario_id}...")
        result = evaluate_scenario(scenario_id, data_dir, llm)
        results.append(result)

        if result["status"] == "success":
            scores = result["scores"]
            print(f"  根因服务: {scores['root_cause_service_accuracy']:.2%}")
            print(f"  根因类型: {scores['root_cause_type_accuracy']:.2%}")
            print(f"  证据完整: {scores['evidence_completeness']:.2%}")
            print(f"  综合评分: {scores['root_cause_accuracy']:.2%}\n")
        else:
            print(f"  失败: {result['error']}\n")

    # 统计
    successful = [r for r in results if r["status"] == "success"]
    if successful:
        avg_service = sum(r["scores"]["root_cause_service_accuracy"] for r in successful) / len(successful)
        avg_type = sum(r["scores"]["root_cause_type_accuracy"] for r in successful) / len(successful)
        avg_evidence = sum(r["scores"]["evidence_completeness"] for r in successful) / len(successful)
        avg_composite = sum(r["scores"]["root_cause_accuracy"] for r in successful) / len(successful)

        print("=" * 50)
        print("评估总结（调试版本）")
        print("=" * 50)
        print(f"成功评估: {len(successful)}/{len(scenarios)}")
        print(f"根因服务平均准确率: {avg_service:.2%}")
        print(f"根因类型平均准确率: {avg_type:.2%}")
        print(f"证据完整性平均得分: {avg_evidence:.2%}")
        print(f"综合准确率: {avg_composite:.2%}")

    # 保存结果到 Markdown（调试版本使用单独的文件）
    output_file = Path(__file__).parent / "evaluation_results_debug.md"
    save_to_markdown(results, output_file)
    print(f"\n结果已追加到 {output_file}")


if __name__ == "__main__":
    main()
