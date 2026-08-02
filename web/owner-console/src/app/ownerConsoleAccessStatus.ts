import type {
  OwnerConsoleHealth,
  OwnerConsoleRoutesEnvelope,
} from "../api/ownerConsoleTypes";

export type OwnerConsoleAccessTone =
  | "neutral"
  | "success"
  | "warning"
  | "danger";

export type OwnerConsoleSnapshotAccessState =
  | "unknown"
  | "read_only"
  | "unsafe";

export type OwnerConsoleWebWriteState =
  | "unknown"
  | "closed"
  | "approval_only"
  | "registered_actions"
  | "unsafe";

export type OwnerConsoleAccessStatus = {
  snapshot: {
    state: OwnerConsoleSnapshotAccessState;
    value: string;
    tone: OwnerConsoleAccessTone;
    route: string;
    detail: string;
  };
  webWrite: {
    state: OwnerConsoleWebWriteState;
    value: string;
    tone: OwnerConsoleAccessTone;
    route: string;
    detail: string;
  };
};

export function buildOwnerConsoleAccessStatus(
  health: OwnerConsoleHealth | null,
  routes: OwnerConsoleRoutesEnvelope | null,
): OwnerConsoleAccessStatus {
  const routeContract = routes?.data ?? null;

  const snapshot =
    health === null || routeContract === null
      ? {
          state: "unknown" as const,
          value: "检查中",
          tone: "neutral" as const,
          route: "/owner-console/diagnostics",
          detail: "尚未取得健康状态与路由合同。",
        }
      : health.snapshot_read_only === true && routes?.read_only === true
        ? {
            state: "read_only" as const,
            value: "只读",
            tone: "success" as const,
            route: "/owner-console/diagnostics",
            detail: "任务、诊断、记忆和配置快照保持只读。",
          }
        : {
            state: "unsafe" as const,
            value: "异常",
            tone: "danger" as const,
            route: "/owner-console/diagnostics",
            detail: "快照读取边界与路由合同不一致，请查看诊断证据。",
          };

  if (health === null || routeContract === null) {
    return {
      snapshot,
      webWrite: {
        state: "unknown",
        value: "检查中",
        tone: "neutral",
        route: "/owner-console/settings",
        detail: "尚未取得网页写入安全合同。",
      },
    };
  }

  const configurationWriteClosed =
    health.configuration_write_enabled === false;
  const approvalRoutesEnabled =
    routeContract.approval_action_routes_enabled === true;
  const taskRoutesEnabled = routeContract.task_action_routes_enabled === true;
  const registeredActionsEnabled =
    health.approval_actions_enabled === approvalRoutesEnabled &&
    health.task_actions_enabled === taskRoutesEnabled &&
    (approvalRoutesEnabled || taskRoutesEnabled) &&
    health.web_write_enabled === true &&
    health.business_data_write_enabled === true &&
    configurationWriteClosed;
  const approvalOnly =
    registeredActionsEnabled && approvalRoutesEnabled && !taskRoutesEnabled;
  const fullyClosed =
    health.approval_actions_enabled === false &&
    health.task_actions_enabled === false &&
    health.web_write_enabled === false &&
    health.business_data_write_enabled === false &&
    configurationWriteClosed &&
    approvalRoutesEnabled === false &&
    taskRoutesEnabled === false;

  if (approvalOnly) {
    return {
      snapshot,
      webWrite: {
        state: "approval_only",
        value: "仅审批",
        tone: "warning",
        route: "/owner-console/approvals?status=pending",
        detail: "只开放注册审批的批准与拒绝；配置写入仍关闭。",
      },
    };
  }


  if (registeredActionsEnabled) {
    return {
      snapshot,
      webWrite: {
        state: "registered_actions",
        value: "受限操作",
        tone: "warning",
        route: taskRoutesEnabled
          ? "/owner-console/tasks?status=pending"
          : "/owner-console/approvals?status=pending",
        detail: "只开放注册审批与单笔待处理任务取消；配置写入、工具执行、审批恢复和自动重试仍关闭。",
      },
    };
  }

  if (fullyClosed) {
    return {
      snapshot,
      webWrite: {
        state: "closed",
        value: "已关闭",
        tone: "success",
        route: "/owner-console/settings",
        detail: "网页业务写入与审批动作均未开放。",
      },
    };
  }

  return {
    snapshot,
    webWrite: {
      state: "unsafe",
      value: "异常",
      tone: "danger",
      route: "/owner-console/settings",
      detail: "网页写入状态超出“完全关闭”或“注册受限操作”安全合同。",
    },
  };
}
