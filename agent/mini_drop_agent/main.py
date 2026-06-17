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
from agent.mini_drop_agent.collectors.ebpf import EBPFCollector
from agent.mini_drop_agent.collectors.perf import PerfCollector
from agent.mini_drop_agent.collectors.pyspy import PySpyCollector
from agent.mini_drop_agent.config import AgentConfig, load_config
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
}

CAPABILITIES = sorted(COLLECTORS.keys())


# ── 任务执行 ───────────────────────────────────────────────────────


def _run_collector(task_payload: dict[str, Any]) -> tuple[bool, str, list[dict[str, Any]]]:
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
    return result.ok, result.reason, result.artifacts


# ── gRPC 客户端 ───────────────────────────────────────────────────


def _register(config: AgentConfig) -> None:
    """通过 gRPC InitAgent.RegisterAgent 注册自身元数据。"""
    channel = grpc.insecure_channel(config.server_grpc_addr)
    stub = init_pb2_grpc.InitAgentStub(channel)
    try:
        stub.RegisterAgent(
            init_pb2.RegisterAgentRequest(
                agent_id=config.agent_id,
                hostname=socket.gethostname(),
                ip_addr="127.0.0.1",
                version="0.1.0",
                os_info=_os_info(),
                capabilities=CAPABILITIES,
            ),
            timeout=5,
        )
    finally:
        channel.close()


def _heartbeat(config: AgentConfig) -> dict[str, Any] | None:
    """通过 gRPC HealthCheck.Do 发送心跳，返回待执行任务或 None。"""
    channel = grpc.insecure_channel(config.server_grpc_addr)
    stub = healthcheck_pb2_grpc.HealthCheckStub(channel)
    try:
        resp = stub.Do(
            healthcheck_pb2.HealthCheckRequest(
                agent_id=config.agent_id,
                hostname=socket.gethostname(),
                ip_addr="127.0.0.1",
                agent_version="0.1.0",
            ),
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
    finally:
        channel.close()


def _notify_result(config: AgentConfig, task_id: str, ok: bool, reason: str, artifacts: list[dict]) -> None:
    """通过 gRPC Hotmethod.NotifyResult 上报采集结果。"""
    channel = grpc.insecure_channel(config.server_grpc_addr)
    stub = hotmethod_pb2_grpc.HotmethodStub(channel)
    try:
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
    finally:
        channel.close()


# ── 主循环 ─────────────────────────────────────────────────────────

_should_exit = False


def _on_signal(signum, frame):
    global _should_exit
    _should_exit = True


def main() -> None:
    global _should_exit
    config = load_config()

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    _register(config)
    print(f"[agent] 注册成功 agent_id={config.agent_id}")

    while not _should_exit:
        try:
            task = _heartbeat(config)
        except grpc.RpcError as exc:
            print(f"[agent] 心跳失败: {exc.code()} {exc.details()}")
            time.sleep(config.heartbeat_interval_sec)
            continue

        if task is None:
            time.sleep(config.heartbeat_interval_sec)
            continue

        print(f"[agent] 拉取任务 task_id={task['id']} collector={task['collector_type']} pid={task['target_pid']}")
        ok, reason, artifacts = _run_collector(task)

        try:
            _notify_result(config, task["id"], ok, reason, artifacts)
        except grpc.RpcError as exc:
            print(f"[agent] 上报结果失败: {exc.code()} {exc.details()}")
            continue

        if ok:
            print(f"[agent] 任务完成 task_id={task['id']}")
        else:
            print(f"[agent] 任务失败 task_id={task['id']} reason={reason}")

        time.sleep(config.heartbeat_interval_sec)


# ── 辅助 ───────────────────────────────────────────────────────────


def _profiler_to_collector(profiler_type: int) -> str:
    mapping = {0: "perf_cpu", 3: "pyspy", 4: "ebpf_io"}
    return mapping.get(profiler_type, "perf_cpu")


def _os_info() -> str:
    try:
        with open("/proc/version", "r") as fh:
            return fh.readline().strip()
    except FileNotFoundError:
        return "unknown"


if __name__ == "__main__":
    main()
