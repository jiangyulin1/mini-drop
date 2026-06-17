import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Collapse,
  Descriptions,
  Empty,
  message,
  Progress,
  Space,
  Spin,
  Table,
  Tag,
  Timeline,
  Tooltip,
  Typography,
} from "antd";
import { ExperimentOutlined, ReloadOutlined } from "@ant-design/icons";
import { useParams } from "react-router-dom";
import {
  getDiagnosis,
  getTask,
  getTaskArtifacts,
  getTaskEvents,
  listTaskDiagnoses,
  submitDiagnosisFeedback,
  triggerDiagnose,
} from "../api/client";

function statusColor(status) {
  if (status === "DONE") return "green";
  if (status === "FAILED") return "red";
  if (status === "RUNNING" || status === "ANALYZING" || status === "UPLOADING") return "blue";
  return "gray";
}

export default function TaskResult() {
  const { taskId } = useParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [task, setTask] = useState(null);
  const [events, setEvents] = useState([]);
  const [artifacts, setArtifacts] = useState([]);
  const [diagnoses, setDiagnoses] = useState([]);
  const [diagnosis, setDiagnosis] = useState(null);
  const [diagnosing, setDiagnosing] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
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
        setDiagnoses(diagnosisList || []);
        if (diagnosisList?.[0]?.id) {
          setDiagnosis(await getDiagnosis(diagnosisList[0].id));
        } else {
          setDiagnosis(null);
        }
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [taskId]);

  const artifactColumns = [
    { title: "类型", dataIndex: "artifact_type" },
    { title: "文件", dataIndex: "filename", render: (value, record) => value || record.object_key || record.local_path },
    { title: "大小", dataIndex: "size_bytes", width: 120 },
  ];

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

  const report = diagnosis?.report?.report || {};
  const rankedCauses = diagnosis?.report?.ranked_causes || [];
  const repairPlan = diagnosis?.repair_plan;
  const toolResults = diagnosis?.tool_results || [];
  const topCause = rankedCauses[0];

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Typography.Title level={4} style={{ margin: 0 }}>任务详情</Typography.Title>
      {error && <Alert type="error" message={error} showIcon />}

      <Spin spinning={loading}>
        {task && (
          <Card>
            <Descriptions column={2} size="middle">
              <Descriptions.Item label="任务 ID">{task.id}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={statusColor(task.status)}>{task.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="名称">{task.name}</Descriptions.Item>
              <Descriptions.Item label="Agent">{task.agent_id}</Descriptions.Item>
              <Descriptions.Item label="PID">{task.target_pid}</Descriptions.Item>
              <Descriptions.Item label="采集器">{task.collector_type}</Descriptions.Item>
              <Descriptions.Item label="采样率">{task.sample_rate} Hz</Descriptions.Item>
              <Descriptions.Item label="采样时长">{task.duration_sec}s</Descriptions.Item>
              <Descriptions.Item label="原因" span={2}>{task.status_reason}</Descriptions.Item>
            </Descriptions>
          </Card>
        )}

        <Card title="状态时间线" style={{ marginTop: 16 }}>
          <Timeline
            items={events.map((event) => ({
              color: statusColor(event.to_status),
              children: (
                <Space direction="vertical" size={0}>
                  <Typography.Text strong>{event.to_status}</Typography.Text>
                  <Typography.Text type="secondary">{event.reason}</Typography.Text>
                </Space>
              ),
            }))}
          />
        </Card>

        <Card title="产物" style={{ marginTop: 16 }}>
          <Table
            rowKey={(record, index) => `${record.artifact_type || "artifact"}-${index}`}
            columns={artifactColumns}
            dataSource={artifacts}
            pagination={false}
            size="middle"
          />
        </Card>

        <Card
          title="智能归因"
          style={{ marginTop: 16 }}
          extra={
            <Space>
              {diagnoses.length > 0 && <Tag>{diagnoses.length} 次诊断</Tag>}
              <Button icon={<ExperimentOutlined />} loading={diagnosing} onClick={runDiagnosis}>
                运行诊断
              </Button>
              <Tooltip title="刷新诊断报告">
                <Button icon={<ReloadOutlined />} onClick={refreshDiagnosis} disabled={!diagnosis?.run?.id} />
              </Tooltip>
            </Space>
          }
        >
          {!diagnosis ? (
            <Empty description="暂无诊断报告" />
          ) : (
            <Space direction="vertical" size={16} style={{ width: "100%" }}>
              <Descriptions column={2} size="small">
                <Descriptions.Item label="诊断 ID">{diagnosis.run.id}</Descriptions.Item>
                <Descriptions.Item label="状态">
                  <Tag color={diagnosis.run.status === "DONE" ? "green" : "red"}>{diagnosis.run.status}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="模型">{diagnosis.run.model_name}</Descriptions.Item>
                <Descriptions.Item label="校验">
                  <Tag color={diagnosis.run.validated ? "green" : "orange"}>{diagnosis.run.validated ? "通过" : "未通过"}</Tag>
                </Descriptions.Item>
              </Descriptions>

              <Alert
                type={report.not_enough_evidence ? "warning" : "info"}
                message={report.summary || diagnosis.run.summary}
                showIcon
              />

              <Table
                rowKey={(record) => record.cause_id}
                dataSource={rankedCauses}
                pagination={false}
                size="small"
                columns={[
                  { title: "根因", dataIndex: "cause_id", width: 220 },
                  {
                    title: "置信度",
                    dataIndex: "confidence",
                    width: 160,
                    render: (value) => <Progress percent={Math.round((value || 0) * 100)} size="small" />,
                  },
                  { title: "结论", dataIndex: "claim" },
                  {
                    title: "证据引用",
                    dataIndex: "evidence_refs",
                    render: (refs = []) => refs.map((ref) => <Tag key={ref}>{ref}</Tag>),
                  },
                ]}
              />

              <Space>
                <Button size="small" onClick={() => sendFeedback("correct", topCause?.cause_id)} disabled={!topCause}>正确</Button>
                <Button size="small" onClick={() => sendFeedback("partial", topCause?.cause_id)} disabled={!topCause}>部分正确</Button>
                <Button size="small" danger onClick={() => sendFeedback("wrong", topCause?.cause_id)} disabled={!topCause}>错误</Button>
              </Space>

              <Collapse
                items={[
                  {
                    key: "tools",
                    label: "Tool-Use 证据链",
                    children: (
                      <Table
                        rowKey={(record, index) => `${record.tool_name}-${index}`}
                        dataSource={toolResults}
                        pagination={false}
                        size="small"
                        columns={[
                          { title: "工具", dataIndex: "tool_name", width: 220 },
                          { title: "状态", dataIndex: "status", width: 120, render: (value) => <Tag>{value}</Tag> },
                          { title: "证据引用", dataIndex: "evidence_ref", width: 260 },
                          {
                            title: "结果",
                            dataIndex: "output",
                            render: (value) => <Typography.Text code>{JSON.stringify(value).slice(0, 160)}</Typography.Text>,
                          },
                        ]}
                      />
                    ),
                  },
                  {
                    key: "repair",
                    label: "修复计划",
                    children: repairPlan ? (
                      <Space direction="vertical" style={{ width: "100%" }}>
                        <Space>
                          <Tag color={repairPlan.risk_level === "safe_auto" ? "green" : "orange"}>{repairPlan.risk_level}</Tag>
                          <Tag>{repairPlan.status}</Tag>
                          {repairPlan.requires_user_confirm && <Tag color="orange">需人工确认风险动作</Tag>}
                        </Space>
                        <Table
                          rowKey="action_id"
                          dataSource={repairPlan.actions || []}
                          pagination={false}
                          size="small"
                          columns={[
                            { title: "动作", dataIndex: "action_type", width: 200 },
                            { title: "风险", dataIndex: "risk_level", width: 140, render: (value) => <Tag>{value}</Tag> },
                            { title: "状态", dataIndex: "status", width: 120 },
                            { title: "说明", dataIndex: "description" },
                            { title: "结果", dataIndex: "result" },
                          ]}
                        />
                      </Space>
                    ) : <Empty description="暂无修复计划" />,
                  },
                ]}
              />
            </Space>
          )}
        </Card>
      </Spin>
    </Space>
  );
}
