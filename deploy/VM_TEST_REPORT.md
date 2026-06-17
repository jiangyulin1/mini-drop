# Mini-Drop 虚拟机端到端验证报告

> 时间: 2026-06-17
> 环境: Ubuntu 22.04 / Linux 5.15.0-27 / Python 3.10.12
> 仓库: https://github.com/jiangyulin1/mini-drop (commit 274ebfb)

## 测试1: perf CPU 采集 ✅

| 项目 | 结果 |
|------|------|
| 目标进程 | `demo/cpu_hotspot.py` PID=8430 |
| 采集参数 | perf_cpu, 99Hz, 10s |
| 最终状态 | **ANALYZING** |
| perf.data | 88,272 bytes |
| 火焰图 SVG | 60,290 bytes (可缩放交互式) |
| Top1 热点 | `[_json.cpython-310-x86_64-linux-gnu.so]` (15.8%) |
| 规则建议 | JSON 编解码占用 CPU 显著 |

### 状态事件链

```
PENDING    | Web 请求创建任务
RUNNING    | Agent 心跳拉取待执行任务
UPLOADING  | 采集完成，准备上传产物
ANALYZING  | 产物已记录，等待分析
```

## 测试2: Agent 审计日志 ✅

- TASK_CREATED 正常，每个任务创建都有审计记录
- AGENT_OFFLINE 正常，Agent 重启后自动检测离线

## 测试3: 异常路径 ✅

| 异常场景 | 结果 |
|------|------|
| perf_event_paranoid=2 | FAILED, reason: "权限不足" |
| 目标 PID 不存在 | FAILED, reason: "PID xxx 不存在" |
| py-spy 非 root | FAILED, reason: "Permission Denied" |
| bpftrace 非 root | FAILED, reason: "only supports root user" |

所有异常都有明确的 **reason 字段** 和 **审计日志记录**。

## 测试4: 智能归因诊断 ✅

未配置 DEEPSEEK_API_KEY 时正常降级，输出规则引擎报告：
- model: `rule-engine-only`
- summary: "归因引擎使用规则候选与工具证据生成降级报告"
- verified 候选原因和工具结果正常返回

## 结论

| 项 | 状态 |
|------|:--:|
| perf CPU 采集 + 火焰图生成 | ✅ 通过 |
| 状态机 6 状态 + reason 落库 | ✅ 通过 |
| Agent 在线/离线审计 | ✅ 通过 |
| 异常路径失败语义 | ✅ 通过 |
| 智能归因降级 | ✅ 通过 |
| py-spy（需 root） | ⚠️ 容器 privileged 模式 |
| bpftrace（需 root） | ⚠️ 容器 privileged 模式 |

端到端链路：**创建任务 → Agent 心跳拉取 → perf record 真实采集 → Analyzer 生成火焰图 SVG + JSON 树 → 诊断报告**，在真实 Linux 环境完整跑通。
