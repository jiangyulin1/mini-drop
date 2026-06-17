"""micro-drop command line interface.

The CLI is intentionally script-friendly: commands print JSON by default and
avoid depending on a running browser. It complements the Web UI for SSH,
automation, CI checks, batch jobs and diff analysis.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from server.app.ai_provider import get_ai_settings
from server.app.nlp.intent_parser import parse_intent
from server.app.nlp.summarizer import summarize, suggest_followup
from server.app.rca.models import EvidenceInput
from server.app.rca.report import run_diagnosis_context


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="micro-drop", description="Micro-Drop profiling CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="start Server + Web API")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8191)

    sub.add_parser("agent", help="start profiling Agent")
    sub.add_parser("ai-config", help="print resolved AI provider and feature flags")

    p_parse = sub.add_parser("parse", help="parse natural language into profiling intent")
    p_parse.add_argument("query", nargs="+")

    p_sum = sub.add_parser("summarize", help="summarize a TopN JSON file")
    p_sum.add_argument("--top-json", required=True)
    p_sum.add_argument("--collector", default="perf_cpu")

    p_diag = sub.add_parser("diagnose-local", help="run local RCA from structured evidence JSON")
    p_diag.add_argument("--evidence", required=True)

    p_diff = sub.add_parser("diff-top", help="compare two TopN JSON files")
    p_diff.add_argument("--base", required=True)
    p_diff.add_argument("--head", required=True)
    p_diff.add_argument("--threshold", type=float, default=5.0)

    args = parser.parse_args(argv)
    return _COMMANDS[args.command](args)


def _cmd_serve(args) -> int:
    import uvicorn
    uvicorn.run("server.app.main:app", host=args.host, port=args.port)
    return 0


def _cmd_agent(_args) -> int:
    from agent.mini_drop_agent.main import main as agent_main
    agent_main()
    return 0


def _cmd_ai_config(_args) -> int:
    settings = get_ai_settings()
    _print_json({
        "enabled": settings.enabled,
        "provider": settings.provider,
        "base_url": settings.base_url,
        "model": settings.model,
        "has_api_key": bool(settings.api_key),
        "features": {
            "nlp": settings.nlp_enabled,
            "rca": settings.rca_enabled,
            "summarize": settings.summarize_enabled,
        },
    })
    return 0


def _cmd_parse(args) -> int:
    intent = parse_intent(" ".join(args.query))
    _print_json(intent.to_dict())
    return 0


def _cmd_summarize(args) -> int:
    top = _read_json(args.top_json)
    summary = summarize(top)
    _print_json({
        "summary": summary,
        "followup_questions": suggest_followup(top, args.collector),
    })
    return 0


def _cmd_diagnose_local(args) -> int:
    evidence_data = _read_json(args.evidence)
    evidence = EvidenceInput(**evidence_data)
    task_record = _TaskRecord(evidence.task_metadata)
    outcome = run_diagnosis_context(
        task_id=task_record.id,
        task_record=task_record,
        top_functions=evidence.top_functions,
        ebpf_metrics=evidence.ebpf_metrics,
        suggestions=evidence.suggestions,
        failure_events=evidence.failure_events,
        baseline_diff=evidence.baseline_diff,
        agent_stats=evidence.agent_stats,
        auto_execute_safe=False,
    )
    _print_json({
        "report": outcome.report.report.model_dump(),
        "validated": outcome.report.validated,
        "tool_results": [item.model_dump() for item in outcome.tool_results],
        "repair_plan": outcome.repair_plan.model_dump() if outcome.repair_plan else None,
    })
    return 0


def _cmd_diff_top(args) -> int:
    base = _top_map(_read_json(args.base))
    head = _top_map(_read_json(args.head))
    names = sorted(set(base) | set(head))
    changes = []
    failed = False
    for name in names:
        delta = round(head.get(name, 0.0) - base.get(name, 0.0), 2)
        if abs(delta) >= args.threshold:
            failed = True
        if delta:
            changes.append({
                "name": name,
                "base_percent": base.get(name, 0.0),
                "head_percent": head.get(name, 0.0),
                "delta_percent": delta,
            })
    _print_json({
        "threshold": args.threshold,
        "failed": failed,
        "changes": sorted(changes, key=lambda item: abs(item["delta_percent"]), reverse=True),
    })
    return 2 if failed else 0


def _read_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _top_map(rows: list[dict]) -> dict[str, float]:
    return {str(item.get("name")): float(item.get("percent", 0.0)) for item in rows}


def _print_json(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


class _TaskRecord:
    def __init__(self, metadata: dict):
        self.id = metadata.get("task_id", "cli_task")
        self.agent_id = metadata.get("agent_id", "cli_agent")
        self.collector_type = metadata.get("collector_type", "perf_cpu")
        self.target_pid = int(metadata.get("target_pid", 0))
        self.sample_rate = int(metadata.get("sample_rate", 99))
        self.duration_sec = int(metadata.get("duration_sec", 15))
        self.status = metadata.get("status", "DONE")
        self.status_reason = metadata.get("status_reason", "CLI local diagnosis")
        self.request_params = metadata.get("request_params", {})


_COMMANDS = {
    "serve": _cmd_serve,
    "agent": _cmd_agent,
    "ai-config": _cmd_ai_config,
    "parse": _cmd_parse,
    "summarize": _cmd_summarize,
    "diagnose-local": _cmd_diagnose_local,
    "diff-top": _cmd_diff_top,
}


if __name__ == "__main__":
    raise SystemExit(main())
