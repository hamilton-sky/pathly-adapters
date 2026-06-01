---
name: Progress
---
# HQ Panel — Progress

## Status: IN PROGRESS

## Story Status

| Story | Title | Delivered by | Status |
|---|---|---|---|
| S1 | HQ rename + FlowControlBar + StageStatusStrip + runnerStore | Conv 1 (Phases 0–3) | DONE |
| S2 | SSE client + live decision menu + session/cost indicators | Conv 2 (Phases 4–6) | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|---|---|---|---|---|
| 1 | 0 (pre-flight), 1 (rename), 2 (runnerStore), 3 (FlowControlBar + StageStatusStrip) | S1 | DONE | `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` |
| 2 | 4 (SSE client), 5 (PathlyMenuCard decision mode), 6 (live cost/session) | S2 | TODO | `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|---|---|---|---|---|---|
| 1 | 0 — Pre-flight | `PROGRESS.md` | Baseline typecheck + backend reachability check | typecheck exits 0; `/runner/start` returns any HTTP response | DONE |
| 1 | 1 — Rename | `ChatPanel/` → `HQ/`, `useChatPanel.tsx` → `useHQ.tsx`, all import sites | Folder rename, hook rename, tab label update | No `ChatPanel*` file remains; typecheck 0 | DONE |
| 1 | 2 — runnerStore | `store/runnerStore.ts` (NEW), `store/index.ts` | Zustand store with status/stage/adapter/cost/session/decisionMenu | Store importable; typecheck 0 | DONE |
| 1 | 3 — Controls + strip | `HQ/FlowControlBar/` (NEW), `HQ/StageStatusStrip/` (NEW) | FlowControlBar + AbortConfirmStrip + ReroutePopover + StageStatusStrip | Start button POSTs; typecheck 0 | DONE |
| 2 | 4 — SSE client | `HQ/useHQ.ts` | EventSource to `/events/runner`; all 6 event types dispatch to runnerStore | Mount opens, unmount closes; typecheck 0 | TODO |
| 2 | 5 — Decision mode | `HQ/PathlyMenuCard.tsx` | Decision menu renders + item click POSTs `/runner/decision` | Round-trip confirmed; non-decision falls through unchanged; typecheck 0 | TODO |
| 2 | 6 — Live indicators | `HQ/StageStatusStrip/StageStatusStrip.tsx` | Cost and session live wiring | Cost ticks on COST_UPDATE events; session label correct; typecheck 0 | TODO |

## Prerequisites

- `multi-adapter-runner` backend feature merged and server running at `http://127.0.0.1:8765`.
- `adapters.gen.ts` generated and present in the Studio source tree.
- Studio typecheck baseline clean (or pre-existing failures recorded in Phase 0).

## Blocked By

- `multi-adapter-runner` backend feature (must ship first — provides `/runner/*` endpoints and `/events/runner` SSE stream).
