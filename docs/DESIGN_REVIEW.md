# Design review

The web app was built from `PRODUCT.md` and `DESIGN.md`, then put through the
Impeccable passes the brief requires: shape, craft, audit, critique, harden,
polish, and the anti-pattern detector. This file records what the detector
found, what was changed, and the one finding that was kept on purpose.

## How it was checked

```text
$ cd apps/web && pnpm exec playwright test e2e/accessibility.spec.ts
  27 passed (19.2s)
```

Each of the seven screens is checked with axe-core at 1440, 768 and 390
pixels. The suite also asserts that no screen scrolls sideways and that the
navigation reaches every screen.

```text
$ impeccable detect http://127.0.0.1:3000/
$ impeccable detect http://127.0.0.1:3000/setup
$ impeccable detect http://127.0.0.1:3000/vault
$ impeccable detect http://127.0.0.1:3000/grants
$ impeccable detect http://127.0.0.1:3000/activity
$ impeccable detect http://127.0.0.1:3000/earnings
$ impeccable detect http://127.0.0.1:3000/redteam
```

Screenshots were captured at 1440 and 390 in both themes and reviewed.

## Findings and fixes

| Finding | Where | Fix |
| --- | --- | --- |
| `kicker-above-heading` | every screen | The mono eyebrow above each title was a generated kicker that repeated the navigation. Removed from `PageHeader` and from the landing page; `DESIGN.md` was updated to match. |
| `cream-palette` | every screen | The warm paper background was the default "tasteful" surface. The palette moved to a cool archival white (`oklch(0.975 0.004 240)`), which reads as a document. `DESIGN.md` records the change and the reason. |
| `cramped-padding` | landing, setup | The rule above the example receipt had its rows flush against it. The border moved onto the definition list, which now carries its own inset. Buttons gained vertical padding so 15px text is never flush with their edge. |
| `low-contrast` | setup, vault, grants, red-team | Disabled buttons were drawn at 40% opacity, which put their labels at 1.2:1. A disabled button now uses the muted ink and the rule colour: still visibly disabled, still readable. |
| `script-error` (React #418) | setup | The theme script mutated `<html>` before hydration. The root element now carries `suppressHydrationWarning`, which is the intended use for a pre-paint theme class. |
| horizontal overflow at 768 | setup | The three-column step layout did not fit beside the rail. The layout now only becomes three columns at 1024px, and every grid track uses `minmax(0, 1fr)` so long hashes cannot widen their column. |

The craft floor was also checked by hand: contrast is at least 4.5:1 for body
text in both themes, the body measure stays inside 54–68 characters, the
display size is 2.25rem, focus is a 2px ink outline with a 2px offset, and
there are no cards, gradients, glass, hard shadows, sparklines or emoji.

## Deliberate choices

**One authored moment.** The only animation is a receipt arriving in the
activity ledger: 120ms, 4px rise, exponential ease-out. It runs on newly
arrived rows only, and `prefers-reduced-motion` reduces it to nothing. There
is no page-load choreography and no ambient animation.

**The revoke confirmation is a dialog.** It asks for a typed word, so it needs
protected focus and an explicit dismissal. A task without either would be a
dialog too often; this one has both.

**A 1px left rule on notices.** The craft floor bans a coloured border above
1px on callouts. The notice keeps a one-pixel rule in the tone colour and
carries the message in the surface tint.

## Reasoned exception

**`numbered-section-labels` (advisory) on the setup screen.** The detector
flags the small `01`–`04` numbers beside the four setup steps. The craft floor
allows section numbers "unless the sequence itself carries information the
reader needs", and here the sequence is the point: the brief asks for a setup
screen where each step shows its own success or failure state, and the numbers
make the order explicit. They are the only numbers of their kind in the app.
The finding is advisory, it never blocks, and the steps would be less clear
without them.
