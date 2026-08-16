"""SQLAlchemy ORM 模型定义。

与 InMemoryRepository 的数据类结构对齐，
通过 SQLAlchemy 2.0 DeclarativeBase 映射。
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    event,
    func,
    select,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
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
    __table_args__ = (
        Index("uq_task_execution_unit", "execution_unit_id", unique=True),
        Index("ix_tasks_case_id", "case_id"),
        Index("ix_tasks_execution_unit_id", "execution_unit_id"),
    )

    id = Column(String(128), primary_key=True)
    name = Column(String(256), nullable=False)
    agent_id = Column(String(128), ForeignKey("agents.id"), nullable=False)
    target_pid = Column(Integer, nullable=False)
    collector_type = Column(String(32), nullable=False)
    sample_rate = Column(Integer, default=99)
    duration_sec = Column(Integer, default=15)
    status = Column(String(16), nullable=False)
    status_reason = Column(Text, default="")
    # ``status`` remains the backwards-compatible aggregate state exposed by
    # the original API.  Collection and analysis are persisted separately so
    # a successful capture is not lost when a later analyzer attempt fails.
    collection_status = Column(String(16), nullable=False, default="PENDING")
    analysis_status = Column(String(16), nullable=False, default="WAITING")
    current_attempt_id = Column(String(128), nullable=True, index=True)
    row_version = Column(Integer, nullable=False, default=0)
    collection_deadline_at = Column(DateTime(timezone=True), nullable=True, index=True)
    request_id = Column(String(64), nullable=True, index=True)
    traceparent = Column(String(64), nullable=True)
    request_params = Column(JSON, default=dict)
    idempotency_key = Column(String(128), nullable=True, unique=True, index=True)
    diagnosis_step_id = Column(String(128), nullable=True, unique=True, index=True)
    # v6 unified execution lineage.  Case-derived Tasks MUST have an
    # execution_unit_id; standalone Drop tasks keep these fields null.
    origin = Column(String(24), nullable=True, default=None)
    visibility = Column(String(24), nullable=True, default=None)
    case_id = Column(String(128), nullable=True)
    case_title = Column(String(256), nullable=True)
    turn_id = Column(String(128), nullable=True)
    plan_step_id = Column(String(128), nullable=True)
    step_revision_id = Column(String(128), nullable=True)
    campaign_id = Column(String(128), nullable=True)
    campaign_revision = Column(Integer, nullable=True)
    assignment_id = Column(String(128), nullable=True)
    execution_unit_id = Column(String(128), nullable=True)
    risk = Column(String(24), nullable=True)
    purpose = Column(Text, nullable=True)
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
            "collection_status": self.collection_status,
            "analysis_status": self.analysis_status,
            "current_attempt_id": self.current_attempt_id,
            "row_version": self.row_version,
            "collection_deadline_at": self.collection_deadline_at,
            "request_id": self.request_id,
            "traceparent": self.traceparent,
            "request_params": self.request_params or {},
            "idempotency_key": self.idempotency_key,
            "origin": self.origin,
            "visibility": self.visibility,
            "case_id": self.case_id,
            "case_title": self.case_title,
            "turn_id": self.turn_id,
            "plan_step_id": self.plan_step_id,
            "step_revision_id": self.step_revision_id,
            "campaign_id": self.campaign_id,
            "campaign_revision": self.campaign_revision,
            "assignment_id": self.assignment_id,
            "execution_unit_id": self.execution_unit_id,
            "risk": self.risk,
            "purpose": self.purpose,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class TaskAttemptModel(Base):
    """One durable execution attempt for a Task.

    Results are keyed by attempt id so an Agent can replay a completed result
    after a network failure without overwriting evidence from an earlier run.
    """

    __tablename__ = "task_attempts"
    __table_args__ = (
        UniqueConstraint("task_id", "attempt_no", name="uq_task_attempt_number"),
    )

    id = Column(String(128), primary_key=True)
    task_id = Column(String(128), ForeignKey("tasks.id"), nullable=False, index=True)
    attempt_no = Column(Integer, nullable=False)
    agent_id = Column(String(128), ForeignKey("agents.id"), nullable=False, index=True)
    status = Column(String(24), nullable=False, default="DELIVERED")
    runner_version = Column(String(64), nullable=True)
    exit_code = Column(Integer, nullable=True)
    error_code = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)
    result_message = Column(Text, nullable=True)
    resource_usage_json = Column(JSON, default=dict)
    artifact_ids_json = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "attempt_id": self.id,
            "task_id": self.task_id,
            "attempt_no": self.attempt_no,
            "agent_id": self.agent_id,
            "status": self.status,
            "runner_version": self.runner_version,
            "exit_code": self.exit_code,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "result_message": self.result_message,
            "resource_usage": self.resource_usage_json or {},
            "artifact_ids": self.artifact_ids_json or [],
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "updated_at": self.updated_at,
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


class AuthorizationGrantModel(Base):
    """Durable, revocable authorization envelope for AI source access."""

    __tablename__ = "authorization_grants"

    id = Column(String(128), primary_key=True)
    principal_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    source_ids_json = Column(JSON, default=list)
    operations_json = Column(JSON, default=list)
    resource_scope_json = Column(JSON, default=dict)
    mode = Column(String(32), nullable=False)
    case_id = Column(String(128), nullable=True, index=True)
    constraints_json = Column(JSON, default=dict)
    valid_until = Column(DateTime(timezone=True), nullable=False, index=True)
    uses_remaining = Column(Integer, nullable=True)
    query_count = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)
    created_by = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(String(128), nullable=True)

    def to_dict(self) -> dict:
        return {
            "grant_id": self.id,
            "principal_id": self.principal_id,
            "tenant_id": self.tenant_id,
            "source_ids": self.source_ids_json or [],
            "operations": self.operations_json or [],
            "resource_scope": self.resource_scope_json or {},
            "mode": self.mode,
            "case_id": self.case_id,
            "constraints": self.constraints_json or {},
            "valid_until": self.valid_until,
            "uses_remaining": self.uses_remaining,
            "query_count": self.query_count or 0,
            "status": self.status,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "revoked_at": self.revoked_at,
            "revoked_by": self.revoked_by,
        }


# ── AI Incident Case 协作层 ─────────────────────────────────────


class IncidentCaseModel(Base):
    """Tenant-scoped user collaboration aggregate over a diagnosis session."""

    __tablename__ = "incident_cases"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_incident_case_tenant"),
    )

    id = Column(String(128), primary_key=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    created_by = Column(String(128), nullable=False, index=True)
    diagnosis_session_id = Column(
        String(128), ForeignKey("diagnosis_sessions.id"), nullable=True, index=True,
    )
    target_session_id = Column(
        String(128), ForeignKey(
            "diagnostic_target_sessions.id", name="fk_incident_case_target_session",
        ), nullable=True, index=True,
    )
    source_task_id = Column(String(128), ForeignKey("tasks.id"), nullable=True, index=True)
    # 数据驱动入口：同一事故窗口、同一明确实例范围内的已完成 Task 证据。
    initial_task_ids = Column(JSON, default=list)
    title = Column(String(256), nullable=False)
    problem_description = Column(Text, nullable=False)
    recovery_goal = Column(Text, nullable=False)
    run_mode = Column(String(32), nullable=False)
    environment = Column(String(64), nullable=False)
    target_scope_json = Column(JSON, default=dict)
    time_range_json = Column(JSON, default=dict)
    state = Column(String(40), nullable=False, index=True)
    state_reason = Column(String(128), nullable=False)
    impact_json = Column(JSON, default=dict)
    current_finding_json = Column(JSON, default=dict)
    current_activity_json = Column(JSON, default=dict)
    need_user_json = Column(JSON, default=dict)
    recovery_json = Column(JSON, default=dict)
    scope_revision = Column(Integer, nullable=False, default=1)
    control_revision = Column(Integer, nullable=False, default=1, server_default="1")
    case_command_revision = Column(Integer, nullable=False, default=1, server_default="1")
    deployment_epoch = Column(Integer, nullable=False, default=1, server_default="1")
    row_version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    stopped_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "case_id": self.id,
            "tenant_id": self.tenant_id,
            "created_by": self.created_by,
            "diagnosis_session_id": self.diagnosis_session_id,
            "target_session_id": self.target_session_id,
            "source_task_id": self.source_task_id,
            "initial_task_ids": self.initial_task_ids or [],
            "title": self.title,
            "problem_description": self.problem_description,
            "recovery_goal": self.recovery_goal,
            "run_mode": self.run_mode,
            "environment": self.environment,
            "target_scope": self.target_scope_json or {},
            "time_range": self.time_range_json or {},
            "state": self.state,
            "state_reason": self.state_reason,
            "summary": {
                "impact": self.impact_json or {},
                "current_finding": self.current_finding_json or {},
                "what_ai_is_doing": self.current_activity_json or {},
                "need_you": self.need_user_json or {},
                "recovery": self.recovery_json or {},
            },
            "scope_revision": self.scope_revision,
            "control_revision": self.control_revision,
            "case_command_revision": self.case_command_revision,
            "deployment_epoch": self.deployment_epoch,
            "row_version": self.row_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "stopped_at": self.stopped_at,
            "resolved_at": self.resolved_at,
        }


class DiagnosticTargetSessionModel(Base):
    """Long-lived tenant target that accumulates signals and incident Cases."""

    __tablename__ = "diagnostic_target_sessions"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_target_session_tenant"),
        UniqueConstraint(
            "tenant_id", "environment", "service_id",
            name="uq_target_session_tenant_environment_service",
        ),
    )

    id = Column(String(128), primary_key=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    service_id = Column(String(128), nullable=False, index=True)
    environment = Column(String(64), nullable=False, index=True)
    display_name = Column(String(256), nullable=False)
    target_scope_json = Column(JSON, default=dict)
    baseline_json = Column(JSON, default=dict)
    signal_policy_json = Column(JSON, default=dict)
    status = Column(String(24), nullable=False, index=True)
    row_version = Column(Integer, nullable=False, default=0)
    latest_signal_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "target_session_id": self.id,
            "tenant_id": self.tenant_id,
            "service_id": self.service_id,
            "environment": self.environment,
            "display_name": self.display_name,
            "target_scope": self.target_scope_json or {},
            "baseline": self.baseline_json or {},
            "signal_policy": self.signal_policy_json or {},
            "status": self.status,
            "row_version": self.row_version,
            "latest_signal_at": self.latest_signal_at,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class CaseResourceAttachmentModel(Base):
    """Unified data-entry binding: a ResourceRef attached to a Case (E1).

    Replaces the multi-way split (initial_task_ids / source_task_id /
    target_scope.evidence_task_ids / source_collection_ids) with one
    tenant-scoped row so a Task, a Collection batch or a conversation `@`
    reference can be proven to enter the next diagnosis.
    """

    __tablename__ = "case_resource_attachments"
    __table_args__ = (
        UniqueConstraint(
            "case_id", "tenant_id", "resource_type", "resource_id",
            name="uq_attachment_case_resource",
        ),
    )

    id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    resource_type = Column(String(40), nullable=False)
    resource_id = Column(String(128), nullable=False)
    resource_revision = Column(Integer, nullable=True)
    label = Column(String(256), nullable=False)
    source = Column(String(40), nullable=False)
    purpose = Column(Text, nullable=True)
    attached_by = Column(String(128), nullable=False)
    status = Column(String(40), nullable=False, default="PENDING_VALIDATION")
    scope_match = Column(String(20), nullable=False, default="UNKNOWN")
    time_match = Column(String(20), nullable=False, default="UNKNOWN")
    freshness = Column(String(20), nullable=False, default="UNKNOWN")
    quality = Column(String(20), nullable=False, default="UNKNOWN")
    evidence_ids_json = Column(JSON, default=list)
    rejection_reason = Column(String(128), nullable=True)
    supersedes_json = Column(JSON, default=list)
    row_version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "attachment_id": self.id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "resource_ref": {
                "type": self.resource_type,
                "id": self.resource_id,
                "revision": self.resource_revision,
            },
            "label": self.label,
            "source": self.source,
            "purpose": self.purpose,
            "attached_by": self.attached_by,
            "status": self.status,
            "scope_match": self.scope_match,
            "time_match": self.time_match,
            "freshness": self.freshness,
            "quality": self.quality,
            "evidence_ids": self.evidence_ids_json or [],
            "rejection_reason": self.rejection_reason,
            "supersedes": self.supersedes_json or [],
            "row_version": self.row_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class InvestigationPlanModel(Base):
    """Persistent, versioned investigation plan (E2, plan 5.4)."""

    __tablename__ = "investigation_plans"
    __table_args__ = (
        UniqueConstraint(
            "case_id", "tenant_id", "plan_revision", name="uq_plan_case_revision",
        ),
    )

    plan_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False)
    plan_revision = Column(Integer, nullable=False, default=0)
    scope_revision = Column(Integer, nullable=False, default=0)
    goal = Column(String(500), nullable=False)
    status = Column(String(24), nullable=False, default="ACTIVE")
    source = Column(String(40), nullable=False, default="deterministic")
    created_by = Column(String(128), nullable=False)
    row_version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "case_id": self.case_id,
            "plan_revision": self.plan_revision,
            "scope_revision": self.scope_revision,
            "goal": self.goal,
            "status": self.status,
            "source": self.source,
            "created_by": self.created_by,
            "row_version": self.row_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class InvestigationPlanStepModel(Base):
    """A single plan step with its own state machine and revisions (E2)."""

    __tablename__ = "investigation_plan_steps"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id"],
            ["investigation_plans.plan_id"],
            name="fk_plan_step_plan",
        ),
    )

    step_id = Column(String(128), primary_key=True)
    plan_id = Column(String(128), nullable=False)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False)
    plan_revision = Column(Integer, nullable=False, default=0)
    scope_revision = Column(Integer, nullable=False, default=0)
    kind = Column(String(32), nullable=False)
    collector_id = Column(String(128), nullable=True)
    target_refs_json = Column(JSON, nullable=True)
    purpose = Column(String(500), nullable=True)
    hypothesis_refs_json = Column(JSON, nullable=True)
    expected_information = Column(String(500), nullable=True)
    priority = Column(Integer, nullable=False, default=0)
    priority_source = Column(String(16), nullable=False, default="AI")
    user_locked = Column(Boolean, nullable=False, default=False)
    depends_on_json = Column(JSON, nullable=True)
    risk = Column(String(24), nullable=False, default="READ_LOW")
    # E3.5：集群 Step 的选择策略（ALL_IN_SCOPE/REPRESENTATIVE/OUTLIERS/...）
    selection_strategy = Column(String(40), nullable=True)
    status = Column(String(32), nullable=False, default="DRAFT")
    task_ids_json = Column(JSON, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "plan_id": self.plan_id,
            "case_id": self.case_id,
            "plan_revision": self.plan_revision,
            "scope_revision": self.scope_revision,
            "kind": self.kind,
            "collector_id": self.collector_id,
            "target_refs": self.target_refs_json or [],
            "purpose": self.purpose,
            "hypothesis_refs": self.hypothesis_refs_json or [],
            "expected_information": self.expected_information,
            "priority": self.priority,
            "priority_source": self.priority_source,
            "user_locked": self.user_locked,
            "depends_on": self.depends_on_json or [],
            "risk": self.risk,
            "selection_strategy": self.selection_strategy,
            "status": self.status,
            "task_ids": self.task_ids_json or [],
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class MembershipSnapshotModel(Base):
    """E3.5: 冻结的集群成员快照；调查期间成员变化不修改历史快照。"""

    __tablename__ = "membership_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "case_id", "tenant_id", "snapshot_id", name="uq_membership_snapshot",
        ),
    )

    snapshot_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False)
    environment_id = Column(String(128), nullable=False, default="")
    cluster_id = Column(String(128), nullable=False, default="")
    topology_version = Column(String(64), nullable=False, default="")
    scope_revision = Column(Integer, nullable=False, default=1)
    members_json = Column(JSON, nullable=False, default=list)
    captured_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "environment_id": self.environment_id,
            "cluster_id": self.cluster_id,
            "topology_version": self.topology_version,
            "scope_revision": self.scope_revision,
            "members": self.members_json or [],
            "captured_at": self.captured_at,
        }


class FanoutCollectionRunModel(Base):
    """E3.5: 一个逻辑采集步骤展开出的多个单目标 Task 及聚合结果。"""

    __tablename__ = "fanout_collection_runs"
    __table_args__ = (
        UniqueConstraint(
            "case_id", "tenant_id", "run_id", name="uq_fanout_run",
        ),
    )

    run_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False)
    plan_step_id = Column(String(128), nullable=False, default="")
    plan_revision = Column(Integer, nullable=False, default=0)
    scope_revision = Column(Integer, nullable=False, default=1)
    snapshot_id = Column(String(128), nullable=False, default="")
    strategy = Column(String(40), nullable=False, default="ALL_IN_SCOPE")
    collector_id = Column(String(128), nullable=False, default="sys_metrics")
    target_members_json = Column(JSON, nullable=False, default=list)
    task_ids_json = Column(JSON, nullable=False, default=list)
    member_task_map_json = Column(JSON, nullable=False, default=dict)
    task_statuses_json = Column(JSON, nullable=False, default=dict)
    status = Column(String(24), nullable=False, default="RUNNING")
    coverage = Column(Float, nullable=False, default=0.0)
    failed_count = Column(Integer, nullable=False, default=0)
    quorum_met = Column(Boolean, nullable=False, default=False)
    aggregate_json = Column(JSON, nullable=False, default=dict)
    late_result_isolated_json = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "plan_step_id": self.plan_step_id,
            "plan_revision": self.plan_revision,
            "scope_revision": self.scope_revision,
            "snapshot_id": self.snapshot_id,
            "strategy": self.strategy,
            "collector_id": self.collector_id,
            "target_members": self.target_members_json or [],
            "task_ids": self.task_ids_json or [],
            "member_task_map": self.member_task_map_json or {},
            "task_statuses": self.task_statuses_json or {},
            "status": self.status,
            "coverage": self.coverage or 0.0,
            "failed_count": self.failed_count or 0,
            "quorum_met": self.quorum_met,
            "aggregate": self.aggregate_json or {},
            "late_result_isolated": self.late_result_isolated_json or [],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class EvidenceReviewModel(Base):
    """User/system decision about an evidence item (E2, plan 5.5)."""

    __tablename__ = "evidence_reviews"
    __table_args__ = (
        UniqueConstraint(
            "case_id", "tenant_id", "evidence_id", "review_revision",
            name="uq_evidence_review_revision",
        ),
    )

    review_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False)
    evidence_id = Column(String(128), nullable=False)
    decision = Column(String(20), nullable=False)
    reason_code = Column(String(64), nullable=True)
    reason = Column(String(1000), nullable=True)
    actor_id = Column(String(128), nullable=False)
    review_revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "review_id": self.review_id,
            "case_id": self.case_id,
            "evidence_id": self.evidence_id,
            "decision": self.decision,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "actor_id": self.actor_id,
            "review_revision": self.review_revision,
            "created_at": self.created_at,
        }


class CollectionDecisionModel(Base):
    """Recorded reuse/recollect decision (E2, plan 5.3)."""

    __tablename__ = "collection_decisions"

    decision_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False)
    requested_collector = Column(String(128), nullable=False)
    purpose = Column(String(500), nullable=True)
    result = Column(String(32), nullable=False)
    reused_task_ids_json = Column(JSON, nullable=True)
    new_plan_step_ids_json = Column(JSON, nullable=True)
    reason_codes_json = Column(JSON, nullable=True)
    estimated_cost_json = Column(JSON, nullable=True)
    created_by = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "case_id": self.case_id,
            "requested_collector": self.requested_collector,
            "purpose": self.purpose,
            "result": self.result,
            "reused_task_ids": self.reused_task_ids_json or [],
            "new_plan_step_ids": self.new_plan_step_ids_json or [],
            "reason_codes": self.reason_codes_json or [],
            "estimated_cost": self.estimated_cost_json or {},
            "created_by": self.created_by,
            "created_at": self.created_at,
        }


class TargetSignalModel(Base):
    """Immutable normalized signal received by a long-lived target session."""

    __tablename__ = "target_signals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["target_session_id", "tenant_id"],
            ["diagnostic_target_sessions.id", "diagnostic_target_sessions.tenant_id"],
            name="fk_target_signal_session_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "target_session_id", "dedupe_key", name="uq_target_signal_dedupe",
        ),
    )

    id = Column(String(128), primary_key=True)
    target_session_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    signal_type = Column(String(64), nullable=False, index=True)
    severity = Column(String(16), nullable=False, index=True)
    observed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    payload_json = Column(JSON, default=dict)
    profile_window_ids_json = Column(JSON, default=list)
    dedupe_key = Column(String(128), nullable=False)
    status = Column(String(24), nullable=False)
    triggered_case_id = Column(String(128), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "signal_id": self.id,
            "target_session_id": self.target_session_id,
            "tenant_id": self.tenant_id,
            "signal_type": self.signal_type,
            "severity": self.severity,
            "observed_at": self.observed_at,
            "payload": self.payload_json or {},
            "profile_window_ids": self.profile_window_ids_json or [],
            "dedupe_key": self.dedupe_key,
            "status": self.status,
            "triggered_case_id": self.triggered_case_id,
            "created_at": self.created_at,
        }


class ProfileWindowModel(Base):
    """Queryable index over a continuous profiling capture window."""

    __tablename__ = "profile_windows"
    __table_args__ = (
        ForeignKeyConstraint(
            ["target_session_id", "tenant_id"],
            ["diagnostic_target_sessions.id", "diagnostic_target_sessions.tenant_id"],
            name="fk_profile_window_session_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "target_session_id", "task_id", "window_index",
            name="uq_profile_window_target_task_index",
        ),
        Index(
            "ix_profile_window_target_time",
            "target_session_id", "tenant_id", "window_start", "window_end",
        ),
    )

    id = Column(String(128), primary_key=True)
    target_session_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    task_id = Column(String(128), ForeignKey("tasks.id"), nullable=False, index=True)
    agent_id = Column(String(128), nullable=False, index=True)
    target_pid = Column(Integer, nullable=False)
    window_index = Column(Integer, nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False, index=True)
    window_end = Column(DateTime(timezone=True), nullable=False, index=True)
    granularity = Column(String(24), nullable=False, default="detail")
    artifact_refs_json = Column(JSON, default=list)
    meta_json = Column("metadata", JSON, default=dict)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "profile_window_id": self.id,
            "target_session_id": self.target_session_id,
            "tenant_id": self.tenant_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "target_pid": self.target_pid,
            "window_index": self.window_index,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "granularity": self.granularity,
            "artifact_refs": self.artifact_refs_json or [],
            "metadata": self.meta_json or {},
            "expires_at": self.expires_at,
            "created_at": self.created_at,
        }


class CaseEventModel(Base):
    """Immutable, tenant-bound Case timeline event."""

    __tablename__ = "case_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["case_id", "tenant_id"],
            ["incident_cases.id", "incident_cases.tenant_id"],
            name="fk_case_event_case_tenant",
            ondelete="CASCADE",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    case_event_seq = Column(Integer, nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    actor_id = Column(String(128), nullable=False)
    payload_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "event_id": self.id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "case_event_seq": self.case_event_seq,
            "event_type": self.event_type,
            "actor_id": self.actor_id,
            "payload": self.payload_json or {},
            "created_at": self.created_at,
        }


class CaseRecoveryPlanModel(Base):
    """Durable Case recovery workflow from proposal through verification/rollback."""

    __tablename__ = "case_recovery_plans"
    __table_args__ = (
        ForeignKeyConstraint(
            ["case_id", "tenant_id"],
            ["incident_cases.id", "incident_cases.tenant_id"],
            name="fk_recovery_plan_case_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "dry_run_attempt_id", name="uq_case_recovery_plans_dry_run_attempt_id",
        ),
        Index("ix_recovery_plan_case_status", "case_id", "tenant_id", "status"),
    )

    id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False)
    tenant_id = Column(String(128), nullable=False)
    diagnosis_session_id = Column(String(128), nullable=True, index=True)
    action_id = Column(String(128), nullable=False, index=True)
    parameters_json = Column(JSON, default=dict)
    value_after_fix = Column(Text, default="")
    verification_method = Column(Text, default="")
    status = Column(String(40), nullable=False, index=True)
    policy_json = Column(JSON, default=dict)
    dry_run_attempt_id = Column(String(128), nullable=True)
    dry_run_json = Column(JSON, default=dict)
    execution_json = Column(JSON, default=dict)
    verification_json = Column(JSON, default=dict)
    rollback_json = Column(JSON, default=dict)
    requires_approval = Column(Integer, nullable=False, default=1)
    approved_by = Column(String(128), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    row_version = Column(Integer, nullable=False, default=0)
    created_by = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "recovery_plan_id": self.id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "diagnosis_session_id": self.diagnosis_session_id,
            "action_id": self.action_id,
            "parameters": self.parameters_json or {},
            "value_after_fix": self.value_after_fix or "",
            "verification_method": self.verification_method or "",
            "status": self.status,
            "policy": self.policy_json or {},
            "dry_run_attempt_id": self.dry_run_attempt_id,
            "dry_run": self.dry_run_json or {},
            "execution": self.execution_json or {},
            "verification": self.verification_json or {},
            "rollback": self.rollback_json or {},
            "requires_approval": bool(self.requires_approval),
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "rejection_reason": self.rejection_reason,
            "row_version": self.row_version,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ServiceChangeModel(Base):
    """用户登记的发布/配置变更（变更登记，C 方案，见 docs/ai_diagnosis_agent_design.md §7）。

    供 AI 做"变更前 vs 变更后"对比与回归关联；也能由 AI 走 Need You 追问后回填。
    """

    __tablename__ = "service_changes"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_service_change_tenant"),
        Index(
            "ix_service_changes_tenant_service",
            "tenant_id",
            "service_id",
            "changed_at",
        ),
    )

    id = Column(String(128), primary_key=True)
    tenant_id = Column(String(128), nullable=False)
    service_id = Column(String(128), nullable=False)
    environment = Column(String(64), nullable=False, default="unknown")
    change_type = Column(String(32), nullable=False)  # release/config/feature_flag/scale/other
    title = Column(String(256), nullable=False)
    description = Column(Text, default="")
    changed_at = Column(DateTime(timezone=True), nullable=False)
    created_by = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "change_id": self.id,
            "tenant_id": self.tenant_id,
            "service_id": self.service_id,
            "environment": self.environment,
            "change_type": self.change_type,
            "title": self.title,
            "description": self.description,
            "changed_at": self.changed_at,
            "created_by": self.created_by,
            "created_at": self.created_at,
        }


class ContextPacketModel(Base):
    """Immutable, versioned projection used as one Case model-call input."""

    __tablename__ = "case_context_packets"
    __table_args__ = (
        UniqueConstraint(
            "id", "case_id", "tenant_id", name="uq_context_packet_case_tenant",
        ),
        ForeignKeyConstraint(
            ["case_id", "tenant_id"],
            ["incident_cases.id", "incident_cases.tenant_id"],
            name="fk_context_packet_case_tenant",
            ondelete="CASCADE",
        ),
    )

    id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    schema_version = Column(String(64), nullable=False)
    purpose = Column(String(128), nullable=False)
    iteration_no = Column(Integer, nullable=False)
    payload_json = Column(JSON, nullable=False)
    projection_stats_json = Column(JSON, default=dict)
    source_versions_json = Column(JSON, default=dict)
    content_hash = Column(String(64), nullable=False)
    created_by = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "context_packet_id": self.id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "schema_version": self.schema_version,
            "purpose": self.purpose,
            "iteration_no": self.iteration_no,
            "payload": self.payload_json or {},
            "projection_stats": self.projection_stats_json or {},
            "source_versions": self.source_versions_json or {},
            "content_hash": self.content_hash,
            "created_by": self.created_by,
            "created_at": self.created_at,
        }


class ModelAttemptModel(Base):
    """Auditable model-call metadata; raw reasoning and credentials are never stored."""

    __tablename__ = "case_model_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["context_packet_id", "case_id", "tenant_id"],
            [
                "case_context_packets.id",
                "case_context_packets.case_id",
                "case_context_packets.tenant_id",
            ],
            name="fk_model_attempt_context_case_tenant",
            ondelete="CASCADE",
        ),
    )

    id = Column(String(128), primary_key=True)
    context_packet_id = Column(String(128), nullable=False, index=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    provider = Column(String(64), nullable=False)
    model = Column(String(128), nullable=False)
    model_snapshot = Column(String(128), nullable=True)
    prompt_version = Column(String(128), nullable=False)
    output_schema = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False)
    latency_ms = Column(Integer, nullable=False, default=0)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    response_hash = Column(String(64), nullable=True)
    error_code = Column(String(128), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "model_attempt_id": self.id,
            "context_packet_id": self.context_packet_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "provider": self.provider,
            "model": self.model,
            "model_snapshot": self.model_snapshot,
            "prompt_version": self.prompt_version,
            "output_schema": self.output_schema,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "response_hash": self.response_hash,
            "error_code": self.error_code,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class CaseHypothesisNodeModel(Base):
    """Normalized Case hypothesis with explicit support, contradiction and gaps."""

    __tablename__ = "case_hypothesis_nodes"
    __table_args__ = (
        UniqueConstraint(
            "case_id", "tenant_id", "hypothesis_id", name="uq_case_hypothesis",
        ),
        ForeignKeyConstraint(
            ["case_id", "tenant_id"],
            ["incident_cases.id", "incident_cases.tenant_id"],
            name="fk_hypothesis_case_tenant",
            ondelete="CASCADE",
        ),
    )

    id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    hypothesis_id = Column(String(128), nullable=False, index=True)
    statement = Column(Text, nullable=False)
    root_entity = Column(String(256), nullable=True)
    mechanism = Column(String(128), nullable=True)
    affected_entities_json = Column(JSON, default=list)
    status = Column(String(32), nullable=False, index=True)
    supporting_evidence_refs_json = Column(JSON, default=list)
    contradicting_evidence_refs_json = Column(JSON, default=list)
    missing_evidence_json = Column(JSON, default=list)
    alternatives_json = Column(JSON, default=list)
    score_components_json = Column(JSON, default=dict)
    source = Column(String(64), nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "hypothesis_id": self.hypothesis_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "statement": self.statement,
            "root_entity": self.root_entity,
            "mechanism": self.mechanism,
            "affected_entities": self.affected_entities_json or [],
            "status": self.status,
            "supporting_evidence_refs": self.supporting_evidence_refs_json or [],
            "contradicting_evidence_refs": self.contradicting_evidence_refs_json or [],
            "missing_evidence": self.missing_evidence_json or [],
            "alternatives": self.alternatives_json or [],
            "score_components": self.score_components_json or {},
            "source": self.source,
            "revision": self.revision,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class CaseHypothesisEdgeModel(Base):
    __tablename__ = "case_hypothesis_edges"
    __table_args__ = (
        ForeignKeyConstraint(
            ["case_id", "tenant_id"],
            ["incident_cases.id", "incident_cases.tenant_id"],
            name="fk_hypothesis_edge_case_tenant",
            ondelete="CASCADE",
        ),
    )

    id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    source_hypothesis_id = Column(String(128), nullable=False)
    target_hypothesis_id = Column(String(128), nullable=False)
    relation = Column(String(32), nullable=False)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "edge_id": self.id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "source": self.source_hypothesis_id,
            "target": self.target_hypothesis_id,
            "relation": self.relation,
            "metadata": self.metadata_json or {},
            "created_at": self.created_at,
        }


class InvestigationIterationModel(Base):
    """One auditable Case investigation decision and its observed outcome."""

    __tablename__ = "case_investigation_iterations"
    __table_args__ = (
        UniqueConstraint(
            "case_id", "tenant_id", "iteration_no", name="uq_case_iteration_no",
        ),
        ForeignKeyConstraint(
            ["case_id", "tenant_id"],
            ["incident_cases.id", "incident_cases.tenant_id"],
            name="fk_iteration_case_tenant",
            ondelete="CASCADE",
        ),
    )

    id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    iteration_no = Column(Integer, nullable=False)
    context_packet_id = Column(
        String(128), ForeignKey("case_context_packets.id"), nullable=True, index=True,
    )
    status = Column(String(32), nullable=False, index=True)
    input_evidence_refs_json = Column(JSON, default=list)
    hypothesis_changes_json = Column(JSON, default=list)
    candidate_actions_json = Column(JSON, default=list)
    selected_action_json = Column(JSON, default=dict)
    policy_decision_json = Column(JSON, default=dict)
    cost_json = Column(JSON, default=dict)
    result_json = Column(JSON, default=dict)
    stop_decision_json = Column(JSON, default=dict)
    created_by = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "iteration_id": self.id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "iteration_no": self.iteration_no,
            "context_packet_id": self.context_packet_id,
            "status": self.status,
            "input_evidence_refs": self.input_evidence_refs_json or [],
            "hypothesis_changes": self.hypothesis_changes_json or [],
            "candidate_actions": self.candidate_actions_json or [],
            "selected_action": self.selected_action_json or {},
            "policy_decision": self.policy_decision_json or {},
            "cost": self.cost_json or {},
            "result": self.result_json or {},
            "stop_decision": self.stop_decision_json or {},
            "created_by": self.created_by,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


class ActionAttemptModel(Base):
    """Durable record of one registered action attempt lifecycle.

    Phases: dry_run / execute / verify / rollback. Idempotent per
    (case_id, tenant_id, operation_key, phase) so Control restarts cannot
    duplicate a logical action attempt.
    """

    __tablename__ = "action_attempts"
    __table_args__ = (
        UniqueConstraint(
            "case_id", "tenant_id", "operation_key", "phase",
            name="uq_case_action_phase",
        ),
        ForeignKeyConstraint(
            ["case_id", "tenant_id"],
            ["incident_cases.id", "incident_cases.tenant_id"],
            name="fk_action_attempt_case_tenant",
            ondelete="CASCADE",
        ),
    )

    id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    action_id = Column(String(128), nullable=False, index=True)
    operation_key = Column(String(256), nullable=False, index=True)
    phase = Column(String(32), nullable=False)
    parameters_json = Column(JSON, default=dict)
    result_json = Column(JSON, default=dict)
    row_version = Column(Integer, nullable=False, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "attempt_id": self.id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "action_id": self.action_id,
            "operation_key": self.operation_key,
            "phase": self.phase,
            "parameters": self.parameters_json or {},
            "result": self.result_json or {},
            "row_version": self.row_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class CaseRuntimeLeaseModel(Base):
    """Short-lived lease so only one Control copy advances a Case at a time."""

    __tablename__ = "case_runtime_leases"
    __table_args__ = (
        UniqueConstraint("case_id", "tenant_id", name="uq_case_runtime_lease"),
        ForeignKeyConstraint(
            ["case_id", "tenant_id"],
            ["incident_cases.id", "incident_cases.tenant_id"],
            name="fk_lease_case_tenant",
            ondelete="CASCADE",
        ),
    )

    id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    owner = Column(String(128), nullable=False)
    lease_until = Column(DateTime(timezone=True), nullable=False, index=True)
    row_version = Column(Integer, nullable=False, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "lease_id": self.id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "owner": self.owner,
            "lease_until": self.lease_until,
            "row_version": self.row_version,
        }


class CaseCommandModel(Base):
    """Queued user/system command for a Case (pause/resume/stop/correction/approval)."""

    __tablename__ = "case_commands"
    __table_args__ = (
        UniqueConstraint(
            "case_id", "tenant_id", "idempotency_key", name="uq_case_command_idem",
        ),
        ForeignKeyConstraint(
            ["case_id", "tenant_id"],
            ["incident_cases.id", "incident_cases.tenant_id"],
            name="fk_command_case_tenant",
            ondelete="CASCADE",
        ),
    )

    id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False)
    command_type = Column(String(32), nullable=False)
    idempotency_key = Column(String(256), nullable=False)
    status = Column(String(16), nullable=False, default="PENDING", index=True)
    payload_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "command_id": self.id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "command_type": self.command_type,
            "idempotency_key": self.idempotency_key,
            "status": self.status,
            "payload": self.payload_json or {},
            "created_at": self.created_at,
            "processed_at": self.processed_at,
        }


class SystemControlModel(Base):
    """Global governance controls (Red Button, capability key rotation epoch)."""

    __tablename__ = "system_controls"

    control_name = Column(String(64), primary_key=True)
    enabled = Column(Boolean, nullable=False, default=False)
    value_json = Column(JSON, default=dict)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "control_name": self.control_name,
            "enabled": bool(self.enabled),
            "value": self.value_json or {},
            "updated_at": self.updated_at,
        }


# ── 产物 ───────────────────────────────────────────────────────


class ArtifactModel(Base):
    __tablename__ = "artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(128), ForeignKey("tasks.id"), nullable=False, index=True)
    attempt_id = Column(String(128), ForeignKey("task_attempts.id"), nullable=True, index=True)
    identity_key = Column(String(64), nullable=True, unique=True, index=True)
    artifact_type = Column(String(32), nullable=False)
    bucket = Column(String(64), default="mini-drop")
    object_key = Column(String(512), nullable=False)
    filename = Column(String(256), nullable=True)
    local_path = Column(String(512), nullable=True)
    content_type = Column(String(128), default="application/octet-stream")
    size_bytes = Column(Integer, default=0)
    sha256 = Column(String(64), nullable=True)
    meta_json = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "attempt_id": self.attempt_id,
            "artifact_type": self.artifact_type,
            "bucket": self.bucket,
            "object_key": self.object_key,
            "filename": self.filename,
            "local_path": self.local_path,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "metadata": self.meta_json or {},
            "created_at": self.created_at,
        }


class AnalysisJobModel(Base):
    """Lease-based asynchronous analysis work item."""

    __tablename__ = "analysis_jobs"
    __table_args__ = (
        UniqueConstraint(
            "task_id", "attempt_id", "pipeline",
            name="uq_analysis_job_task_attempt_pipeline",
        ),
    )

    id = Column(String(128), primary_key=True)
    task_id = Column(String(128), ForeignKey("tasks.id"), nullable=False, index=True)
    attempt_id = Column(String(128), ForeignKey("task_attempts.id"), nullable=False, index=True)
    pipeline = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False, default="PENDING", index=True)
    priority = Column(Integer, nullable=False, default=0)
    lease_owner = Column(String(128), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    analyzer_version = Column(String(64), nullable=True)
    input_artifact_ids_json = Column(JSON, default=list)
    output_artifact_ids_json = Column(JSON, default=list)
    error_code = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "analysis_job_id": self.id,
            "task_id": self.task_id,
            "attempt_id": self.attempt_id,
            "pipeline": self.pipeline,
            "status": self.status,
            "priority": self.priority,
            "lease_owner": self.lease_owner,
            "lease_expires_at": self.lease_expires_at,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "analyzer_version": self.analyzer_version,
            "input_artifact_ids": self.input_artifact_ids_json or [],
            "output_artifact_ids": self.output_artifact_ids_json or [],
            "error_code": self.error_code,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "updated_at": self.updated_at,
        }


class AnalyzerWorkerModel(Base):
    """Readiness heartbeat for an independently deployed Analyzer process."""

    __tablename__ = "analyzer_workers"

    id = Column(String(128), primary_key=True)
    version = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False)
    current_job_id = Column(String(128), nullable=True, index=True)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "worker_id": self.id,
            "version": self.version,
            "status": self.status,
            "current_job_id": self.current_job_id,
            "last_heartbeat_at": self.last_heartbeat_at,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
        }


# ── 智能归因 ───────────────────────────────────────────────────


class DiagnosisRunModel(Base):
    __tablename__ = "diagnosis_runs"

    id = Column(String(128), primary_key=True)
    task_id = Column(String(128), ForeignKey("tasks.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False)
    model_name = Column(String(64), nullable=False)
    summary = Column(Text, default="")
    validated = Column(Integer, default=0)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "status": self.status,
            "model_name": self.model_name,
            "summary": self.summary or "",
            "validated": bool(self.validated),
            "retry_count": self.retry_count,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


class DiagnosisToolResultModel(Base):
    __tablename__ = "diagnosis_tool_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    diagnosis_id = Column(String(128), ForeignKey("diagnosis_runs.id"), nullable=False, index=True)
    tool_name = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)
    evidence_ref = Column(String(128), nullable=False)
    input_json = Column(JSON, default=dict)
    output_json = Column(JSON, default=dict)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "status": self.status,
            "evidence_ref": self.evidence_ref,
            "input": self.input_json or {},
            "output": self.output_json or {},
            "error_message": self.error_message,
            "created_at": self.created_at,
        }


class DiagnosisReportModel(Base):
    __tablename__ = "diagnosis_reports"

    id = Column(String(128), primary_key=True)
    diagnosis_id = Column(String(128), ForeignKey("diagnosis_runs.id"), nullable=False, index=True)
    report_json = Column(JSON, default=dict)
    ranked_causes_json = Column(JSON, default=list)
    confidence = Column(Integer, default=0)
    not_enough_evidence = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "diagnosis_id": self.diagnosis_id,
            "report": self.report_json or {},
            "ranked_causes": self.ranked_causes_json or [],
            "confidence": (self.confidence or 0) / 1000,
            "not_enough_evidence": bool(self.not_enough_evidence),
            "created_at": self.created_at,
        }


class RepairPlanModel(Base):
    __tablename__ = "repair_plans"

    id = Column(String(128), primary_key=True)
    diagnosis_id = Column(String(128), ForeignKey("diagnosis_runs.id"), nullable=False, index=True)
    cause_id = Column(String(128), nullable=False)
    risk_level = Column(String(32), nullable=False)
    actions_json = Column(JSON, default=list)
    executed_actions_json = Column(JSON, default=list)
    requires_user_confirm = Column(Integer, default=1)
    status = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "diagnosis_id": self.diagnosis_id,
            "cause_id": self.cause_id,
            "risk_level": self.risk_level,
            "actions": self.actions_json or [],
            "executed_actions": self.executed_actions_json or [],
            "requires_user_confirm": bool(self.requires_user_confirm),
            "status": self.status,
            "created_at": self.created_at,
        }


class RCAFeedbackModel(Base):
    __tablename__ = "rca_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    diagnosis_id = Column(String(128), ForeignKey("diagnosis_runs.id"), nullable=False, index=True)
    task_id = Column(String(128), nullable=False, index=True)
    predicted_cause_id = Column(String(128), nullable=False)
    feedback_label = Column(String(32), nullable=False)
    corrected_cause_id = Column(String(128), nullable=True)
    feedback_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)


class RCAFeedbackWeightModel(Base):
    __tablename__ = "rca_feedback_weights"

    candidate_id = Column(String(128), primary_key=True)
    positive_count = Column(Integer, default=0)
    negative_count = Column(Integer, default=0)
    partial_count = Column(Integer, default=0)
    weight_delta = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), nullable=False)


# ── Agent 指标快照 ───────────────────────────────────────────────


class AgentMetricSnapshotModel(Base):
    """Agent 周期性资源开销快照，用于趋势分析和容量规划。"""

    __tablename__ = "agent_metric_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String(128), ForeignKey("agents.id"), nullable=False, index=True)
    cpu_percent = Column(Integer, default=0)
    rss_mb = Column(Integer, default=0)
    read_kb_s = Column(Integer, default=0)
    write_kb_s = Column(Integer, default=0)
    children_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "cpu_percent": self.cpu_percent,
            "rss_mb": self.rss_mb,
            "read_kb_s": self.read_kb_s,
            "write_kb_s": self.write_kb_s,
            "children_count": self.children_count,
            "created_at": self.created_at,
        }


# ── AI 集群诊断控制层 ────────────────────────────────────────────


class TopologySnapshotModel(Base):
    """诊断创建时冻结的服务/实例/宿主机拓扑。"""

    __tablename__ = "topology_snapshots"

    id = Column(String(128), primary_key=True)
    effective_at = Column(DateTime(timezone=True), nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=False)
    nodes_json = Column(JSON, default=list)
    edges_json = Column(JSON, default=list)
    source_versions_json = Column(JSON, default=dict)
    confidence_summary_json = Column(JSON, default=dict)

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.id,
            "effective_at": self.effective_at,
            "generated_at": self.generated_at,
            "nodes": self.nodes_json or [],
            "edges": self.edges_json or [],
            "source_versions": self.source_versions_json or {},
            "confidence_summary": self.confidence_summary_json or {},
        }


class DiagnosisSessionModel(Base):
    """独立于单个采集 Task 的、可恢复的诊断工作流。"""

    __tablename__ = "diagnosis_sessions"

    id = Column(String(128), primary_key=True)
    creator_id = Column(String(128), nullable=False)
    raw_query = Column(Text, nullable=False)
    normalized_intent_json = Column(JSON, default=dict)
    target_scope_json = Column(JSON, default=dict)
    requested_time_range_json = Column(JSON, default=dict)
    effective_time_range_json = Column(JSON, default=dict)
    topology_snapshot_id = Column(
        String(128), ForeignKey("topology_snapshots.id"), nullable=True, index=True,
    )
    baseline_snapshot_id = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False)
    policy_profile = Column(String(64), nullable=False)
    risk_budget_json = Column(JSON, default=dict)
    resource_budget_json = Column(JSON, default=dict)
    budget_used_json = Column(JSON, default=dict)
    hypothesis_graph_json = Column(JSON, default=dict)
    evaluation_oracle_json = Column(JSON, default=dict)
    child_task_ids_json = Column(JSON, default=list)
    conclusion_versions_json = Column(JSON, default=list)
    # 数据驱动入口：initial_tasks 装载为初始证据的记录
    initial_evidence_loaded_json = Column(JSON, default=list)
    initial_evidence_count = Column(Integer, default=0)
    model_version = Column(String(128), nullable=False)
    planner_version = Column(String(64), nullable=False)
    lease_owner = Column(String(128), nullable=True)
    lease_until = Column(DateTime(timezone=True), nullable=True)
    paused_from_status = Column(String(32), nullable=True)
    row_version = Column(Integer, nullable=False, default=0)
    deadline_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "diagnosis_id": self.id,
            "creator_id": self.creator_id,
            "raw_query": self.raw_query,
            "initial_evidence_loaded": self.initial_evidence_loaded_json or [],
            "initial_evidence_count": self.initial_evidence_count or 0,
            "normalized_intent": self.normalized_intent_json or {},
            "target_scope": self.target_scope_json or {},
            "requested_time_range": self.requested_time_range_json or {},
            "effective_time_range": self.effective_time_range_json or {},
            "topology_snapshot_id": self.topology_snapshot_id,
            "baseline_snapshot_id": self.baseline_snapshot_id,
            "status": self.status,
            "policy_profile": self.policy_profile,
            "risk_budget": self.risk_budget_json or {},
            "resource_budget": self.resource_budget_json or {},
            "budget_used": self.budget_used_json or {},
            "hypothesis_graph": self.hypothesis_graph_json or {},
            "evaluation_oracle": self.evaluation_oracle_json or {},
            "child_task_ids": self.child_task_ids_json or [],
            "conclusion_versions": self.conclusion_versions_json or [],
            "model_version": self.model_version,
            "planner_version": self.planner_version,
            "lease_owner": self.lease_owner,
            "lease_until": self.lease_until,
            "paused_from_status": self.paused_from_status,
            "row_version": self.row_version,
            "deadline_at": self.deadline_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class DiagnosisEventModel(Base):
    __tablename__ = "diagnosis_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    diagnosis_id = Column(
        String(128), ForeignKey("diagnosis_sessions.id"), nullable=False, index=True,
    )
    event_type = Column(String(64), nullable=False)
    from_status = Column(String(32), nullable=True)
    to_status = Column(String(32), nullable=False)
    payload_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "diagnosis_id": self.diagnosis_id,
            "event_type": self.event_type,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "payload": self.payload_json or {},
            "created_at": self.created_at,
        }


class ProbeExecutionModel(Base):
    """一次受控探针计划/审批/执行记录；step id 同时作为幂等键。"""

    __tablename__ = "diagnosis_probe_executions"

    id = Column(String(128), primary_key=True)
    diagnosis_id = Column(
        String(128), ForeignKey("diagnosis_sessions.id"), nullable=False, index=True,
    )
    probe_id = Column(String(128), nullable=False)
    target_json = Column(JSON, default=dict)
    parameters_json = Column(JSON, default=dict)
    reason = Column(Text, nullable=False)
    risk_level = Column(String(8), nullable=False)
    status = Column(String(32), nullable=False)
    requires_approval = Column(Integer, default=0)
    task_id = Column(String(128), ForeignKey("tasks.id"), nullable=True, index=True)
    approved_by = Column(String(128), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    retry_count = Column(Integer, nullable=False, default=0)
    error_code = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "step_id": self.id,
            "diagnosis_id": self.diagnosis_id,
            "probe_id": self.probe_id,
            "target": self.target_json or {},
            "parameters": self.parameters_json or {},
            "reason": self.reason,
            "risk_level": self.risk_level,
            "status": self.status,
            "requires_approval": bool(self.requires_approval),
            "task_id": self.task_id,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "retry_count": self.retry_count,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


class DiagnosisOutboxModel(Base):
    """Transactional intent to create the one Task belonging to a probe step."""

    __tablename__ = "diagnosis_task_outbox"

    id = Column(String(160), primary_key=True)
    diagnosis_id = Column(String(128), ForeignKey("diagnosis_sessions.id"), nullable=False, index=True)
    step_id = Column(String(128), ForeignKey("diagnosis_probe_executions.id"), nullable=False, unique=True)
    status = Column(String(32), nullable=False, default="PENDING")
    attempt = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class DiagnosisEvidenceModel(Base):
    """可追溯到 Task/Artifact 的不可变证据摘要。"""

    __tablename__ = "diagnosis_evidence"

    id = Column(String(128), primary_key=True)
    diagnosis_id = Column(
        String(128), ForeignKey("diagnosis_sessions.id"), nullable=False, index=True,
    )
    source_type = Column(String(32), nullable=False)
    source_system = Column(String(64), nullable=False)
    evidence_role = Column(String(32), nullable=False, default="incident")
    target_json = Column(JSON, default=dict)
    event_time_range_json = Column(JSON, default=dict)
    ingestion_time = Column(DateTime(timezone=True), nullable=False)
    query_or_probe = Column(String(256), nullable=False)
    raw_artifact_ref = Column(String(512), nullable=True)
    derived_artifact_ref = Column(String(512), nullable=True)
    derivation_version = Column(String(64), nullable=False)
    observed_value_json = Column(JSON, default=dict)
    baseline_value_json = Column(JSON, default=dict)
    anomaly_score_json = Column(JSON, default=dict)
    data_quality_json = Column(JSON, default=dict)
    integrity_hash = Column(String(80), nullable=False)
    claim_links_json = Column(JSON, default=list)

    def to_dict(self) -> dict:
        return {
            "evidence_id": self.id,
            "diagnosis_id": self.diagnosis_id,
            "source_type": self.source_type,
            "source_system": self.source_system,
            "evidence_role": self.evidence_role,
            "target": self.target_json or {},
            "event_time_range": self.event_time_range_json or {},
            "ingestion_time": self.ingestion_time,
            "query_or_probe": self.query_or_probe,
            "raw_artifact_ref": self.raw_artifact_ref,
            "derived_artifact_ref": self.derived_artifact_ref,
            "derivation_version": self.derivation_version,
            "observed_value": self.observed_value_json or {},
            "baseline_value": self.baseline_value_json or {},
            "anomaly_score": self.anomaly_score_json or {},
            "data_quality": self.data_quality_json or {},
            "integrity_hash": self.integrity_hash,
            "claim_links": self.claim_links_json or [],
        }


class DiagnosisNodeRunModel(Base):
    """显式诊断流水线节点的可恢复运行记录。"""

    __tablename__ = "diagnosis_node_runs"
    __table_args__ = (UniqueConstraint("diagnosis_id", "node_name", name="uq_diagnosis_node_name"),)

    id = Column(String(256), primary_key=True)
    diagnosis_id = Column(
        String(128), ForeignKey("diagnosis_sessions.id"), nullable=False, index=True,
    )
    node_name = Column(String(64), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False)
    attempt = Column(Integer, nullable=False, default=0)
    input_refs_json = Column(JSON, default=list)
    output_refs_json = Column(JSON, default=list)
    metrics_json = Column(JSON, default=dict)
    error_code = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)
    implementation_version = Column(String(64), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "node_run_id": self.id,
            "diagnosis_id": self.diagnosis_id,
            "node_name": self.node_name,
            "sequence": self.sequence,
            "status": self.status,
            "attempt": self.attempt,
            "input_refs": self.input_refs_json or [],
            "output_refs": self.output_refs_json or [],
            "metrics": self.metrics_json or {},
            "error_code": self.error_code,
            "error_message": self.error_message,
            "implementation_version": self.implementation_version,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "updated_at": self.updated_at,
        }


# ── Agent Runtime persistence (G1/G2) ──────────────────────────────


class AgentRuntimeBindingModel(Base):
    """Durable binding between a Case and a replaceable Agent Runtime session.

    The Sidecar/Pi session is in-memory and not authoritative.  This row lets
    Mini-Drop rebuild a snapshot and generation after a sidecar restart.
    """

    __tablename__ = "agent_runtime_bindings"
    __table_args__ = (
        UniqueConstraint("case_id", "tenant_id", name="uq_agent_runtime_binding_case"),
    )

    case_id = Column(String(128), primary_key=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    runtime_type = Column(String(32), nullable=False)
    runtime_version = Column(String(64), nullable=False)
    runtime_session_id = Column(String(128), nullable=False)
    runtime_generation = Column(Integer, nullable=False, default=1)
    deployment_epoch = Column(Integer, nullable=False, default=1, server_default="1")
    status = Column(String(32), nullable=False, default="READY")
    last_event_seq = Column(Integer, nullable=False, default=0)
    last_context_snapshot_id = Column(String(128), nullable=True)
    lease_owner = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "runtime_type": self.runtime_type,
            "runtime_version": self.runtime_version,
            "runtime_session_id": self.runtime_session_id,
            "runtime_generation": self.runtime_generation,
            "deployment_epoch": self.deployment_epoch,
            "status": self.status,
            "last_event_seq": self.last_event_seq,
            "last_context_snapshot_id": self.last_context_snapshot_id,
            "lease_owner": self.lease_owner,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class AgentRuntimeTurnModel(Base):
    """One user Turn submitted to an Agent Runtime (AcceptedTurn separated from completion)."""

    __tablename__ = "agent_runtime_turns"
    __table_args__ = (
        UniqueConstraint("case_id", "tenant_id", "turn_id", name="uq_agent_runtime_turn"),
        UniqueConstraint("idempotency_key", name="uq_agent_runtime_turn_idem"),
        Index("ix_agent_runtime_turns_idempotency_key", "idempotency_key"),
    )

    turn_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    runtime_session_id = Column(String(128), nullable=True)
    runtime_generation = Column(Integer, nullable=False, default=1)
    user_message = Column(Text, nullable=False)
    requested_mode = Column(String(40), nullable=True)
    disposition = Column(String(40), nullable=True)
    side_effect_policy = Column(String(24), nullable=True)
    actor_id = Column(String(128), nullable=True)
    client_command_id = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="ACCEPTED")
    accepted_mode = Column(String(32), nullable=False, default="deterministic")
    detail = Column(Text, nullable=True)
    idempotency_key = Column(String(128), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "turn_id": self.turn_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "runtime_session_id": self.runtime_session_id,
            "runtime_generation": self.runtime_generation,
            "user_message": self.user_message,
            "requested_mode": self.requested_mode,
            "disposition": self.disposition,
            "side_effect_policy": self.side_effect_policy,
            "actor_id": self.actor_id,
            "client_command_id": self.client_command_id,
            "status": self.status,
            "accepted_mode": self.accepted_mode,
            "detail": self.detail,
            "idempotency_key": self.idempotency_key,
            "completed_at": self.completed_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class AgentRuntimeEventModel(Base):
    """Normalized, replay-safe events emitted by an Agent Runtime.

    Private thinking is never persisted.  Event seq is unique within a
    generation so a sidecar restart/replay cannot duplicate a side effect.
    """

    __tablename__ = "agent_runtime_events"
    __table_args__ = (
        UniqueConstraint(
            "case_id", "tenant_id", "runtime_generation", "event_seq",
            name="uq_agent_runtime_event_seq",
        ),
        UniqueConstraint("idempotency_key", name="uq_agent_runtime_event_idem"),
        Index("ix_agent_runtime_events_idempotency_key", "idempotency_key"),
    )

    event_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    runtime_generation = Column(Integer, nullable=False, default=1)
    event_seq = Column(Integer, nullable=False)
    event_type = Column(String(64), nullable=False)
    cycle_id = Column(String(128), nullable=True, index=True)
    model_request_id = Column(String(128), nullable=True, index=True)
    evaluation_run_id = Column(String(128), nullable=True)
    payload_json = Column(JSON, nullable=False, default=dict)
    idempotency_key = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "runtime_generation": self.runtime_generation,
            "event_seq": self.event_seq,
            "event_type": self.event_type,
            "cycle_id": self.cycle_id,
            "model_request_id": self.model_request_id,
            "evaluation_run_id": self.evaluation_run_id,
            "payload": self.payload_json or {},
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at,
        }


class CaseEvidenceModel(Base):
    """Canonical per-Case Evidence record (G3).

    Attachment and legacy DiagnosisEvidence may project into this table, but
    only this table is consumed by conclusion validation and evidence-chain
    rendering.  Evidence IDs are deterministic from Task/Artifact provenance.
    """

    __tablename__ = "case_evidence"
    __table_args__ = (
        UniqueConstraint(
            "case_id", "tenant_id", "evidence_id", name="uq_case_evidence",
        ),
    )

    evidence_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    attachment_id = Column(String(128), nullable=True)
    task_id = Column(String(128), nullable=True, index=True)
    artifact_id = Column(Integer, nullable=True)
    artifact_type = Column(String(32), nullable=True)
    collector_id = Column(String(64), nullable=True)
    source_type = Column(String(32), nullable=False, default="task_artifact")
    source_channel = Column(String(24), nullable=False, default="COLLECTOR", server_default="COLLECTOR")
    data_origin = Column(String(24), nullable=False, default="LIVE", server_default="LIVE")
    investigation_run_id = Column(String(128), nullable=True, index=True)
    execution_unit_id = Column(String(128), nullable=True, index=True)
    source_call_id = Column(String(128), nullable=True)
    membership_snapshot_id = Column(String(128), nullable=True)
    target_ref = Column(String(256), nullable=True)
    resource_incarnation = Column(String(256), nullable=True)
    content_hash = Column(String(64), nullable=True)
    projection_hash = Column(String(64), nullable=True)
    status = Column(String(24), nullable=False, default="ACTIVE", index=True)
    quality = Column(String(20), nullable=False, default="UNKNOWN")
    freshness = Column(String(20), nullable=False, default="UNKNOWN")
    time_window_json = Column(JSON, nullable=False, default=dict)
    event_time_start = Column(DateTime(timezone=True), nullable=True)
    event_time_end = Column(DateTime(timezone=True), nullable=True)
    ingested_at = Column(DateTime(timezone=True), nullable=True)
    clock_id = Column(String(128), nullable=True)
    clock_offset_ms = Column(Integer, nullable=True)
    clock_uncertainty_ms = Column(Integer, nullable=True)
    artifact_schema = Column(String(64), nullable=True)
    schema_version = Column(String(32), nullable=True)
    producer_version = Column(String(64), nullable=True)
    raw_locator = Column(String(512), nullable=True)
    late_after_cancel = Column(Boolean, nullable=False, default=False, server_default="0")
    stale_for_current_revision = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "evidence_id": self.evidence_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "attachment_id": self.attachment_id,
            "task_id": self.task_id,
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "collector_id": self.collector_id,
            "source_type": self.source_type,
            "source_channel": self.source_channel,
            "data_origin": self.data_origin,
            "investigation_run_id": self.investigation_run_id,
            "execution_unit_id": self.execution_unit_id,
            "source_call_id": self.source_call_id,
            "membership_snapshot_id": self.membership_snapshot_id,
            "target_ref": self.target_ref,
            "resource_incarnation": self.resource_incarnation,
            "content_hash": self.content_hash,
            "projection_hash": self.projection_hash,
            "status": self.status,
            "quality": self.quality,
            "freshness": self.freshness,
            "time_window": self.time_window_json or {},
            "event_time_start": self.event_time_start,
            "event_time_end": self.event_time_end,
            "ingested_at": self.ingested_at,
            "clock_id": self.clock_id,
            "clock_offset_ms": self.clock_offset_ms,
            "clock_uncertainty_ms": self.clock_uncertainty_ms,
            "artifact_schema": self.artifact_schema,
            "schema_version": self.schema_version,
            "producer_version": self.producer_version,
            "raw_locator": self.raw_locator,
            "late_after_cancel": bool(self.late_after_cancel),
            "stale_for_current_revision": bool(self.stale_for_current_revision),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ── v6 canonical Agent core: Turn/Run/Cycle/Model/Proposal/Message ─────


class InvestigationRunModel(Base):
    """One Case business investigation run.  Distinct from evaluation_run_id."""

    __tablename__ = "investigation_runs"
    __table_args__ = (
        UniqueConstraint("case_id", "tenant_id", "run_id", name="uq_investigation_run"),
        ForeignKeyConstraint(
            ["case_id", "tenant_id"],
            ["incident_cases.id", "incident_cases.tenant_id"],
            name="fk_investigation_run_case_tenant",
            ondelete="CASCADE",
        ),
        Index("ix_investigation_runs_case_status", "case_id", "status"),
    )

    run_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="CREATED", index=True)
    scope_revision = Column(Integer, nullable=False, default=1)
    control_revision = Column(Integer, nullable=False, default=1)
    case_command_revision = Column(Integer, nullable=False, default=1)
    active_plan_revision = Column(Integer, nullable=False, default=0)
    evidence_watermark = Column(Integer, nullable=False, default=0)
    created_from_turn_id = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "status": self.status,
            "scope_revision": self.scope_revision,
            "control_revision": self.control_revision,
            "case_command_revision": self.case_command_revision,
            "active_plan_revision": self.active_plan_revision,
            "evidence_watermark": self.evidence_watermark,
            "created_from_turn_id": self.created_from_turn_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class CaseContextSnapshotModel(Base):
    __tablename__ = "case_context_snapshots"
    __table_args__ = (
        UniqueConstraint("case_id", "snapshot_id", name="uq_case_context_snapshot"),
    )

    snapshot_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    investigation_run_id = Column(String(128), nullable=True, index=True)
    case_command_revision = Column(Integer, nullable=False, default=1)
    control_revision = Column(Integer, nullable=False, default=1)
    scope_revision = Column(Integer, nullable=False, default=1)
    plan_revision = Column(Integer, nullable=False, default=0)
    campaign_revision = Column(Integer, nullable=False, default=0)
    evidence_watermark = Column(Integer, nullable=False, default=0)
    snapshot_hash = Column(String(128), nullable=False)
    content_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "investigation_run_id": self.investigation_run_id,
            "case_command_revision": self.case_command_revision,
            "control_revision": self.control_revision,
            "scope_revision": self.scope_revision,
            "plan_revision": self.plan_revision,
            "campaign_revision": self.campaign_revision,
            "evidence_watermark": self.evidence_watermark,
            "snapshot_hash": self.snapshot_hash,
            "content": self.content_json or {},
            "created_at": self.created_at,
        }


class AgentCycleModel(Base):
    __tablename__ = "agent_cycles"
    __table_args__ = (
        UniqueConstraint("case_id", "run_id", "cycle_id", name="uq_agent_cycle"),
    )

    cycle_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    run_id = Column(String(128), nullable=False, index=True)
    trigger_type = Column(String(32), nullable=False)
    trigger_ref = Column(String(128), nullable=True)
    trigger_turn_id = Column(String(128), nullable=True, index=True)
    origin_turn_id = Column(String(128), nullable=True, index=True)
    recovery_of_cycle_id = Column(String(128), nullable=True)
    context_snapshot_id = Column(String(128), nullable=True)
    evidence_watermark = Column(Integer, nullable=False, default=0)
    runtime_binding_id = Column(String(128), nullable=True)
    generation = Column(Integer, nullable=False, default=1)
    status = Column(String(32), nullable=False, default="QUEUED", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "cycle_id": self.cycle_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "run_id": self.run_id,
            "trigger_type": self.trigger_type,
            "trigger_ref": self.trigger_ref,
            "trigger_turn_id": self.trigger_turn_id,
            "origin_turn_id": self.origin_turn_id,
            "recovery_of_cycle_id": self.recovery_of_cycle_id,
            "context_snapshot_id": self.context_snapshot_id,
            "evidence_watermark": self.evidence_watermark,
            "runtime_binding_id": self.runtime_binding_id,
            "generation": self.generation,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ModelRequestModel(Base):
    __tablename__ = "model_requests"
    __table_args__ = (
        UniqueConstraint("case_id", "model_request_id", name="uq_model_request"),
        Index("ix_model_requests_cycle_status", "cycle_id", "status"),
    )

    model_request_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    run_id = Column(String(128), nullable=False, index=True)
    cycle_id = Column(String(128), nullable=False, index=True)
    provider_request_id = Column(String(128), nullable=True)
    idempotency_key = Column(String(128), nullable=True, unique=True, index=True)
    input_snapshot_hash = Column(String(128), nullable=True)
    evidence_projection_hashes = Column(JSON, nullable=False, default=list)
    status = Column(String(32), nullable=False, default="QUEUED", index=True)
    usage = Column(JSON, nullable=False, default=dict)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "model_request_id": self.model_request_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "run_id": self.run_id,
            "cycle_id": self.cycle_id,
            "provider_request_id": self.provider_request_id,
            "idempotency_key": self.idempotency_key,
            "input_snapshot_hash": self.input_snapshot_hash,
            "evidence_projection_hashes": self.evidence_projection_hashes or [],
            "status": self.status,
            "usage": self.usage or {},
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "created_at": self.created_at,
        }


class ModelResponseModel(Base):
    __tablename__ = "model_responses"
    __table_args__ = (
        UniqueConstraint("model_request_id", "idempotency_key", name="uq_model_response_idem"),
        UniqueConstraint("model_response_id", name="uq_model_response_id"),
    )

    model_response_id = Column(String(128), primary_key=True)
    model_request_id = Column(String(128), nullable=False, index=True)
    provider_request_id = Column(String(128), nullable=True)
    idempotency_key = Column(String(128), nullable=False)
    canonical_visible_content = Column(Text, nullable=False, default="")
    proposed_tool_calls = Column(JSON, nullable=False, default=list)
    response_hash = Column(String(128), nullable=False)
    durable_spool_offset = Column(BigInteger, nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "model_response_id": self.model_response_id,
            "model_request_id": self.model_request_id,
            "provider_request_id": self.provider_request_id,
            "idempotency_key": self.idempotency_key,
            "canonical_visible_content": self.canonical_visible_content,
            "proposed_tool_calls": self.proposed_tool_calls or [],
            "response_hash": self.response_hash,
            "durable_spool_offset": self.durable_spool_offset,
            "accepted_at": self.accepted_at,
        }


class AssistantMessageModel(Base):
    __tablename__ = "assistant_messages"
    __table_args__ = (
        UniqueConstraint("case_id", "message_id", name="uq_assistant_message"),
        Index("ix_assistant_messages_turn", "trigger_turn_id", "created_at"),
    )

    message_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    trigger_turn_id = Column(String(128), nullable=True)
    origin_turn_id = Column(String(128), nullable=True)
    cycle_id = Column(String(128), nullable=True, index=True)
    model_request_id = Column(String(128), nullable=True, index=True)
    content = Column(Text, nullable=False)
    evidence_refs = Column(JSON, nullable=False, default=list)
    limitation_refs = Column(JSON, nullable=False, default=list)
    conclusion_revision_id = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "trigger_turn_id": self.trigger_turn_id,
            "origin_turn_id": self.origin_turn_id,
            "cycle_id": self.cycle_id,
            "model_request_id": self.model_request_id,
            "content": self.content,
            "evidence_refs": self.evidence_refs or [],
            "limitation_refs": self.limitation_refs or [],
            "conclusion_revision_id": self.conclusion_revision_id,
            "created_at": self.created_at,
        }


class AgentProposalModel(Base):
    __tablename__ = "agent_proposals"
    __table_args__ = (
        UniqueConstraint("case_id", "proposal_id", name="uq_agent_proposal"),
    )

    proposal_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    object_type = Column(String(48), nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    validation_result = Column(JSON, nullable=False, default=dict)
    source_cycle_id = Column(String(128), nullable=True, index=True)
    status = Column(String(24), nullable=False, default="PROPOSED", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "object_type": self.object_type,
            "payload": self.payload or {},
            "validation_result": self.validation_result or {},
            "source_cycle_id": self.source_cycle_id,
            "status": self.status,
            "created_at": self.created_at,
            "decided_at": self.decided_at,
        }


class AgentDecisionRecordModel(Base):
    __tablename__ = "agent_decision_records"
    __table_args__ = (
        UniqueConstraint("cycle_id", "decision_id", name="uq_agent_decision"),
    )

    decision_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    cycle_id = Column(String(128), nullable=False, index=True)
    model_request_id = Column(String(128), nullable=False, index=True)
    observed_projection_hashes = Column(JSON, nullable=False, default=list)
    hypotheses = Column(JSON, nullable=False, default=list)
    opposing_evidence = Column(JSON, nullable=False, default=list)
    selected_missing_fact = Column(String(500), nullable=True)
    selection_reason = Column(Text, nullable=True)
    proposed_operation_or_action = Column(JSON, nullable=False, default=dict)
    alternatives_considered = Column(JSON, nullable=False, default=list)
    stop_reason = Column(String(64), nullable=True)
    provider_response_hash = Column(String(128), nullable=True)
    tool_call_ids = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "cycle_id": self.cycle_id,
            "model_request_id": self.model_request_id,
            "observed_projection_hashes": self.observed_projection_hashes or [],
            "hypotheses": self.hypotheses or [],
            "opposing_evidence": self.opposing_evidence or [],
            "selected_missing_fact": self.selected_missing_fact,
            "selection_reason": self.selection_reason,
            "proposed_operation_or_action": self.proposed_operation_or_action or {},
            "alternatives_considered": self.alternatives_considered or [],
            "stop_reason": self.stop_reason,
            "provider_response_hash": self.provider_response_hash,
            "tool_call_ids": self.tool_call_ids or [],
            "created_at": self.created_at,
        }


# ── v6 Evidence projection / review / durable wake ───────────────────


class EvidenceProjectionModel(Base):
    __tablename__ = "evidence_projections"
    __table_args__ = (
        UniqueConstraint("evidence_id", "projection_kind", "projection_version", name="uq_evidence_projection"),
        Index("ix_evidence_projections_evidence", "evidence_id"),
    )

    projection_id = Column(String(128), primary_key=True)
    evidence_id = Column(String(128), nullable=False, index=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    projection_kind = Column(String(32), nullable=False)
    projection_schema = Column(String(64), nullable=False, default="evidence-projection.v1")
    projection_version = Column(Integer, nullable=False, default=1)
    content_json = Column(JSON, nullable=False, default=dict)
    projection_hash = Column(String(128), nullable=False)
    truncated = Column(Boolean, nullable=False, default=False)
    source_bytes = Column(Integer, nullable=False, default=0)
    projected_bytes = Column(Integer, nullable=False, default=0)
    parser_version = Column(String(64), nullable=False, default="deterministic.v1")
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "projection_id": self.projection_id,
            "evidence_id": self.evidence_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "projection_kind": self.projection_kind,
            "projection_schema": self.projection_schema,
            "projection_version": self.projection_version,
            "content": self.content_json or {},
            "projection_hash": self.projection_hash,
            "truncated": bool(self.truncated),
            "source_bytes": self.source_bytes,
            "projected_bytes": self.projected_bytes,
            "parser_version": self.parser_version,
            "created_at": self.created_at,
        }


class EvidenceReviewRevisionModel(Base):
    __tablename__ = "evidence_review_revisions"
    __table_args__ = (
        UniqueConstraint("evidence_id", "review_revision", name="uq_evidence_review_revision"),
    )

    review_revision_id = Column(String(128), primary_key=True)
    evidence_id = Column(String(128), nullable=False, index=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    review_revision = Column(Integer, nullable=False, default=1)
    decision = Column(String(24), nullable=False)
    reason = Column(Text, nullable=True)
    reviewed_by = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "review_revision_id": self.review_revision_id,
            "evidence_id": self.evidence_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "review_revision": self.review_revision,
            "decision": self.decision,
            "reason": self.reason,
            "reviewed_by": self.reviewed_by,
            "created_at": self.created_at,
        }


class DomainOutboxModel(Base):
    __tablename__ = "domain_outbox"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_domain_outbox_dedupe"),
        Index("ix_domain_outbox_status_available", "status", "available_at"),
    )

    outbox_id = Column(String(128), primary_key=True)
    aggregate_type = Column(String(64), nullable=False)
    aggregate_id = Column(String(128), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    dedupe_key = Column(String(128), nullable=False)
    status = Column(String(24), nullable=False, default="PENDING", index=True)
    available_at = Column(DateTime(timezone=True), nullable=False)
    claim_token = Column(String(128), nullable=True)
    claimed_by = Column(String(128), nullable=True)
    claim_expires_at = Column(DateTime(timezone=True), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    dispatch_outcome = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "outbox_id": self.outbox_id,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "event_type": self.event_type,
            "payload": self.payload or {},
            "dedupe_key": self.dedupe_key,
            "status": self.status,
            "available_at": self.available_at,
            "claim_token": self.claim_token,
            "claimed_by": self.claimed_by,
            "claim_expires_at": self.claim_expires_at,
            "attempts": self.attempts,
            "last_error": self.last_error,
            "dispatch_outcome": self.dispatch_outcome,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class RuntimeWakeupModel(Base):
    __tablename__ = "runtime_wakeups"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_runtime_wakeup_dedupe"),
    )

    wakeup_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    investigation_run_id = Column(String(128), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    source_refs = Column(JSON, nullable=False, default=list)
    control_revision = Column(Integer, nullable=False, default=1)
    scope_revision = Column(Integer, nullable=False, default=1)
    reason_class = Column(String(32), nullable=False)
    from_evidence_watermark = Column(Integer, nullable=False, default=0)
    to_evidence_watermark = Column(Integer, nullable=False, default=0)
    status = Column(String(24), nullable=False, default="PENDING", index=True)
    claim_token = Column(String(128), nullable=True)
    claim_expires_at = Column(DateTime(timezone=True), nullable=True)
    dedupe_key = Column(String(128), nullable=False)
    sealed_at = Column(DateTime(timezone=True), nullable=True)
    sealed_to_evidence_watermark = Column(Integer, nullable=True)
    cycle_id = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "wakeup_id": self.wakeup_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "investigation_run_id": self.investigation_run_id,
            "reason": self.reason,
            "source_refs": self.source_refs or [],
            "control_revision": self.control_revision,
            "scope_revision": self.scope_revision,
            "reason_class": self.reason_class,
            "from_evidence_watermark": self.from_evidence_watermark,
            "to_evidence_watermark": self.to_evidence_watermark,
            "status": self.status,
            "claim_token": self.claim_token,
            "claim_expires_at": self.claim_expires_at,
            "dedupe_key": self.dedupe_key,
            "sealed_at": self.sealed_at,
            "sealed_to_evidence_watermark": self.sealed_to_evidence_watermark,
            "cycle_id": self.cycle_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class RuntimeWakeupSourceModel(Base):
    __tablename__ = "runtime_wakeup_sources"
    __table_args__ = (
        UniqueConstraint("outbox_id", name="uq_runtime_wakeup_source_outbox"),
    )

    wakeup_id = Column(String(128), nullable=False, primary_key=True)
    outbox_id = Column(String(128), nullable=False, index=True)
    source_ref = Column(String(256), nullable=False)
    evidence_watermark = Column(Integer, nullable=False, default=0)
    mapped_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "wakeup_id": self.wakeup_id,
            "outbox_id": self.outbox_id,
            "source_ref": self.source_ref,
            "evidence_watermark": self.evidence_watermark,
            "mapped_at": self.mapped_at,
        }


# ── v6 Plan / Campaign / Execution domain ───────────────────────────


class OperationSpecModel(Base):
    __tablename__ = "operation_specs"
    __table_args__ = (
        UniqueConstraint("operation_id", "version", name="uq_operation_spec"),
    )

    operation_id = Column(String(128), primary_key=True)
    version = Column(String(32), nullable=False, default="v1")
    execution_kind = Column(String(24), nullable=False)
    backend_ref = Column(String(128), nullable=False)
    description = Column(Text, nullable=False, default="")
    supported_target_types = Column(JSON, nullable=False, default=list)
    parameters_schema = Column(JSON, nullable=False, default=dict)
    evidence_schema = Column(JSON, nullable=False, default=dict)
    required_capabilities = Column(JSON, nullable=False, default=list)
    capability_version = Column(String(32), nullable=True)
    risk = Column(String(24), nullable=False, default="READ_LOW")
    timeout_sec = Column(Integer, nullable=False, default=30)
    max_output_bytes = Column(Integer, nullable=False, default=1048576)
    parser_version = Column(String(64), nullable=True)
    renderer_hash = Column(String(128), nullable=True)
    cache_ttl = Column(Integer, nullable=False, default=0)
    fingerprint_fields = Column(JSON, nullable=False, default=list)
    enabled = Column(Boolean, nullable=False, default=True)
    auto_allowed = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "operation_id": self.operation_id,
            "version": self.version,
            "execution_kind": self.execution_kind,
            "backend_ref": self.backend_ref,
            "description": self.description,
            "supported_target_types": self.supported_target_types or [],
            "parameters_schema": self.parameters_schema or {},
            "evidence_schema": self.evidence_schema or {},
            "required_capabilities": self.required_capabilities or [],
            "capability_version": self.capability_version,
            "risk": self.risk,
            "timeout_sec": self.timeout_sec,
            "max_output_bytes": self.max_output_bytes,
            "parser_version": self.parser_version,
            "renderer_hash": self.renderer_hash,
            "cache_ttl": self.cache_ttl,
            "fingerprint_fields": self.fingerprint_fields or [],
            "enabled": bool(self.enabled),
            "auto_allowed": bool(self.auto_allowed),
            "updated_at": self.updated_at,
        }


class CampaignRevisionModel(Base):
    __tablename__ = "campaign_revisions"
    __table_args__ = (
        UniqueConstraint("campaign_id", "revision", name="uq_campaign_revision"),
    )

    campaign_id = Column(String(128), primary_key=True)
    revision = Column(Integer, nullable=False, default=1)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    plan_step_revision_id = Column(String(128), nullable=True)
    membership_snapshot_id = Column(String(128), nullable=True)
    coverage_policy = Column(String(64), nullable=False, default="REQUIRED_ALL")
    status = Column(String(24), nullable=False, default="DRAFT", index=True)
    common_baseline_assignment_ids = Column(JSON, nullable=False, default=list)
    differential_assignment_ids = Column(JSON, nullable=False, default=list)
    actor = Column(String(24), nullable=False, default="USER")
    created_by = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "campaign_id": self.campaign_id,
            "revision": self.revision,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "plan_step_revision_id": self.plan_step_revision_id,
            "membership_snapshot_id": self.membership_snapshot_id,
            "coverage_policy": self.coverage_policy,
            "status": self.status,
            "common_baseline_assignment_ids": self.common_baseline_assignment_ids or [],
            "differential_assignment_ids": self.differential_assignment_ids or [],
            "actor": self.actor,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class AcquisitionAssignmentModel(Base):
    __tablename__ = "acquisition_assignments"
    __table_args__ = (
        UniqueConstraint("campaign_id", "assignment_id", name="uq_acquisition_assignment"),
    )

    assignment_id = Column(String(128), primary_key=True)
    campaign_id = Column(String(128), nullable=False, index=True)
    campaign_revision = Column(Integer, nullable=False, default=1)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    role = Column(String(64), nullable=True)
    operation_ref = Column(String(128), nullable=False)
    target_selector = Column(JSON, nullable=False, default=dict)
    parameters = Column(JSON, nullable=False, default=dict)
    requested_window = Column(JSON, nullable=False, default=dict)
    required_fact_ids = Column(JSON, nullable=False, default=list)
    risk = Column(String(24), nullable=False, default="READ_LOW")
    priority = Column(Integer, nullable=False, default=50)
    depends_on = Column(JSON, nullable=False, default=list)
    required_coverage = Column(Integer, nullable=False, default=1)
    status = Column(String(24), nullable=False, default="PLANNED")
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "assignment_id": self.assignment_id,
            "campaign_id": self.campaign_id,
            "campaign_revision": self.campaign_revision,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "role": self.role,
            "operation_ref": self.operation_ref,
            "target_selector": self.target_selector or {},
            "parameters": self.parameters or {},
            "requested_window": self.requested_window or {},
            "required_fact_ids": self.required_fact_ids or [],
            "risk": self.risk,
            "priority": self.priority,
            "depends_on": self.depends_on or [],
            "required_coverage": self.required_coverage,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ExecutionUnitModel(Base):
    __tablename__ = "execution_units"
    __table_args__ = (
        UniqueConstraint("assignment_id", "resource_ref", "fingerprint", name="uq_execution_unit_fingerprint"),
        UniqueConstraint("task_id", name="uq_execution_unit_task"),
        UniqueConstraint("source_call_id", name="uq_execution_unit_source_call"),
        Index("ix_execution_units_case_status", "case_id", "status"),
    )

    execution_unit_id = Column(String(128), primary_key=True)
    assignment_id = Column(String(128), nullable=False, index=True)
    campaign_id = Column(String(128), nullable=False, index=True)
    campaign_revision = Column(Integer, nullable=False, default=1)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    resource_ref = Column(String(256), nullable=False)
    operation_id = Column(String(128), nullable=False)
    operation_version = Column(String(32), nullable=False, default="v1")
    normalized_parameters = Column(JSON, nullable=False, default=dict)
    evaluation_run_id = Column(String(128), nullable=True)
    deployment_epoch = Column(Integer, nullable=False, default=1)
    control_revision = Column(Integer, nullable=False, default=1)
    scope_revision = Column(Integer, nullable=False, default=1)
    plan_revision = Column(Integer, nullable=False, default=0)
    fingerprint = Column(String(128), nullable=False)
    status = Column(String(24), nullable=False, default="PLANNED", index=True)
    task_id = Column(String(128), nullable=True)
    source_call_id = Column(String(128), nullable=True)
    cancel_epoch = Column(Integer, nullable=True)
    cancel_command_id = Column(String(128), nullable=True)
    cancel_requested_at = Column(DateTime(timezone=True), nullable=True)
    terminal_result_status = Column(String(24), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "execution_unit_id": self.execution_unit_id,
            "assignment_id": self.assignment_id,
            "campaign_id": self.campaign_id,
            "campaign_revision": self.campaign_revision,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "resource_ref": self.resource_ref,
            "operation_id": self.operation_id,
            "operation_version": self.operation_version,
            "normalized_parameters": self.normalized_parameters or {},
            "evaluation_run_id": self.evaluation_run_id,
            "deployment_epoch": self.deployment_epoch,
            "control_revision": self.control_revision,
            "scope_revision": self.scope_revision,
            "plan_revision": self.plan_revision,
            "fingerprint": self.fingerprint,
            "status": self.status,
            "task_id": self.task_id,
            "source_call_id": self.source_call_id,
            "cancel_epoch": self.cancel_epoch,
            "cancel_command_id": self.cancel_command_id,
            "cancel_requested_at": self.cancel_requested_at,
            "terminal_result_status": self.terminal_result_status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ── v6 Causal / Gap / Conclusion / Repair ───────────────────────────


class CausalGraphRevisionModel(Base):
    __tablename__ = "causal_graph_revisions"
    __table_args__ = (
        UniqueConstraint("case_id", "graph_revision", name="uq_causal_graph_revision"),
    )

    graph_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    investigation_run_id = Column(String(128), nullable=True, index=True)
    graph_revision = Column(Integer, nullable=False, default=1)
    evidence_watermark = Column(Integer, nullable=False, default=0)
    status = Column(String(24), nullable=False, default="PROPOSED")
    model_proposed_json = Column(JSON, nullable=False, default=dict)
    verifier_json = Column(JSON, nullable=False, default=dict)
    verifier_version = Column(String(64), nullable=True)
    created_from_cycle_id = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "graph_id": self.graph_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "investigation_run_id": self.investigation_run_id,
            "graph_revision": self.graph_revision,
            "evidence_watermark": self.evidence_watermark,
            "status": self.status,
            "model_proposed": self.model_proposed_json or {},
            "verifier": self.verifier_json or {},
            "verifier_version": self.verifier_version,
            "created_from_cycle_id": self.created_from_cycle_id,
            "created_at": self.created_at,
        }


class CausalNodeModel(Base):
    __tablename__ = "causal_nodes"
    __table_args__ = (
        UniqueConstraint("graph_id", "node_id", name="uq_causal_node"),
    )

    node_id = Column(String(128), primary_key=True)
    graph_id = Column(String(128), nullable=False, index=True)
    case_id = Column(String(128), nullable=False, index=True)
    entity_ref = Column(String(256), nullable=False)
    mechanism = Column(Text, nullable=False)
    role = Column(String(40), nullable=False, default="SYMPTOM")
    model_proposed_role = Column(String(40), nullable=True)
    verifier_role = Column(String(40), nullable=True)
    onset_start = Column(DateTime(timezone=True), nullable=True)
    onset_end = Column(DateTime(timezone=True), nullable=True)
    supporting_evidence_refs = Column(JSON, nullable=False, default=list)
    opposing_evidence_refs = Column(JSON, nullable=False, default=list)
    confidence = Column(Float, nullable=False, default=0.0)
    role_rationale = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "graph_id": self.graph_id,
            "case_id": self.case_id,
            "entity_ref": self.entity_ref,
            "mechanism": self.mechanism,
            "role": self.role,
            "model_proposed_role": self.model_proposed_role,
            "verifier_role": self.verifier_role,
            "onset_start": self.onset_start,
            "onset_end": self.onset_end,
            "supporting_evidence_refs": self.supporting_evidence_refs or [],
            "opposing_evidence_refs": self.opposing_evidence_refs or [],
            "confidence": self.confidence,
            "role_rationale": self.role_rationale,
            "created_at": self.created_at,
        }


class CausalEdgeModel(Base):
    __tablename__ = "causal_edges"
    __table_args__ = (
        UniqueConstraint("graph_id", "edge_id", name="uq_causal_edge"),
    )

    edge_id = Column(String(128), primary_key=True)
    graph_id = Column(String(128), nullable=False, index=True)
    case_id = Column(String(128), nullable=False, index=True)
    source_node_id = Column(String(128), nullable=False)
    target_node_id = Column(String(128), nullable=False)
    relation = Column(String(32), nullable=False, default="CAUSES")
    model_proposed_relation = Column(String(32), nullable=True)
    verifier_relation = Column(String(32), nullable=True)
    mechanism = Column(Text, nullable=True)
    expected_lag = Column(String(64), nullable=True)
    observed_lag = Column(String(64), nullable=True)
    topology_path_refs = Column(JSON, nullable=False, default=list)
    supporting_evidence_refs = Column(JSON, nullable=False, default=list)
    knowledge_refs = Column(JSON, nullable=False, default=list)
    verification_state = Column(String(24), nullable=False, default="UNVERIFIED")
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "graph_id": self.graph_id,
            "case_id": self.case_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "relation": self.relation,
            "model_proposed_relation": self.model_proposed_relation,
            "verifier_relation": self.verifier_relation,
            "mechanism": self.mechanism,
            "expected_lag": self.expected_lag,
            "observed_lag": self.observed_lag,
            "topology_path_refs": self.topology_path_refs or [],
            "supporting_evidence_refs": self.supporting_evidence_refs or [],
            "knowledge_refs": self.knowledge_refs or [],
            "verification_state": self.verification_state,
            "created_at": self.created_at,
        }


class EvidenceGapModel(Base):
    __tablename__ = "evidence_gaps"
    __table_args__ = (
        UniqueConstraint("case_id", "gap_id", name="uq_evidence_gap"),
    )

    gap_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    investigation_run_id = Column(String(128), nullable=True, index=True)
    blocked_claim = Column(Text, nullable=True)
    required_fact = Column(Text, nullable=False)
    attempted_execution = Column(String(128), nullable=True)
    target = Column(String(256), nullable=True)
    requested_time_window = Column(JSON, nullable=False, default=dict)
    status = Column(String(24), nullable=False, default="OPEN", index=True)
    reason_code = Column(String(48), nullable=False)
    raw_error_ref = Column(String(128), nullable=True)
    observed_evidence = Column(JSON, nullable=False, default=list)
    what_it_supports = Column(Text, nullable=True)
    what_it_does_not_support = Column(Text, nullable=True)
    conflicting_evidence_refs = Column(JSON, nullable=False, default=list)
    retryable = Column(Boolean, nullable=False, default=False)
    next_best_action = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "gap_id": self.gap_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "investigation_run_id": self.investigation_run_id,
            "blocked_claim": self.blocked_claim,
            "required_fact": self.required_fact,
            "attempted_execution": self.attempted_execution,
            "target": self.target,
            "requested_time_window": self.requested_time_window or {},
            "status": self.status,
            "reason_code": self.reason_code,
            "raw_error_ref": self.raw_error_ref,
            "observed_evidence": self.observed_evidence or [],
            "what_it_supports": self.what_it_supports,
            "what_it_does_not_support": self.what_it_does_not_support,
            "conflicting_evidence_refs": self.conflicting_evidence_refs or [],
            "retryable": bool(self.retryable),
            "next_best_action": self.next_best_action,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }


class ConclusionRevisionModel(Base):
    __tablename__ = "conclusion_revisions"
    __table_args__ = (
        UniqueConstraint("case_id", "revision", name="uq_conclusion_revision"),
    )

    conclusion_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    investigation_run_id = Column(String(128), nullable=False, index=True)
    revision = Column(Integer, nullable=False, default=1)
    state = Column(String(32), nullable=False, default="PARTIALLY_CONFIRMED")
    primary_root_causes = Column(JSON, nullable=False, default=list)
    ranked_primary_candidates = Column(JSON, nullable=False, default=list)
    contributing_factors = Column(JSON, nullable=False, default=list)
    amplifiers = Column(JSON, nullable=False, default=list)
    propagated_effects = Column(JSON, nullable=False, default=list)
    symptoms = Column(JSON, nullable=False, default=list)
    coincidental_anomalies = Column(JSON, nullable=False, default=list)
    ruled_out = Column(JSON, nullable=False, default=list)
    causal_graph_revision_id = Column(String(128), nullable=True)
    claims = Column(JSON, nullable=False, default=list)
    evidence_gap_ids = Column(JSON, nullable=False, default=list)
    recommendation_ids = Column(JSON, nullable=False, default=list)
    limitations = Column(JSON, nullable=False, default=list)
    abstention_reason = Column(Text, nullable=True)
    report_text = Column(Text, nullable=True)
    created_from_cycle_id = Column(String(128), nullable=True)
    model_request_id = Column(String(128), nullable=True)
    verifier_version = Column(String(64), nullable=False, default="causal-report-verifier.v1")
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "conclusion_id": self.conclusion_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "investigation_run_id": self.investigation_run_id,
            "revision": self.revision,
            "state": self.state,
            "primary_root_causes": self.primary_root_causes or [],
            "ranked_primary_candidates": self.ranked_primary_candidates or [],
            "contributing_factors": self.contributing_factors or [],
            "amplifiers": self.amplifiers or [],
            "propagated_effects": self.propagated_effects or [],
            "symptoms": self.symptoms or [],
            "coincidental_anomalies": self.coincidental_anomalies or [],
            "ruled_out": self.ruled_out or [],
            "causal_graph_revision_id": self.causal_graph_revision_id,
            "claims": self.claims or [],
            "evidence_gap_ids": self.evidence_gap_ids or [],
            "recommendation_ids": self.recommendation_ids or [],
            "limitations": self.limitations or [],
            "abstention_reason": self.abstention_reason,
            "report_text": self.report_text,
            "created_from_cycle_id": self.created_from_cycle_id,
            "model_request_id": self.model_request_id,
            "verifier_version": self.verifier_version,
            "created_at": self.created_at,
        }


class ClaimEvidenceBindingModel(Base):
    __tablename__ = "claim_evidence_bindings"
    __table_args__ = (
        UniqueConstraint("conclusion_id", "claim_id", "evidence_id", name="uq_claim_evidence_binding"),
    )

    claim_id = Column(String(128), primary_key=True)
    conclusion_id = Column(String(128), nullable=False, index=True)
    evidence_id = Column(String(128), nullable=False, index=True)
    projection_hash = Column(String(128), nullable=False)
    field_path = Column(String(256), nullable=True)
    extractor_id = Column(String(128), nullable=True)
    extractor_version = Column(String(32), nullable=True)
    extractor_hash = Column(String(128), nullable=True)
    target_ref = Column(String(256), nullable=True)
    resource_incarnation = Column(String(256), nullable=True)
    event_window = Column(JSON, nullable=False, default=dict)
    predicate = Column(JSON, nullable=False, default=dict)
    observed_value = Column(JSON, nullable=False, default=dict)
    support_kind = Column(String(16), nullable=False, default="SUPPORTS")
    verifier_result = Column(String(24), nullable=False, default="PENDING")
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "conclusion_id": self.conclusion_id,
            "evidence_id": self.evidence_id,
            "projection_hash": self.projection_hash,
            "field_path": self.field_path,
            "extractor_id": self.extractor_id,
            "extractor_version": self.extractor_version,
            "extractor_hash": self.extractor_hash,
            "target_ref": self.target_ref,
            "resource_incarnation": self.resource_incarnation,
            "event_window": self.event_window or {},
            "predicate": self.predicate or {},
            "observed_value": self.observed_value or {},
            "support_kind": self.support_kind,
            "verifier_result": self.verifier_result,
            "created_at": self.created_at,
        }


class RepairRecommendationModel(Base):
    __tablename__ = "repair_recommendations"
    __table_args__ = (
        UniqueConstraint("case_id", "recommendation_id", name="uq_repair_recommendation"),
    )

    recommendation_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    conclusion_id = Column(String(128), nullable=True, index=True)
    cause_or_edge_ref = Column(String(128), nullable=False)
    category = Column(String(32), nullable=False)
    target = Column(String(256), nullable=False)
    concrete_action = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    evidence_refs = Column(JSON, nullable=False, default=list)
    prerequisites = Column(JSON, nullable=False, default=list)
    risk = Column(String(24), nullable=True)
    approval = Column(String(24), nullable=True)
    expected_effect = Column(Text, nullable=True)
    verification_operations = Column(JSON, nullable=False, default=list)
    success_criteria = Column(JSON, nullable=False, default=list)
    rollback_or_failure_condition = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False, default=0.0)
    limitations = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "recommendation_id": self.recommendation_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "conclusion_id": self.conclusion_id,
            "cause_or_edge_ref": self.cause_or_edge_ref,
            "category": self.category,
            "target": self.target,
            "concrete_action": self.concrete_action,
            "rationale": self.rationale,
            "evidence_refs": self.evidence_refs or [],
            "prerequisites": self.prerequisites or [],
            "risk": self.risk,
            "approval": self.approval,
            "expected_effect": self.expected_effect,
            "verification_operations": self.verification_operations or [],
            "success_criteria": self.success_criteria or [],
            "rollback_or_failure_condition": self.rollback_or_failure_condition,
            "confidence": self.confidence,
            "limitations": self.limitations or [],
            "created_at": self.created_at,
        }


class DeploymentAssessmentModel(Base):
    __tablename__ = "deployment_assessments"
    __table_args__ = (
        UniqueConstraint("case_id", "assessment_id", name="uq_deployment_assessment"),
    )

    assessment_id = Column(String(128), primary_key=True)
    case_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    verdict = Column(String(24), nullable=False)
    summary = Column(Text, nullable=False)
    requirements_json = Column(JSON, nullable=False, default=dict)
    eligible_nodes = Column(JSON, nullable=False, default=list)
    rejected_nodes = Column(JSON, nullable=False, default=list)
    missing_inputs = Column(JSON, nullable=False, default=list)
    assumptions = Column(JSON, nullable=False, default=list)
    evidence_refs = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "assessment_id": self.assessment_id,
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "verdict": self.verdict,
            "summary": self.summary,
            "requirements": self.requirements_json or {},
            "eligible_nodes": self.eligible_nodes or [],
            "rejected_nodes": self.rejected_nodes or [],
            "missing_inputs": self.missing_inputs or [],
            "assumptions": self.assumptions or [],
            "evidence_refs": self.evidence_refs or [],
            "created_at": self.created_at,
        }


# ── Monotonic CaseEvent sequence ─────────────────────────────────────
# case_event_seq is assigned inside the insert transaction so historical and
# future event writers share one cursor.  It is intentionally not a client
# default: the next value must be computed from the same table snapshot.
@event.listens_for(CaseEventModel, "before_insert")
def _assign_case_event_seq(mapper, connection, target) -> None:
    if target.case_event_seq is not None:
        return
    current = connection.execute(
        select(func.max(CaseEventModel.case_event_seq)).where(
            CaseEventModel.case_id == target.case_id,
            CaseEventModel.tenant_id == target.tenant_id,
        )
    ).scalar()
    target.case_event_seq = int(current or 0) + 1
