export interface QuoteCard {
  source: string;
  quote: string;
  detail?: string;
}

/**
 * Quotes are real outputs of this system, not testimonials. Each one names
 * where it came from.
 */
export function QuoteCards({ quotes }: { quotes: QuoteCard[] }): React.ReactNode {
  return (
    <ul className="grid gap-3 lg:grid-cols-3">
      {quotes.map((quote) => (
        <li key={quote.source} className="card flex flex-col px-5 py-4">
          <p className="field-label">{quote.source}</p>
          <p className="mt-2 flex-1 text-body text-ink">“{quote.quote}”</p>
          {quote.detail === undefined ? null : (
            <p className="hash mt-3 text-caption text-muted">{quote.detail}</p>
          )}
        </li>
      ))}
    </ul>
  );
}
