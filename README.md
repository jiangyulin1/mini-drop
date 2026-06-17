# Mini-Drop

面向 Linux 主机的轻量级性能诊断平台，支持 CPU 火焰图、eBPF IO 延迟观测、
Python 用户态采样、持续 Profiling、AI 智能归因和自然语言采集。

## 快速开始

```bash
git clone https://github.com/jiangyulin1/mini-drop.git
cd mini-drop
docker compose up -d
# 浏览器打开 http://localhost
```

演示：
```bash
make demo
```

## 环境要求

- Ubuntu 22.04 / Docker Compose v2
- Agent 容器需要 privileged + pid:host（perf / bpftrace 权限）
- 可选：DEEPSEEK_API_KEY（启用 AI 归因和自然语言采集）

## 架构

```
Web (React + Ant Design + d3-flame-graph + ECharts)
  → REST /api → Server (FastAPI :8191)
                   → gRPC (:50051) → Agent
                       → perf / eBPF / py-spy / continuous
                   → Analyzer CLI (火焰图 JSON 树 + TopN)
                   → DeepSeek (智能归因 + 自然语言采集)
  ← PostgreSQL ↔ MinIO
```

## 功能

- 4 种采集器：perf CPU / eBPF IO / py-spy / Continuous Profiling
- d3-flame-graph 交互式火焰图 + ECharts TopN 柱状图
- 6 状态任务生命周期，每次迁移带 reason
- Agent 5 秒心跳，30 秒离线检测 + 审计日志
- DataFrame 持久化（SQLite 默认 / PostgreSQL 生产）
- MinIO 对象存储 + 预签名 URL
- 智能归因 5 层引擎（证据 → 候选 → 校准 → LLM → 修复）
- 自然语言采集（描述问题 → 自动选采集器 → 确认 → 总结）

## 开发

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make test   # pytest
make server # localhost:8191
```

## 仓库结构

```
server/    FastAPI + gRPC + RCA + NLP
agent/     采集器（perf/eBPF/py-spy/continuous）
analyzer/  CLI 火焰图生成引擎
web/       React SPA 前端
proto/     5 个 gRPC 契约文件
demo/      演示负载
deploy/    Docker + nginx 部署配置
tests/     190 个测试（含 4 E2E）
docs/      设计文档 + 归因评测报告
```

## 设计原则

- gRPC 契约优先（参考 DeepFlow message/ 模式）
- 采集器通过统一接口接入，Server 不绑定具体工具
- LLM 只能调用预定义工具，不做自由决策
- 归因结论可追溯（每条 claim 有 evidence_refs）
- 本地开发不提交密钥和临时产物
