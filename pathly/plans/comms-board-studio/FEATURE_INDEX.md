---
name: Feature Index
---
# Comms Board — Studio CommsPanel (Phase 2) — Feature Index

> **Read this first.** Every agent working on this feature loads this file before any other plan file.

> **Scope:** Phase 2 of the communication board — the Studio UI. Builds the single-feature
> **CommsPanel** on top of the Phase 1 backend (already on master: `/comms/*` + `/events/comms`).
> Delivers a visual board: see agent messages in real time, post nudges/decisions, answer
> questions, switch Feature/Project/Global views. **Not** in scope: the 3-panel command center
> (Phase 4) or artifact attach UI (`/comms/attach` is a 501 stub). Parent design: `../comms-board/SPEC.md`
> §7 (panel anatomy), §19 (layout), `../comms-board/CONSULTATION.md` §3 (designer guidance).

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder | Phase-by-phase design |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator | Conversation status |

### Optional plan files

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Store/SSE/HTTP integration + component decomposition decisions |
| `EDGE_CASES.md` | yes | Server down, empty board, SSE reconnect, optimistic post failure |
| `HAPPY_FLOW.md` | yes | Agent posts → human sees live → human answers → resolved |
| `FLOW_DIAGRAM.md` | yes | SSE + fetch wiring between CommsPanel, store, and the FSM |

---

## Prerequisite (already shipped — Phase 1 on master)

| Endpoint / capability | Where |
|---|---|
| `POST /comms/post`, `GET /comms`, `POST /comms/search`, `POST /comms/answer`, `POST /comms/acknowledge` | `src/pathly_orchestrator/http_server/blueprints/comms.py` |
| `GET /events/comms?scope=<feature>` (SSE `COMMS_UPDATE`) | `blueprints/streams.py` + `sse.py` |
| Convention: `board` ∈ {feature,project,global}, `scope` = identifier (feature name / project root / 'global') | SPEC §21.1 |

---

## Codebase touchpoints

| Codebase file | Conversation | What changes |
|---|---|---|
| `studio/src/renderer/src/store/commsStore.ts` | Conv 1 | CREATE: Zustand store — messages, board, scope, pendingCount, actions |
| `studio/src/renderer/src/store/index.ts` | Conv 1 | MODIFY: re-export `useCommsStore` |
| `studio/src/renderer/src/services/commsApi.ts` | Conv 1 | CREATE: fetch wrappers for `/comms/*` |
| `studio/src/renderer/src/store/notificationStore.ts` | Conv 1 | MODIFY: add `'comms_update'` toast category |
| `studio/src/renderer/src/components/HQ/useHQ.tsx` | Conv 1 | MODIFY: 2nd EventSource → `/events/comms?scope=`; COMMS_UPDATE handler; initial fetch |
| `studio/src/renderer/src/components/HQ/CommsPanel/CommsPanel.tsx` | Conv 2 | CREATE: outer shell (subtitle, board toggle, thread, send slot) |
| `studio/src/renderer/src/components/HQ/CommsPanel/CommsMsgList.tsx` | Conv 2 | CREATE: thread; pinned decisions on top |
| `studio/src/renderer/src/components/HQ/CommsPanel/CommsMsgCard.tsx` | Conv 2 | CREATE: one message; `data-type` variants |
| `studio/src/renderer/src/components/HQ/CommsPanel/BoardToggle.tsx` | Conv 2 | CREATE: pill toggles (Feature/Project/Global) — NOT tabs |
| `studio/src/renderer/src/components/HQ/CommsPanel/hooks/useCommsPanel.ts` | Conv 2 | CREATE: UI state — active board, filtered messages |
| `studio/src/renderer/src/components/HQ/index.tsx` | Conv 2 | MODIFY: mount `<CommsPanel>` after `AgentQuestionCard` |
| `studio/src/renderer/src/components/HQ/CommsPanel/CommsInput.tsx` | Conv 3 | CREATE: compose bar; type dropdown (default Note) |
| `studio/src/renderer/src/components/HQ/CommsPanel/CommsQuestionCard.tsx` | Conv 3 | CREATE: question + options (reuse AgentQuestionCard pattern) |

> Each component folder also gets its own `*.module.css` (Studio rule: one component + module per folder).
> **Verify every path before editing** — glob each.

---

## Conversation map

| Conv | Title | Stories | Status | Key files |
|---|---|---|---|---|
| 1 | Store + API + SSE wiring | S1.1, S1.2 | TODO | `commsStore.ts`, `commsApi.ts`, `useHQ.tsx` |
| 2 | CommsPanel shell + message thread | S2.1, S2.2 | TODO | `CommsPanel/*`, `index.tsx` |
| 3 | Compose + question/decision/escalation interactions | S3.1, S3.2 | TODO | `CommsInput.tsx`, `CommsQuestionCard.tsx` |

---

## Studio rules (non-negotiable — from `studio/CLAUDE.md`)

- **No inline styles** — all styling in `.module.css`; theme via `var(--accent)` etc. from `tokens.css`.
- **~150 line** component cap; one component + module per folder; extract hooks to `hooks/`.
- **`data-*` attributes** for 3+ states (use `data-type` for message variants).
- Every `<button>` has `type="button"`. Use ARIA (`aria-label`, `aria-expanded` via spread pattern).
- **Typecheck from repo root:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` (or `cd studio; npm run typecheck`).

## Feedback files (transient)

Live in `pathly/plans/comms-board-studio/feedback/`. `REVIEW_FAILURES.md`, `TEST_FAILURES.md`, `IMPL_QUESTIONS.md`, `HUMAN_QUESTIONS.md`.
