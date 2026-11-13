# Demo Ready Knowledge Exchange Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a laptop demo of paid access to private expertise, with real answers, receipts and revocation.

**Architecture:** Extend the existing Next.js app with guarded local demo routes that reuse the MCP tools for reads and near-api-js for a fixed set of owner actions. Keep encryption in the browser and all authorization, inference and settlement in the existing pipeline.

**Tech Stack:** Existing Next.js 16, TypeScript, near-api-js 7.4.0, FastAPI, Postgres, Rust near-sdk, Playwright, Vitest.

**Spec:** `docs/superpowers/specs/2026-11-13-demo-ready-design.md`

## Global Constraints

- Testnet only; use configured credentials without exposing them.
- Laptop only; mutations require loopback, same-origin, explicit demo mode and the owner session.
- No mock inference or receipts in the live product; preserve existing visual tokens and shared components.
- No public hosting, posting, submission, mainnet spending or protocol redesign.
- Keep source files about 400 lines or less.

## Review Focus

- Remote requests, forwarded hosts, disabled demo mode and wrong owner must not sign transactions.
- A stale/revoked grant or ungranted scope must not return an answer or charge a successful read.
- A failed dependency must produce a recoverable error and never a verified success badge.
- Repeated clicks must not create duplicate writes; answer/question text must not persist in browser storage.
- Demo preparation must not delete or overwrite existing owner notes or hide incompatible encryption keys.

### Task 1: Audit baseline and lock the local signing boundary

**Files:** `apps/web/src/lib/server/demo-guard.ts`, `apps/web/src/app/api/auth/demo/route.ts`, `apps/web/test/demo-guard.test.ts`, `UX-CONTRACT.md`.

**Interfaces:** `requireLocalDemo(request: Request, env): void`; async owner validation against the broker session; canonical `DemoError` envelope.

- [ ] Run `make check`; record current baseline and dependency health.
- [ ] Write guard tests for loopback/origin, disabled demo, mainnet, forwarded requests, invalid owner and body limits; observe failure with `pnpm --filter @mnemos/web test`.
- [ ] Implement fail-closed guard, apply it to the existing demo login route, add shared UX ownership contract.
- [ ] Run web tests/typecheck/lint. Expected: pass. Commit the independently verified boundary.

### Task 2: Real demo agent and owner operations

**Files:** `apps/web/src/lib/server/exchange.ts`, `apps/web/src/app/api/demo/exchange/route.ts`, `apps/web/package.json`, `apps/web/Dockerfile`, `docker-compose.yml`, `apps/web/test/exchange.test.ts`.

**Interfaces:** GET returns configured owner, agent, grant, credit, broker-key binding; POST accepts only `grant`, `ask` or `revoke`; asks use `askMemory(createDeps(...), { owner, scope, question })` from `@mnemos/mcp`.

- [ ] Write failing tests proving action validation, fixed owner/agent binding, session enforcement, credit bounds, scoped asks, contract failures and no false verification.
- [ ] Implement fixed-action service and route with serialized writes, bounded request parsing and safe error responses; add workspace MCP dependency and build it before web.
- [ ] Pass agent credentials server-side through Compose only; enforce testnet and loopback bindings for all services.
- [ ] Run web/MCP tests, typecheck, lint and production build. Expected: pass. Commit.

### Task 3: Guided knowledge exchange and truthful product copy

**Files:** `apps/web/src/app/exchange/page.tsx`, `apps/web/src/components/exchange/*`, `apps/web/src/lib/exchange.ts`, landing/nav/docs copy, `PRODUCT.md`, `DESIGN.md`, `apps/web/e2e/exchange.spec.ts`.

**Interfaces:** browser encrypts labeled sample notes using existing broker-key validation and vault APIs; action route returns real tool results and transaction hashes.

- [ ] Write browser acceptance tests for initial state, preparation, grant, answer receipt, scope denial, confirm revoke, denied repeat, recoverable failure and keyboard use.
- [ ] Build one clear owner/agent workspace with terms, progress, live evidence, explicit network label, sample-content disclosure and no persistent plaintext.
- [ ] Fix unsupported privacy claims, receipt/attestation labels and landing dependency errors; preserve existing styles and links.
- [ ] Run web tests/lint/typecheck/build and mocked browser workflow tests. Expected: pass. Commit.

### Task 4: Reproducible laptop operation, live rehearsal and evidence

**Files:** `scripts/demo-ready.*`, `scripts/record-demo.*`, `Makefile`, `.env.example`, `README.md`, `docs/DEMO.md`, `docs/SUBMISSION.md`, `docs/VERIFICATION.md`, `docs/PROGRESS.md`.

- [ ] Add doctor/start commands that validate configuration without printing secrets and prepare the existing accounts for the laptop demo without overwriting data.
- [ ] Rebuild/start Docker services and run the complete real browser flow against testnet and NEAR AI; capture screenshots and a local video.
- [ ] Run `make check`, contract sandbox and broker integration tests, browser/accessibility/responsive suites, production build and design detectors. Expected: pass, skips reported honestly.
- [ ] Document exact evidence, trust limits, recovery steps, demo narration, submission text and remaining manual submission actions.
- [ ] Obtain one fresh final review per executing-plans, fix material findings, verify affected suites, commit and leave the laptop services ready.
