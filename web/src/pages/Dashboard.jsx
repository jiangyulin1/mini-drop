import { useEffect, useState } from "react";
import { Alert, Button, Card, Col, Row, Space, Spin, Table, Tag, Typography } from "antd";
import { ApiOutlined, ReloadOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import { healthz, listAgents, listTasks } from "../api/client";
import NLPTaskInput from "../components/NLPTaskInput";

function statusColor(status) {
  if (status === "DONE" || status === "ONLINE") return "green";
  if (status === "FAILED" || status === "OFFLINE") return "red";
  if (status === "RUNNING" || status === "ANALYZING" || status === "UPLOADING") return "blue";
  return "default";
}

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [service, setService] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [agents, setAgents] = useState([]);

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      const [health, taskResp, agentResp] = await Promise.all([
        healthz(),
        listTasks(),
        listAgents(),
      ]);
      setService(health);
      setTasks(taskResp.items || []);
      setAgents(agentResp || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const taskColumns = [
    {
      title: "任务",
      dataIndex: "name",
      render: (value, record) => <Link to={`/task/${record.id}`}>{value || record.id}</Link>,
    },
    { title: "Agent", dataIndex: "agent_id" },
    { title: "PID", dataIndex: "target_pid", width: 90 },
    { title: "采集器", dataIndex: "collector_type", width: 130 },
    {
      title: "状态",
      dataIndex: "status",
      width: 120,
      render: (value) => <Tag color={statusColor(value)}>{value}</Tag>,
    },
  ];

  const agentColumns = [
    { title: "Agent", dataIndex: "id" },
    { title: "Host", dataIndex: "hostname" },
    { title: "IP", dataIndex: "ip_addr", width: 140 },
    {
      title: "CPU",
      width: 90,
      render: (_, record) => `${record.latest_metrics?.self?.cpu_percent ?? 0}%`,
    },
    {
      title: "RSS",
      width: 100,
      render: (_, record) => `${record.latest_metrics?.self?.rss_mb ?? 0} MB`,
    },
    {
      title: "IO",
      width: 120,
      render: (_, record) => {
        const self = record.latest_metrics?.self || {};
        return `${self.read_kb_s ?? 0}/${self.write_kb_s ?? 0} KB/s`;
      },
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 120,
      render: (value) => <Tag color={statusColor(value)}>{value}</Tag>,
    },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Space align="center" style={{ justifyContent: "space-between", width: "100%" }}>
        <Typography.Title level={4} style={{ margin: 0 }}>任务面板</Typography.Title>
        <Button icon={<ReloadOutlined />} onClick={refresh}>刷新</Button>
      </Space>

      <NLPTaskInput onTaskCreated={() => refresh()} />

      {error && <Alert type="error" message={error} showIcon />}

      <Spin spinning={loading}>
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Card>
              <Space>
                <ApiOutlined />
                <Typography.Text strong>{service?.service || "mini-drop-server"}</Typography.Text>
                <Tag>{service?.version || "unknown"}</Tag>
              </Space>
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card>
              <Typography.Text type="secondary">任务数</Typography.Text>
              <Typography.Title level={3} style={{ margin: 0 }}>{tasks.length}</Typography.Title>
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card>
              <Typography.Text type="secondary">在线 Agent</Typography.Text>
              <Typography.Title level={3} style={{ margin: 0 }}>
                {agents.filter((item) => item.status === "ONLINE").length}
              </Typography.Title>
            </Card>
          </Col>
        </Row>

        <Card title="任务列表" style={{ marginTop: 16 }}>
          <Table
            rowKey="id"
            columns={taskColumns}
            dataSource={tasks}
            pagination={{ pageSize: 8 }}
            size="middle"
          />
        </Card>

        <Card title="Agent 列表" style={{ marginTop: 16 }}>
          <Table
            rowKey="id"
            columns={agentColumns}
            dataSource={agents}
            pagination={false}
            size="middle"
          />
        </Card>
      </Spin>
    </Space>
  );
}
