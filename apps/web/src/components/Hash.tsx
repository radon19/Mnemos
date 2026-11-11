import { truncateHash } from "@/lib/format";

export interface HashProps {
  value: string;
  head?: number;
  tail?: number;
  /** Render the whole value, used where the hash is the subject of the row. */
  full?: boolean;
  label?: string;
  className?: string;
}

/**
 * A hash is content, not fine print. It is shown in the evidence face,
 * middle-truncated, with the full value available on hover and in the title.
 */
export function Hash({
  value,
  head = 8,
  tail = 6,
  full = false,
  label = "Receipt hash",
  className = "",
}: HashProps): React.ReactNode {
  if (value === "") {
    return <span className={`hash text-muted ${className}`}>—</span>;
  }
  return (
    <span
      className={`hash ${className}`}
      title={value}
      aria-label={`${label} ${value}`}
    >
      {full ? value : truncateHash(value, head, tail)}
    </span>
  );
}
