/** NEAR amount conversion without floating point. */

export const YOCTO_PER_NEAR = 10n ** 24n;

/**
 * Parse a NEAR amount into yoctoNEAR.
 *
 * Returns null when the text is not an amount: at most 24 decimals, no sign,
 * no exponent. The grant form shows the reason instead of sending a value the
 * contract would reject.
 */
export function nearToYocto(amount: string): string | null {
  const trimmed = amount.trim();
  if (!/^\d+(\.\d{1,24})?$/u.test(trimmed)) {
    return null;
  }
  const [whole = "0", fraction = ""] = trimmed.split(".");
  const padded = fraction.padEnd(24, "0");
  return (BigInt(whole) * YOCTO_PER_NEAR + BigInt(padded)).toString();
}
