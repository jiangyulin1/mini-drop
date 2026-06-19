# Mini-Drop x NapCat QQ 机器人

[NapCat](https://github.com/NapNeko/NapCatQQ) 是基于 PC QQ 的 OneBot v11 实现，
让个人 QQ 号变成机器人，Mini-Drop 通过它把性能告警推送到 QQ 群。

**无需企业认证，个人 QQ 即可。**

## 架构

```
Mini-Drop Server           NapCat (OneBot v11)         QQ 群
     │                          │                      │
     │ POST /send_group_msg     │                      │
     ├─────────────────────────►│                      │
     │  chatops/providers/      │  注入 QQ 进程发送     │
     │  qqbot.py                ├─────────────────────►│
     │                          │                      │
```

## 第一步：安装 NapCat

```powershell
# 项目目录下 PowerShell 执行（已做过可跳过）
powershell -ExecutionPolicy Bypass -File deploy\napcat\setup.ps1
```

或手动：
1. 访问 <https://github.com/NapNeko/NapCatQQ/releases>
2. 下载 `NapCat.Shell.Windows.OneKey.zip`
3. 解压到 `deploy/napcat/`
4. 双击 `NapCatInstaller.exe` 完成安装

## 第二步：启动并登录 QQ

```cmd
deploy\napcat\start.cmd
```

1. 如弹出 QQ 登录窗口 → 扫码登录
2. 看到 `[NapCat] WebSocket 已连接` 即为成功
3. 验证：浏览器打开 <http://localhost:5700>

> **关于「装了两个 QQ」**：NapCat 会额外下载一个 QQ（在 `NapCat.*.Shell/` 目录），这是正常的。NapCat 需要特定版本的 QQ 来注入，不会影响你日常使用的 QQ。

## 第三步：获取群号

1. PC 端 QQ → 右键目标群 → 查看群资料
2. 复制**群号**（纯数字）

## 第四步：配置 Mini-Drop

在项目 `.env` 中添加：

```bash
MINI_DROP_CHATOPS_ENABLED=1
MINI_DROP_CHATOPS_PROVIDER=qqbot
MINI_DROP_CHATOPS_WEBHOOK_URL=http://localhost:5700
MINI_DROP_QQBOT_TARGET_TYPE=group
MINI_DROP_QQBOT_TARGET_ID=你的群号
```

## 第五步：测试

```bash
# 启动 Mini-Drop
micro-drop serve

# 另开终端，发送测试消息
micro-drop chatops-test
```

群聊应收到：

```
✅ 【Mini-Drop ChatOps 连接测试】
这是一条来自 Mini-Drop 性能诊断平台的测试消息。
  .......
───
  平台：qqbot
  时间：2026-06-19T20:00:00
```

## 自动推送事件

| 事件 | 触发 | 图标 |
|------|------|------|
| 任务开始 | RUNNING | ℹ️ |
| 任务完成 | DONE | ✅ |
| 任务失败 | FAILED | 🚨 |
| Agent 离线 | 心跳超时 | ⚠️ |
| AI 诊断完成 | 分析结束 | ℹ️ |

## 自定义通知

```bash
micro-drop chatops-notify \
  --title "性能告警" \
  --content "mysqld CPU 飙至 95%，请排查" \
  --level error
```

## 排查

| 问题 | 解决 |
|------|------|
| start.cmd 闪退 | 右键管理员运行 |
| localhost:5700 无响应 | 等 10-20 秒初始化，检查防火墙 |
| chatops-test 失败 | `micro-drop chatops-config` 查配置 |
| 群消息收不到 | 确认机器人有发言权限；确认群号正确 |
| QQ 被风控 | 极低概率，换号或等 24h 恢复 |
