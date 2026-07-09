import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  OwnerConsoleApiError,
  ownerConsoleApi,
} from "../api/ownerConsoleApi";
import type {
  OwnerConsoleDiagnosticsEnvelope,
  OwnerConsoleRuntimeBoundary,
  OwnerConsoleTextSnapshotSection,
} from "../api/ownerConsoleTypes";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";

type DiagnosticsPageState = {
  loading: boolean;
  diagnostics: OwnerConsoleDiagnosticsEnvelope | null;
  error: Error | null;
};

function apiErrorDescription(error: Error): string {
  if (error instanceof OwnerConsoleApiError) {
    if (error.status === 403) {
      return "无法读取主人上下文，请检查 BOT_OWNER_QQ 是否已配置。";
    }
    if (error.status === 400) {
      return "请求参数错误，请检查诊断快照请求。";
    }
    return `后端返回 HTTP ${error.status}：${error.message}`;
  }
  return error.message;
}

function SnapshotCard({ section }: { section: OwnerConsoleTextSnapshotSection }) {
  return (
    <section className="diagnostic-card">
      <header>
        <h2>{section.title}</h2>
        <StatusBadge
          label="状态"
          value={section.ok ? "正常" : "异常"}
          tone={section.ok ? "success" : "warning"}
        />
      </header>
      {section.summary_text ? (
        <p className="diagnostic-card__summary">{section.summary_text}</p>
      ) : null}
      {section.error ? (
        <p className="diagnostic-card__error">{section.error}</p>
      ) : null}
      {section.display_lines.length > 0 ? (
        <ul className="diagnostic-lines">
          {section.display_lines.map((line, index) => (
            <li key={`${index}:${line}`}>{line}</li>
          ))}
        </ul>
      ) : (
        <p className="diagnostic-card__empty">暂无明细</p>
      )}
    </section>
  );
}

function ObservationPanel({
  title,
  lines,
}: {
  title: string;
  lines: string[];
}) {
  return (
    <section className="detail-panel">
      <h2>{title}</h2>
      {lines.length > 0 ? (
        <ul className="diagnostic-lines">
          {lines.map((line, index) => (
            <li key={`${index}:${line}`}>{line}</li>
          ))}
        </ul>
      ) : (
        <p className="diagnostic-card__empty">暂无观测</p>
      )}
    </section>
  );
}

function RuntimeBoundaryPanel({
  boundary,
}: {
  boundary: OwnerConsoleRuntimeBoundary;
}) {
  return (
    <section className="detail-panel">
      <h2>运行边界</h2>
      <div className="boundary-grid">
        <StatusBadge
          label="MainAgent 入口"
          value={boundary.main_agent_entry || "/agent"}
          tone="success"
        />
        <StatusBadge
          label="普通聊天触发 MainAgent"
          value={boundary.ordinary_chat_can_trigger_main_agent ? "异常" : "禁止"}
          tone={
            boundary.ordinary_chat_can_trigger_main_agent ? "danger" : "success"
          }
        />
        <StatusBadge
          label="ProjectDocRAG 普通聊天"
          value={boundary.project_doc_rag_in_ordinary_chat ? "异常" : "禁止"}
          tone={boundary.project_doc_rag_in_ordinary_chat ? "danger" : "success"}
        />
        <StatusBadge
          label="Shell 工具"
          value={boundary.shell_tools_exposed ? "异常" : "未暴露"}
          tone={boundary.shell_tools_exposed ? "danger" : "success"}
        />
        <StatusBadge
          label="主人写操作"
          value={boundary.owner_write_requires_approval ? "需要审批" : "异常"}
          tone={boundary.owner_write_requires_approval ? "success" : "danger"}
        />
        <StatusBadge
          label="多步写自动化"
          value={boundary.multi_step_write_automation_allowed ? "异常" : "未开放"}
          tone={
            boundary.multi_step_write_automation_allowed ? "danger" : "success"
          }
        />
      </div>
    </section>
  );
}

export function DiagnosticsPage() {
  const [state, setState] = useState<DiagnosticsPageState>({
    loading: true,
    diagnostics: null,
    error: null,
  });

  const load = useCallback(async (signal?: AbortSignal) => {
    setState((current) => ({
      ...current,
      loading: true,
      error: null,
    }));

    try {
      const diagnostics = await ownerConsoleApi.getDiagnostics(signal);
      if (signal?.aborted) {
        return;
      }
      setState({
        loading: false,
        diagnostics,
        error: null,
      });
    } catch (exc) {
      if (exc instanceof DOMException && exc.name === "AbortError") {
        return;
      }
      setState({
        loading: false,
        diagnostics: null,
        error: exc instanceof Error ? exc : new Error("诊断快照加载失败"),
      });
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const diagnostics = state.diagnostics?.data;

  return (
    <section className="page diagnostics-page">
      <header className="page-header">
        <div>
          <p className="page-header__eyebrow">主人控制台</p>
          <h1>诊断</h1>
        </div>
        <button
          className="refresh-button"
          type="button"
          onClick={() => void load()}
          disabled={state.loading}
        >
          <RefreshCw aria-hidden="true" size={16} />
          <span>刷新诊断</span>
        </button>
      </header>

      {state.loading ? (
        <section className="loading-panel" role="status">
          正在加载诊断快照
        </section>
      ) : null}

      {state.error ? (
        <ErrorState
          title="诊断快照暂不可用"
          description={apiErrorDescription(state.error)}
          details={
            state.error instanceof OwnerConsoleApiError
              ? state.error.code
              : undefined
          }
        />
      ) : null}

      {diagnostics ? (
        <>
          <section className="data-toolbar" aria-label="诊断快照状态">
            <div>
              <p>快照时间</p>
              <strong>{diagnostics.generated_at || "未知"}</strong>
            </div>
            <StatusBadge
              label="机器人状态"
              value={diagnostics.bot_status.ok ? "正常" : "异常"}
              tone={diagnostics.bot_status.ok ? "success" : "warning"}
            />
            <StatusBadge
              label="最近错误"
              value={diagnostics.recent_errors.ok ? "正常" : "需要查看"}
              tone={diagnostics.recent_errors.ok ? "success" : "warning"}
            />
          </section>

          <div className="diagnostic-card-grid">
            <SnapshotCard section={diagnostics.bot_status} />
            <SnapshotCard section={diagnostics.diagnostics} />
            <SnapshotCard section={diagnostics.config} />
            <SnapshotCard section={diagnostics.vision} />
            <SnapshotCard section={diagnostics.image_cache} />
            <SnapshotCard section={diagnostics.memory} />
            <SnapshotCard section={diagnostics.tts} />
            <SnapshotCard section={diagnostics.recent_errors} />
          </div>

          <section className="detail-grid">
            <ObservationPanel
              title="MainAgent 观测"
              lines={diagnostics.observations.main_agent}
            />
            <ObservationPanel
              title="RootGraph 观测"
              lines={diagnostics.observations.root_graph}
            />
          </section>

          <RuntimeBoundaryPanel boundary={diagnostics.boundary} />
        </>
      ) : null}
    </section>
  );
}
