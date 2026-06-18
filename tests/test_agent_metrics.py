from agent.mini_drop_agent.metrics import ProcessStatsSampler


def test_process_stats_sampler_handles_missing_proc(monkeypatch):
    monkeypatch.setattr("agent.mini_drop_agent.metrics._read_proc_stat", lambda *_args: {"cpu_seconds": 0.0, "rss_mb": 0.0})
    monkeypatch.setattr("agent.mini_drop_agent.metrics._read_proc_io", lambda *_args: {"read_bytes": 0, "write_bytes": 0})
    monkeypatch.setattr("agent.mini_drop_agent.metrics._child_pids", lambda *_args: [])

    sampler = ProcessStatsSampler(pid=123)

    assert sampler.sample_self()["rss_mb"] == 0.0
    assert sampler.sample_children()["children_count"] == 0
