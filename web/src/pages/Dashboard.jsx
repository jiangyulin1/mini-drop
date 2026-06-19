import { useEffect, useState, useMemo } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Row,
  Skeleton,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from "antd";
import {
  ApiOutlined,
  ReloadOutlined,
  DashboardOutlined,
  CloudServerOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
} from "@ant-design/icons";
import { Link } from "react-router-dom";
import { healthz, listAgents, listTasks } from "../api/client";
import NLPTaskInput from "../components/NLPTaskInput";
import StatusTag from "../components/StatusTag";
import ErrorAlert from "../components/ErrorAlert";
import usePolling from "../hooks/usePolling";
import { COLORS, SPACING } from "../theme";

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [service, setService] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [agents, setAgents] = useState([]);

  async function refresh() {
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

  // 每 10 秒自动刷新
  const { isPolling } = usePolling(refresh, { interval: 10000, enabled: !loading });

  // ── 统计 ──────────────────────────────────────────────

  const stats = useMemo(() => {
    const doneCount = tasks.filter((t) => t.status === "DONE").length;
    const failedCount = tasks.filter((t) => t.status === "FAILED").length;
    const activeCount = tasks.filter(
      (t) =>
        t.status === "RUNNING" ||
        t.status === "ANALYZING" ||
        t.status === "UPLOADING" ||
        t.status === "PENDING"
    ).length;
    const onlineCount = agents.filter((a) => a.status === "ONLINE").length;
    const offlineCount = agents.filter((a) => a.status === "OFFLINE").length;

    return { doneCount, failedCount, activeCount, onlineCount, offlineCount, total: tasks.length };
  }, [tasks, agents]);

  // ── 表格列定义 ────────────────────────────────────────

  const taskColumns = useMemo(
    () => [
      {
        title: "任务",
        dataIndex: "name",
        ellipsis: true,
        render: (value, record) => (
          <Link to={`/task/${record.id}`}>{value || record.id}</Link>
        ),
      },
      { title: "Agent", dataIndex: "agent_id", width: 140, ellipsis: true },
      { title: "PID", dataIndex: "target_pid", width: 80 },
      { title: "采集器", dataIndex: "collector_type", width: 110 },
      {
        title: "状态",
        dataIndex: "status",
        width: 110,
        render: (value) => <StatusTag status={value} />,
      },
    ],
    []
  );

  const agentColumns = useMemo(
    () => [
      { title: "Agent", dataIndex: "id", width: 140, ellipsis: true },
      { title: "Host", dataIndex: "hostname", width: 120, ellipsis: true },
      { title: "IP", dataIndex: "ip_addr", width: 140 },
      {
        title: "CPU",
        width: 80,
        render: (_, record) =>
          `${record.latest_metrics?.self?.cpu_percent ?? 0}%`,
      },
      {
        title: "RSS",
        width: 90,
        render: (_, record) =>
          `${record.latest_metrics?.self?.rss_mb ?? 0} MB`,
      },
      {
        title: "IO",
        width: 110,
        render: (_, record) => {
          const s = record.latest_metrics?.self || {};
          return `${s.read_kb_s ?? 0}/${s.write_kb_s ?? 0} KB/s`;
        },
      },
      {
        title: "状态",
        dataIndex: "status",
        width: 100,
        render: (value) => <StatusTag status={value} />,
      },
    ],
    []
  );

  // ── 加载骨架屏 ────────────────────────────────────────

  if (loading) {
    return (
      <Space direction="vertical" size={SPACING.lg} style={{ width: "100%" }}>
        <Skeleton.Input active size="small" style={{ width: 160 }} />
        <Row gutter={SPACING.lg}>
          {[1, 2, 3].map((i) => (
            <Col xs={24} md={8} key={i}>
              <Card size="small">
                <Skeleton active paragraph={{ rows: 1 }} />
              </Card>
            </Col>
          ))}
        </Row>
        <Card size="small">
          <Skeleton active paragraph={{ rows: 5 }} />
        </Card>
        <Card size="small">
          <Skeleton active paragraph={{ rows: 3 }} />
        </Card>
      </Space>
    );
  }

  // ── 渲染 ──────────────────────────────────────────────

  return (
    <Space direction="vertical" size={SPACING.lg} style={{ width: "100%" }}>
      {/* 页头 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <Space align="center">
          <DashboardOutlined style={{ fontSize: 20, color: COLORS.primary }} />
          <Typography.Title level={4} style={{ margin: 0 }}>
            任务面板
          </Typography.Title>
        </Space>
        <Space>
          {isPolling && (
            <Tag icon={<SyncOutlined spin />} color="processing">
              每 10s 自动刷新
            </Tag>
          )}
          <Button icon={<ReloadOutlined />} onClick={refresh}>
            刷新
          </Button>
        </Space>
      </div>

      {/* NLP 输入 */}
      <NLPTaskInput onTaskCreated={() => refresh()} />

      <ErrorAlert error={error} onClose={() => setError("")} />

      {/* 统计卡片 */}
      <Row gutter={SPACING.lg}>
        <Col xs={24} md={8}>
          <Card size="small" style={{ background: COLORS.primaryBg }}>
            <Space>
              <ApiOutlined style={{ color: COLORS.primary }} />
              <Typography.Text strong>{service?.service || "mini-drop-server"}</Typography.Text>
              <Tag color="blue">{service?.version || "unknown"}</Tag>
            </Space>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card size="small">
            <Space direction="vertical" style={{ width: "100%" }} size={4}>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                <CloudServerOutlined /> 任务数
              </Typography.Text>
              <Typography.Title level={3} style={{ margin: 0, fontSize: 28 }}>
                {stats.total}
              </Typography.Title>
              <Space size={[4, 4]} wrap>
                <Tag icon={<CheckCircleOutlined />} color="green">
                  {stats.doneCount} 完成
                </Tag>
                <Tag icon={<CloseCircleOutlined />} color="red">
                  {stats.failedCount} 失败
                </Tag>
                <Tag icon={<SyncOutlined spin={stats.activeCount > 0} />} color="blue">
                  {stats.activeCount} 进行中
                </Tag>
              </Space>
            </Space>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card size="small">
            <Space direction="vertical" style={{ width: "100%" }} size={4}>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                <CloudServerOutlined /> Agent 在线
              </Typography.Text>
              <Typography.Title level={3} style={{ margin: 0, fontSize: 28 }}>
                {stats.onlineCount}
              </Typography.Title>
              <Space size={[4, 4]} wrap>
                <Badge status="success" text={`${stats.onlineCount} 在线`} />
                <Badge status="default" text={`${stats.offlineCount} 离线`} />
              </Space>
            </Space>
          </Card>
        </Col>
      </Row>

      {/* 任务列表 */}
      <Card title="任务列表" size="small">
        <Table
          rowKey="id"
          columns={taskColumns}
          dataSource={tasks}
          pagination={{ pageSize: 8, showSizeChanger: false }}
          size="middle"
          scroll={{ x: 600 }}
          locale={{ emptyText: "暂无任务，使用上方 NLP 输入或 API 创建第一个任务" }}
        />
      </Card>

      {/* Agent 列表 */}
      <Card title="Agent 列表" size="small">
        <Table
          rowKey="id"
          columns={agentColumns}
          dataSource={agents}
          pagination={false}
          size="middle"
          scroll={{ x: 700 }}
          locale={{ emptyText: "暂无 Agent 注册，请在目标主机上启动 Agent" }}
        />
      </Card>
    </Space>
  );
}
