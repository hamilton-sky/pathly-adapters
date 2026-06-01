---
name: Feature Index
---
# HQ Panel — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## What this feature does

Renames the Studio `ChatPanel` to **HQ** and upgrades it into a pipeline command center. HQ gives the user full flow control (Start, Pause, Resume, Advance, Reroute, Retry, Abort) via buttons wired to `/runner/*` REST endpoints, a live `StageStatusStrip` (stage, adapter chip, cost, session), and a streaming decision menu driven by SSE from `/events/runner`. When the runner emits a `DECISION_MENU` event the existing `PathlyMenuCard` switches into decision mode and item clicks POST to `/runner/decision` instead of writing to a terminal.

**This is the Studio half** of a two-part effort. The backend half — `/runner/*` endpoints, `/events/runner` SSE stream, and the generated `adapters.gen.ts` file — is delivered by the **`multi-adapter-runner`** feature and must ship first.

**Locked decisions:** CSS Modules only (no Tailwind, no inline styles); theme tokens from `tokens.css`; one component per folder (~150-line limit); `runnerStore` (Zustand) owns all runner-state; SSE client is a plain `EventSource` mirroring the existing `/events/menu` pattern.

---

## Dependency

| Upstream feature | What it provides | Must ship before |
|---|---|---|
| `multi-adapter-runner` | `POST /runner/start`, `/runner/pause`, `/runner/resume`, `/runner/advance`, `/runner/reroute`, `/runner/retry`, `/runner/abort`, `POST /runner/decision`, `GET /events/runner` SSE stream, `adapters.gen.ts` | Conv 1 of this feature |

> Builder: before starting Conv 1, confirm `http://127.0.0.1:8765/runner/start` exists (Phase 0 pre-flight). If it does not, halt and report.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point for feature context |
| `DESIGN.md` | Designer | All agents | Authoritative UI spec — component layout, tokens, interaction patterns |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria — the contract |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design — the what and how |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts — one section per conversation |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status — the checkpoint |

### Optional plan files (all present)

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Component tree, store design, SSE integration decisions |
| `EDGE_CASES.md` | yes | SSE reconnect, backend not reachable, decision race |
| `HAPPY_FLOW.md` | yes | Golden-path narrative: user starts a run, confirms a decision |
| `FLOW_DIAGRAM.md` | yes | HQ → runnerStore → SSE → backend interaction diagram |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies. **Verify each path exists before editing (glob it).**

| Codebase file | Conv | What changes |
|---|---|---|
| `studio/src/renderer/src/components/ChatPanel/` | 1 | Rename folder → `HQ/`; update barrel export |
| `studio/src/renderer/src/components/ChatPanel/index.tsx` | 1 | Rename → `HQ/index.tsx`; rename component `ChatPanel` → `HQ` |
| `studio/src/renderer/src/components/ChatPanel/useChatPanel.tsx` | 1 | Rename → `HQ/useHQ.ts`; rename hook |
| `studio/src/renderer/src/components/ChatPanel/ChatHeader.tsx` | 1 | Rename → `HQ/ChatHeader.tsx`; add subtitle/tooltip per DESIGN.md |
| `studio/src/renderer/src/components/ChatPanel/PathlyMenuCard.tsx` | 1 | Move → `HQ/PathlyMenuCard.tsx`; no behavior change yet |
| `studio/src/renderer/src/components/ChatPanel/MatchCard.tsx` | 1 | Move → `HQ/MatchCard.tsx` |
| `studio/src/renderer/src/components/ChatPanel/*.module.css` | 1 | Move to `HQ/` |
| `studio/src/renderer/src/store/index.ts` | 1 | Add `runnerStore` to root merge |
| `studio/src/renderer/src/store/runnerStore.ts` | 1 | NEW — runner state, actions, SSE-driven mutations |
| `studio/src/renderer/src/components/HQ/FlowControlBar/FlowControlBar.tsx` | 1 | NEW — Start/Pause/Resume/Advance/Reroute/Retry + AbortConfirmStrip inline |
| `studio/src/renderer/src/components/HQ/FlowControlBar/FlowControlBar.module.css` | 1 | NEW |
| `studio/src/renderer/src/components/HQ/FlowControlBar/AbortConfirmStrip.tsx` | 1 | NEW — inline confirm strip per DESIGN.md |
| `studio/src/renderer/src/components/HQ/FlowControlBar/AbortConfirmStrip.module.css` | 1 | NEW |
| `studio/src/renderer/src/components/HQ/FlowControlBar/ReroutePopover.tsx` | 1 | NEW — adapter picker popover per DESIGN.md |
| `studio/src/renderer/src/components/HQ/FlowControlBar/ReroutePopover.module.css` | 1 | NEW |
| `studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.tsx` | 1 | NEW — status dot, stage, adapter chip, cost, session |
| `studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.module.css` | 1 | NEW |
| All import sites of `ChatPanel` across the app | 1 | Update to `HQ` |
| `studio/src/renderer/src/components/HQ/PathlyMenuCard.tsx` | 2 | Extend: decision mode, item click POSTs to `/runner/decision` when runner-driven |
| `studio/src/renderer/src/components/HQ/useHQ.ts` | 2 | Wire SSE client + runnerStore dispatch |
| `studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.tsx` | 2 | Wire live cost and session indicators from runnerStore |

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Structural — rename + FlowControlBar + StageStatusStrip + runnerStore | S1 | TODO | `HQ/` folder, `runnerStore.ts`, `FlowControlBar/`, `StageStatusStrip/`, `store/index.ts` |
| 2 | Behavioral — SSE client + decision menu + cost/session live | S2 | TODO | `useHQ.ts`, `PathlyMenuCard.tsx`, `StageStatusStrip.tsx` |

**Dependency:** Conv 2 requires Conv 1 complete. `multi-adapter-runner` backend must be reachable before Conv 1 Phase 0 passes.

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/hq-panel/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
