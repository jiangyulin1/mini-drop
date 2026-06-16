"""gRPC 服务器启动模块。

在后台线程中运行 gRPC server（端口 50051），
与 FastAPI HTTP server（端口 8191）共存于同一进程。
两者共享同一个 Repository 实例。
"""

from __future__ import annotations

from concurrent import futures
from typing import Any

import grpc

from server.app.generated import (
    control_pb2_grpc,
    healthcheck_pb2_grpc,
    hotmethod_pb2_grpc,
    init_pb2_grpc,
)
from server.app.grpc_services.control_service import ControlService
from server.app.grpc_services.healthcheck_service import HealthCheckService
from server.app.grpc_services.hotmethod_service import HotmethodService
from server.app.grpc_services.init_service import InitAgentService


def serve(repo: Any, port: int = 50051) -> grpc.Server:
    """创建并启动 gRPC server。

    Returns:
        grpc.Server 实例，调用方负责在进程退出时调用 server.stop()。
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    init_pb2_grpc.add_InitAgentServicer_to_server(InitAgentService(repo), server)
    healthcheck_pb2_grpc.add_HealthCheckServicer_to_server(HealthCheckService(repo), server)
    hotmethod_pb2_grpc.add_HotmethodServicer_to_server(HotmethodService(repo), server)
    control_pb2_grpc.add_ControlServicer_to_server(ControlService(repo), server)

    address = f"0.0.0.0:{port}"
    server.add_insecure_port(address)
    server.start()
    return server


def serve_in_background(repo: Any, port: int = 50051) -> grpc.Server:
    """在后台守护线程启动 gRPC server，主线程继续执行 HTTP server。"""

    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    init_pb2_grpc.add_InitAgentServicer_to_server(InitAgentService(repo), grpc_server)
    healthcheck_pb2_grpc.add_HealthCheckServicer_to_server(HealthCheckService(repo), grpc_server)
    hotmethod_pb2_grpc.add_HotmethodServicer_to_server(HotmethodService(repo), grpc_server)
    control_pb2_grpc.add_ControlServicer_to_server(ControlService(repo), grpc_server)

    grpc_server.add_insecure_port(f"0.0.0.0:{port}")
    grpc_server.start()

    return grpc_server
