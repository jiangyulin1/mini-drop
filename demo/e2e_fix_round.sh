#!/bin/bash
# Quick fix test: memory_smaps + sys_metrics + pyspy
set -e
export PATH=$HOME/.local/bin:$PATH
cd ~/mini-drop-new
fuser -k 50051/tcp 2>/dev/null || true
fuser -k 8191/tcp 2>/dev/null || true
sleep 1

export MINI_DROP_API_AUTH_ENABLED=0 MINI_DROP_GRPC_AUTH_ENABLED=0 MINIO_AUTO_CREATE_BUCKET=0
export AGENT_ID=test_agent AGENT_GRPC_ADDR=localhost:50051 AGENT_UPLOAD_ARTIFACTS=0

run() {
  local scene="$1" collector="$2" dur="$3" label="$4"
  echo ""
  echo "===== $label ($collector) ====="
  python3 -m server.app.main &
  SPID=$!; sleep 3
  echo "312q" | sudo -S -E env PATH=$PATH python3 -m agent.mini_drop_agent.main &
  APID=$!; sleep 4
  python3 demo/vm_test_targets.py "$scene" $((dur+10>30?dur+10:30)) &
  TARGET=$!; sleep 2
  R=$(curl -s -X POST http://localhost:8191/api/tasks \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$label\",\"agent_id\":\"test_agent\",\"target_pid\":$TARGET,\"collector_type\":\"$collector\",\"sample_rate\":99,\"duration_sec\":$dur}")
  TID=$(echo "$R" | python3 -c "import json,sys;print(json.load(sys.stdin)['data']['task_id'])")
  echo "  task=$TID"
  for i in $(seq 1 45); do
    S=$(curl -s http://localhost:8191/api/tasks/$TID | python3 -c "import json,sys;print(json.load(sys.stdin)['data']['status'])" 2>/dev/null || echo '?')
    if [ $i -le 2 ] || [ "$S" = "DONE" ] || [ "$S" = "FAILED" ]; then echo "  [$i] $S"; fi
    if [ "$S" = "DONE" ] || [ "$S" = "FAILED" ]; then break; fi
    sleep 1
  done
  A=$(curl -s http://localhost:8191/api/tasks/$TID/artifacts | python3 -c "import json,sys;d=json.load(sys.stdin);print([a['artifact_type'] for a in d['data']['items']])" 2>/dev/null || echo '?')
  echo "  artifacts=$A"
  ls /tmp/mini-drop/$TID/ 2>/dev/null
  case "$collector" in
    memory_smaps)
      python3 -c "import json;d=json.load(open('/tmp/mini-drop/$TID/memory_profile.json'));print(f'  RSS: {d[\"first_rss_mb\"]}->{d[\"last_rss_mb\"]}MB trend={d[\"trend\"]} samples={d[\"sample_count\"]}')" 2>/dev/null || true
      ;;
    sys_metrics)
      python3 -c "import json;d=json.load(open('/tmp/mini-drop/$TID/sys_metrics.json'));s=d['summary'];print(f'  threads={s[\"thread_count\"]} trend={s[\"thread_trend\"]} fd={s[\"fd_count\"]} ctx_nvol={s[\"ctx_nonvoluntary_rate\"]}/s net={s[\"net_rx_kbps\"]}KB/s')" 2>/dev/null || true
      ;;
    pyspy)
      ls -la /tmp/mini-drop/$TID/flamegraph.svg 2>/dev/null && echo "  SVG: $(wc -c < /tmp/mini-drop/$TID/flamegraph.svg) bytes" || true
      ;;
  esac
  kill $TARGET 2>/dev/null; sudo kill $APID 2>/dev/null; kill $SPID 2>/dev/null; wait 2>/dev/null
  sleep 2
  fuser -k 50051/tcp 2>/dev/null; fuser -k 8191/tcp 2>/dev/null; sleep 1
}

run memory-leak  memory_smaps 10 "Memory Leak → memory_json"
run thread-spawn sys_metrics 10 "Thread Growth → sys_metrics"
run python-cpu   pyspy       12 "Python CPU → py-spy"

echo ""
echo "=== DONE ==="
echo "Results: ls /tmp/mini-drop/"
ls -d /tmp/mini-drop/*/ 2>/dev/null
