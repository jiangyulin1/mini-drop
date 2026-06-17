"""智能归因编排入口。

串联证据采集 → 候选生成 → 置信度校准 → LLM 推理 → 校验修复 → 反馈闭环。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from server.app.rca.calibrator import calibrate, format_for_llm
from server.app.rca.candidates import generate_candidates
from server.app.rca.evidence import collect_evidence
from server.app.rca.llm_client import diagnose
from server.app.rca.models import (
    DiagnosisReport,
    EvidenceInput,
    FeedbackPrior,
    RCAFeedback,
    ValidatedReport,
)


def run_diagnosis(
    task_id: str,
    task_record,
    top_functions: list[dict] | None = None,
    ebpf_metrics: dict | None = None,
    suggestions: list[str] | None = None,
    failure_events: list[str] | None = None,
    baseline_diff: dict | None = None,
    agent_stats: dict | None = None,
    feedback_priors: dict[str, FeedbackPrior] | None = None,
    model_name: str | None = None,
) -> ValidatedReport:
    """执行一次完整的智能归因。

    Args:
        task_id: 任务 ID。
        task_record: 任务记录。
        top_functions: TopN 热点函数。
        ebpf_metrics: eBPF IO 延迟分布。
        suggestions: 规则引擎建议。
        failure_events: 失败原因列表。
        baseline_diff: 历史基线差异。
        agent_stats: Agent 资源开销。
        feedback_priors: 历史反馈先验。
        model_name: LLM 模型，默认从环境变量读取。

    Returns:
        ValidatedReport。
    """
    model = model_name or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # 1. 证据采集
    evidence = collect_evidence(
        task_id=task_id,
        task_record=task_record,
        top_functions=top_functions,
        ebpf_metrics=ebpf_metrics,
        suggestions=suggestions,
        failure_events=failure_events,
        baseline_diff=baseline_diff,
        agent_stats=agent_stats,
    )

    # 2. 候选归因生成
    candidates = generate_candidates(evidence, feedback_priors)

    # 3. 置信度校准
    calibrated = calibrate(candidates, evidence, feedback_priors)
    candidates_json = format_for_llm(calibrated)

    # 4. LLM 推理（含校验 + 自修复）
    result = diagnose(task_id, evidence, candidates_json, model_name=model)

    return result
