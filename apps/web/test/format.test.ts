import { describe, expect, it } from "vitest";

import { nearToYocto } from "../src/lib/amount";
import {
  formatDays,
  formatNear,
  formatRelative,
  formatTimestamp,
  truncateAccount,
  truncateHash,
} from "../src/lib/format";

describe("nearToYocto", () => {
  it("converts a whole amount exactly", () => {
    expect(nearToYocto("1")).toBe("1000000000000000000000000");
    expect(nearToYocto("5")).toBe("5000000000000000000000000");
  });

  it("converts a fractional amount without rounding", () => {
    expect(nearToYocto("0.01")).toBe("10000000000000000000000");
    expect(nearToYocto("0.000000000000000000000001")).toBe("1");
  });

  it("rejects text that is not an amount", () => {
    expect(nearToYocto("")).toBeNull();
    expect(nearToYocto("-1")).toBeNull();
    expect(nearToYocto("1e18")).toBeNull();
    expect(nearToYocto("0.0000000000000000000000001")).toBeNull();
    expect(nearToYocto("abc")).toBeNull();
  });
});

describe("formatNear", () => {
  it("renders yoctoNEAR as NEAR", () => {
    expect(formatNear("10000000000000000000000")).toBe("0.01");
    expect(formatNear("5000000000000000000000000")).toBe("5");
    expect(formatNear("1")).toBe("0");
  });

  it("keeps four decimals by default and trims trailing zeros", () => {
    expect(formatNear("12345000000000000000000000")).toBe("12.345");
  });

  it("handles negative amounts", () => {
    expect(formatNear("-10000000000000000000000")).toBe("-0.01");
  });
});

describe("hash and account truncation", () => {
  it("keeps the head and tail of a hash", () => {
    const hash = "a".repeat(64);
    expect(truncateHash(hash)).toBe("aaaaaaaa…aaaaaa");
    expect(truncateHash("short")).toBe("short");
  });

  it("keeps the head and tail of an account", () => {
    expect(truncateAccount("mnemos-agent-76badc8e.testnet")).toBe("mnemos…tnet");
  });
});

describe("timestamps", () => {
  it("formats an ISO timestamp in UTC", () => {
    expect(formatTimestamp("2026-11-11T09:41:02.000Z")).toBe("2026-11-11 09:41:02Z");
  });

  it("renders a missing timestamp as a dash", () => {
    expect(formatTimestamp(null)).toBe("—");
    expect(formatTimestamp("not a date")).toBe("—");
  });

  it("describes recent times in words", () => {
    const now = Date.now();
    expect(formatRelative(new Date(now - 5_000))).toBe("just now");
    expect(formatRelative(new Date(now - 120_000))).toBe("2 minutes ago");
    expect(formatRelative(new Date(now - 7_200_000))).toBe("2 hours ago");
  });

  it("converts nanoseconds to days", () => {
    expect(formatDays("86400000000000")).toBe("1 day");
    expect(formatDays("172800000000000")).toBe("2 days");
  });
});
