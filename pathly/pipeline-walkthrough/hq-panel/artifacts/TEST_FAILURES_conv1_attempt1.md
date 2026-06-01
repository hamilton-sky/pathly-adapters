# TEST_FAILURES — hq-panel

Tester: claude-sonnet-4-6
Date: 2026-06-01
Verify command: `cd C:/Users/Yafit/pathly-adapters/studio && npx tsc --noEmit -p tsconfig.web.json 2>&1`
Typecheck result: EXIT 0 (PASS)

---

## Full Test Plan

### Story S1: HQ rename + FlowControlBar + StageStatusStrip + runnerStore

---

Story S1, Criterion 1: Folder renamed, hook renamed, tab label reads "HQ"
  Criterion: Folder `studio/src/renderer/src/components/ChatPanel/` is renamed to `HQ/`; hook renamed `useChatPanel.tsx` → `useHQ.ts`; all import sites updated; the Studio tab label reads "HQ".
  Test: Glob for ChatPanel/ directory (not found), check HQ/ directory (exists with ~20 files), check topbar for "HQ" label, check for useHQ file.
  Status: FAIL
  Notes:
    - ChatPanel/ directory does not exist — PASS.
    - HQ/ directory exists — PASS.
    - Tab label "HQ" confirmed at studio/src/renderer/src/components/topbar/index.tsx:70 — PASS.
    - Hook file is `useHQ.tsx` (not `useHQ.ts` as the AC specifies). The file contains JSX (renderTerminalCard returns JSX.Element | null), so the .tsx extension is correct TypeScript practice. However the acceptance criterion explicitly says `useHQ.ts`. Minor discrepancy, flagged for awareness.

---

Story S1, Criterion 2: ChatHeader subtitle or tooltip element
  Criterion: `ChatHeader.tsx` renders a subtitle or tooltip element per `DESIGN.md` (element is present in the DOM, content non-empty).
  Test: Read ChatHeader.tsx for subtitle span or static description element. Read Tooltip.tsx to verify DOM presence. Read DESIGN.md for spec.
  Status: FAIL
  Notes:
    - ChatHeader.tsx has no subtitle element and no static description text element in the DOM.
    - The `<Tooltip>` components in ChatHeader render only on hover via a React portal (`createPortal` into `document.body`). They are NOT present in the DOM at initial render and are therefore not "present in the DOM" as the AC requires.
    - DESIGN.md does not explicitly define what the subtitle element should contain — it lists general design guidelines only.
    - File: studio/src/renderer/src/components/HQ/ChatHeader/ChatHeader.tsx — no subtitle or always-visible tooltip element found.

---

Story S1, Criterion 3: runnerStore fields and actions
  Criterion: `runnerStore` exists in `studio/src/renderer/src/store/runnerStore.ts` and is merged into `store/index.ts`; it exposes at minimum `status`, `stage`, `adapter`, `cost`, `sessionKind` fields and `setRunnerState` / `resetRunner` actions.
  Test: Read runnerStore.ts and store/index.ts.
  Status: PASS

---

Story S1, Criterion 4: FlowControlBar — 7 buttons, type, aria-label, POST endpoints
  Criterion: FlowControlBar renders seven buttons: Start, Pause, Resume, Advance, Reroute, Retry, Abort. Each has `type="button"` and `aria-label`. Start→/runner/start; Pause→/runner/pause; Resume→/runner/resume; Advance→/runner/advance; Retry→/runner/retry.
  Test: Read FlowControlBar.tsx for all 7 buttons, type, aria-label, and fetch calls.
  Status: PASS
  Notes: All 7 buttons present with type="button" and aria-label. POST endpoints confirmed for Start, Pause, Resume, Advance, Retry.

---

Story S1, Criterion 5: Abort — no immediate POST, reveals AbortConfirmStrip, Confirm POSTs /runner/abort, Cancel dismisses without POST
  Criterion: Clicking Abort does NOT immediately POST — reveals inline AbortConfirmStrip. Confirming POSTs to `/runner/abort`. Cancelling dismisses without any network call.
  Test: Read FlowControlBar.tsx (onClick handler for Abort), AbortConfirmStrip.tsx.
  Status: PASS
  Notes: Abort onClick sets `showAbort` state, renders AbortConfirmStrip. Confirm POSTs to /runner/abort. Cancel calls onCancel which sets showAbort(false) with no fetch call.

---

Story S1, Criterion 6: Reroute — opens ReroutePopover with adapter selector (claude/codex/copilot), Confirm POSTs /runner/reroute with adapter, Dismiss sends no request
  Criterion: Clicking Reroute opens `ReroutePopover` with an adapter selector (claude / codex / copilot). Confirming POSTs to `/runner/reroute` with the chosen adapter. Dismissing without confirming sends no request.
  Test: Read ReroutePopover.tsx and adapters.gen.ts.
  Status: PASS
  Notes: ReroutePopover uses ADAPTERS from adapters.gen.ts which contains exactly claude, codex, copilot. `<select>` renders these options. Confirm POSTs {adapter: selected} to /runner/reroute. Cancel calls onClose with no fetch.

---

Story S1, Criterion 7: Button enabled/visibility logic
  Criterion: Start enabled when `status === 'idle'`; Pause when `'running'`; Resume when `'paused'`; Advance, Reroute, Retry enabled when `'blocked'`; Abort when `status !== 'idle'`.
  Test: Read FlowControlBar.tsx enabled condition variables.
  Status: FAIL
  Notes:
    - Start: `startEnabled = status === 'idle' || status === 'done'` — PASS for `idle`, but also enabled when `done`. AC says only `idle`.
    - Pause: `pauseEnabled = status === 'running'` — PASS.
    - Resume: `resumeEnabled = status === 'paused'` — PASS.
    - Advance: `advanceEnabled = status === 'blocked'` — PASS.
    - Reroute: `rerouteEnabled = status === 'blocked'` — PASS.
    - Retry: `retryEnabled = status === 'error'` — FAIL. AC says Retry is enabled when `status === 'blocked'`; code enables it when `status === 'error'`.
    - Abort: `abortEnabled = status !== 'idle'` — PASS.

    Bug 1: Retry button is enabled when `status === 'error'` but the AC requires it to be enabled when `status === 'blocked'`. These are mutually exclusive states — this is a logic discrepancy.
    Bug 2: Start button is also enabled when `status === 'done'`, which is not specified in the AC. This may be intentional product behavior (allow restart after completion) but diverges from the stated acceptance criterion.

---

Story S1, Criterion 8: StageStatusStrip — status dot (pulsing when running), stage name, adapter chip with CSS custom props + aria-hidden, cost display, session indicator, neutral placeholder when no data
  Criterion: `StageStatusStrip` renders: status dot (pulsing CSS animation when `status === 'running'`), current stage name, adapter color chip (claude=`var(--accent)`, codex=`var(--green)`, copilot=`var(--yellow)`) with `aria-hidden="true"`, cost display, session indicator. When `runnerStore` holds no data the strip renders a neutral placeholder.
  Test: Read StageStatusStrip.tsx and StageStatusStrip.module.css.
  Status: FAIL
  Notes:
    - Status dot: present with `dotRunning` class applying `animation: pulse 1.4s ease-in-out infinite` — PASS.
    - Stage name: `{stage ?? '—'}` — PASS with neutral placeholder.
    - Adapter chip: present when adapter non-null with `style={{ '--chip-color': adapterColor }}`. Adapter colors are: claude=`var(--accent)`, codex=`var(--green)`, copilot=`var(--yellow)` — PASS.
    - `aria-hidden="true"` on adapterChip span — PASS.
    - Cost display: present with `$${cost.toFixed(3)}` format — PASS.
    - Session indicator: present using SESSION_LABELS lookup — PASS.
    - Neutral placeholder: stage shows '—', dot uses dotIdle class — PASS.

    Bug 3: Adapter chip uses an inline style prop `style={{ '--chip-color': adapterColor } as React.CSSProperties}` in JSX. Per studio/CLAUDE.md: inline styles are forbidden; CSS custom properties should be set via `ref.current.style.setProperty(...)` in a `useEffect`, not via the JSX `style` prop. This is a code quality/CLAUDE.md violation, not a functional AC failure. Flagged for the builder.

---

Story S1, Criterion 9: Typecheck passes
  Criterion: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` exits 0 after all changes.
  Test: Run `cd C:/Users/Yafit/pathly-adapters/studio && npx tsc --noEmit -p tsconfig.web.json 2>&1`
  Status: PASS
  Notes: Exit code 0. No TypeScript errors.

---

Story S1, Criterion 10: Failure case — non-2xx POST surfaces error in strip, no silent failure
  Criterion: If the POST to any `/runner/*` endpoint returns a non-2xx status, the error is surfaced in the strip (visible error message string).
  Test: Read FlowControlBar.tsx postAction error path, AbortConfirmStrip.tsx, ReroutePopover.tsx error paths.
  Status: PASS
  Notes: postAction catches non-2xx and calls `setRunnerState({ errorMessage: ... })`. AbortConfirmStrip and ReroutePopover call onError which propagates to setRunnerState. StageStatusStrip renders errorMessage with role="alert" when non-null.

---

### Story S2: SSE client + live decision menu + session/cost indicators

---

Story S2, Criterion 1: useHQ.ts opens EventSource on mount, closes on unmount, no duplicate connections
  Criterion: `useHQ.ts` opens an `EventSource` to `http://127.0.0.1:8765/events/runner` on mount and closes it on unmount. No duplicate connections on re-renders.
  Test: Read useHQ.tsx for EventSource lifecycle.
  Status: PASS
  Notes: EventSource opened in a `useEffect([], [])` with empty deps array (runs once). Cleanup function closes via `es?.close()`. Reconnect timeout is also cleared on unmount. URL confirmed as `http://127.0.0.1:8765/events/runner`.

---

Story S2, Criterion 2: SSE event types handled and update runnerStore
  Criterion: STAGE_CHANGE (→ stage, adapter, status), DECISION_MENU (→ decisionMenu, status='blocked'), RUNNER_STATUS (→ status), COST_UPDATE (→ cost), SESSION (→ sessionKind), RUNNER_ERROR (→ errorMessage, status='error').
  Test: Read useHQ.tsx SSE onmessage handler.
  Status: PASS
  Notes: All 6 event types handled at useHQ.tsx lines 228-249. Each maps to the correct store fields per the AC.

---

Story S2, Criterion 3: PathlyMenuCard decision mode — typewriter reveal, POST on click, optimistic clear
  Criterion: When `runnerStore.decisionMenu` is non-null, PathlyMenuCard renders in decision mode: items streamed token-by-token (typewriter reveal); clicking item POSTs `{ choice: item.id }` to `POST http://127.0.0.1:8765/runner/decision` and clears `decisionMenu` optimistically.
  Test: Read PathlyMenuCard.tsx and DecisionButton.tsx.
  Status: FAIL
  Notes:
    - Typewriter reveal: DecisionButton.tsx uses setInterval at 20ms per character — PASS.
    - POST on click: POSTs `{ choice: item.id }` to `/runner/decision` — PASS.
    - Optimistic clear: The AC says the menu is cleared "optimistically" (before the response). The actual code does NOT clear optimistically — it calls `onDone()` (which sets decisionMenu to null) only after a successful 2xx response. On non-2xx, disabled state is reverted and error is shown, but the menu never disappeared in the first place. The end behavior (menu disappears on success, remains on failure) is correct, but the mechanism is conservative (success-gated) rather than optimistic.

    Bug 4: The AC says "clears decisionMenu from the store optimistically" — meaning the clear should happen immediately on click, before the network response, and be reverted on failure. The current implementation clears only on success. The practical difference: on slow network, the menu items remain visible and clickable (button disabled for one) until the POST resolves. File: studio/src/renderer/src/components/HQ/PathlyMenuCard/DecisionButton.tsx:25-42

---

Story S2, Criterion 4: PathlyMenuCard reverts to FSM-menu behavior when decisionMenu is null
  Criterion: When `runnerStore.decisionMenu` is null, PathlyMenuCard reverts to its original FSM-menu behavior (clicking item calls `writeToTerminal` as before).
  Test: Read PathlyMenuCard.tsx conditional rendering.
  Status: PASS
  Notes: Lines 99-116 render the standard FSM menu items when decisionMenu is null, calling onSelect (which maps to handleMenuSelect → writeToTerminal in useHQ.tsx).

---

Story S2, Criterion 5: StageStatusStrip displays live cost from runnerStore
  Criterion: `StageStatusStrip` displays the live `cost` value from `runnerStore` (formatted as a string, e.g. "$0.012"); it updates without a page reload.
  Test: Read StageStatusStrip.tsx cost display logic.
  Status: PASS
  Notes: `costDisplay = cost === 0 && status === 'idle' ? '—' : \`$\${cost.toFixed(3)}\`` — e.g. "$0.012" format. Reads from runnerStore selector so updates reactively.

---

Story S2, Criterion 6: Session indicator labels
  Criterion: Session indicator renders "New session" for `opened`, "Continued" for `continued`, "Degraded" for `degraded`; absent when no session event received.
  Test: Read StageStatusStrip.tsx SESSION_LABELS and render logic.
  Status: PASS
  Notes: SESSION_LABELS at lines 5-9 map exactly these values. `sessionLabel` is null when sessionKind is null, so the span is not rendered. PASS.

---

Story S2, Criterion 7: SSE disconnect — "Reconnecting..." state, reconnect after delay
  Criterion: On `EventSource` `onerror` the strip shows a "Reconnecting…" state; it attempts reconnect after a 3-second delay (exponential back-off is not required).
  Test: Read useHQ.tsx onerror handler.
  Status: PASS
  Notes: onerror at line 252 sets `errorMessage: 'Reconnecting...'` and calls connect() after `delay = Math.min(3000 * Math.pow(2, retryCount), 30000)` ms. First delay is 3000ms (3s). Exponential backoff is implemented as a bonus beyond the AC's minimum requirement.

---

Story S2, Criterion 8: Typecheck passes after Conv 2 changes
  Criterion: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` exits 0.
  Test: Run typecheck.
  Status: PASS
  Notes: Exit code 0. Confirmed same run as S1 Criterion 9.

---

Story S2, Criterion 9: Failure case — /runner/decision non-2xx revert + error shown
  Criterion: If `/runner/decision` returns a non-2xx, the optimistic clear is reverted (menu items reappear) and an error message appears in the strip.
  Test: Read DecisionButton.tsx error path.
  Status: FAIL
  Notes: Same as Bug 4 above. The clear is not optimistic — it never fires on failure. Menu items do not disappear and therefore cannot "reappear". The error message IS shown via onError → setRunnerState({ errorMessage: ... }) in StageStatusStrip. The second half of the criterion (error message appears) is satisfied. The first half (optimistic clear + revert) is not implemented.

---

## Summary

| Story | Criterion | Status |
|---|---|---|
| S1.1 | Folder/hook rename, tab label | FAIL (hook is .tsx not .ts) |
| S1.2 | ChatHeader subtitle/tooltip in DOM | FAIL |
| S1.3 | runnerStore fields and actions | PASS |
| S1.4 | FlowControlBar 7 buttons, type, aria-label, POSTs | PASS |
| S1.5 | Abort → AbortConfirmStrip, POST /runner/abort | PASS |
| S1.6 | Reroute → ReroutePopover, POST /runner/reroute | PASS |
| S1.7 | Button enabled logic | FAIL |
| S1.8 | StageStatusStrip renders | FAIL (CLAUDE.md inline style violation) |
| S1.9 | Typecheck passes | PASS |
| S1.10 | Non-2xx POST surfaces error | PASS |
| S2.1 | EventSource lifecycle | PASS |
| S2.2 | SSE event types handled | PASS |
| S2.3 | PathlyMenuCard decision mode + optimistic clear | FAIL |
| S2.4 | PathlyMenuCard FSM fallback | PASS |
| S2.5 | Cost display live | PASS |
| S2.6 | Session indicator labels | PASS |
| S2.7 | SSE disconnect → Reconnecting... | PASS |
| S2.8 | Typecheck passes (Conv 2) | PASS |
| S2.9 | /runner/decision non-2xx revert | FAIL |

---

## Bugs Found

**Bug 1 (S1.7 — FAIL):** `retryEnabled = status === 'error'` in FlowControlBar.tsx line 31. AC requires Retry to be enabled when `status === 'blocked'`. These are different states. File: studio/src/renderer/src/components/HQ/FlowControlBar/FlowControlBar.tsx:31

**Bug 2 (S1.7 — FAIL):** `startEnabled = status === 'idle' || status === 'done'` in FlowControlBar.tsx line 26. AC specifies Start is enabled only when `status === 'idle'`. The extra `|| status === 'done'` is unspecified behavior. File: studio/src/renderer/src/components/HQ/FlowControlBar/FlowControlBar.tsx:26

**Bug 3 (S1.8 — code quality):** StageStatusStrip.tsx line 44 uses `style={{ '--chip-color': adapterColor } as React.CSSProperties}` — a JSX inline style prop for a CSS custom property. CLAUDE.md prohibits inline styles except via `ref.current.style.setProperty(...)` in a `useEffect`, not via the JSX `style` prop. Not a functional AC failure but violates coding rules. Same pattern in ReroutePopover.tsx line 68. Files: studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.tsx:44, studio/src/renderer/src/components/HQ/FlowControlBar/ReroutePopover.tsx:68

**Bug 4 (S2.3 + S2.9 — FAIL):** DecisionButton.tsx does not implement optimistic clear. `onDone()` (which sets decisionMenu=null) is called only after `res.ok`. On non-2xx, the button reverts disabled state and shows an error, but menu was never cleared. File: studio/src/renderer/src/components/HQ/PathlyMenuCard/DecisionButton.tsx:25-42

**Minor (S1.1):** Hook file is named `useHQ.tsx` not `useHQ.ts` as the AC specifies. File: studio/src/renderer/src/components/HQ/useHQ.tsx

**Bug 5 (S1.2 — FAIL):** ChatHeader.tsx has no subtitle element and no always-visible tooltip text in the DOM. Tooltip components render only on hover via portal. DESIGN.md does not specify what the subtitle content should be. File: studio/src/renderer/src/components/HQ/ChatHeader/ChatHeader.tsx
