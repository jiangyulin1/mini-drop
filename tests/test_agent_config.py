"""Agent 配置加载单元测试。"""

from dataclasses import FrozenInstanceError

import pytest

from agent.mini_drop_agent.config import load_config
from agent.mini_drop_agent.main import CAPABILITIES, COLLECTORS, _run_collector


class TestAgentConfig:
    """配置文件从环境变量读取。"""

    def _clean_env(self, monkeypatch):
        for key in ("AGENT_ID", "AGENT_GRPC_ADDR", "AGENT_IP_ADDR", "AGENT_HEARTBEAT_INTERVAL_SEC"):
            monkeypatch.delenv(key, raising=False)

    def test_default_config(self, monkeypatch):
        self._clean_env(monkeypatch)
        cfg = load_config()
        assert cfg.agent_id == "agent_local_demo"
        assert cfg.server_grpc_addr == "localhost:50051"
        assert cfg.agent_ip_addr
        assert cfg.heartbeat_interval_sec == 5

    def test_custom_agent_id(self, monkeypatch):
        self._clean_env(monkeypatch)
        monkeypatch.setenv("AGENT_ID", "agent_ubuntu_01")
        cfg = load_config()
        assert cfg.agent_id == "agent_ubuntu_01"

    def test_custom_grpc_addr(self, monkeypatch):
        self._clean_env(monkeypatch)
        monkeypatch.setenv("AGENT_GRPC_ADDR", "192.168.1.100:50051")
        cfg = load_config()
        assert cfg.server_grpc_addr == "192.168.1.100:50051"

    def test_custom_agent_ip(self, monkeypatch):
        self._clean_env(monkeypatch)
        monkeypatch.setenv("AGENT_IP_ADDR", "10.0.0.20")
        cfg = load_config()
        assert cfg.agent_ip_addr == "10.0.0.20"

    def test_custom_heartbeat_interval(self, monkeypatch):
        self._clean_env(monkeypatch)
        monkeypatch.setenv("AGENT_HEARTBEAT_INTERVAL_SEC", "10")
        cfg = load_config()
        assert cfg.heartbeat_interval_sec == 10

    def test_config_is_frozen(self, monkeypatch):
        self._clean_env(monkeypatch)
        cfg = load_config()
        with pytest.raises(FrozenInstanceError):
            cfg.agent_id = "hacked"


class TestAgentCollectorDispatch:
    """Agent 任务执行入口。"""

    def test_capabilities_match_registered_collectors(self):
        assert CAPABILITIES == sorted(COLLECTORS.keys())
        assert CAPABILITIES == ["continuous_perf", "ebpf_io", "perf_cpu", "pyspy"]

    def test_unregistered_collector_reports_failure_without_artifact(self):
        ok, reason, artifacts = _run_collector({
            "id": "task_001",
            "collector_type": "nonexistent_collector",
        })
        assert ok is False
        assert "未在此 Agent 构建中注册" in reason
        assert artifacts == []
