#!/bin/bash
# Mini-Drop Final E2E Test (4 scenarios)
set -e
export PATH=$HOME/.local/bin:$PATH
cd ~/mini-drop-new

cleanup() {
  fuser -k 50051/tcp 2>/dev/null || true
  fuser -k 8191/tcp 2>/dev/null || true
  sleep 1
}

run_scene() {
  local scene="$1" collector="$2" extra_duration="$3"
  local label="$4"
  echo ""
  echo "═══════════════════════════════════════════"
  echo "  SCENE: $label ($collector)"
  echo "═══════════════════════════════════════════"

  cleanup

  # Start Server
  python3 -m server.app.main &
  SERVER_PID=$!
  sleep 3

  # Start Agent (with PATH for py-spy, sudo for bpftrace)
  if [ "$collector" = "pyspy" ] || [ "$collector" = "ebpf_io" ]; then
    echo "312q" | sudo -S -E python3 -m agent.mini_drop_agent.main &
    AGENT_PID=$!
  else
    python3 -m agent.mini_drop_agent.main &
    AGENT_PID=$!
  fi
  sleep 4

  # Start target process
  python3 demo/vm_test_targets.py "$scene" $((extra_duration + 10 > 30 ? extra_duration + 10 : 30)) &
  TARGET=$!
  sleep 2

  # Create task
  local resp tid status arts
  resp=$(curl -s -X POST http://localhost:8191/api/tasks \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"e2e-$scene\",\"agent_id\":\"test_agent\",\"target_pid\":$TARGET,\"collector_type\":\"$collector\",\"sample_rate\":99,\"duration_sec\":$extra_duration}")
  tid=$(echo "$resp" | python3 -c "import json,sys;print(json.load(sys.stdin)['data']['task_id'])")
  echo "  Task ID: $tid"

  # Poll
  for i in $(seq 1 45); do
    status=$(curl -s "http://localhost:8191/api/tasks/$tid" | python3 -c "import json,sys;print(json.load(sys.stdin)['data']['status'])" 2>/dev/null || echo '?')
    if [ $i -le 3 ] || [ "$status" = "DONE" ] || [ "$status" = "FAILED" ]; then
      printf "  [%2d] %s\n" "$i" "$status"
    fi
    if [ "$status" = "DONE" ] || [ "$status" = "FAILED" ]; then break; fi
    sleep 1
  done

  # Artifacts
  arts=$(curl -s "http://localhost:8191/api/tasks/$tid/artifacts")
  echo "  Artifacts:" $(echo "$arts" | python3 -c "import json,sys;d=json.load(sys.stdin);print([a['artifact_type'] for a in d['data']['items']])" 2>/dev/null || echo '?')

  # Disk files
  disk_dir="/tmp/mini-drop/$tid"
  if [ -d "$disk_dir" ]; then
    echo "  Disk: $(ls $disk_dir 2>/dev/null | tr '\n' ' ')"
    # Show key data
    case "$collector" in
      perf_cpu)
        if [ -f "$disk_dir/top.json" ]; then
          python3 -c "import json;d=json.load(open('$disk_dir/top.json'));print(f'  TopN: {len(d)} items, #1={d[0][\"percent\"]:.1f}% {d[0][\"name\"][:50]}')"
        fi
        if [ -f "$disk_dir/flamegraph.svg" ]; then
          echo "  SVG: $(wc -c < $disk_dir/flamegraph.svg) bytes"
        fi
        ;;
      memory_smaps)
        if [ -f "$disk_dir/memory_profile.json" ]; then
          python3 -c "import json;d=json.load(open('$disk_dir/memory_profile.json'));print(f'  Memory: {d.get(\"sample_count\",0)} samples RSS {d.get(\"first_rss_mb\",0)}->{d.get(\"last_rss_mb\",0)} MB trend={d.get(\"trend\",\"?\")}')"
        fi
        ;;
      sys_metrics)
        if [ -f "$disk_dir/sys_metrics.json" ]; then
          python3 -c "import json;d=json.load(open('$disk_dir/sys_metrics.json'));s=d['summary'];print(f'  sys_metrics: threads={s.get(\"thread_count\",0)} trend={s.get(\"thread_trend\",\"?\")} fd={s.get(\"fd_count\",0)} ctx={s.get(\"ctx_nonvoluntary_rate\",0)}/s')"
        fi
        ;;
      pyspy)
        if [ -f "$disk_dir/flamegraph.svg" ]; then
          echo "  py-spy SVG: $(wc -c < $disk_dir/flamegraph.svg) bytes"
        fi
        ;;
    esac
  fi

  # Cleanup this scene
  kill $TARGET 2>/dev/null || true
  kill $AGENT_PID 2>/dev/null || true
  sudo kill $AGENT_PID 2>/dev/null || true
  kill $SERVER_PID 2>/dev/null || true
  wait 2>/dev/null || true
}

# ──────────────────────────────────────────────────
export MINI_DROP_API_AUTH_ENABLED=0
export MINI_DROP_GRPC_AUTH_ENABLED=0
export MINIO_AUTO_CREATE_BUCKET=0
export AGENT_ID=test_agent
export AGENT_GRPC_ADDR=localhost:50051
export AGENT_UPLOAD_ARTIFACTS=0

echo "Mini-Drop E2E Test Suite"
echo "========================"
which perf && perf --version 2>&1 | head -1 || echo "WARN: no perf"
which py-spy && py-spy --version 2>&1 || echo "WARN: no py-spy"
which bpftrace && bpftrace --version 2>&1 || echo "WARN: no bpftrace"
echo "pycache: cleared"
find . -path '*/__pycache__/*' -delete 2>/dev/null || true
echo ""

run_scene cpu-loop    perf_cpu      12 "CPU Loop → Flamegraph + TopN"
run_scene memory-leak  memory_smaps 10 "Memory Leak → RSS trend"
run_scene thread-spawn sys_metrics  10 "Thread Growth → sys_metrics"
run_scene python-cpu   pyspy        12 "Python CPU → py-spy Flamegraph"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║     ALL 4 E2E SCENARIOS COMPLETE             ║"
echo "║     Results: /tmp/mini-drop/                 ║"
echo "╚══════════════════════════════════════════════╝"
