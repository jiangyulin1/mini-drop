"""Lightweight process resource sampling for Agent heartbeats."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass


@dataclass
class _Snapshot:
    monotonic_ts: float
    cpu_seconds: float
    read_bytes: int
    write_bytes: int


class ProcessStatsSampler:
    def __init__(self, pid: int | None = None) -> None:
        self.pid = pid or os.getpid()
        self._clock_ticks = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
        self._page_size = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096
        self._last_self: _Snapshot | None = None

    def sample_self(self) -> dict:
        stat = _read_proc_stat(self.pid, self._clock_ticks, self._page_size)
        io = _read_proc_io(self.pid)
        current = _Snapshot(time.monotonic(), stat["cpu_seconds"], io["read_bytes"], io["write_bytes"])
        rates = _rates(self._last_self, current)
        self._last_self = current
        return {
            "cpu_percent": rates["cpu_percent"],
            "rss_mb": stat["rss_mb"],
            "read_kb_s": rates["read_kb_s"],
            "write_kb_s": rates["write_kb_s"],
            "children_count": 0,
        }

    def sample_children(self) -> dict:
        pids = _child_pids(self.pid)
        rss_mb = 0.0
        for pid in pids:
            rss_mb += _read_proc_stat(pid, self._clock_ticks, self._page_size)["rss_mb"]
        return {
            "cpu_percent": 0.0,
            "rss_mb": round(rss_mb, 3),
            "read_kb_s": 0.0,
            "write_kb_s": 0.0,
            "children_count": len(pids),
        }


def _rates(previous: _Snapshot | None, current: _Snapshot) -> dict:
    if previous is None:
        return {"cpu_percent": 0.0, "read_kb_s": 0.0, "write_kb_s": 0.0}
    elapsed = max(current.monotonic_ts - previous.monotonic_ts, 0.001)
    return {
        "cpu_percent": round(max(0.0, (current.cpu_seconds - previous.cpu_seconds) / elapsed * 100), 3),
        "read_kb_s": round(max(0, current.read_bytes - previous.read_bytes) / elapsed / 1024, 3),
        "write_kb_s": round(max(0, current.write_bytes - previous.write_bytes) / elapsed / 1024, 3),
    }


def _read_proc_stat(pid: int, clock_ticks: int, page_size: int) -> dict:
    try:
        with open(f"/proc/{pid}/stat", "r", encoding="utf-8") as fh:
            data = fh.read()
        end = data.rfind(")")
        fields = data[end + 2 :].split()
        utime = int(fields[11])
        stime = int(fields[12])
        rss_pages = int(fields[21])
        return {
            "cpu_seconds": (utime + stime) / clock_ticks,
            "rss_mb": round(max(0, rss_pages) * page_size / 1024 / 1024, 3),
        }
    except (OSError, ValueError, IndexError):
        return {"cpu_seconds": 0.0, "rss_mb": 0.0}


def _read_proc_io(pid: int) -> dict:
    result = {"read_bytes": 0, "write_bytes": 0}
    try:
        with open(f"/proc/{pid}/io", "r", encoding="utf-8") as fh:
            for line in fh:
                key, _, value = line.partition(":")
                if key == "read_bytes":
                    result["read_bytes"] = int(value.strip())
                elif key == "write_bytes":
                    result["write_bytes"] = int(value.strip())
    except (OSError, ValueError):
        pass
    return result


def _child_pids(parent_pid: int) -> list[int]:
    try:
        proc_entries = os.listdir("/proc")
    except OSError:
        return []
    children: list[int] = []
    for entry in proc_entries:
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat", "r", encoding="utf-8") as fh:
                data = fh.read()
            end = data.rfind(")")
            fields = data[end + 2 :].split()
            if int(fields[1]) == parent_pid:
                children.append(int(entry))
        except (OSError, ValueError, IndexError):
            continue
    return children
