import { useEffect, useState } from "react";
import { Alert, Card, Space, Spin, Table, Tag, Typography } from "antd";
import { listAuditLogs } from "../api/client";

export default function AuditLogs() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError("");
      try {
        setLogs(await listAuditLogs());
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const columns = [
    { title: "事件", dataIndex: "event_type", width: 180, render: (value) => <Tag>{value}</Tag> },
    { title: "消息", dataIndex: "message" },
    { title: "Agent", dataIndex: "agent_id", width: 180 },
    { title: "任务", dataIndex: "task_id", width: 220 },
    { title: "时间", dataIndex: "created_at", width: 220 },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Typography.Title level={4} style={{ margin: 0 }}>审计日志</Typography.Title>
      {error && <Alert type="error" message={error} showIcon />}
      <Spin spinning={loading}>
        <Card>
          <Table
            rowKey={(record, index) => `${record.event_type}-${record.created_at}-${index}`}
            columns={columns}
            dataSource={logs}
            pagination={{ pageSize: 10 }}
            size="middle"
          />
        </Card>
      </Spin>
    </Space>
  );
}
