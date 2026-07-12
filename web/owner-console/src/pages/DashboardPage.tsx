import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  OwnerConsoleApiError,
  ownerConsoleApi,
} from "../api/ownerConsoleApi";
import type {
  OwnerConsoleDiagnosticsEnvelope,
  OwnerConsoleExternalReadEnvelope,
  OwnerConsoleOverviewEnvelope,
  OwnerConsoleTaskRow,
  OwnerConsoleApprovalRow,
  OwnerConsoleTextSnapshotSection,
} from "../api/ownerConsoleTypes";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";

type DashboardState = {
  loading: boolean;
  overview: OwnerConsoleOverviewEnvelope | null;
  diagnostics: OwnerConsoleDiagnosticsEnvelope | null;
  externalRead: OwnerConsoleExternalReadEnvelope | null;
  overviewError: Error | null;
  diagnosticsError: Error | null;
  externalReadError: Error | null;
};

const initialState: DashboardState = {
  loading: true,
  overview: null,
  diagnostics: null,
  externalRead: null,
  overviewError: null,
  diagnosticsError: null,
  externalReadError: null,
};

function formatCount(value: number | undefined): string {
  return typeof value === "number" ? String(value) : "0";
}

function apiErrorDescription(error: Error): string {
  if (error instanceof OwnerConsoleApiError) {
    if (error.status === 403) {
      return "无法读取主人上下文，请检查 BOT_OWNER_QQ 是否已配置。";
    }
    if (error.status === 404) {
      return "未找到该资源，或该资源不属于主人私聊上下文。";
    }
    if (error.status === 400) {
      return "请求参数错误，请检查筛选条件。";
    }
    return `后端返回 HTTP ${error.status}：${error.message}`;
  }
  return error.message;
}

function SnapshotSection({ section }: { section: OwnerConsoleTextSnapshotSection }) {
  return (
    <section className="diagnostic-section">
      <header>
        <h3>{section.title}</h3>
        <StatusBadge
          label="状态"
          value={section.ok ? "正常" : "异常"}
          tone={section.ok ? "success" : "warning"}
        />
      </header>
      {section.summary_text ? <p>{section.summary_text}</p> : null}
      {section.display_lines.length > 0 ? (
        <ul>
          {section.display_lines.slice(0, 6).map((line, index) => (
            <li key={`${index}:${line}`}>{line}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function RecentTaskList({ rows }: { rows: OwnerConsoleTaskRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="暂无最近任务"
        description="当前主人私聊上下文中没有可显示的最近任务。"
      />
    );
  }

  return (
    <div className="compact-table" role="table" aria-label="最近任务">
      <div className="compact-table__row compact-table__row--head" role="row">
        <span role="columnheader">任务 ID</span>
        <span role="columnheader">目标摘要</span>
        <span role="columnheader">状态</span>
        <span role="columnheader">下一步</span>
      </div>
      {rows.map((task) => (
        <div className="compact-table__row" role="row" key={task.task_id}>
          <span role="cell">{task.task_id}</span>
          <span role="cell">{task.goal_preview || task.title}</span>
          <span role="cell">{task.status_label || task.status}</span>
          <span role="cell">{task.next_action || "暂无"}</span>
        </div>
      ))}
    </div>
  );
}

function PendingApprovalList({ rows }: { rows: OwnerConsoleApprovalRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="暂无待审批"
        description="当前没有需要处理的主人审批。"
      />
    );
  }

  return (
    <div className="compact-table" role="table" aria-label="待审批">
      <div className="compact-table__row compact-table__row--head" role="row">
        <span role="columnheader">审批 ID</span>
        <span role="columnheader">工具</span>
        <span role="columnheader">风险等级</span>
        <span role="columnheader">状态</span>
      </div>
      {rows.map((approval) => (
        <div
          className="compact-table__row"
          role="row"
          key={approval.approval_id}
        >
          <span role="cell">{approval.approval_id}</span>
          <span role="cell">{approval.tool_name}</span>
          <span role="cell">{approval.risk_level}</span>
          <span role="cell">{approval.status_label || approval.status}</span>
        </div>
      ))}
    </div>
  );
}

export function DashboardPage() {
  const [state, setState] = useState<DashboardState>(initialState);

  const load = useCallback(async (signal?: AbortSignal) => {
    setState((current) => ({
      ...current,
      loading: true,
      overviewError: null,
      diagnosticsError: null,
      externalReadError: null,
    }));

    const [overviewResult, diagnosticsResult, externalReadResult] = await Promise.allSettled([
      ownerConsoleApi.getOverview(
        {
          task_limit: 5,
          approval_limit: 5,
        },
        signal,
      ),
      ownerConsoleApi.getDiagnostics(signal),
      ownerConsoleApi.getExternalRead(signal),
    ]);

    if (signal?.aborted) {
      return;
    }

    setState({
      loading: false,
      overview:
        overviewResult.status === "fulfilled" ? overviewResult.value : null,
      diagnostics:
        diagnosticsResult.status === "fulfilled"
          ? diagnosticsResult.value
          : null,
      externalRead:
        externalReadResult.status === "fulfilled"
          ? externalReadResult.value
          : null,
      overviewError:
        overviewResult.status === "rejected"
          ? overviewResult.reason instanceof Error
            ? overviewResult.reason
            : new Error("概览加载失败")
          : null,
      diagnosticsError:
        diagnosticsResult.status === "rejected"
          ? diagnosticsResult.reason instanceof Error
            ? diagnosticsResult.reason
            : new Error("诊断加载失败")
          : null,
      externalReadError:
        externalReadResult.status === "rejected"
          ? externalReadResult.reason instanceof Error
            ? externalReadResult.reason
            : new Error("联网状态加载失败")
          : null,
    });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const overview = state.overview?.data;
  const diagnostics = state.diagnostics?.data;
  const externalRead = state.externalRead?.data;

  return (
    <section className="page dashboard-page">
      <header className="page-header">
        <div>
          <p className="page-header__eyebrow">主人控制台</p>
          <h1>概览</h1>
        </div>
        <button
          className="refresh-button"
          type="button"
          onClick={() => void load()}
          disabled={state.loading}
        >
          <RefreshCw aria-hidden="true" size={16} />
          <span>刷新概览</span>
        </button>
      </header>

      {state.loading ? (
        <section className="loading-panel" role="status">
          正在加载概览数据
        </section>
      ) : null}

      {state.overviewError ? (
        <ErrorState
          title="概览暂不可用"
          description={apiErrorDescription(state.overviewError)}
          details={
            state.overviewError instanceof OwnerConsoleApiError
              ? state.overviewError.code
              : undefined
          }
        />
      ) : null}

      {overview ? (
        <>
          <section className="metric-grid" aria-label="任务和审批计数">
            <article className="metric-tile">
              <span>待处理任务</span>
              <strong>{formatCount(overview.counters.pending_tasks)}</strong>
            </article>
            <article className="metric-tile">
              <span>失败任务</span>
              <strong>{formatCount(overview.counters.failed_tasks)}</strong>
            </article>
            <article className="metric-tile">
              <span>待审批</span>
              <strong>{formatCount(overview.counters.pending_approvals)}</strong>
            </article>
            <article className="metric-tile">
              <span>网页写入</span>
              <strong>
                {state.overview?.web_write_enabled === false ? "已关闭" : "异常"}
              </strong>
            </article>
          </section>

          <section className="dashboard-grid">
            <section className="dashboard-panel">
              <h2>最近任务</h2>
              <RecentTaskList rows={overview.recent_tasks} />
            </section>
            <section className="dashboard-panel">
              <h2>待审批</h2>
              <PendingApprovalList rows={overview.pending_approvals} />
            </section>
          </section>

          <section className="dashboard-panel">
            <h2>运行边界</h2>
            <div className="boundary-grid">
              <StatusBadge
                label="普通聊天触发 MainAgent"
                value={
                  overview.boundary.ordinary_chat_can_trigger_main_agent
                    ? "异常"
                    : "禁止"
                }
                tone={
                  overview.boundary.ordinary_chat_can_trigger_main_agent
                    ? "danger"
                    : "success"
                }
              />
              <StatusBadge
                label="ProjectDocRAG 普通聊天"
                value={
                  overview.boundary.project_doc_rag_in_ordinary_chat
                    ? "异常"
                    : "禁止"
                }
                tone={
                  overview.boundary.project_doc_rag_in_ordinary_chat
                    ? "danger"
                    : "success"
                }
              />
              <StatusBadge
                label="主人写操作"
                value={
                  overview.boundary.owner_write_requires_approval
                    ? "需要审批"
                    : "异常"
                }
                tone={
                  overview.boundary.owner_write_requires_approval
                    ? "success"
                    : "danger"
                }
              />
              <StatusBadge
                label="多步写自动化"
                value={
                  overview.boundary.multi_step_write_automation_allowed
                    ? "异常"
                    : "未开放"
                }
                tone={
                  overview.boundary.multi_step_write_automation_allowed
                    ? "danger"
                    : "success"
                }
              />
            </div>
          </section>
        </>
      ) : null}

      {state.diagnosticsError ? (
        <ErrorState
          title="诊断快照暂不可用"
          description={apiErrorDescription(state.diagnosticsError)}
        />
      ) : null}

      {state.externalReadError ? (
        <ErrorState
          title="联网状态暂不可用"
          description={apiErrorDescription(state.externalReadError)}
        />
      ) : null}

      {externalRead ? (
        <section className="dashboard-panel">
          <div className="detail-panel__header">
            <h2>外部只读查询</h2>
            <StatusBadge
              label="本地配置"
              value={externalRead.executor_configured ? "正常" : "未就绪"}
              tone={externalRead.executor_configured ? "success" : "warning"}
            />
          </div>
          <div className="boundary-grid">
            <StatusBadge label="Provider" value={`${externalRead.provider_name} ${externalRead.search_depth}`} />
            <StatusBadge label="最多结果" value={String(externalRead.max_results)} />
            <StatusBadge
              label="最近任务"
              value={externalRead.recent_task.available ? `#${externalRead.recent_task.task_id} ${externalRead.recent_task.task_status}` : "暂无"}
            />
            <StatusBadge
              label="实时探测"
              value={externalRead.boundary.live_probe_executed ? "已执行" : "未执行"}
              tone={externalRead.boundary.live_probe_executed ? "warning" : "success"}
            />
          </div>
          <p className="panel-note">刷新此卡片只读取本地配置和安全任务元数据，不访问 Tavily，也不消耗 credit。</p>
        </section>
      ) : null}

      {diagnostics ? (
        <section className="dashboard-panel">
          <h2>轻量诊断</h2>
          <div className="diagnostic-grid">
            <SnapshotSection section={diagnostics.bot_status} />
            <SnapshotSection section={diagnostics.diagnostics} />
            <SnapshotSection section={diagnostics.memory} />
            <SnapshotSection section={diagnostics.recent_errors} />
          </div>
        </section>
      ) : null}
    </section>
  );
}
