import { ArrowRight, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";

import {
  OwnerConsoleApiError,
  ownerConsoleApi,
} from "../api/ownerConsoleApi";
import type {
  OwnerConsoleApprovalRow,
  OwnerConsoleDiagnosticsEnvelope,
  OwnerConsoleExternalReadEnvelope,
  OwnerConsoleOverviewEnvelope,
  OwnerConsoleReliabilityEnvelope,
  OwnerConsoleSnapshot,
  OwnerConsoleTaskRow,
  OwnerConsoleTextSnapshotSection,
} from "../api/ownerConsoleTypes";
import {
  classifyOwnerConsoleAutoRefreshError,
  OWNER_CONSOLE_AUTO_REFRESH_FAILURE_LIMIT,
  OWNER_CONSOLE_PAGE_REFRESH_INTERVAL_MS,
  OWNER_CONSOLE_VISIBILITY_RESUME_DELAY_MS,
} from "../app/ownerConsoleRefreshPolicy";
import { useAutoRefreshPreference } from "../app/AutoRefreshContext";
import { buildOwnerConsoleAccessStatus } from "../app/ownerConsoleAccessStatus";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";
import { useControlledAutoRefresh } from "../hooks/useControlledAutoRefresh";
import {
  buildDashboardOverview,
  type DashboardSourceKey,
  type DashboardTone,
} from "./dashboardOverview";

type DashboardState = {
  loading: boolean;
  overview: OwnerConsoleOverviewEnvelope | null;
  diagnostics: OwnerConsoleDiagnosticsEnvelope | null;
  externalRead: OwnerConsoleExternalReadEnvelope | null;
  reliability: OwnerConsoleReliabilityEnvelope | null;
  overviewError: Error | null;
  diagnosticsError: Error | null;
  externalReadError: Error | null;
  reliabilityError: Error | null;
  lastLoadedAt: Date | null;
};

const initialState: DashboardState = {
  loading: true,
  overview: null,
  diagnostics: null,
  externalRead: null,
  reliability: null,
  overviewError: null,
  diagnosticsError: null,
  externalReadError: null,
  reliabilityError: null,
  lastLoadedAt: null,
};

const TONE_LABELS: Record<DashboardTone, string> = {
  neutral: "证据不足",
  success: "当前稳定",
  warning: "需要关注",
  danger: "已降级",
};

function formatCount(value: number | undefined): string {
  return typeof value === "number" ? String(value) : "—";
}

function formatTime(value: string | Date | null): string {
  if (!value) return "尚未刷新";
  const parsed = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(parsed.getTime())) return typeof value === "string" ? value : "未知";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "Asia/Shanghai",
  }).format(parsed);
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
  return "只读数据源请求失败，请检查 Owner Console 后端连接后重试。";
}

function toError(reason: unknown, fallback: string): Error {
  return reason instanceof Error ? reason : new Error(fallback);
}

function SnapshotSection({ section }: { section: OwnerConsoleTextSnapshotSection }) {
  return (
    <section className="diagnostic-section">
      <header>
        <h3>{section.title}</h3>
        <StatusBadge
          label="快照"
          value={section.ok ? "可读取" : "读取异常"}
          tone={section.ok ? "success" : "warning"}
        />
      </header>
      {section.summary_text ? <p>{section.summary_text}</p> : null}
      {section.display_lines.length > 0 ? (
        <ul>
          {section.display_lines.slice(0, 4).map((line, index) => (
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
          <span role="cell">
            <Link className="table-link" to={`/owner-console/tasks/${task.task_id}`}>
              #{task.task_id}
            </Link>
          </span>
          <span role="cell">{task.goal_preview || task.title}</span>
          <span role="cell">{task.status_label || task.status}</span>
          <span role="cell">{task.processing_detail || "暂无"}</span>
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
        <div className="compact-table__row" role="row" key={approval.approval_id}>
          <span role="cell">
            <Link
              className="table-link"
              to={`/owner-console/approvals/${approval.approval_id}`}
            >
              #{approval.approval_id}
            </Link>
          </span>
          <span role="cell">{approval.tool_name}</span>
          <span role="cell">{approval.risk_level}</span>
          <span role="cell">{approval.status_label || approval.status}</span>
        </div>
      ))}
    </div>
  );
}

export function DashboardPage() {
  const { enabled: autoRefreshEnabled } = useAutoRefreshPreference();
  const shellSnapshot = useOutletContext<OwnerConsoleSnapshot | null>();
  const [state, setState] = useState<DashboardState>(initialState);

  const load = useCallback(
    async (signal?: AbortSignal, throwWhenAllUnavailable = false): Promise<boolean> => {
      setState((current) => ({
        ...current,
        loading: true,
        overviewError: null,
        diagnosticsError: null,
        externalReadError: null,
        reliabilityError: null,
      }));

      const [overviewResult, diagnosticsResult, externalReadResult, reliabilityResult] =
        await Promise.allSettled([
          ownerConsoleApi.getOverview(
            {
              task_limit: 5,
              approval_limit: 5,
            },
            signal,
          ),
          ownerConsoleApi.getDiagnostics(signal),
          ownerConsoleApi.getExternalRead(signal),
          ownerConsoleApi.getReliability(signal),
        ]);

      if (signal?.aborted) {
        setState((current) => ({ ...current, loading: false }));
        return false;
      }

      const overview = overviewResult.status === "fulfilled" ? overviewResult.value : null;
      const diagnostics =
        diagnosticsResult.status === "fulfilled" ? diagnosticsResult.value : null;
      const externalRead =
        externalReadResult.status === "fulfilled" ? externalReadResult.value : null;
      const reliability =
        reliabilityResult.status === "fulfilled" ? reliabilityResult.value : null;
      const successCount = [overview?.data, diagnostics?.data, externalRead?.data, reliability?.data].filter(
        Boolean,
      ).length;

      setState((current) => ({
        loading: false,
        overview: overview?.data ? overview : current.overview,
        diagnostics: diagnostics?.data ? diagnostics : current.diagnostics,
        externalRead: externalRead?.data ? externalRead : current.externalRead,
        reliability: reliability?.data ? reliability : current.reliability,
        overviewError:
          overviewResult.status === "rejected"
            ? toError(overviewResult.reason, "概览加载失败")
            : overview?.data
              ? null
              : new Error("概览返回空数据"),
        diagnosticsError:
          diagnosticsResult.status === "rejected"
            ? toError(diagnosticsResult.reason, "诊断加载失败")
            : diagnostics?.data
              ? null
              : new Error("诊断返回空数据"),
        externalReadError:
          externalReadResult.status === "rejected"
            ? toError(externalReadResult.reason, "联网状态加载失败")
            : externalRead?.data
              ? null
              : new Error("联网状态返回空数据"),
        reliabilityError:
          reliabilityResult.status === "rejected"
            ? toError(reliabilityResult.reason, "可靠性快照加载失败")
            : reliability?.data
              ? null
              : new Error("可靠性快照返回空数据"),
        lastLoadedAt: successCount > 0 ? new Date() : current.lastLoadedAt,
      }));

      if (throwWhenAllUnavailable && successCount === 0) {
        const firstRejected = [
          overviewResult,
          diagnosticsResult,
          externalReadResult,
          reliabilityResult,
        ].find((result) => result.status === "rejected");
        throw firstRejected?.status === "rejected"
          ? toError(firstRejected.reason, "概况自动刷新失败")
          : new Error("概况自动刷新未返回有效数据");
      }
      return successCount > 0;
    },
    [],
  );

  const autoRefreshTask = useCallback(
    async (signal: AbortSignal) => {
      await load(signal, true);
    },
    [load],
  );
  const autoRefresh = useControlledAutoRefresh({
    enabled: autoRefreshEnabled,
    intervalMs: OWNER_CONSOLE_PAGE_REFRESH_INTERVAL_MS,
    refresh: autoRefreshTask,
    classifyError: classifyOwnerConsoleAutoRefreshError,
    failureLimit: OWNER_CONSOLE_AUTO_REFRESH_FAILURE_LIMIT,
    visibilityResumeDelayMs: OWNER_CONSOLE_VISIBILITY_RESUME_DELAY_MS,
  });

  const handleManualRefresh = useCallback(async () => {
    if (!autoRefresh.beginManualRefresh()) return;
    const succeeded = await load();
    autoRefresh.finishManualRefresh(succeeded);
  }, [autoRefresh, load]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const overview = state.overview?.data ?? null;
  const diagnostics = state.diagnostics?.data ?? null;
  const externalRead = state.externalRead?.data ?? null;
  const reliability = state.reliability?.data ?? null;
  const unavailableSources = useMemo(() => {
    const keys: DashboardSourceKey[] = [];
    if (state.overviewError || !overview) keys.push("overview");
    if (state.diagnosticsError || !diagnostics) keys.push("diagnostics");
    if (state.externalReadError || !externalRead) keys.push("external_read");
    if (state.reliabilityError || !reliability) keys.push("reliability");
    return keys;
  }, [
    diagnostics,
    externalRead,
    overview,
    reliability,
    state.diagnosticsError,
    state.externalReadError,
    state.overviewError,
    state.reliabilityError,
  ]);
  const hasAnyData = Boolean(overview || diagnostics || externalRead || reliability);
  const accessStatus = useMemo(
    () =>
      buildOwnerConsoleAccessStatus(
        shellSnapshot?.health ?? null,
        shellSnapshot?.routes ?? null,
      ),
    [shellSnapshot],
  );
  const viewModel = useMemo(
    () =>
      hasAnyData
        ? buildDashboardOverview({
            overview,
            webWriteState: accessStatus.webWrite.state,
            diagnostics,
            externalRead,
            reliability,
            unavailableSources,
          })
        : null,
    [
      diagnostics,
      externalRead,
      hasAnyData,
      overview,
      reliability,
      accessStatus.webWrite.state,
      unavailableSources,
    ],
  );

  const sourceErrors = [
    ["任务与审批", state.overviewError],
    ["诊断快照", state.diagnosticsError],
    ["联网配置", state.externalReadError],
    ["结构化可靠性", state.reliabilityError],
  ] as const;
  const failedSources = sourceErrors.filter(([, error]) => error !== null);

  return (
    <section className="page dashboard-page">
      <header className="page-header">
        <div>
          <p className="page-header__eyebrow">主人控制台</p>
          <h1>概况</h1>
          <p className="page-header__resource">
            统一状态判断 · 待关注事项 · 24 小时可靠性 · 确定性下钻
          </p>
        </div>
        <button
          className="refresh-button"
          type="button"
          onClick={() => void handleManualRefresh()}
          disabled={state.loading || autoRefresh.status === "refreshing"}
        >
          <RefreshCw aria-hidden="true" size={16} />
          <span>刷新概况</span>
        </button>
      </header>

      {state.loading && !hasAnyData ? (
        <section className="loading-panel" role="status">
          正在加载概况数据
        </section>
      ) : null}

      {viewModel ? (
        <>
          <section
            className={`dashboard-overall dashboard-overall--${viewModel.overall.tone}`}
            aria-label="当前总体判断"
          >
            <div className="dashboard-overall__copy">
              <p>当前判断</p>
              <h2>{viewModel.overall.headline}</h2>
              <span>{viewModel.overall.detail}</span>
            </div>
            <div className="dashboard-overall__meta">
              <StatusBadge
                label="总体状态"
                value={TONE_LABELS[viewModel.overall.tone]}
                tone={viewModel.overall.tone}
              />
              <StatusBadge
                label="数据源"
                value={`${viewModel.availableSourceCount}/4 可读取`}
                tone={viewModel.availableSourceCount === 4 ? "success" : "warning"}
              />
              <StatusBadge
                label="最近刷新"
                value={formatTime(state.lastLoadedAt)}
              />
            </div>
          </section>

          <section className="data-toolbar dashboard-freshness" aria-label="概况数据新鲜度">
            <div>
              <p>快照来源</p>
              <strong>
                {viewModel.availableSourceCount}/4 可读取 · {viewModel.staleSourceCount} 个过期
              </strong>
            </div>
            <div className="boundary-grid">
              {viewModel.sources.map((source) => (
                <StatusBadge
                  key={source.key}
                  label={source.label}
                  value={
                    !source.available
                      ? "不可用"
                      : source.stale
                        ? "已过期"
                        : formatTime(source.generatedAt)
                  }
                  tone={!source.available || source.stale ? "warning" : "success"}
                />
              ))}
              <StatusBadge
                label="页面自动刷新"
                value={
                  autoRefresh.status === "refreshing"
                    ? "检查中"
                    : autoRefresh.status === "paused_error"
                      ? "因错误暂停"
                      : autoRefreshEnabled
                        ? "已开启"
                        : "已关闭"
                }
                tone={autoRefresh.status === "paused_error" ? "warning" : "neutral"}
              />
            </div>
          </section>

          <section className="metric-grid dashboard-metric-grid" aria-label="首页关键计数">
            <a className="metric-tile metric-tile--link" href="#attention-details">
              <span>需要关注</span>
              <strong>{viewModel.actionableCount}</strong>
              <small>查看具体异常与待处理事项 →</small>
            </a>
            <Link className="metric-tile metric-tile--link" to="/owner-console/reliability">
              <span>活跃可靠性故障组</span>
              <strong>{reliability ? viewModel.reliability.activeGroups : "—"}</strong>
              <small>{reliability ? "查看未恢复与反复故障 →" : "可靠性证据不可用"}</small>
            </Link>
            <Link
              className="metric-tile metric-tile--link"
              to="/owner-console/approvals?status=pending"
            >
              <span>待审批</span>
              <strong>{formatCount(overview?.counters.pending_approvals)}</strong>
              <small>只查看需要处理的审批 →</small>
            </Link>
            <Link
              className="metric-tile metric-tile--link"
              to="/owner-console/tasks?status=pending&category=awaiting_approval"
            >
              <span>等待审批任务</span>
              <strong>{formatCount(overview?.counters.awaiting_approval_tasks)}</strong>
              <small>只看必须先审批的任务 →</small>
            </Link>
            <Link
              className="metric-tile metric-tile--link"
              to="/owner-console/tasks?status=pending&category=ordinary_pending"
            >
              <span>普通待处理</span>
              <strong>{formatCount(overview?.counters.ordinary_pending_tasks)}</strong>
              <small>查看可核对或取消的任务 →</small>
            </Link>
            <Link
              className="metric-tile metric-tile--link"
              to="/owner-console/tasks?status=pending&category=stale_residual"
            >
              <span>旧任务残留</span>
              <strong>{formatCount(overview?.counters.stale_pending_tasks)}</strong>
              <small>逐项查看并安全收口 →</small>
            </Link>
          </section>

          <section
            className="dashboard-panel dashboard-attention"
            id="attention-details"
            aria-label="异常与待处理明细"
          >
            <div className="detail-panel__header">
              <div>
                <h2>异常与待处理明细</h2>
                <p className="panel-note">
                  每一项都展示具体原因和确定性处理入口；首页不会自动运行诊断、修复或写操作。
                </p>
              </div>
              <span className="dashboard-section-count">
                {viewModel.actionableCount} 项需处理 · {viewModel.attentionItems.length} 条明细
              </span>
            </div>
            {viewModel.attentionItems.length > 0 ? (
              <div className="dashboard-attention-list">
                {viewModel.attentionItems.map((item) => (
                  <article
                    className={`dashboard-attention-item dashboard-attention-item--${item.tone}`}
                    key={item.id}
                  >
                    <div>
                      <StatusBadge
                        label="优先级"
                        value={
                          item.tone === "danger"
                            ? "优先处理"
                            : item.tone === "warning"
                              ? "需要关注"
                              : "证据提示"
                        }
                        tone={item.tone}
                      />
                      <h3>{item.title}</h3>
                      <p>{item.detail}</p>
                    </div>
                    <Link className="dashboard-action-link" to={item.route}>
                      {item.actionLabel}
                      <ArrowRight aria-hidden="true" size={15} />
                    </Link>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState
                title="当前没有需要处理的事项"
                description="仅表示已接入且新鲜的证据中没有待处理项，不证明未接入组件持续在线。"
              />
            )}
          </section>

          <section className="dashboard-grid dashboard-primary-grid">
            <section className="dashboard-panel" aria-label="最近二十四小时可靠性">
              <div className="detail-panel__header">
                <div>
                  <h2>最近 24 小时可靠性</h2>
                  <p className="panel-note">结构化事件，不读取聊天正文或原始异常。</p>
                </div>
                <Link className="dashboard-action-link" to="/owner-console/reliability">
                  查看全部
                  <ArrowRight aria-hidden="true" size={15} />
                </Link>
              </div>
              {reliability ? (
                <>
                  <div className="dashboard-reliability-grid">
                    <div><span>失败/降级记录</span><strong>{viewModel.reliability.failureOccurrences}</strong></div>
                    <div><span>需要关注</span><strong>{viewModel.reliability.activeGroups}</strong></div>
                    <div><span>已有恢复证据</span><strong>{viewModel.reliability.recoveredGroups}</strong></div>
                    <div><span>证据不足</span><strong>{viewModel.reliability.insufficientGroups}</strong></div>
                  </div>
                  {viewModel.reliability.topItem ? (
                    <article className="dashboard-top-evidence">
                      <span>优先证据</span>
                      <strong>
                        {viewModel.reliability.topItem.component_label} · {viewModel.reliability.topItem.operation_label}
                      </strong>
                      <p>
                        {viewModel.reliability.topItem.code_label} · {viewModel.reliability.topItem.recovery_state_label} · 最近 {formatTime(viewModel.reliability.topItem.last_seen_at)}
                      </p>
                      <code>
                        {viewModel.reliability.topItem.component} / {viewModel.reliability.topItem.operation} / {viewModel.reliability.topItem.code}
                      </code>
                    </article>
                  ) : (
                    <p className="panel-note">
                      当前窗口没有结构化故障记录；这不等于已经证明系统持续在线。
                    </p>
                  )}
                </>
              ) : (
                <EmptyState
                  title="可靠性证据暂不可用"
                  description="无法读取结构化事件快照，因此不会把缺失数据展示为零故障。"
                />
              )}
            </section>

            <section className="dashboard-panel" aria-label="安全边界摘要">
              <div className="detail-panel__header">
                <div>
                  <h2>安全边界</h2>
                  <p className="panel-note">正常时收拢展示；异常项会自动进入异常与待处理明细。</p>
                </div>
                <StatusBadge
                  label="检查"
                  value={`${viewModel.security.checkedCount}/${viewModel.security.expectedCount}`}
                  tone={
                    !overview
                      ? "neutral"
                      : viewModel.security.violationLabels.length === 0
                        ? "success"
                        : "danger"
                  }
                />
              </div>
              {overview ? (
                <div className="boundary-grid">
                  <StatusBadge
                    label="网页写入"
                    value={accessStatus.webWrite.value}
                    tone={accessStatus.webWrite.tone}
                  />
                  <StatusBadge
                    label="普通聊天 MainAgent"
                    value={overview.boundary.ordinary_chat_can_trigger_main_agent ? "异常开放" : "禁止"}
                    tone={overview.boundary.ordinary_chat_can_trigger_main_agent ? "danger" : "success"}
                  />
                  <StatusBadge
                    label="主人写操作"
                    value={overview.boundary.owner_write_requires_approval ? "需要审批" : "异常"}
                    tone={overview.boundary.owner_write_requires_approval ? "success" : "danger"}
                  />
                  <StatusBadge
                    label="Shell 工具"
                    value={overview.boundary.shell_tools_exposed ? "异常开放" : "未开放"}
                    tone={overview.boundary.shell_tools_exposed ? "danger" : "success"}
                  />
                </div>
              ) : (
                <StatusBadge label="安全边界快照" value="证据不可用" tone="neutral" />
              )}
              {overview ? (
                <p className="panel-note">
                  历史失败任务 {overview.counters.failed_tasks} 个，仅作为历史计数，不直接判定当前系统故障。
                </p>
              ) : null}
              <Link className="dashboard-action-link dashboard-panel-link" to="/owner-console/settings">
                查看完整设置边界
                <ArrowRight aria-hidden="true" size={15} />
              </Link>
            </section>
          </section>

          {overview ? (
            <section className="dashboard-grid">
              <section className="dashboard-panel">
                <div className="detail-panel__header">
                  <h2>最近任务</h2>
                  <Link className="dashboard-action-link" to="/owner-console/tasks">
                    查看全部
                    <ArrowRight aria-hidden="true" size={15} />
                  </Link>
                </div>
                <RecentTaskList rows={overview.recent_tasks} />
              </section>
              <section className="dashboard-panel">
                <div className="detail-panel__header">
                  <h2>待审批</h2>
                  <Link className="dashboard-action-link" to="/owner-console/approvals?status=pending">
                    只看待审批
                    <ArrowRight aria-hidden="true" size={15} />
                  </Link>
                </div>
                <PendingApprovalList rows={overview.pending_approvals} />
              </section>
            </section>
          ) : null}

          <section className="dashboard-grid dashboard-evidence-grid">
            {externalRead ? (
              <section className="dashboard-panel">
                <div className="detail-panel__header">
                  <div>
                    <h2>联网查询证据</h2>
                    <p className="panel-note">配置就绪不等于实时可用。</p>
                  </div>
                  <StatusBadge
                    label="本地装配"
                    value={externalRead.executor_configured ? "配置就绪" : "未就绪"}
                    tone={externalRead.executor_configured ? "success" : "warning"}
                  />
                </div>
                <div className="boundary-grid">
                  <StatusBadge label="Provider" value={`${externalRead.provider_name} ${externalRead.search_depth}`} />
                  <StatusBadge
                    label="最近任务"
                    value={externalRead.recent_task.available ? `#${externalRead.recent_task.task_id} ${externalRead.recent_task.task_status}` : "暂无"}
                  />
                  <StatusBadge
                    label="实时探测"
                    value={externalRead.boundary.live_probe_executed ? "已执行" : "未执行"}
                    tone={externalRead.boundary.live_probe_executed ? "warning" : "neutral"}
                  />
                </div>
                <p className="panel-note">
                  首页只读取本地配置和安全任务元数据，不访问 Tavily、不消耗 credit。
                </p>
                <Link className="dashboard-action-link dashboard-panel-link" to="/owner-console/external-read">
                  查看联网详情
                  <ArrowRight aria-hidden="true" size={15} />
                </Link>
              </section>
            ) : null}

            {diagnostics ? (
              <section className="dashboard-panel">
                <div className="detail-panel__header">
                  <div>
                    <h2>诊断快照解读</h2>
                    <p className="panel-note">可读取只表示快照成功，不证明外部服务持续健康。</p>
                  </div>
                  <Link className="dashboard-action-link" to="/owner-console/diagnostics">
                    查看全部
                    <ArrowRight aria-hidden="true" size={15} />
                  </Link>
                </div>
                <div className="diagnostic-grid dashboard-diagnostic-grid">
                  <SnapshotSection section={diagnostics.bot_status} />
                  <SnapshotSection section={diagnostics.diagnostics} />
                  <SnapshotSection section={diagnostics.memory} />
                  <SnapshotSection section={diagnostics.recent_errors} />
                </div>
              </section>
            ) : null}
          </section>
        </>
      ) : null}

      {!state.loading && !hasAnyData ? (
        <ErrorState
          title="概况暂不可用"
          description="四个只读数据源均未返回有效快照，请检查 Owner Console 后端后重试。"
        />
      ) : null}

      {failedSources.length > 0 && hasAnyData ? (
        <section className="dashboard-panel dashboard-partial-errors" aria-label="部分数据源异常">
          <h2>部分数据源暂不可用</h2>
          <ul>
            {failedSources.map(([label, error]) => (
              <li key={label}>
                <strong>{label}</strong>
                <span>{error ? apiErrorDescription(error) : "未知错误"}</span>
              </li>
            ))}
          </ul>
          <p className="panel-note">已保留其他成功快照；总体判断不会把缺失数据当作正常。</p>
        </section>
      ) : null}
    </section>
  );
}
