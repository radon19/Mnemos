/** Formatting helpers. Amounts and hashes are evidence, so they are exact. */

const YOCTO = 10n ** 24n;

export function formatNear(yocto: string | number | bigint, decimals = 4): string {
  const value = BigInt(yocto);
  const negative = value < 0n;
  const absolute = negative ? -value : value;
  const whole = absolute / YOCTO;
  const fraction = absolute % YOCTO;
  const padded = fraction.toString().padStart(24, "0").slice(0, decimals);
  const trimmed = padded.replace(/0+$/u, "");
  const sign = negative ? "-" : "";
  if (trimmed === "") {
    return `${sign}${whole}`;
  }
  return `${sign}${whole}.${trimmed}`;
}

export function formatTimestamp(value: string | number | Date | null): string {
  if (value === null) {
    return "—";
  }
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return date.toISOString().replace("T", " ").slice(0, 19) + "Z";
}

export function formatRelative(value: string | number | Date | null): string {
  if (value === null) {
    return "—";
  }
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) {
    return "just now";
  }
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  }
  const hours = Math.round(minutes / 60);
  if (hours < 24) {
    return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  }
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

/** Hashes are shown middle-truncated; the full value stays in the title. */
export function truncateHash(hash: string, head = 8, tail = 6): string {
  if (hash.length <= head + tail + 1) {
    return hash;
  }
  return `${hash.slice(0, head)}…${hash.slice(-tail)}`;
}

export function truncateAccount(account: string, head = 6, tail = 4): string {
  if (account.length <= head + tail + 1) {
    return account;
  }
  return `${account.slice(0, head)}…${account.slice(-tail)}`;
}

export function formatDays(nanos: string): string {
  const days = BigInt(nanos) / 86_400_000_000_000n;
  return `${days} day${days === 1n ? "" : "s"}`;
}

export function formatExpiry(nanos: string): string {
  const milliseconds = Number(BigInt(nanos) / 1_000_000n);
  return formatTimestamp(milliseconds);
}
