"""候选归因规则引擎。

规则定义外部化到 rules.json。配置文件只声明 match_type 和参数，
具体执行由本模块中的白名单 matcher 完成，避免把规则配置变成任意代码入口。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from server.app.rca.models import CandidateCause, EvidenceInput, FeedbackPrior

RULES_PATH = Path(__file__).with_name("rules.json")


def generate_candidates(
    evidence: EvidenceInput,
    feedback_priors: dict[str, FeedbackPrior] | None = None,
) -> list[CandidateCause]:
    """规则引擎生成候选归因列表。"""
    candidates: list[CandidateCause] = []
    priors = feedback_priors or {}

    for rule in load_rules():
        try:
            matched = _match_rule(rule, evidence)
        except Exception:
            matched = False

        if not matched:
            continue

        candidate_id = rule["candidate_id"]
        score = float(rule.get("rule_score", 0.0))
        if candidate_id in priors:
            score += priors[candidate_id].weight_delta

        candidates.append(CandidateCause(
            candidate_id=candidate_id,
            description=rule["description"],
            evidence_refs=_filter_available_refs(rule.get("evidence_refs", []), evidence),
            rule_score=min(max(score, 0.0), 1.0),
            missing_evidence=_detect_missing_evidence(candidate_id, evidence),
        ))

    candidates.sort(key=lambda item: item.rule_score, reverse=True)
    if not candidates:
        candidates.append(CandidateCause(
            candidate_id="insufficient_data",
            description="当前证据量不足以触发任何预置规则，建议补充采集",
            evidence_refs=[],
            rule_score=0.10,
            missing_evidence=["更长的采样时长", "多采集器交叉验证", "历史基线对比"],
        ))
    return candidates


@lru_cache(maxsize=1)
def load_rules(path: str | None = None) -> list[dict[str, Any]]:
    """加载外部规则配置。测试可传入 path 或 clear cache 后重载。"""
    rules_path = Path(path) if path else RULES_PATH
    data = json.loads(rules_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("RCA 规则文件必须是数组")
    for item in data:
        _validate_rule(item)
    return data


def _validate_rule(rule: dict[str, Any]) -> None:
    required = {"candidate_id", "description", "match_type", "rule_score"}
    missing = sorted(required - set(rule))
    if missing:
        raise ValueError(f"RCA 规则缺少字段: {', '.join(missing)}")
    if rule["match_type"] not in _MATCHERS:
        raise ValueError(f"未知 RCA match_type: {rule['match_type']}")


def _match_rule(rule: dict[str, Any], evidence: EvidenceInput) -> bool:
    matcher = _MATCHERS[rule["match_type"]]
    return matcher(evidence, rule.get("params", {}))


def _match_top_function_keyword(evidence: EvidenceInput, params: dict[str, Any]) -> bool:
    if not evidence.top_functions:
        return False
    top = evidence.top_functions[0]
    if float(top.get("percent", 0)) < float(params.get("min_percent", 40)):
        return False
    name = top.get("name", "").lower()
    return any(keyword.lower() in name for keyword in params.get("keywords", []))


def _match_ebpf_latency_present(evidence: EvidenceInput, _params: dict[str, Any]) -> bool:
    histogram = evidence.ebpf_metrics.get("io_latency_us", {}) if evidence.ebpf_metrics else {}
    return isinstance(histogram, dict) and len(histogram) > 0


def _match_collector_or_suggestion(evidence: EvidenceInput, params: dict[str, Any]) -> bool:
    collector_type = params.get("collector_type", "")
    if evidence.task_metadata.get("collector_type") == collector_type:
        return True
    keyword = params.get("suggestion_keyword", "").lower()
    return bool(keyword) and any(keyword in item.lower() for item in evidence.suggestions)


def _match_agent_cpu_overhead(evidence: EvidenceInput, params: dict[str, Any]) -> bool:
    threshold = float(params.get("min_cpu_percent", 10))
    return float(evidence.agent_stats.get("max_cpu_percent", 0)) > threshold


def _match_failure_contains(evidence: EvidenceInput, params: dict[str, Any]) -> bool:
    status = params.get("status")
    if status and evidence.task_metadata.get("status") != status:
        return False
    joined = "\n".join(evidence.failure_events).lower()
    return any(keyword.lower() in joined for keyword in params.get("keywords", []))


_MATCHERS = {
    "top_function_keyword": _match_top_function_keyword,
    "ebpf_latency_present": _match_ebpf_latency_present,
    "collector_or_suggestion": _match_collector_or_suggestion,
    "agent_cpu_overhead": _match_agent_cpu_overhead,
    "failure_contains": _match_failure_contains,
}


def _filter_available_refs(refs: list[str], evidence: EvidenceInput) -> list[str]:
    return [ref for ref in refs if _ref_available(ref, evidence)]


def _ref_available(ref: str, evidence: EvidenceInput) -> bool:
    top = ref.split(".", 1)[0].split("[", 1)[0]
    if top == "top_functions":
        return bool(evidence.top_functions)
    if top == "ebpf_metrics":
        return bool(evidence.ebpf_metrics)
    if top == "baseline_diff":
        return bool(evidence.baseline_diff)
    if top == "agent_stats":
        return bool(evidence.agent_stats)
    if top == "suggestions":
        return bool(evidence.suggestions)
    if top == "failure_events":
        return bool(evidence.failure_events)
    if top == "task_metadata":
        sub = ref.split(".", 1)[1] if "." in ref else ""
        return bool(evidence.task_metadata.get(sub)) if sub else bool(evidence.task_metadata)
    if top == "tool_results":
        tool_name = ref.split(".", 1)[1] if "." in ref else ""
        return any(item.get("tool_name") == tool_name for item in evidence.tool_results)
    return False


def _detect_missing_evidence(candidate_id: str, evidence: EvidenceInput) -> list[str]:
    missing: list[str] = []
    if not evidence.top_functions and candidate_id in ("cpu_hotspot_recursive", "python_userland_hotspot"):
        missing.append("缺少 TopN 热点函数数据")
    if not evidence.ebpf_metrics and candidate_id == "io_wait_high":
        missing.append("缺少 eBPF IO 延迟分布数据")
    if not evidence.baseline_diff and candidate_id in ("cpu_hotspot_recursive", "io_wait_high"):
        missing.append("缺少历史基线对比数据")
    return missing
