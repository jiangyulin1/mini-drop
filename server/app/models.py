"""SQLAlchemy ORM 模型定义。

与 InMemoryRepository 的数据类结构对齐，
通过 SQLAlchemy 2.0 DeclarativeBase 映射。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ── Agent ────────────────────────────────────────────────────────


class AgentModel(Base):
    __tablename__ = "agents"

    id = Column(String(128), primary_key=True)
    hostname = Column(String(256), nullable=False)
    ip_addr = Column(String(64), nullable=False)
    version = Column(String(32), default="0.1.0")
    os_info = Column(String(256), default="unknown")
    capabilities = Column(JSON, default=list)
    status = Column(String(16), default="ONLINE")
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "hostname": self.hostname,
            "ip_addr": self.ip_addr,
            "version": self.version,
            "os_info": self.os_info,
            "capabilities": self.capabilities or [],
            "status": self.status,
            "last_heartbeat_at": self.last_heartbeat_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ── Task ────────────────────────────────────────────────────────


class TaskModel(Base):
    __tablename__ = "tasks"

    id = Column(String(128), primary_key=True)
    name = Column(String(256), nullable=False)
    agent_id = Column(String(128), ForeignKey("agents.id"), nullable=False)
    target_pid = Column(Integer, nullable=False)
    collector_type = Column(String(32), nullable=False)
    sample_rate = Column(Integer, default=99)
    duration_sec = Column(Integer, default=15)
    status = Column(String(16), nullable=False)
    status_reason = Column(Text, default="")
    request_params = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    agent = relationship("AgentModel", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "agent_id": self.agent_id,
            "target_pid": self.target_pid,
            "collector_type": self.collector_type,
            "sample_rate": self.sample_rate,
            "duration_sec": self.duration_sec,
            "status": self.status,
            "status_reason": self.status_reason or "",
            "request_params": self.request_params or {},
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


# ── 状态事件 ────────────────────────────────────────────────────


class StatusEventModel(Base):
    __tablename__ = "task_status_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(128), ForeignKey("tasks.id"), nullable=False, index=True)
    from_status = Column(String(16), nullable=True)
    to_status = Column(String(16), nullable=False)
    reason = Column(Text, nullable=False)
    actor = Column(String(16), nullable=False)
    meta_json = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "reason": self.reason,
            "actor": self.actor,
            "metadata": self.meta_json or {},
            "created_at": self.created_at,
        }


# ── 审计日志 ────────────────────────────────────────────────────


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(32), nullable=False)
    message = Column(Text, nullable=False)
    agent_id = Column(String(128), nullable=True)
    task_id = Column(String(128), nullable=True)
    meta_json = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "message": self.message,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "metadata": self.meta_json or {},
            "created_at": self.created_at,
        }


# ── 产物 ───────────────────────────────────────────────────────


class ArtifactModel(Base):
    __tablename__ = "artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(128), ForeignKey("tasks.id"), nullable=False, index=True)
    artifact_type = Column(String(32), nullable=False)
    bucket = Column(String(64), default="mini-drop")
    object_key = Column(String(512), nullable=False)
    filename = Column(String(256), nullable=True)
    local_path = Column(String(512), nullable=True)
    content_type = Column(String(128), default="application/octet-stream")
    size_bytes = Column(Integer, default=0)
    meta_json = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "artifact_type": self.artifact_type,
            "bucket": self.bucket,
            "object_key": self.object_key,
            "filename": self.filename,
            "local_path": self.local_path,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "metadata": self.meta_json or {},
        }
