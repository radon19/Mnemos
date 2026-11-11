export type StatusKind = "verified" | "pending" | "refused" | "revoked" | "neutral";

export interface StatusMarkProps {
  kind: StatusKind;
  label: string;
  className?: string;
}

const SHAPE: Record<StatusKind, string> = {
  verified: "bg-verified",
  pending: "border border-ink bg-transparent",
  refused: "border border-destructive bg-transparent",
  revoked: "bg-destructive",
  neutral: "border border-rule bg-transparent",
};

/**
 * Status is a word first and a mark second. The mark never carries the
 * meaning on its own.
 */
export function StatusMark({ kind, label, className = "" }: StatusMarkProps): React.ReactNode {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <span aria-hidden="true" className={`inline-block h-[7px] w-[7px] ${SHAPE[kind]}`} />
      <span className="field-label">{label}</span>
    </span>
  );
}
