import json

from agent.mini_drop_agent.logging_utils import log_event


def test_log_event_writes_json(capsys):
    log_event("info", "task_completed", task_id="task_1", artifact_count=2)

    captured = capsys.readouterr()
    record = json.loads(captured.out)

    assert record["level"] == "info"
    assert record["event"] == "task_completed"
    assert record["task_id"] == "task_1"
    assert record["artifact_count"] == 2
    assert "ts" in record


def test_error_log_uses_stderr(capsys):
    log_event("error", "heartbeat_failed", code="UNAVAILABLE")

    captured = capsys.readouterr()
    record = json.loads(captured.err)

    assert record["level"] == "error"
    assert record["event"] == "heartbeat_failed"
