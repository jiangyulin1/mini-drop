"""ChatOps 消息模型与发送器抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatopsMessage:
    """平台无关的消息结构。"""
    title: str
    content: str
    level: str = "info"  # info | warning | error | success
    extra_fields: list[dict[str, str]] = field(default_factory=list)
    link_url: str = ""
    link_text: str = ""


class BaseProvider(ABC):
    """IM 平台提供者抽象基类。"""

    @abstractmethod
    def send(self, message: ChatopsMessage, webhook_url: str) -> bool:
        """发送消息到指定 webhook。返回 True 表示成功。"""
        ...

    @abstractmethod
    def validate_webhook_url(self, url: str) -> bool:
        """校验 webhook URL 格式是否合法。"""
        ...

    @staticmethod
    def _truncate(text: str, max_len: int = 4000) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len - 3] + "…"
