import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  OwnerConsoleApiError,
  ownerConsoleApi,
} from "../api/ownerConsoleApi";
import type {
  OwnerConsoleModelConfigSnapshot,
  OwnerConsoleRoleCardRow,
  OwnerConsoleSettingsEnvelope,
  OwnerConsoleSettingsSnapshot,
} from "../api/ownerConsoleTypes";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";

type SettingsPageState = {
  loading: boolean;
  settings: OwnerConsoleSettingsEnvelope | null;
  error: Error | null;
};

type FeatureFlagRow = {
  key: string;
  label: string;
  invertedGood?: boolean;
};

const featureFlags: FeatureFlagRow[] = [
  { key: "enable_main_agent", label: "MainAgent" },
  { key: "main_agent_use_llm", label: "MainAgent 使用 LLM" },
  { key: "main_agent_owner_only", label: "MainAgent 仅主人" },
  { key: "main_agent_allow_group", label: "MainAgent 群聊", invertedGood: true },
  { key: "enable_chat_graph_runtime", label: "ChatGraph Runtime" },
  { key: "enable_vision", label: "视觉" },
  { key: "enable_memory_rag", label: "MemoryRAG" },
  { key: "enable_project_doc_rag", label: "ProjectDocRAG" },
  {
    key: "memory_rag_inject_in_chat",
    label: "MemoryRAG 普通聊天注入",
  },
  { key: "enable_tts", label: "TTS" },
  { key: "enable_agent_web", label: "Agent Web", invertedGood: true },
  { key: "enable_agent_shell", label: "Agent Shell", invertedGood: true },
  { key: "enable_agent_local_write", label: "Agent 本地写", invertedGood: true },
  {
    key: "enable_agent_external_write",
    label: "Agent 外部写",
    invertedGood: true,
  },
];

function apiErrorDescription(error: Error): string {
  if (error instanceof OwnerConsoleApiError) {
    if (error.status === 400) {
      return "请求参数错误，请检查设置快照请求。";
    }
    return `后端返回 HTTP ${error.status}：${error.message}`;
  }
  return error.message;
}

function enabledLabel(value: boolean): string {
  return value ? "已开启" : "已关闭";
}

function flagTone(
  value: boolean,
  invertedGood = false,
): "neutral" | "success" | "warning" | "danger" {
  if (invertedGood) {
    return value ? "warning" : "success";
  }
  return value ? "success" : "neutral";
}

function ModelPanel({
  title,
  model,
}: {
  title: string;
  model: OwnerConsoleModelConfigSnapshot;
}) {
  return (
    <section className="detail-panel">
      <header className="detail-panel__header">
        <h2>{title}</h2>
        <StatusBadge
          label="API Key"
          value={model.api_key_configured ? "已配置" : "未配置"}
          tone={model.api_key_configured ? "success" : "warning"}
        />
      </header>
      <dl className="detail-list">
        <div>
          <dt>模型</dt>
          <dd>{model.model_name || "未配置"}</dd>
        </div>
        <div>
          <dt>Base URL</dt>
          <dd>{model.base_url_redacted || "未配置"}</dd>
        </div>
        <div>
          <dt>超时</dt>
          <dd>{model.timeout_seconds} 秒</dd>
        </div>
      </dl>
    </section>
  );
}

function FeatureFlagPanel({
  settings,
}: {
  settings: OwnerConsoleSettingsSnapshot;
}) {
  return (
    <section className="detail-panel">
      <h2>功能开关</h2>
      <div className="feature-flag-grid">
        {featureFlags.map((flag) => {
          const value = settings.feature_flags[flag.key] === true;
          return (
            <StatusBadge
              key={flag.key}
              label={flag.label}
              value={enabledLabel(value)}
              tone={flagTone(value, flag.invertedGood)}
            />
          );
        })}
      </div>
    </section>
  );
}

function RoleCardsPanel({ rows }: { rows: OwnerConsoleRoleCardRow[] }) {
  return (
    <section className="detail-panel">
      <h2>角色卡</h2>
      {rows.length > 0 ? (
        <div className="role-card-list">
          {rows.map((card) => (
            <article className="role-card-row" key={card.key || card.title}>
              <div>
                <strong>{card.title || card.key || "未命名角色卡"}</strong>
                <span>{card.key || "无 key"}</span>
              </div>
              <StatusBadge
                label="状态"
                value={card.active ? "当前启用" : "可选"}
                tone={card.active ? "success" : "neutral"}
              />
            </article>
          ))}
        </div>
      ) : (
        <p className="diagnostic-card__empty">暂无角色卡</p>
      )}
    </section>
  );
}

function BoundaryPanel({
  settings,
}: {
  settings: OwnerConsoleSettingsSnapshot;
}) {
  return (
    <section className="detail-panel">
      <h2>运行边界</h2>
      <div className="boundary-grid">
        <StatusBadge
          label="普通聊天触发 MainAgent"
          value={
            settings.boundary.ordinary_chat_can_trigger_main_agent
              ? "异常"
              : "禁止"
          }
          tone={
            settings.boundary.ordinary_chat_can_trigger_main_agent
              ? "danger"
              : "success"
          }
        />
        <StatusBadge
          label="ProjectDocRAG 普通聊天"
          value={
            settings.boundary.project_doc_rag_in_ordinary_chat ? "异常" : "禁止"
          }
          tone={
            settings.boundary.project_doc_rag_in_ordinary_chat
              ? "danger"
              : "success"
          }
        />
        <StatusBadge
          label="Shell 工具"
          value={settings.boundary.shell_tools_exposed ? "异常" : "未暴露"}
          tone={settings.boundary.shell_tools_exposed ? "danger" : "success"}
        />
        <StatusBadge
          label="主人写操作"
          value={
            settings.boundary.owner_write_requires_approval ? "需要审批" : "异常"
          }
          tone={
            settings.boundary.owner_write_requires_approval
              ? "success"
              : "danger"
          }
        />
        <StatusBadge
          label="多步写自动化"
          value={
            settings.boundary.multi_step_write_automation_allowed
              ? "异常"
              : "未开放"
          }
          tone={
            settings.boundary.multi_step_write_automation_allowed
              ? "danger"
              : "success"
          }
        />
      </div>
    </section>
  );
}

export function SettingsPage() {
  const [state, setState] = useState<SettingsPageState>({
    loading: true,
    settings: null,
    error: null,
  });

  const load = useCallback(async (signal?: AbortSignal) => {
    setState((current) => ({
      ...current,
      loading: true,
      error: null,
    }));

    try {
      const settings = await ownerConsoleApi.getSettings(signal);
      if (signal?.aborted) {
        return;
      }
      setState({
        loading: false,
        settings,
        error: null,
      });
    } catch (exc) {
      if (exc instanceof DOMException && exc.name === "AbortError") {
        return;
      }
      setState({
        loading: false,
        settings: null,
        error: exc instanceof Error ? exc : new Error("设置快照加载失败"),
      });
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const settings = state.settings?.data;

  return (
    <section className="page settings-page">
      <header className="page-header">
        <div>
          <p className="page-header__eyebrow">主人控制台</p>
          <h1>设置</h1>
        </div>
        <button
          className="refresh-button"
          type="button"
          onClick={() => void load()}
          disabled={state.loading}
        >
          <RefreshCw aria-hidden="true" size={16} />
          <span>刷新设置</span>
        </button>
      </header>

      {state.loading ? (
        <section className="loading-panel" role="status">
          正在加载设置快照
        </section>
      ) : null}

      {state.error ? (
        <ErrorState
          title="设置快照暂不可用"
          description={apiErrorDescription(state.error)}
          details={
            state.error instanceof OwnerConsoleApiError
              ? state.error.code
              : undefined
          }
        />
      ) : null}

      {settings ? (
        <>
          <section className="data-toolbar" aria-label="设置快照状态">
            <div>
              <p>快照时间</p>
              <strong>{settings.generated_at || "未知"}</strong>
            </div>
            <StatusBadge
              label="当前角色卡"
              value={settings.active_role_card_key || "未配置"}
              tone={settings.active_role_card_key ? "success" : "warning"}
            />
            <StatusBadge
              label="网页写入"
              value={state.settings?.web_write_enabled === false ? "已关闭" : "异常"}
              tone={
                state.settings?.web_write_enabled === false ? "success" : "danger"
              }
            />
          </section>

          <section className="detail-grid">
            <ModelPanel title="聊天模型" model={settings.chat_model} />
            <ModelPanel
              title="MainAgent 模型"
              model={settings.main_agent_model}
            />
          </section>

          <ModelPanel title="Embedding" model={settings.embedding} />

          <FeatureFlagPanel settings={settings} />

          <section className="detail-grid">
            <RoleCardsPanel rows={settings.role_cards} />
            <BoundaryPanel settings={settings} />
          </section>
        </>
      ) : null}
    </section>
  );
}
