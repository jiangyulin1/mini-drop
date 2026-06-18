import { Suspense, lazy } from "react";
import { Spin } from "antd";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import Dashboard from "./pages/Dashboard";

const AuditLogs = lazy(() => import("./pages/AuditLogs"));
const TaskResult = lazy(() => import("./pages/TaskResult"));

export default function Router() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route
            path="/audit"
            element={(
              <Suspense fallback={<Spin />}>
                <AuditLogs />
              </Suspense>
            )}
          />
          <Route
            path="/task/:taskId"
            element={(
              <Suspense fallback={<Spin />}>
                <TaskResult />
              </Suspense>
            )}
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
