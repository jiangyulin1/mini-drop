"""NLP 意图解析：DeepSeek function calling 将自然语言映射为任务参数。

LLM 只能调用 create_profiling_task 这个预定义 function，
输出通过 Pydantic 校验 + 参数边界 clamp 后才返回。
"""

from __future__ import annotations

import json
import os

import requests

from server.app.nlp.tool_schemas import CREATE_PROFILING_TASK_SCHEMA, NLP_SYSTEM_PROMPT

API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# 参数硬约束（不受 LLM 输出影响）
CLAMP_DURATION = (5, 120)
CLAMP_SAMPLE_RATE = (1, 999)
VALID_COLLECTORS = {"perf_cpu", "ebpf_io", "pyspy", "continuous_perf"}


class StructuredIntent:
    """解析后的结构化意图。"""

    def __init__(
        self, process_name: str, collector_type: str, duration_sec: int,
        sample_rate: int, reasoning: str, raw_llm_output: dict | None = None,
    ):
        self.process_name = process_name
        self.collector_type = collector_type
        self.duration_sec = duration_sec
        self.sample_rate = sample_rate
        self.reasoning = reasoning
        self.raw_llm_output = raw_llm_output or {}

    def to_dict(self) -> dict:
        return {
            "process_name": self.process_name,
            "collector_type": self.collector_type,
            "duration_sec": self.duration_sec,
            "sample_rate": self.sample_rate,
            "reasoning": self.reasoning,
        }


def parse_intent(user_input: str) -> StructuredIntent:
    """将用户自然语言输入解析为结构化意图。

    Args:
        user_input: 用户自然语言描述，如 "mysqld CPU 飙高，帮我看看"

    Returns:
        StructuredIntent

    如果 API Key 未配置，返回基于关键词的保守匹配。
    """
    if not API_KEY or not _get_api_key():
        return _keyword_fallback(user_input.strip())

    messages = [
        {"role": "system", "content": NLP_SYSTEM_PROMPT},
        {"role": "user", "content": user_input.strip()},
    ]

    try:
        resp = requests.post(
            f"{API_BASE}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {_get_api_key()}",
                "Content-Type": "application/json",
            },
            json={
                "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 512,
                "tools": [{
                    "type": "function",
                    "function": CREATE_PROFILING_TASK_SCHEMA,
                }],
                "tool_choice": {"type": "function", "function": {"name": "create_profiling_task"}},
            },
            timeout=20,
        )

        if resp.status_code != 200:
            return _keyword_fallback(user_input.strip())

        body = resp.json()
        tool_calls = body.get("choices", [{}])[0].get("message", {}).get("tool_calls", [])

        if not tool_calls:
            return _keyword_fallback(user_input.strip())

        args_str = tool_calls[0].get("function", {}).get("arguments", "{}")
        args = json.loads(args_str) if isinstance(args_str, str) else args_str

        return _clamp_and_validate(args)

    except Exception:
        return _keyword_fallback(user_input.strip())


def _get_api_key() -> str:
    return API_KEY


def _clamp_and_validate(args: dict) -> StructuredIntent:
    """将 LLM 输出的参数 clamp 到安全范围内。"""
    collector = args.get("collector_type", "perf_cpu")
    if collector not in VALID_COLLECTORS:
        collector = "perf_cpu"

    duration = int(args.get("duration_sec", 15))
    duration = max(CLAMP_DURATION[0], min(CLAMP_DURATION[1], duration))

    sample_rate = int(args.get("sample_rate", 99))
    sample_rate = max(CLAMP_SAMPLE_RATE[0], min(CLAMP_SAMPLE_RATE[1], sample_rate))

    process = args.get("process_name", "unknown")
    reasoning = args.get("reasoning", f"自然语言解析：{collector} 采集 {process}，{duration}s {sample_rate}Hz")

    return StructuredIntent(
        process_name=process,
        collector_type=collector,
        duration_sec=duration,
        sample_rate=sample_rate,
        reasoning=reasoning,
        raw_llm_output=args,
    )


def _keyword_fallback(text: str) -> StructuredIntent:
    """基于关键词的保守匹配（无 API Key 时使用）。

    关键词按优先级排序——先检查更具体的采集器关键词，
    CPU 类关键词作为最后兜底，避免通用词吞掉专用匹配。
    """
    text_lower = text.lower()

    # 按优先级检测：continuous > pyspy > ebpf > perf_cpu（兜底）
    if any(kw in text_lower for kw in ("持续", "监控", "长期", "趋势", "continuous")):
        collector = "continuous_perf"
        reason = "关键词匹配：持续/监控相关描述 → continuous_perf"
    elif any(kw in text_lower for kw in ("python", "django", "flask", "pytorch")):
        collector = "pyspy"
        reason = "关键词匹配：Python 相关描述 → py-spy"
    elif any(kw in text_lower for kw in ("磁盘", "io", "读写", "存储")):
        collector = "ebpf_io"
        reason = "关键词匹配：IO/磁盘相关描述 → ebpf_io"
    elif any(kw in text_lower for kw in ("cpu", "热点", "卡顿", "慢", "飙高", "高负载")):
        collector = "perf_cpu"
        reason = "关键词匹配：CPU 相关描述 → perf_cpu"
    else:
        collector = "perf_cpu"
        reason = "未匹配到明确关键词，保守选择 perf_cpu"

    # 尝试从文本中提取进程名
    process = _extract_process_name(text)

    return StructuredIntent(
        process_name=process,
        collector_type=collector,
        duration_sec=15,
        sample_rate=99,
        reasoning=reason,
    )


def _extract_process_name(text: str) -> str:
    """从自然语言文本中提取可能的进程名。"""
    import re
    # 常见进程名模式：字母、数字、下划线、点、短横
    candidates = re.findall(r'\b([a-zA-Z][\w.-]{1,30})\b', text)
    # 过滤掉明显不是进程名的词
    skip = {"cpu", "io", "慢", "卡顿", "python", "帮我", "看看", "一下",
            "the", "this", "and", "for", "with", "帮我看看", "怎么回事"}
    for c in candidates:
        if c.lower() not in skip:
            return c
    return "unknown"