---
name: Conversation Guide
---
# HQ Panel — Conversation Guide

Split into 2 conversations. Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

Dependency: Conv 1 → Conv 2. Both depend on `multi-adapter-runner` backend being shipped first.

---

## Conversation 1: Structural — rename + FlowControlBar + StageStatusStrip + runnerStore (Phases 0–3)

**Stories delivered:** S1

**Prompt to paste:**
```
Read pathly/plans/hq-panel/FEATURE_INDEX.md first to orient yourself and verify codebase paths.
Read pathly/plans/hq-panel/DESIGN.md for the exact component spec and interaction rules.

Implement HQ Panel Conversation 1 (Phases 0–3) from pathly/plans/hq-panel/IMPLEMENTATION_PLAN.md.

Before editing anything: glob/read the live repo to confirm every file path listed below exists.
Correct any discrepancy between the plan's stated paths and reality before proceeding.
Read studio/CLAUDE.md — Studio UI rules are non-negotiable and apply to every file you touch:
  - NO inline styles. CSS Modules only. All colors from tokens.css custom properties.
  - One component per folder with a paired *.module.css. ~150-line component limit; extract sub-components if needed.
  - Every <button> must carry type="button".
  - ARIA on all interactive elements: aria-label on icon-only buttons, aria-disabled mirrors disabled prop, aria-hidden="true" on decorative chips.
  - Disabled state: opacity: 0.45 + cursor: not-allowed — never same visual as enabled.

Codebase files this conversation touches:
- `studio/src/renderer/src/components/ChatPanel/` — rename to HQ/
- `studio/src/renderer/src/components/ChatPanel/index.tsx` — rename to HQ/index.tsx, component ChatPanel → HQ
- `studio/src/renderer/src/components/ChatPanel/useChatPanel.tsx` — rename to HQ/useHQ.ts, hook → useHQ
- `studio/src/renderer/src/components/ChatPanel/ChatHeader.tsx` — move to HQ/, add subtitle/tooltip per DESIGN.md
- `studio/src/renderer/src/components/ChatPanel/PathlyMenuCard.tsx` — move to HQ/ (no behavior change)
- `studio/src/renderer/src/components/ChatPanel/MatchCard.tsx` — move to HQ/ (no behavior change)
- `studio/src/renderer/src/components/ChatPanel/*.module.css` — move to HQ/
- All import sites of ChatPanel across studio/src/renderer/src/ — update to HQ
- `studio/src/renderer/src/store/runnerStore.ts` — NEW
- `studio/src/renderer/src/store/index.ts` — add runnerStore
- `studio/src/renderer/src/components/HQ/FlowControlBar/FlowControlBar.tsx` — NEW
- `studio/src/renderer/src/components/HQ/FlowControlBar/FlowControlBar.module.css` — NEW
- `studio/src/renderer/src/components/HQ/FlowControlBar/AbortConfirmStrip.tsx` — NEW
- `studio/src/renderer/src/components/HQ/FlowControlBar/AbortConfirmStrip.module.css` — NEW
- `studio/src/renderer/src/components/HQ/FlowControlBar/ReroutePopover.tsx` — NEW
- `studio/src/renderer/src/components/HQ/FlowControlBar/ReroutePopover.module.css` — NEW
- `studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.tsx` — NEW
- `studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.module.css` — NEW

Scope:
- Phase 0 (pre-flight): run `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` and record any pre-existing errors as baseline — do NOT fix them. Confirm `GET http://127.0.0.1:8765/runner/start` returns any HTTP response (curl — a 405 counts). Glob for adapters.gen.ts; if absent write an OPEN item to pathly/plans/hq-panel/feedback/HUMAN_QUESTIONS.md and halt.
- Phase 1 (rename): rename the ChatPanel folder to HQ and all contained files per the plan. Rename the component export to HQ, the hook to useHQ. Add subtitle/tooltip to ChatHeader per DESIGN.md. Grep and update all import sites. Update the tab label to "HQ".
- Phase 2 (runnerStore): create studio/src/renderer/src/store/runnerStore.ts with the state shape and actions from the plan (RunnerStatus, SessionKind, DecisionMenuItem, setRunnerState, resetRunner, setDecisionMenu). Add to store/index.ts.
- Phase 3 (controls + strip): create FlowControlBar (with AbortConfirmStrip and ReroutePopover sub-components) and StageStatusStrip per the plan and DESIGN.md. Wire FlowControlBar and StageStatusStrip into HQ/index.tsx. Button disabled logic and POST endpoints as specified in S1 acceptance criteria. Non-2xx responses surface an errorMessage in runnerStore.

Do NOT wire SSE or modify PathlyMenuCard behavior yet. Do NOT touch any Python files.
Verify: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`
After done, update pathly/plans/hq-panel/PROGRESS.md phases 0–3 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** ChatPanel fully renamed to HQ; runnerStore in place; FlowControlBar renders seven buttons with correct disabled logic; AbortConfirmStrip and ReroutePopover present as sub-components; StageStatusStrip renders with neutral placeholder state; typecheck exits 0.

**Files touched:** `HQ/` folder (all renamed/moved files), `store/runnerStore.ts`, `store/index.ts`, `HQ/FlowControlBar/` (3 components + 3 CSS Modules), `HQ/StageStatusStrip/` (1 component + 1 CSS Module)

---

## Conversation 2: Behavioral — SSE client + decision menu + cost/session live (Phases 4–6)

**Stories delivered:** S2

**Prompt to paste:**
```
Read pathly/plans/hq-panel/FEATURE_INDEX.md first to orient yourself and verify codebase paths.
Read pathly/plans/hq-panel/DESIGN.md for the exact component spec and interaction rules.

Implement HQ Panel Conversation 2 (Phases 4–6) from pathly/plans/hq-panel/IMPLEMENTATION_PLAN.md.
Conversation 1 (structural) is complete — HQ folder exists, runnerStore is in place, FlowControlBar and StageStatusStrip render.

Before editing anything: glob/read the live repo to confirm every file path listed below exists.
Correct any discrepancy between the plan's stated paths and reality before proceeding.
Read studio/CLAUDE.md — Studio UI rules apply to every file you touch:
  - NO inline styles. CSS Modules only. All colors from tokens.css custom properties.
  - One component per folder with a paired *.module.css. ~150-line component limit; extract sub-components if needed.
  - Every <button> must carry type="button".
  - ARIA on all interactive elements: aria-label on icon-only buttons, aria-live="polite" on streaming content, aria-disabled mirrors disabled prop.
  - Disabled state: opacity: 0.45 + cursor: not-allowed — never same visual as enabled.
Read studio/src/renderer/src/pathlyContext.ts (or wherever the /events/menu EventSource is set up) to mirror the SSE pattern exactly.

Codebase files this conversation touches:
- `studio/src/renderer/src/components/HQ/useHQ.ts` — add EventSource to /events/runner; dispatch all 6 event types to runnerStore; 3s reconnect on error
- `studio/src/renderer/src/components/HQ/PathlyMenuCard.tsx` — extend with decision mode: when runnerStore.decisionMenu is non-null render decision items with typewriter reveal; item click POSTs /runner/decision; when null original writeToTerminal behavior unchanged
- `studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.tsx` — wire live cost (already reads store, ensure selector updates on cost/sessionKind); session label map (opened/continued/degraded)

Scope:
- Phase 4 (SSE client): in useHQ.ts open EventSource('http://127.0.0.1:8765/events/runner') in a useEffect([]) — close on cleanup. Handle STAGE_CHANGE, DECISION_MENU, RUNNER_STATUS, COST_UPDATE (throttle: max 1 store write per 200ms via useRef timestamp), SESSION, RUNNER_ERROR. On onerror: setRunnerState({ errorMessage: 'Reconnecting...' }) + 3s setTimeout to create a new EventSource (cancel timeout on cleanup).
- Phase 5 (PathlyMenuCard decision mode): when runnerStore.decisionMenu is non-null render decision buttons with typewriter reveal (20ms/char interval, aria-live="polite" on container). On click: disable button immediately, POST { choice: item.id } to /runner/decision, on success clear decisionMenu in store, on non-2xx revert disabled and set errorMessage. When null: writeToTerminal behavior unchanged.
- Phase 6 (live indicators): ensure StageStatusStrip re-renders on cost and sessionKind changes (use selective Zustand selectors). Session label map: opened → "New session", continued → "Continued", degraded → "Degraded" (var(--yellow) text). Verify cost ticks during a live run.

Do NOT touch any Python files. Do NOT touch FlowControlBar, runnerStore shape, or store/index.ts.
Verify: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`
Then launch Studio, click Start, wait for a DECISION_MENU SSE event, confirm a menu item, and verify the round-trip (item disappears from the UI, POST to /runner/decision was sent).
After done, update pathly/plans/hq-panel/PROGRESS.md phases 4–6 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `useHQ.ts` drives all runner state from SSE; `PathlyMenuCard` streams decision items and round-trips to `/runner/decision`; cost and session labels update live; typecheck exits 0; manual round-trip confirmed.

**Files touched:** `HQ/useHQ.ts`, `HQ/PathlyMenuCard.tsx`, `HQ/StageStatusStrip/StageStatusStrip.tsx`
