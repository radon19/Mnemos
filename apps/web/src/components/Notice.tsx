export interface NoticeProps {
  tone: "error" | "success" | "info";
  title: string;
  children?: React.ReactNode;
  className?: string;
}

const TONE_CLASS: Record<NoticeProps["tone"], string> = {
  error: "border-destructive text-destructive",
  success: "border-verified text-verified",
  info: "border-rule text-ink",
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
      className={`border-l bg-surface px-4 py-3 ${TONE_CLASS[tone]} ${className}`}
    >
      <p className="field-label">{title}</p>
      {children === undefined ? null : (
        <div className="mt-1 text-body text-ink">{children}</div>
      )}
    </div>
  );
}
