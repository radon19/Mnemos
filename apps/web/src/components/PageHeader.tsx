export interface PageHeaderProps {
  title: string;
  lede?: string;
  actions?: React.ReactNode;
}

/**
 * Every screen opens the same way: a serif title, one sentence of
 * orientation, and the controls that belong to this screen. The screen name
 * is already in the navigation, so the header does not repeat it.
 */
export function PageHeader({ title, lede, actions }: PageHeaderProps): React.ReactNode {
  return (
    <header className="flex flex-wrap items-end justify-between gap-5 pb-8">
      <div className="max-w-[54ch]">
        <h1 className="text-[1.75rem] leading-tight text-ink sm:text-[2.25rem]">{title}</h1>
        {lede === undefined ? null : <p className="mt-3 text-lede text-muted">{lede}</p>}
      </div>
      {actions === undefined ? null : <div className="flex items-center gap-3">{actions}</div>}
    </header>
  );
}
