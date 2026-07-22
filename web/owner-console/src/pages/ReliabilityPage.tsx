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

type ReliabilityOption = {
  value: string;
  label: string;
};

type ReliabilityReading = {
  tone: "neutral" | "success" | "warning" | "danger";
  headline: string;
  detail: string;
};

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

function uniqueOptions(
  rows: OwnerConsoleReliabilityTrendItem[],
  valueOf: (row: OwnerConsoleReliabilityTrendItem) => string,
  labelOf: (row: OwnerConsoleReliabilityTrendItem) => string,
): ReliabilityOption[] {
  const options = new Map<string, string>();
  for (const row of rows) {
    options.set(valueOf(row), labelOf(row));
  }
  return [...options.entries()]
    .map(([value, label]) => ({ value, label }))
    .sort((left, right) => left.label.localeCompare(right.label, "zh-CN"));
}

const RECOVERY_PRIORITY: Record<string, number> = {
  recurring: 0,
  unresolved: 1,
  insufficient_evidence: 2,
  recovered: 3,
};

function buildReliabilityReading(
  rows: OwnerConsoleReliabilityTrendItem[],
  allRowCount: number,
): ReliabilityReading {
  if (rows.length === 0) {
    return allRowCount === 0
      ? {
          tone: "neutral",
          headline: "当前窗口没有结构化故障记录",
          detail: "这不等于系统持续在线，也不覆盖尚未接入的组件。",
        }
      : {
          tone: "neutral",
          headline: "当前筛选没有匹配的故障组",
          detail: "可以调整或清除筛选；完整英文技术证据仍保留在明细中。",
        };
  }

  const counts = {
    unresolved: rows.filter((row) => row.recovery_state === "unresolved").length,
    recurring: rows.filter((row) => row.recovery_state === "recurring").length,
    recovered: rows.filter((row) => row.recovery_state === "recovered").length,
    insufficient: rows.filter(
      (row) => row.recovery_state === "insufficient_evidence",
    ).length,
  };
  const attention = counts.unresolved + counts.recurring;
  const top = [...rows].sort((left, right) => {
    const priority =
      (RECOVERY_PRIORITY[left.recovery_state] ?? 9) -
      (RECOVERY_PRIORITY[right.recovery_state] ?? 9);
    if (priority !== 0) return priority;
    if (left.occurrence_count !== right.occurrence_count) {
      return right.occurrence_count - left.occurrence_count;
    }
    return Date.parse(right.last_seen_at) - Date.parse(left.last_seen_at);
  })[0];
  const topEvidence = `${top.component_label} · ${top.operation_label}：${top.code_label}（${top.code}），证据状态为${top.recovery_state_label}（${top.recovery_state}）`;

  if (attention > 0) {
    const parts = [];
    if (counts.recurring > 0) parts.push(`反复发生 ${counts.recurring} 组`);
    if (counts.unresolved > 0) parts.push(`未恢复 ${counts.unresolved} 组`);
    return {
      tone: counts.recurring > 0 ? "warning" : "danger",
      headline: `当前筛选有 ${attention} 组需要关注`,
      detail: `${parts.join("，")}。优先查看 ${topEvidence}。`,
    };
  }

  if (counts.recovered > 0 && counts.insufficient === 0) {
    return {
      tone: "success",
      headline: "当前筛选没有未恢复或反复发生的故障组",
      detail: `${counts.recovered} 组在最后失败之后已有真实成功证据；历史英文错误码继续保留。`,
    };
  }

  if (counts.recovered > 0) {
    return {
      tone: "neutral",
      headline: "当前筛选没有可判定为未恢复的故障组",
      detail: `${counts.recovered} 组已有恢复证据，${counts.insufficient} 组证据不足。优先查看 ${topEvidence}。`,
    };
  }

  return {
    tone: "neutral",
    headline: "当前筛选没有可判定为未恢复的故障组",
    detail: `${counts.insufficient} 组证据不足，不能据此判断仍在故障或已经恢复。优先查看 ${topEvidence}。`,
  };
}

function ReliabilityMetrics({ window }: { window: OwnerConsoleReliabilityWindow }) {
  const metrics = [
    ["失败/降级记录", window.failure_occurrence_count],
    ["需要关注", window.state_counts.unresolved + window.state_counts.recurring],
    ["已有恢复证据", window.state_counts.recovered],
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
    () =>
      uniqueOptions(
        allRows,
        (row) => row.component,
        (row) => `${row.component_label}（${row.component}）`,
      ),
    [allRows],
  );
  const categories = useMemo(
    () =>
      uniqueOptions(
        allRows,
        (row) => row.category,
        (row) => `${row.category_label}（${row.category}）`,
      ),
    [allRows],
  );
  const recoveries = useMemo(
    () =>
      uniqueOptions(
        allRows,
        (row) => row.recovery_state,
        (row) => `${row.recovery_state_label}（${row.recovery_state}）`,
      ),
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
  const reading = useMemo(
    () => buildReliabilityReading(filteredRows, allRows.length),
    [allRows.length, filteredRows],
  );
  const hasActiveFilters =
    componentFilter !== "all" ||
    categoryFilter !== "all" ||
    recoveryFilter !== "all";

  return (
    <section className="page reliability-page">
      <header className="page-header">
        <div>
          <p className="page-header__eyebrow">主人控制台</p>
          <h1>结构化可靠性</h1>
          <p className="page-header__resource">P2.48 中文解读 · 英文证据保留 · SQLite 真只读</p>
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
                <p className="panel-note">中文用于解读；英文 component / operation / category / code 保留为原始证据。</p>
              </div>
              <span className="reliability-result-count">
                显示 {filteredRows.length} / {allRows.length} 组
              </span>
            </div>

            <div className="reliability-filters" aria-label="故障组筛选">
              <label>
                <span>功能</span>
                <select value={componentFilter} onChange={(event) => setComponentFilter(event.target.value)}>
                  <option value="all">全部功能</option>
                  {components.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
              <label>
                <span>问题类别</span>
                <select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
                  <option value="all">全部类别</option>
                  {categories.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
              <label>
                <span>证据状态</span>
                <select value={recoveryFilter} onChange={(event) => setRecoveryFilter(event.target.value)}>
                  <option value="all">全部状态</option>
                  {recoveries.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
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
                disabled={!hasActiveFilters}
              >
                清除筛选
              </button>
            </div>

            <section
              className={`reliability-reading reliability-reading--${reading.tone}`}
              aria-label="当前可靠性解读"
            >
              <strong>{reading.headline}</strong>
              <p>{reading.detail}</p>
            </section>

            {filteredRows.length > 0 ? (
              <div className="reliability-table-scroll">
                <div className="reliability-table" role="table" aria-label="结构化故障组">
                  <div className="reliability-table__row reliability-table__row--head" role="row">
                    <span>功能 / 操作</span><span>问题解读 / 英文代码</span><span>次数</span>
                    <span>时间证据</span><span>证据状态</span>
                  </div>
                  {filteredRows.map((row) => (
                    <div className="reliability-table__row" role="row" key={`${row.component}:${row.operation}:${row.category}:${row.code}`}>
                      <span><strong>{row.component_label} · {row.operation_label}</strong><small>{row.component} / {row.operation}</small></span>
                      <span><strong>{row.category_label} · {row.code_label}</strong><small>{row.category} / {row.code}</small></span>
                      <span>{row.occurrence_count} 次</span>
                      <span className="reliability-time-list">
                        <span><small>首次失败</small>{formatTime(row.first_seen_at)}</span>
                        <span><small>最后失败</small>{formatTime(row.last_seen_at)}</span>
                        <span><small>最近成功</small>{formatTime(row.last_success_at)}</span>
                      </span>
                      <span><StatusBadge label="证据" value={row.recovery_state_label} tone={RECOVERY_TONES[row.recovery_state] ?? "neutral"} /><small>{row.recovery_state}</small></span>
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
                  <code key={`${row.component}:${row.operation}`}>
                    <span>{row.component_label} · {row.operation_label}</span>
                    <small>{row.component} / {row.operation}</small>
                  </code>
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
