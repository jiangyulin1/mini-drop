"""Optional token authentication for the Agent gRPC control plane."""

from __future__ import annotations

import os
import secrets
from collections.abc import Sequence
from typing import Any

import grpc

TOKEN_HEADER = "x-mini-drop-grpc-token"


class GrpcAuthInterceptor(grpc.ServerInterceptor):
    def intercept_service(self, continuation, handler_call_details):
        if not grpc_auth_enabled():
            return continuation(handler_call_details)
        if _metadata_has_valid_token(handler_call_details.invocation_metadata):
            return continuation(handler_call_details)
        return grpc.unary_unary_rpc_method_handler(_abort_unauthenticated)


def grpc_auth_enabled() -> bool:
    return os.getenv("MINI_DROP_GRPC_AUTH_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}


def grpc_auth_token() -> str:
    return os.getenv("MINI_DROP_GRPC_TOKEN", os.getenv("MINI_DROP_API_KEY", "")).strip()


def _metadata_has_valid_token(metadata: Sequence[tuple[str, str]] | None) -> bool:
    expected = grpc_auth_token()
    if not expected:
        return False
    for key, value in metadata or ():
        lowered = key.lower()
        token = _extract_token(lowered, value)
        if token and secrets.compare_digest(token, expected):
            return True
    return False


def _extract_token(key: str, value: str) -> str:
    if key == TOKEN_HEADER:
        return value.strip()
    if key == "authorization" and value.lower().startswith("bearer "):
        return value[7:].strip()
    return ""


def _abort_unauthenticated(request: Any, context: grpc.ServicerContext):
    context.abort(grpc.StatusCode.UNAUTHENTICATED, "invalid gRPC token")
