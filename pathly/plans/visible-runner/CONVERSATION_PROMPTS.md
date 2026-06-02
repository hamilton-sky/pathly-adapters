# visible-runner — Conversation Guide

Split into 3 conversations. Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Backend contracts (Phases 0–3)

**Stories delivered:** S1 (backend side), S3 (abort signal), S7 (headless fallback)

**Prompt to paste:**
```
Read pathly/plans/visible-runner/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement visible-runner Conversation 1 (Phases 0–3) from pathly/plans/visible-runner/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy between the plan's stated paths and reality before proceeding.

**Codebase files this conversation touches:**
- `src/pathly_orchestrator/runner.py` — extract `resolve_argv()` function (Phase 1)
- `src/pathly_orchestrator/http_server.py` — add POST /runner/terminal/started and POST /runner/terminal/result endpoints (Phase 2)
- `src/pathly_orchestrator/supervisor.py` — add `_run_stage_via_terminal()`, refactor `_loop` to call it, add TERMINAL_SPAWN/SIGNAL/WARNING broadcasts (Phase 3)

Phase 0 — Pre-flight:
Run `python -m pytest tests/ -q` and record the exit code and any failures. Stop here if tests fail — do not continue if the baseline is broken.

Phase 1 — Extract argv builder:
In `runner.py`, extract argv construction from `invoke_agent()` into a new `resolve_argv(adapter, prompt, model, session=None, autonomy=None) → list[str]` function. `invoke_agent()` calls `resolve_argv()` internally. The argv must include `--output-format=json` (or adapter equivalent) so PTY and headless modes share the same argv construction.

Phase 2 — HTTP callback endpoints:
In `http_server.py`, add two new POST routes:
- `POST /runner/terminal/started`: body `{topic, run_id, tab_id, pid}`. Finds the active RunnerState by topic, sets a `threading.Event` keyed by `run_id` (stored in a dict on the supervisor module or RunnerState). Returns `{"ok": true}`.
- `POST /runner/terminal/result`: body `{topic, run_id, exit_code, final_json, wall_seconds}`. Stores the result and sets a second threading.Event to unblock `_run_stage_via_terminal`. Returns `{"ok": true}`.
Both return `{"error": "unknown run_id"}` if not found.
Follow the existing handler registration pattern in http_server.py exactly.

Phase 3 — _run_stage_via_terminal:
In `supervisor.py`, add `_run_stage_via_terminal(state, instructions, adapter, model, run_id) → dict`:
1. Build argv via `resolve_argv(adapter, instructions, model, ...)`.
2. Generate `tab_id = f"runner-{run_id[:8]}"`, `label = f"{adapter} — {state}"`.
3. Broadcast SSE: `{"type": "TERMINAL_SPAWN", "topic": topic, "run_id": run_id, "tab_id": tab_id, "label": label, "adapter": adapter, "argv": argv, "cwd": project_root, "prompt": instructions}`.
4. Wait on started_event[run_id] with timeout=5 seconds. If timeout: broadcast `{"type": "RUNNER_WARNING", "topic": topic, "run_id": run_id, "reason": "terminal_spawn_timeout", "stage": state}`. Fall back to `invoke_agent()` and return its result.
5. Wait on result_event[run_id] with no timeout.
6. Return stored result dict.
In `_loop()`: replace the `invoke_agent()` call with `_run_stage_via_terminal(...)`.
Abort path: when `_abort_flag` is set and there is an active run_id, broadcast `{"type": "TERMINAL_SIGNAL", "topic": topic, "run_id": run_id, "signal": "term"}` before the existing abort handling.

Architectural rules to observe:
- Read src/pathly_orchestrator/CLAUDE.md if it exists before touching any orchestrator file.
- Do NOT touch any Studio/renderer files in this conversation.
- Do NOT change the public signature of `invoke_agent()` — it must remain usable as a headless fallback.
- The threading.Event storage must be safe for concurrent calls (use a dict on the supervisor module-level or a thread-safe structure).

Verify: `python -m pytest tests/ -q`
After verification passes, update pathly/plans/visible-runner/PROGRESS.md phases 0–3 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `python -m pytest tests/ -q` exits 0. Three new functions/endpoints exist. `_loop()` calls `_run_stage_via_terminal()`.
**Files touched:** `runner.py`, `http_server.py`, `supervisor.py`

---

## Conversation 2: Studio wiring (Phases 4–9)

**Stories delivered:** S1 (terminal tab opens, live output, done marker), S2 (intervention warning), S3 (abort kill, result POST)

**Prompt to paste:**
```
Read pathly/plans/visible-runner/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement visible-runner Conversation 2 (Phases 4–9) from pathly/plans/visible-runner/IMPLEMENTATION_PLAN.md.

Conversation 1 is complete: supervisor.py broadcasts TERMINAL_SPAWN/TERMINAL_SIGNAL SSE, and http_server.py has /runner/terminal/started + /runner/terminal/result endpoints.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/styles/tokens.css` — add --runner-bg, --runner-border tokens (Phase 4)
- `studio/src/renderer/src/types/terminal.ts` — add runnerOwned?: boolean to TerminalTab (Phase 5)
- `studio/src/renderer/src/store/runnerStore.ts` — add stageLog, activeRunnerTabId, logCardExpanded, 4 new actions (Phase 6)
- `studio/src/renderer/src/components/HQ/useHQ.tsx` — handle TERMINAL_SPAWN + TERMINAL_SIGNAL SSE events (Phase 7)
- `studio/src/main/ipc/terminal.ts` — buffer PTY output; POST result on exit (Phase 8)
- `studio/src/renderer/src/components/Terminal/PaneTabBar.tsx` + `.module.css` — runner tab styling (Phase 9)

Phase 4 — CSS tokens:
In tokens.css, add `--runner-bg: rgba(45, 212, 191, 0.10)` and `--runner-border: rgba(45, 212, 191, 0.35)` to the `:root` block (dark theme). Add `--runner-bg: rgba(15, 118, 110, 0.10)` and `--runner-border: rgba(15, 118, 110, 0.35)` to the `[data-theme="light"]` block. If other theme blocks exist (high-contrast, etc.), add appropriate values there too.

Phase 5 — TerminalTab type:
Find the `TerminalTab` type/interface in `studio/src/renderer/src/types/terminal.ts` (or wherever it is defined — read the file first). Add optional field `runnerOwned?: boolean`.

Phase 6 — runnerStore additions:
Add to RunnerState type and store:
- `stageLog: Array<{stage: string; adapter: string | null; tabId: string | null; startedAt: number; endedAt: number | null; exitCode: number | null;}>`  (initialize to [])
- `activeRunnerTabId: string | null`  (initialize to null)
- `logCardExpanded: boolean`  (initialize to false)
- `runStartedAt: number | null`  (initialize to null)
Actions:
- `recordStageStart(stage, adapter, tabId)` — push entry to stageLog, set activeRunnerTabId, set runStartedAt if stageLog was empty
- `recordStageEnd(exitCode)` — update last stageLog entry with endedAt: Date.now() and exitCode
- `setActiveRunnerTabId(tabId)` — set field
- `setLogCardExpanded(expanded)` — set field
- `jumpToLiveTab()` — import useTerminalStore and call openTab(activeRunnerTabId) if set; also call toggle() if terminal pane is not open

Phase 7 — useHQ SSE handlers:
In the SSE event switch in useHQ.tsx, add:
- case 'TERMINAL_SPAWN': parse {run_id, tab_id, label, adapter, cwd, prompt, stage} from event.data.
  1. Call `useTerminalStore.getState().addTab(tab_id, label, 'left', adapter as TerminalKind)` to open tab.
  2. Patch the tab to set runnerOwned: true — read current tabs, find the new tab by id, set runnerOwned=true, call set({ tabs: updatedTabs }). Or add a `setTabRunnerOwned(id)` action to terminalStore.
  3. Call `window.pathly.terminal.spawn(tab_id, cwd, adapter)`.
  4. After a 300ms delay (setTimeout), call `window.pathly.terminal.write(tab_id, prompt + '\n')`.
  5. Call `useRunnerStore.getState().recordStageStart(stage ?? '', adapter, tab_id)`.
  6. POST to `http://127.0.0.1:8765/runner/terminal/started` with body `{topic: activeTopic, run_id, tab_id, pid: 0}`.
- case 'TERMINAL_SIGNAL': parse {signal}. If signal === 'term', call `window.pathly.terminal.kill(useRunnerStore.getState().activeRunnerTabId ?? '')`.
Note: the warn-on-first-click behavior (S2, AC 2.2) is written by terminal.ts into the xterm buffer, not handled here. The renderer only needs to handle the SSE events.

Phase 8 — terminal.ts result POST:
In terminal.ts, add a per-tab output buffer `Map<string, string[]>` called `ptyOutput`. 
In the pty onData handler: append chunk to `ptyOutput.get(tabId) ?? []`. Trim to last 500 entries.
In the terminal:spawn handler: if the tabId starts with 'runner-', store `{run_id: tabId's run_id portion, topic: stored from a module-level map, spawnedAt: Date.now()}` in a `runnerTabMeta: Map<string, RunnerTabMeta>` map.
On PTY exit event for a runner tab:
1. Write the completion banner to xterm (NOT to PTY stdin) via `event.sender.send('terminal:data:' + tabId, banner)`:
   - exitCode === 0: `\r\n\x1b[2m──\x1b[0m \x1b[1;32m[label] DONE\x1b[0m \x1b[2m──────────────────────────────\x1b[0m\r\n`
   - exitCode !== 0: `\r\n\x1b[2m──\x1b[0m \x1b[1;31m[label] ABORTED\x1b[0m \x1b[2m──────────────────────────────\x1b[0m\r\n`
2. Compute `wall_seconds = (Date.now() - spawnedAt) / 1000`.
3. Determine `userInitiated: boolean` — true if exit was triggered by `terminal:kill` from a TERMINAL_SIGNAL handler (track via `ptyKilledByRunner: Set<string>`).
4. POST to `http://127.0.0.1:8765/runner/terminal/result` with `{topic, run_id, exit_code: exitCode, stdout_tail: ptyOutputBuf.get(tabId) ?? '', wall_seconds, user_initiated: userInitiated}`. Python-side `runner.parse_result()` handles JSON extraction — do NOT attempt JSON parsing in terminal.ts. Use `fetch()` — fire and forget with one retry.
5. Clean up: delete entries from `ptyOutputBuf`, `ptyKilledByRunner`, and `runnerTabMeta`.
Note: a first-click warning (S2, AC 2.2) would write ANSI yellow text to xterm when a terminal:write arrives for a runner tab — this is a bonus if within scope, but not required for typecheck to pass.

Phase 9 — PaneTabBar runner tab styling:
Read PaneTabBar.tsx. The terminal uses one shared CSS file — `Terminal.module.css` — there is NO separate `PaneTabBar.module.css`. In the tab render loop apply classes: `cn(styles.tab, tab.runnerOwned && styles.tabRunner, isActive ? styles.tabActive : styles.tabInactive)`. In `Terminal.module.css`, add after the existing `.tabInactive` block:
```css
.tabRunner {
  border-left: 2px solid var(--runtime);  /* tab container — different element from .iconBtnClaude border-left */
  background: var(--runner-bg);
  opacity: 1 !important;  /* override .tabInactive opacity:0.6 so runner tabs stay fully visible when not focused */
  transition: background 120ms ease-out;
}
.tabRunner:hover {
  background: var(--runner-bg-hover);
}
```
No inline styles. `.tabActive` border-bottom and `.tabRunner` border-left coexist on the same element — both render correctly.

Do NOT touch RunnerLogCard, StageStatusStrip [live] button, or DECISION_MENU toast — those are in Conversation 3.

Architectural rules:
- Read studio/CLAUDE.md before touching any Studio file.
- No inline styles. All styling via CSS modules using var(--token) values.
- All buttons must have type="button".
- Component files ≤ 150 lines. Extract sub-components if needed.

Verify: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json && node_modules/.bin/tsc --noEmit -p studio/tsconfig.node.json`
After verification passes, update pathly/plans/visible-runner/PROGRESS.md phases 4–9 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Both typecheck commands exit 0. TERMINAL_SPAWN opens a teal-bordered tab; PTY exit POSTs result to runner.
**Files touched:** `tokens.css`, `terminal.ts`, `types/terminal.ts`, `runnerStore.ts`, `useHQ.tsx`, `PaneTabBar.tsx`, `Terminal.module.css`

---

## Conversation 3: RunnerLogCard + polish (Phases 10–13)

**Stories delivered:** S4 (RunnerLogCard), S5 (live jump button), S6 (decision toast + auto-expand)

**Prompt to paste:**
```
Read pathly/plans/visible-runner/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement visible-runner Conversation 3 (Phases 10–13) from pathly/plans/visible-runner/IMPLEMENTATION_PLAN.md.

Conversations 1 and 2 are complete: supervisor broadcasts TERMINAL_SPAWN/SIGNAL, Studio opens terminal tabs, PTY exit POSTs results, runnerStore has stageLog + logCardExpanded + jumpToLiveTab.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/components/HQ/RunnerLogCard/RunnerLogCard.tsx` — new component (Phase 10)
- `studio/src/renderer/src/components/HQ/RunnerLogCard/RunnerLogCard.module.css` — new CSS module (Phase 10)
- `studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.tsx` — add [live ↗] button (Phase 11)
- `studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.module.css` — add .liveBtn style (Phase 11)
- `studio/src/renderer/src/components/HQ/useHQ.tsx` — DECISION_MENU auto-expand + toast (Phase 12)
- `studio/src/renderer/src/components/HQ/HQPanel.tsx` — mount RunnerLogCard in panel layout (Phase 13)

Phase 10 — RunnerLogCard:
Create the folder and both files. The component:
- Reads stageLog, status, cost, logCardExpanded, runStartedAt, activeRunnerTabId from useRunnerStore.
- Renders nothing when stageLog.length === 0.
- Has a collapsed view and an expanded view, toggled by the [▾]/[▴] button (type="button").
  - Collapsed: pulsing status dot (reuse runnerStore status → dotRunning/dotIdle class) + `N stages done — [currentStageName]` text + [▾] toggle + [Jump ↗] button.
  - Expanded: table with columns (stage name, adapter, timestamp HH:MM:SS, duration Xs, status badge) + footer (run start time, total stages, cumulative $cost).
- [Jump ↗] button calls useRunnerStore.getState().jumpToLiveTab(). Label: "live ↗", type="button".
- Card is sticky during run: add `data-running={status === 'running'}` attribute; handle sticky vs static in CSS using `[data-running="true"]`.
- Extract RunnerLogRow as a separate sub-component within the same folder if the file would exceed 150 lines.
- No inline styles. All values from CSS tokens (--bg-surface0, --border, --runner-border, --runtime, --text-primary, --text-secondary, --text-muted, --green, --red, --accent).

CSS module (RunnerLogCard.module.css) must include:
- .card — border-left: 3px solid var(--runner-border), background: var(--bg-surface0), a subtle border, border-radius, padding
- .cardRunning — position: sticky, bottom: 0, z-index appropriate value
- .headerRow — flex, align-items: center, gap, padding
- .stageName — font-weight: 500, color: var(--text-primary)
- .dot — reuse pattern from StageStatusStrip (7px circle)
- .table — width: 100%, border-collapse, font-size: 11px
- .footer — padding, color: var(--text-muted), font-size: 10px
- .jumpBtn — styled like a pill: background: var(--runner-bg), border: 1px solid var(--runner-border), color: var(--runtime), border-radius: 3px, font-size: 10px

Phase 11 — StageStatusStrip live button:
Read StageStatusStrip.tsx first. Read the existing store fields it uses.
When status === 'running' and activeRunnerTabId is set:
- Render: `<button type="button" className={styles.liveBtn} onClick={() => useRunnerStore.getState().jumpToLiveTab()} aria-label="Jump to live terminal">live ↗</button>`
- Position it after the adapter chip and before the cost display.
In StageStatusStrip.module.css, add:
```css
.liveBtn {
  background: var(--runner-bg);
  border: 1px solid var(--runner-border);
  color: var(--runtime);
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  cursor: pointer;
}
```

Phase 12 — DECISION_MENU toast:
In useHQ.tsx, find the existing DECISION_MENU SSE event case (or add it).
Add: `useRunnerStore.getState().setLogCardExpanded(true)`.
Add: `useToastStore.getState().push('Runner is waiting for your decision', 'info')`.
Import useToastStore from '../../../store/toastStore' if not already imported.

Phase 13 — Wire RunnerLogCard:
Find the HQ panel component file (read the HQ directory to identify it). Import RunnerLogCard and add it to the panel layout as a sibling of the message list, above the input bar. The component itself handles its own empty-state (renders nothing when stageLog is empty), so no conditional wrapper is needed here.

Architectural rules:
- Read studio/CLAUDE.md before touching any Studio file.
- No inline styles. All styling via CSS modules.
- All buttons have type="button".
- Component files ≤ 150 lines. Extract sub-components if needed.
- RunnerLogCard must follow the folder rule: RunnerLogCard/ folder with .tsx + .module.css.

Verify: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`
After verification passes, update pathly/plans/visible-runner/PROGRESS.md phases 10–13 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Typecheck exits 0. RunnerLogCard renders. [live ↗] button appears in StageStatusStrip. DECISION_MENU shows toast and expands card.
**Files touched:** `RunnerLogCard/RunnerLogCard.tsx`, `RunnerLogCard/RunnerLogCard.module.css`, `StageStatusStrip.tsx`, `StageStatusStrip.module.css`, `useHQ.tsx`, `HQPanel.tsx`
