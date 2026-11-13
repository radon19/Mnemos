# Mnemos — Design Direction

> This direction replaces the first one (a left rail of hairline rules over
> archival paper). It was rewritten after the owner asked for a redesign based
> on a marketing reference they supplied: a light page lit from behind, one
> vivid accent, a floating navigation bar, a headline built around a real
> number, and a row of figure cards. The product truth did not change: the
> evidence is still the content, and every figure on the page is read from the
> chain when the page loads.

## Concept: a lit ledger

The page is a sheet of paper on a lit desk. The light comes from behind the
sheet — a violet ambient glow bleeding in from the edges — and the interface
sits on top of it as white cards with soft, layered shadows. Evidence is
printed on those cards: receipt hashes, attestation fields, prices, scopes,
timestamps. Nothing floats without a reason.

The reference offered a big number and a row of country cards. Mnemos uses the
same move with the same discipline: the headline number is the owner's real
earnings, and the cards are the system's real figures.

## Typography

| Role | Face | Why |
| --- | --- | --- |
| Display / headings | **Bricolage Grotesque** | A variable grotesque with a slightly off-axis character. It gives a headline presence without the flatness of a geometric sans, and it holds its own next to a mono. |
| UI / body | **Instrument Sans** | A neutral, highly legible sans with clear lowercase shapes. It stays quiet in dense tables and reads well at 13–15px. |
| Evidence / mono | **IBM Plex Mono** | Hashes, account ids, prices and timestamps need unambiguous glyphs and tabular numerals. |

All three are self-hosted through `next/font/google`. Amounts and counts use
IBM Plex Mono with `font-variant-numeric: tabular-nums`. No Inter, Roboto,
Arial, system defaults, Poppins or Space Grotesk.

The scale is deliberately small: the display size is reserved for the landing
headline and the screen titles step down to 1.75rem, because the app screens
are dense and the type has to stay out of the way of the data.

## Colour

OKLCH tokens. The canvas is a near-white with a faint violet cast, the
surfaces are pure white, and one accent carries the brand. Status colour is
never the only signal: every status also has a word and a mark.

### Light

```
--canvas     oklch(0.985 0.004 285)   near-white, faintly violet
--surface   oklch(1 0 0)              cards
--sunken     oklch(0.968 0.006 285)   recessed fields
--ink        oklch(0.19 0.02 285)      primary text
--muted      oklch(0.52 0.022 285)    secondary text
--rule       oklch(0.91 0.008 285)    hairlines
--accent     oklch(0.55 0.24 292)     brand accent, the headline figure
--accent-ink oklch(0.46 0.22 292)    accent text on a light tint
--accent-soft oklch(0.955 0.028 292) accent tint
--verified   oklch(0.52 0.14 158)    verified state
--destructive oklch(0.54 0.19 25)     destructive state
```

### Dark

```
--canvas     oklch(0.145 0.016 285)
--surface   oklch(0.195 0.02 285)
--sunken     oklch(0.225 0.022 285)
--ink        oklch(0.96 0.006 285)
--muted      oklch(0.72 0.024 285)
--rule       oklch(0.29 0.022 285)
--accent     oklch(0.74 0.185 292)
--verified   oklch(0.82 0.15 158)
--destructive oklch(0.72 0.16 25)
```

Both themes are designed separately. The dark theme is a dim reading surface,
not neon on black. Body text meets WCAG AA (4.5:1) against its surface, large
headings meet 3:1, and focus is a 2px accent outline with a 3px offset.

The violet ambient light is a fixed layer behind the page: three radial
gradients bleeding in from the top corners and the bottom centre, at 30–38%
alpha. It is decoration with a job — it makes a white page feel lit rather
than blank — and it never carries meaning.

## Layout

- A floating navigation bar sits at the top of the viewport: a white pill with
  a hairline border and a soft shadow, holding the wordmark, the section links
  and one dark pill for the primary action. It is sticky.
- Below 1024px the bar collapses: the section links move into a disclosure
  panel under the bar, and the owner block moves with them.
- The landing page centres its hero, then opens into wide grids: four figure
  cards, three promise cards, five step cards, three limit cards and one
  receipt block. It says what the project does in two sentences before it
  shows a figure, and the closing call to action links to `/docs`.
- The documentation page is held to the same standard as the app: a left
  contents rail, measured prose, definition lists for the contract calls and
  the endpoints, and the same honest limits section. It is reachable from the
  navigation bar on every screen.
- The app screens are left aligned and dense. A screen title at 1.75rem, one
  sentence of orientation, then cards that hold forms, tables and evidence.
- Prose is measured: 54–76 characters per line, never the full width.
- Tables sit inside cards with hairline rows. No zebra striping.
- On mobile the grids collapse to one column and the ledger tables become a
  stack of records: one card per read, each field labelled the way a receipt
  is labelled. Nothing scrolls sideways at any width, and no text is cut off.
- The layouts are checked at 320, 360, 390, 414, 480, 540, 640, 768, 834, 1024,
  1280, 1440 and 1920 pixels. Every interactive control is at least 44 pixels
  tall on a phone.

## Components

- **Wordmark:** a rounded ink square with a lighter band at the top — a ledger
  sheet seen from above.
- **Figure card:** a label, a large tabular number, and a note that says where
  the number came from. A figure that cannot be read says so instead of
  showing an example.
- **Quote card:** a real output of the system with its source named. There are
  no testimonials in this product.
- **Status mark:** a 7px square (filled for served, hollow for pending,
  outlined for refused) plus a word in mono. Never colour alone.
- **Hash:** mono, middle-truncated with `…`, the full value on hover and in
  the accessible name. Hashes are content, not fine print.
- **Pill button:** rounded, 40px tall, ink fill for primary, hairline for
  quiet, destructive ink for revoke. A disabled button keeps its label legible.
- **Empty state:** one sentence explaining what to do next, centred in its
  card.
- **Evidence block:** a definition list of attestation fields, chat id, signing
  address, TCB status and the explorer link.

## Motion

One authored moment: a receipt arriving in the activity ledger, 140ms, a 6px
rise with an exponential ease-out. Rows that were already known stay still.
`prefers-reduced-motion` reduces every duration to nothing. There is no
page-load choreography and no ambient animation.

## Copy

Specific, plain, declarative. No exclamation marks, no emojis, no lorem ipsum.
Errors state what happened, why, and what to do next. Empty states teach the
next action. Security claims are precise about what is and is not guaranteed.

The landing page never shows an invented figure. Every number is read from
`mnemos-contract-76badc8e.testnet` when the page loads, and the page says so.

## Banned

Neon on dark, glassmorphism as decoration, emoji or sparkle icons, identical
rounded cards standing in for content, icon-in-circle feature tiles, fake
testimonials, fake figures, stock illustrations, gradient text, hard offset
shadows, sparkle icons, centred marketing copy without a real number.

## Accessibility and responsiveness

Semantic landmarks, visible focus, full keyboard operation, labelled
controls, `aria-live` for the activity stream, colour-independent status, 4.5:1
text contrast. Verified at 390, 768 and 1440 pixels with axe-core and
Playwright: 36 tests, no violations. A separate responsive suite walks every
screen at thirteen widths from 320 to 1920 pixels and fails on sideways
scrolling, clipped text or a touch target under 30 pixels.
