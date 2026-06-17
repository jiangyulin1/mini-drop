# Mini-Drop 部署说明

## 环境要求

- Docker Engine 20.10+ / Docker Compose v2
- Linux 内核 5.4+（Agent 需要 perf 和 bpftrace）
- 8 GB 可用内存

## 快速启动

```bash
git clone https://github.com/jiangyulin1/mini-drop.git
cd mini-drop
docker compose up -d
```

启动后访问 http://localhost 打开 Web 界面。

## 一键演示

```bash
make demo
```

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| Web | 80 | React SPA 前端 |
| Server HTTP | 8191 | REST API |
| Server gRPC | 50051 | Agent 通信 |
| PostgreSQL | 5432 | 任务与审计数据 |
| MinIO API | 9000 | 对象存储 |
| MinIO Console | 9001 | 管理面板 |

## 容器权限说明

Agent 容器需要 `privileged: true` + `pid: host` + `SYS_ADMIN`，
因为 perf 和 bpftrace 需要访问宿主机内核接口。
生产环境建议以 root 用户运行 Agent 而非开启 privileged 模式。

## 环境变量

复制 `.env.example` 为 `.env` 后根据需要修改：
- `DATABASE_URL` — PostgreSQL 连接串
- `DEEPSEEK_API_KEY` — DeepSeek API 密钥（可选，不影响核心功能）
- `MINIO_*` — MinIO 凭证
