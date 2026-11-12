"use client";

import { useState } from "react";

import { truncateHash } from "@/lib/format";

export interface HashProps {
  value: string;
  head?: number;
  tail?: number;
  /** Render the whole value, used where the hash is the subject of the row. */
  full?: boolean;
  label?: string;
  className?: string;
  /** Show the copy control. */
  copyable?: boolean;
}

/**
 * A hash is content, not fine print. It is shown in the evidence face,
 * middle-truncated, with the full value available on hover, in the accessible
 * name and, when the reader wants it, on the clipboard.
 */
export function Hash({
  value,
  head = 8,
  tail = 6,
  full = false,
  label = "Receipt hash",
  className = "",
  copyable = false,
}: HashProps): React.ReactNode {
  const [copied, setCopied] = useState(false);

  if (value === "") {
    return <span className={`hash text-muted ${className}`}>—</span>;
  }

  const text = full ? value : truncateHash(value, head, tail);

  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <span className="hash" title={value} aria-label={`${label} ${value}`}>
        {text}
      </span>
      {copyable ? (
        <button
          type="button"
          className="field-label rounded-full border border-rule px-2 py-1 transition-colors hover:border-ink"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(value);
              setCopied(true);
              setTimeout(() => {
                setCopied(false);
              }, 1200);
            } catch {
              setCopied(false);
            }
          }}
          aria-label={`Copy the ${label.toLowerCase()}`}
        >
          {copied ? "Copied" : "Copy"}
        </button>
      ) : null}
    </span>
  );
}
