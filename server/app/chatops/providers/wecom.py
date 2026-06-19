"""企业微信机器人 Webhook 提供者。"""

from __future__ import annotations

import json
import re

import requests

from server.app.chatops.base import BaseProvider, ChatopsMessage


class WeComProvider(BaseProvider):
    """企业微信群机器人 Markdown 消息推送。"""

    LEVEL_COLORS = {
        "info": "info",
        "warning": "warning",
        "error": "warning",
        "success": "info",
    }

    def send(self, message: ChatopsMessage, webhook_url: str) -> bool:
        payload = self._build_payload(message)
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    def validate_webhook_url(self, url: str) -> bool:
        return bool(re.match(r"^https://qyapi\.weixin\.qq\.com/cgi-bin/webhook/send\?key=[\w-]+$", url))

    def _build_payload(self, msg: ChatopsMessage) -> dict:
        level_tag = {"info": "ℹ️", "warning": "⚠️", "error": "🚨", "success": "✅"}.get(msg.level, "")
        content_lines = [
            f"{level_tag} **{msg.title}**",
            "",
            msg.content,
        ]
        if msg.extra_fields:
            content_lines.append("")
            for field in msg.extra_fields:
                content_lines.append(f"> {field.get('label', '')}: **{field.get('value', '-')}**")
        if msg.link_url:
            content_lines.append("")
            content_lines.append(f"[{msg.link_text}]({msg.link_url})")

        return {
            "msgtype": "markdown",
            "markdown": {
                "content": self._truncate("\n".join(content_lines), 4096),
            },
        }


def _post_json(url: str, payload: dict, timeout: int = 10):
    return requests.post(url, json=payload, timeout=timeout)
