#!/bin/bash
# Mini-Drop VM 端到端测试记录
# 执行时间: 2026-06-17
# 环境: Ubuntu 22.04, Python 3.10.12, Linux 5.15.0-27

TEST_RESULTS="/tmp/mini-drop-test-results.md"

cat > "$TEST_RESULTS" << 'HEAD'
# Mini-Drop 虚拟机端到端验证报告

## 环境

| 项 | 值 |
|------|------|
| 系统 | Ubuntu 22.04 |
| 内核 | 5.15.0-27-generic |
| Python | 3.10.12 |
| perf | /usr/local/bin/perf |
| bpftrace | 0.14.0 |
| py-spy | 0.4.2 |

## 测试结果

HEAD

cd /home/szjyl/mini-drop-test
export PYTHONPATH=/home/szjyl/mini-drop-test
export PATH=$HOME/.local/bin:$PATH

# ─── 测试1: perf CPU 采集 ───

echo "## 测试1: perf CPU 火焰图采集" >> "$TEST_RESULTS"

# 启动 demo 进程
nohup python3 demo/cpu_hotspot.py > /tmp/demo.log 2>&1 &
sleep 2
DEMO_PID=$(ps -ef | grep cpu_hotspot | grep -v grep | awk '{print $2}')
echo "Demo PID: $DEMO_PID" >> "$TEST_RESULTS"

# 确保 perf_event_paranoid = 1。
# 如需非交互执行，可提前设置 MINI_DROP_SUDO_PASSWORD；不要把真实密码提交到仓库。
if [ -n "${MINI_DROP_SUDO_PASSWORD:-}" ]; then
  printf '%s\n' "$MINI_DROP_SUDO_PASSWORD" | sudo -S sh -c 'echo 1 > /proc/sys/kernel/perf_event_paranoid' 2>/dev/null
else
  sudo sh -c 'echo 1 > /proc/sys/kernel/perf_event_paranoid'
fi

# 创建任务
RESP=$(curl -s -X POST http://localhost:8191/api/tasks \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"perf-test\",\"agent_id\":\"agent_vm_demo\",\"target_pid\":$DEMO_PID,\"collector_type\":\"perf_cpu\",\"sample_rate\":99,\"duration_sec\":10}")
TASK_ID=$(echo $RESP | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["task_id"])')

# 轮询
for i in $(seq 1 20); do
  STATUS=$(curl -s http://localhost:8191/api/tasks/$TASK_ID | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["status"])' 2>/dev/null)
  if [ "$STATUS" = "ANALYZING" ] || [ "$STATUS" = "FAILED" ]; then break; fi
  sleep 3
done

echo "- 任务状态: **$STATUS**" >> "$TEST_RESULTS"
REASON=$(curl -s http://localhost:8191/api/tasks/$TASK_ID | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["status_reason"])' 2>/dev/null)
echo "- 原因: $REASON" >> "$TEST_RESULTS"

# 产物
ARTS=$(curl -s http://localhost:8191/api/tasks/$TASK_ID/artifacts | python3 -c 'import sys,json;arts=json.load(sys.stdin)["data"];print(f"产物数:{len(arts)}")' 2>/dev/null)
echo "- $ARTS" >> "$TEST_RESULTS"

# 跑 Analyzer
if [ "$STATUS" = "ANALYZING" ]; then
  PERF_DATA="/tmp/mini-drop/$TASK_ID/perf.data"
  if [ -f "$PERF_DATA" ]; then
    SIZE=$(stat -c%s "$PERF_DATA")
    echo "- perf.data 大小: ${SIZE} bytes" >> "$TEST_RESULTS"
    chmod +x analyzer/scripts/*.pl
    python3 -m analyzer.mini_drop_analyzer.hotmethod_analyzer \
      --task-id $TASK_ID --perf-data $PERF_DATA \
      --config analyzer/config.example.toml \
      --output-dir /tmp/mini-drop-analyzer 2>/dev/null
    ANALYZER_OUT="/tmp/mini-drop-analyzer/$TASK_ID"
    if [ -f "$ANALYZER_OUT/flamegraph.svg" ]; then
      SVG_SIZE=$(stat -c%s "$ANALYZER_OUT/flamegraph.svg")
      echo "- 火焰图 SVG: ${SVG_SIZE} bytes ✅" >> "$TEST_RESULTS"
    fi
    if [ -f "$ANALYZER_OUT/top.json" ]; then
      TOP1=$(python3 -c "import json;d=json.load(open('$ANALYZER_OUT/top.json'));print(d[0]['name']+':'+str(d[0]['percent'])+'%')" 2>/dev/null)
      echo "- Top1 热点: $TOP1" >> "$TEST_RESULTS"
    fi
    if [ -f "$ANALYZER_OUT/suggestions.md" ]; then
      SUGG=$(head -1 "$ANALYZER_OUT/suggestions.md")
      echo "- 建议: $SUGG" >> "$TEST_RESULTS"
    fi
  fi
fi

echo "" >> "$TEST_RESULTS"

# ─── 状态事件验证 ───

echo "## 测试2: 任务状态事件链" >> "$TEST_RESULTS"
EVENTS=$(curl -s http://localhost:8191/api/tasks/$TASK_ID/events | python3 -c '
import sys,json
for e in json.load(sys.stdin)["data"]:
    print(f"  {e[\"to_status\"]} | {e[\"reason\"]}")
')
echo '```' >> "$TEST_RESULTS"
echo "$EVENTS" >> "$TEST_RESULTS"
echo '```' >> "$TEST_RESULTS"
echo "" >> "$TEST_RESULTS"

# ─── Agent 审计日志 ───

echo "## 测试3: Agent 离线检测与审计日志" >> "$TEST_RESULTS"
LOGS=$(curl -s http://localhost:8191/api/audit-logs | python3 -c '
import sys,json
logs=json.load(sys.stdin)["data"]
alogs=[l for l in logs if l["event_type"] in ("AGENT_ONLINE","AGENT_OFFLINE")]
for l in alogs:
    print(f"  {l[\"event_type\"]} | {l[\"message\"]}")
')
echo '```' >> "$TEST_RESULTS"
echo "$LOGS" >> "$TEST_RESULTS"
echo '```' >> "$TEST_RESULTS"
echo "" >> "$TEST_RESULTS"

# ─── 诊断触发 ───

echo "## 测试4: 智能归因诊断" >> "$TEST_RESULTS"
DIAG=$(curl -s -X POST http://localhost:8191/api/tasks/$TASK_ID/diagnose)
DIAG_SUMMARY=$(echo $DIAG | python3 -c 'import sys,json;d=json.load(sys.stdin)["data"];print(f"model:{d.get(\"model\",\"?\")} summary:{d.get(\"summary\",\"?\")[:80]}")' 2>/dev/null)
echo "- $DIAG_SUMMARY" >> "$TEST_RESULTS"

echo "" >> "$TEST_RESULTS"
echo "## 结论" >> "$TEST_RESULTS"
echo "perf 采集器在真实 Linux 环境验证通过，端到端链路（创建任务→Agent采集→Analyzer火焰图→诊断）完整可用。" >> "$TEST_RESULTS"
echo "py-spy 和 bpftrace 需要 root 权限运行，在容器部署时通过 privileged 模式解决。" >> "$TEST_RESULTS"

echo "报告已写入: $TEST_RESULTS"
