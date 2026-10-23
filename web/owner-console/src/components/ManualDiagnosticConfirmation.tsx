import type { ReactNode } from "react";

export function ManualDiagnosticConfirmation({
  label,
  title,
  children,
  running,
  onCancel,
  onConfirm,
}: {
  label: string;
  title: string;
  children: ReactNode;
  running: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="manual-diagnostic-confirmation" role="group" aria-label={label}>
      <strong>{title}</strong>
      <p>{children}</p>
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
  );
}
