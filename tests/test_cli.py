"""micro-drop CLI tests."""

import json

from server.app import cli


def test_ai_config_prints_provider(monkeypatch, capsys):
    monkeypatch.setenv("MINI_DROP_AI_PROVIDER", "test-provider")
    monkeypatch.setenv("MINI_DROP_AI_BASE_URL", "https://ai.example.com")
    monkeypatch.setenv("MINI_DROP_AI_MODEL", "m1")
    code = cli.main(["ai-config"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["provider"] == "test-provider"
    assert out["model"] == "m1"


def test_parse_uses_rule_fallback_without_key(monkeypatch, capsys):
    monkeypatch.setenv("MINI_DROP_AI_ENABLED", "none")
    code = cli.main(["parse", "mysqld", "CPU", "飙高"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["collector_type"] == "perf_cpu"
    assert out["process_name"] == "mysqld"


def test_diff_top_returns_nonzero_on_threshold(tmp_path, capsys):
    base = tmp_path / "base.json"
    head = tmp_path / "head.json"
    base.write_text('[{"name":"fib","percent":10.0}]', encoding="utf-8")
    head.write_text('[{"name":"fib","percent":20.0}]', encoding="utf-8")
    code = cli.main([
        "diff-top", "--base", str(base), "--head", str(head), "--threshold", "5",
    ])
    out = json.loads(capsys.readouterr().out)
    assert code == 2
    assert out["failed"] is True
    assert out["changes"][0]["delta_percent"] == 10.0
