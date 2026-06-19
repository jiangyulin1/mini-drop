"""ChatOps 模块 —— 企业 IM 通知与交互。

支持平台：企业微信 / 飞书 / 钉钉 / Slack

用法：
  from server.app.chatops import dispatch_event
  dispatch_event(event_type, data)

或直接通过环境变量启动时自动订阅事件总线：
  MINI_DROP_CHATOPS_ENABLED=1
  MINI_DROP_CHATOPS_PROVIDER=wecom
  MINI_DROP_CHATOPS_WEBHOOK_URL=https://qyapi.weixin.qq.com/...
"""

from server.app.chatops.dispatcher import dispatch_event, init_chatops
