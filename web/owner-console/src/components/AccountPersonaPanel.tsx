import { useEffect, useRef, useState } from "react";
import { ownerConsoleApi } from "../api/ownerConsoleApi";
import type { AccountPersonaModel, AccountPersonaProfile } from "../api/accountPersonaTypes";
import { StatusBadge } from "./StatusBadge";

const states: Record<string, string> = {
  enabled: "已启用", disabled: "未启用", unsupported: "尚未接入",
  incomplete: "配置不完整", blocked: "绑定异常，已阻止",
};
const memoryModes: Record<string, string> = {
  legacy_database: "原有持久记忆库", persona_database: "人格独立持久记忆库",
  process_memory: "进程短时记忆", unavailable: "配置异常，存储不可用",
};
const serviceTypes: Record<string, string> = {
  openai: "OpenAI 兼容接口", ollama: "Ollama", aliyun_bailian: "阿里云百炼",
  persona_grok: "人格视觉兼容接口",
  persona_deepseek: "DeepSeek 图片识别接口",
};

const reasoningEfforts: Record<string, string> = {
  low: "low（低）", high: "high（高）", max: "max（最高）",
};

function ModelDetails({ title, model }: { title: string; model: AccountPersonaModel }) {
  return <section className="persona-config-section">
    <h3>{title}</h3>
    <dl className="detail-list">
      <div><dt>模型</dt><dd>{model.model_name || "未配置"}</dd></div>
      <div><dt>服务类型</dt><dd>{serviceTypes[model.provider] || model.provider || "未确定"}</dd></div>
      <div><dt>配置来源</dt><dd>{model.source || "未接入"}</dd></div>
      <div><dt>服务地址</dt><dd>{model.base_url_redacted || "未配置"}</dd></div>
      <div><dt>凭据</dt><dd>{model.api_key_configured ? "已配置" : model.provider === "ollama" ? "无需凭据" : "未配置"}</dd></div>
      <div><dt>请求超时</dt><dd>{model.timeout_seconds} 秒</dd></div>
      {model.max_tokens !== undefined ? <div><dt>输出额度</dt><dd>{model.max_tokens} token（思考模式包含思考消耗）</dd></div> : null}
      {model.reasoning_effort !== undefined ? <>
        <div><dt>思考强度</dt><dd>{model.reasoning_effort ? reasoningEfforts[model.reasoning_effort] : "未指定（服务端默认）"}</dd></div>
        <div><dt>思考配置来源</dt><dd>{model.reasoning_effort_source || "服务端默认"}</dd></div>
      </> : null}
      <div><dt>配置状态</dt><dd>{model.configured ? "配置齐全" : "不可用或配置不完整"}</dd></div>
    </dl>
    {model.errors.length > 0 ? <p className="persona-config-error">{model.errors.join("、")}</p> : null}
  </section>;
}

function VoiceSample({ profile }: { profile: AccountPersonaProfile }) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const request = useRef<AbortController | null>(null);
  const objectUrl = useRef("");
  useEffect(() => () => {
    request.current?.abort();
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
  }, []);
  async function listen() {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setLoading(true); setError("");
    try {
      const blob = await ownerConsoleApi.getPersonaVoiceSample(profile.bot_self_id, controller.signal);
      if (controller.signal.aborted) return;
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
      objectUrl.current = URL.createObjectURL(blob);
      setUrl(objectUrl.current);
    } catch (exc) {
      if (!controller.signal.aborted) setError(exc instanceof Error ? exc.message : "音色样例加载失败");
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }
  return <div className="persona-voice-sample">
    <button type="button" className="refresh-button" onClick={() => void listen()}
      disabled={loading || !profile.voice.sample_available}>
      {loading ? "正在加载音色" : "试听音色"}
    </button>
    {url ? <audio controls autoPlay src={url} aria-label={`${profile.persona_name}音色样例`} /> : null}
    <p>{profile.voice.sample_available
      ? "播放当前音色的本地参考样例；情绪与实际合成效果在统一验收时检查。"
      : "当前配置的参考音频缺失或不可读，暂时无法试听。"}</p>
    {error ? <p role="alert">{error}</p> : null}
  </div>;
}

export function AccountPersonaPanel({ profiles, bindingErrors = [] }: { profiles: AccountPersonaProfile[]; bindingErrors?: string[] }) {
  return <section className="account-persona-list" aria-label="账号人格完整配置">
    <div><h2>账号与人格配置</h2><p>按账号展示当前配置解析结果和能力差异。绑定与配置仍通过部署文件维护。</p></div>
    {bindingErrors.length > 0 ? <p role="alert">绑定配置错误：{bindingErrors.join("、")}</p> : null}
    {profiles.length === 0 ? <p className="diagnostic-card__empty">未配置账号绑定</p> : null}
    {profiles.map((profile) => <article className="detail-panel account-persona-card" key={profile.bot_self_id}
      aria-label={`${profile.persona_name}账号配置`}>
      <header className="detail-panel__header">
        <div><h2>{profile.persona_name} · {profile.account_label}</h2><p>账号：{profile.bot_self_id}</p></div>
        <StatusBadge label="绑定与聊天配置" value={profile.ready ? "正常" : "异常"} tone={profile.ready ? "success" : "danger"} />
      </header>
      <dl className="detail-list">
        <div><dt>人格标识</dt><dd>{profile.persona_id}</dd></div>
        <div><dt>固定角色卡</dt><dd>{profile.role_card_key} · {profile.role_card_available ? "可用" : "不可用"}</dd></div>
      </dl>
      {profile.errors.length > 0 ? <p role="alert">配置错误：{profile.errors.join("、")}</p> : null}
      <div className="detail-grid persona-config-grid">
        <ModelDetails title="普通聊天模型" model={profile.chat_model} />
        <ModelDetails title="视觉模型" model={profile.vision_model} />
        <section className="persona-config-section">
          <h3>记忆库归属</h3>
          <dl className="detail-list">
            <div><dt>存储方式</dt><dd>{memoryModes[profile.memory.storage] || profile.memory.storage}</dd></div>
            <div><dt>数据库</dt><dd>{profile.memory.database || "不使用持久数据库"}</dd></div>
            <div><dt>本地文件</dt><dd>{profile.memory.database ? profile.memory.file_exists ? "已存在" : "尚未发现" : "不适用"}</dd></div>
            <div><dt>会话命名空间</dt><dd>{profile.memory.session_namespace || "不可用"}</dd></div>
            <div><dt>摘要模型</dt><dd>{profile.memory.summary_model.model_name || "未配置"} · {profile.memory.summary_model.source}</dd></div>
            <div><dt>向量模型</dt><dd>{profile.memory.embedding_model || "未配置"}</dd></div>
          </dl>
          <p>这里检查库归属和文件存在性；数据库完整性与历史污染尚未在此检查。</p>
        </section>
        <section className="persona-config-section">
          <h3>音色与语音</h3>
          <dl className="detail-list">
            <div><dt>音色</dt><dd>{profile.voice.voice_id || "未配置"}</dd></div>
            <div><dt>情绪</dt><dd>{profile.voice.emotion || "未配置"}</dd></div>
            <div><dt>配置来源</dt><dd>{profile.voice.source}</dd></div>
            <div><dt>语音回复</dt><dd>{profile.voice.enabled ? "已启用" : "未启用"}</dd></div>
            <div><dt>语音服务</dt><dd>{profile.voice.service_url_redacted || "未配置"}</dd></div>
            <div><dt>长度与冷却</dt><dd>{profile.voice.max_chars} 字 / {profile.voice.max_total_seconds} 秒 / 冷却 {profile.voice.cooldown_seconds} 秒</dd></div>
            <div><dt>请求超时</dt><dd>{profile.voice.timeout_seconds} 秒</dd></div>
            <div><dt>尾部噪声清理</dt><dd>{profile.voice.trim_trailing_noise ? "启用" : "未启用"}</dd></div>
          </dl>
          <VoiceSample key={`${profile.bot_self_id}:${profile.voice.voice_id}:${profile.voice.emotion}`} profile={profile} />
        </section>
      </div>
      <section className="persona-capability-section">
        <h3>能力与使用范围</h3>
        <div className="persona-capability-grid">
          {profile.capabilities.map((capability) => <div className="persona-capability" key={capability.key}>
            <StatusBadge label={capability.label} value={states[capability.state] || capability.state}
              tone={capability.state === "enabled" ? "success" : capability.state === "blocked" ? "danger" : capability.state === "incomplete" ? "warning" : "neutral"} />
            <p>{capability.detail}</p>
          </div>)}
        </div>
      </section>
      <details className="persona-extra-settings">
        <summary>场景模型与其他配置参数</summary>
        {profile.scene.assigned ? <ModelDetails title="SceneHub 场景回复模型" model={profile.scene.actor_model} /> : <p>当前账号没有分配共享场景演员。</p>}
        <dl className="detail-list">
          <div><dt>场景导演模型</dt><dd>{profile.scene.director_model || "未配置"}</dd></div>
          <div><dt>场景风格样例</dt><dd>{profile.scene.style_examples_status}</dd></div>
          <div><dt>普通聊天独立世界卡注入</dt><dd>{profile.scene.ordinary_world_card_injection ? "启用" : "保留原有加载方式"}</dd></div>
          <div><dt>聊天温度</dt><dd>{profile.parameters.temperature}</dd></div>
          <div><dt>私聊图片合并等待</dt><dd>{profile.parameters.vision_private_image_wait_seconds} 秒</dd></div>
          <div><dt>记忆检索数量与长度</dt><dd>Top {profile.parameters.memory_rag_top_k} / {profile.parameters.memory_rag_max_context_chars} 字</dd></div>
          <div><dt>表情意图模型</dt><dd>{profile.parameters.sticker_classifier_model || "当前人格未接入"}</dd></div>
          <div><dt>表情冷却与频率</dt><dd>{profile.parameters.sticker_cooldown_seconds} 秒 / 每小时 {profile.parameters.sticker_max_per_hour} 次</dd></div>
          <div><dt>图片生成 / 编辑模型</dt><dd>{profile.parameters.image_generation_model} / {profile.parameters.image_edit_model}</dd></div>
          <div><dt>天气策略</dt><dd>{profile.parameters.weather_mode}</dd></div>
        </dl>
      </details>
    </article>)}
  </section>;
}
