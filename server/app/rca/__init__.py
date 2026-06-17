"""Mini-Drop 智能归因模块。

5 层架构：
  1. 证据层 (evidence.py)   — 结构化证据采集
  2. 候选归因 (candidates.py) — 规则引擎自动匹配
  3. 置信度校准 (calibrator.py) — 五维加权评分
  4. LLM 推理 (llm_client.py) — DeepSeek API + schema 注入 + few-shot
  5. 反馈闭环 (commit 18+ 扩展)

使用入口:
  from server.app.rca.report import run_diagnosis
  report = run_diagnosis(task_id, task_record, top_functions=top, ...)
"""

from server.app.rca.report import run_diagnosis

__all__ = ["run_diagnosis"]
