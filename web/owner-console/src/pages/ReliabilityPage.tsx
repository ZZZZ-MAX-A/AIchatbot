import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  OwnerConsoleApiError,
  ownerConsoleApi,
} from "../api/ownerConsoleApi";
import type {
  OwnerConsoleReliabilityEnvelope,
  OwnerConsoleReliabilityTrendItem,
  OwnerConsoleReliabilityWindow,
} from "../api/ownerConsoleTypes";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";

type ReliabilityPageState = {
  loading: boolean;
  snapshot: OwnerConsoleReliabilityEnvelope | null;
  error: Error | null;
};

type WindowKey = "recent" | "weekly";

const RECOVERY_TONES: Record<
  string,
  "neutral" | "success" | "warning" | "danger"
> = {
  unresolved: "danger",
  recovered: "success",
  recurring: "warning",
  insufficient_evidence: "neutral",
};

function formatTime(value: string): string {
  if (!value) {
    return "—";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
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
    return `后端返回 HTTP ${error.status}：${error.message}`;
  }
  return error.message;
}

function uniqueValues(
  rows: OwnerConsoleReliabilityTrendItem[],
  select: (row: OwnerConsoleReliabilityTrendItem) => string,
): string[] {
  return [...new Set(rows.map(select))].sort((left, right) =>
    left.localeCompare(right),
  );
}

function ReliabilityMetrics({ window }: { window: OwnerConsoleReliabilityWindow }) {
  const metrics = [
    ["失败/降级次数", window.failure_occurrence_count],
    ["故障组", window.failure_group_count],
    ["未恢复", window.state_counts.unresolved],
    ["已恢复", window.state_counts.recovered],
    ["反复发生", window.state_counts.recurring],
    ["证据不足", window.state_counts.insufficient_evidence],
  ] as const;
  return (
    <section className="metric-grid reliability-metric-grid" aria-label="可靠性摘要">
      {metrics.map(([label, value]) => (
        <article className="metric-tile" key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
        </article>
      ))}
    </section>
  );
}

export function ReliabilityPage() {
  const [state, setState] = useState<ReliabilityPageState>({
    loading: true,
    snapshot: null,
    error: null,
  });
  const [windowKey, setWindowKey] = useState<WindowKey>("recent");
  const [componentFilter, setComponentFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [recoveryFilter, setRecoveryFilter] = useState("all");

  const load = useCallback(async (signal?: AbortSignal) => {
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      const snapshot = await ownerConsoleApi.getReliability(signal);
      if (signal?.aborted) {
        return;
      }
      setState({ loading: false, snapshot, error: null });
    } catch (exc) {
      if (exc instanceof DOMException && exc.name === "AbortError") {
        return;
      }
      setState({
        loading: false,
        snapshot: null,
        error: exc instanceof Error ? exc : new Error("可靠性快照加载失败"),
      });
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const data = state.snapshot?.data;
  const window = data?.[windowKey] ?? null;
  const allRows = window?.items ?? [];
  const components = useMemo(
    () => uniqueValues(allRows, (row) => row.component),
    [allRows],
  );
  const categories = useMemo(
    () => uniqueValues(allRows, (row) => row.category),
    [allRows],
  );
  const recoveries = useMemo(
    () => uniqueValues(allRows, (row) => row.recovery_state),
    [allRows],
  );
  const filteredRows = useMemo(
    () =>
      allRows.filter(
        (row) =>
          (componentFilter === "all" || row.component === componentFilter) &&
          (categoryFilter === "all" || row.category === categoryFilter) &&
          (recoveryFilter === "all" ||
            row.recovery_state === recoveryFilter),
      ),
    [allRows, categoryFilter, componentFilter, recoveryFilter],
  );

  return (
    <section className="page reliability-page">
      <header className="page-header">
        <div>
          <p className="page-header__eyebrow">主人控制台</p>
          <h1>结构化可靠性</h1>
          <p className="page-header__resource">P2.47 固定事件合同 · SQLite 真只读</p>
        </div>
        <button
          className="refresh-button"
          type="button"
          onClick={() => void load()}
          disabled={state.loading}
        >
          <RefreshCw aria-hidden="true" size={16} />
          <span>刷新趋势</span>
        </button>
      </header>

      {state.loading ? (
        <section className="loading-panel" role="status">
          正在读取结构化可靠性事件
        </section>
      ) : null}

      {state.error ? (
        <ErrorState
          title="可靠性快照暂不可用"
          description={apiErrorDescription(state.error)}
          details={state.error instanceof OwnerConsoleApiError ? state.error.code : undefined}
        />
      ) : null}

      {data && window ? (
        <>
          <section className="data-toolbar" aria-label="可靠性快照状态">
            <div>
              <p>快照时间</p>
              <strong>{formatTime(data.generated_at)}</strong>
            </div>
            <div className="filter-tabs" aria-label="时间范围">
              <button
                className={`filter-tabs__item ${windowKey === "recent" ? "is-active" : ""}`}
                type="button"
                onClick={() => setWindowKey("recent")}
              >
                最近 24 小时
              </button>
              <button
                className={`filter-tabs__item ${windowKey === "weekly" ? "is-active" : ""}`}
                type="button"
                onClick={() => setWindowKey("weekly")}
              >
                最近 7 天
              </button>
            </div>
            <StatusBadge label="数据库读取" value="mode=ro" tone="success" />
          </section>

          <ReliabilityMetrics window={window} />

          <section className="detail-panel">
            <div className="detail-panel__header">
              <div>
                <h2>故障组</h2>
                <p className="panel-note">按 component + operation + category + code 聚合</p>
              </div>
              <span className="reliability-result-count">
                显示 {filteredRows.length} / {allRows.length} 组
              </span>
            </div>

            <div className="reliability-filters" aria-label="故障组筛选">
              <label>
                <span>组件</span>
                <select value={componentFilter} onChange={(event) => setComponentFilter(event.target.value)}>
                  <option value="all">全部组件</option>
                  {components.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </label>
              <label>
                <span>类别</span>
                <select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
                  <option value="all">全部类别</option>
                  {categories.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </label>
              <label>
                <span>恢复状态</span>
                <select value={recoveryFilter} onChange={(event) => setRecoveryFilter(event.target.value)}>
                  <option value="all">全部状态</option>
                  {recoveries.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </label>
              <button
                className="secondary-button"
                type="button"
                onClick={() => {
                  setComponentFilter("all");
                  setCategoryFilter("all");
                  setRecoveryFilter("all");
                }}
              >
                清除筛选
              </button>
            </div>

            {filteredRows.length > 0 ? (
              <div className="reliability-table-scroll">
                <div className="reliability-table" role="table" aria-label="结构化故障组">
                  <div className="reliability-table__row reliability-table__row--head" role="row">
                    <span>组件 / 操作</span><span>类别 / 代码</span><span>次数</span>
                    <span>首次失败</span><span>最后失败</span><span>最近成功</span><span>恢复状态</span>
                  </div>
                  {filteredRows.map((row) => (
                    <div className="reliability-table__row" role="row" key={`${row.component}:${row.operation}:${row.category}:${row.code}`}>
                      <span><strong>{row.component}</strong><small>{row.operation}</small></span>
                      <span><strong>{row.category_label}</strong><small>{row.code}</small></span>
                      <span>{row.occurrence_count}</span>
                      <span>{formatTime(row.first_seen_at)}</span>
                      <span>{formatTime(row.last_seen_at)}</span>
                      <span>{formatTime(row.last_success_at)}</span>
                      <span><StatusBadge label="状态" value={row.recovery_state_label} tone={RECOVERY_TONES[row.recovery_state] ?? "neutral"} /></span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <EmptyState
                title={allRows.length === 0 ? "当前窗口没有结构化故障" : "没有符合筛选条件的故障组"}
                description={data.evidence_note}
              />
            )}
          </section>

          <section className="detail-grid reliability-detail-grid">
            <article className="detail-panel">
              <h2>当前接入范围</h2>
              <div className="coverage-list">
                {data.coverage.map((row) => (
                  <code key={`${row.component}:${row.operation}`}>{row.component} / {row.operation}</code>
                ))}
              </div>
              <p className="panel-note">{data.evidence_note}</p>
            </article>
            <article className="detail-panel">
              <h2>只读安全边界</h2>
              <div className="boundary-grid">
                <StatusBadge label="SQLite" value={data.boundary.sqlite_mode_ro ? "mode=ro" : "异常"} tone={data.boundary.sqlite_mode_ro ? "success" : "danger"} />
                <StatusBadge label="聊天正文" value={data.boundary.chat_content_read ? "已读取" : "未读取"} tone={data.boundary.chat_content_read ? "danger" : "success"} />
                <StatusBadge label="原始异常" value={data.boundary.raw_exception_read ? "已读取" : "未读取"} tone={data.boundary.raw_exception_read ? "danger" : "success"} />
                <StatusBadge label="LLM / RAG" value={data.boundary.llm_called || data.boundary.rag_called ? "已调用" : "未调用"} tone={data.boundary.llm_called || data.boundary.rag_called ? "danger" : "success"} />
                <StatusBadge label="写入副作用" value={data.boundary.write_side_effect_allowed ? "允许" : "禁止"} tone={data.boundary.write_side_effect_allowed ? "danger" : "success"} />
                <StatusBadge label="自动处置" value={data.boundary.alert_executed || data.boundary.repair_executed || data.boundary.restart_executed ? "已执行" : "未执行"} tone={data.boundary.alert_executed || data.boundary.repair_executed || data.boundary.restart_executed ? "danger" : "success"} />
              </div>
              <p className="panel-note">{data.scope_note}</p>
            </article>
          </section>
        </>
      ) : null}
    </section>
  );
}
