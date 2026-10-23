import type { AccountPersonaProfile } from "../api/accountPersonaTypes";
import type { MemoryMaintenanceScope } from "../api/memoryScopeTypes";

export function MemoryScopePanel({ profiles, scope, selectedAccount, loading, error, disabled, onSelect }: {
  profiles: AccountPersonaProfile[];
  scope: MemoryMaintenanceScope | null;
  selectedAccount: string;
  loading: boolean;
  error: string;
  disabled?: boolean;
  onSelect: (account: string) => void;
}) {
  return (
    <section className="detail-panel memory-scope-panel" aria-label="记忆维护范围">
      <h2>记忆维护范围</h2>
      <label>
        固定账号与人物
        <select value={selectedAccount} onChange={(event) => onSelect(event.target.value)} disabled={loading || disabled}>
          <option value="" disabled>{loading ? "正在读取账号绑定" : "选择记忆账号"}</option>
          {profiles.map((p) => <option key={p.bot_self_id} value={p.bot_self_id} disabled={!p.memory.maintenance_scope}>
            {p.persona_name} · {p.bot_self_id}{p.memory.maintenance_scope ? "" : "（持久记忆不可用）"}
          </option>)}
        </select>
      </label>
      {scope ? <p>当前人物：<strong>{scope.persona_name}</strong> · 记忆库：<code>{scope.database}</code> · 会话命名空间：<code>{scope.session_namespace}</code></p> : null}
      <p className="panel-note">范围只影响记忆统计与 MemoryRAG 一致性检查；每个人格库包含各自的群聊和私聊记录，原有受众隔离规则继续生效。项目文档检索、模型和语音检查使用各自配置。</p>
      {error ? <p role="alert" className="manual-diagnostic-panel__error">{error}</p> : null}
    </section>
  );
}
