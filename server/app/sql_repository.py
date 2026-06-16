"""SQLAlchemy 持久化 Repository。

接口与 InMemoryRepository 保持一致，替换时 gRPC 服务和 HTTP handler
无需修改调用代码。通过 DATABASE_URL 切换 PostgreSQL / SQLite 后端。
"""

from __future__ import annotations

import json
import threading
from collections import deque
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session as OrmSession

from server.app.database import new_session
from server.app.models import (
    AgentModel,
    ArtifactModel,
    AuditLogModel,
    StatusEventModel,
    TaskModel,
)
from server.app.schemas import CreateTaskRequest
from server.app.state_machine import (
    Actor,
    StatusEvent,
    TaskStatus,
    build_status_event,
    now_utc,
)


class SqlRepository:
    """SQLAlchemy 持久化 Repository。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # 任务队列仍用内存，因为 IP→队列的映射无需持久化
        self._task_queues: dict[str, deque[str]] = {}

    # ------------------------------------------------------------------
    # Agent
    # ------------------------------------------------------------------

    def register_agent(
        self, agent_id: str, hostname: str, ip_addr: str,
        version: str = "0.1.0", os_info: str = "unknown",
        capabilities: list[str] | None = None,
    ) -> AgentModel:
        caps = list(capabilities or [])
        ts = now_utc()

        with self._lock:
            session = new_session()
            try:
                existing = session.get(AgentModel, agent_id)
                if existing is not None and existing.status == "OFFLINE":
                    self._write_audit(
                        session, "AGENT_ONLINE", agent_id,
                        f"{agent_id} 恢复在线",
                    )

                if existing is not None:
                    existing.hostname = hostname
                    existing.ip_addr = ip_addr
                    existing.version = version
                    existing.os_info = os_info
                    existing.capabilities = caps
                    existing.status = "ONLINE"
                    existing.last_heartbeat_at = ts
                    existing.updated_at = ts
                    agent = existing
                else:
                    agent = AgentModel(
                        id=agent_id, hostname=hostname, ip_addr=ip_addr,
                        version=version, os_info=os_info, capabilities=caps,
                        status="ONLINE", last_heartbeat_at=ts,
                        created_at=ts, updated_at=ts,
                    )
                    session.add(agent)

                if ip_addr not in self._task_queues:
                    self._task_queues[ip_addr] = deque()

                session.commit()
                return agent
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

    def heartbeat(self, agent_id: str, ip_addr: str) -> TaskModel | None:
        with self._lock:
            session = new_session()
            try:
                agent = session.get(AgentModel, agent_id)
                if agent is None:
                    return None

                agent.status = "ONLINE"
                agent.last_heartbeat_at = now_utc()
                agent.updated_at = now_utc()

                # 从 IP 队列取下一个 PENDING 任务
                queue = self._task_queues.get(ip_addr)
                if not queue:
                    session.commit()
                    return None

                while queue:
                    task_id = queue[0]
                    task = session.get(TaskModel, task_id)
                    if task is not None and task.status == TaskStatus.PENDING.value:
                        queue.popleft()
                        self._transition_task_in_session(
                            session, task_id, TaskStatus.RUNNING,
                            "Agent 心跳拉取待执行任务", Actor.SERVER,
                        )
                        session.commit()
                        result = task
                        result.status = TaskStatus.RUNNING.value
                        return result
                    queue.popleft()

                session.commit()
                return None
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

    def mark_offline_agents(self, timeout_sec: int = 30) -> list[AgentModel]:
        with self._lock:
            session = new_session()
            try:
                cutoff = now_utc() - timedelta(seconds=timeout_sec)
                changed = (
                    session.query(AgentModel)
                    .filter(
                        AgentModel.status == "ONLINE",
                        AgentModel.last_heartbeat_at < cutoff,
                    )
                    .all()
                )
                for agent in changed:
                    agent.status = "OFFLINE"
                    agent.updated_at = now_utc()
                    self._write_audit(
                        session, "AGENT_OFFLINE", agent.id,
                        f"{agent.id} 心跳超时 {timeout_sec}s，标记为离线",
                    )
                session.commit()
                return changed
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

    @property
    def agents(self) -> dict[str, AgentModel]:
        """返回 {agent_id: AgentModel} 字典（兼容旧接口的 dict 访问）。"""
        session = new_session()
        try:
            return {a.id: a for a in session.query(AgentModel).all()}
        finally:
            session.close()

    def find_agent_by_ip(self, ip_addr: str) -> AgentModel | None:
        session = new_session()
        try:
            return session.query(AgentModel).filter(AgentModel.ip_addr == ip_addr).first()
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Task
    # ------------------------------------------------------------------

    def create_task(self, payload: CreateTaskRequest) -> TaskModel:
        with self._lock:
            session = new_session()
            try:
                ts = now_utc()
                hex_suffix = uuid4().hex[:6]
                task_id = f"task_{ts.strftime('%Y%m%d_%H%M%S')}_{hex_suffix}"
                agent = session.get(AgentModel, payload.agent_id)
                if agent is None:
                    raise ValueError(f"Agent {payload.agent_id} 不存在")

                task = TaskModel(
                    id=task_id,
                    name=payload.name,
                    agent_id=payload.agent_id,
                    target_pid=payload.target_pid,
                    collector_type=payload.collector_type,
                    sample_rate=payload.sample_rate,
                    duration_sec=payload.duration_sec,
                    status=TaskStatus.PENDING.value,
                    status_reason="Web 请求创建任务",
                    request_params=payload.model_dump(),
                    created_at=ts,
                )
                session.add(task)

                # 状态事件
                self._write_event(session, task_id, None, TaskStatus.PENDING,
                                  "Web 请求创建任务", Actor.WEB, payload.model_dump())

                # 审计日志
                self._write_audit(session, "TASK_CREATED", task_id=task_id,
                                  message=f"任务 {task_id} 已创建",
                                  metadata=payload.model_dump())

                # IP 队列
                ip = agent.ip_addr
                if ip not in self._task_queues:
                    self._task_queues[ip] = deque()
                self._task_queues[ip].append(task_id)

                session.commit()
                return task
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

    def transition_task(
        self, task_id: str, to_status: TaskStatus,
        reason: str, actor: Actor,
        metadata: dict[str, Any] | None = None,
    ) -> TaskModel:
        with self._lock:
            session = new_session()
            try:
                task = session.get(TaskModel, task_id)
                if task is None:
                    raise ValueError(f"任务 {task_id} 不存在")

                _ = build_status_event(
                    task_id, TaskStatus(task.status), to_status,
                    reason, actor, metadata or {},
                )

                self._transition_task_in_session(
                    session, task_id, to_status, reason, actor, metadata,
                )
                session.commit()
                task.status = to_status.value
                return task
            except ValueError:
                session.rollback()
                raise
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

    @property
    def tasks(self) -> dict[str, TaskModel]:
        session = new_session()
        try:
            return {t.id: t for t in session.query(TaskModel).all()}
        finally:
            session.close()

    @property
    def events(self) -> list[StatusEvent]:
        """返回所有状态事件，兼容原有 list[StatusEvent] 接口。"""
        session = new_session()
        try:
            models = session.query(StatusEventModel).all()
            result: list[StatusEvent] = []
            for m in models:
                result.append(StatusEvent(
                    task_id=m.task_id if m.task_id else "",
                    from_status=TaskStatus(m.from_status) if m.from_status else None,
                    to_status=TaskStatus(m.to_status),
                    reason=m.reason if m.reason else "",
                    actor=Actor(m.actor) if m.actor else Actor.SERVER,
                    metadata=m.meta_json if isinstance(m.meta_json, dict) else {},
                    created_at=m.created_at if m.created_at else now_utc(),
                ))
            return result
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    def add_artifacts(self, task_id: str, artifacts: list[dict[str, Any]]) -> None:
        with self._lock:
            session = new_session()
            try:
                ts = now_utc()
                for art in artifacts:
                    session.add(ArtifactModel(
                        task_id=task_id,
                        artifact_type=art.get("artifact_type", "raw"),
                        bucket=art.get("bucket", "mini-drop"),
                        object_key=art.get("object_key", ""),
                        filename=art.get("filename"),
                        local_path=art.get("local_path"),
                        content_type=art.get("content_type", "application/octet-stream"),
                        size_bytes=art.get("size_bytes", 0),
                        meta_json=art.get("metadata", {}),
                        created_at=ts,
                    ))
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

    @property
    def artifacts(self) -> dict[str, list[dict[str, Any]]]:
        session = new_session()
        try:
            result: dict[str, list[dict[str, Any]]] = {}
            for art in session.query(ArtifactModel).all():
                tid = art.task_id if art.task_id else ""
                result.setdefault(tid, []).append(art.to_dict())
            return result
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def _write_audit(
        self, session: OrmSession, event_type: str, agent_id: str | None = None,
        task_id: str | None = None, message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        session.add(AuditLogModel(
            event_type=event_type,
            message=message,
            agent_id=agent_id,
            task_id=task_id,
            meta_json=metadata or {},
            created_at=now_utc(),
        ))

    @property
    def audit_logs(self) -> list[AuditLogModel]:
        session = new_session()
        try:
            return session.query(AuditLogModel).all()
        finally:
            session.close()

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _write_event(
        self, session: OrmSession, task_id: str,
        from_status, to_status: TaskStatus,
        reason: str, actor: Actor,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        session.add(StatusEventModel(
            task_id=task_id,
            from_status=from_status.value if from_status else None,
            to_status=to_status.value,
            reason=reason,
            actor=actor.value,
            meta_json=metadata or {},
            created_at=now_utc(),
        ))

    def _transition_task_in_session(
        self, session: OrmSession, task_id: str,
        to_status: TaskStatus, reason: str, actor: Actor,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        task = session.get(TaskModel, task_id)
        # 事件：from 用旧 status value
        session.add(StatusEventModel(
            task_id=task_id,
            from_status=task.status,
            to_status=to_status.value,
            reason=reason,
            actor=actor.value,
            meta_json=metadata or {},
            created_at=now_utc(),
        ))
        task.status = to_status.value
        task.status_reason = reason
        if to_status == TaskStatus.RUNNING and task.started_at is None:
            task.started_at = now_utc()
        if to_status in (TaskStatus.DONE, TaskStatus.FAILED):
            task.finished_at = now_utc()

    def as_dict(self, value: Any) -> dict[str, Any]:
        if isinstance(value, StatusEvent):
            data = asdict(value)
            data["from_status"] = value.from_status.value if value.from_status else None
            data["to_status"] = value.to_status.value
            data["actor"] = value.actor.value
            return data
        if isinstance(value, (AgentModel, TaskModel, StatusEventModel, AuditLogModel, ArtifactModel)):
            return value.to_dict()
        return json.loads(json.dumps(value, default=str))
