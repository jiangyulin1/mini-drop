"""CPU 热点演示进程。

运行后持续执行三类计算密集型操作：
  - fib_hotspot：递归 Fibonacci（深度 25，栈特征明显）
  - sort_hotspot：大列表排序（内存密集）
  - json_hotspot：JSON 编解码（序列化/反序列化热点）

每 60 秒切换一次负载类型，供 perf / py-spy / continuous 采集验证。
启动后打印 PID，方便在 Web 上创建任务时填写。
"""

from __future__ import annotations

import json
import os
import random
import time


def fib_hotspot(n: int = 25) -> int:
    """递归 Fibonacci，perf 火焰图中最深栈的贡献者。"""
    if n <= 1:
        return n
    return fib_hotspot(n - 1) + fib_hotspot(n - 2)


def sort_hotspot() -> int:
    """大列表排序，触发内存分配和比较函数热点。"""
    values = [random.randint(0, 1_000_000) for _ in range(20_000)]
    values.sort()
    return values[-1]


def json_hotspot() -> int:
    """JSON 编解码，触发序列化/反序列化 CPU 热点。"""
    payload = [{"index": item, "value": str(item) * 3} for item in range(5_000)]
    encoded = json.dumps(payload)
    decoded = json.loads(encoded)
    return len(decoded)


def main() -> None:
    print(f"cpu_hotspot pid={os.getpid()}", flush=True)
    stages = [fib_hotspot, sort_hotspot, json_hotspot]
    index = 0
    while True:
        stage = stages[index % len(stages)]
        started = time.time()
        while time.time() - started < 60:
            if stage is fib_hotspot:
                stage(25)
            else:
                stage()
        index += 1


if __name__ == "__main__":
    main()
