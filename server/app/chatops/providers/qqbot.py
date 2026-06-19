"""QQ 机器人提供者（基于 OneBot v11 标准）。

支持两种连接模式：

模式 A — HTTP（主动调用）：
  需要 NapCat 开启 OneBot HTTP Server。
  MINI_DROP_CHATOPS_WEBHOOK_URL=http://localhost:5700

模式 B — WebSocket 反向连接（推荐，免配置端口）：
  Mini-Drop 启动内嵌 WebSocket 服务端，NapCat 作为客户端连入。
  双方通过 WS 双向通信，无需 NapCat 侧开启 HTTP。
  MINI_DROP_CHATOPS_WEBHOOK_URL=ws://0.0.0.0:5701

兼容框架：
  - NapCat        → https://github.com/NapNeko/NapCatQQ
  - go-cqhttp     → https://github.com/Mrs4s/go-cqhttp
  - Lagrange      → https://github.com/LagrangeDev/Lagrange

环境变量：
  MINI_DROP_CHATOPS_WEBHOOK_URL  OneBot API 地址（HTTP 或 WS）
  MINI_DROP_QQBOT_TARGET_TYPE    group | private（默认 group）
  MINI_DROP_QQBOT_TARGET_ID      目标群号或 QQ 号
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from typing import Any

import requests

from server.app.chatops.base import BaseProvider, ChatopsMessage
from server.app.logging_utils import log_event


class QQBotProvider(BaseProvider):
    """OneBot v11 消息发送器。

    自动检测 webhook_url 协议：
      - http://... → HTTP POST 模式
      - ws://...  → WebSocket 反向连接模式（自建 WS 服务端）
    """

    LEVEL_EMOJI = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "\U0001f6a8",
        "success": "✅",
    }

    MAX_MSG_LENGTH = 3500

    # WebSocket 模式状态
    _ws_server_started = False
    _ws_lock = threading.Lock()
    _ws_pending_actions: dict[str, asyncio.Future] = {}
    _ws_connections: dict = {}
    _ws_echo_seq = 0
    _ws_seq_lock = threading.Lock()

    def send(self, message: ChatopsMessage, webhook_url: str) -> bool:
        text = self._build_text(message)
        if not text:
            return False

        target_type = os.getenv("MINI_DROP_QQBOT_TARGET_TYPE", "group").strip()
        target_id = os.getenv("MINI_DROP_QQBOT_TARGET_ID", "").strip()
        if not target_id:
            log_event("warning", "chatops_qqbot_no_target_id")
            return False

        action = "send_group_msg" if target_type != "private" else "send_private_msg"
        key = "group_id" if target_type != "private" else "user_id"
        params = {
            "action": action,
            "params": {key: int(target_id), "message": text},
        }

        if webhook_url.startswith("ws://") or webhook_url.startswith("wss://"):
            return self._send_ws(webhook_url, params)
        else:
            return self._send_http(webhook_url, action, {key: int(target_id), "message": text})

    def validate_webhook_url(self, url: str) -> bool:
        if not url:
            return False
        return url.startswith("http://") or url.startswith("https://") or url.startswith("ws://") or url.startswith("wss://")

    # ── HTTP 模式 ────────────────────────────────────────

    def _send_http(self, base_url: str, action: str, params: dict) -> bool:
        endpoint = f"{base_url.rstrip('/')}/{action}"
        try:
            resp = requests.post(endpoint, json=params, timeout=10)
            return resp.status_code == 200 and resp.json().get("status") == "ok"
        except Exception:
            return False

    # ── WebSocket 模式 ────────────────────────────────────

    def _send_ws(self, bind_url: str, params: dict) -> bool:
        host, port = self._parse_ws_bind(bind_url)
        conn = self._ws_connections.get((host, port))
        if conn is None:
            return False

        try:
            import websockets
            seq = self._next_seq()
            params["echo"] = seq
            future: asyncio.Future = asyncio.get_event_loop().create_future()
            self._ws_pending_actions[str(seq)] = future

            asyncio.get_event_loop().call_soon_threadsafe(
                lambda: asyncio.ensure_future(self._ws_send_and_wait(conn, params, future))
            )

            try:
                result = future.result(timeout=15)
                return result.get("status") == "ok"
            except Exception:
                return False
        except ImportError:
            log_event("error", "chatops_qqbot_ws_no_websockets_lib",
                      hint="pip install websockets")
            return False
        except Exception as exc:
            log_event("warning", "chatops_qqbot_ws_send_failed", error=str(exc)[:100])
            return False

    async def _ws_send_and_wait(self, conn, params: dict, future: asyncio.Future):
        try:
            await conn.send(json.dumps(params, ensure_ascii=False))
        except Exception as exc:
            if not future.done():
                future.set_exception(exc)

    @staticmethod
    def _parse_ws_bind(url: str):
        url = url.replace("ws://", "http://").replace("wss://", "https://")
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.hostname or "0.0.0.0", parsed.port or 5701

    def _next_seq(self) -> int:
        with self._ws_seq_lock:
            self._ws_echo_seq += 1
            return self._ws_echo_seq

    # ── WebSocket 服务端启动 ──────────────────────────────

    @classmethod
    def start_ws_server(cls, webhook_url: str):
        """启动内嵌 WebSocket 服务端。

        在后台线程运行 asyncio event loop，接受 NapCat 作为客户端连入。
        """
        host, port = cls._parse_ws_bind(webhook_url)
        key = (host, port)

        with cls._ws_lock:
            if cls._ws_server_started:
                return
            cls._ws_server_started = True

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(cls._ws_serve(host, port, key))
            except Exception as exc:
                log_event("error", "chatops_qqbot_ws_server_error", error=str(exc)[:100])

        t = threading.Thread(target=_run, daemon=True, name="qqbot-ws-server")
        t.start()
        log_event("info", "chatops_qqbot_ws_server_started", host=host, port=port)

    @classmethod
    async def _ws_serve(cls, host: str, port: int, key: tuple):
        try:
            import websockets
        except ImportError:
            log_event("error", "chatops_qqbot_ws_no_websockets",
                      hint="pip install websockets to use QQ Bot WebSocket mode")
            return

        async def handler(websocket, path=""):
            cls._ws_connections[key] = websocket
            log_event("info", "chatops_qqbot_ws_client_connected", host=host, port=port)
            try:
                async for raw in websocket:
                    try:
                        data = json.loads(raw)
                        if "echo" in data:
                            echo_key = str(data["echo"])
                            future = cls._ws_pending_actions.pop(echo_key, None)
                            if future and not future.done():
                                future.set_result(data)
                    except json.JSONDecodeError:
                        pass
            except Exception:
                pass
            finally:
                cls._ws_connections.pop(key, None)
                log_event("info", "chatops_qqbot_ws_client_disconnected", host=host, port=port)

        async with websockets.serve(handler, host, port):
            await asyncio.Future()  # 永远运行

    # ── 消息格式化 ────────────────────────────────────────

    def _build_text(self, msg: ChatopsMessage) -> str:
        emoji = self.LEVEL_EMOJI.get(msg.level, "")

        lines = [
            f"{emoji} 【{msg.title}】",
            "",
            msg.content,
        ]

        if msg.extra_fields:
            lines.append("")
            lines.append("───")
            for field in msg.extra_fields:
                label = field.get("label", "")
                value = field.get("value", "-")
                lines.append(f"  {label}：{value}")

        if msg.link_url:
            lines.append("")
            lines.append(f"\U0001f517 {msg.link_text or '查看详情'}：{msg.link_url}")

        return self._truncate("\n".join(lines), self.MAX_MSG_LENGTH)
