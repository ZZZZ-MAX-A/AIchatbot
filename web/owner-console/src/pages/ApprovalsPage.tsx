import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  OwnerConsoleApiError,
  ownerConsoleApi,
} from "../api/ownerConsoleApi";
import type {
  OwnerConsoleApprovalListEnvelope,
  OwnerConsoleApprovalRow,
} from "../api/ownerConsoleTypes";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";

type ApprovalStatusFilter =
  | "all"
  | "pending"
  | "approved"
  | "rejected"
  | "expired";

type ApprovalsPageState = {
  loading: boolean;
  approvals: OwnerConsoleApprovalListEnvelope | null;
  error: Error | null;
};

const statusFilters: Array<{ label: string; value: ApprovalStatusFilter }> = [
  { label: "全部", value: "all" },
  { label: "待审批", value: "pending" },
  { label: "已确认", value: "approved" },
  { label: "已拒绝", value: "rejected" },
  { label: "已过期", value: "expired" },
];

function apiErrorDescription(error: Error): string {
  if (error instanceof OwnerConsoleApiError) {
    if (error.status === 403) {
      return "无法读取主人上下文，请检查 BOT_OWNER_QQ 是否已配置。";
    }
    if (error.status === 400) {
      return "请求参数错误，请检查审批状态筛选或 limit。";
    }
    return `后端返回 HTTP ${error.status}：${error.message}`;
  }
  return error.message;
}

function approvalStatusTone(
  status: string,
): "neutral" | "success" | "warning" | "danger" {
  if (status === "approved") {
    return "success";
  }
  if (status === "rejected") {
    return "danger";
  }
  if (status === "expired") {
    return "neutral";
  }
  return "warning";
}

function formatActionability(approval: OwnerConsoleApprovalRow): string {
  if (approval.actionability.future_operation_only) {
    return "网页只读";
  }
  if (approval.actionability.blocked_reason) {
    return approval.actionability.blocked_reason;
  }
  return "仅展示";
}

function ApprovalRows({ rows }: { rows: OwnerConsoleApprovalRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="暂无审批"
        description="当前筛选条件下没有可显示的主人审批。"
      />
    );
  }

  return (
    <div className="approval-table" role="table" aria-label="审批列表">
      <div className="approval-table__row approval-table__row--head" role="row">
        <span role="columnheader">审批 ID</span>
        <span role="columnheader">任务 ID</span>
        <span role="columnheader">工具</span>
        <span role="columnheader">风险等级</span>
        <span role="columnheader">状态</span>
        <span role="columnheader">原因摘要</span>
        <span role="columnheader">操作状态</span>
        <span role="columnheader">创建时间</span>
        <span role="columnheader">详情</span>
      </div>
      {rows.map((approval) => (
        <div
          className="approval-table__row"
          role="row"
          key={approval.approval_id}
        >
          <span role="cell">{approval.approval_id}</span>
          <span role="cell">{approval.task_id}</span>
          <span role="cell">{approval.tool_name}</span>
          <span role="cell">{approval.risk_level}</span>
          <span role="cell">
            <StatusBadge
              label="状态"
              value={approval.status_label || approval.status}
              tone={approvalStatusTone(approval.status)}
            />
          </span>
          <span role="cell">{approval.reason_preview || "暂无"}</span>
          <span role="cell">{formatActionability(approval)}</span>
          <span role="cell">{approval.created_at || "未知"}</span>
          <span role="cell">
            <Link
              className="table-link"
              to={`/owner-console/approvals/${approval.approval_id}`}
            >
              查看详情
            </Link>
          </span>
        </div>
      ))}
    </div>
  );
}

export function ApprovalsPage() {
  const [status, setStatus] = useState<ApprovalStatusFilter>("all");
  const [state, setState] = useState<ApprovalsPageState>({
    loading: true,
    approvals: null,
    error: null,
  });

  const selectedStatus = status === "all" ? null : status;

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setState((current) => ({
        ...current,
        loading: true,
        error: null,
      }));
      try {
        const approvals = await ownerConsoleApi.getApprovals(
          {
            status: selectedStatus,
            limit: 20,
          },
          signal,
        );
        if (signal?.aborted) {
          return;
        }
        setState({
          loading: false,
          approvals,
          error: null,
        });
      } catch (exc) {
        if (exc instanceof DOMException && exc.name === "AbortError") {
          return;
        }
        setState({
          loading: false,
          approvals: null,
          error: exc instanceof Error ? exc : new Error("审批列表加载失败"),
        });
      }
    },
    [selectedStatus],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const rows = state.approvals?.data?.rows ?? [];
  const totalVisible = state.approvals?.data?.total_visible ?? 0;
  const activeLabel = useMemo(
    () => statusFilters.find((item) => item.value === status)?.label ?? "全部",
    [status],
  );

  return (
    <section className="page approvals-page">
      <header className="page-header">
        <div>
          <p className="page-header__eyebrow">主人控制台</p>
          <h1>审批</h1>
        </div>
        <button
          className="refresh-button"
          type="button"
          onClick={() => void load()}
          disabled={state.loading}
        >
          <RefreshCw aria-hidden="true" size={16} />
          <span>刷新审批</span>
        </button>
      </header>

      <section className="data-toolbar" aria-label="审批筛选">
        <div>
          <p>当前筛选</p>
          <strong>{activeLabel}</strong>
        </div>
        <div className="filter-tabs" role="group" aria-label="审批状态">
          {statusFilters.map((filter) => (
            <button
              key={filter.value}
              className={
                filter.value === status
                  ? "filter-tabs__item is-active"
                  : "filter-tabs__item"
              }
              type="button"
              onClick={() => setStatus(filter.value)}
            >
              {filter.label}
            </button>
          ))}
        </div>
        <StatusBadge label="可见审批" value={`${totalVisible} 个`} />
      </section>

      {state.loading ? (
        <section className="loading-panel" role="status">
          正在加载审批列表
        </section>
      ) : null}

      {state.error ? (
        <ErrorState
          title="审批列表暂不可用"
          description={apiErrorDescription(state.error)}
          details={
            state.error instanceof OwnerConsoleApiError
              ? state.error.code
              : undefined
          }
        />
      ) : null}

      {!state.error ? (
        <section className="dashboard-panel">
          <h2>审批列表</h2>
          <ApprovalRows rows={rows} />
        </section>
      ) : null}
    </section>
  );
}
