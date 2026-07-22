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
  vision_model: "视觉模型",
  vision_num_ctx: "视觉上下文上限",
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
    { key: "vision", label: "视觉配置", section: diagnostics.vision },
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

          {manualDiagnostics ? (
            <>
              <ManualProjectDocRagPanel
                snapshot={manualDiagnostics}
                confirming={probeConfirming}
                running={probeRunning || memoryRunning || mainLlmRunning}
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
                running={memoryRunning || probeRunning || mainLlmRunning}
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
                running={mainLlmRunning || probeRunning || memoryRunning}
                actionError={mainLlmError}
                onRequestConfirmation={() => {
                  setMainLlmError("");
                  setMainLlmConfirming(true);
                }}
                onCancel={() => setMainLlmConfirming(false)}
                onConfirm={() => void runMainLlmContract()}
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
