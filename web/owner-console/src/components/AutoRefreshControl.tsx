import type { AutoRefreshStatus } from "../hooks/useControlledAutoRefresh";

function statusLabel(status: AutoRefreshStatus): string {
  if (status === "refreshing") {
    return "检查中";
  }
  if (status === "paused_hidden") {
    return "页面隐藏";
  }
  if (status === "paused_error") {
    return "已暂停";
  }
  return status === "waiting" ? "已开启" : "已关闭";
}

export function AutoRefreshControl({
  enabled,
  status,
  onChange,
}: {
  enabled: boolean;
  status: AutoRefreshStatus;
  onChange: (enabled: boolean) => void;
}) {
  return (
    <label className="auto-refresh-control">
      <span className="auto-refresh-control__label">自动刷新</span>
      <input
        checked={enabled}
        onChange={(event) => onChange(event.currentTarget.checked)}
        type="checkbox"
      />
      <span className="auto-refresh-control__track" aria-hidden="true">
        <span className="auto-refresh-control__thumb" />
      </span>
      <span className="auto-refresh-control__state">{statusLabel(status)}</span>
    </label>
  );
}
