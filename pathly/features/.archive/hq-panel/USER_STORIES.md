---
name: User Stories
---
# HQ Panel — User Stories

## Context

Pathly Studio currently has a `ChatPanel` that renders FSM menu cards and lets users write to a terminal tab. As Pathly gains an autonomous multi-adapter runner (the `multi-adapter-runner` backend feature), Studio needs a command center that surfaces runner state, lets the user drive the pipeline (Start, Pause, Resume, Advance, Reroute, Retry, Abort), and streams live decision menus so the user can confirm or steer the AI mid-run — all without leaving the panel.

These two stories cover the full Studio upgrade. They build sequentially: S1 delivers the structure and controls wired to the backend; S2 brings the panel to life with SSE streaming, decision interactivity, and cost/session tracking.

---

## Stories

### S1: HQ rename + FlowControlBar + StageStatusStrip + runnerStore

**As a** Pathly Studio user, **I want** the ChatPanel renamed to HQ with a control bar and a live status strip, **so that** I can start, pause, resume, advance, reroute, retry, or abort a pipeline run from one place and see what stage and adapter are currently active.

**Acceptance Criteria:**
- [ ] Folder `studio/src/renderer/src/components/ChatPanel/` is renamed to `HQ/`; hook renamed `useChatPanel.tsx` → `useHQ.tsx`; all import sites updated; the Studio tab label reads "HQ".
- [ ] `ChatHeader.tsx` renders a subtitle or tooltip element per `DESIGN.md` (element is present in the DOM, content non-empty).
- [ ] `runnerStore` exists in `studio/src/renderer/src/store/runnerStore.ts` and is merged into `store/index.ts`; it exposes at minimum `status`, `stage`, `adapter`, `cost`, `sessionKind` fields and `setRunnerState` / `resetRunner` actions.
- [ ] `FlowControlBar` renders seven buttons: Start, Pause, Resume, Advance, Reroute, Retry, Abort. Each button carries `type="button"` and an `aria-label`. Clicking Start sends `POST http://127.0.0.1:8765/runner/start`; Pause → `/runner/pause`; Resume → `/runner/resume`; Advance → `/runner/advance`; Retry → `/runner/retry`. (Reroute and Abort have their own AC below.)
- [ ] Clicking Abort does NOT immediately POST — it reveals the inline `AbortConfirmStrip` per `DESIGN.md`. Confirming in that strip POSTs to `/runner/abort`. Cancelling dismisses the strip without any network call.
- [ ] Clicking Reroute opens `ReroutePopover` with an adapter selector (claude / codex / copilot). Confirming in the popover POSTs to `/runner/reroute` with the chosen adapter. Dismissing without confirming sends no request.
- [ ] Button disabled/visibility logic: Start is enabled when `status === 'idle'`; Pause when `status === 'running'`; Resume when `status === 'paused'`; Advance, Reroute, Retry are enabled when `status === 'blocked'`; Abort is enabled when `status !== 'idle'`.
- [ ] `StageStatusStrip` renders: a status dot (pulsing CSS animation when `status === 'running'`), current stage name, adapter color chip (claude=`var(--accent)`, codex=`var(--green)`, copilot=`var(--yellow)`) with `aria-hidden="true"`, cost display, and session indicator. When `runnerStore` holds no data the strip renders a neutral placeholder — it does not crash.
- [ ] `typecheck` passes: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` exits 0 after all changes.
- [ ] **Failure case:** If the POST to any `/runner/*` endpoint returns a non-2xx status, the error is surfaced in the strip (e.g. a visible error message string) — the button does not silently fail.

**Edge Cases:**
- `multi-adapter-runner` backend not running: buttons still render; the POST attempt fails and the error is shown in the strip.
- All buttons pressed while `status === 'running'`: only Pause and Abort are enabled; others carry `disabled` attribute and `opacity: 0.45` per `DESIGN.md`.
- `runnerStore` has null/undefined `adapter`: `StageStatusStrip` renders no chip rather than throwing.

**Delivered by:** Phase 0–3 → Conversation 1

---

### S2: SSE client + live decision menu + session/cost indicators

**As a** Pathly Studio user, **I want** the HQ panel to stream runner events in real time and show me a live decision menu I can confirm, **so that** I can stay in the loop and steer the pipeline without switching context.

**Acceptance Criteria:**
- [ ] `useHQ.ts` opens an `EventSource` to `http://127.0.0.1:8765/events/runner` on mount and closes it on unmount. No duplicate connections on re-renders.
- [ ] The following SSE event types are handled and update `runnerStore`: `STAGE_CHANGE` (→ `stage`, `adapter`, `status`), `DECISION_MENU` (→ `decisionMenu`, `status = 'blocked'`), `RUNNER_STATUS` (→ `status`), `COST_UPDATE` (→ `cost`), `SESSION` (→ `sessionKind`: one of `opened` / `continued` / `degraded`), `RUNNER_ERROR` (→ `errorMessage`, `status = 'error'`).
- [ ] When `runnerStore.decisionMenu` is non-null, `PathlyMenuCard` renders in decision mode: menu items are streamed token-by-token per `DESIGN.md`'s typewriter-reveal rule; clicking an item POSTs `{ choice: item.id }` to `POST http://127.0.0.1:8765/runner/decision` and clears `decisionMenu` from the store optimistically.
- [ ] When `runnerStore.decisionMenu` is null, `PathlyMenuCard` reverts to its original FSM-menu behavior (clicking an item calls `writeToTerminal` as before).
- [ ] `StageStatusStrip` displays the live `cost` value from `runnerStore` (formatted as a string, e.g. "$0.012"); it updates without a page reload.
- [ ] Session indicator in `StageStatusStrip` renders a visible label for each `sessionKind`: "New session" for `opened`, "Continued" for `continued`, "Degraded" for `degraded`; absent when no session event has been received.
- [ ] SSE disconnect is handled: on `EventSource` `onerror` the strip shows a "Reconnecting…" state; it attempts reconnect after a 3-second delay (exponential back-off is not required).
- [ ] `typecheck` passes after Conv 2 changes: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` exits 0.
- [ ] **Failure case:** If `/runner/decision` returns a non-2xx, the optimistic clear is reverted (menu items reappear) and an error message appears in the strip.

**Edge Cases:**
- SSE connection never established (backend offline): strip shows "Reconnecting…" immediately; no unhandled exception.
- `DECISION_MENU` event arrives twice before user clicks (runner resent it): `runnerStore` replaces the existing menu with the new one; no duplicate menus rendered.
- User clicks a decision menu item twice rapidly: only one POST is sent; button is disabled after first click.
- `COST_UPDATE` events arrive at high frequency: the cost display throttles DOM updates (no more than one render per 200 ms).

**Delivered by:** Phases 4–6 → Conversation 2
