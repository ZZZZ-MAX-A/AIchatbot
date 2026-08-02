import { ArrowLeft, Check, RefreshCw, ShieldAlert, X } from "lucide-react";
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

type ApprovalDecision = "approve" | "reject";

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
    if (error.status === 409) {
      return "该审批已被另一请求处理，请刷新详情确认最终状态。";
    }
    return `后端返回 HTTP ${error.status}：${error.message}`;
  }
  return error.message;
}

function actionBlockedDescription(reason: string): string {
  if (reason.includes("web approval actions are disabled")) {
    return "网页审批当前未开放。请使用 -EnableApprovalActions 重启主人控制台后再处理。";
  }
  if (reason.includes("redacted")) {
    return "参数中存在被隐藏的敏感值，网页禁止批准；你仍然可以拒绝。";
  }
  if (reason.includes("truncated")) {
    return "参数预览不完整，网页禁止批准；你仍然可以拒绝。";
  }
  if (reason.includes("external writes")) {
    return "该审批会产生外部写入，V1 不允许通过网页批准；你仍然可以拒绝。";
  }
  if (reason.includes("has expired")) {
    return "该审批已经超过有效期，网页禁止批准；你仍然可以拒绝以结束待处理状态。";
  }
  if (reason.includes("expiration is invalid")) {
    return "该审批的过期时间格式无效，网页禁止批准；你仍然可以拒绝。";
  }
  if (reason.includes("QQ Bot process")) {
    return "该命令依赖 QQ Bot 进程内状态，主人控制台不能可靠执行；请通过 QQ 处理或直接拒绝。";
  }
  if (reason.includes("not registered")) {
    return "该工具没有注册到主人控制台的受控恢复表，网页禁止批准。";
  }
  if (reason.includes("saved tool input")) {
    return "审批保存的参数不符合当前工具协议，网页禁止批准。";
  }
  if (reason.includes("not pending")) {
    return "该审批已经结束，不能再次批准或拒绝。";
  }
  return reason || "当前审批不能通过网页处理。";
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

function ApprovalDecisionPanel({
  approval,
  toolInput,
  decision,
  submitting,
  message,
  error,
  onSelect,
  onCancel,
  onConfirm,
}: {
  approval: OwnerConsoleApprovalRow;
  toolInput: OwnerConsoleToolInputPreview;
  decision: ApprovalDecision | null;
  submitting: boolean;
  message: string;
  error: Error | null;
  onSelect: (value: ApprovalDecision) => void;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const actionability = approval.actionability;
  const pending = approval.status === "pending";
  const blocked = actionability.blocked_reason
    ? actionBlockedDescription(actionability.blocked_reason)
    : "";

  return (
    <section className="approval-decision-panel" aria-label="主人审批决定">
      <header>
        <div>
          <p>受控写入</p>
          <h2>主人决定</h2>
        </div>
        <StatusBadge
          label="网页审批"
          value={pending && (actionability.can_approve || actionability.can_reject) ? "可处理" : "不可处理"}
          tone={pending && (actionability.can_approve || actionability.can_reject) ? "warning" : "neutral"}
        />
      </header>

      {pending ? (
        <p className="approval-decision-panel__description">
          批准会使用审批创建时保存的原始参数，立即恢复已注册的本地工具；网页不能修改参数。拒绝不会执行工具。
        </p>
      ) : (
        <p className="approval-decision-panel__description">
          该审批已经形成最终决定，网页不会提供重复执行或重试入口。
        </p>
      )}

      {toolInput.redacted || toolInput.truncated ? (
        <div className="approval-decision-panel__warning">
          <ShieldAlert aria-hidden="true" size={17} />
          <span>
            {toolInput.redacted ? "参数含有已脱敏字段。" : ""}
            {toolInput.truncated ? "参数预览已截断。" : ""}
          </span>
        </div>
      ) : null}

      {blocked ? <p className="approval-decision-panel__blocked">{blocked}</p> : null}
      {message ? <p className="approval-decision-panel__success">{message}</p> : null}
      {error ? <p className="approval-decision-panel__error">{apiErrorDescription(error)}</p> : null}

      {pending && decision === null ? (
        <div className="approval-decision-panel__actions">
          <button
            className="approval-action approval-action--approve"
            type="button"
            disabled={!actionability.can_approve || submitting}
            onClick={() => onSelect("approve")}
          >
            <Check aria-hidden="true" size={16} />
            批准并执行
          </button>
          <button
            className="approval-action approval-action--reject"
            type="button"
            disabled={!actionability.can_reject || submitting}
            onClick={() => onSelect("reject")}
          >
            <X aria-hidden="true" size={16} />
            拒绝审批
          </button>
        </div>
      ) : null}

      {pending && decision !== null ? (
        <div className={`approval-confirmation approval-confirmation--${decision}`} role="group" aria-label="二次确认审批决定">
          <strong>{decision === "approve" ? "确认批准并立即执行？" : "确认拒绝该审批？"}</strong>
          <p>
            {decision === "approve"
              ? "确认后将使用上方显示的原始参数恢复本地工具；审批决定不可撤销，网页不会自动重试。"
              : "确认后审批将变为已拒绝，对应工具不会执行，之后不能再次批准。"}
          </p>
          <div>
            <button
              className={`approval-action approval-action--${decision}`}
              type="button"
              disabled={submitting}
              onClick={onConfirm}
            >
              {submitting ? "正在提交" : decision === "approve" ? "确认批准并执行" : "确认拒绝"}
            </button>
            <button className="approval-action approval-action--cancel" type="button" disabled={submitting} onClick={onCancel}>
              返回检查
            </button>
          </div>
        </div>
      ) : null}
    </section>
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
  const [decision, setDecision] = useState<ApprovalDecision | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState<Error | null>(null);
  const [actionMessage, setActionMessage] = useState("");

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

  const submitDecision = useCallback(async () => {
    if (approvalId === null || decision === null || submitting) {
      return;
    }
    setSubmitting(true);
    setActionError(null);
    setActionMessage("");
    try {
      const envelope = decision === "approve"
        ? await ownerConsoleApi.approveApproval(approvalId)
        : await ownerConsoleApi.rejectApproval(approvalId);
      if (!envelope.data) {
        throw new Error("审批动作没有返回结果");
      }
      setState({
        loading: false,
        detail: {
          ...state.detail!,
          generated_at: envelope.generated_at,
          data: envelope.data.approval_detail,
          error: null,
        },
        error: null,
      });
      setActionMessage(envelope.data.action.safe_message);
      setDecision(null);
    } catch (exc) {
      setActionError(exc instanceof Error ? exc : new Error("审批动作失败"));
    } finally {
      setSubmitting(false);
    }
  }, [approvalId, decision, state.detail, submitting]);

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

          <ApprovalDecisionPanel
            approval={detail.approval}
            toolInput={detail.tool_input}
            decision={decision}
            submitting={submitting}
            message={actionMessage}
            error={actionError}
            onSelect={(value) => {
              setDecision(value);
              setActionError(null);
              setActionMessage("");
            }}
            onCancel={() => setDecision(null)}
            onConfirm={() => void submitDecision()}
          />

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
