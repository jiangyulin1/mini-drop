"""轻量级异步事件总线。

支持 Server-Sent Events (SSE) 实时推送到前端：
任务状态变更、Agent 上下线、诊断完成等事件即时通知，
减少无效轮询请求。
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
from datetime import datetime, timezone
from typing import Any

# 每类事件最多保留的历史条数
MAX_HISTORY = 64


class EventBus:
    """线程安全的发布-订阅事件总线。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[queue.Queue] = []
        self._history: list[dict[str, Any]] = []

    def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """发布事件。通知所有订阅者并记录历史。"""
        event = {
            "event": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._history.append(event)
            if len(self._history) > MAX_HISTORY:
                self._history = self._history[-MAX_HISTORY:]
            dead: list[queue.Queue] = []
            for q in self._subscribers:
                try:
                    q.put_nowait(event)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)

    def subscribe(self) -> queue.Queue:
        """注册一个订阅者队列。调用方负责取消订阅时 clean up。"""
        q: queue.Queue = queue.Queue(maxsize=256)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        """取消订阅。"""
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def get_history(self, since: str | None = None) -> list[dict[str, Any]]:
        """获取历史事件（可选地：仅返回 since 时间戳之后的事件）。"""
        with self._lock:
            if since is None:
                return list(self._history)
            return [e for e in self._history if e["timestamp"] > since]


# 全局单例
BUS = EventBus()


# ── 便捷发布函数（供 Server/gRPC 服务调用） ──────────────


def notify_task_changed(task_id: str, from_status: str, to_status: str, reason: str = "") -> None:
    BUS.publish("task_changed", {
        "task_id": task_id,
        "from_status": from_status,
        "to_status": to_status,
        "reason": reason,
    })


def notify_agent_status(agent_id: str, status: str, ip_addr: str = "") -> None:
    BUS.publish("agent_status", {
        "agent_id": agent_id,
        "status": status,
        "ip_addr": ip_addr,
    })


def notify_diagnosis_complete(task_id: str, diagnosis_id: str, status: str) -> None:
    BUS.publish("diagnosis_complete", {
        "task_id": task_id,
        "diagnosis_id": diagnosis_id,
        "status": status,
    })
