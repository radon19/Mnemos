"use client";

import { useEffect, useId, useRef } from "react";
import { Button } from "./Button";

/** Native dialog supplies focus trapping, inert background and Escape. */
export function ConfirmDialog({ open, title, children, busy = false, onCancel, onConfirm, confirmLabel, cancelLabel, intent = "destructive", busyLabel = "Revoking…" }: {
  open: boolean; title: string; children: React.ReactNode; busy?: boolean;
  onCancel: () => void; onConfirm: () => void; confirmLabel: string; cancelLabel: string;
  intent?: "destructive" | "purchase"; busyLabel?: string;
}): React.ReactNode {
  const id = useId();
  const ref = useRef<HTMLDialogElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog || !open) return;
    const previous = document.activeElement as HTMLElement | null;
    dialog.showModal();
    cancel.current?.focus();
    return () => { dialog.close(); previous?.focus(); };
  }, [open]);
  return (
    <dialog ref={ref} aria-labelledby={`${id}-title`} aria-describedby={`${id}-description`}
      onCancel={(event) => { event.preventDefault(); if (!busy) onCancel(); }}
      className="m-auto max-h-[85dvh] w-[calc(100%-2rem)] max-w-[32rem] overflow-y-auto rounded-[var(--radius-card)] bg-surface p-6 text-ink shadow-[var(--shadow-lift)] backdrop:bg-ink/35">
      <h2 id={`${id}-title`} className="text-title">{title}</h2>
      <div id={`${id}-description`} className="mt-3 text-body text-muted">{children}</div>
      <div className="mt-6 flex flex-wrap gap-3">
        <button ref={cancel} type="button" disabled={busy} onClick={onCancel}
          className="min-h-11 rounded-full border border-rule px-5 py-2 text-body hover:border-ink disabled:cursor-not-allowed">{cancelLabel}</button>
        <Button tone={intent === "purchase" ? "primary" : "destructive"} disabled={busy} onClick={onConfirm}>{busy ? busyLabel : confirmLabel}</Button>
      </div>
    </dialog>
  );
}
