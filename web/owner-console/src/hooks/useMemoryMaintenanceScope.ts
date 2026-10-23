import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ownerConsoleApi } from "../api/ownerConsoleApi";
import type { AccountPersonaProfile } from "../api/accountPersonaTypes";

export function useMemoryMaintenanceScope() {
  const [params, setParams] = useSearchParams();
  const [profiles, setProfiles] = useState<AccountPersonaProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const reload = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError("");
    try {
      const result = await ownerConsoleApi.getSettings(signal);
      if (signal?.aborted) return;
      setProfiles(result.data?.account_personas ?? []);
    } catch {
      if (signal?.aborted) return;
      setProfiles([]);
      setError("无法读取固定账号绑定，请刷新配置后重试。");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    void reload(controller.signal);
    return () => controller.abort();
  }, [reload]);
  const requested = params.get("memory_account");
  const selected = useMemo(() => requested !== null
    ? profiles.find((p) => p.bot_self_id === requested)
    : profiles.filter((p) => p.memory.storage === "legacy_database").length === 1
      ? profiles.find((p) => p.memory.storage === "legacy_database") : undefined,
  [profiles, requested]);
  const scope = selected?.memory.maintenance_scope ?? null;
  return {
    profiles, loading, scope, selectedAccount: requested ?? selected?.bot_self_id ?? "",
    error: error || (!loading && !scope ? "当前账号的持久记忆绑定不可用于维护，请检查配置或选择可用账号。" : ""),
    select: (account: string) => { const next = new URLSearchParams(params); next.set("memory_account", account); setParams(next); },
    reload,
  };
}
