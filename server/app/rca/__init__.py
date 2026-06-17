"""Mini-Drop 智能归因模块。

7 层架构：
  1. 证据层 (evidence.py)   — 结构化证据采集
  2. 工具层 (tools.py)       — 只读工具执行，结果进入证据链
  3. 候选归因 (candidates.py) — 规则引擎自动匹配
  4. 置信度校准 (calibrator.py) — 多维加权评分 + 反馈先验
  5. LLM 推理 (llm_client.py) — DeepSeek API + schema 注入 + few-shot
  6. 修复计划 (repair.py)    — safe_auto 自动执行，风险动作只建议
  7. 反馈闭环               — 反馈写入 DB 并校准后续置信度

使用入口:
  from server.app.rca.report import run_diagnosis
  report = run_diagnosis(task_id, task_record, top_functions=top, ...)
"""

from server.app.rca.report import run_diagnosis

__all__ = ["run_diagnosis"]
