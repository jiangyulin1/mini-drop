import { useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Button, Input, Layout, Menu, message, Space, Typography } from "antd";
import {
  DashboardOutlined,
  AuditOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  KeyOutlined,
} from "@ant-design/icons";
import { getStoredApiKey, setStoredApiKey } from "../api/client";
import { COLORS, LAYOUT, SPACING } from "../theme";

const { Sider, Header, Content } = Layout;

const MENU_ITEMS = [
  { key: "/", icon: <DashboardOutlined />, label: "任务面板" },
  { key: "/audit", icon: <AuditOutlined />, label: "审计日志" },
];

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [apiKey, setApiKey] = useState(getStoredApiKey() || "");

  const selectedKey = location.pathname === "/audit" ? "/audit" : "/";

  function handleSaveKey() {
    setStoredApiKey(apiKey.trim() || null);
    message.success(apiKey.trim() ? "API Key 已保存" : "API Key 已清除");
  }

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={(v) => setCollapsed(v)}
        breakpoint="lg"
        collapsedWidth={64}
        width={LAYOUT.siderWidth}
        theme="dark"
        style={{ overflow: "auto", height: "100vh", position: "sticky", top: 0, left: 0 }}
      >
        {/* Logo */}
        <div
          style={{
            height: LAYOUT.headerHeight,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderBottom: "1px solid rgba(255,255,255,0.15)",
          }}
        >
          <Typography.Text
            strong
            style={{
              color: "#fff",
              fontSize: collapsed ? 16 : 18,
              letterSpacing: 1,
              whiteSpace: "nowrap",
            }}
          >
            {collapsed ? "MD" : "Mini-Drop"}
          </Typography.Text>
        </div>

        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={MENU_ITEMS}
          onClick={({ key }) => navigate(key)}
          style={{ marginTop: SPACING.sm }}
        />
      </Sider>

      <Layout>
        {/* 顶栏 */}
        <Header
          style={{
            height: LAYOUT.headerHeight,
            lineHeight: `${LAYOUT.headerHeight}px`,
            padding: `0 ${SPACING.lg}px`,
            background: COLORS.cardBackground,
            borderBottom: `1px solid ${COLORS.border}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            position: "sticky",
            top: 0,
            zIndex: 10,
          }}
        >
          <Typography.Text strong style={{ fontSize: 16, whiteSpace: "nowrap" }}>
            Mini-Drop 性能诊断平台
          </Typography.Text>

          <Space size="small" wrap style={{ flexShrink: 0 }}>
            <Input.Password
              placeholder="API Key（可选）"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              onPressEnter={handleSaveKey}
              size="small"
              style={{ width: 200, maxWidth: "40vw" }}
              prefix={<KeyOutlined style={{ color: COLORS.textSecondary }} />}
            />
            <Button size="small" type="primary" onClick={handleSaveKey}>
              保存
            </Button>
          </Space>
        </Header>

        {/* 内容 */}
        <Content
          style={{
            margin: SPACING.lg,
            padding: SPACING.xl,
            background: COLORS.cardBackground,
            borderRadius: 8,
            minHeight: `calc(100vh - ${LAYOUT.headerHeight}px - ${SPACING.lg * 2}px)`,
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
