"""Pydantic 数据模型：HTTP API 的请求/响应结构。

gRPC 服务自身使用 protobuf 消息，此处的模型用于 FastAPI 层和 Repository。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

CollectorType = Literal["perf_cpu", "ebpf_io", "pyspy", "continuous_perf"]


class AgentRegistration(BaseModel):
    """Agent 注册请求（gRPC InitAgent.RegisterAgent 的同构 HTTP 版本）。"""

    agent_id: str
    hostname: str
    ip_addr: str
    version: str = "0.1.0"
    os_info: str = "unknown"
    capabilities: list[CollectorType] = Field(default_factory=list)


class AgentMetrics(BaseModel):
    """Agent 自身上报的资源指标。"""

    cpu_percent: float = 0.0
    rss_mb: float = 0.0
    read_kb_s: float = 0.0
    write_kb_s: float = 0.0
    children_count: int = 0


class CreateTaskRequest(BaseModel):
    """Web 创建任务的请求体。"""

    name: str
    agent_id: str
    target_pid: int
    collector_type: CollectorType
    sample_rate: int = 99
    duration_sec: int = 15
    options: dict[str, Any] = Field(default_factory=dict)
