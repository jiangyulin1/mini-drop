"""钉钉自定义机器人 Webhook 提供者。"""

from __future__ import annotations

import re

from server.app.chatops.base import BaseProvider, ChatopsMessage


class DingTalkProvider(BaseProvider):
    """钉钉群机器人 Markdown 消息推送。"""

    LEVEL_TITLES = {
        "info": "📊 通知",
        "warning": "⚠️ 告警",
        "error": "🚨 异常",
        "success": "✅ 完成",
    }

    def send(self, message: ChatopsMessage, webhook_url: str) -> bool:
        payload = self._build_payload(message)
        try:
            import requests
            resp = requests.post(webhook_url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    def validate_webhook_url(self, url: str) -> bool:
        return bool(re.match(r"^https://oapi\.dingtalk\.com/robot/send\?access_token=[\w-]+$", url))

    def _build_payload(self, msg: ChatopsMessage) -> dict:
        level = self.LEVEL_TITLES.get(msg.level, "📋 消息")
        content_lines = [
            f"### {level}：{msg.title}",
            "",
            msg.content,
        ]
        if msg.extra_fields:
            content_lines.append("")
            for f in msg.extra_fields:
                content_lines.append(f"- {f.get('label', '')}：**{f.get('value', '-')}**")
        if msg.link_url:
            content_lines.append("")
            content_lines.append(f"[{msg.link_text or '查看详情'}]({msg.link_url})")

        return {
            "msgtype": "markdown",
            "markdown": {
                "title": msg.title,
                "text": self._truncate("\n".join(content_lines), 4096),
            },
        }
