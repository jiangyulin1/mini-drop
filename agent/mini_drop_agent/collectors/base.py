"""采集器统一接口。

所有采集器（perf / eBPF / py-spy / continuous）实现 collect(task) → CollectorResult。
Agent 主循环只依赖这个协议，不关心具体采集工具。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class CollectorTask:
    """描述一次采集任务的全部参数，从 gRPC TaskDesc 转换而来。"""

    id: str
    collector_type: str
    target_pid: int
    sample_rate: int
    duration_sec: int
    options: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CollectorResult:
    """采集器执行结果。"""

    ok: bool
    reason: str
    artifacts: list[dict] = field(default_factory=list)


class Collector(Protocol):
    """采集器统一接口。"""

    def collect(self, task: CollectorTask) -> CollectorResult:
        """执行采集并返回结果。"""
        ...
