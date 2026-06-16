"""Agent 配置加载：从环境变量读取，提供合理默认值。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentConfig:
    agent_id: str
    server_grpc_addr: str
    heartbeat_interval_sec: int = 5


def load_config() -> AgentConfig:
    return AgentConfig(
        agent_id=os.getenv("AGENT_ID", "agent_local_demo"),
        server_grpc_addr=os.getenv("AGENT_GRPC_ADDR", "localhost:50051"),
        heartbeat_interval_sec=int(os.getenv("AGENT_HEARTBEAT_INTERVAL_SEC", "5")),
    )
