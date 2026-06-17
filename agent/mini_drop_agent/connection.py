"""gRPC connection management for the Agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, TypeVar

import grpc

T = TypeVar("T")


@dataclass
class GrpcConnection:
    address: str
    _channel: grpc.Channel | None = field(default=None, init=False)

    @property
    def channel(self) -> grpc.Channel:
        if self._channel is None:
            self._channel = grpc.insecure_channel(self.address)
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
