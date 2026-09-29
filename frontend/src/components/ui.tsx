import type { ReactNode } from "react";

export function StatCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: "positive" | "negative";
}) {
  return (
    <div className={`card stat-card${tone ? ` ${tone}` : ""}`} data-label={label}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {hint && <div className="hint">{hint}</div>}
    </div>
  );
}

export function TypeBadge({ type }: { type: string }) {
  return <span className={`badge type-${type}`}>{type}</span>;
}

export function ErrorBanner({ message, code }: { message: string; code?: string }) {
  return (
    <div className="banner banner-error" role="alert">
      <strong>{code ? `${code}: ` : ""}</strong>
      {message}
    </div>
  );
}

export function SuccessBanner({ children }: { children: ReactNode }) {
  return (
    <div className="banner banner-success" role="status">
      {children}
    </div>
  );
}

export function InfoBanner({ children }: { children: ReactNode }) {
  return <div className="banner banner-info">{children}</div>;
}

export function LoadingBlock({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="loading-block" role="status">
      <span className="spinner" aria-hidden="true" />
      {label}
    </div>
  );
}

export function EmptyState({
  icon = "📂",
  title,
  children,
  action,
}: {
  icon?: string;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="card empty-state">
      <div className="icon" aria-hidden="true">
        {icon}
      </div>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}
