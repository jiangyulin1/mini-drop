import { Layout, Typography } from "antd";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import {
  DashboardOutlined,
  AuditOutlined,
} from "@ant-design/icons";
import { useState } from "react";

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: "/", icon: <DashboardOutlined />, label: "任务面板" },
  { key: "/audit", icon: <AuditOutlined />, label: "审计日志" },
];

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed] = useState(false);

  const selectedKey = location.pathname.startsWith("/task/")
    ? "/"
    : location.pathname;

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        collapsible
        collapsed={collapsed}
        trigger={null}
        theme="dark"
        width={200}
      >
        <div
          style={{
            height: 48,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Typography.Text
            strong
            style={{ color: "white", fontSize: collapsed ? 14 : 16 }}
          >
            {collapsed ? "MD" : "Mini-Drop"}
          </Typography.Text>
        </div>
        {menuItems.map((item) => (
          <div
            key={item.key}
            onClick={() => navigate(item.key)}
            style={{
              padding: "12px 24px",
              cursor: "pointer",
              color: selectedKey === item.key ? "#1677ff" : "rgba(255,255,255,0.65)",
              background: selectedKey === item.key ? "rgba(22,119,255,0.1)" : "transparent",
              display: "flex",
              alignItems: "center",
              gap: 10,
              fontSize: 14,
            }}
          >
            {item.icon}
            {!collapsed && item.label}
          </div>
        ))}
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#fff",
            padding: "0 24px",
            borderBottom: "1px solid #f0f0f0",
            display: "flex",
            alignItems: "center",
          }}
        >
          <Typography.Text strong style={{ fontSize: 16 }}>
            Mini-Drop 性能诊断平台
          </Typography.Text>
        </Header>
        <Content style={{ margin: 16, padding: 24, background: "#fff", borderRadius: 8 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
