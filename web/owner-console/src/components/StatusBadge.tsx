type StatusBadgeTone = "neutral" | "success" | "warning" | "danger";

type StatusBadgeProps = {
  label: string;
  value: string;
  tone?: StatusBadgeTone;
};

export function StatusBadge({
  label,
  value,
  tone = "neutral",
}: StatusBadgeProps) {
  return (
    <span className={`status-badge status-badge--${tone}`}>
      <span className="status-badge__label">{label}</span>
      <span className="status-badge__value">{value}</span>
    </span>
  );
}
