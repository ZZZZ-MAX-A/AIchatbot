import {
  Brain,
  ChartNoAxesCombined,
  ClipboardCheck,
  FileClock,
  Gauge,
  ListChecks,
  LockKeyhole,
  RefreshCw,
  Settings,
  ShieldCheck,
  SearchCheck,
  Wifi,
  WifiOff,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import type { LucideIcon } from "lucide-react";

import { ownerConsoleApi } from "../api/ownerConsoleApi";
import type { OwnerConsoleSnapshot } from "../api/ownerConsoleTypes";
import { AutoRefreshControl } from "../components/AutoRefreshControl";
import { StatusBadge } from "../components/StatusBadge";
import { useControlledAutoRefresh } from "../hooks/useControlledAutoRefresh";
import { useAutoRefreshPreference } from "./AutoRefreshContext";
import {
  classifyOwnerConsoleAutoRefreshError,
  OWNER_CONSOLE_AUTO_REFRESH_FAILURE_LIMIT,
  OWNER_CONSOLE_HEALTH_REFRESH_INTERVAL_MS,
  OWNER_CONSOLE_VISIBILITY_RESUME_DELAY_MS,
} from "./ownerConsoleRefreshPolicy";

type LoadState = "loading" | "ready" | "error";

type NavItem = {
  label: string;
  path: string;
  icon: LucideIcon;
};

const navItems: NavItem[] = [
  { label: "概览", path: "/owner-console", icon: Gauge },
  { label: "任务", path: "/owner-console/tasks", icon: ListChecks },
  { label: "审批", path: "/owner-console/approvals", icon: ClipboardCheck },
  { label: "诊断", path: "/owner-console/diagnostics", icon: FileClock },
  {
    label: "可靠性",
    path: "/owner-console/reliability",
    icon: ChartNoAxesCombined,
  },
  { label: "联网查询", path: "/owner-console/external-read", icon: SearchCheck },
  { label: "记忆", path: "/owner-console/memory", icon: Brain },
  { label: "访问控制", path: "/owner-console/access-control", icon: LockKeyhole },
  { label: "设置", path: "/owner-console/settings", icon: Settings },
];

function formatRefreshTime(value: Date | null): string {
  if (!value) {
    return "尚未刷新";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(value);
}

export function AppShell() {
  const { enabled: autoRefreshEnabled, setEnabled: setAutoRefreshEnabled } =
    useAutoRefreshPreference();
  const [state, setState] = useState<LoadState>("loading");
  const [snapshot, setSnapshot] = useState<OwnerConsoleSnapshot>({
    health: null,
    routes: null,
  });
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  const refresh = useCallback(async (signal?: AbortSignal): Promise<boolean> => {
    setState("loading");
    setError(null);
    try {
      const [health, routes] = await Promise.all([
        ownerConsoleApi.getHealth(signal),
        ownerConsoleApi.getRoutes(signal),
      ]);
      setSnapshot({ health, routes });
      setLastRefreshed(new Date());
      setState("ready");
      return true;
    } catch (exc) {
      if (exc instanceof DOMException && exc.name === "AbortError") {
        return false;
      }
      setError(exc instanceof Error ? exc.message : "后端连接失败");
      setState("error");
      return false;
    }
  }, []);

  const refreshHealth = useCallback(async (signal: AbortSignal) => {
    const health = await ownerConsoleApi.getHealth(signal);
    if (signal.aborted) {
      return;
    }
    setSnapshot((current) => ({ ...current, health }));
    setLastRefreshed(new Date());
    setError(null);
  }, []);

  const autoRefresh = useControlledAutoRefresh({
    enabled: autoRefreshEnabled,
    intervalMs: OWNER_CONSOLE_HEALTH_REFRESH_INTERVAL_MS,
    refresh: refreshHealth,
    classifyError: classifyOwnerConsoleAutoRefreshError,
    failureLimit: OWNER_CONSOLE_AUTO_REFRESH_FAILURE_LIMIT,
    visibilityResumeDelayMs: OWNER_CONSOLE_VISIBILITY_RESUME_DELAY_MS,
  });

  const handleManualRefresh = useCallback(async () => {
    if (!autoRefresh.beginManualRefresh()) {
      return;
    }
    const succeeded = await refresh();
    autoRefresh.finishManualRefresh(succeeded);
  }, [
    autoRefresh.beginManualRefresh,
    autoRefresh.finishManualRefresh,
    refresh,
  ]);

  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => controller.abort();
  }, [refresh]);

  const status = useMemo(() => {
    const health = snapshot.health;
    const routes = snapshot.routes;
    const connected = state === "ready" && autoRefresh.lastError === null;
    const readOnly = health?.read_only === true && routes?.read_only === true;
    const writeClosed =
      health?.web_write_enabled === false &&
      routes?.web_write_enabled === false;
    const manualDiagnostics =
      health?.manual_diagnostic_actions_enabled === true;
    const schemaVersion =
      routes?.schema_version ?? health?.schema_version ?? "未知";
    const routeCount = routes?.data?.route_count ?? 0;

    return {
      connected,
      readOnly,
      writeClosed,
      manualDiagnostics,
      schemaVersion,
      routeCount,
    };
  }, [autoRefresh.lastError, snapshot, state]);

  const connectionError =
    autoRefresh.lastError?.message ??
    (state === "error" ? error ?? "后端连接失败" : null);

  return (
    <div className="app-shell">
      <aside className="side-nav" aria-label="主人控制台导航">
        <div className="side-nav__brand">
          <ShieldCheck aria-hidden="true" size={22} />
          <span>主人控制台</span>
        </div>
        <nav className="side-nav__items">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === "/owner-console"}
                className={({ isActive }) =>
                  isActive ? "side-nav__link is-active" : "side-nav__link"
                }
              >
                <Icon aria-hidden="true" size={18} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </aside>

      <div className="workspace">
        <header className="top-status-bar">
          <div className="top-status-bar__title">
            <span className="top-status-bar__eyebrow">主人控制台</span>
            <strong>诊断工作台</strong>
          </div>

          <div className="top-status-bar__badges" aria-live="polite">
            <StatusBadge
              label="快照读取"
              value={status.readOnly ? "只读" : "异常"}
              tone={status.readOnly ? "success" : "danger"}
            />
            <StatusBadge
              label="网页写入"
              value={status.writeClosed ? "已关闭" : "异常"}
              tone={status.writeClosed ? "success" : "danger"}
            />
            <StatusBadge
              label="手动诊断"
              value={status.manualDiagnostics ? "按需开放" : "未开放"}
              tone={status.manualDiagnostics ? "warning" : "success"}
            />
            <StatusBadge
              label="后端连接"
              value={
                state === "loading"
                  ? "连接中"
                  : status.connected
                    ? "已连接"
                    : "已断开"
              }
              tone={
                state === "loading"
                  ? "warning"
                  : status.connected
                    ? "success"
                    : "danger"
              }
            />
            <StatusBadge label="接口版本" value={status.schemaVersion} />
            <StatusBadge
              label="连接检查"
              value={formatRefreshTime(lastRefreshed)}
            />
          </div>

          <div className="top-status-bar__actions">
            <AutoRefreshControl
              enabled={autoRefreshEnabled}
              status={autoRefresh.status}
              onChange={setAutoRefreshEnabled}
            />
            <button
              className="refresh-button"
              type="button"
              onClick={() => void handleManualRefresh()}
              disabled={state === "loading" || autoRefresh.status === "refreshing"}
            >
              <RefreshCw aria-hidden="true" size={16} />
              <span>刷新</span>
            </button>
          </div>
        </header>

        {connectionError ? (
          <section className="connection-banner" role="status">
            <WifiOff aria-hidden="true" size={18} />
            <span>{connectionError}</span>
          </section>
        ) : (
          <section className="connection-banner connection-banner--ready">
            <Wifi aria-hidden="true" size={18} />
            <span>已加载只读接口契约，资源路由 {status.routeCount} 个</span>
          </section>
        )}

        <main className="workspace__main">
          <Outlet context={snapshot} />
        </main>
      </div>
    </div>
  );
}
