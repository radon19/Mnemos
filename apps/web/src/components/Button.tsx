import type { ButtonHTMLAttributes } from "react";

export type ButtonTone = "primary" | "quiet" | "destructive";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  tone?: ButtonTone;
}

const TONE: Record<ButtonTone, string> = {
  primary:
    "border border-ink bg-ink text-paper hover:bg-transparent hover:text-ink disabled:border-rule disabled:bg-transparent disabled:text-muted",
  quiet:
    "border border-rule bg-transparent text-ink hover:border-ink disabled:border-rule disabled:text-muted",
  destructive:
    "border border-destructive bg-transparent text-destructive hover:bg-destructive-bg disabled:border-rule disabled:text-muted",
};

/**
 * Buttons are square. A ledger does not have rounded corners, and a soft
 * shadow would hide the hairline rules the layout is built from.
 *
 * A disabled button stays legible: it turns to the muted ink rather than
 * fading out, so the label can still be read and the reason it is disabled
 * stays visible.
 */
export function Button({
  tone = "primary",
  className = "",
  type = "button",
  ...rest
}: ButtonProps): React.ReactNode {
  return (
    <button
      type={type}
      className={`inline-flex min-h-11 items-center justify-center gap-2 px-4 py-2 text-body transition-colors disabled:cursor-not-allowed ${TONE[tone]} ${className}`}
      {...rest}
    />
  );
}
