import { useEffect, useState, useRef, useCallback } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Collapse,
  Descriptions,
  Empty,
  message,
  Progress,
  Row,
  Skeleton,
  Space,
  Spin,
  Table,
  Tag,
  Timeline,
  Tooltip,
  Typography,
} from "antd";
import {
  ArrowLeftOutlined,
  BarChartOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { useParams, useNavigate } from "react-router-dom";
import {
  getDiagnosis,
  getTask,
  getTaskArtifactContent,
  getTaskArtifacts,
  getTaskEvents,
  listTaskDiagnoses,
  submitDiagnosisFeedback,
  triggerDiagnose,
} from "../api/client";
import FlamegraphViewer from "../components/FlamegraphViewer";
import TopNChart from "../components/TopNChart";
import StatusTag from "../components/StatusTag";
import ErrorAlert from "../components/ErrorAlert";
import usePolling from "../hooks/usePolling";
import { isTaskActive } from "../utils/status";
import { COLORS, SPACING } from "../theme";
import styles from "./TaskResult.module.css";

export default function TaskResult() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const flameRef = useRef(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [task, setTask] = useState(null);
  const [events, setEvents] = useState([]);
  const [artifacts, setArtifacts] = useState([]);
  const [diagnoses, setDiagnoses] = useState([]);
  const [diagnosis, setDiagnosis] = useState(null);
  const [diagnosing, setDiagnosing] = useState(false);
  const [analysis, setAnalysis] = useState({ top: [], svg: "", hasFlameJson: false });
  const [analysisLoading, setAnalysisLoading] = useState(true);

  // ── 数据加载 ──────────────────────────────────────────

  const loadAll = useCallback(async () => {
    setError("");
    try {
      const [taskResp, eventResp, artifactResp, diagnosisList] = await Promise.all([
        getTask(taskId),
        getTaskEvents(taskId),
        getTaskArtifacts(taskId),
        listTaskDiagnoses(taskId),
      ]);
      setTask(taskResp);
      setEvents(eventResp || []);
      setArtifacts(artifactResp || []);
      await loadAnalysisArtifacts(artifactResp || []);
      setDiagnoses(diagnosisList || []);
      if (diagnosisList?.[0]?.id) {
        try {
          setDiagnosis(await getDiagnosis(diagnosisList[0].id));
        } catch {
          setDiagnosis(null);
        }
      } else {
        setDiagnosis(null);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // 任务活跃时每 5 秒自动刷新
  const isActive = isTaskActive(task?.status);
  usePolling(loadAll, { interval: 5000, enabled: isActive });

  async function loadAnalysisArtifacts(artifactResp) {
    setAnalysisLoading(true);
    const hasTop = artifactResp.some((item) => item.artifact_type === "top_json");
    const hasFlameJson = artifactResp.some((item) => item.artifact_type === "flamegraph_json");
    const hasSvg = artifactResp.some((item) => item.artifact_type === "flamegraph_svg");
    const next = { top: [], svg: "", hasFlameJson: false };

    if (hasTop) {
      try {
        next.top = await getTaskArtifactContent(taskId, "top_json");
      } catch {
        next.top = [];
      }
    }
    if (hasFlameJson) {
      next.hasFlameJson = true;
    }
    if (hasSvg && !hasFlameJson) {
      // 仅在无交互式火焰图时加载 SVG 作为降级
      try {
        const content = await getTaskArtifactContent(taskId, "flamegraph_svg");
        next.svg = content.text || "";
      } catch {
        next.svg = "";
      }
    }
    setAnalysis(next);
    setAnalysisLoading(false);
  }

  // ── 诊断操作 ──────────────────────────────────────────

  async function runDiagnosis() {
    setDiagnosing(true);
    setError("");
    try {
      const result = await triggerDiagnose(taskId);
      const detail = await getDiagnosis(result.diagnosis_id);
      const list = await listTaskDiagnoses(taskId);
      setDiagnosis(detail);
      setDiagnoses(list || []);
      message.success("诊断完成");
    } catch (err) {
      setError(err.message);
    } finally {
      setDiagnosing(false);
    }
  }

  async function sendFeedback(label, causeId) {
    if (!diagnosis?.run?.id) return;
    try {
      await submitDiagnosisFeedback(diagnosis.run.id, {
        predicted_cause_id: causeId || "insufficient_data",
        feedback_label: label,
      });
      message.success("反馈已记录");
    } catch (err) {
      setError(err.message);
    }
  }

  async function refreshDiagnosis() {
    if (!diagnosis?.run?.id) return;
    try {
      setDiagnosis(await getDiagnosis(diagnosis.run.id));
    } catch (err) {
      setError(err.message);
    }
  }

  // ── 产物提取 ──────────────────────────────────────────

  const report = diagnosis?.report?.report || {};
  const rankedCauses = diagnosis?.report?.ranked_causes || [];
  const repairPlan = diagnosis?.repair_plan;
  const toolResults = diagnosis?.tool_results || [];
  const topCause = rankedCauses[0];
  const topArtifact = artifacts.find((item) => item.artifact_type === "top_json");
  const flameArtifact = artifacts.find(
    (item) =>
      item.artifact_type === "flamegraph_svg" ||
      item.artifact_type === "flamegraph_json"
  );
  const suggestionArtifact = artifacts.find(
    (item) => item.artifact_type === "suggestions_md"
  );
  const continuousSummary = artifacts.find(
    (item) => item.artifact_type === "continuous_summary"
  );
  const continuousWindows = continuousSummary?.metadata?.windows || [];

  const artifactColumns = [
    {
      title: "类型",
      dataIndex: "artifact_type",
      width: 140,
      render: (value) => {
        const colors = {
          flamegraph_json: "blue",
          flamegraph_svg: "blue",
          top_json: "green",
          suggestions_md: "orange",
          raw: "default",
        };
        return <Tag color={colors[value] || "default"}>{value}</Tag>;
      },
    },
    {
      title: "文件",
      dataIndex: "filename",
      ellipsis: true,
      render: (value, record) =>
        value || record.object_key || record.local_path || "-",
    },
    {
      title: "大小",
      dataIndex: "size_bytes",
      width: 100,
      render: (v) => (v ? `${(v / 1024).toFixed(1)} KB` : "-"),
    },
  ];

  // ── 加载骨架屏 ────────────────────────────────────────

  const FLAMEGRAPH_HEIGHT = 360;

  if (loading) {
    return (
      <Space direction="vertical" size={SPACING.lg} style={{ width: "100%" }}>
        <Skeleton.Input active size="small" style={{ width: 200 }} />
        <div className={styles.skeletonCard}>
          <Skeleton active paragraph={{ rows: 4 }} />
        </div>
        <div className={styles.skeletonCard}>
          <Skeleton active paragraph={{ rows: 3 }} />
        </div>
        <div className={styles.skeletonCard}>
          <Skeleton.Input active block style={{ height: FLAMEGRAPH_HEIGHT, borderRadius: 8 }} />
        </div>
      </Space>
    );
  }

  // ── 主渲染 ────────────────────────────────────────────

  return (
    <Space direction="vertical" size={SPACING.lg} style={{ width: "100%" }}>
      {/* 页面标题 + 返回 + 自动刷新指示 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <Space align="center">
          <Button
            icon={<ArrowLeftOutlined />}
            type="text"
            onClick={() => navigate("/")}
          >
            返回任务面板
          </Button>
          <Typography.Title level={4} style={{ margin: 0 }}>
            任务详情
          </Typography.Title>
        </Space>
        {isActive && (
          <Tag color="blue">自动刷新中（任务运行中）</Tag>
        )}
      </div>

      <ErrorAlert error={error} style={{ marginBottom: 0 }} onClose={() => setError("")} />

      {/* 任务基本信息 */}
      {task && (
        <Card size="small">
          <Descriptions column={{ xs: 1, sm: 2, md: 2, lg: 4 }} size="small">
            <Descriptions.Item label="任务 ID">
              <Typography.Text copyable={{ text: task.id }} style={{ fontSize: 12 }}>
                {task.id}
              </Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <StatusTag status={task.status} />
            </Descriptions.Item>
            <Descriptions.Item label="名称">{task.name}</Descriptions.Item>
            <Descriptions.Item label="Agent">{task.agent_id}</Descriptions.Item>
            <Descriptions.Item label="PID">{task.target_pid}</Descriptions.Item>
            <Descriptions.Item label="采集器">
              <Tag>{task.collector_type}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="采样率">{task.sample_rate} Hz</Descriptions.Item>
            <Descriptions.Item label="采样时长">{task.duration_sec}s</Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      {/* 状态时间线 + 产物 并排 */}
      <Row gutter={SPACING.lg}>
        <Col xs={24} lg={12}>
          <Card title="状态时间线" size="small">
            {events.length > 0 ? (
              <Timeline
                items={events.map((event) => ({
                  color: event.to_status === "DONE"
                    ? "green"
                    : event.to_status === "FAILED"
                    ? "red"
                    : "blue",
                  children: (
                    <Space direction="vertical" size={0}>
                      <Typography.Text strong>
                        <StatusTag status={event.to_status} />
                      </Typography.Text>
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        {event.reason}
                      </Typography.Text>
                    </Space>
                  ),
                }))}
              />
            ) : (
              <Empty description="暂无状态事件" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="产物" size="small">
            {artifacts.length > 0 ? (
              <Table
                rowKey={(record, index) => `${record.artifact_type || "artifact"}-${index}`}
                columns={artifactColumns}
                dataSource={artifacts}
                pagination={false}
                size="small"
                scroll={{ x: 400 }}
              />
            ) : (
              <Empty description="暂无分析产物" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
      </Row>

      {/* 火焰图 + TopN 并排 ⭐ 核心区域 */}
      <Card
        title={
          <Space>
            <FileTextOutlined style={{ color: COLORS.primary }} />
            分析结果
            {isActive && <Spin size="small" />}
          </Space>
        }
        size="small"
      >
        {flameArtifact || topArtifact ? (
          <Row gutter={SPACING.lg}>
            {/* 火焰图 */}
            <Col xs={24} lg={topArtifact ? 16 : 24}>
              <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
                🔥 火焰图
              </Typography.Text>
              {analysis.hasFlameJson ? (
                <FlamegraphViewer ref={flameRef} taskId={taskId} />
              ) : analysis.svg ? (
                <div
                  style={{
                    border: `1px solid ${COLORS.border}`,
                    borderRadius: 6,
                    overflowX: "auto",
                    maxHeight: FLAMEGRAPH_HEIGHT,
                    background: "#fff",
                  }}
                  dangerouslySetInnerHTML={{ __html: analysis.svg }}
                />
              ) : analysisLoading ? (
                <Skeleton.Input active block style={{ height: FLAMEGRAPH_HEIGHT, borderRadius: 8 }} />
              ) : (
                <Empty description="暂无火焰图，请等待分析完成" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </Col>

            {/* TopN 柱状图 */}
            {topArtifact && (
              <Col xs={24} lg={8}>
                <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
                  📊 热点 Top {Math.min(analysis.top.length, 10)}
                </Typography.Text>
                <TopNChart
                  data={analysis.top.slice(0, 10)}
                  loading={analysisLoading}
                  height={FLAMEGRAPH_HEIGHT}
                  onBarClick={(funcName) => {
                    if (flameRef.current) {
                      flameRef.current.search(funcName);
                    }
                  }}
                />
                <Typography.Text
                  type="secondary"
                  style={{ fontSize: 11, display: "block", marginTop: 4, textAlign: "center" }}
                >
                  点击柱状图 → 火焰图中高亮对应函数
                </Typography.Text>
              </Col>
            )}
          </Row>
        ) : (
          <Empty
            description={
              isActive
                ? "任务运行中，分析产物将在完成后生成…"
                : "暂无火焰图或 TopN 分析结果"
            }
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            {isActive && <Spin />}
          </Empty>
        )}

        {/* 建议 */}
        {suggestionArtifact && (
          <div style={{ marginTop: 12 }}>
            <Tag color="orange" icon={<BarChartOutlined />}>
              建议已生成: {suggestionArtifact.filename || suggestionArtifact.local_path || suggestionArtifact.object_key}
            </Tag>
          </div>
        )}

        {/* 持续采样窗口 */}
        {continuousWindows.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <Typography.Text strong>连续采样窗口</Typography.Text>
            <Table
              rowKey={(record) => record.window_index}
              dataSource={continuousWindows}
              pagination={false}
              size="small"
              style={{ marginTop: 8 }}
              scroll={{ x: 600 }}
              columns={[
                { title: "窗口", dataIndex: "window_index", width: 70 },
                {
                  title: "开始",
                  dataIndex: "start_ts",
                  width: 170,
                  render: (value) =>
                    value
                      ? new Date(value * 1000).toLocaleString()
                      : "-",
                },
                {
                  title: "结束",
                  dataIndex: "end_ts",
                  width: 170,
                  render: (value) =>
                    value
                      ? new Date(value * 1000).toLocaleString()
                      : "-",
                },
                {
                  title: "状态",
                  dataIndex: "ok",
                  width: 100,
                  render: (value) => (
                    <Tag color={value ? "green" : "red"}>
                      {value ? "OK" : "FAILED"}
                    </Tag>
                  ),
                },
                { title: "说明", dataIndex: "reason", ellipsis: true },
              ]}
            />
          </div>
        )}
      </Card>

      {/* 智能归因 */}
      <Card
        title={
          <Space>
            <ExperimentOutlined style={{ color: COLORS.primary }} />
            智能归因
          </Space>
        }
        size="small"
        extra={
          <Space>
            {diagnoses.length > 0 && <Tag>{diagnoses.length} 次诊断</Tag>}
            <Button
              icon={<ExperimentOutlined />}
              loading={diagnosing}
              onClick={runDiagnosis}
              type="primary"
              size="small"
            >
              运行诊断
            </Button>
            <Tooltip title="刷新诊断报告">
              <Button
                icon={<ReloadOutlined />}
                size="small"
                onClick={refreshDiagnosis}
                disabled={!diagnosis?.run?.id}
              />
            </Tooltip>
          </Space>
        }
      >
        {!diagnosis ? (
          <Empty
            description={
              diagnosing
                ? "诊断进行中…"
                : "暂无诊断报告，点击「运行诊断」基于当前证据进行 AI 归因分析"
            }
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            {diagnosing && <Spin />}
          </Empty>
        ) : (
          <Space direction="vertical" size={SPACING.lg} style={{ width: "100%" }}>
            {/* 诊断元数据 */}
            <Descriptions column={{ xs: 1, sm: 2, md: 4 }} size="small">
              <Descriptions.Item label="诊断 ID">
                <Typography.Text copyable={{ text: diagnosis.run?.id }} style={{ fontSize: 12 }}>
                  {diagnosis.run?.id}
                </Typography.Text>
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <StatusTag
                  status={diagnosis.run?.status === "DONE" ? "DONE" : "FAILED"}
                />
              </Descriptions.Item>
              <Descriptions.Item label="模型">
                <Tag>{diagnosis.run?.model_name}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="校验">
                <Tag color={diagnosis.run?.validated ? "green" : "orange"}>
                  {diagnosis.run?.validated ? "通过" : "未通过"}
                </Tag>
              </Descriptions.Item>
            </Descriptions>

            {/* 摘要 */}
            <Alert
              type={report.not_enough_evidence ? "warning" : "info"}
              message={report.summary || diagnosis.run?.summary || "诊断完成"}
              showIcon
            />

            {/* 归因列表 */}
            {rankedCauses.length > 0 && (
              <Table
                rowKey={(record) => record.cause_id}
                dataSource={rankedCauses}
                pagination={false}
                size="small"
                scroll={{ x: 600 }}
                columns={[
                  { title: "根因", dataIndex: "cause_id", width: 200 },
                  {
                    title: "置信度",
                    dataIndex: "confidence",
                    width: 140,
                    render: (value) => (
                      <Progress
                        percent={Math.round((value || 0) * 100)}
                        size="small"
                        strokeColor={
                          (value || 0) > 0.7
                            ? COLORS.success
                            : (value || 0) > 0.4
                            ? COLORS.warning
                            : COLORS.error
                        }
                      />
                    ),
                  },
                  { title: "结论", dataIndex: "claim", ellipsis: true },
                  {
                    title: "证据引用",
                    dataIndex: "evidence_refs",
                    width: 200,
                    render: (refs = []) => (
                      <Space size={[2, 2]} wrap>
                        {refs.map((ref) => (
                          <Tag key={ref} style={{ fontSize: 10, margin: 0 }}>
                            {ref}
                          </Tag>
                        ))}
                      </Space>
                    ),
                  },
                ]}
              />
            )}

            {/* 反馈 */}
            <Space>
              <Button
                size="small"
                onClick={() => sendFeedback("correct", topCause?.cause_id)}
                disabled={!topCause}
              >
                👍 正确
              </Button>
              <Button
                size="small"
                onClick={() => sendFeedback("partial", topCause?.cause_id)}
                disabled={!topCause}
              >
                🔶 部分正确
              </Button>
              <Button
                size="small"
                danger
                onClick={() => sendFeedback("wrong", topCause?.cause_id)}
                disabled={!topCause}
              >
                👎 错误
              </Button>
            </Space>

            {/* 可折叠详情 */}
            <Collapse
              ghost
              items={[
                {
                  key: "tools",
                  label: `Tool-Use 证据链 (${toolResults.length})`,
                  children: toolResults.length > 0 ? (
                    <Table
                      rowKey={(record, index) => `${record.tool_name}-${index}`}
                      dataSource={toolResults}
                      pagination={false}
                      size="small"
                      scroll={{ x: 700 }}
                      columns={[
                        { title: "工具", dataIndex: "tool_name", width: 200 },
                        {
                          title: "状态",
                          dataIndex: "status",
                          width: 100,
                          render: (value) => <Tag>{value}</Tag>,
                        },
                        {
                          title: "证据引用",
                          dataIndex: "evidence_ref",
                          width: 240,
                          ellipsis: true,
                        },
                        {
                          title: "结果",
                          dataIndex: "output",
                          render: (value) => (
                            <Typography.Text
                              code
                              ellipsis
                              style={{ maxWidth: 200, display: "inline-block" }}
                            >
                              {JSON.stringify(value).slice(0, 160)}
                            </Typography.Text>
                          ),
                        },
                      ]}
                    />
                  ) : (
                    <Empty description="无工具调用记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ),
                },
                {
                  key: "repair",
                  label: "修复计划",
                  children: repairPlan ? (
                    <Space direction="vertical" style={{ width: "100%" }}>
                      <Space wrap>
                        <Tag
                          color={
                            repairPlan.risk_level === "safe_auto" ? "green" : "orange"
                          }
                        >
                          {repairPlan.risk_level}
                        </Tag>
                        <Tag>{repairPlan.status}</Tag>
                        {repairPlan.requires_user_confirm && (
                          <Tag color="orange">需人工确认风险动作</Tag>
                        )}
                      </Space>
                      <Table
                        rowKey="action_id"
                        dataSource={repairPlan.actions || []}
                        pagination={false}
                        size="small"
                        scroll={{ x: 600 }}
                        columns={[
                          { title: "动作", dataIndex: "action_type", width: 180 },
                          {
                            title: "风险",
                            dataIndex: "risk_level",
                            width: 120,
                            render: (value) => <Tag>{value}</Tag>,
                          },
                          { title: "状态", dataIndex: "status", width: 100 },
                          { title: "说明", dataIndex: "description", ellipsis: true },
                          { title: "结果", dataIndex: "result", ellipsis: true },
                        ]}
                      />
                    </Space>
                  ) : (
                    <Empty description="暂无修复计划" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ),
                },
              ]}
            />
          </Space>
        )}
      </Card>
    </Space>
  );
}
