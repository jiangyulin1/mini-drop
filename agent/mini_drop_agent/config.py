"""Agent 配置加载：从环境变量读取，提供合理默认值。"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    agent_id: str
    server_grpc_addr: str
    agent_ip_addr: str
    heartbeat_interval_sec: int = 5
    grpc_auth_token: str = ""
    upload_artifacts: bool = False
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "mini_drop"
    minio_secret_key: str = "mini_drop_secret"
    minio_bucket: str = "mini-drop"


def load_config() -> AgentConfig:
    server_grpc_addr = os.getenv("AGENT_GRPC_ADDR", "localhost:50051")
    return AgentConfig(
        agent_id=os.getenv("AGENT_ID", "agent_local_demo"),
        server_grpc_addr=server_grpc_addr,
        agent_ip_addr=_resolve_ip(server_grpc_addr),
        heartbeat_interval_sec=int(os.getenv("AGENT_HEARTBEAT_INTERVAL_SEC", "5")),
        grpc_auth_token=os.getenv("MINI_DROP_GRPC_TOKEN", os.getenv("MINI_DROP_API_KEY", "")),
        upload_artifacts=os.getenv("AGENT_UPLOAD_ARTIFACTS", "0").strip().lower() in {"1", "true", "yes", "on"},
        minio_endpoint=os.getenv("MINIO_ENDPOINT", "minio:9000"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY", "mini_drop"),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY", "mini_drop_secret"),
        minio_bucket=os.getenv("MINIO_BUCKET", "mini-drop"),
    )


def _resolve_ip(server_grpc_addr: str) -> str:
    explicit = os.getenv("AGENT_IP_ADDR", "").strip()
    if explicit:
        return explicit

    host, port = _split_host_port(server_grpc_addr)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((host, port))
            return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"


def _split_host_port(address: str) -> tuple[str, int]:
    host, sep, port = address.rpartition(":")
    if not sep:
        return address, 50051
    try:
        return host or "localhost", int(port)
    except ValueError:
        return host or "localhost", 50051
