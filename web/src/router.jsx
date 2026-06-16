import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import AuditLogs from "./pages/AuditLogs";
import Dashboard from "./pages/Dashboard";
import TaskResult from "./pages/TaskResult";

export default function Router() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/audit" element={<AuditLogs />} />
          <Route path="/task/:taskId" element={<TaskResult />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
