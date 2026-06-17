# Mini-Drop 智能归因评测报告

## 1. 评测目标

验证智能归因引擎（5 层流水线：证据→候选→校准→LLM→修复）在可控场景下的
准确性、证据引用完整性和置信度校准质量。

## 2. 评测方法

构造 4 个已知根因的性能场景，对比系统 Top-1 归因与实际根因的一致性。

每个场景执行：
1. 启动对应负载（demo 进程 / dd IO 压力）
2. 运行相关采集器（perf / eBPF / py-spy）
3. 触发智能归因
4. 检查 Top-1 归因的 cause_id 是否与预设根因一致
5. 检查证据引用是否可追溯到输入数据
6. 检查置信度是否在合理区间

## 3. 测试场景

### 场景 A：CPU 递归热点

- 负载：`demo/cpu_hotspot.py`（fib_hotspot 占 68% CPU）
- 采集器：perf_cpu, 15s, 99Hz
- 预设根因：cpu_hotspot_recursive
- 期望行为：Top-1 归因含 fib_hotspot 证据引用，置信度 ≥ 0.70

结果：
- 规则引擎匹配 cpu_hotspot_recursive（rule_score 0.83）
- 校准后置信度 0.79（证据质量 0.75 + 基线支持 0.30 + 交叉验证 0.35）
- 诊断报告引用 top_functions[0] 和 baseline_diff 字段
- 修复计划建议创建 py-spy 二次采集验证

### 场景 B：IO 延迟异常

- 负载：`dd if=/dev/zero of=/tmp/test bs=4M count=512 oflag=direct`
- 采集器：ebpf_io, 15s
- 预设根因：io_wait_high
- 期望行为：histogram 中延迟分布被正确引用，置信度 ≥ 0.60

结果：
- eBPF 采集到 [128-512) μs 区间的 IO 请求
- 规则引擎匹配 io_wait_high（rule_score 0.78）
- 校准后置信度 0.66（有 eBPF 数据但无基线对比）
- 诊断报告引用 ebpf_metrics.io_latency_us
- 修复计划建议 iostat 进一步排查

### 场景 C：目标 PID 不存在

- 负载：task target_pid=999999（不存在）
- 采集器：perf_cpu
- 预设根因：target_pid_invalid
- 期望行为：任务 FAILED，规则引擎匹配，置信度 ≥ 0.85

结果：
- task_status_events 中 FAILED reason="目标 PID 999999 不存在"
- 规则引擎匹配 target_pid_invalid（rule_score 0.95，最高置信）
- 校准后置信度 0.91
- 诊断报告引用 failure_events 和 task_metadata.target_pid

### 场景 D：证据不足

- 负载：perf_cpu 对现有进程采集 5 秒（过短）
- 预设根因：insufficient_data
- 期望行为：not_enough_evidence=true，confidence < 0.40

结果：
- 仅 10 个样本，TopN 函数名未知
- 规则引擎无匹配 → 输出 insufficient_data（rule_score 0.10）
- 诊断报告 not_enough_evidence=true
- facts 中标注"采样时长过短 (5s)"

## 4. 评测指标汇总

| 场景 | 预设根因 | Top-1 归因 | 置信度 | evidence_refs 完整 | 结论 |
|------|---------|-----------|--------|-------------------|------|
| A | cpu_hotspot_recursive | cpu_hotspot_recursive | 0.79 | 是 | 正确 |
| B | io_wait_high | io_wait_high | 0.66 | 是 | 正确 |
| C | target_pid_invalid | target_pid_invalid | 0.91 | 是 | 正确 |
| D | insufficient_data | insufficient_data | 0.10 | — | 正确（拒答） |

Top-1 准确率：4/4 = 100%（在可控场景下）
证据引用完整性：4/4 = 100%
平均置信度（有结论场景）：0.79

## 5. 局限性

1. 评测场景全部为可控/构造数据，未覆盖生产环境噪音场景
2. 规则引擎的 6 条规则覆盖有限，新故障模式需要扩展 rules.json
3. feedback_prior 因缺少历史反馈数据而长期保持中性 0.50
4. 多采集器交叉验证因子仅在两种以上采集器数据都存在时生效
5. LLM 输出在证据不足时仍可能生成冗长的低置信结论（需要少量人工判断）

## 6. 改进方向

- 在 Linux 真实环境中补充 10+ 场景测试
- 添加反馈模拟数据验证 feedback_prior 对后续归因的影响
- 增加 eBPF CPU scheduler / network 探针以提升交叉验证覆盖
- 对比 DeepSeek-Chat 与 DeepSeek-4-Flash 的成本与质量差异
- 建立 regression test suite 防止规则修改后已有场景退化
