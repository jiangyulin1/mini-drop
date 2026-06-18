# Mini-Drop 设计文档

## 1. 项目概述

Mini-Drop 是一个面向 Linux 主机的轻量级性能诊断平台。用户通过 Web UI 创建采集任务，
Server 负责任务编排和状态管理，Agent 在目标主机执行 perf/eBPF/py-spy/continuous 采集，
Analyzer 将原始数据转为 d3-flame-graph 交互式火焰图和热点分析，智能归因引擎提供
可追溯的诊断报告。

项目在 7 天内从空仓库逐步构建到完整可演示平台，多批次 commit 记录真实开发过程。

## 2. 总体架构

```
Web (React + Ant Design + d3-flame-graph)
  → REST /api/* → Server (FastAPI :8191)
                    → gRPC (:50051) → Agent (心跳 + 采集器调度)
                                         → perf / eBPF / py-spy / continuous
                    → Agent 本地 Analyzer CLI (perf script → flamegraph JSON 树)
                    → DeepSeek API (智能归因 + 自然语言采集)
  ← PostgreSQL (任务 / 状态事件 / 审计 / 诊断)
  ← MinIO (采集产物 / 火焰图 / 分析结果)
```

## 3. 核心架构决策

### 3.1 gRPC + Protobuf 作为 Agent 通信协议

Server ↔ Agent 使用 gRPC，参考 DeepFlow 的 `message/` 契约优先模式。
5 个 `.proto` 文件定义了全部通信接口，编译后 Server 和 Agent 各持一份 stub。

选择原因：
- 强类型契约，编译期发现字段不匹配
- 内置超时和取消传播
- 二进制序列化，PidStats 等数值数组比 JSON 小 3-5 倍
- 与腾讯原版 Drop 系统架构一致

Web ↔ Server 保留 REST/JSON：浏览器原生支持，易于调试和 curl 测试。

### 3.2 d3-flame-graph 交互式火焰图

Analyzer 将 perf.data 转换为折叠栈后，构建 `{name, value, children}` JSON 树供
d3-flame-graph 渲染。提供点击放大、搜索高亮、hover 详情等交互能力。
同时产出 SVG 作为降级备用。

JSON 树深度超过 50 层时截断，防止浏览器卡死。

### 3.3 SQLAlchemy + SQLite/PostgreSQL 双后端

开发/测试环境默认 SQLite（零配置），生产环境通过 `DATABASE_URL` 切换 PostgreSQL。
所有数据在 `expire_on_commit=False` 模式下 session 关闭后仍可读。

### 3.4 工具驱动的智能归因

LLM 不能随意生成结论。5 层流水线：
1. 证据层 — 从 DB/MinIO 收集结构化数据
2. 候选归因 — rules.json 定义的规则引擎自动匹配
3. 置信度校准 — 五维加权公式
4. LLM 推理 — DeepSeek 在 few-shot 约束下生成报告
5. 修复计划 — 三级风险分层（safe_auto / confirm_required / manual_only）

feedback_prior 因子允许历史用户标注修正后续归因。

### 3.5 自然语言采集

用户输入自然语言描述 → DeepSeek function calling 解析为结构化参数 →
/proc 进程名→PID 解析 → 用户确认 → 创建任务 → 结果 AI 总结。

LLM 只能调用 `create_profiling_task` 函数，不得自由输出决策。
进程解析不做在 LLM 中（LLM 不知道系统上运行什么进程）。

## 4. 任务状态机

```
PENDING → RUNNING → UPLOADING → ANALYZING → DONE
   │         │          │            │
   └─────────┴──────────┴────────────┘→ FAILED
```

比题目要求的 5 状态多一个 ANALYZING，采集完成和分析完成是两个独立阶段。

每次状态迁移写入 `task_status_events` 表，包含 from/to/reason/actor/metadata/timestamp。

## 5. 数据库设计

P0 表（5 张）：agents / tasks / task_status_events / audit_logs / artifacts

P1 增强：analysis_results / agent_metric_snapshots / diagnosis_reports / diagnosis_feedback /
         rca_feedback_weights / diagnosis_runs / tool_results / repair_plans

P2 亮点：continuous_windows / baselines

## 6. 智能归因评测方法

见 `docs/rca_eval_report.md`。

## 7. AI 协作章节

本项目全部代码由人工规划和审核，AI（DeepSeek-V4-Pro + Claude Code）辅助实现。
AI 的角色是：按人工规划生成代码骨架，由人工逐行审核、修改命名和错误处理、
运行测试后合并。

人工决策的关键点：
- 架构取舍（gRPC vs HTTP / d3 vs SVG / SQLite vs PG）
- 安全边界（LLM tool_choice 强制、参数 clamp、进程解析不做在 LLM 里）
- 测试策略（状态机 100% 覆盖、gRPC 集成测试动态端口、E2E 覆盖异常路径）
- commit message 全部中文手写，每个 commit 独立可 review

"如果再有 7 天我会做什么"：
- HTTP 控制面升级为 gRPC streaming（任务状态推送替代轮询）
- Analyzer 升级为队列化 worker，支持并行分析
- 增加完整权限模型和用户组管理
- eBPF 采集器扩展调度延迟、网络和文件系统探针
- 建立智能归因评测集，量化结论准确性和建议可操作性

## 8. 性能自证

Agent 采集期间自身开销：
- CPU < 5%（单核）
- RSS < 100MB
- IO 读 < 50 KB/s

数据来源：Agent 心跳中上报的 PidStats（读取 /proc/self/stat + /proc/self/io）。

## 9. 安全加固补充

### 9.1 HTTP API Key 认证

默认开发模式保持无认证，便于本地 demo 和自动化测试。生产或公网演示时可通过环境变量开启最小认证：

```bash
MINI_DROP_API_AUTH_ENABLED=1
MINI_DROP_API_KEY=<strong-random-token>
```

开启后，除 `/api/healthz` 外的 `/api/*` 接口必须携带以下任一凭据：

- `Authorization: Bearer <token>`
- `X-API-Key: <token>`

认证使用常量时间比较，避免普通字符串比较带来的时序侧信道。该方案属于单租户最小安全边界，不替代完整用户、组、权限模型。

### 9.2 产物访问边界

Agent 上报的 `local_path` 不再被 Server 无条件读取。HTTP 产物内容接口会先把路径解析到受控根目录：

```bash
MINI_DROP_ARTIFACT_ROOT=/tmp/mini-drop
```

规则：

- 相对路径会被解释为 `MINI_DROP_ARTIFACT_ROOT` 下的路径。
- 绝对路径必须仍位于 `MINI_DROP_ARTIFACT_ROOT` 内。
- `resolve()` 后逃逸根目录的路径会被拒绝，包含符号链接逃逸场景。
- 预签名 URL 只允许配置 bucket，且 object key 必须位于 `tasks/` 目录下。

### 9.3 剩余安全工作

- gRPC 仍为 insecure channel，后续应增加可选 TLS / mTLS。
- API Key 是全局共享密钥，后续应升级为用户级 token 或接入真实鉴权系统。
- 产物元数据仍由 Agent 上报，后续应增加 artifact schema 校验和上传侧签名校验。
- 多租户、任务权限、审计查询权限尚未实现，当前版本定位为单租户 Mini-Drop MVP。
