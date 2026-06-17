"""候选归因规则引擎。

基于结构化证据自动生成候选原因，LLM 不对凭空猜测负责——
候选原因由规则引擎和工具结果产生。
"""

from __future__ import annotations

from server.app.rca.models import CandidateCause, EvidenceInput, FeedbackPrior


# ── 规则定义 ──

_RULES = [
    {
        "candidate_id": "cpu_hotspot_recursive",
        "description": "单一计算函数占 CPU 采样数比例过高，可能存在递归或密集型计算瓶颈",
        "match": lambda ev: (
            len(ev.top_functions) > 0
            and ev.top_functions[0].get("percent", 0) > 40
            and any(kw in ev.top_functions[0].get("name", "").lower()
                    for kw in ("fib", "recursive", "loop", "compute", "hotspot"))
        ),
        "rule_score": 0.83,
    },
    {
        "candidate_id": "io_wait_high",
        "description": "块设备 IO 延迟异常，可能是磁盘带宽或 IOPS 达到上限",
        "match": lambda ev: (
            ev.ebpf_metrics is not None
            and "io_latency_us" in ev.ebpf_metrics
            and len(ev.ebpf_metrics.get("io_latency_us", {})) > 0
        ),
        "rule_score": 0.78,
    },
    {
        "candidate_id": "python_userland_hotspot",
        "description": "Python 用户态函数热点，与 perf 系统级热点一致，根因在应用层",
        "match": lambda ev: (
            ev.task_metadata.get("collector_type") == "pyspy"
            or any("python" in s.lower() for s in ev.suggestions)
        ),
        "rule_score": 0.72,
    },
    {
        "candidate_id": "agent_overhead",
        "description": "采集 Agent 自身资源开销过高，可能影响目标进程性能",
        "match": lambda ev: (
            ev.agent_stats is not None
            and ev.agent_stats.get("max_cpu_percent", 0) > 10
        ),
        "rule_score": 0.55,
    },
    {
        "candidate_id": "collector_permission_denied",
        "description": "采集权限不足导致采集失败或结果异常",
        "match": lambda ev: (
            ev.task_metadata.get("status") == "FAILED"
            and any("permission" in s.lower() or "权限" in s
                    for s in ev.failure_events)
        ),
        "rule_score": 0.90,
    },
    {
        "candidate_id": "target_pid_invalid",
        "description": "目标 PID 不存在或在采集期间退出",
        "match": lambda ev: (
            ev.task_metadata.get("status") == "FAILED"
            and any("不存在" in s or "exited" in s.lower() or "not found" in s.lower()
                    for s in ev.failure_events)
        ),
        "rule_score": 0.95,
    },
]


def generate_candidates(
    evidence: EvidenceInput,
    feedback_priors: dict[str, FeedbackPrior] | None = None,
) -> list[CandidateCause]:
    """规则引擎生成候选归因列表。

    Args:
        evidence: 结构化证据。
        feedback_priors: 历史反馈先验（可选），用于调整候选排序。

    Returns:
        按 rule_score 降序排列的候选原因列表。
    """
    candidates: list[CandidateCause] = []
    priors = feedback_priors or {}

    for rule in _RULES:
        try:
            matched = rule["match"](evidence)
        except Exception:
            matched = False

        if not matched:
            continue

        evidence_refs = _infer_refs(rule["candidate_id"], evidence)
        missing = _detect_missing_evidence(rule["candidate_id"], evidence)
        score = rule["rule_score"]

        # 反馈先验修正：正确反馈 +0.05，错误 -0.08
        if rule["candidate_id"] in priors:
            prior = priors[rule["candidate_id"]]
            score += prior.weight_delta

        candidates.append(CandidateCause(
            candidate_id=rule["candidate_id"],
            description=rule["description"],
            evidence_refs=evidence_refs,
            rule_score=min(max(score, 0.0), 1.0),
            missing_evidence=missing,
        ))

    candidates.sort(key=lambda c: c.rule_score, reverse=True)

    # 如果没有规则命中，生成一个兜底候选
    if not candidates:
        candidates.append(CandidateCause(
            candidate_id="insufficient_data",
            description="当前证据量不足以触发任何预置规则，建议补充采集",
            evidence_refs=[],
            rule_score=0.10,
            missing_evidence=["更长的采样时长", "多采集器交叉验证", "历史基线对比"],
        ))

    return candidates


def _infer_refs(candidate_id: str, evidence: EvidenceInput) -> list[str]:
    """根据候选原因类型推断相关证据引用字段。"""
    refs: list[str] = []
    mapping: dict[str, list[str]] = {
        "cpu_hotspot_recursive": ["top_functions[0]", "baseline_diff"],
        "io_wait_high": ["ebpf_metrics.io_latency_us", "baseline_diff"],
        "python_userland_hotspot": ["top_functions", "suggestions"],
        "agent_overhead": ["agent_stats"],
        "collector_permission_denied": ["failure_events", "task_metadata.status"],
        "target_pid_invalid": ["failure_events", "task_metadata.target_pid"],
    }
    return mapping.get(candidate_id, [])


def _detect_missing_evidence(candidate_id: str, evidence: EvidenceInput) -> list[str]:
    """检测当前证据中缺失的关键数据。"""
    missing: list[str] = []
    checks: dict[str, list[str]] = {
        "cpu_hotspot_recursive": [],
        "io_wait_high": [],
        "python_userland_hotspot": [],
        "agent_overhead": [],
    }

    for check in checks.get(candidate_id, []):
        if check == "baseline" and not evidence.baseline_diff:
            missing.append("缺少历史基线对比数据")

    if not evidence.top_functions and candidate_id in ("cpu_hotspot_recursive", "python_userland_hotspot"):
        missing.append("缺少 TopN 热点函数数据")

    if not evidence.ebpf_metrics and candidate_id == "io_wait_high":
        missing.append("缺少 eBPF IO 延迟分布数据")

    return missing
