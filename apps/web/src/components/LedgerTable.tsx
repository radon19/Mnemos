import type { ReactNode } from "react";

export interface LedgerColumn<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  /** The value that leads the stacked layout on a narrow screen. */
  primary?: boolean;
  /** Dropped entirely from the stacked layout when the screen is tight. */
  secondary?: boolean;
}

export interface LedgerTableProps<T> {
  caption: string;
  columns: LedgerColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  actions?: { header: string; render: (row: T) => ReactNode };
  /** Applied to a row, for example when a receipt has just arrived. */
  rowClassName?: (row: T) => string | undefined;
  empty?: ReactNode;
}

/**
 * A ledger table that works on a phone.
 *
 * From `md` up it is a real table: a header row, hairline rules, aligned
 * columns. Below that it becomes a stack of records, one per read, each
 * labelled the way a receipt is labelled. Nothing is scrolled sideways and
 * nothing is cut off.
 */
export function LedgerTable<T>({
  caption,
  columns,
  rows,
  rowKey,
  onRowClick,
  actions,
  rowClassName,
  empty,
}: LedgerTableProps<T>): ReactNode {
  if (rows.length === 0) {
    return empty ?? null;
  }

  const primary = columns.find((column) => column.primary === true) ?? columns[0];
  const secondary = columns.filter(
    (column) => column !== primary && column.secondary !== true,
  );

  return (
    <>
      <div className="hidden md:block">
        <table className="w-full text-left">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  className="field-label border-b border-rule py-3 pr-4 last:pr-0"
                >
                  {column.header}
                </th>
              ))}
              {actions === undefined ? null : (
                <th scope="col" className="field-label border-b border-rule py-3 text-right">
                  <span className="sr-only">{actions.header}</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={rowKey(row)}
                onClick={
                  onRowClick === undefined
                    ? undefined
                    : () => {
                        onRowClick(row);
                      }
                }
                className={`${onRowClick === undefined ? "" : "cursor-pointer hover:bg-sunken"} ${
                  rowClassName === undefined ? "" : (rowClassName(row) ?? "")
                }`}
              >
                {columns.map((column) => (
                  <td key={column.key} className="border-b border-rule py-3 pr-4 align-top last:pr-0">
                    {column.render(row)}
                  </td>
                ))}
                {actions === undefined ? null : (
                  <td className="border-b border-rule py-3 text-right align-top">
                    {actions.render(row)}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="space-y-3 md:hidden">
        {rows.map((row) => (
          <li key={rowKey(row)} className="rounded-2xl bg-sunken px-4 py-3">
            <div className="flex items-baseline justify-between gap-3">
              <span className="min-w-0 text-body text-ink">{primary?.render(row)}</span>
            </div>
            <dl className="mt-2 space-y-1.5">
              {secondary.map((column) => (
                <div key={column.key} className="flex items-baseline justify-between gap-3">
                  <dt className="field-label">{column.header}</dt>
                  <dd className="min-w-0 text-right text-caption text-ink">
                    {column.render(row)}
                  </dd>
                </div>
              ))}
            </dl>
            {onRowClick === undefined ? null : (
              <button
                type="button"
                className="field-label mt-3 inline-flex min-h-11 items-center rounded-full border border-rule px-4 text-accent-ink transition-colors hover:border-accent"
                onClick={() => {
                  onRowClick(row);
                }}
              >
                Open the evidence
              </button>
            )}
            {actions === undefined ? null : (
              <div className="mt-3 border-t border-rule pt-3">{actions.render(row)}</div>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}
