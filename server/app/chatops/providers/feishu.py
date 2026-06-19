"""飞书自定义机器人 Webhook 提供者。"""

from __future__ import annotations

import re

import requests

from server.app.chatops.base import BaseProvider, ChatopsMessage


class FeishuProvider(BaseProvider):
    """飞书自定义机器人消息推送（interactive 卡片）。"""

    LEVEL_TITLES = {
        "info": "📊 通知",
        "warning": "⚠️ 告警",
        "error": "🚨 异常",
        "success": "✅ 完成",
    }
    LEVEL_COLORS = {
        "info": "blue",
        "warning": "yellow",
        "error": "red",
        "success": "green",
    }

    def send(self, message: ChatopsMessage, webhook_url: str) -> bool:
        payload = self._build_payload(message)
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    def validate_webhook_url(self, url: str) -> bool:
        return bool(re.match(r"^https://open\.feishu\.cn/open-apis/bot/v2/hook/[\w-]+$", url))

    def _build_payload(self, msg: ChatopsMessage) -> dict:
        level_title = self.LEVEL_TITLES.get(msg.level, "📋 消息")
        color = self.LEVEL_COLORS.get(msg.level, "blue")
        title_text = f"{level_title}：{msg.title}"

        elements = [
            {"tag": "div", "text": {"tag": "lark_md", "content": msg.content}},
        ]
        if msg.extra_fields:
            field_lines = []
            for f in msg.extra_fields:
                field_lines.append(f"**{f.get('label', '')}**：{f.get('value', '-')}")
            elements.append({"tag": "hr"})
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(field_lines)}})
        if msg.link_url:
            elements.append({"tag": "hr"})
            elements.append({
                "tag": "action",
                "actions": [{
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": msg.link_text or "查看详情"},
                    "type": "default",
                    "url": msg.link_url,
                }],
            })

        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title_text},
                    "template": color,
                },
                "elements": elements,
            },
        }
