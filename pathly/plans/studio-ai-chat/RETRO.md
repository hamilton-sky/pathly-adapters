# Studio AI Chat — Retrospective

**Feature:** studio-ai-chat
**Date:** 2026-05-27
**Conversations:** 0–9 (10 total) | **Stories delivered:** S0.1–S9.4 (38 stories)

---

## What went well?

**Strong incremental pipeline discipline.** The project followed a clear conversation-by-conversation sequence with tight scope gates. Each conversation delivered a cohesive set of stories (0–9) that built on the previous layer without backtracking. The phased approach — core chat infrastructure first (Conv 0–5), then Track A automation (Conv 6–8), then Track B local models (Conv 9) — meant dependencies were resolved in the right order and reviewers had clear acceptance criteria to verify.

**Efficient problem-solving under constraint.** Multiple friction points (Windows PTY escaping, embedding model latency, scope violations on Conv 2/5/6/7/8) were caught early and resolved without derailing the pipeline. Post-implementation hotfixes (terminal `\n` → `\r`, `/pathly` prefix removal, SkillsPanel overflow) kept the product functional while maintaining code quality.

**Embedding-first matching strategy paid off.** Using MiniLM (transformers.js) for instant skill matching gave the Conductor a responsive, low-latency foundation. The fallback to Playwright + semantic resolution for UI automation (Conv 7) extended that capability without runtime DOM scanning or brittle selectors.

**User stories with acceptance criteria are load-bearing.** Explicit AC for each story made review gate decisions fast and unambiguous. Reviewers caught scope violations 6 times but the AC format let builders re-scope quickly instead of guessing.

---

## What was harder than expected?

**Scope gate brittleness cost time across 5 conversations.** Conv 2, 5, 6, 7, and 8 each failed the scope gate despite being in scope — the gate flagged `tsconfig.tsbuildinfo` and type-generation files as violations. This forced manual feedback resolution cycles. The gate needed exemption rules for build artifacts.

**WebLLM pivot added dependency complexity.** The initial design called for a Python-side chat agent (Conv 1 phases 2–3 removed), but shifting to WebLLM mid-project required embedding router plumbing, model download infrastructure, and careful coordination between local cache and CDN fallback. This added ~30% to Conv 9's scope and made testing harder (browser-native, not server-testable).

**Playwright executor reliability hinged on element label stability.** Conv 7's 3-tier cascade (Playwright selector → semantic label match → LLM embedding fallback) was necessary because Studio's UI uses React synthetic events and dynamic label generation. Testing across mock and live Studio windows required careful IPC plumbing.

**Context inflation across the pipeline.** Each conversation added new context fields (FSM state, skills list, studioSchema). By Conv 6 the context request size was nearing LLM token budgets. Keeping the system prompt lean became a real constraint.

---

## What would we do differently next time?

**Partition scope gates by file category earlier.** Build artifacts, lock files, and generated types should not trigger scope gates — only source code should. Establish exemption rules before the first review cycle.

**Test WebLLM integration in a parallel track to unblock Conv 8.** A dedicated pre-spike conversation could have validated the WebLLM architecture, download pipeline, and streaming contract, letting Conv 8–9 run in parallel.

**Establish a single `buildPathlyContext()` contract in Conv 0.** By Conv 4 we had inconsistency in how context was built (sometimes renderer, sometimes Python). Agreeing on a canonical context builder upfront reduces back-and-forth.

**Create mock/stub UI for automation testing in Conv 6, not Conv 7.** Conv 7's Playwright executor needed mocked Studio controls. Creating stubs earlier would have let Conv 7 focus purely on IPC and executor reliability.

**Version the `studioSchema` with explicit update ceremonies.** The static schema in `lib/studioSchema.ts` lacks versioning. Add `SCHEMA_VERSION` and a Conv-X update log so future refinements are traceable.

---

## Lessons Extracted

- **Acceptance criteria enforce discipline.** Explicit AC for each story made scope violations obvious and gave reviewers a clear gate signal.
- **Static schema over runtime scanning.** `studioSchema.ts` as a typed constant eliminated a class of flaky automation bugs and made element mapping testable.
- **Embedding models buy responsiveness for free.** MiniLM (transformers.js) gave sub-50ms latency for skill matching — and doubled as the automation label-matcher in Conv 7.
- **Scope gates need exemption rules for build artifacts.** `tsconfig.tsbuildinfo` and generated files should not trigger violations; a category filter would recover hours.
- **Context inflation is real — budget tokens early.** Every added context field (FSM state, skills, schema) costs tokens. A context budget agreed in Conv 0 prevents bloat by Conv 6.
