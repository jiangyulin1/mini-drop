import json

from server.app.logging_utils import log_event


def test_server_log_event_writes_json(capsys):
    log_event("info", "http_request", method="GET", path="/api/healthz", status_code=200)

    captured = capsys.readouterr()
    record = json.loads(captured.out)

    assert record["level"] == "info"
    assert record["event"] == "http_request"
    assert record["method"] == "GET"
    assert record["status_code"] == 200


def test_server_warning_log_uses_stderr(capsys):
    log_event("warning", "slow_request", path="/api/tasks")

    captured = capsys.readouterr()
    record = json.loads(captured.err)

    assert record["level"] == "warning"
    assert record["event"] == "slow_request"
