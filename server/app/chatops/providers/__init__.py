"""ChatOps IM 平台提供者集合。"""

from server.app.chatops.providers.wecom import WeComProvider
from server.app.chatops.providers.feishu import FeishuProvider
from server.app.chatops.providers.dingtalk import DingTalkProvider
from server.app.chatops.providers.slack import SlackProvider
from server.app.chatops.providers.qqbot import QQBotProvider

PROVIDERS = {
    "wecom": WeComProvider(),
    "feishu": FeishuProvider(),
    "dingtalk": DingTalkProvider(),
    "slack": SlackProvider(),
    "qqbot": QQBotProvider(),
}
