import type { ButtonHTMLAttributes } from "react";

export type ButtonTone = "primary" | "accent" | "quiet" | "destructive";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  tone?: ButtonTone;
}

const TONE: Record<ButtonTone, string> = {
  primary:
    "border border-ink bg-ink text-canvas hover:opacity-90 disabled:border-rule disabled:bg-transparent disabled:text-muted",
  accent:
    "border border-accent bg-accent text-white hover:opacity-90 disabled:border-rule disabled:bg-transparent disabled:text-muted",
  quiet:
    "border border-rule bg-transparent text-ink hover:border-ink disabled:border-rule disabled:text-muted",
  destructive:
    "border border-destructive bg-transparent text-destructive hover:bg-destructive-soft disabled:border-rule disabled:text-muted",
};

/**
 * Buttons are pills, the way a physical control is. A disabled button stays
 * legible: it turns to the muted ink rather than fading out, so the label can
 * still be read and the reason it is disabled stays visible.
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
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-5 py-2 text-body md:min-h-10 transition-colors disabled:cursor-not-allowed ${TONE[tone]} ${className}`}
      {...rest}
    />
  );
}
