import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  OwnerConsoleApiError,
  ownerConsoleApi,
} from "../api/ownerConsoleApi";
import type {
  OwnerConsoleTaskListEnvelope,
  OwnerConsoleTaskRow,
} from "../api/ownerConsoleTypes";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";

type TaskStatusFilter = "all" | "pending" | "done" | "failed" | "cancelled";
type TaskWorkTypeFilter =
  | "all"
  | "development_context_report"
  | "system_diagnostics_report"
  | "external_read_report";

type TasksPageState = {
  loading: boolean;
  tasks: OwnerConsoleTaskListEnvelope | null;
  error: Error | null;
};

const statusFilters: Array<{ label: string; value: TaskStatusFilter }> = [
  { label: "全部", value: "all" },
  { label: "待处理", value: "pending" },
  { label: "已完成", value: "done" },
  { label: "失败", value: "failed" },
  { label: "已取消", value: "cancelled" },
];

const workTypeFilters: Array<{ label: string; value: TaskWorkTypeFilter }> = [
  { label: "全部类型", value: "all" },
  { label: "研发上下文", value: "development_context_report" },
  { label: "系统诊断", value: "system_diagnostics_report" },
  { label: "联网查询", value: "external_read_report" },
];

function workTypeLabel(workType: string): string {
  return workTypeFilters.find((item) => item.value === workType)?.label ?? "普通任务";
}

function apiErrorDescription(error: Error): string {
  if (error instanceof OwnerConsoleApiError) {
    if (error.status === 403) {
      return "无法读取主人上下文，请检查 BOT_OWNER_QQ 是否已配置。";
    }
    if (error.status === 400) {
      return "请求参数错误，请检查任务状态筛选或 limit。";
    }
    return `后端返回 HTTP ${error.status}：${error.message}`;
  }
  return error.message;
}

function taskStatusTone(status: string): "neutral" | "success" | "warning" | "danger" {
  if (status === "done") {
    return "success";
  }
  if (status === "failed") {
    return "danger";
  }
  if (status === "cancelled") {
    return "neutral";
  }
  return "warning";
}

function formatPendingApprovals(task: OwnerConsoleTaskRow): string {
  if (task.pending_approval_ids.length === 0) {
    return "无";
  }
  return task.pending_approval_ids.join(", ");
}

function TaskRows({ rows }: { rows: OwnerConsoleTaskRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="暂无任务"
        description="当前筛选条件下没有可显示的主人任务。"
      />
    );
  }

  return (
    <div className="task-table" role="table" aria-label="任务列表">
      <div className="task-table__row task-table__row--head" role="row">
        <span role="columnheader">任务 ID</span>
        <span role="columnheader">目标摘要</span>
        <span role="columnheader">工作类型</span>
        <span role="columnheader">状态</span>
        <span role="columnheader">最近事件</span>
        <span role="columnheader">待审批</span>
        <span role="columnheader">下一步</span>
        <span role="columnheader">详情</span>
      </div>
      {rows.map((task) => (
        <div className="task-table__row" role="row" key={task.task_id}>
          <span role="cell">{task.task_id}</span>
          <span role="cell">{task.goal_preview || task.title}</span>
          <span role="cell">
            <StatusBadge label="类型" value={workTypeLabel(task.work_type)} />
          </span>
          <span role="cell">
            <StatusBadge
              label="状态"
              value={task.status_label || task.status}
              tone={taskStatusTone(task.status)}
            />
          </span>
          <span role="cell">
            {task.latest_event_summary || task.latest_event_kind || "暂无"}
          </span>
          <span role="cell">{formatPendingApprovals(task)}</span>
          <span role="cell">{task.next_action || "暂无"}</span>
          <span role="cell">
            <Link className="table-link" to={`/owner-console/tasks/${task.task_id}`}>
              查看详情
            </Link>
          </span>
        </div>
      ))}
    </div>
  );
}

export function TasksPage() {
  const [status, setStatus] = useState<TaskStatusFilter>("all");
  const [workType, setWorkType] = useState<TaskWorkTypeFilter>("all");
  const [state, setState] = useState<TasksPageState>({
    loading: true,
    tasks: null,
    error: null,
  });

  const selectedStatus = status === "all" ? null : status;
  const selectedWorkType = workType === "all" ? null : workType;

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setState((current) => ({
        ...current,
        loading: true,
        error: null,
      }));
      try {
        const tasks = await ownerConsoleApi.getTasks(
          {
            status: selectedStatus,
            work_type: selectedWorkType,
            limit: 20,
          },
          signal,
        );
        if (signal?.aborted) {
          return;
        }
        setState({
          loading: false,
          tasks,
          error: null,
        });
      } catch (exc) {
        if (exc instanceof DOMException && exc.name === "AbortError") {
          return;
        }
        setState({
          loading: false,
          tasks: null,
          error: exc instanceof Error ? exc : new Error("任务列表加载失败"),
        });
      }
    },
    [selectedStatus, selectedWorkType],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const rows = state.tasks?.data?.rows ?? [];
  const totalVisible = state.tasks?.data?.total_visible ?? 0;
  const activeLabel = useMemo(
    () => statusFilters.find((item) => item.value === status)?.label ?? "全部",
    [status],
  );
  const activeWorkTypeLabel = useMemo(
    () => workTypeFilters.find((item) => item.value === workType)?.label ?? "全部类型",
    [workType],
  );

  return (
    <section className="page tasks-page">
      <header className="page-header">
        <div>
          <p className="page-header__eyebrow">主人控制台</p>
          <h1>任务</h1>
        </div>
        <button
          className="refresh-button"
          type="button"
          onClick={() => void load()}
          disabled={state.loading}
        >
          <RefreshCw aria-hidden="true" size={16} />
          <span>刷新任务</span>
        </button>
      </header>

      <section className="data-toolbar" aria-label="任务筛选">
        <div>
          <p>当前筛选</p>
          <strong>{activeLabel} · {activeWorkTypeLabel}</strong>
        </div>
        <div className="filter-tabs" role="group" aria-label="任务工作类型">
          {workTypeFilters.map((filter) => (
            <button
              key={filter.value}
              className={
                filter.value === workType
                  ? "filter-tabs__item is-active"
                  : "filter-tabs__item"
              }
              type="button"
              onClick={() => setWorkType(filter.value)}
            >
              {filter.label}
            </button>
          ))}
        </div>
        <div className="filter-tabs" role="group" aria-label="任务状态">
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
        <StatusBadge label="可见任务" value={`${totalVisible} 个`} />
      </section>

      {state.loading ? (
        <section className="loading-panel" role="status">
          正在加载任务列表
        </section>
      ) : null}

      {state.error ? (
        <ErrorState
          title="任务列表暂不可用"
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
          <h2>任务列表</h2>
          <TaskRows rows={rows} />
        </section>
      ) : null}
    </section>
  );
}
