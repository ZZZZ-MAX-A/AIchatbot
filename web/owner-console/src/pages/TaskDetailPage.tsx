import { ArrowLeft, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  OwnerConsoleApiError,
  ownerConsoleApi,
} from "../api/ownerConsoleApi";
import type {
  OwnerConsoleApprovalRow,
  OwnerConsoleTaskDetailEnvelope,
  OwnerConsoleTaskEventRow,
  OwnerConsoleTaskRow,
} from "../api/ownerConsoleTypes";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";

type TaskDetailState = {
  loading: boolean;
  detail: OwnerConsoleTaskDetailEnvelope | null;
  error: Error | null;
};

function parseTaskId(value: string | undefined): number | null {
  if (!value || !/^[1-9]\d*$/.test(value)) {
    return null;
  }
  return Number(value);
}

function apiErrorDescription(error: Error): string {
  if (error instanceof OwnerConsoleApiError) {
    if (error.status === 403) {
      return "无法读取主人上下文，请检查 BOT_OWNER_QQ 是否已配置。";
    }
    if (error.status === 404) {
      return "未找到该任务，或该任务不属于主人私聊上下文。";
    }
    if (error.status === 400) {
      return "请求参数错误，请检查任务 ID、事件数量或预览长度。";
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

function DetailSummary({ task }: { task: OwnerConsoleTaskRow }) {
  return (
    <section className="detail-panel">
      <h2>任务信息</h2>
      <dl className="summary-grid">
        <div>
          <dt>任务 ID</dt>
          <dd>{task.task_id}</dd>
        </div>
        <div>
          <dt>状态</dt>
          <dd>
            <StatusBadge
              label="状态"
              value={task.status_label || task.status}
              tone={taskStatusTone(task.status)}
            />
          </dd>
        </div>
        <div>
          <dt>工作类型</dt>
          <dd>{task.work_type || "普通任务"}</dd>
        </div>
        <div>
          <dt>创建时间</dt>
          <dd>{task.created_at || "未知"}</dd>
        </div>
        <div>
          <dt>更新时间</dt>
          <dd>{task.updated_at || "未知"}</dd>
        </div>
      </dl>
    </section>
  );
}

function EventRows({ rows }: { rows: OwnerConsoleTaskEventRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="暂无事件"
        description="当前任务还没有可显示的事件。"
      />
    );
  }

  return (
    <div className="event-table" role="table" aria-label="任务事件">
      <div className="event-table__row event-table__row--head" role="row">
        <span role="columnheader">步骤</span>
        <span role="columnheader">类型</span>
        <span role="columnheader">工具</span>
        <span role="columnheader">状态</span>
        <span role="columnheader">输入预览</span>
        <span role="columnheader">输出摘要</span>
        <span role="columnheader">时间</span>
      </div>
      {rows.map((event) => (
        <div className="event-table__row" role="row" key={event.event_id}>
          <span role="cell">{event.step_index}</span>
          <span role="cell">{event.kind || "未知"}</span>
          <span role="cell">{event.tool_name || "无"}</span>
          <span role="cell">{event.status_label || event.status || "未知"}</span>
          <span role="cell">{event.input_preview || "无"}</span>
          <span role="cell">
            {event.error || event.output_summary || "暂无"}
          </span>
          <span role="cell">{event.created_at || "未知"}</span>
        </div>
      ))}
    </div>
  );
}

function ApprovalRows({ rows }: { rows: OwnerConsoleApprovalRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="暂无关联审批"
        description="当前任务没有关联审批。"
      />
    );
  }

  return (
    <div className="approval-mini-table" role="table" aria-label="关联审批">
      <div
        className="approval-mini-table__row approval-mini-table__row--head"
        role="row"
      >
        <span role="columnheader">审批 ID</span>
        <span role="columnheader">工具</span>
        <span role="columnheader">风险等级</span>
        <span role="columnheader">状态</span>
        <span role="columnheader">详情</span>
      </div>
      {rows.map((approval) => (
        <div
          className="approval-mini-table__row"
          role="row"
          key={approval.approval_id}
        >
          <span role="cell">{approval.approval_id}</span>
          <span role="cell">{approval.tool_name}</span>
          <span role="cell">{approval.risk_level}</span>
          <span role="cell">{approval.status_label || approval.status}</span>
          <span role="cell">
            <Link
              className="table-link"
              to={`/owner-console/approvals/${approval.approval_id}`}
            >
              查看审批
            </Link>
          </span>
        </div>
      ))}
    </div>
  );
}

export function TaskDetailPage() {
  const { task_id } = useParams();
  const taskId = useMemo(() => parseTaskId(task_id), [task_id]);
  const [state, setState] = useState<TaskDetailState>({
    loading: true,
    detail: null,
    error: null,
  });

  const load = useCallback(
    async (signal?: AbortSignal) => {
      if (taskId === null) {
        setState({
          loading: false,
          detail: null,
          error: new Error("任务 ID 无效"),
        });
        return;
      }

      setState((current) => ({
        ...current,
        loading: true,
        error: null,
      }));

      try {
        const detail = await ownerConsoleApi.getTaskDetail(
          taskId,
          {
            event_limit: 20,
            preview_limit: 800,
          },
          signal,
        );
        if (signal?.aborted) {
          return;
        }
        setState({
          loading: false,
          detail,
          error: null,
        });
      } catch (exc) {
        if (exc instanceof DOMException && exc.name === "AbortError") {
          return;
        }
        setState({
          loading: false,
          detail: null,
          error: exc instanceof Error ? exc : new Error("任务详情加载失败"),
        });
      }
    },
    [taskId],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const detail = state.detail?.data;

  return (
    <section className="page task-detail-page">
      <header className="page-header">
        <div>
          <p className="page-header__eyebrow">主人控制台</p>
          <h1>任务详情</h1>
        </div>
        <div className="page-header__actions">
          <Link className="back-link" to="/owner-console/tasks">
            <ArrowLeft aria-hidden="true" size={16} />
            <span>返回任务</span>
          </Link>
          <button
            className="refresh-button"
            type="button"
            onClick={() => void load()}
            disabled={state.loading}
          >
            <RefreshCw aria-hidden="true" size={16} />
            <span>刷新详情</span>
          </button>
        </div>
      </header>

      {state.loading ? (
        <section className="loading-panel" role="status">
          正在加载任务详情
        </section>
      ) : null}

      {state.error ? (
        <ErrorState
          title="任务详情暂不可用"
          description={apiErrorDescription(state.error)}
          details={
            state.error instanceof OwnerConsoleApiError
              ? state.error.code
              : undefined
          }
        />
      ) : null}

      {detail ? (
        <>
          <DetailSummary task={detail.task} />

          <section className="detail-grid">
            <section className="detail-panel">
              <h2>目标</h2>
              <p className="detail-text">{detail.goal || "暂无目标"}</p>
            </section>
            <section className="detail-panel">
              <h2>结果</h2>
              <p className="detail-text">{detail.result || "暂无结果"}</p>
            </section>
          </section>

          <section className="detail-panel">
            <h2>下一步</h2>
            <p className="detail-text">{detail.next_action || "暂无"}</p>
          </section>

          <section className="detail-panel">
            <h2>关联审批</h2>
            <ApprovalRows rows={detail.approvals} />
          </section>

          <section className="detail-panel">
            <h2>事件时间线</h2>
            <EventRows rows={detail.events} />
          </section>
        </>
      ) : null}
    </section>
  );
}
