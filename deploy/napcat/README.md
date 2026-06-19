# Mini-Drop × NapCat QQ 机器人部署指南

## 概述

[NapCat](https://github.com/NapNeko/NapCatQQ) 是基于 PC QQ 的 OneBot v11 协议实现，
可以让你的 QQ 号变成一个机器人，接收 Mini-Drop 的性能告警和诊断通知。

**相比企业微信/飞书/钉钉机器人的优势：**
- 无需企业认证，个人 QQ 号即可使用
- 免费，无消息条数限制
- OneBot v11 标准协议，生态成熟

## 第一步：安装 NapCat

### 方式一：运行一键安装脚本（推荐）

```powershell
# 在项目根目录下的 PowerShell 中执行
powershell -ExecutionPolicy Bypass -File deploy\napcat\setup.ps1
```

脚本会自动下载 v4.18.6 版本并配置启动文件。

### 方式二：手动安装

1. 访问 <https://github.com/NapNeko/NapCatQQ/releases>
2. 下载 `NapCat.Shell.Windows.OneKey.zip`
3. 解压到 `deploy/napcat/` 目录

## 第二步：登录 QQ

```cmd
# 双击运行
deploy\napcat\start-qq.cmd
```

1. 在弹窗中选择 QQ 的安装路径
2. **重要**：使用小号扫码登录（不要用常用号，有极小概率被风控）
3. 等待 NapCat 启动完成 —— 看到 `[NapCat] 初始化完成` 即为成功
4. 验证 HTTP API：浏览器打开 <http://localhost:5700>，应能看到 NapCat 回显

> 不建议用你日常使用的大号——虽然 NapCat 风险很低，但任何第三方 QQ 客户端理论上都有风控可能。准备一个小号即可。

### 快速重新登录（已安装过的后续使用）

```cmd
deploy\napcat\start-qq-quick.cmd
```

跳过框架更新检查，直接注入 QQ 进程。

## 第三步：把机器人拉入群聊

1. 在 QQ 里创建或选择一个群
2. 将你登录的机器人 QQ 号拉入群
3. 给机器人**发言权限**

> 获取群号：PC 端右键群 → 查看群资料 → 复制群号（一串纯数字）

## 第四步：配置 Mini-Drop

在 `.env` 文件中添加：

```bash
# ── QQ 机器人 ──────────────────────────
MINI_DROP_CHATOPS_ENABLED=1
MINI_DROP_CHATOPS_PROVIDER=qqbot
MINI_DROP_CHATOPS_WEBHOOK_URL=http://localhost:5700

# 目标群（群消息模式）
MINI_DROP_QQBOT_TARGET_TYPE=group
MINI_DROP_QQBOT_TARGET_ID=123456789     # 替换为你的实际群号

# 如果机器人和 Mini-Drop 不在同一台机器上：
# MINI_DROP_CHATOPS_WEBHOOK_URL=http://192.168.1.100:5700
```

> 如果想让机器人给你发私聊而非群消息：
> ```bash
> MINI_DROP_QQBOT_TARGET_TYPE=private
> MINI_DROP_QQBOT_TARGET_ID=你的QQ号
> ```

## 第五步：启动并测试

```bash
# 1. 启动 Mini-Drop
micro-drop serve

# 2. 另开终端，测试 QQ 机器人连接
micro-drop chatops-test
```

群聊中应收到：

```
✅ 【Mini-Drop ChatOps 连接测试】

这是一条来自 Mini-Drop 性能诊断平台的测试消息。

───
  平台：qqbot
  时间：2026-06-19T20:00:00
```

## 自动推送事件

配置完成后，以下事件会自动推送到 QQ 群：

| 事件 | 触发条件 | 图标 |
|------|---------|------|
| 采集任务开始 | 任务进入 RUNNING 状态 | ℹ️ |
| 采集任务完成 | 任务变为 DONE | ✅ |
| 采集任务失败 | 任务变为 FAILED（附原因） | 🚨 |
| Agent 离线 | Agent 心跳超时 30 秒 | ⚠️ |
| AI 诊断完成 | 归因分析完成 | ℹ️ |

## 手动发送通知

```bash
# 用于脚本/CI 中发送自定义消息到 QQ 群
micro-drop chatops-notify \
  --title "性能告警" \
  --content "mysqld CPU 飙至 95%，请检查" \
  --level error
```

## 故障排查

### 1. start-qq.cmd 启动后无反应

- 确认已安装 PC QQ（版本 ≥ 9.9.0）
- 尝试以管理员身份运行 `start-qq.cmd`
- 如果弹窗闪退，在 cmd 中手动运行查看报错

### 2. 浏览器访问 localhost:5700 无响应

- NapCat 启动约需 10-20 秒完成初始化
- 检查 QQ 是否成功登录（托盘图标是否正常）
- 检查 Windows 防火墙是否拦截了端口 5700

### 3. chatops-test 发送失败

```bash
# 检查 ChatOps 配置
micro-drop chatops-config

# 输出应为 {"enabled": true, "provider": "qqbot", ...}

# 手动测试 OneBot API 是否可达
curl http://localhost:5700/send_group_msg -H "Content-Type: application/json" -d "{\"group_id\":你的群号,\"message\":\"手动测试\"}"
```

### 4. 群消息收不到

- 确认机器人在群中且有发言权限
- 确认 `MINI_DROP_QQBOT_TARGET_ID` 群号正确（纯数字，不带引号）
- 查看 Mini-Drop 日志中是否有 `chatops_send_failed` 错误

### 5. QQ 被风控

- 概率极低，但若遇到：换一个 QQ 号或等待 24 小时自动恢复
- 不要短时间发送大量重复消息
- 不要用 NapCat 做群发广告（那是真正的风控触发场景）

## 多平台同时通知

你可以同时启用多个 ChatOps 渠道：

```bash
# QQ 群推送（通过 NapCat）
MINI_DROP_CHATOPS_PROVIDER=qqbot
MINI_DROP_CHATOPS_ENABLED=1
# ...

# 同时推送到 Slack（通过 webhook）
# 只需修改 CHATOPS_PROVIDER 和 CHATOPS_WEBHOOK_URL 即可切换
# 注意：当前版本只支持单渠道，多渠道支持在规划中
```

## 资源链接

- NapCat 官方仓库: <https://github.com/NapNeko/NapCatQQ>
- OneBot v11 协议文档: <https://github.com/botuniverse/onebot-11>
- Mini-Drop ChatOps 模块源码: `server/app/chatops/`
