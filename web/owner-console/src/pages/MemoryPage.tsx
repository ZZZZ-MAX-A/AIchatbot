import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  OwnerConsoleApiError,
  ownerConsoleApi,
} from "../api/ownerConsoleApi";
import type {
  OwnerConsoleMemoryContextPolicy,
  OwnerConsoleMemoryEnvelope,
  OwnerConsoleMemoryRagSnapshot,
  OwnerConsoleMemorySnapshot,
  OwnerConsoleProjectDocRagSnapshot,
} from "../api/ownerConsoleTypes";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";

type MemoryPageState = {
  loading: boolean;
  memory: OwnerConsoleMemoryEnvelope | null;
  error: Error | null;
};

type DetailItem = {
  label: string;
  value: string | number;
};

function apiErrorDescription(error: Error): string {
  if (error instanceof OwnerConsoleApiError) {
    if (error.status === 403) {
      return "无法读取主人上下文，请检查 BOT_OWNER_QQ 是否已配置。";
    }
    if (error.status === 400) {
      return "请求参数错误，请检查记忆快照请求。";
    }
    return `后端返回 HTTP ${error.status}：${error.message}`;
  }
  return error.message;
}

function booleanValue(value: boolean): string {
  return value ? "已开启" : "已关闭";
}

function DetailList({ items }: { items: DetailItem[] }) {
  return (
    <dl className="detail-list">
      {items.map((item) => (
        <div key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function CountPanel({ memory }: { memory: OwnerConsoleMemorySnapshot }) {
  const counts = memory.counts;

  return (
    <section className="metric-grid" aria-label="记忆计数">
      <article className="metric-tile">
        <span>消息</span>
        <strong>{counts.message_count}</strong>
      </article>
      <article className="metric-tile">
        <span>会话</span>
        <strong>{counts.session_count}</strong>
      </article>
      <article className="metric-tile">
        <span>会话摘要</span>
        <strong>{counts.session_summary_count}</strong>
      </article>
      <article className="metric-tile">
        <span>长期记忆</span>
        <strong>{counts.manual_memory_count}</strong>
      </article>
    </section>
  );
}

function BoundaryPanel({ memory }: { memory: OwnerConsoleMemorySnapshot }) {
  return (
    <section className="detail-panel">
      <h2>隐私边界</h2>
      <div className="boundary-grid">
        <StatusBadge
          label="记忆正文"
          value={memory.memory_content_exposed ? "异常展示" : "未展示"}
          tone={memory.memory_content_exposed ? "danger" : "success"}
        />
        <StatusBadge
          label="项目文档正文"
          value={memory.project_doc_content_exposed ? "异常展示" : "未展示"}
          tone={memory.project_doc_content_exposed ? "danger" : "success"}
        />
        <StatusBadge
          label="检索"
          value={memory.retrieval_executed ? "异常执行" : "未执行"}
          tone={memory.retrieval_executed ? "danger" : "success"}
        />
        <StatusBadge
          label="索引重建"
          value={memory.index_rebuild_executed ? "异常执行" : "未执行"}
          tone={memory.index_rebuild_executed ? "danger" : "success"}
        />
        <StatusBadge
          label="ProjectDocRAG 普通聊天"
          value={
            memory.boundary.project_doc_rag_in_ordinary_chat ? "异常" : "禁止"
          }
          tone={
            memory.boundary.project_doc_rag_in_ordinary_chat
              ? "danger"
              : "success"
          }
        />
      </div>
    </section>
  );
}

function ContextPolicyPanel({
  policy,
}: {
  policy: OwnerConsoleMemoryContextPolicy;
}) {
  return (
    <section className="detail-panel">
      <h2>上下文策略</h2>
      <div className="boundary-grid">
        <StatusBadge
          label="摘要压缩"
          value={booleanValue(policy.memory_compression_enabled)}
          tone={policy.memory_compression_enabled ? "success" : "neutral"}
        />
        <StatusBadge
          label="场景摘要"
          value={booleanValue(policy.gap_scene_summaries_enabled)}
          tone={policy.gap_scene_summaries_enabled ? "success" : "neutral"}
        />
        <StatusBadge
          label="长期记忆上下文"
          value={booleanValue(policy.long_term_memory_context_enabled)}
          tone={policy.long_term_memory_context_enabled ? "success" : "neutral"}
        />
      </div>
      <DetailList
        items={[
          { label: "最大上下文消息", value: policy.max_context_messages },
          {
            label: "每会话最大存储",
            value: policy.max_stored_messages_per_session,
          },
          {
            label: "摘要保留近期消息",
            value: policy.summary_keep_recent_messages,
          },
          { label: "摘要批量消息", value: policy.summary_batch_messages },
          {
            label: "摘要最小来源消息",
            value: policy.summary_min_source_messages,
          },
          {
            label: "上下文会话摘要",
            value: policy.max_session_summaries_in_context,
          },
          {
            label: "上下文场景摘要",
            value: policy.max_gap_scene_summaries_in_context,
          },
          {
            label: "上下文长期记忆",
            value: policy.max_long_term_memories_in_context,
          },
        ]}
      />
    </section>
  );
}

function MemoryRagPanel({
  memoryRag,
}: {
  memoryRag: OwnerConsoleMemoryRagSnapshot;
}) {
  return (
    <section className="detail-panel">
      <h2>MemoryRAG</h2>
      <div className="boundary-grid">
        <StatusBadge
          label="MemoryRAG"
          value={booleanValue(memoryRag.enabled)}
          tone={memoryRag.enabled ? "success" : "neutral"}
        />
        <StatusBadge
          label="普通聊天注入"
          value={booleanValue(memoryRag.inject_in_chat)}
          tone={memoryRag.inject_in_chat ? "warning" : "neutral"}
        />
        <StatusBadge
          label="主人调试"
          value={booleanValue(memoryRag.owner_only_debug)}
          tone={memoryRag.owner_only_debug ? "success" : "neutral"}
        />
      </div>
      <DetailList
        items={[
          { label: "Top K", value: memoryRag.top_k },
          { label: "最低分数", value: memoryRag.min_score },
          { label: "最大上下文字符", value: memoryRag.max_context_chars },
          {
            label: "包含事实记忆",
            value: booleanValue(memoryRag.include_manual_facts),
          },
          {
            label: "包含偏好记忆",
            value: booleanValue(memoryRag.include_manual_preferences),
          },
          {
            label: "包含会话摘要",
            value: booleanValue(memoryRag.include_session_summaries),
          },
          {
            label: "包含短消息",
            value: booleanValue(memoryRag.include_short_messages),
          },
          {
            label: "包含场景摘要",
            value: booleanValue(memoryRag.include_gap_scene_summaries),
          },
        ]}
      />
    </section>
  );
}

function ProjectDocRagPanel({
  projectDocRag,
}: {
  projectDocRag: OwnerConsoleProjectDocRagSnapshot;
}) {
  return (
    <section className="detail-panel">
      <h2>ProjectDocRAG</h2>
      <div className="boundary-grid">
        <StatusBadge
          label="ProjectDocRAG"
          value={booleanValue(projectDocRag.enabled)}
          tone={projectDocRag.enabled ? "success" : "neutral"}
        />
        <StatusBadge
          label="/agent dev_context"
          value={projectDocRag.explicit_agent_dev_context_only ? "仅显式" : "异常"}
          tone={
            projectDocRag.explicit_agent_dev_context_only ? "success" : "danger"
          }
        />
        <StatusBadge
          label="普通聊天注入"
          value={projectDocRag.ordinary_chat_injection_allowed ? "异常" : "禁止"}
          tone={
            projectDocRag.ordinary_chat_injection_allowed ? "danger" : "success"
          }
        />
      </div>
      <DetailList
        items={[
          { label: "Top K", value: projectDocRag.top_k },
          { label: "最低分数", value: projectDocRag.min_score },
          { label: "最大上下文字符", value: projectDocRag.max_context_chars },
        ]}
      />
    </section>
  );
}

export function MemoryPage() {
  const [state, setState] = useState<MemoryPageState>({
    loading: true,
    memory: null,
    error: null,
  });

  const load = useCallback(async (signal?: AbortSignal) => {
    setState((current) => ({
      ...current,
      loading: true,
      error: null,
    }));

    try {
      const memory = await ownerConsoleApi.getMemory(signal);
      if (signal?.aborted) {
        return;
      }
      setState({
        loading: false,
        memory,
        error: null,
      });
    } catch (exc) {
      if (exc instanceof DOMException && exc.name === "AbortError") {
        return;
      }
      setState({
        loading: false,
        memory: null,
        error: exc instanceof Error ? exc : new Error("记忆快照加载失败"),
      });
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const memory = state.memory?.data;

  return (
    <section className="page memory-page">
      <header className="page-header">
        <div>
          <p className="page-header__eyebrow">主人控制台</p>
          <h1>记忆</h1>
        </div>
        <button
          className="refresh-button"
          type="button"
          onClick={() => void load()}
          disabled={state.loading}
        >
          <RefreshCw aria-hidden="true" size={16} />
          <span>刷新记忆</span>
        </button>
      </header>

      {state.loading ? (
        <section className="loading-panel" role="status">
          正在加载记忆快照
        </section>
      ) : null}

      {state.error ? (
        <ErrorState
          title="记忆快照暂不可用"
          description={apiErrorDescription(state.error)}
          details={
            state.error instanceof OwnerConsoleApiError
              ? state.error.code
              : undefined
          }
        />
      ) : null}

      {memory ? (
        <>
          <section className="data-toolbar" aria-label="记忆快照状态">
            <div>
              <p>快照时间</p>
              <strong>{memory.generated_at || "未知"}</strong>
            </div>
            <StatusBadge
              label="记忆正文"
              value={memory.memory_content_exposed ? "异常展示" : "未展示"}
              tone={memory.memory_content_exposed ? "danger" : "success"}
            />
            <StatusBadge
              label="检索"
              value={memory.retrieval_executed ? "异常执行" : "未执行"}
              tone={memory.retrieval_executed ? "danger" : "success"}
            />
            <StatusBadge
              label="索引重建"
              value={memory.index_rebuild_executed ? "异常执行" : "未执行"}
              tone={memory.index_rebuild_executed ? "danger" : "success"}
            />
          </section>

          <CountPanel memory={memory} />

          <section className="detail-grid">
            <section className="detail-panel">
              <h2>详细计数</h2>
              <DetailList
                items={[
                  {
                    label: "已摘要消息",
                    value: memory.counts.summarized_message_count,
                  },
                  {
                    label: "长期记忆主体",
                    value: memory.counts.manual_memory_subject_count,
                  },
                  {
                    label: "场景摘要",
                    value: memory.counts.gap_scene_summary_count,
                  },
                  {
                    label: "场景来源消息",
                    value: memory.counts.gap_scene_source_message_count,
                  },
                  {
                    label: "RAG 文档",
                    value: memory.counts.rag_document_count,
                  },
                  {
                    label: "RAG 活跃文档",
                    value: memory.counts.rag_active_document_count,
                  },
                  {
                    label: "RAG 向量",
                    value: memory.counts.rag_embedding_count,
                  },
                ]}
              />
            </section>
            <BoundaryPanel memory={memory} />
          </section>

          <ContextPolicyPanel policy={memory.context_policy} />

          <section className="detail-grid">
            <MemoryRagPanel memoryRag={memory.memory_rag} />
            <ProjectDocRagPanel projectDocRag={memory.project_doc_rag} />
          </section>
        </>
      ) : null}
    </section>
  );
}
