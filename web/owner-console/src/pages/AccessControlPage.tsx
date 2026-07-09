import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  OwnerConsoleApiError,
  ownerConsoleApi,
} from "../api/ownerConsoleApi";
import type {
  OwnerConsoleAccessControlEnvelope,
  OwnerConsoleAccessControlSnapshot,
  OwnerConsoleAccessList,
} from "../api/ownerConsoleTypes";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";

type AccessControlPageState = {
  loading: boolean;
  accessControl: OwnerConsoleAccessControlEnvelope | null;
  error: Error | null;
};

function apiErrorDescription(error: Error): string {
  if (error instanceof OwnerConsoleApiError) {
    if (error.status === 400) {
      return "请求参数错误，请检查列表数量限制。";
    }
    return `后端返回 HTTP ${error.status}：${error.message}`;
  }
  return error.message;
}

function enabledLabel(value: boolean): string {
  return value ? "已开启" : "已关闭";
}

function unknownPrivatePolicyLabel(value: string): string {
  if (value === "allow_trial") {
    return "允许试用";
  }
  if (value === "deny") {
    return "拒绝";
  }
  return value || "未知";
}

function AccessListPanel({ list }: { list: OwnerConsoleAccessList }) {
  return (
    <section className="detail-panel">
      <header className="detail-panel__header">
        <h2>{accessListTitle(list.label)}</h2>
        <div className="boundary-grid">
          <StatusBadge label="数量" value={`${list.count} 个`} />
          <StatusBadge
            label="截断"
            value={list.truncated ? "是" : "否"}
            tone={list.truncated ? "warning" : "success"}
          />
        </div>
      </header>
      {list.items.length > 0 ? (
        <ul className="access-list-items">
          {list.items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="diagnostic-card__empty">暂无条目</p>
      )}
    </section>
  );
}

function accessListTitle(label: string): string {
  if (label === "private_whitelist") {
    return "私聊白名单";
  }
  if (label === "group_whitelist") {
    return "群聊白名单";
  }
  if (label === "user_blacklist") {
    return "用户黑名单";
  }
  return label;
}

function BoundaryPanel({
  accessControl,
}: {
  accessControl: OwnerConsoleAccessControlSnapshot;
}) {
  return (
    <section className="detail-panel">
      <h2>运行边界</h2>
      <div className="boundary-grid">
        <StatusBadge
          label="普通聊天触发 MainAgent"
          value={
            accessControl.boundary.ordinary_chat_can_trigger_main_agent
              ? "异常"
              : "禁止"
          }
          tone={
            accessControl.boundary.ordinary_chat_can_trigger_main_agent
              ? "danger"
              : "success"
          }
        />
        <StatusBadge
          label="ProjectDocRAG 普通聊天"
          value={
            accessControl.boundary.project_doc_rag_in_ordinary_chat
              ? "异常"
              : "禁止"
          }
          tone={
            accessControl.boundary.project_doc_rag_in_ordinary_chat
              ? "danger"
              : "success"
          }
        />
        <StatusBadge
          label="Shell 工具"
          value={accessControl.boundary.shell_tools_exposed ? "异常" : "未暴露"}
          tone={
            accessControl.boundary.shell_tools_exposed ? "danger" : "success"
          }
        />
        <StatusBadge
          label="主人写操作"
          value={
            accessControl.boundary.owner_write_requires_approval
              ? "需要审批"
              : "异常"
          }
          tone={
            accessControl.boundary.owner_write_requires_approval
              ? "success"
              : "danger"
          }
        />
      </div>
    </section>
  );
}

export function AccessControlPage() {
  const [state, setState] = useState<AccessControlPageState>({
    loading: true,
    accessControl: null,
    error: null,
  });

  const load = useCallback(async (signal?: AbortSignal) => {
    setState((current) => ({
      ...current,
      loading: true,
      error: null,
    }));

    try {
      const accessControl = await ownerConsoleApi.getAccessControl(
        { item_limit: 50 },
        signal,
      );
      if (signal?.aborted) {
        return;
      }
      setState({
        loading: false,
        accessControl,
        error: null,
      });
    } catch (exc) {
      if (exc instanceof DOMException && exc.name === "AbortError") {
        return;
      }
      setState({
        loading: false,
        accessControl: null,
        error:
          exc instanceof Error ? exc : new Error("访问控制快照加载失败"),
      });
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const accessControl = state.accessControl?.data;

  return (
    <section className="page access-control-page">
      <header className="page-header">
        <div>
          <p className="page-header__eyebrow">主人控制台</p>
          <h1>访问控制</h1>
        </div>
        <button
          className="refresh-button"
          type="button"
          onClick={() => void load()}
          disabled={state.loading}
        >
          <RefreshCw aria-hidden="true" size={16} />
          <span>刷新访问控制</span>
        </button>
      </header>

      {state.loading ? (
        <section className="loading-panel" role="status">
          正在加载访问控制快照
        </section>
      ) : null}

      {state.error ? (
        <ErrorState
          title="访问控制快照暂不可用"
          description={apiErrorDescription(state.error)}
          details={
            state.error instanceof OwnerConsoleApiError
              ? state.error.code
              : undefined
          }
        />
      ) : null}

      {accessControl ? (
        <>
          <section className="data-toolbar" aria-label="访问控制快照状态">
            <div>
              <p>快照时间</p>
              <strong>{accessControl.generated_at || "未知"}</strong>
            </div>
            <StatusBadge
              label="主人配置"
              value={accessControl.owner_configured ? "已配置" : "未配置"}
              tone={accessControl.owner_configured ? "success" : "warning"}
            />
            <StatusBadge
              label="私聊入口"
              value={enabledLabel(accessControl.private_chat_enabled)}
              tone={accessControl.private_chat_enabled ? "success" : "neutral"}
            />
            <StatusBadge
              label="群聊入口"
              value={enabledLabel(accessControl.group_chat_enabled)}
              tone={accessControl.group_chat_enabled ? "success" : "neutral"}
            />
            <StatusBadge
              label="陌生私聊"
              value={unknownPrivatePolicyLabel(
                accessControl.unknown_private_policy,
              )}
              tone={
                accessControl.unknown_private_policy === "allow_trial"
                  ? "warning"
                  : "success"
              }
            />
          </section>

          <section className="detail-grid">
            <AccessListPanel list={accessControl.private_whitelist} />
            <AccessListPanel list={accessControl.group_whitelist} />
          </section>

          <section className="detail-grid">
            <AccessListPanel list={accessControl.user_blacklist} />
            <BoundaryPanel accessControl={accessControl} />
          </section>
        </>
      ) : null}
    </section>
  );
}
