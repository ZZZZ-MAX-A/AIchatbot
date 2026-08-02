import { AlertTriangle, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  OwnerConsoleApiError,
  ownerConsoleApi,
} from "../api/ownerConsoleApi";
import type {
  OwnerConsoleAccessControlEnvelope,
  OwnerConsoleAccessControlSnapshot,
  OwnerConsoleAccessList,
  OwnerConsoleAccessListName,
} from "../api/ownerConsoleTypes";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";

type AccessControlPageState = {
  loading: boolean;
  accessControl: OwnerConsoleAccessControlEnvelope | null;
  error: Error | null;
};

type PendingAction = {
  listName: OwnerConsoleAccessListName;
  operation: "add" | "remove";
  item: string;
  conflictNote?: string;
} | null;

function apiErrorDescription(error: Error): string {
  if (error instanceof OwnerConsoleApiError) {
    if (error.status === 409) {
      return "名单已被其他操作修改，或目标条目状态已变化。请刷新后重试。";
    }
    if (error.status === 403) {
      return "网页访问名单维护未开放，或该条目由环境配置锁定。";
    }
    if (error.status === 400) {
      return "请求无效。QQ 号或群号必须是 5–20 位纯数字。";
    }
    return `后端返回 HTTP ${error.status}：${error.message}`;
  }
  return error.message;
}

function enabledLabel(value: boolean): string {
  return value ? "已开启" : "已关闭";
}

function unknownPrivatePolicyLabel(value: string): string {
  if (value === "allow_trial") return "允许试用";
  if (value === "deny") return "拒绝";
  return value || "未知";
}

function accessListTitle(label: string): string {
  if (label === "private_whitelist") return "私聊白名单";
  if (label === "group_whitelist") return "群聊白名单";
  if (label === "user_blacklist") return "用户黑名单";
  return label;
}

function sourceLabel(source: string): string {
  if (source === "environment") return "环境固定";
  if (source === "environment_and_dynamic") return "环境固定 + 动态副本";
  return "动态可编辑";
}

function actionWarning(action: NonNullable<PendingAction>): string {
  if (action.operation === "add") {
    if (action.listName === "private_whitelist") {
      return "加入后，该用户将立即获得动态私聊访问权限。";
    }
    if (action.listName === "group_whitelist") {
      return "加入后，机器人将立即允许在该群中响应。";
    }
    return "加入后，该用户将立即被拦截；黑名单优先于主人与白名单。";
  }
  if (action.listName === "private_whitelist") {
    return "移出后，该用户将失去动态私聊权限。";
  }
  if (action.listName === "group_whitelist") {
    return "移出后，机器人将不再响应该群。";
  }
  return "移出后，该用户可能恢复访问。";
}

function AccessListPanel({
  listName,
  list,
  actionsEnabled,
  pendingAction,
  submitting,
  onPrepare,
  onCancel,
  onConfirm,
}: {
  listName: OwnerConsoleAccessListName;
  list: OwnerConsoleAccessList;
  actionsEnabled: boolean;
  pendingAction: PendingAction;
  submitting: boolean;
  onPrepare: (action: NonNullable<PendingAction>) => void;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const [item, setItem] = useState("");
  const activeAction =
    pendingAction?.listName === listName ? pendingAction : null;
  const normalized = item.trim();
  const inputValid = /^[0-9]{5,20}$/.test(normalized);

  return (
    <section className="detail-panel access-list-panel">
      <header className="detail-panel__header">
        <div>
          <h2>{accessListTitle(list.label)}</h2>
          <p className="access-list-panel__counts">
            环境固定 {list.environment_count} 项 · 动态 {list.dynamic_count} 项
          </p>
        </div>
        <div className="boundary-grid">
          <StatusBadge label="有效数量" value={`${list.count} 个`} />
          <StatusBadge
            label="完整显示"
            value={list.truncated ? "否" : "是"}
            tone={list.truncated ? "warning" : "success"}
          />
        </div>
      </header>

      <div className="access-list-editor">
        <label>
          <span>{listName === "group_whitelist" ? "群号" : "QQ 号"}</span>
          <input
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={20}
            value={item}
            onChange={(event) => setItem(event.target.value)}
            placeholder="输入 5–20 位纯数字"
            disabled={!actionsEnabled || submitting}
          />
        </label>
        <button
          className="approval-action approval-action--approve"
          type="button"
          disabled={!actionsEnabled || !inputValid || submitting}
          onClick={() =>
            onPrepare({ listName, operation: "add", item: normalized })
          }
        >
          <Plus aria-hidden="true" size={16} />
          准备加入
        </button>
      </div>
      {!actionsEnabled ? (
        <p className="access-list-panel__locked">
          网页维护默认关闭；使用 -EnableAccessActions 重启主人控制台后开放。
        </p>
      ) : null}

      {list.items.length > 0 ? (
        <ul className="access-list-items access-list-items--managed">
          {list.items.map((entry) => (
            <li key={entry.value}>
              <span className="access-list-item__value">{entry.value}</span>
              <span
                className={`access-list-item__source access-list-item__source--${entry.editable ? "dynamic" : "fixed"}`}
              >
                {sourceLabel(entry.source)}
              </span>
              {entry.editable && actionsEnabled ? (
                <button
                  type="button"
                  className="access-list-item__remove"
                  disabled={submitting}
                  onClick={() =>
                    onPrepare({
                      listName,
                      operation: "remove",
                      item: entry.value,
                    })
                  }
                  aria-label={`移除 ${entry.value}`}
                >
                  <Trash2 aria-hidden="true" size={14} />
                  移除
                </button>
              ) : (
                <span className="access-list-item__lock">网页不可删除</span>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="diagnostic-card__empty">暂无条目</p>
      )}

      {activeAction ? (
        <div
          className={`approval-confirmation approval-confirmation--${activeAction.operation === "add" ? "approve" : "reject"}`}
          role="group"
          aria-label="二次确认访问名单操作"
        >
          <strong>
            <AlertTriangle aria-hidden="true" size={16} />
            确认{activeAction.operation === "add" ? "加入" : "移除"}“
            {activeAction.item}”吗？
          </strong>
          <p>{actionWarning(activeAction)}</p>
          {activeAction.conflictNote ? (
            <p className="approval-decision-panel__warning">
              {activeAction.conflictNote}
            </p>
          ) : null}
          <p>本次只修改动态 access.json，不会修改 .env，也不会联动其他名单。</p>
          <div>
            <button
              className={`approval-action approval-action--${activeAction.operation === "add" ? "approve" : "reject"}`}
              type="button"
              disabled={submitting}
              onClick={onConfirm}
            >
              {submitting ? "正在提交…" : "确认执行"}
            </button>
            <button
              className="approval-action approval-action--cancel"
              type="button"
              disabled={submitting}
              onClick={onCancel}
            >
              返回检查
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
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
          value={accessControl.boundary.ordinary_chat_can_trigger_main_agent ? "异常" : "禁止"}
          tone={accessControl.boundary.ordinary_chat_can_trigger_main_agent ? "danger" : "success"}
        />
        <StatusBadge
          label="ProjectDocRAG 普通聊天"
          value={accessControl.boundary.project_doc_rag_in_ordinary_chat ? "异常" : "禁止"}
          tone={accessControl.boundary.project_doc_rag_in_ordinary_chat ? "danger" : "success"}
        />
        <StatusBadge
          label="Shell 工具"
          value={accessControl.boundary.shell_tools_exposed ? "异常" : "未暴露"}
          tone={accessControl.boundary.shell_tools_exposed ? "danger" : "success"}
        />
        <StatusBadge
          label="主人写操作"
          value={accessControl.boundary.owner_write_requires_approval ? "需要审批" : "异常"}
          tone={accessControl.boundary.owner_write_requires_approval ? "success" : "danger"}
        />
      </div>
    </section>
  );
}

async function executeAccessAction(
  action: NonNullable<PendingAction>,
  revision: number,
) {
  if (action.listName === "private_whitelist") {
    return action.operation === "add"
      ? ownerConsoleApi.addPrivateWhitelistItem(action.item, revision)
      : ownerConsoleApi.removePrivateWhitelistItem(action.item, revision);
  }
  if (action.listName === "group_whitelist") {
    return action.operation === "add"
      ? ownerConsoleApi.addGroupWhitelistItem(action.item, revision)
      : ownerConsoleApi.removeGroupWhitelistItem(action.item, revision);
  }
  return action.operation === "add"
    ? ownerConsoleApi.addUserBlacklistItem(action.item, revision)
    : ownerConsoleApi.removeUserBlacklistItem(action.item, revision);
}

export function AccessControlPage() {
  const [state, setState] = useState<AccessControlPageState>({
    loading: true,
    accessControl: null,
    error: null,
  });
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState("");

  const load = useCallback(async (signal?: AbortSignal) => {
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      const accessControl = await ownerConsoleApi.getAccessControl(
        { item_limit: 50 },
        signal,
      );
      if (signal?.aborted) return;
      setState({ loading: false, accessControl, error: null });
    } catch (exc) {
      if (exc instanceof DOMException && exc.name === "AbortError") return;
      setState((current) => ({
        loading: false,
        accessControl: current.accessControl,
        error: exc instanceof Error ? exc : new Error("访问控制快照加载失败"),
      }));
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const accessControl = state.accessControl?.data;

  async function confirmAction() {
    if (!pendingAction || !accessControl || submitting) return;
    setSubmitting(true);
    setNotice("");
    setState((current) => ({ ...current, error: null }));
    try {
      const response = await executeAccessAction(
        pendingAction,
        accessControl.revision,
      );
      if (!response.data) {
        throw new Error("访问名单动作返回空结果");
      }
      setNotice(response.data.action.safe_message);
      setPendingAction(null);
      await load();
    } catch (exc) {
      setState((current) => ({
        ...current,
        error: exc instanceof Error ? exc : new Error("访问名单操作失败"),
      }));
    } finally {
      setSubmitting(false);
    }
  }

  const panelProps = accessControl
    ? {
        actionsEnabled: accessControl.access_actions_enabled,
        pendingAction,
        submitting,
        onPrepare: (action: NonNullable<PendingAction>) => {
          setNotice("");
          const privateValues = new Set(
            accessControl.private_whitelist.items.map((item) => item.value),
          );
          const blacklistValues = new Set(
            accessControl.user_blacklist.items.map((item) => item.value),
          );
          const conflictNote =
            action.operation === "add" &&
            action.listName === "private_whitelist" &&
            blacklistValues.has(action.item)
              ? "该用户同时位于黑名单；黑名单优先，加入白名单后仍会被拦截。"
              : action.operation === "add" &&
                  action.listName === "user_blacklist" &&
                  privateValues.has(action.item)
                ? "该用户同时位于私聊白名单；加入黑名单后，黑名单将优先拦截。"
                : undefined;
          setPendingAction({ ...action, conflictNote });
        },
        onCancel: () => setPendingAction(null),
        onConfirm: () => void confirmAction(),
      }
    : null;

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
          disabled={state.loading || submitting}
        >
          <RefreshCw aria-hidden="true" size={16} />
          <span>刷新访问控制</span>
        </button>
      </header>

      {state.loading && !accessControl ? (
        <section className="loading-panel" role="status">正在加载访问控制快照</section>
      ) : null}

      {state.error ? (
        <ErrorState
          title="访问控制操作未完成"
          description={apiErrorDescription(state.error)}
          details={state.error instanceof OwnerConsoleApiError ? state.error.code : undefined}
        />
      ) : null}

      {notice ? <p className="access-control-notice" role="status">{notice}</p> : null}

      {accessControl && panelProps ? (
        <>
          <section className="data-toolbar" aria-label="访问控制快照状态">
            <div>
              <p>快照时间 · 修订 {accessControl.revision}</p>
              <strong>{accessControl.generated_at || "未知"}</strong>
            </div>
            <StatusBadge
              label="网页维护"
              value={accessControl.access_actions_enabled ? "已开放" : "只读"}
              tone={accessControl.access_actions_enabled ? "warning" : "neutral"}
            />
            <StatusBadge label="主人配置" value={accessControl.owner_configured ? "已配置" : "未配置"} tone={accessControl.owner_configured ? "success" : "warning"} />
            <StatusBadge label="私聊入口" value={enabledLabel(accessControl.private_chat_enabled)} tone={accessControl.private_chat_enabled ? "success" : "neutral"} />
            <StatusBadge label="群聊入口" value={enabledLabel(accessControl.group_chat_enabled)} tone={accessControl.group_chat_enabled ? "success" : "neutral"} />
            <StatusBadge label="陌生私聊" value={unknownPrivatePolicyLabel(accessControl.unknown_private_policy)} tone={accessControl.unknown_private_policy === "allow_trial" ? "warning" : "success"} />
          </section>

          <section className="detail-grid">
            <AccessListPanel key={`private-${accessControl.revision}`} listName="private_whitelist" list={accessControl.private_whitelist} {...panelProps} />
            <AccessListPanel key={`group-${accessControl.revision}`} listName="group_whitelist" list={accessControl.group_whitelist} {...panelProps} />
          </section>
          <section className="detail-grid">
            <AccessListPanel key={`blacklist-${accessControl.revision}`} listName="user_blacklist" list={accessControl.user_blacklist} {...panelProps} />
            <BoundaryPanel accessControl={accessControl} />
          </section>
        </>
      ) : null}
    </section>
  );
}
