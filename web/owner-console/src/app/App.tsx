import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./AppShell";
import { PlaceholderPage } from "./PlaceholderPage";
import { ApprovalDetailPage } from "../pages/ApprovalDetailPage";
import { ApprovalsPage } from "../pages/ApprovalsPage";
import { DashboardPage } from "../pages/DashboardPage";
import { DiagnosticsPage } from "../pages/DiagnosticsPage";
import { MemoryPage } from "../pages/MemoryPage";
import { TaskDetailPage } from "../pages/TaskDetailPage";
import { TasksPage } from "../pages/TasksPage";

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
          element={<TasksPage />}
        />
        <Route
          path="/owner-console/tasks/:task_id"
          element={<TaskDetailPage />}
        />
        <Route
          path="/owner-console/approvals"
          element={<ApprovalsPage />}
        />
        <Route
          path="/owner-console/approvals/:approval_id"
          element={<ApprovalDetailPage />}
        />
        <Route
          path="/owner-console/diagnostics"
          element={<DiagnosticsPage />}
        />
        <Route
          path="/owner-console/memory"
          element={<MemoryPage />}
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
