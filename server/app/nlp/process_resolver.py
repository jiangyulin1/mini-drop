"""进程名 → PID 解析。

通过 /proc 文件系统查找匹配进程，返回候选 PID 列表供用户确认。
不做在 LLM 里——LLM 不知道系统上运行什么进程。
"""

from __future__ import annotations

import os


class ProcessMatch:
    """一个匹配到的进程。"""

    def __init__(self, pid: int, comm: str = "", cmdline: str = ""):
        self.pid = pid
        self.comm = comm
        self.cmdline = cmdline

    def to_dict(self) -> dict:
        return {"pid": self.pid, "comm": self.comm, "cmdline": self.cmdline}


def resolve_pid(process_name: str, limit: int = 10) -> list[ProcessMatch]:
    """在 /proc 中查找进程名匹配的进程，返回 PID 列表。

    Args:
        process_name: 目标进程名（模糊匹配）。
        limit: 最多返回多少候选。

    Returns:
        ProcessMatch 列表，每个包含 pid/comm/cmdline。
    """
    if not os.path.isdir("/proc"):
        return []

    matches: list[ProcessMatch] = []
    name_lower = process_name.lower()

    try:
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            pid = int(entry)
            proc_dir = f"/proc/{entry}"

            try:
                # 读取 comm（短进程名，最多 15 字符）
                comm_path = os.path.join(proc_dir, "comm")
                comm = ""
                try:
                    with open(comm_path, "r") as fh:
                        comm = fh.read().strip()
                except (PermissionError, FileNotFoundError):
                    pass

                # 读取 cmdline（完整命令行）
                cmdline = ""
                try:
                    with open(os.path.join(proc_dir, "cmdline"), "rb") as fh:
                        raw = fh.read()
                        # 兼容 mock: raw 可能是 str 或 bytes
                        if isinstance(raw, bytes):
                            raw = raw.replace(b"\x00", b" ")
                        cmdline = raw.decode("utf-8", errors="replace").strip() if isinstance(raw, bytes) else raw.strip()
                except (PermissionError, FileNotFoundError):
                    pass

                # 匹配：comm 或 cmdline 中包含目标进程名
                if name_lower in comm.lower() or name_lower in cmdline.lower():
                    matches.append(ProcessMatch(pid=pid, comm=comm, cmdline=cmdline))
                    if len(matches) >= limit:
                        break
            except (PermissionError, OSError):
                continue
    except OSError:
        pass

    return matches
