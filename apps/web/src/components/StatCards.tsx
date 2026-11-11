export interface StatCard {
  label: string;
  value: string;
  unit?: string;
  note?: string;
  accent?: boolean;
}

/**
 * The figures row. Each card carries a label, a value and, where it matters,
 * the note that says where the number came from. A card without a value says
 * so instead of inventing one.
 */
export function StatCards({ cards }: { cards: StatCard[] }): React.ReactNode {
  return (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <li key={card.label} className="card px-5 py-4">
          <div className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className={`inline-block h-2 w-2 rounded-full ${
                card.accent === true ? "bg-accent" : "bg-rule"
              }`}
            />
            <span className="field-label">{card.label}</span>
          </div>
          <p className="numeric mt-2 text-[1.75rem] leading-none font-semibold">
            <span className={card.accent === true ? "text-accent" : "text-ink"}>
              {card.value}
            </span>
            {card.unit === undefined ? null : (
              <span className="ml-1.5 text-caption text-muted">{card.unit}</span>
            )}
          </p>
          {card.note === undefined ? null : (
            <p className="mt-1.5 text-caption text-muted">{card.note}</p>
          )}
        </li>
      ))}
    </ul>
  );
}
