# Mnemos interaction contract

Visual context: [DESIGN.md](DESIGN.md). English interface; local time labels
use the browser locale; protocol daily caps reset at UTC midnight.

## Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
| --- | --- | --- | --- | --- |
| Form | Existing labeled native inputs + shared Button/Notice | UX-CONTRACT.md | Inline errors, preserve inputs, no native validation bubbles, disable duplicate submissions | browser exchange and vault flows |
| Select/Listbox | Native select | UX-CONTRACT.md | Platform popup geometry and keyboard behavior accepted | browser keyboard/axe |
| Date | Existing numeric expiry inputs | UX-CONTRACT.md | Duration converted to nanoseconds at submit | contract and grant tests |
| Scrollbar | `apps/web/src/app/globals.css` | UX-CONTRACT.md | Visible global theme; document scrolling; no hidden scrollbars | responsive browser tests |
| Toast | `components/Notice.tsx` | UX-CONTRACT.md | Inline status/alert, stable placement; critical evidence stays visible | axe + error workflow tests |
| CRUD | Existing Vault/Grants pages | UX-CONTRACT.md | Refetch owning dataset after changes; never erase user data to prepare demo | owner flow tests |
| Table | `components/LedgerTable.tsx` | UX-CONTRACT.md | Read-only semantic table, mobile labeled records, cursor paging | responsive tests |
| Confirmation | Native HTML dialog wrapped by `components/ConfirmDialog.tsx` | UX-CONTRACT.md | Modal focus trap, cancel initially focused, Escape and focus restoration, named consequence | exchange keyboard tests |

Local demo mutations require explicit demo enablement, testnet, loopback host,
same origin and a broker-verified session for the configured owner. Compose
binds services to loopback. The local demo is a rehearsal tool, never a public
custodial service. Owner and agent are distinct real testnet accounts on one
laptop. No mutations happen on page load. Questions and answers stay in React
memory and disappear on reload. Sample notes are labeled and encrypted before
upload; preparing them never deletes unrelated notes.

The separate Agent API offer uses real mainnet USDC under owner-signed wallet
policies. The guarded local proxy forwards only the configured owner's broker
session; API credentials and owner signing keys never enter the browser.
Purchases require an explicit 0.01 USDC confirmation. An unfunded wallet says
Funding needed and disables new purchases. Retry keeps the same ID and bound
question. Mainnet settlement and refund evidence stays separate from testnet
NEAR. No successful mainnet payment is claimed for an unfunded rehearsal.

An asynchronous action disables competing writes, announces progress, and
keeps its last error visible until the next explicit action. Upstream failures
never become a successful or verified badge. The chain is the authority for
grant state and balances. A chain receipt alone does not prove model
attestation. Revocation stops future access and cannot retract prior answers.
