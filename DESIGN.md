# Mnemos — Design Direction

## Concept: the ledger instrument

Mnemos should feel like a calm, exact instrument for chain of custody. The
interface is a ledger, not a dashboard. Evidence leads: receipt hashes,
attestation fields, prices, scopes, caps, timestamps. Decoration is subordinate
to legibility and proof.

The reference objects are a laboratory notebook, a bank ledger and a signed
receipt. Not a crypto app, not a SaaS template, not a marketing site.

## Typography

| Role | Face | Why |
| --- | --- | --- |
| Display / headings | **Newsreader** | A contemporary text serif with editorial authority. Gives headings a documentary register; distinguishes Mnemos from technical dashboards without becoming decorative. |
| UI / body | **Public Sans** | A neutral, highly legible civic sans with an unusually clear lowercase. It stays out of the way of dense tables and reads well at 13–15px. |
| Evidence / mono | **IBM Plex Mono** | Hashes, account IDs, prices and timestamps need unambiguous glyphs and tabular numerals. Plex Mono's slightly humanist forms keep it from feeling like a terminal costume. |

All three are self-hosted through `next/font/google` (downloaded at build time,
served from the app origin). Headings use Newsreader at optical sizes; body uses
Public Sans; all numeric data uses IBM Plex Mono with `font-variant-numeric:
tabular-nums`. No Inter, Roboto, Arial, system defaults, Poppins or Space Grotesk.

## Colour

OKLCH tokens, neutral-dominant. One restrained accent is reserved for the
verified state; one for destructive actions. Colour never carries meaning alone:
every status also has a word and a shape.

### Light

```
--paper       oklch(0.975 0.004 240)   archival white, faintly cool
--surface     oklch(0.945 0.006 240)   recessed rows
--ink         oklch(0.22 0.012 250)    primary text
--muted       oklch(0.50 0.014 250)    secondary text (5.58:1 on paper)
--rule        oklch(0.86 0.008 245)    hairline rules
--verified    oklch(0.43 0.095 160)   verified ink
--verified-bg oklch(0.94 0.025 160)   verified tint
--destructive oklch(0.48 0.145 30)    destructive ink
--destructive-bg oklch(0.95 0.03 30)  destructive tint
```

### Dark

```
--paper       oklch(0.16 0.008 250)
--surface     oklch(0.205 0.010 250)
--ink         oklch(0.93 0.006 240)
--muted       oklch(0.70 0.012 245)
--rule        oklch(0.30 0.010 245)
--verified    oklch(0.80 0.105 160)
--verified-bg oklch(0.24 0.035 160)
--destructive oklch(0.74 0.130 30)
--destructive-bg oklch(0.26 0.045 30)
```

Both themes are designed separately, not inverted. The dark theme is a dim
reading surface, not neon on black. Body text and interactive labels meet WCAG
AA (4.5:1) against their surfaces; large headings meet 3:1. Focus is a 2px ink
outline with a 2px offset, visible in both themes.

The paper is a cool archival white rather than a warm cream. A cream page
background is the default "tasteful" surface and reads as decoration; a faintly
cool white reads as a document, which is what this interface is. The warmth
that remains lives in the type, not in the background.

## Layout

- A fixed left rail (208px) holds the wordmark, the ledger navigation and the
  owner identity. Content occupies a 12-column grid with a 1180px maximum.
- **Table-first.** Activity, grants, earnings history and vault items are tables
  or definition lists with hairline rules. No card grids, no three-column feature
  rows, no centered hero over a gradient.
- Deliberate asymmetry: forms use a narrow label column (4 cols) against a wide
  field column (8 cols). Detail views put a large hash in a wide right column.
- Whitespace is generous but not empty: section spacing 48–72px, row padding
  12–16px.
- On mobile the rail becomes a top bar with a disclosure menu; tables become
  definition lists with labels above values. No horizontal scrolling for primary
  content; hashes wrap.

## Components

- **Status mark:** a 7px square (filled for verified/served, hollow for pending,
  crossed for revoked/refused) plus a word in mono. Never colour alone.
- **Hash:** mono, middle-truncated with `…`, a copy control, and a title with the
  full value. Hashes are content, not fine print.
- **Ledger table:** header in small caps mono; rows separated by 1px rules; no
  zebra striping; hover undims a row's actions.
- **Screen opening:** a serif title and one sentence of orientation. The screen
  name is already in the navigation, so it is not repeated above the title.
- **Grant form:** inline, labelled, with live computed price in NEAR and a plain
  explanation of what each limit does. Revoke is a separate, deliberate action
  with a typed confirmation.
- **Empty state:** one sentence explaining what to do next, plus the action.
- **Evidence block:** definition list of attestation fields, chat id, model,
  signing address, verification result, timestamps, explorer link.

## Motion

Motion only communicates state change: a receipt row arriving (120ms fade and
4px rise), a grant being revoked (160ms strike-through and status swap), a copy
confirmation (100ms). No parallax, no ambient animation, no page-load choreography.
`prefers-reduced-motion: reduce` removes transforms and reduces durations to 0ms.

## Copy

Specific, plain, declarative. No exclamation marks, no emojis, no lorem ipsum.
Errors state what happened, why, and what to do next. Empty states teach the next
action. Security claims are precise about what is and is not guaranteed.

## Banned

Purple-to-blue gradients, glassmorphism, glowing borders, neon on dark, emoji or
sparkle icons, identical rounded cards with soft shadows, icon-in-circle feature
tiles, fake testimonials or logos, stock illustrations, gratuitous blur, default
Tailwind palette, centered marketing hero.

## Accessibility and responsiveness

Semantic landmarks (`header`, `nav`, `main`, `section` with accessible names),
visible focus, full keyboard operation, labelled controls, `aria-live="polite"`
for the activity stream, colour-independent status, 4.5:1 text contrast. Verified
at 390, 768 and 1440 widths and wider. Tap targets at least 44px on mobile.
