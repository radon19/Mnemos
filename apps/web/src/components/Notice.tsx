export interface NoticeProps {
  tone: "error" | "success" | "info";
  title: string;
  children?: React.ReactNode;
  className?: string;
}

const TONE: Record<NoticeProps["tone"], { wrap: string; label: string }> = {
  error: { wrap: "bg-destructive-soft text-ink", label: "text-destructive" },
  success: { wrap: "bg-verified-soft text-ink", label: "text-verified" },
  info: { wrap: "bg-sunken text-ink", label: "text-muted" },
};

/**
 * Errors say what happened and what to do next. Nothing here is decorative.
 */
export function Notice({
  tone,
  title,
  children,
  className = "",
}: NoticeProps): React.ReactNode {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`rounded-[var(--radius-card)] px-5 py-4 ${TONE[tone].wrap} ${className}`}
    >
      <p className={`field-label ${TONE[tone].label}`}>{title}</p>
      {children === undefined ? null : (
        <div className="mt-1 text-body text-ink">{children}</div>
      )}
    </div>
  );
}
