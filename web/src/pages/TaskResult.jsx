import { useEffect, useState } from "react";
import { Alert, Card, Descriptions, Space, Spin, Table, Tag, Timeline, Typography } from "antd";
import { useParams } from "react-router-dom";
import { getTask, getTaskArtifacts, getTaskEvents } from "../api/client";

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

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError("");
      try {
        const [taskResp, eventResp, artifactResp] = await Promise.all([
          getTask(taskId),
          getTaskEvents(taskId),
          getTaskArtifacts(taskId),
        ]);
        setTask(taskResp);
        setEvents(eventResp || []);
        setArtifacts(artifactResp || []);
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
      </Spin>
    </Space>
  );
}
