import { ArrowLeft, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  OwnerConsoleApiError,
  ownerConsoleApi,
} from "../api/ownerConsoleApi";
import type {
  OwnerConsoleApprovalDetailEnvelope,
  OwnerConsoleApprovalRow,
  OwnerConsoleTaskEventRow,
  OwnerConsoleTaskRow,
  OwnerConsoleToolInputPreview,
} from "../api/ownerConsoleTypes";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";

type ApprovalDetailState = {
  loading: boolean;
  detail: OwnerConsoleApprovalDetailEnvelope | null;
  error: Error | null;
};

function parseApprovalId(value: string | undefined): number | null {
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
      return "未找到该审批，或该审批不属于主人私聊上下文。";
    }
    if (error.status === 400) {
      return "请求参数错误，请检查审批 ID、事件数量或预览长度。";
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

function taskStatusTone(
  status: string,
): "neutral" | "success" | "warning" | "danger" {
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

function ApprovalSummary({ approval }: { approval: OwnerConsoleApprovalRow }) {
  return (
    <section className="detail-panel">
      <h2>审批信息</h2>
      <dl className="summary-grid">
        <div>
          <dt>审批 ID</dt>
          <dd>{approval.approval_id}</dd>
        </div>
        <div>
          <dt>状态</dt>
          <dd>
            <StatusBadge
              label="状态"
              value={approval.status_label || approval.status}
              tone={approvalStatusTone(approval.status)}
            />
          </dd>
        </div>
        <div>
          <dt>工具</dt>
          <dd>{approval.tool_name}</dd>
        </div>
        <div>
          <dt>风险等级</dt>
          <dd>{approval.risk_level}</dd>
        </div>
        <div>
          <dt>任务 ID</dt>
          <dd>{approval.task_id}</dd>
        </div>
        <div>
          <dt>创建时间</dt>
          <dd>{approval.created_at || "未知"}</dd>
        </div>
        <div>
          <dt>过期时间</dt>
          <dd>{approval.expires_at || "未知"}</dd>
        </div>
        <div>
          <dt>决定时间</dt>
          <dd>{approval.decided_at || "尚未决定"}</dd>
        </div>
      </dl>
    </section>
  );
}

function ToolInputPreview({ input }: { input: OwnerConsoleToolInputPreview }) {
  return (
    <section className="detail-panel">
      <header className="detail-panel__header">
        <h2>工具输入预览</h2>
        <div className="boundary-grid">
          <StatusBadge
            label="脱敏"
            value={input.redacted ? "已处理" : "未触发"}
            tone={input.redacted ? "success" : "neutral"}
          />
          <StatusBadge
            label="截断"
            value={input.truncated ? "是" : "否"}
            tone={input.truncated ? "warning" : "success"}
          />
        </div>
      </header>
      <pre className="tool-input-preview">{input.preview_json || "{}"}</pre>
    </section>
  );
}

function TaskPanel({ task }: { task: OwnerConsoleTaskRow | null }) {
  if (task === null) {
    return (
      <EmptyState
        title="暂无关联任务"
        description="该审批没有可显示的关联任务记录。"
      />
    );
  }

  return (
    <section className="detail-panel">
      <h2>关联任务</h2>
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
          <dt>目标摘要</dt>
          <dd>{task.goal_preview || task.title}</dd>
        </div>
        <div>
          <dt>下一步</dt>
          <dd>{task.next_action || "暂无"}</dd>
        </div>
      </dl>
      <div className="detail-panel__footer">
        <Link className="table-link" to={`/owner-console/tasks/${task.task_id}`}>
          查看任务详情
        </Link>
      </div>
    </section>
  );
}

function EventRows({ rows }: { rows: OwnerConsoleTaskEventRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="暂无近期事件"
        description="该审批关联任务没有可显示的近期事件。"
      />
    );
  }

  return (
    <div className="event-table" role="table" aria-label="近期任务事件">
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

export function ApprovalDetailPage() {
  const { approval_id } = useParams();
  const approvalId = useMemo(
    () => parseApprovalId(approval_id),
    [approval_id],
  );
  const [state, setState] = useState<ApprovalDetailState>({
    loading: true,
    detail: null,
    error: null,
  });

  const load = useCallback(
    async (signal?: AbortSignal) => {
      if (approvalId === null) {
        setState({
          loading: false,
          detail: null,
          error: new Error("审批 ID 无效"),
        });
        return;
      }

      setState((current) => ({
        ...current,
        loading: true,
        error: null,
      }));

      try {
        const detail = await ownerConsoleApi.getApprovalDetail(
          approvalId,
          {
            event_limit: 5,
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
          error: exc instanceof Error ? exc : new Error("审批详情加载失败"),
        });
      }
    },
    [approvalId],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const detail = state.detail?.data;

  return (
    <section className="page approval-detail-page">
      <header className="page-header">
        <div>
          <p className="page-header__eyebrow">主人控制台</p>
          <h1>审批详情</h1>
        </div>
        <div className="page-header__actions">
          <Link className="back-link" to="/owner-console/approvals">
            <ArrowLeft aria-hidden="true" size={16} />
            <span>返回审批</span>
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
          正在加载审批详情
        </section>
      ) : null}

      {state.error ? (
        <ErrorState
          title="审批详情暂不可用"
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
          <ApprovalSummary approval={detail.approval} />

          <section className="detail-panel">
            <h2>审批原因</h2>
            <p className="detail-text">{detail.reason || "暂无原因"}</p>
          </section>

          <ToolInputPreview input={detail.tool_input} />

          <TaskPanel task={detail.task} />

          <section className="detail-panel">
            <h2>近期任务事件</h2>
            <EventRows rows={detail.recent_events} />
          </section>
        </>
      ) : null}
    </section>
  );
}
