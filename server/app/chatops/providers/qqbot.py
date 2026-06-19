"""QQ 机器人提供者（基于 OneBot v11 标准 HTTP API）。

兼容以下框架（个人用户无需企业认证）：
  - go-cqhttp     → https://github.com/Mrs4s/go-cqhttp
  - NapCat        → https://github.com/NapNeko/NapCatQQ
  - Lagrange.OneBot → https://github.com/LagrangeDev/Lagrange

前置条件：
  1. 部署上述任一框架，配置 QQ 号登录
  2. 开启 HTTP API（默认地址 http://localhost:5700）
  3. 将机器人号拉入目标群并授予发言权限

环境变量：
  MINI_DROP_QQBOT_API_URL=http://localhost:5700       # OneBot HTTP API 地址
  MINI_DROP_QQBOT_TARGET_TYPE=group                    # group | private
  MINI_DROP_QQBOT_TARGET_ID=123456789                  # 群号或 QQ 号
"""

from __future__ import annotations

import os

import requests

from server.app.chatops.base import BaseProvider, ChatopsMessage


class QQBotProvider(BaseProvider):
    """OneBot v11 标准 HTTP API 消息发送器。

    通过 send_group_msg / send_private_msg 接口发送文本消息。
    消息以纯文本形式发送，使用 emoji 区分严重程度。
    """

    LEVEL_EMOJI = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "🚨",
        "success": "✅",
    }

    MAX_MSG_LENGTH = 3500  # QQ 群消息实际限制约 4000 字符，留余量

    def send(self, message: ChatopsMessage, webhook_url: str) -> bool:
        """发送消息。

        通过 webhook_url 参数传入 OneBot HTTP API 的 base URL。
        目标群号/QQ 号从环境变量读取。
        """
        text = self._build_text(message)
        if not text:
            return False

        target_type = os.getenv("MINI_DROP_QQBOT_TARGET_TYPE", "group").strip()
        target_id = os.getenv("MINI_DROP_QQBOT_TARGET_ID", "").strip()
        if not target_id:
            return False

        if target_type == "private":
            endpoint = f"{webhook_url.rstrip('/')}/send_private_msg"
            payload = {
                "user_id": int(target_id),
                "message": text,
            }
        else:
            endpoint = f"{webhook_url.rstrip('/')}/send_group_msg"
            payload = {
                "group_id": int(target_id),
                "message": text,
            }

        try:
            resp = requests.post(endpoint, json=payload, timeout=10)
            return resp.status_code == 200 and resp.json().get("status") == "ok"
        except Exception:
            return False

    def validate_webhook_url(self, url: str) -> bool:
        """校验 URL：OneBot HTTP API 地址，例如 http://localhost:5700 或 http://192.168.1.100:5700。"""
        if not url:
            return False
        return url.startswith("http://") or url.startswith("https://")

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
            lines.append(f"🔗 {msg.link_text or '查看详情'}：{msg.link_url}")

        return self._truncate("\n".join(lines), self.MAX_MSG_LENGTH)
