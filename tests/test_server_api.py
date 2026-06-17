"""HTTP API 测试。

通过 FastAPI TestClient 验证各 REST 端点，
测试使用独立 repo 实例避免与 gRPC 测试共享状态。

注意：TestClient 会触发 FastAPI startup 事件尝试启动 gRPC server。
50051 端口被占用时 gRPC 启动失败不影响 HTTP 端点功能，
测试在 setUp 中直接清理 repo 状态。
"""

import pytest
from fastapi.testclient import TestClient

from server.app import storage as store
from server.app.database import init_db, reset_engine
from server.app.main import app, repo
from server.app.models import Base
from server.app.state_machine import Actor, TaskStatus


@pytest.fixture(autouse=True)
def _reset_repo(monkeypatch):
    """每个测试使用独立 SQLite 内存库，确保用例间无状态交叉。"""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    reset_engine()
    init_db()
    repo._task_queues.clear()
    repo.register_agent("agent_local_demo", "demo-host", "10.0.0.10")
    repo.register_agent("a1", "agent-one", "10.0.0.11")
    repo.register_agent("a2", "agent-two", "10.0.0.12")
    repo.register_agent("a3", "agent-three", "10.0.0.13")
    yield
    from server.app.database import _get_engine
    Base.metadata.drop_all(bind=_get_engine())
    reset_engine()


@pytest.fixture(name="client")
def client_fixture():
    """提供预配置的 TestClient 实例。"""
    return TestClient(app)


class TestHealthz:
    """健康与用户信息端点。"""

    def test_healthz_returns_service_info(self, client: TestClient):
        resp = client.get("/api/healthz")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["service"] == "mini-drop-server"

    def test_me_returns_demo_user(self, client: TestClient):
        resp = client.get("/api/me")
        assert resp.status_code == 200
        assert resp.json()["data"]["user_id"] == "demo_user"


class TestCreateTask:
    """任务创建端点。"""

    def test_create_task_records_pending_status(self, client: TestClient):
        resp = client.post("/api/tasks", json={
            "name": "demo cpu profile",
            "agent_id": "agent_local_demo",
            "target_pid": 1234,
            "collector_type": "perf_cpu",
            "sample_rate": 99,
            "duration_sec": 10,
        })
        assert resp.status_code == 200
        body = resp.json()
        task_id = body["data"]["task_id"]
        assert body["data"]["status"] == "PENDING"

        # 通过详情端点确认
        detail = client.get(f"/api/tasks/{task_id}")
        assert detail.json()["data"]["status"] == "PENDING"

    def test_create_task_writes_status_event(self, client: TestClient):
        resp = client.post("/api/tasks", json={
            "name": "test", "agent_id": "a1",
            "target_pid": 1, "collector_type": "perf_cpu",
        })
        task_id = resp.json()["data"]["task_id"]
        events = client.get(f"/api/tasks/{task_id}/events").json()["data"]
        assert len(events) >= 1
        assert events[0]["to_status"] == "PENDING"
        assert events[0]["reason"] == "Web 请求创建任务"

    def test_create_task_writes_audit_log(self, client: TestClient):
        client.post("/api/tasks", json={
            "name": "test", "agent_id": "a2",
            "target_pid": 1, "collector_type": "perf_cpu",
        })
        logs = client.get("/api/audit-logs").json()["data"]
        assert any(log["event_type"] == "TASK_CREATED" for log in logs)

    def test_rejects_zero_duration(self, client: TestClient):
        resp = client.post("/api/tasks", json={
            "name": "bad", "agent_id": "a1",
            "target_pid": 1, "collector_type": "perf_cpu",
            "duration_sec": 0,
        })
        assert resp.status_code == 400

    def test_rejects_negative_sample_rate(self, client: TestClient):
        resp = client.post("/api/tasks", json={
            "name": "bad", "agent_id": "a1",
            "target_pid": 1, "collector_type": "perf_cpu",
            "sample_rate": -1,
        })
        assert resp.status_code == 400

    def test_rejects_unknown_agent(self, client: TestClient):
        resp = client.post("/api/tasks", json={
            "name": "bad-agent", "agent_id": "missing_agent",
            "target_pid": 1, "collector_type": "perf_cpu",
        })
        assert resp.status_code == 404


class TestTaskListAndDetail:
    """任务列表与详情端点。"""

    def test_list_returns_empty_initially(self, client: TestClient):
        resp = client.get("/api/tasks")
        assert resp.json()["data"]["total"] == 0

    def test_list_returns_created_tasks(self, client: TestClient):
        client.post("/api/tasks", json={
            "name": "task1", "agent_id": "a1",
            "target_pid": 1, "collector_type": "perf_cpu",
        })
        client.post("/api/tasks", json={
            "name": "task2", "agent_id": "a1",
            "target_pid": 2, "collector_type": "ebpf_io",
        })
        resp = client.get("/api/tasks")
        assert resp.json()["data"]["total"] == 2

    def test_detail_returns_full_fields(self, client: TestClient):
        resp = client.post("/api/tasks", json={
            "name": "detail-test", "agent_id": "a3",
            "target_pid": 9999, "collector_type": "pyspy",
            "sample_rate": 11, "duration_sec": 5,
        })
        task_id = resp.json()["data"]["task_id"]
        detail = client.get(f"/api/tasks/{task_id}").json()["data"]
        assert detail["name"] == "detail-test"
        assert detail["target_pid"] == 9999
        assert detail["collector_type"] == "pyspy"
        assert detail["sample_rate"] == 11
        assert detail["duration_sec"] == 5

    def test_nonexistent_task_returns_404(self, client: TestClient):
        resp = client.get("/api/tasks/nonexistent")
        assert resp.status_code == 404


class TestTaskEvents:
    """状态迁移事件端点。"""

    def test_events_are_returned_in_order(self, client: TestClient):
        resp = client.post("/api/tasks", json={
            "name": "events-test", "agent_id": "a1",
            "target_pid": 1, "collector_type": "perf_cpu",
        })
        task_id = resp.json()["data"]["task_id"]

        # 手动推进两步
        repo.transition_task(task_id, TaskStatus.RUNNING, "heartbeat", Actor.SERVER)
        repo.transition_task(task_id, TaskStatus.UPLOADING, "done collecting", Actor.AGENT)

        events = client.get(f"/api/tasks/{task_id}/events").json()["data"]
        statuses = [e["to_status"] for e in events]
        assert statuses == ["PENDING", "RUNNING", "UPLOADING"]

    def test_events_404_for_nonexistent_task(self, client: TestClient):
        resp = client.get("/api/tasks/does-not-exist/events")
        assert resp.status_code == 404


class TestTaskArtifacts:
    """产物查询端点。"""

    def test_empty_artifacts_for_new_task(self, client: TestClient):
        resp = client.post("/api/tasks", json={
            "name": "art-test", "agent_id": "a1",
            "target_pid": 1, "collector_type": "perf_cpu",
        })
        task_id = resp.json()["data"]["task_id"]
        arts = client.get(f"/api/tasks/{task_id}/artifacts").json()["data"]
        assert arts == []

    def test_artifacts_after_result_report(self, client: TestClient):
        resp = client.post("/api/tasks", json={
            "name": "art2", "agent_id": "a1",
            "target_pid": 1, "collector_type": "perf_cpu",
        })
        task_id = resp.json()["data"]["task_id"]
        repo.add_artifacts(task_id, [{"artifact_type": "raw", "bucket": "mini-drop", "object_key": "tasks/x/perf.data"}])
        arts = client.get(f"/api/tasks/{task_id}/artifacts").json()["data"]
        assert len(arts) == 1
        assert arts[0]["artifact_type"] == "raw"


class TestStoragePresign:
    """对象存储预签名 URL 端点。"""

    def test_presign_returns_url(self, client: TestClient, monkeypatch):
        monkeypatch.setattr(
            store,
            "presigned_get_url",
            lambda bucket, key, expires: "http://minio:9000/mini-drop/artifact.svg",
        )
        resp = client.get("/api/storage/presign", params={
            "bucket": "mini-drop",
            "key": "tasks/demo/flamegraph.svg",
            "expires": 600,
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["url"].startswith("http://minio:9000")

    def test_presign_rejects_empty_key(self, client: TestClient):
        resp = client.get("/api/storage/presign", params={"bucket": "mini-drop"})
        assert resp.status_code == 400

    def test_presign_rejects_invalid_expires(self, client: TestClient):
        resp = client.get("/api/storage/presign", params={
            "bucket": "mini-drop",
            "key": "tasks/demo/flamegraph.svg",
            "expires": 0,
        })
        assert resp.status_code == 400


class TestDiagnose:
    """诊断触发端点。"""

    def test_diagnose_enqueues_report(self, client: TestClient):
        resp = client.post("/api/tasks", json={
            "name": "diag", "agent_id": "a1",
            "target_pid": 1, "collector_type": "perf_cpu",
        })
        task_id = resp.json()["data"]["task_id"]
        diag = client.post(f"/api/tasks/{task_id}/diagnose").json()["data"]
        assert diag["diagnosis_id"].startswith("diag_")
        assert diag["report_id"].startswith("report_")
        assert diag["task_id"] == task_id
        assert "summary" in diag
        assert "ranked_causes" in diag
        assert "model" in diag
        assert len(diag["tool_results"]) >= 1
        assert diag["repair_plan"]["plan_id"].startswith("repair_")

        detail = client.get(f"/api/diagnoses/{diag['diagnosis_id']}").json()["data"]
        assert detail["run"]["task_id"] == task_id
        assert len(detail["tool_results"]) >= 1
        history = client.get(f"/api/tasks/{task_id}/diagnoses").json()["data"]
        assert history[0]["id"] == diag["diagnosis_id"]

        feedback = client.post(
            f"/api/diagnoses/{diag['diagnosis_id']}/feedback",
            json={
                "predicted_cause_id": "insufficient_data",
                "feedback_label": "partial",
                "feedback_note": "需要更多证据",
            },
        )
        assert feedback.status_code == 200
        assert feedback.json()["data"]["feedback_saved"] is True

    def test_diagnose_404_for_nonexistent(self, client: TestClient):
        resp = client.post("/api/tasks/nope/diagnose")
        assert resp.status_code == 404

    def test_diagnosis_detail_404_for_nonexistent(self, client: TestClient):
        resp = client.get("/api/diagnoses/diag_missing")
        assert resp.status_code == 404
