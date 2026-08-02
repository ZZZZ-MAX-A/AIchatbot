import { AlertTriangle, ArrowLeft, RefreshCw, XCircle } from "lucide-react";
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

type TaskActionState = {
  confirming: boolean;
  submitting: boolean;
  error: Error | null;
  successMessage: string;
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
              {approval.status === "pending" ? "处理审批" : "查看审批"}
            </Link>
          </span>
        </div>
      ))}
    </div>
  );
}

function TaskActionPanel({
  task,
  actionState,
  onBegin,
  onCancelConfirmation,
  onConfirm,
}: {
  task: OwnerConsoleTaskRow;
  actionState: TaskActionState;
  onBegin: () => void;
  onCancelConfirmation: () => void;
  onConfirm: () => void;
}) {
  if (task.status !== "pending") {
    return (
      <section className="detail-panel">
        <h2>主人处理任务</h2>
        <p className="detail-text">任务已经收口，仅提供只读复盘，不再显示处理动作。</p>
        {actionState.successMessage ? (
          <p className="action-feedback action-feedback--success" role="status">
            {actionState.successMessage}
          </p>
        ) : null}
      </section>
    );
  }

  if (task.processing_category === "awaiting_approval") {
    const approvalId = task.pending_approval_ids[0];
    return (
      <section className="detail-panel">
        <h2>主人处理任务</h2>
        <p className="detail-text">
          {task.processing_detail || "请先处理关联审批；审批未决定前不能取消任务。"}
        </p>
        {approvalId ? (
          <Link className="table-link" to={`/owner-console/approvals/${approvalId}`}>
            处理审批 #{approvalId}
          </Link>
        ) : null}
      </section>
    );
  }

  const stale = task.processing_category === "stale_residual";
  return (
    <section className="detail-panel task-action-panel task-action-panel--danger">
      <header className="task-action-heading">
        <div className="task-action-heading__title">
          <AlertTriangle aria-hidden="true" size={22} />
          <div>
            <span className="task-action-eyebrow">风险操作</span>
            <h2>{stale ? "取消并收口旧任务" : "取消待处理任务"}</h2>
          </div>
        </div>
        <StatusBadge label="影响" value="不可撤销" tone="danger" />
      </header>
      <p className="detail-text">{task.processing_detail || task.next_action}</p>
      <div className="task-risk-callout" role="note" aria-label="取消任务风险提示">
        <AlertTriangle aria-hidden="true" size={18} />
        <p>
          <strong>风险提示：</strong>
          取消后任务状态将永久收口为“已取消”，不能从网页恢复；如仍需处理，必须重新创建任务。
        </p>
      </div>
      {!task.actionability.task_actions_enabled ? (
        <p className="panel-note">网页任务处理开关未开启，当前只能查看任务证据。</p>
      ) : null}
      {task.actionability.can_cancel && !actionState.confirming ? (
        <button className="danger-action-button" type="button" onClick={onBegin}>
          <XCircle aria-hidden="true" size={17} />
          {stale ? "取消并收口" : "取消任务"}
        </button>
      ) : null}
      {actionState.confirming ? (
        <div
          className="action-confirmation action-confirmation--danger"
          role="group"
          aria-label="取消任务确认"
        >
          <div className="action-confirmation__title">
            <XCircle aria-hidden="true" size={20} />
            <strong>不可撤销操作</strong>
          </div>
          <p className="action-confirmation__question">
            {stale
              ? "确认取消并收口这个旧任务？"
              : "确认取消这个待处理任务？"}
          </p>
          <ul className="task-risk-list">
            <li><strong>任务状态将永久变为“已取消”</strong></li>
            <li>不会执行原工具</li>
            <li>不会恢复任何审批</li>
            <li>不会自动重试</li>
          </ul>
          <div className="page-header__actions">
            <button
              className="danger-action-button danger-action-button--confirm"
              type="button"
              onClick={onConfirm}
              disabled={actionState.submitting}
            >
              <XCircle aria-hidden="true" size={17} />
              {actionState.submitting
                ? "正在取消"
                : stale
                  ? "确认取消并收口（不可撤销）"
                  : "确认取消任务（不可撤销）"}
            </button>
            <button
              className="back-link"
              type="button"
              onClick={onCancelConfirmation}
              disabled={actionState.submitting}
            >
              返回
            </button>
          </div>
        </div>
      ) : null}
      {actionState.error ? (
        <p className="action-feedback action-feedback--error" role="alert">
          {apiErrorDescription(actionState.error)}
        </p>
      ) : null}
    </section>
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
  const [actionState, setActionState] = useState<TaskActionState>({
    confirming: false,
    submitting: false,
    error: null,
    successMessage: "",
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

  const cancelTask = useCallback(async () => {
    if (taskId === null) return;
    setActionState((current) => ({
      ...current,
      submitting: true,
      error: null,
    }));
    try {
      const envelope = await ownerConsoleApi.cancelTask(taskId);
      if (!envelope.data) {
        throw new Error("任务取消接口没有返回详情");
      }
      setState({
        loading: false,
        detail: {
          ...state.detail!,
          generated_at: envelope.generated_at,
          data: envelope.data.task_detail,
        },
        error: null,
      });
      setActionState({
        confirming: false,
        submitting: false,
        error: null,
        successMessage: envelope.data.action.safe_message,
      });
    } catch (exc) {
      setActionState({
        confirming: true,
        submitting: false,
        error: exc instanceof Error ? exc : new Error("任务取消失败"),
        successMessage: "",
      });
    }
  }, [state.detail, taskId]);

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

          <TaskActionPanel
            task={detail.task}
            actionState={actionState}
            onBegin={() =>
              setActionState({
                confirming: true,
                submitting: false,
                error: null,
                successMessage: "",
              })
            }
            onCancelConfirmation={() =>
              setActionState((current) => ({
                ...current,
                confirming: false,
                error: null,
              }))
            }
            onConfirm={() => void cancelTask()}
          />

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
