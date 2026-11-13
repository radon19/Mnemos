# Mnemos interaction contract

Visual context: [DESIGN.md](DESIGN.md). English interface; local time labels
use the browser locale; protocol daily caps reset at UTC midnight.

| Capability | Canonical owner | Allowed behavior | Verification |
| --- | --- | --- | --- |
| Form | Existing labeled native inputs + shared Button/Notice | Inline errors, preserve inputs, no native validation bubbles, disable duplicate submissions | browser exchange and vault flows |
| Select/Listbox | Native select | Platform popup geometry and keyboard behavior accepted | browser keyboard/axe |
| Date | Existing numeric expiry inputs | Duration converted to nanoseconds at submit | contract and grant tests |
| Scrollbar | `apps/web/src/app/globals.css` | Visible global theme; document scrolling; no hidden scrollbars | responsive browser tests |
| Toast | `components/Notice.tsx` | Inline status/alert, stable placement; critical evidence stays visible | axe + error workflow tests |
| CRUD | Existing Vault/Grants pages | Refetch owning dataset after changes; never erase user data to prepare demo | owner flow tests |
| Table | `components/LedgerTable.tsx` | Read-only semantic table, mobile labeled records, cursor paging | responsive tests |
| Confirmation | Native HTML dialog wrapped by `components/ConfirmDialog.tsx` | Modal focus trap, cancel initially focused, Escape and focus restoration, named consequence | exchange keyboard tests |

Local demo mutations require explicit demo enablement, testnet, loopback host,
same origin and a broker-verified session for the configured owner. Compose
binds services to loopback. The local demo is a rehearsal tool, never a public
custodial service. Owner and agent are distinct real testnet accounts on one
laptop. No mutations happen on page load. Questions and answers stay in React
memory and disappear on reload. Sample notes are labeled and encrypted before
upload; preparing them never deletes unrelated notes.

An asynchronous action disables competing writes, announces progress, and
keeps its last error visible until the next explicit action. Upstream failures
never become a successful or verified badge. The chain is the authority for
grant state and balances. A chain receipt alone does not prove model
attestation. Revocation stops future access and cannot retract prior answers.
