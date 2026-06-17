"""micro-drop command line interface.

The CLI is intentionally script-friendly: commands print JSON by default and
avoid depending on a running browser. It complements the Web UI for SSH,
automation, CI checks, batch jobs and diff analysis.
"""

from __future__ import annotations

import argparse
import json
import time
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

    p_ci = sub.add_parser("ci-check", help="fail CI when TopN diff exceeds threshold")
    p_ci.add_argument("--base", required=True)
    p_ci.add_argument("--head", required=True)
    p_ci.add_argument("--threshold", type=float, default=5.0)

    p_alert = sub.add_parser("alert", help="evaluate hotspot thresholds from TopN JSON")
    p_alert.add_argument("--top-json", required=True)
    p_alert.add_argument("--hotspot-threshold", type=float, default=70.0)
    p_alert.add_argument("--sample-threshold", type=int, default=0)

    p_batch = sub.add_parser("batch-diagnose", help="run local RCA for a directory of evidence JSON files")
    p_batch.add_argument("--dir", required=True)
    p_batch.add_argument("--pattern", default="*.json")

    p_export = sub.add_parser("export-summary", help="export TopN summary as markdown or JSON")
    p_export.add_argument("--top-json", required=True)
    p_export.add_argument("--format", choices=["json", "markdown"], default="json")
    p_export.add_argument("--limit", type=int, default=10)

    p_watch = sub.add_parser("watch-task", help="poll a Server task until terminal status")
    p_watch.add_argument("--url", default="http://localhost:8191")
    p_watch.add_argument("--task-id", required=True)
    p_watch.add_argument("--interval", type=float, default=2.0)
    p_watch.add_argument("--timeout", type=float, default=120.0)

    p_keywords = sub.add_parser("keywords", help="print CLI keyword dictionaries")
    p_keywords.add_argument("--kind", choices=["all", "commands", "collectors", "causes", "fields"], default="all")

    p_suggest = sub.add_parser("suggest", help="suggest commands/keywords for a prefix")
    p_suggest.add_argument("prefix", nargs="?", default="")
    p_suggest.add_argument("--kind", choices=["all", "commands", "collectors", "causes", "fields"], default="all")

    p_completion = sub.add_parser("completion", help="print shell completion script")
    p_completion.add_argument("--shell", choices=["bash", "zsh", "powershell"], required=True)

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
    _print_json(_diagnose_local_payload(args.evidence))
    return 0


def _cmd_diff_top(args) -> int:
    result = _diff_top(args.base, args.head, args.threshold)
    _print_json(result)
    return 2 if result["failed"] else 0


def _cmd_ci_check(args) -> int:
    result = _diff_top(args.base, args.head, args.threshold)
    result["ci_status"] = "failed" if result["failed"] else "passed"
    _print_json(result)
    return 2 if result["failed"] else 0


def _cmd_alert(args) -> int:
    top = _read_json(args.top_json)
    top1 = top[0] if top else {}
    percent = float(top1.get("percent", 0.0))
    samples = int(top1.get("samples", 0))
    triggered = percent >= args.hotspot_threshold and samples >= args.sample_threshold
    _print_json({
        "triggered": triggered,
        "reason": "hotspot_threshold_exceeded" if triggered else "within_threshold",
        "top_function": top1.get("name", ""),
        "percent": percent,
        "samples": samples,
        "thresholds": {
            "hotspot_percent": args.hotspot_threshold,
            "samples": args.sample_threshold,
        },
    })
    return 2 if triggered else 0


def _cmd_batch_diagnose(args) -> int:
    rows = []
    for path in sorted(Path(args.dir).glob(args.pattern)):
        try:
            report = _diagnose_local_payload(str(path))
            rows.append({
                "file": str(path),
                "ok": True,
                "summary": report["report"].get("summary", ""),
                "top_cause": (report["report"].get("ranked_causes") or [{}])[0].get("cause_id"),
            })
        except Exception as exc:
            rows.append({"file": str(path), "ok": False, "error": str(exc)})
    _print_json({"total": len(rows), "items": rows})
    return 1 if any(not item["ok"] for item in rows) else 0


def _cmd_export_summary(args) -> int:
    top = _read_json(args.top_json)[:args.limit]
    if args.format == "markdown":
        print("| Rank | Function | Samples | Percent |")
        print("|---:|---|---:|---:|")
        for idx, item in enumerate(top, start=1):
            print(f"| {idx} | `{item.get('name', '')}` | {item.get('samples', 0)} | {item.get('percent', 0)}% |")
    else:
        _print_json({"top_functions": top})
    return 0


def _cmd_watch_task(args) -> int:
    import requests
    deadline = time.time() + args.timeout
    last = None
    while time.time() <= deadline:
        resp = requests.get(f"{args.url.rstrip('/')}/api/tasks/{args.task_id}", timeout=5)
        resp.raise_for_status()
        data = resp.json()["data"]
        last = data
        status = data.get("status")
        print(json.dumps(data, ensure_ascii=False, default=str))
        if status in {"DONE", "FAILED"}:
            return 0 if status == "DONE" else 2
        time.sleep(args.interval)
    _print_json({"status": "TIMEOUT", "last": last})
    return 124


def _cmd_keywords(args) -> int:
    _print_json(_filter_keywords(args.kind))
    return 0


def _cmd_suggest(args) -> int:
    prefix = args.prefix.lower()
    result = {}
    for key, values in _filter_keywords(args.kind).items():
        result[key] = [item for item in values if item.lower().startswith(prefix)]
    _print_json(result)
    return 0


def _cmd_completion(args) -> int:
    print(_completion_script(args.shell))
    return 0


def _read_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _top_map(rows: list[dict]) -> dict[str, float]:
    return {str(item.get("name")): float(item.get("percent", 0.0)) for item in rows}


def _diff_top(base_path: str, head_path: str, threshold: float) -> dict:
    base = _top_map(_read_json(base_path))
    head = _top_map(_read_json(head_path))
    names = sorted(set(base) | set(head))
    changes = []
    failed = False
    for name in names:
        delta = round(head.get(name, 0.0) - base.get(name, 0.0), 2)
        if abs(delta) >= threshold:
            failed = True
        if delta:
            changes.append({
                "name": name,
                "base_percent": base.get(name, 0.0),
                "head_percent": head.get(name, 0.0),
                "delta_percent": delta,
            })
    return {
        "threshold": threshold,
        "failed": failed,
        "changes": sorted(changes, key=lambda item: abs(item["delta_percent"]), reverse=True),
    }


def _diagnose_local_payload(evidence_path: str) -> dict:
    evidence_data = _read_json(evidence_path)
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
    return {
        "report": outcome.report.report.model_dump(),
        "validated": outcome.report.validated,
        "tool_results": [item.model_dump() for item in outcome.tool_results],
        "repair_plan": outcome.repair_plan.model_dump() if outcome.repair_plan else None,
    }


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
    "ci-check": _cmd_ci_check,
    "alert": _cmd_alert,
    "batch-diagnose": _cmd_batch_diagnose,
    "export-summary": _cmd_export_summary,
    "watch-task": _cmd_watch_task,
    "keywords": _cmd_keywords,
    "suggest": _cmd_suggest,
    "completion": _cmd_completion,
}


_KEYWORDS = {
    "commands": sorted(_COMMANDS.keys()),
    "collectors": ["perf_cpu", "ebpf_io", "pyspy", "continuous_perf"],
    "causes": [
        "cpu_hotspot_recursive",
        "io_wait_high",
        "python_userland_hotspot",
        "agent_overhead",
        "collector_permission_denied",
        "target_pid_invalid",
        "insufficient_data",
    ],
    "fields": [
        "top_functions",
        "top_functions[0].name",
        "top_functions[0].percent",
        "ebpf_metrics.io_latency_us",
        "baseline_diff",
        "agent_stats.max_cpu_percent",
        "task_metadata.status",
        "failure_events",
        "tool_results.get_flamegraph_top",
    ],
}


def _filter_keywords(kind: str) -> dict[str, list[str]]:
    if kind == "all":
        return _KEYWORDS
    return {kind: _KEYWORDS[kind]}


def _completion_script(shell: str) -> str:
    words = _completion_words()
    if shell == "bash":
        return (
            "_micro_drop_complete() {\n"
            "  local cur=\"${COMP_WORDS[COMP_CWORD]}\"\n"
            f"  COMPREPLY=( $(compgen -W \"{' '.join(words)}\" -- \"$cur\") )\n"
            "}\n"
            "complete -F _micro_drop_complete micro-drop\n"
        )
    if shell == "zsh":
        zsh_words = " ".join(_shell_single_quote(word) for word in words)
        return (
            "#compdef micro-drop\n"
            "_micro_drop() {\n"
            f"  compadd -- {zsh_words}\n"
            "}\n"
            "compdef _micro_drop micro-drop\n"
        )
    ps_words = ", ".join(_powershell_single_quote(word) for word in words)
    return (
        "Register-ArgumentCompleter -Native -CommandName micro-drop -ScriptBlock {\n"
        "  param($wordToComplete)\n"
        f"  @({ps_words}) | Where-Object {{ $_ -like \"$wordToComplete*\" }}\n"
        "}\n"
    )


def _completion_words() -> list[str]:
    words = []
    for values in _KEYWORDS.values():
        words.extend(values)
    return sorted(set(words))


def _shell_single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _powershell_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


if __name__ == "__main__":
    raise SystemExit(main())
