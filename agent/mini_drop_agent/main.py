"""Mini-Drop Agent：gRPC 客户端，心跳拉取任务并执行采集。

启动流程：
  config ← 环境变量
  → InitAgent.RegisterAgent（注册元数据）
  → loop:
      → HealthCheck.Do（心跳 + 拉取任务）
      → 如有任务 → 执行采集 → Hotmethod.NotifyResult（上报结果）
      → sleep 5s
"""

from __future__ import annotations

import json
import os
import signal
import socket
import time
from typing import Any

import grpc

from agent.mini_drop_agent.collectors.base import CollectorTask
from agent.mini_drop_agent.collectors.continuous import ContinuousCollector
from agent.mini_drop_agent.collectors.ebpf import EBPFCollector
from agent.mini_drop_agent.collectors.perf import PerfCollector
from agent.mini_drop_agent.collectors.pyspy import PySpyCollector
from agent.mini_drop_agent.artifact_upload import maybe_upload_artifacts
from agent.mini_drop_agent.connection import GrpcConnection
from agent.mini_drop_agent.config import AgentConfig, load_config
from agent.mini_drop_agent.logging_utils import log_event
from agent.mini_drop_agent.metrics import ProcessStatsSampler
from server.app.generated import (
    healthcheck_pb2,
    healthcheck_pb2_grpc,
    hotmethod_pb2,
    hotmethod_pb2_grpc,
    init_pb2,
    init_pb2_grpc,
)

# ── 采集器注册 ────────────────────────────────────────────────────

COLLECTORS = {
    "perf_cpu": PerfCollector(),
    "ebpf_io": EBPFCollector(),
    "pyspy": PySpyCollector(),
    "continuous_perf": ContinuousCollector(),
}

CAPABILITIES = sorted(COLLECTORS.keys())


# ── 任务执行 ───────────────────────────────────────────────────────


def _run_collector(task_payload: dict[str, Any], config: AgentConfig | None = None) -> tuple[bool, str, list[dict[str, Any]]]:
    """执行采集任务：构造 CollectorTask 后分发到注册的采集器。

    如果 collector_type 不在 COLLECTORS 中，明确上报失败。
    """
    collector_type = task_payload.get("collector_type", "perf_cpu")
    collector = COLLECTORS.get(collector_type)
    if collector is None:
        return False, f"collector {collector_type} 未在此 Agent 构建中注册", []

    collector_task = CollectorTask(
        id=task_payload["id"],
        collector_type=collector_type,
        target_pid=task_payload["target_pid"],
        sample_rate=task_payload.get("sample_rate", 99),
        duration_sec=task_payload.get("duration_sec", 15),
        options=task_payload.get("request_params", {}).get("options", {}),
    )
    result = collector.collect(collector_task)
    artifacts = result.artifacts
    if result.ok and config is not None:
        try:
            artifacts = maybe_upload_artifacts(task_payload["id"], result.artifacts, config)
        except Exception as exc:
            return False, f"artifact upload failed: {exc}", result.artifacts
    return result.ok, result.reason, artifacts


# ── gRPC 客户端 ───────────────────────────────────────────────────


def _register(stub: init_pb2_grpc.InitAgentStub, config: AgentConfig) -> None:
    """通过 gRPC InitAgent.RegisterAgent 注册自身元数据。"""
    stub.RegisterAgent(
        init_pb2.RegisterAgentRequest(
            agent_id=config.agent_id,
            hostname=socket.gethostname(),
            ip_addr=config.agent_ip_addr,
            version="0.1.0",
            os_info=_os_info(),
            capabilities=CAPABILITIES,
        ),
        timeout=5,
    )


def _heartbeat(
    stub: healthcheck_pb2_grpc.HealthCheckStub,
    config: AgentConfig,
    sampler: ProcessStatsSampler | None = None,
) -> dict[str, Any] | None:
    """通过 gRPC HealthCheck.Do 发送心跳，返回待执行任务或 None。"""
    request = healthcheck_pb2.HealthCheckRequest(
        agent_id=config.agent_id,
        hostname=socket.gethostname(),
        ip_addr=config.agent_ip_addr,
        agent_version="0.1.0",
    )
    if sampler is not None:
        _fill_pid_stats(request.self_pstats, sampler.sample_self())
        _fill_pid_stats(request.children_pstats, sampler.sample_children())
    resp = stub.Do(
        request,
        timeout=5,
    )
    if resp.pending and resp.task_desc.task_id:
        return {
            "id": resp.task_desc.task_id,
            "collector_type": _profiler_to_collector(resp.task_desc.profiler_type),
            "target_pid": resp.task_desc.sample_argv.pid,
            "sample_rate": resp.task_desc.sample_argv.hz,
            "duration_sec": resp.task_desc.sample_argv.duration,
            "request_params": {
                "options": {
                    "callgraph": resp.task_desc.sample_argv.callgraph,
                    "event": resp.task_desc.sample_argv.event,
                },
            },
        }
    return None


def _notify_result(
    stub: hotmethod_pb2_grpc.HotmethodStub,
    task_id: str,
    ok: bool,
    reason: str,
    artifacts: list[dict],
) -> None:
    """通过 gRPC Hotmethod.NotifyResult 上报采集结果。"""
    if ok:
        stub.NotifyResult(
            hotmethod_pb2.TaskResult(
                task_id=task_id,
                error_message="",
                artifact_type="raw",
                artifact_metadata_json=json.dumps(artifacts),
            ),
            timeout=10,
        )
    else:
        stub.NotifyResult(
            hotmethod_pb2.TaskResult(
                task_id=task_id,
                error_message=reason,
            ),
            timeout=10,
        )


# ── 主循环 ─────────────────────────────────────────────────────────

_should_exit = False


def _on_signal(signum, frame):
    global _should_exit
    _should_exit = True


def main() -> None:
    global _should_exit
    config = load_config()
    conn = GrpcConnection(config.server_grpc_addr, auth_token=config.grpc_auth_token)
    sampler = ProcessStatsSampler()

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    _register(init_pb2_grpc.InitAgentStub(conn.channel), config)
    log_event("info", "agent_registered", agent_id=config.agent_id, ip_addr=config.agent_ip_addr)

    while not _should_exit:
        try:
            task = conn.call_with_retry(
                lambda: _heartbeat(healthcheck_pb2_grpc.HealthCheckStub(conn.channel), config, sampler)
            )
        except grpc.RpcError as exc:
            log_event("error", "heartbeat_failed", code=exc.code(), details=exc.details())
            time.sleep(config.heartbeat_interval_sec)
            continue

        if task is None:
            time.sleep(config.heartbeat_interval_sec)
            continue

        log_event(
            "info",
            "task_pulled",
            task_id=task["id"],
            collector=task["collector_type"],
            pid=task["target_pid"],
        )
        ok, reason, artifacts = _run_collector(task, config)

        try:
            conn.call_with_retry(
                lambda: _notify_result(
                    hotmethod_pb2_grpc.HotmethodStub(conn.channel),
                    task["id"],
                    ok,
                    reason,
                    artifacts,
                )
            )
        except grpc.RpcError as exc:
            log_event("error", "notify_result_failed", task_id=task["id"], code=exc.code(), details=exc.details())
            continue

        if ok:
            log_event("info", "task_completed", task_id=task["id"], artifact_count=len(artifacts))
        else:
            log_event("error", "task_failed", task_id=task["id"], reason=reason)

        time.sleep(config.heartbeat_interval_sec)

    conn.close()


# ── 辅助 ───────────────────────────────────────────────────────────


def _profiler_to_collector(profiler_type: int) -> str:
    mapping = {0: "perf_cpu", 3: "pyspy", 4: "ebpf_io"}
    return mapping.get(profiler_type, "perf_cpu")


def _fill_pid_stats(message, stats: dict[str, Any]) -> None:
    message.cpu_percent = float(stats.get("cpu_percent", 0.0) or 0.0)
    message.rss_mb = float(stats.get("rss_mb", 0.0) or 0.0)
    message.read_kb_s = float(stats.get("read_kb_s", 0.0) or 0.0)
    message.write_kb_s = float(stats.get("write_kb_s", 0.0) or 0.0)
    message.children_count = int(stats.get("children_count", 0) or 0)


def _os_info() -> str:
    try:
        with open("/proc/version", "r") as fh:
            return fh.readline().strip()
    except FileNotFoundError:
        return "unknown"


if __name__ == "__main__":
    main()
