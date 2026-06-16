"""
Mini-Drop HTTP API 入口。

启动 FastAPI 服务（端口 8191），同时在后台线程运行 gRPC server（端口 50051）。
两者共享同一个 InMemoryRepository 实例——Agent 通过 gRPC 上报的数据，
Web 通过 HTTP API 即时可见。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from server.app.grpc_server import serve_in_background
from server.app.repository import InMemoryRepository
from server.app.schemas import (
    APIResponse,
    CreateTaskRequest,
    TaskView,
)

repo = InMemoryRepository()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """应用生命周期：启动时拉起 gRPC，关闭时停止。"""
    _grpc = serve_in_background(repo)
    yield
    _grpc.stop(grace=None).wait(timeout=5)


app = FastAPI(title="Mini-Drop Server", version="0.1.0", lifespan=_lifespan)


def _task_view(record) -> TaskView:
    """将 TaskRecord 转为前端模型。"""
    return TaskView(
        id=record.id,
        name=record.name,
        agent_id=record.agent_id,
        target_pid=record.target_pid,
        collector_type=record.collector_type,
        sample_rate=record.sample_rate,
        duration_sec=record.duration_sec,
        status=record.status.value,
        status_reason=record.status_reason,
        request_params=record.request_params,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )


# ── 通用 ──────────────────────────────────────────────────────


@app.get("/api/healthz")
def healthz() -> APIResponse:
    return APIResponse(data={"service": "mini-drop-server", "version": "0.1.0"})


@app.get("/api/me")
def current_user() -> APIResponse:
    return APIResponse(data={
        "user_id": "demo_user",
        "name": "Mini-Drop Demo User",
        "role": "admin",
    })


# ── Agent（查询面） ────────────────────────────────────────────


@app.get("/api/agents")
def list_agents() -> APIResponse:
    """返回所有 Agent 列表。调用前自动检查离线。"""
    repo.mark_offline_agents()
    items = [repo.as_dict(agent) for agent in repo.agents.values()]
    return APIResponse(data=items)


@app.get("/api/audit-logs")
def list_audit_logs() -> APIResponse:
    items = [repo.as_dict(log) for log in repo.audit_logs]
    return APIResponse(data=items)


# ── 任务 ──────────────────────────────────────────────────────


@app.post("/api/tasks")
def create_task(payload: CreateTaskRequest) -> APIResponse:
    if payload.duration_sec <= 0:
        raise HTTPException(status_code=400, detail="duration_sec 必须为正整数")
    if payload.sample_rate <= 0:
        raise HTTPException(status_code=400, detail="sample_rate 必须为正整数")
    task = repo.create_task(payload)
    return APIResponse(data={"task_id": task.id, "status": task.status.value})


@app.get("/api/tasks")
def list_tasks() -> APIResponse:
    items = [_task_view(t).model_dump() for t in repo.tasks.values()]
    return APIResponse(data={"items": items, "total": len(items)})


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str) -> APIResponse:
    task = repo.tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return APIResponse(data=_task_view(task).model_dump())


@app.get("/api/tasks/{task_id}/events")
def get_task_events(task_id: str) -> APIResponse:
    if task_id not in repo.tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    items = [repo.as_dict(e) for e in repo.events if e.task_id == task_id]
    return APIResponse(data=items)


@app.get("/api/tasks/{task_id}/artifacts")
def get_task_artifacts(task_id: str) -> APIResponse:
    if task_id not in repo.tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    return APIResponse(data=repo.artifacts.get(task_id, []))


@app.post("/api/tasks/{task_id}/diagnose")
def diagnose_task(task_id: str) -> APIResponse:
    if task_id not in repo.tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    return APIResponse(data={
        "report_id": f"diag_{task_id}",
        "status": "QUEUED",
        "task_id": task_id,
    })


# ── 启动入口 ──────────────────────────────────────────────────


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8191)
