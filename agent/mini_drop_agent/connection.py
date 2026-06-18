"""gRPC connection management for the Agent."""

from __future__ import annotations

from collections import namedtuple
from dataclasses import dataclass, field
from typing import Callable, Sequence, TypeVar

import grpc

T = TypeVar("T")

_ClientCallDetails = namedtuple(
    "_ClientCallDetails",
    ("method", "timeout", "metadata", "credentials", "wait_for_ready", "compression"),
)


class _AuthClientInterceptor(grpc.UnaryUnaryClientInterceptor):
    def __init__(self, token: str):
        self._token = token

    def intercept_unary_unary(self, continuation, client_call_details, request):
        metadata: Sequence[tuple[str, str]] = client_call_details.metadata or ()
        details = _ClientCallDetails(
            method=client_call_details.method,
            timeout=client_call_details.timeout,
            metadata=tuple(metadata) + (("x-mini-drop-grpc-token", self._token),),
            credentials=client_call_details.credentials,
            wait_for_ready=client_call_details.wait_for_ready,
            compression=client_call_details.compression,
        )
        return continuation(details, request)


@dataclass
class GrpcConnection:
    address: str
    auth_token: str = ""
    _channel: grpc.Channel | None = field(default=None, init=False)

    @property
    def channel(self) -> grpc.Channel:
        if self._channel is None:
            channel = grpc.insecure_channel(self.address)
            if self.auth_token:
                channel = grpc.intercept_channel(channel, _AuthClientInterceptor(self.auth_token))
            self._channel = channel
        return self._channel

    def close(self) -> None:
        if self._channel is not None:
            self._channel.close()
            self._channel = None

    def reconnect(self) -> None:
        self.close()

    def call_with_retry(self, func: Callable[[], T], max_retries: int = 1) -> T:
        last_exc: grpc.RpcError | None = None
        for attempt in range(max_retries + 1):
            try:
                return func()
            except grpc.RpcError as exc:
                last_exc = exc
                if attempt >= max_retries or exc.code() != grpc.StatusCode.UNAVAILABLE:
                    raise
                self.reconnect()
        raise last_exc
