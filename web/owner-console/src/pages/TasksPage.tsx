import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

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
type TaskCategoryFilter =
  | "all"
  | "awaiting_approval"
  | "ordinary_pending"
  | "stale_residual";

type TasksPageState = {
  loading: boolean;
  tasks: OwnerConsoleTaskListEnvelope | null;
  error: Error | null;
};

const DEFAULT_TASK_PAGE_SIZE = 20;
const TASK_PAGE_SIZES = [10, 20, 50] as const;

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

const categoryFilters: Array<{ label: string; value: TaskCategoryFilter }> = [
  { label: "全部处理分类", value: "all" },
  { label: "等待审批", value: "awaiting_approval" },
  { label: "普通待处理", value: "ordinary_pending" },
  { label: "旧任务残留", value: "stale_residual" },
];

function taskStatusFilterFromSearch(value: string | null): TaskStatusFilter {
  return statusFilters.some((filter) => filter.value === value)
    ? (value as TaskStatusFilter)
    : "all";
}

function taskWorkTypeFilterFromSearch(value: string | null): TaskWorkTypeFilter {
  return workTypeFilters.some((filter) => filter.value === value)
    ? (value as TaskWorkTypeFilter)
    : "all";
}

function taskCategoryFilterFromSearch(value: string | null): TaskCategoryFilter {
  return categoryFilters.some((filter) => filter.value === value)
    ? (value as TaskCategoryFilter)
    : "all";
}

function positivePageFromSearch(value: string | null): number {
  if (value === null || !/^\d+$/.test(value)) {
    return 1;
  }
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}

function pageSizeFromSearch(value: string | null): number {
  if (value === null || !/^\d+$/.test(value)) {
    return DEFAULT_TASK_PAGE_SIZE;
  }
  const parsed = Number(value);
  return TASK_PAGE_SIZES.includes(parsed as (typeof TASK_PAGE_SIZES)[number])
    ? parsed
    : DEFAULT_TASK_PAGE_SIZE;
}

function visiblePageNumbers(currentPage: number, totalPages: number): number[] {
  const count = Math.min(5, Math.max(1, totalPages));
  const start = Math.max(1, Math.min(currentPage - 2, totalPages - count + 1));
  return Array.from({ length: count }, (_, index) => start + index);
}

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

function taskProcessingTone(
  category: string,
): "neutral" | "success" | "warning" | "danger" {
  if (category === "stale_residual" || category === "failed") {
    return "danger";
  }
  if (category === "awaiting_approval" || category === "ordinary_pending") {
    return "warning";
  }
  if (category === "closed") {
    return "success";
  }
  return "neutral";
}

function taskProcessLabel(task: OwnerConsoleTaskRow): string {
  if (task.processing_category === "stale_residual") {
    return "处理收口";
  }
  if (task.processing_category === "awaiting_approval") {
    return "处理审批";
  }
  return "处理任务";
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
        <span role="columnheader">处理</span>
        <span role="columnheader">目标摘要</span>
        <span role="columnheader">工作类型</span>
        <span role="columnheader">状态</span>
        <span role="columnheader">处理分类</span>
        <span role="columnheader">处理说明</span>
        <span role="columnheader">最近事件</span>
        <span role="columnheader">待审批</span>
      </div>
      {rows.map((task) => (
        <div className="task-table__row" role="row" key={task.task_id}>
          <span role="cell">
            <Link
              className="table-link"
              to={`/owner-console/tasks/${task.task_id}`}
              aria-label={`进入任务 #${task.task_id} 详情`}
            >
              #{task.task_id}
            </Link>
          </span>
          <span role="cell">
            <Link
              className={
                task.processing_category === "stale_residual"
                  ? "task-process-link task-process-link--danger"
                  : task.processing_category === "awaiting_approval"
                    ? "task-process-link task-process-link--warning"
                    : "task-process-link"
              }
              to={`/owner-console/tasks/${task.task_id}`}
              aria-label={`${taskProcessLabel(task)} #${task.task_id}`}
            >
              {taskProcessLabel(task)}
            </Link>
          </span>
          <span role="cell">
            <Link
              className="task-goal-link"
              to={`/owner-console/tasks/${task.task_id}`}
            >
              {task.goal_preview || task.title}
            </Link>
          </span>
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
            <StatusBadge
              label="分类"
              value={task.processing_label || "未分类"}
              tone={taskProcessingTone(task.processing_category)}
            />
          </span>
          <span
            role="cell"
            className={
              task.processing_category === "stale_residual"
                ? "task-processing-detail task-processing-detail--danger"
                : "task-processing-detail"
            }
          >
            <span className="task-cell-clamp">
              {task.processing_detail || task.next_action || "暂无"}
            </span>
          </span>
          <span role="cell">
            <span className="task-cell-clamp">
              {task.latest_event_summary || task.latest_event_kind || "暂无"}
            </span>
          </span>
          <span role="cell">{formatPendingApprovals(task)}</span>
        </div>
      ))}
    </div>
  );
}

export function TasksPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const status = taskStatusFilterFromSearch(searchParams.get("status"));
  const workType = taskWorkTypeFilterFromSearch(searchParams.get("work_type"));
  const category = taskCategoryFilterFromSearch(searchParams.get("category"));
  const page = positivePageFromSearch(searchParams.get("page"));
  const pageSize = pageSizeFromSearch(searchParams.get("page_size"));
  const [state, setState] = useState<TasksPageState>({
    loading: true,
    tasks: null,
    error: null,
  });

  const selectedStatus = status === "all" ? null : status;
  const selectedWorkType = workType === "all" ? null : workType;
  const selectedCategory = category === "all" ? null : category;

  const updateFilter = useCallback(
    (
      key: "status" | "work_type" | "category",
      value: TaskStatusFilter | TaskWorkTypeFilter | TaskCategoryFilter,
    ) => {
      const next = new URLSearchParams(searchParams);
      if (value === "all") {
        next.delete(key);
      } else {
        next.set(key, value);
      }
      next.delete("page");
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const updatePage = useCallback(
    (nextPage: number) => {
      const next = new URLSearchParams(searchParams);
      if (nextPage <= 1) {
        next.delete("page");
      } else {
        next.set("page", String(nextPage));
      }
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const updatePageSize = useCallback(
    (nextPageSize: number) => {
      const next = new URLSearchParams(searchParams);
      if (nextPageSize === DEFAULT_TASK_PAGE_SIZE) {
        next.delete("page_size");
      } else {
        next.set("page_size", String(nextPageSize));
      }
      next.delete("page");
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

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
            category: selectedCategory,
            page,
            page_size: pageSize,
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
    [selectedStatus, selectedWorkType, selectedCategory, page, pageSize],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const rows = state.tasks?.data?.rows ?? [];
  const totalVisible = state.tasks?.data?.total_visible ?? 0;
  const totalMatching = state.tasks?.data?.total_matching ?? 0;
  const resolvedPage = state.tasks?.data?.page ?? page;
  const totalPages = state.tasks?.data?.total_pages ?? 1;
  const hasPrevious = state.tasks?.data?.has_previous ?? false;
  const hasNext = state.tasks?.data?.has_next ?? false;
  const pageNumbers = useMemo(
    () => visiblePageNumbers(resolvedPage, totalPages),
    [resolvedPage, totalPages],
  );

  const activeLabel = useMemo(
    () => statusFilters.find((item) => item.value === status)?.label ?? "全部",
    [status],
  );
  const activeWorkTypeLabel = useMemo(
    () => workTypeFilters.find((item) => item.value === workType)?.label ?? "全部类型",
    [workType],
  );
  const activeCategoryLabel = useMemo(
    () => categoryFilters.find((item) => item.value === category)?.label ?? "全部处理分类",
    [category],
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
          <strong>{activeLabel} · {activeWorkTypeLabel} · {activeCategoryLabel}</strong>
        </div>
        <div className="filter-tabs" role="group" aria-label="任务处理分类">
          {categoryFilters.map((filter) => (
            <button
              key={filter.value}
              className={
                filter.value === category
                  ? "filter-tabs__item is-active"
                  : "filter-tabs__item"
              }
              type="button"
              onClick={() => updateFilter("category", filter.value)}
            >
              {filter.label}
            </button>
          ))}
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
              onClick={() => updateFilter("work_type", filter.value)}
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
              onClick={() => updateFilter("status", filter.value)}
            >
              {filter.label}
            </button>
          ))}
        </div>
        <div className="task-counts" aria-label="任务数量">
          <StatusBadge label="符合筛选" value={`${totalMatching} 个`} />
          <StatusBadge label="当前页" value={`${totalVisible} 个`} />
        </div>
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
          <p className="panel-note task-list-entry-note">
            点击每行左侧的任务编号、“处理任务”或目标摘要即可进入详情；取消任务需要在详情页再次确认。
          </p>
          <TaskRows rows={rows} />
          <nav className="task-pagination" aria-label="任务分页">
            <div className="task-pagination__summary" aria-live="polite">
              第 {resolvedPage} / {totalPages} 页，共 {totalMatching} 个任务
            </div>
            <div className="task-pagination__controls">
              <button
                className="task-pagination__button"
                type="button"
                onClick={() => updatePage(resolvedPage - 1)}
                disabled={!hasPrevious || state.loading}
              >
                上一页
              </button>
              <div className="task-pagination__pages" role="group" aria-label="页码">
                {pageNumbers.map((pageNumber) => (
                  <button
                    key={pageNumber}
                    className={
                      pageNumber === resolvedPage
                        ? "task-pagination__button is-active"
                        : "task-pagination__button"
                    }
                    type="button"
                    aria-current={pageNumber === resolvedPage ? "page" : undefined}
                    aria-label={`第 ${pageNumber} 页`}
                    onClick={() => updatePage(pageNumber)}
                    disabled={state.loading}
                  >
                    {pageNumber}
                  </button>
                ))}
              </div>
              <button
                className="task-pagination__button"
                type="button"
                onClick={() => updatePage(resolvedPage + 1)}
                disabled={!hasNext || state.loading}
              >
                下一页
              </button>
              <label className="task-pagination__page-size">
                <span>每页</span>
                <select
                  aria-label="每页任务数"
                  value={pageSize}
                  onChange={(event) => updatePageSize(Number(event.target.value))}
                  disabled={state.loading}
                >
                  {TASK_PAGE_SIZES.map((size) => (
                    <option key={size} value={size}>
                      {size} 个
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </nav>
        </section>
      ) : null}
    </section>
  );
}
