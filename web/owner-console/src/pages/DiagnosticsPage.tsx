import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  OwnerConsoleApiError,
  ownerConsoleApi,
} from "../api/ownerConsoleApi";
import type {
  OwnerConsoleDiagnosticsEnvelope,
  OwnerConsoleHealthSnapshot,
  OwnerConsoleMainLlmContractRun,
  OwnerConsoleManualDiagnosticRun,
  OwnerConsoleManualDiagnosticsEnvelope,
  OwnerConsoleManualDiagnosticsSnapshot,
  OwnerConsoleMemoryRagConsistencyRun,
  OwnerConsoleRuntimeBoundary,
  OwnerConsoleTextSnapshotSection,
  OwnerConsoleTtsSynthesisRun,
  OwnerConsoleCloudVisionRun,
} from "../api/ownerConsoleTypes";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";

type DiagnosticsPageState = {
  loading: boolean;
  diagnostics: OwnerConsoleDiagnosticsEnvelope | null;
  manualDiagnostics: OwnerConsoleManualDiagnosticsEnvelope | null;
  error: Error | null;
};

type DiagnosticSection = {
  key: string;
  label: string;
  section: OwnerConsoleTextSnapshotSection;
};

type BooleanInterpretation = {
  true: string;
  false: string;
};

const EVIDENCE_LABELS: Record<string, string> = {
  transport: "传输方式",
  mode: "运行模式",
  web_write_enabled: "网页写入能力",
  diagnostics_snapshot: "诊断快照模式",
  external_probes_executed: "外部探测",
  qq_adapter_imported: "QQ 适配器导入",
  diagnostics_module_imported: "主动诊断模块导入",
  bot_owner_configured: "主人身份配置",
  enable_private_chat: "私聊功能",
  enable_group_chat: "群聊功能",
  enable_main_agent: "MainAgent",
  main_agent_use_llm: "MainAgent 模型规划",
  enable_chat_graph_runtime: "聊天图运行时",
  enable_vision: "视觉功能",
  vision_provider: "视觉提供方",
  vision_model: "视觉模型",
  vision_region: "视觉地域",
  workspace_configured: "百炼 Workspace URL",
  credentials_configured: "百炼 API Key",
  thinking_enabled: "思考模式",
  client_automatic_retry: "客户端自动重试",
  automatic_local_fallback: "本地模型自动回退",
  vision_max_images: "单次图片上限",
  ollama_probe_executed: "Ollama 探测",
  vision_inference_executed: "视觉推理",
  image_cache_stats_collected: "图片缓存统计",
  image_cache_ttl_seconds: "图片缓存有效期",
  private_image_wait_seconds: "私聊图片等待时间",
  memory_snapshot: "记忆统计快照",
  message_count: "消息记录数",
  session_count: "会话数",
  session_summary_count: "会话摘要数",
  summarized_message_count: "已摘要消息数",
  manual_memory_count: "手工记忆数",
  rag_document_count: "RAG 文档数",
  rag_embedding_count: "RAG 向量数",
  memory_content_exposed: "记忆正文暴露",
  project_doc_content_exposed: "项目文档正文暴露",
  retrieval_executed: "检索执行",
  index_rebuild_executed: "索引重建",
  enable_tts: "语音功能",
  tts_voice_configured: "语音角色配置",
  tts_auto_start: "TTS 自动启动",
  tts_probe_executed: "TTS 探测",
  recent_error_log_read: "近期错误日志读取",
  recent_errors_collected: "近期错误采集",
};

const BOOLEAN_INTERPRETATIONS: Record<string, BooleanInterpretation> = {
  web_write_enabled: { true: "已开放", false: "未开放" },
  external_probes_executed: {
    true: "已执行",
    false: "未执行（符合只读边界）",
  },
  qq_adapter_imported: {
    true: "已导入",
    false: "未导入（符合只读边界）",
  },
  diagnostics_module_imported: {
    true: "已导入",
    false: "未导入（符合只读边界）",
  },
  bot_owner_configured: { true: "已配置", false: "未配置" },
  enable_private_chat: { true: "已启用", false: "未启用" },
  enable_group_chat: { true: "已启用", false: "未启用" },
  enable_main_agent: { true: "已启用", false: "未启用" },
  main_agent_use_llm: { true: "已启用", false: "未启用" },
  enable_chat_graph_runtime: { true: "已启用", false: "未启用" },
  enable_vision: { true: "已启用", false: "未启用" },
  workspace_configured: { true: "已配置", false: "未配置" },
  credentials_configured: { true: "已配置", false: "未配置" },
  thinking_enabled: { true: "已启用", false: "已关闭" },
  client_automatic_retry: { true: "已启用", false: "已关闭" },
  automatic_local_fallback: { true: "已启用", false: "已关闭" },
  ollama_probe_executed: {
    true: "已执行",
    false: "未执行（符合只读边界）",
  },
  vision_inference_executed: {
    true: "已执行",
    false: "未执行（符合只读边界）",
  },
  image_cache_stats_collected: {
    true: "已采集",
    false: "未采集（当前快照不主动探测）",
  },
  memory_content_exposed: { true: "已暴露", false: "未暴露" },
  project_doc_content_exposed: { true: "已暴露", false: "未暴露" },
  retrieval_executed: {
    true: "已执行",
    false: "未执行（符合只读边界）",
  },
  index_rebuild_executed: {
    true: "已执行",
    false: "未执行（符合只读边界）",
  },
  enable_tts: { true: "已启用", false: "未启用" },
  tts_voice_configured: { true: "已配置", false: "未配置" },
  tts_auto_start: { true: "已启用", false: "未启用" },
  tts_probe_executed: {
    true: "已执行",
    false: "未执行（符合只读边界）",
  },
  recent_error_log_read: {
    true: "已读取",
    false: "未读取（当前快照不读取日志）",
  },
  recent_errors_collected: {
    true: "已采集",
    false: "未采集（不代表没有错误）",
  },
};

const VALUE_INTERPRETATIONS: Record<string, Record<string, string>> = {
  transport: { http: "HTTP" },
  mode: { read_only: "只读" },
  diagnostics_snapshot: { read_only: "只读" },
  memory_snapshot: { collected: "已采集" },
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

function diagnosticSections(
  diagnostics: OwnerConsoleHealthSnapshot,
): DiagnosticSection[] {
  return [
    { key: "bot_status", label: "Owner Console", section: diagnostics.bot_status },
    { key: "diagnostics", label: "只读诊断边界", section: diagnostics.diagnostics },
    { key: "config", label: "功能配置", section: diagnostics.config },
    { key: "vision", label: "云端视觉配置", section: diagnostics.vision },
    { key: "image_cache", label: "图片缓存", section: diagnostics.image_cache },
    { key: "memory", label: "记忆与 RAG 统计", section: diagnostics.memory },
    { key: "tts", label: "语音配置", section: diagnostics.tts },
    { key: "recent_errors", label: "近期错误取证", section: diagnostics.recent_errors },
  ];
}

function interpretEvidenceLine(line: string): {
  label: string;
  value: string;
} {
  if (line === "Owner Console HTTP API: ok") {
    return { label: "Owner Console HTTP API", value: "可读取" };
  }

  const separatorIndex = line.indexOf("=");
  if (separatorIndex < 1) {
    return { label: "原始信息", value: "请查看下方技术证据" };
  }

  const key = line.slice(0, separatorIndex);
  const rawValue = line.slice(separatorIndex + 1);
  const booleanInterpretation = BOOLEAN_INTERPRETATIONS[key];
  let value = rawValue;

  if (booleanInterpretation && (rawValue === "true" || rawValue === "false")) {
    value = booleanInterpretation[rawValue];
  } else {
    value = VALUE_INTERPRETATIONS[key]?.[rawValue] ?? rawValue;
  }

  return {
    label: EVIDENCE_LABELS[key] ?? key,
    value,
  };
}

function SnapshotCard({ item }: { item: DiagnosticSection }) {
  const summaryDuplicatesLines =
    item.section.summary_text.trim() === item.section.display_lines.join("\n").trim();

  return (
    <section
      className={`diagnostic-card${item.section.ok ? "" : " diagnostic-card--attention"}`}
      data-section={item.key}
    >
      <header>
        <div className="diagnostic-card__title">
          <h2>{item.label}</h2>
          <code>{item.section.title}</code>
        </div>
        <StatusBadge
          label="快照"
          value={item.section.ok ? "已读取" : "读取异常"}
          tone={item.section.ok ? "success" : "warning"}
        />
      </header>
      {item.section.summary_text && !summaryDuplicatesLines ? (
        <p className="diagnostic-card__summary">{item.section.summary_text}</p>
      ) : null}
      {item.section.error ? (
        <div className="diagnostic-card__error">
          <strong>原始错误</strong>
          <code>{item.section.error}</code>
        </div>
      ) : null}
      {item.section.display_lines.length > 0 ? (
        <ul className="diagnostic-evidence-list">
          {item.section.display_lines.map((line, index) => {
            const interpretation = interpretEvidenceLine(line);
            return (
              <li key={`${index}:${line}`}>
                <span>{interpretation.label}</span>
                <strong>{interpretation.value}</strong>
                <code>{line}</code>
              </li>
            );
          })}
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
      <header className="observation-panel__header">
        <h2>{title}</h2>
        <span>{lines.length} 条</span>
      </header>
      {lines.length > 0 ? (
        <ul className="diagnostic-lines">
          {lines.map((line, index) => (
            <li key={`${index}:${line}`}>{line}</li>
          ))}
        </ul>
      ) : (
        <p className="diagnostic-card__empty">本次快照无结构化观测记录</p>
      )}
    </section>
  );
}

function ManualProjectDocRagPanel({
  snapshot,
  confirming,
  running,
  actionError,
  onRequestConfirmation,
  onCancel,
  onConfirm,
}: {
  snapshot: OwnerConsoleManualDiagnosticsSnapshot;
  confirming: boolean;
  running: boolean;
  actionError: string;
  onRequestConfirmation: () => void;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!snapshot.project_doc_rag_probe_enabled) {
    return null;
  }

  const latest: OwnerConsoleManualDiagnosticRun | null =
    snapshot.project_doc_rag_latest_run;
  const latestRunning = latest?.status === "running";
  const tone =
    latest?.outcome === "succeeded"
      ? "success"
      : latest?.outcome === "failed"
        ? "warning"
        : "neutral";

  return (
    <section className="manual-diagnostic-panel" aria-label="项目文档 RAG 手动检查">
      <header>
        <div>
          <p>主人手动动作</p>
          <h2>项目文档 RAG 真实检索</h2>
        </div>
        <StatusBadge
          label="最近结果"
          value={
            latestRunning || running
              ? "执行中"
              : latest?.outcome === "succeeded"
                ? "通过"
                : latest?.outcome === "failed"
                  ? "需要查看"
                  : "尚未执行"
          }
          tone={tone}
        />
      </header>

      <p className="manual-diagnostic-panel__description">
        使用一个后端固定问题执行一次真实 embedding 与前五项检索；不显示查询正文或文档片段，不重建索引，不调用 Main LLM 或 DevContext。
      </p>

      {latest ? (
        <div className="manual-diagnostic-result">
          <strong>{latest.code_label}</strong>
          <div className="manual-diagnostic-result__metrics">
            <span>
              生产功能 {latest.runtime_feature_enabled ? "已启用" : "未启用"}
            </span>
            <span>项目文档 {latest.document_count}</span>
            <span>有效向量 {latest.embedding_count}</span>
            <span>返回结果 {latest.result_count}</span>
            <span>最高相似度 {latest.top_score.toFixed(3)}</span>
          </div>
          <code>{`workflow=${latest.workflow}`}</code>
          <code>{`stage=${latest.stage}`}</code>
          <code>{`code=${latest.code}`}</code>
          <code>{`runtime_feature_enabled=${latest.runtime_feature_enabled}`}</code>
          <small>
            只证明本次固定检索结果；不代表所有项目问题都能正确召回。
          </small>
        </div>
      ) : null}

      {actionError ? (
        <p className="manual-diagnostic-panel__error">{actionError}</p>
      ) : null}

      {confirming ? (
        <div className="manual-diagnostic-confirmation" role="group" aria-label="确认项目文档 RAG 手动检查">
          <strong>确认执行一次固定真实检索？</strong>
          <p>
            本次只调用 embedding 一次，不自动重试；不会写索引、读取私人记忆、运行 DevContext 或执行后续诊断。
          </p>
          <div>
            <button className="secondary-button" type="button" onClick={onCancel}>
              取消
            </button>
            <button
              className="manual-diagnostic-action"
              type="button"
              onClick={onConfirm}
              disabled={running}
            >
              {running ? "正在检查" : "确认并执行"}
            </button>
          </div>
        </div>
      ) : (
        <button
          className="manual-diagnostic-action"
          type="button"
          onClick={onRequestConfirmation}
          disabled={running || latestRunning}
        >
          {running || latestRunning ? "正在检查" : "手动检查检索"}
        </button>
      )}

      <p className="manual-diagnostic-panel__boundary">
        自动诊断关闭 · 配置写入关闭 · 业务数据写入关闭 · 索引重建关闭
      </p>
    </section>
  );
}

function ManualMemoryRagConsistencyPanel({
  snapshot,
  confirming,
  running,
  actionError,
  onRequestConfirmation,
  onCancel,
  onConfirm,
}: {
  snapshot: OwnerConsoleManualDiagnosticsSnapshot;
  confirming: boolean;
  running: boolean;
  actionError: string;
  onRequestConfirmation: () => void;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!snapshot.memory_rag_consistency_enabled) {
    return null;
  }

  const latest: OwnerConsoleMemoryRagConsistencyRun | null =
    snapshot.memory_rag_consistency_latest_run;
  const latestRunning = latest?.status === "running";
  const tone =
    latest?.outcome === "succeeded"
      ? "success"
      : latest?.outcome === "attention" || latest?.outcome === "failed"
        ? "warning"
        : "neutral";

  return (
    <section className="manual-diagnostic-panel" aria-label="MemoryRAG 索引一致性手动检查">
      <header>
        <div>
          <p>主人手动动作</p>
          <h2>MemoryRAG 索引一致性</h2>
        </div>
        <StatusBadge
          label="最近结果"
          value={
            latestRunning || running
              ? "执行中"
              : latest?.outcome === "succeeded"
                ? "通过"
                : latest?.outcome === "attention"
                  ? "需要关注"
                  : latest?.outcome === "failed"
                    ? "执行失败"
                    : "尚未执行"
          }
          tone={tone}
        />
      </header>

      <p className="manual-diagnostic-panel__description">
        只读核对活动记忆文档、当前有效向量与来源映射；不读取记忆正文，不执行私人记忆检索或 embedding，不重建索引。
      </p>

      {latest ? (
        <div className="manual-diagnostic-result">
          <strong>{latest.code_label}</strong>
          <div className="manual-diagnostic-result__metrics">
            <span>生产功能 {latest.runtime_feature_enabled ? "已启用" : "未启用"}</span>
            <span>活动文档 {latest.active_document_count}</span>
            <span>有效向量 {latest.valid_embedding_count}</span>
            <span>缺失向量 {latest.missing_embedding_count}</span>
            <span>事实文档 {latest.manual_fact_documents}</span>
            <span>偏好文档 {latest.manual_preference_documents}</span>
            <span>会话摘要 {latest.session_summary_documents}</span>
            <span>事实缺失向量 {latest.missing_manual_fact_embeddings}</span>
            <span>偏好缺失向量 {latest.missing_manual_preference_embeddings}</span>
            <span>摘要缺失向量 {latest.missing_session_summary_embeddings}</span>
            <span>来源缺失 {latest.active_documents_missing_source + latest.source_records_missing_document}</span>
            <span>软删除历史向量 {latest.inactive_document_embedding_count}</span>
          </div>
          <code>{`workflow=${latest.workflow}`}</code>
          <code>{`stage=${latest.stage}`}</code>
          <code>{`code=${latest.code}`}</code>
          <code>{`memory_content_read=${latest.memory_content_read}`}</code>
          <code>{`private_memory_query_executed=${latest.private_memory_query_executed}`}</code>
          <code>{`embedding_called=${latest.embedding_called}`}</code>
          <small>
            只证明索引结构的一致性；不会验证私人记忆能否回答具体问题。
          </small>
        </div>
      ) : null}

      {actionError ? (
        <p className="manual-diagnostic-panel__error">{actionError}</p>
      ) : null}

      {confirming ? (
        <div className="manual-diagnostic-confirmation" role="group" aria-label="确认 MemoryRAG 索引一致性手动检查">
          <strong>确认执行一次只读一致性核对？</strong>
          <p>
            本次不读取记忆正文、不执行检索或 embedding，不写数据库、不重建索引，也不自动修复缺失向量。
          </p>
          <div>
            <button className="secondary-button" type="button" onClick={onCancel}>
              取消
            </button>
            <button
              className="manual-diagnostic-action"
              type="button"
              onClick={onConfirm}
              disabled={running}
            >
              {running ? "正在检查" : "确认并执行"}
            </button>
          </div>
        </div>
      ) : (
        <button
          className="manual-diagnostic-action"
          type="button"
          onClick={onRequestConfirmation}
          disabled={running || latestRunning}
        >
          {running || latestRunning ? "正在检查" : "手动检查一致性"}
        </button>
      )}

      <p className="manual-diagnostic-panel__boundary">
        私人记忆检索关闭 · embedding 调用关闭 · 数据库写入关闭 · 自动修复关闭
      </p>
    </section>
  );
}

function ManualMainLlmContractPanel({
  snapshot,
  confirming,
  running,
  actionError,
  onRequestConfirmation,
  onCancel,
  onConfirm,
}: {
  snapshot: OwnerConsoleManualDiagnosticsSnapshot;
  confirming: boolean;
  running: boolean;
  actionError: string;
  onRequestConfirmation: () => void;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!snapshot.main_llm_contract_enabled) {
    return null;
  }

  const latest: OwnerConsoleMainLlmContractRun | null =
    snapshot.main_llm_contract_latest_run;
  const latestRunning = latest?.status === "running";
  const tone =
    latest?.outcome === "succeeded"
      ? "success"
      : latest?.outcome === "attention" || latest?.outcome === "failed"
        ? "warning"
        : "neutral";
  const tokenValue = (value: number | null) =>
    value === null ? "未提供" : String(value);

  return (
    <section className="manual-diagnostic-panel" aria-label="Main LLM 固定问答手动检查">
      <header>
        <div>
          <p>主人手动动作</p>
          <h2>Main LLM 固定问答</h2>
        </div>
        <StatusBadge
          label="最近结果"
          value={
            latestRunning || running
              ? "执行中"
              : latest?.outcome === "succeeded"
                ? "通过"
                : latest?.outcome === "attention"
                  ? "需要关注"
                  : latest?.outcome === "failed"
                    ? "执行失败"
                    : "尚未执行"
          }
          tone={tone}
        />
      </header>

      <p className="manual-diagnostic-panel__description">
        向当前 Main LLM 发送一个后端固定问题，判断模型能否正常回答并返回固定 JSON；不读取聊天、记忆或项目文档，也不评价任意问题应选择什么工具。
      </p>

      {latest ? (
        <div className="manual-diagnostic-result">
          <strong>{latest.code_label}</strong>
          <div className="manual-diagnostic-result__metrics">
            <span>模型 {latest.configured_model || "未提供"}</span>
            <span>响应 {latest.elapsed_ms} ms</span>
            <span>输入 token {tokenValue(latest.input_tokens)}</span>
            <span>输出 token {tokenValue(latest.output_tokens)}</span>
            <span>总 token {tokenValue(latest.total_tokens)}</span>
            <span>回答合同 {latest.contract_valid ? "通过" : "未通过"}</span>
          </div>
          <code>{`workflow=${latest.workflow}`}</code>
          <code>{`stage=${latest.stage}`}</code>
          <code>{`code=${latest.code}`}</code>
          <code>{`llm_called=${latest.llm_called}`}</code>
          <code>{`client_automatic_retry=${latest.client_automatic_retry}`}</code>
          <code>{`tool_definitions_sent=${latest.tool_definitions_sent}`}</code>
          <code>{`database_write_allowed=${latest.database_write_allowed}`}</code>
          <small>
            只证明本次固定问题能够正常运行和回答；不代表任意问题质量或工具选择能力。
          </small>
        </div>
      ) : null}

      {actionError ? (
        <p className="manual-diagnostic-panel__error">{actionError}</p>
      ) : null}

      {confirming ? (
        <div className="manual-diagnostic-confirmation" role="group" aria-label="确认 Main LLM 固定问答检查">
          <strong>确认执行一次远程固定问答？</strong>
          <p>
            本次会产生一次少量 token 的 Main LLM 调用；只发送固定合成问题，不发送主人输入、聊天历史、项目文档或私人记忆，不开放工具，也不自动重试。
          </p>
          <div>
            <button className="secondary-button" type="button" onClick={onCancel}>
              取消
            </button>
            <button
              className="manual-diagnostic-action"
              type="button"
              onClick={onConfirm}
              disabled={running}
            >
              {running ? "正在检查" : "确认并执行"}
            </button>
          </div>
        </div>
      ) : (
        <button
          className="manual-diagnostic-action"
          type="button"
          onClick={onRequestConfirmation}
          disabled={running || latestRunning}
        >
          {running || latestRunning ? "正在检查" : "手动检查问答"}
        </button>
      )}

      <p className="manual-diagnostic-panel__boundary">
        自由问题关闭 · 工具定义关闭 · 客户端重试关闭 · 业务数据库写入关闭
      </p>
    </section>
  );
}

function ManualTtsSynthesisPanel({
  snapshot,
  confirming,
  running,
  reviewRunning,
  actionError,
  previewUrl,
  previewLoading,
  previewCompleted,
  onRequestConfirmation,
  onCancel,
  onConfirm,
  onLoadPreview,
  onPreviewEnded,
  onAcceptQuality,
  onRejectQuality,
}: {
  snapshot: OwnerConsoleManualDiagnosticsSnapshot;
  confirming: boolean;
  running: boolean;
  reviewRunning: boolean;
  actionError: string;
  previewUrl: string;
  previewLoading: boolean;
  previewCompleted: boolean;
  onRequestConfirmation: () => void;
  onCancel: () => void;
  onConfirm: () => void;
  onLoadPreview: (runId: number) => void;
  onPreviewEnded: () => void;
  onAcceptQuality: (runId: number) => void;
  onRejectQuality: (runId: number) => void;
}) {
  if (!snapshot.tts_synthesis_enabled) {
    return null;
  }

  const latest: OwnerConsoleTtsSynthesisRun | null =
    snapshot.tts_synthesis_latest_run;
  const latestRunning = latest?.status === "running";
  const tone =
    latest?.outcome === "succeeded"
      ? "success"
      : latest?.outcome === "attention" || latest?.outcome === "failed"
        ? "warning"
        : "neutral";

  return (
    <section className="manual-diagnostic-panel" aria-label="TTS 一键生命周期手动检查">
      <header>
        <div>
          <p>主人手动动作</p>
          <h2>TTS 一键生命周期</h2>
        </div>
        <StatusBadge
          label="最近结果"
          value={
            latestRunning || running
              ? "执行中"
              : latest?.audio_quality_review_required
                ? "等待试听"
              : latest?.outcome === "succeeded"
                ? "通过"
                : latest?.outcome === "attention"
                  ? "需要关注"
                  : latest?.outcome === "failed"
                    ? "执行失败"
                    : "尚未执行"
          }
          tone={tone}
        />
      </header>

      <p className="manual-diagnostic-panel__description">
        检查本机 TTS 是否在线；明确离线时临时启动一个受管理进程，执行一次后端固定中文合成，验证并清理本次音频，再只停止诊断自己启动的进程。
      </p>

      {latest ? (
        <div className="manual-diagnostic-result">
          <strong>{latest.code_label}</strong>
          <div className="manual-diagnostic-result__metrics">
            <span>总延迟 {latest.elapsed_ms} ms</span>
            <span>启动 {latest.startup_elapsed_ms} ms</span>
            <span>健康检查 {latest.health_elapsed_ms} ms</span>
            <span>合成 {latest.synthesis_elapsed_ms} ms</span>
            <span>清理 {latest.cleanup_elapsed_ms} ms</span>
            <span>WAV {latest.output_bytes} bytes</span>
            <span>WAV 时长 {latest.output_duration_ms} ms</span>
            <span>调用前模型 {latest.model_loaded_before ? "已加载" : "未加载"}</span>
            <span>调用前 runtime {latest.runtime_imported_before ? "已导入" : "未导入"}</span>
            <span>
              服务来源 {latest.service_preexisting ? "原本在线" : latest.service_started ? "诊断启动" : "未启动"}
            </span>
            <span>
              服务收尾 {latest.service_owned_by_diagnostic ? latest.service_stopped ? "已停止" : "停止不完整" : "不停止已有服务"}
            </span>
            <span>最终 WAV {latest.output_retained ? "仍保留" : "已清理"}</span>
            <span>分段目录 {latest.segment_directory_retained ? "仍保留" : "已清理"}</span>
            <span>
              主人听检 {latest.audio_quality_reviewed ? latest.audio_quality_accepted ? "合格" : "不合格" : latest.audio_quality_review_required ? "待确认" : "未进入"}
            </span>
          </div>
          <div className="manual-diagnostic-audio-review">
            <p>
              应听到：<strong>{latest.fixed_text}</strong>
            </p>
            {latest.audio_quality_review_required && latest.audio_preview_available ? (
              <>
                {previewUrl ? (
                  <audio
                    aria-label="TTS 固定语音临时试听"
                    controls
                    controlsList="nodownload noplaybackrate"
                    preload="metadata"
                    src={previewUrl}
                    onEnded={onPreviewEnded}
                  />
                ) : (
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={previewLoading || reviewRunning}
                    onClick={() => onLoadPreview(latest.run_id)}
                  >
                    {previewLoading ? "正在加载试听" : "加载临时试听"}
                  </button>
                )}
                <p>
                  请确认内容完整准确、中文清晰，没有明显截断、重复、卡顿、爆音、杂音或不合理长静音。
                </p>
                <div className="manual-diagnostic-audio-review__actions">
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={!previewUrl || reviewRunning}
                    onClick={() => onRejectQuality(latest.run_id)}
                  >
                    {reviewRunning ? "正在提交" : "语音不合格"}
                  </button>
                  <button
                    className="manual-diagnostic-action"
                    type="button"
                    disabled={!previewUrl || !previewCompleted || reviewRunning}
                    onClick={() => onAcceptQuality(latest.run_id)}
                  >
                    {reviewRunning ? "正在提交" : previewCompleted ? "语音合格" : "播放结束后确认合格"}
                  </button>
                </div>
              </>
            ) : null}
          </div>
          <code>{`workflow=${latest.workflow}`}</code>
          <code>{`stage=${latest.stage}`}</code>
          <code>{`code=${latest.code}`}</code>
          <code>{`technical_outcome=${latest.technical_outcome}`}</code>
          <code>{`technical_code=${latest.technical_code}`}</code>
          <code>{`audio_preview_available=${latest.audio_preview_available}`}</code>
          <code>{`audio_quality_review_required=${latest.audio_quality_review_required}`}</code>
          <code>{`audio_quality_reviewed=${latest.audio_quality_reviewed}`}</code>
          <code>{`audio_quality_accepted=${latest.audio_quality_accepted}`}</code>
          <code>{`audio_preview_persisted=${latest.audio_preview_persisted}`}</code>
          <code>{`audio_preview_path_exposed=${latest.audio_preview_path_exposed}`}</code>
          <code>{`audio_review_action_executed=${latest.audio_review_action_executed}`}</code>
          <code>{`tts_called=${latest.tts_called}`}</code>
          <code>{`runtime_imported_before=${latest.runtime_imported_before}`}</code>
          <code>{`service_preexisting=${latest.service_preexisting}`}</code>
          <code>{`service_start_attempted=${latest.service_start_attempted}`}</code>
          <code>{`service_started=${latest.service_started}`}</code>
          <code>{`service_owned_by_diagnostic=${latest.service_owned_by_diagnostic}`}</code>
          <code>{`service_stop_attempted=${latest.service_stop_attempted}`}</code>
          <code>{`service_stopped=${latest.service_stopped}`}</code>
          <code>{`artifact_cleanup_attempted=${latest.artifact_cleanup_attempted}`}</code>
          <code>{`artifact_cleanup_succeeded=${latest.artifact_cleanup_succeeded}`}</code>
          <code>{`output_retained=${latest.output_retained}`}</code>
          <code>{`segment_directory_retained=${latest.segment_directory_retained}`}</code>
          <code>{`automatic_retry=${latest.automatic_retry}`}</code>
          <code>{`qq_write_executed=${latest.qq_write_executed}`}</code>
          <code>{`reliability_event_written=${latest.reliability_event_written}`}</code>
          <code>{`database_write_allowed=${latest.database_write_allowed}`}</code>
          <code>{`local_file_write_expected=${latest.local_file_write_expected}`}</code>
          <code>{`cleanup_executed=${latest.cleanup_executed}`}</code>
          <code>{`partial_artifact_state=${latest.partial_artifact_state}`}</code>
          <small>
            最终通过还要求主人听完固定音频并明确确认质量合格；只代表本次固定文本，不代表任意文本、QQ 语音或长期运行稳定性。
          </small>
        </div>
      ) : null}

      {actionError ? (
        <p className="manual-diagnostic-panel__error">{actionError}</p>
      ) : null}

      {confirming ? (
        <div className="manual-diagnostic-confirmation" role="group" aria-label="确认 TTS 一键生命周期检查">
          <strong>确认执行一次 TTS 生命周期诊断？</strong>
          <p>
            若服务明确离线，诊断会启动一个受管理 TTS 子进程，等待健康后完成一次固定合成；服务原本在线则直接复用且绝不停止。验证后只清理本次 artifact ID 的最终 WAV 与分段目录，并且只停止本次持有句柄的进程。不会扫描或结束其他 Python 进程，不会发送 QQ、写业务数据库或可靠性事件，也不会调用 LLM/RAG 或自动重试合成。
          </p>
          <div>
            <button className="secondary-button" type="button" onClick={onCancel}>
              取消
            </button>
            <button
              className="manual-diagnostic-action"
              type="button"
              onClick={onConfirm}
              disabled={running}
            >
              {running ? "正在检查" : "确认并执行"}
            </button>
          </div>
        </div>
      ) : (
        <button
          className="manual-diagnostic-action"
          type="button"
          onClick={onRequestConfirmation}
          disabled={running || latestRunning || Boolean(latest?.audio_quality_review_required)}
        >
          {running || latestRunning ? "正在检查" : latest?.audio_quality_review_required ? "等待主人听检" : "检查启动、合成与清理"}
        </button>
      )}

      <p className="manual-diagnostic-panel__boundary">
        固定文本 · 磁盘立即清理 · 临时内存试听 · 主人听检门控 · 自动重试关闭 · QQ 发送关闭
      </p>
    </section>
  );
}

function ManualCloudVisionPanel({
  snapshot,
  confirming,
  running,
  reviewRunning,
  actionError,
  previewUrl,
  previewLoading,
  previewLoaded,
  onRequestConfirmation,
  onCancel,
  onConfirm,
  onLoadPreview,
  onPreviewLoaded,
  onAcceptQuality,
  onRejectQuality,
}: {
  snapshot: OwnerConsoleManualDiagnosticsSnapshot;
  confirming: boolean;
  running: boolean;
  reviewRunning: boolean;
  actionError: string;
  previewUrl: string;
  previewLoading: boolean;
  previewLoaded: boolean;
  onRequestConfirmation: () => void;
  onCancel: () => void;
  onConfirm: () => void;
  onLoadPreview: () => void;
  onPreviewLoaded: () => void;
  onAcceptQuality: (runId: number) => void;
  onRejectQuality: (runId: number) => void;
}) {
  if (!snapshot.cloud_vision_enabled) {
    return null;
  }

  const latest: OwnerConsoleCloudVisionRun | null =
    snapshot.cloud_vision_latest_run;
  const latestRunning = latest?.status === "running";
  const tone =
    latest?.outcome === "succeeded"
      ? "success"
      : latest?.outcome === "attention" || latest?.outcome === "failed"
        ? "warning"
        : "neutral";
  const tokenValue = (value: number | null) =>
    value === null ? "未提供" : String(value);

  return (
    <section className="manual-diagnostic-panel" aria-label="阿里云百炼固定图片手动检查">
      <header>
        <div>
          <p>主人手动动作</p>
          <h2>阿里云百炼固定图片识别</h2>
        </div>
        <StatusBadge
          label="最近结果"
          value={
            latestRunning || running
              ? "执行中"
              : latest?.outcome === "succeeded"
                ? "通过"
                : latest?.outcome === "attention"
                  ? "需要关注"
                  : latest?.outcome === "failed"
                    ? "执行失败"
                    : "尚未执行"
          }
          tone={tone}
        />
      </header>

      <p className="manual-diagnostic-panel__description">
        使用正式表情库中固定登记的 500×500 owner_private PNG，向阿里云百炼北京地域 qwen3.7-flash 发送一次内容与感情色彩描述请求；图片会外发，供应商侧处理与留存不受应用控制，清理后的回复与参考图会展示给主人判断准确性。
      </p>

      {latest ? (
        <div className="manual-diagnostic-result">
          <strong>{latest.code_label}</strong>
          <div className="manual-diagnostic-result__metrics">
            <span>提供方 阿里云百炼</span>
            <span>地域 北京</span>
            <span>配置模型 {latest.configured_model || "未提供"}</span>
            <span>返回模型 {latest.returned_model || "未提供"}</span>
            <span>请求耗时 {latest.request_elapsed_ms} ms</span>
            <span>输入 token {tokenValue(latest.input_tokens)}</span>
            <span>输出 token {tokenValue(latest.output_tokens)}</span>
            <span>总 token {tokenValue(latest.total_tokens)}</span>
            <span>固定 PNG {latest.fixed_image_bytes} bytes</span>
            <span>固定样例 {latest.reference_sticker_id || "未登记"}</span>
            <span>图片合同 {latest.fixed_image_contract_valid ? "通过" : "未通过"}</span>
            <span>基础回复合同 {latest.response_contract_valid ? "通过" : "未通过"}</span>
            <span>
              主人质检 {latest.visual_quality_reviewed ? latest.visual_quality_accepted ? "合格" : "不合格" : latest.visual_quality_review_required ? "待确认" : "未进入"}
            </span>
            <span>URL {latest.workspace_configured ? "已配置" : "未配置"}</span>
            <span>API Key {latest.credentials_configured ? "已配置" : "未配置"}</span>
            <span>回复清理 {latest.response_cleanup_applied ? "已执行" : "无需清理"}</span>
            <span>图片外发 {latest.external_image_upload_executed ? "已执行" : "未执行"}</span>
          </div>
          {latest.response_preview ? (
            <div className="manual-diagnostic-vision-review">
              <div>
                <h3>模型实际中文描述</h3>
                <p>{latest.response_description || "未提供有效中文描述"}</p>
              </div>
              <details>
                <summary>查看清理后的模型回复</summary>
                <pre>{latest.response_preview}</pre>
              </details>
              {latest.reference_preview_available ? (
                previewUrl ? (
                  <img
                    src={previewUrl}
                    alt="固定视觉诊断参考表情"
                    onLoad={onPreviewLoaded}
                  />
                ) : (
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={previewLoading || reviewRunning}
                    onClick={onLoadPreview}
                  >
                    {previewLoading ? "正在加载参考图" : "加载固定参考图"}
                  </button>
                )
              ) : null}
              {latest.visual_quality_review_required ? (
                <div className="manual-diagnostic-vision-review__actions">
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={!previewUrl || reviewRunning}
                    onClick={() => onRejectQuality(latest.run_id)}
                  >
                    {reviewRunning ? "正在提交" : "描述不合格"}
                  </button>
                  <button
                    className="manual-diagnostic-action"
                    type="button"
                    disabled={!previewLoaded || reviewRunning}
                    onClick={() => onAcceptQuality(latest.run_id)}
                  >
                    {reviewRunning ? "正在提交" : previewLoaded ? "描述合格" : "参考图加载后确认合格"}
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}
          <code>{`workflow=${latest.workflow}`}</code>
          <code>{`stage=${latest.stage}`}</code>
          <code>{`code=${latest.code}`}</code>
          <code>{`provider=${latest.provider}`}</code>
          <code>{`region=${latest.region}`}</code>
          <code>{`cloud_vision_called=${latest.cloud_vision_called}`}</code>
          <code>{`request_count=${latest.request_count}`}</code>
          <code>{`response_contract_valid=${latest.response_contract_valid}`}</code>
          <code>{`response_mode=${latest.response_mode}`}</code>
          <code>{`structured_output_requested=${latest.structured_output_requested}`}</code>
          <code>{`semantic_contract_automatically_validated=${latest.semantic_contract_automatically_validated}`}</code>
          <code>{`owner_visual_judgment_required=${latest.owner_visual_judgment_required}`}</code>
          <code>{`reference_sticker_id=${latest.reference_sticker_id}`}</code>
          <code>{`registered_reference_asset_read=${latest.registered_reference_asset_read}`}</code>
          <code>{`response_cleanup_applied=${latest.response_cleanup_applied}`}</code>
          <code>{`external_image_upload_planned=${latest.external_image_upload_planned}`}</code>
          <code>{`external_image_upload_executed=${latest.external_image_upload_executed}`}</code>
          <code>{`provider_side_persistence_controlled_by_app=${latest.provider_side_persistence_controlled_by_app}`}</code>
          <code>{`technical_outcome=${latest.technical_outcome}`}</code>
          <code>{`technical_code=${latest.technical_code}`}</code>
          <code>{`visual_quality_review_required=${latest.visual_quality_review_required}`}</code>
          <code>{`visual_quality_reviewed=${latest.visual_quality_reviewed}`}</code>
          <code>{`visual_quality_accepted=${latest.visual_quality_accepted}`}</code>
          <code>{`visual_review_action_executed=${latest.visual_review_action_executed}`}</code>
          <code>{`response_preview_persisted=${latest.response_preview_persisted}`}</code>
          <code>{`client_automatic_retry=${latest.client_automatic_retry}`}</code>
          <code>{`tool_definitions_sent=${latest.tool_definitions_sent}`}</code>
          <code>{`thinking_enabled=${latest.thinking_enabled}`}</code>
          <code>{`api_key_exposed=${latest.api_key_exposed}`}</code>
          <code>{`workspace_id_exposed=${latest.workspace_id_exposed}`}</code>
          <code>{`image_base64_exposed=${latest.image_base64_exposed}`}</code>
          <code>{`local_gpu_model_loaded=${latest.local_gpu_model_loaded}`}</code>
          <code>{`qq_write_executed=${latest.qq_write_executed}`}</code>
          <code>{`database_write_allowed=${latest.database_write_allowed}`}</code>
          <code>{`project_artifact_write_expected=${latest.project_artifact_write_expected}`}</code>
          <code>{`local_vision_called=${latest.local_vision_called}`}</code>
          <small>
            只证明本次固定表情通过百炼北京地域 qwen3.7-flash 的单次请求和主人描述质检结果；不代表任意图片质量、长期稳定性、QQ 图片下载或 Main LLM 工具选择能力。
          </small>
        </div>
      ) : null}

      {actionError ? (
        <p className="manual-diagnostic-panel__error">{actionError}</p>
      ) : null}

      {confirming ? (
        <div className="manual-diagnostic-confirmation" role="group" aria-label="确认阿里云百炼固定图片检查">
          <strong>确认把固定 owner_private 表情发送到阿里云百炼？</strong>
          <p>
            本次只读取正式表情库固定登记且哈希锁定的 aike_affection_005.png，并发送到阿里云百炼北京地域，调用 qwen3.7-flash 一次。应用无法控制供应商侧的数据处理与留存；不会读取聊天、QQ 临时图片或图片缓存，不会写业务数据库、发送 QQ、自动重试或切换其他模型。
          </p>
          <div>
            <button className="secondary-button" type="button" onClick={onCancel}>
              取消
            </button>
            <button
              className="manual-diagnostic-action"
              type="button"
              onClick={onConfirm}
              disabled={running}
            >
              {running ? "正在检查" : "确认并执行"}
            </button>
          </div>
        </div>
      ) : (
        <button
          className="manual-diagnostic-action"
          type="button"
          onClick={onRequestConfirmation}
          disabled={running || latestRunning || Boolean(latest?.visual_quality_review_required)}
        >
          {running || latestRunning ? "正在检查" : latest?.visual_quality_review_required ? "等待主人检查描述" : "检查百炼表情描述与感情色彩"}
        </button>
      )}

      <p className="manual-diagnostic-panel__boundary">
        固定 owner_private PNG 外发 · 北京地域 · qwen3.7-flash · 情感描述 · 主人质检 · 自动重试与 fallback 关闭
      </p>
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
    manualDiagnostics: null,
    error: null,
  });
  const [probeConfirming, setProbeConfirming] = useState(false);
  const [probeRunning, setProbeRunning] = useState(false);
  const [probeError, setProbeError] = useState("");
  const [memoryConfirming, setMemoryConfirming] = useState(false);
  const [memoryRunning, setMemoryRunning] = useState(false);
  const [memoryError, setMemoryError] = useState("");
  const [mainLlmConfirming, setMainLlmConfirming] = useState(false);
  const [mainLlmRunning, setMainLlmRunning] = useState(false);
  const [mainLlmError, setMainLlmError] = useState("");
  const [ttsConfirming, setTtsConfirming] = useState(false);
  const [ttsRunning, setTtsRunning] = useState(false);
  const [ttsError, setTtsError] = useState("");
  const [ttsPreviewUrl, setTtsPreviewUrl] = useState("");
  const [ttsPreviewLoading, setTtsPreviewLoading] = useState(false);
  const [ttsPreviewCompleted, setTtsPreviewCompleted] = useState(false);
  const [ttsReviewRunning, setTtsReviewRunning] = useState(false);
  const [visionConfirming, setVisionConfirming] = useState(false);
  const [visionRunning, setVisionRunning] = useState(false);
  const [visionError, setVisionError] = useState("");
  const [visionPreviewUrl, setVisionPreviewUrl] = useState("");
  const [visionPreviewLoading, setVisionPreviewLoading] = useState(false);
  const [visionPreviewLoaded, setVisionPreviewLoaded] = useState(false);
  const [visionReviewRunning, setVisionReviewRunning] = useState(false);

  useEffect(() => {
    return () => {
      if (ttsPreviewUrl) {
        URL.revokeObjectURL(ttsPreviewUrl);
      }
    };
  }, [ttsPreviewUrl]);

  useEffect(() => {
    return () => {
      if (visionPreviewUrl) {
        URL.revokeObjectURL(visionPreviewUrl);
      }
    };
  }, [visionPreviewUrl]);

  const load = useCallback(async (signal?: AbortSignal) => {
    setState((current) => ({
      ...current,
      loading: true,
      error: null,
    }));

    try {
      const [diagnostics, manualDiagnostics] = await Promise.all([
        ownerConsoleApi.getDiagnostics(signal),
        ownerConsoleApi.getManualDiagnostics(signal),
      ]);
      if (signal?.aborted) {
        return;
      }
      setState({
        loading: false,
        diagnostics,
        manualDiagnostics,
        error: null,
      });
    } catch (exc) {
      if (exc instanceof DOMException && exc.name === "AbortError") {
        return;
      }
      setState({
        loading: false,
        diagnostics: null,
        manualDiagnostics: null,
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
  const manualDiagnostics = state.manualDiagnostics?.data;
  const manualDiagnosticsUnavailable = Boolean(
    manualDiagnostics &&
      (!manualDiagnostics.manual_diagnostic_actions_enabled ||
        manualDiagnostics.supported_workflows.length === 0),
  );
  const sections = diagnostics ? diagnosticSections(diagnostics) : [];
  const failedSections = sections.filter((item) => !item.section.ok);
  const readSectionCount = sections.length - failedSections.length;
  const externalProbesSkipped = diagnostics?.diagnostics.display_lines.includes(
    "external_probes_executed=false",
  );

  const runProjectDocRagProbe = useCallback(async () => {
    setProbeRunning(true);
    setProbeError("");
    try {
      const result = await ownerConsoleApi.runProjectDocRagProbe();
      setState((current) => {
        if (!current.manualDiagnostics?.data) {
          return current;
        }
        return {
          ...current,
          manualDiagnostics: {
            ...current.manualDiagnostics,
            generated_at: result.generated_at,
            data: {
              ...current.manualDiagnostics.data,
              generated_at: result.generated_at,
              latest_run: result.data,
              project_doc_rag_latest_run: result.data,
            },
          },
        };
      });
      setProbeConfirming(false);
    } catch (exc) {
      setProbeError(apiErrorDescription(exc instanceof Error ? exc : new Error("手动检查失败")));
    } finally {
      setProbeRunning(false);
    }
  }, []);

  const runMemoryRagConsistency = useCallback(async () => {
    setMemoryRunning(true);
    setMemoryError("");
    try {
      const result = await ownerConsoleApi.runMemoryRagConsistency();
      setState((current) => {
        if (!current.manualDiagnostics?.data) {
          return current;
        }
        return {
          ...current,
          manualDiagnostics: {
            ...current.manualDiagnostics,
            generated_at: result.generated_at,
            data: {
              ...current.manualDiagnostics.data,
              generated_at: result.generated_at,
              latest_run: result.data,
              memory_rag_consistency_latest_run: result.data,
            },
          },
        };
      });
      setMemoryConfirming(false);
    } catch (exc) {
      setMemoryError(apiErrorDescription(exc instanceof Error ? exc : new Error("一致性检查失败")));
    } finally {
      setMemoryRunning(false);
    }
  }, []);

  const runMainLlmContract = useCallback(async () => {
    setMainLlmRunning(true);
    setMainLlmError("");
    try {
      const result = await ownerConsoleApi.runMainLlmContract();
      setState((current) => {
        if (!current.manualDiagnostics?.data) {
          return current;
        }
        return {
          ...current,
          manualDiagnostics: {
            ...current.manualDiagnostics,
            generated_at: result.generated_at,
            data: {
              ...current.manualDiagnostics.data,
              generated_at: result.generated_at,
              latest_run: result.data,
              main_llm_contract_latest_run: result.data,
            },
          },
        };
      });
      setMainLlmConfirming(false);
    } catch (exc) {
      setMainLlmError(
        apiErrorDescription(
          exc instanceof Error ? exc : new Error("Main LLM 固定问答失败"),
        ),
      );
    } finally {
      setMainLlmRunning(false);
    }
  }, []);

  const applyTtsResult = useCallback(
    (data: OwnerConsoleTtsSynthesisRun, generatedAt: string) => {
      setState((current) => {
        if (!current.manualDiagnostics?.data) {
          return current;
        }
        return {
          ...current,
          manualDiagnostics: {
            ...current.manualDiagnostics,
            generated_at: generatedAt,
            data: {
              ...current.manualDiagnostics.data,
              generated_at: generatedAt,
              latest_run: data,
              tts_synthesis_latest_run: data,
            },
          },
        };
      });
    },
    [],
  );

  const resetTtsPreview = useCallback(() => {
    setTtsPreviewUrl("");
    setTtsPreviewCompleted(false);
  }, []);

  const runTtsSynthesis = useCallback(async () => {
    setTtsRunning(true);
    setTtsError("");
    resetTtsPreview();
    try {
      const result = await ownerConsoleApi.runTtsSynthesis();
      if (!result.data) {
        throw new Error("TTS 固定合成结果缺失");
      }
      applyTtsResult(result.data, result.generated_at);
      setTtsConfirming(false);
    } catch (exc) {
      setTtsError(
        apiErrorDescription(
          exc instanceof Error ? exc : new Error("TTS 固定合成失败"),
        ),
      );
    } finally {
      setTtsRunning(false);
    }
  }, [applyTtsResult, resetTtsPreview]);

  const loadTtsAudioPreview = useCallback(async (runId: number) => {
    setTtsPreviewLoading(true);
    setTtsError("");
    setTtsPreviewCompleted(false);
    try {
      const blob = await ownerConsoleApi.getTtsAudioPreview(runId);
      const url = URL.createObjectURL(blob);
      setTtsPreviewUrl(url);
    } catch (exc) {
      setTtsError(
        apiErrorDescription(
          exc instanceof Error ? exc : new Error("TTS 临时试听加载失败"),
        ),
      );
    } finally {
      setTtsPreviewLoading(false);
    }
  }, []);

  const reviewTtsAudioQuality = useCallback(
    async (runId: number, accepted: boolean) => {
      setTtsReviewRunning(true);
      setTtsError("");
      try {
        const result = accepted
          ? await ownerConsoleApi.acceptTtsAudioQuality(runId)
          : await ownerConsoleApi.rejectTtsAudioQuality(runId);
        if (!result.data) {
          throw new Error("TTS 主人听检结果缺失");
        }
        applyTtsResult(result.data, result.generated_at);
        resetTtsPreview();
      } catch (exc) {
        setTtsError(
          apiErrorDescription(
            exc instanceof Error ? exc : new Error("TTS 主人听检提交失败"),
          ),
        );
      } finally {
        setTtsReviewRunning(false);
      }
    },
    [applyTtsResult, resetTtsPreview],
  );

  const applyVisionResult = useCallback(
    (data: OwnerConsoleCloudVisionRun, generatedAt: string) => {
      setState((current) => {
        if (!current.manualDiagnostics?.data) {
          return current;
        }
        return {
          ...current,
          manualDiagnostics: {
            ...current.manualDiagnostics,
            generated_at: generatedAt,
            data: {
              ...current.manualDiagnostics.data,
              generated_at: generatedAt,
              latest_run: data,
              cloud_vision_latest_run: data,
            },
          },
        };
      });
    },
    [],
  );

  const resetVisionPreview = useCallback(() => {
    setVisionPreviewUrl("");
    setVisionPreviewLoaded(false);
  }, []);

  const runVisionInference = useCallback(async () => {
    setVisionRunning(true);
    setVisionError("");
    resetVisionPreview();
    try {
      const result = await ownerConsoleApi.runCloudVisionFixedDescription();
      if (!result.data) {
        throw new Error("视觉固定表情诊断结果缺失");
      }
      applyVisionResult(result.data, result.generated_at);
      setVisionConfirming(false);
    } catch (exc) {
      setVisionError(
        apiErrorDescription(
          exc instanceof Error ? exc : new Error("视觉固定图片诊断失败"),
        ),
      );
    } finally {
      setVisionRunning(false);
    }
  }, [applyVisionResult, resetVisionPreview]);

  const loadVisionReferencePreview = useCallback(async () => {
    setVisionPreviewLoading(true);
    setVisionError("");
    setVisionPreviewLoaded(false);
    try {
      const blob = await ownerConsoleApi.getCloudVisionReferencePreview();
      const url = URL.createObjectURL(blob);
      setVisionPreviewUrl(url);
    } catch (exc) {
      setVisionError(
        apiErrorDescription(
          exc instanceof Error ? exc : new Error("视觉固定参考图加载失败"),
        ),
      );
    } finally {
      setVisionPreviewLoading(false);
    }
  }, []);

  const reviewVisionResponseQuality = useCallback(
    async (runId: number, accepted: boolean) => {
      setVisionReviewRunning(true);
      setVisionError("");
      try {
        const result = accepted
          ? await ownerConsoleApi.acceptCloudVisionResponseQuality(runId)
          : await ownerConsoleApi.rejectCloudVisionResponseQuality(runId);
        if (!result.data) {
          throw new Error("视觉主人质检结果缺失");
        }
        applyVisionResult(result.data, result.generated_at);
      } catch (exc) {
        setVisionError(
          apiErrorDescription(
            exc instanceof Error ? exc : new Error("视觉主人质检提交失败"),
          ),
        );
      } finally {
        setVisionReviewRunning(false);
      }
    },
    [applyVisionResult],
  );

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
              label="读取成功"
              value={`${readSectionCount}/${sections.length}`}
              tone={failedSections.length === 0 ? "success" : "warning"}
            />
            <StatusBadge
              label="读取异常"
              value={String(failedSections.length)}
              tone={failedSections.length === 0 ? "success" : "warning"}
            />
          </section>

          <section
            className={`diagnostics-reading diagnostics-reading--${
              failedSections.length === 0 ? "success" : "warning"
            }`}
            aria-label="当前诊断解读"
          >
            <strong>
              {failedSections.length === 0
                ? `${sections.length} 个诊断区块均已读取；当前没有区块级读取异常。`
                : `${sections.length} 个诊断区块中有 ${failedSections.length} 个读取异常：${failedSections
                    .map((item) => item.label)
                    .join("、")}。`}
            </strong>
            <p>
              {externalProbesSkipped
                ? "这是一份只读配置与统计快照，未执行外部探测；“未执行”或“未采集”描述取证边界，不等同于功能异常。"
                : "这里的总体判断只表示快照区块能否读取，不证明外部服务持续健康。"}
            </p>
          </section>

          {manualDiagnosticsUnavailable ? (
            <section
              className="manual-diagnostic-panel manual-diagnostic-panel--disabled"
              aria-label="手动诊断配置状态"
            >
              <header>
                <div>
                  <p>主人手动动作</p>
                  <h2>手动诊断当前未开放</h2>
                </div>
                <StatusBadge label="当前进程" value="未授权工作流" tone="warning" />
              </header>
              <p className="manual-diagnostic-panel__description">
                手动诊断功能代码和历史结果没有被删除；当前 Owner Console
                进程没有显式启用已批准的固定工作流，因此不会显示或接受诊断动作。
              </p>
              <p className="manual-diagnostic-panel__boundary">
                普通快照仍保持只读 · 不会自动运行诊断 · 需要按已批准工作流重新启动本地控制台
              </p>
            </section>
          ) : null}

          {manualDiagnostics ? (
            <>
              <ManualProjectDocRagPanel
                snapshot={manualDiagnostics}
                confirming={probeConfirming}
                running={probeRunning || memoryRunning || mainLlmRunning || ttsRunning || ttsReviewRunning || visionRunning || visionReviewRunning}
                actionError={probeError}
                onRequestConfirmation={() => {
                  setProbeError("");
                  setProbeConfirming(true);
                }}
                onCancel={() => setProbeConfirming(false)}
                onConfirm={() => void runProjectDocRagProbe()}
              />
              <ManualMemoryRagConsistencyPanel
                snapshot={manualDiagnostics}
                confirming={memoryConfirming}
                running={memoryRunning || probeRunning || mainLlmRunning || ttsRunning || ttsReviewRunning || visionRunning || visionReviewRunning}
                actionError={memoryError}
                onRequestConfirmation={() => {
                  setMemoryError("");
                  setMemoryConfirming(true);
                }}
                onCancel={() => setMemoryConfirming(false)}
                onConfirm={() => void runMemoryRagConsistency()}
              />
              <ManualMainLlmContractPanel
                snapshot={manualDiagnostics}
                confirming={mainLlmConfirming}
                running={mainLlmRunning || probeRunning || memoryRunning || ttsRunning || ttsReviewRunning || visionRunning || visionReviewRunning}
                actionError={mainLlmError}
                onRequestConfirmation={() => {
                  setMainLlmError("");
                  setMainLlmConfirming(true);
                }}
                onCancel={() => setMainLlmConfirming(false)}
                onConfirm={() => void runMainLlmContract()}
              />
              <ManualTtsSynthesisPanel
                snapshot={manualDiagnostics}
                confirming={ttsConfirming}
                running={ttsRunning || probeRunning || memoryRunning || mainLlmRunning || visionRunning || visionReviewRunning}
                reviewRunning={ttsReviewRunning}
                actionError={ttsError}
                previewUrl={ttsPreviewUrl}
                previewLoading={ttsPreviewLoading}
                previewCompleted={ttsPreviewCompleted}
                onRequestConfirmation={() => {
                  setTtsError("");
                  setTtsConfirming(true);
                }}
                onCancel={() => setTtsConfirming(false)}
                onConfirm={() => void runTtsSynthesis()}
                onLoadPreview={(runId) => void loadTtsAudioPreview(runId)}
                onPreviewEnded={() => setTtsPreviewCompleted(true)}
                onAcceptQuality={(runId) => void reviewTtsAudioQuality(runId, true)}
                onRejectQuality={(runId) => void reviewTtsAudioQuality(runId, false)}
              />
              <ManualCloudVisionPanel
                snapshot={manualDiagnostics}
                confirming={visionConfirming}
                running={visionRunning || probeRunning || memoryRunning || mainLlmRunning || ttsRunning || ttsReviewRunning}
                reviewRunning={visionReviewRunning}
                actionError={visionError}
                previewUrl={visionPreviewUrl}
                previewLoading={visionPreviewLoading}
                previewLoaded={visionPreviewLoaded}
                onRequestConfirmation={() => {
                  setVisionError("");
                  setVisionConfirming(true);
                }}
                onCancel={() => setVisionConfirming(false)}
                onConfirm={() => void runVisionInference()}
                onLoadPreview={() => void loadVisionReferencePreview()}
                onPreviewLoaded={() => setVisionPreviewLoaded(true)}
                onAcceptQuality={(runId) => void reviewVisionResponseQuality(runId, true)}
                onRejectQuality={(runId) => void reviewVisionResponseQuality(runId, false)}
              />
            </>
          ) : null}

          <div className="diagnostic-card-grid">
            {sections.map((item) => (
              <SnapshotCard key={item.key} item={item} />
            ))}
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
