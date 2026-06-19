import { useEffect, useState, useCallback } from "react";
import { Card, Skeleton, Space, Table, Tag, Typography, Button } from "antd";
import { ReloadOutlined, AuditOutlined } from "@ant-design/icons";
import { listAuditLogs } from "../api/client";
import ErrorAlert from "../components/ErrorAlert";
import { COLORS, SPACING } from "../theme";

export default function AuditLogs() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [logs, setLogs] = useState([]);

  const load = useCallback(async () => {
    setError("");
    try {
      setLogs(await listAuditLogs());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const columns = [
    {
      title: "事件",
      dataIndex: "event_type",
      width: 180,
      render: (value) => {
        const colorMap = {
          TASK_CREATED: "blue",
          AGENT_ONLINE: "green",
          AGENT_OFFLINE: "red",
          TASK_DONE: "green",
          TASK_FAILED: "red",
        };
        return <Tag color={colorMap[value] || "default"}>{value}</Tag>;
      },
    },
    { title: "消息", dataIndex: "message", ellipsis: true },
    { title: "Agent", dataIndex: "agent_id", width: 140, ellipsis: true },
    { title: "任务", dataIndex: "task_id", width: 200, ellipsis: true },
    { title: "时间", dataIndex: "created_at", width: 220 },
  ];

  if (loading) {
    return (
      <Space direction="vertical" size={SPACING.lg} style={{ width: "100%" }}>
        <Skeleton.Input active size="small" style={{ width: 140 }} />
        <Card size="small">
          <Skeleton active paragraph={{ rows: 8 }} />
        </Card>
      </Space>
    );
  }

  return (
    <Space direction="vertical" size={SPACING.lg} style={{ width: "100%" }}>
      {/* 页头 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <Space align="center">
          <AuditOutlined style={{ fontSize: 20, color: COLORS.primary }} />
          <Typography.Title level={4} style={{ margin: 0 }}>
            审计日志
          </Typography.Title>
        </Space>
        <Button icon={<ReloadOutlined />} onClick={load}>
          刷新
        </Button>
      </div>

      <ErrorAlert error={error} onClose={() => setError("")} />

      <Card size="small">
        <Table
          rowKey={(record, index) => `${record.event_type}-${record.created_at}-${index}`}
          columns={columns}
          dataSource={logs}
          pagination={{ pageSize: 15, showSizeChanger: false }}
          size="middle"
          scroll={{ x: 800 }}
          locale={{ emptyText: "暂无审计日志记录" }}
        />
      </Card>
    </Space>
  );
}
