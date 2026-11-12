# Design review

Two rounds. The first built the interface from the original design direction.
The second was a redesign at the owner's request, using a marketing reference
they supplied: a light page lit from behind, one vivid accent, a floating
navigation bar, a headline built around a real number, and a row of figure
cards.

Every screen was checked with the Impeccable detector and with axe-core
through Playwright at 1440, 768 and 390 pixels, and reviewed as screenshots
in both themes.

## How it was checked

```text
$ cd apps/web && pnpm exec playwright test
  36 passed (3.3m)
```

Each of the seven screens is checked with axe-core at 1440, 768 and 390
pixels. The suite also asserts that no screen scrolls sideways, that the
navigation reaches every screen, and that the owner can sign in, store an
encrypted note and run the red-team set against a live broker.

```text
$ impeccable detect http://127.0.0.1:3000/          # and the other six screens
```

## The redesign

The reference supplied the direction; the product supplied the content. The
landing page now opens with the owner's real earnings and the real number of
served reads, both read from the contract when the page loads, and the figure
cards below it carry the real price per read, the real number of requests
created and the real broker fingerprint. The quote cards hold real outputs:
the latest receipt on chain, the contract's own panic text after a revoke, and
the broker's published key. There is not one invented figure on the page, and
the copy says where each number comes from.

The app screens moved from a left rail to a floating navigation bar, from
hairline rules to white cards with soft layered shadows, and from square
buttons to pills. The information architecture did not change: the same seven
screens, the same tables, the same evidence.

## Findings and fixes in the redesign round

| Finding | Where | Fix |
| --- | --- | --- |
| `cramped-padding` | setup, vault, grants | Pill buttons had no vertical padding of their own, so the label sat 0px from the edge of the control. They now carry `py-2`, and the nav links `py-1.5`. |
| `line-length` | landing, setup, vault, earnings | Prose blocks ran the full width of the page. Every prose block is now measured between 54 and 76 characters. |
| `label-content-name-mismatch` (axe) | theme toggle | The visible label did not match the accessible name. The name now contains the visible word. |
| horizontal overflow at 768 | every screen | The navigation bar was too wide beside the content at tablet width. The owner block and the primary action moved to the large breakpoint, and the menu links wrap. |
| a link that did not navigate | mobile | The disclosure panel was unmounted on click, which removed the link from the document mid-click and cancelled the navigation. The panel now stays mounted and is hidden with `hidden`. |
| the mobile menu ran off the screen | mobile | The six section links were one row. They wrap. |
| a token rename left dead classes | grants | The redesign renamed the paper token, and `text-paper` silently became no class, so an active scope chip rendered as ink-on-ink. A script now compares every colour utility used in the app against the theme and fails on an unknown one. |

## Responsive work

The ledger tables were the one thing the redesign broke on a phone: six
columns at 390 pixels is 411 pixels of table, and the card clipped the rest, so
the receipt hash and the delete control were simply unreachable. The tables are
now one component: a real table from `md` up, and below that a stack of
records, one per read, each field labelled the way a receipt is labelled.
Nothing scrolls sideways and nothing is cut off.

Also fixed while making it work on a phone:

- The navigation bar overflowed at 768 pixels, because the owner block and the
  primary action were still in the bar at that width. Both moved to the large
  breakpoint, and the menu links wrap.
- The grant form squeezed four fields into two columns; it is one column below
  `sm`.
- The revoke dialog could run past the bottom of a short screen; it scrolls.
- The touch targets: buttons, nav links, the theme toggle, the menu button and
  the evidence link are all at least 44 pixels tall on a phone.
- The owner account in the bar was truncated with `text-overflow`, so a screen
  reader read the truncated string. The full account id is now announced and
  the short one is marked decorative.

A responsive suite now walks every screen at thirteen widths from 320 to 1920
pixels, signs in so the screens carry their real content, and fails on
sideways scrolling, clipped text or a touch target under 30 pixels.

```text
$ cd apps/web && pnpm exec playwright test
  81 passed (8.0m)
```

## Deliberate choices

**The violet ambient light.** The detector calls a purple gradient background
an AI default and a radial spotlight glow decoration. Both are true in
general, and both are the point of the reference the owner chose. The light is
a fixed layer behind the page at 30–38% alpha; it carries no meaning, it
makes a white page read as lit, and the accent colour is the only place the
same hue appears. This is a user-directed decision, recorded here rather than
silently applied.

**One accent, one status colour.** Violet is the brand. Green is reserved for
the verified state, because "verified" is a claim about a signature and a TEE
attestation, not a decoration. Red is destructive. Nothing else is coloured.

**The body face dominates the app screens.** The detector notes that the
interface sans carries 45–70% of the text. In the app screens that is
correct: the display face carries every heading and every headline figure,
the mono carries every hash, account id, amount and timestamp, and what is
left is body copy and small data labels, where a geometric display face would
be wrong.

**The numbered setup steps.** The detector flags the small `01`–`04` labels
beside the four setup steps as an advisory. The steps are an ordered procedure
and the numbers carry the order, which is the information the reader needs.

**One authored moment.** The only animation is a receipt arriving in the
activity ledger. The reference's floating cards and drifting glow are static
here: motion would fight the ledger, which is a record of what happened.

## Reasoned exceptions

| Finding | Why it stays |
| --- | --- |
| `ai-color-palette` | The owner asked for this reference. The violet is deliberate, not a default. |
| `radial-spotlight-glow` | Same. The ambient layer is fixed, low alpha, and carries no meaning. |
| `overused-font` | A data interface is mostly text; the display face is used where type has to carry weight. |
| `numbered-section-labels` (advisory) | The setup steps are a sequence and the numbers are the order. |
