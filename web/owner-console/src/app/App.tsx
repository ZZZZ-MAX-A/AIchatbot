import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./AppShell";
import { PlaceholderPage } from "./PlaceholderPage";
import { DashboardPage } from "../pages/DashboardPage";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/owner-console" replace />} />
        <Route path="/owner-console" element={<DashboardPage />} />
        <Route
          path="/owner-console/dashboard"
          element={<Navigate to="/owner-console" replace />}
        />
        <Route
          path="/owner-console/tasks"
          element={<PlaceholderPage title="任务" />}
        />
        <Route
          path="/owner-console/tasks/:task_id"
          element={<PlaceholderPage title="任务详情" />}
        />
        <Route
          path="/owner-console/approvals"
          element={<PlaceholderPage title="审批" />}
        />
        <Route
          path="/owner-console/approvals/:approval_id"
          element={<PlaceholderPage title="审批详情" />}
        />
        <Route
          path="/owner-console/diagnostics"
          element={<PlaceholderPage title="诊断" />}
        />
        <Route
          path="/owner-console/memory"
          element={<PlaceholderPage title="记忆" />}
        />
        <Route
          path="/owner-console/access-control"
          element={<PlaceholderPage title="访问控制" />}
        />
        <Route
          path="/owner-console/settings"
          element={<PlaceholderPage title="设置" />}
        />
        <Route path="*" element={<Navigate to="/owner-console" replace />} />
      </Route>
    </Routes>
  );
}
