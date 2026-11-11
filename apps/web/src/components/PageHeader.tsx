export interface PageHeaderProps {
  title: string;
  lede?: string;
  actions?: React.ReactNode;
}

/**
 * Every screen opens the same way: a serif title, one sentence of
 * orientation, and the controls that belong to this screen. The screen name
 * lives in the navigation, so the header does not repeat it.
 */
export function PageHeader({ title, lede, actions }: PageHeaderProps): React.ReactNode {
  return (
    <header className="rule pb-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-[62ch]">
          <h1 className="text-title text-ink sm:text-display">{title}</h1>
          {lede === undefined ? null : <p className="mt-3 text-lede text-muted">{lede}</p>}
        </div>
        {actions === undefined ? null : <div className="flex items-center gap-3">{actions}</div>}
      </div>
    </header>
  );
}
