export interface EmptyStateProps {
  title: string;
  body: string;
  action?: React.ReactNode;
}

/** An empty state teaches the next action. */
export function EmptyState({ title, body, action }: EmptyStateProps): React.ReactNode {
  return (
    <div className="px-2 py-8 text-center">
      <p className="font-display text-title">{title}</p>
      <p className="mx-auto mt-2 max-w-[48ch] text-body text-muted">{body}</p>
      {action === undefined ? null : <div className="mt-5 flex justify-center">{action}</div>}
    </div>
  );
}
