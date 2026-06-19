"""Slack Incoming Webhook 提供者。"""

from __future__ import annotations

import re

import requests

from server.app.chatops.base import BaseProvider, ChatopsMessage


class SlackProvider(BaseProvider):
    """Slack Incoming Webhook (Block Kit) 消息推送。"""

    LEVEL_COLORS = {
        "info": "#1677ff",
        "warning": "#faad14",
        "error": "#ff4d4f",
        "success": "#52c41a",
    }
    LEVEL_EMOJI = {
        "info": ":information_source:",
        "warning": ":warning:",
        "error": ":rotating_light:",
        "success": ":white_check_mark:",
    }

    def send(self, message: ChatopsMessage, webhook_url: str) -> bool:
        payload = self._build_payload(message)
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    def validate_webhook_url(self, url: str) -> bool:
        return bool(re.match(r"^https://hooks\.slack\.com/services/T[\w/]+$", url))

    def _build_payload(self, msg: ChatopsMessage) -> dict:
        emoji = self.LEVEL_EMOJI.get(msg.level, ":bell:")
        color = self.LEVEL_COLORS.get(msg.level, "#888888")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} {msg.title}", "emoji": True},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": msg.content},
            },
        ]
        if msg.extra_fields:
            field_text = "\n".join(f"*{f.get('label', '')}*: {f.get('value', '-')}" for f in msg.extra_fields)
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": field_text},
            })
        if msg.link_url:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": msg.link_text or "点击查看详情"},
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "查看", "emoji": True},
                    "url": msg.link_url,
                },
            })

        return {
            "attachments": [{
                "color": color,
                "blocks": blocks,
            }],
        }
