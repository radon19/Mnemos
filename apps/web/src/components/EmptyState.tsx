export interface EmptyStateProps {
  title: string;
  body: string;
  action?: React.ReactNode;
}

/** An empty state teaches the next action. */
export function EmptyState({ title, body, action }: EmptyStateProps): React.ReactNode {
  return (
    <div className="border-t border-rule py-12">
      <p className="font-display text-title">{title}</p>
      <p className="mt-2 max-w-[54ch] text-body text-muted">{body}</p>
      {action === undefined ? null : <div className="mt-5">{action}</div>}
    </div>
  );
}
