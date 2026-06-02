# visible-runner — Implementation Plan

## Overview

When the autonomous runner starts a pipeline stage, instead of spawning the CLI agent headlessly, it broadcasts a `TERMINAL_SPAWN` SSE event. The Studio receives this event, opens a named terminal tab in PaneTabBar, and runs the agent in xterm so the user sees live output. When the PTY exits, Studio POSTs the result back to the supervisor. A collapsible RunnerLogCard in HQ chat shows stage history.

## Layer Architecture

```
Python supervisor                    Electron main                 React renderer
  supervisor.py                        terminal.ts                  useHQ.tsx
       │                                    │                           │
       │── SSE: TERMINAL_SPAWN ─────────────────────────────────────► │
       │                                    │ ◄── window.pathly ──────  │
       │                                    │     .terminal.spawn()     │
       │   PTY runs agent live              │                           │
       │ ◄── POST /terminal/started ────────│                          │
       │                                    │  agent output → xterm    │
       │   (waits on threading.Event)       │                           │
       │ ◄── POST /terminal/result ─────────│ (on PTY exit)            │
       │   resumes _loop                    │                           │
       │── SSE: TERMINAL_SIGNAL ────────────────────────────────────► │
       │   (on abort)                       │ terminal.kill(tabId) ──► │
```

## Prerequisites

- `python -m pytest tests/ -q` passes before Conv 1 begins (pre-flight baseline).
- `src/pathly_orchestrator/supervisor.py`, `http_server.py`, and `runner.py` exist at their expected paths.
- `studio/src/main/ipc/terminal.ts` exists and exports PTY handlers.

## Key Decisions

1. **Option E SSE relay**: Supervisor ↔ Studio communicate via existing SSE broadcast channel + two new HTTP callback endpoints. No second HTTP server, no file polling.
2. **Headless fallback**: 5-second timeout after TERMINAL_SPAWN; if no `/terminal/started`, fall back to `invoke_agent()`. Pipeline never blocks on UI.
3. **Result extraction**: Studio buffers all PTY output via `appendScrollback`; on exit, reverse-scans for last valid JSON line and POSTs it.
4. **Abort via SSE**: Supervisor never holds the PTY PID. It broadcasts `TERMINAL_SIGNAL`; Studio owns the kill.
5. **Pause between stages only**: `_pause_flag` is checked at stage loop top as today. No mid-stage PTY pause.

## Event and Endpoint Contracts

### New SSE events (supervisor → Studio)

```json
{ "type": "TERMINAL_SPAWN", "topic": "<str>", "run_id": "<uuid>",
  "tab_id": "<str>", "label": "<str>", "adapter": "<str>",
  "argv": ["claude", "--output-format=json", ...], "cwd": "<str>",
  "prompt": "<str>" }

{ "type": "TERMINAL_SIGNAL", "topic": "<str>", "run_id": "<str>", "signal": "term" }

{ "type": "RUNNER_WARNING", "topic": "<str>", "run_id": "<str>",
  "reason": "terminal_spawn_timeout", "stage": "<str>" }
```

### New HTTP endpoints (Studio → supervisor)

```
POST /runner/terminal/started
  Body: { "topic": "<str>", "run_id": "<str>", "tab_id": "<str>", "pid": <int> }
  Response: { "ok": true }

POST /runner/terminal/result
  Body: { "topic": "<str>", "run_id": "<str>", "exit_code": <int>,
          "final_json": { ... } | null, "wall_seconds": <float> }
  Response: { "ok": true }
```

---

## Phase 0: Pre-flight   ← Conversation: 1

**File:** `src/pathly_orchestrator/supervisor.py`
**Done when:** `python -m pytest tests/ -q` exits 0 AND `grep -rn "invoke_agent\|_loop\|broadcast_sse" src/pathly_orchestrator/supervisor.py` returns matches at expected locations.
**Details:** Run the test suite and record any pre-existing failures as a baseline. Note exact paths for `supervisor.py`, `http_server.py`, `runner.py`. Do not start Phase 1 if any test is already failing due to new code.

---

## Phase 1: Extract argv builder in runner.py   ← Conversation: 1

**File:** `src/pathly_orchestrator/runner.py`
**Done when:** `grep -n "def resolve_argv\|def invoke_agent" src/pathly_orchestrator/runner.py` shows both functions; `invoke_agent` calls `resolve_argv` internally.
**Depends on:** Phase 0 (clean baseline)
**Enables:** Phase 2 can import `resolve_argv` to build the `argv` list for `TERMINAL_SPAWN`
**Details:**
- Extract the argv construction from `invoke_agent()` into a new standalone function `resolve_argv(adapter, prompt, model, session=None, autonomy=None) → list[str]`.
- `invoke_agent()` calls `resolve_argv()` internally — no behavior change on the headless path.
- The function must include the `--output-format=json` flag (or adapter equivalent) so PTY and headless modes share the same argv.
**Verify:** `python -m pytest tests/ -q`

---

## Phase 2: New HTTP callback endpoints in http_server.py   ← Conversation: 1

**File:** `src/pathly_orchestrator/http_server.py`
**Done when:** `curl -s -X POST http://127.0.0.1:8765/runner/terminal/started -H 'Content-Type: application/json' -d '{"topic":"test","run_id":"x","tab_id":"t1","pid":0}'` returns `{"ok":true}`.
**Depends on:** Phase 0
**Enables:** Phase 3 can wait for the callback to set the threading.Event
**Details:**
- Add `POST /runner/terminal/started`: looks up active `RunnerState` by topic, sets a `threading.Event` keyed by `run_id` to signal "Studio is connected". Stores `(run_id, tab_id, pid)` in a dict on RunnerState.
- Add `POST /runner/terminal/result`: looks up RunnerState by topic + run_id, stores `exit_code` + `final_json` on a result dict keyed by run_id, sets the result Event to unblock `_run_stage_via_terminal`.
- Both endpoints return `{"ok": true}` on success, `{"error": "..."}` on unknown topic/run_id.
- Register routes using the existing handler pattern in http_server.py (no framework change).
**Verify:** `python -m pytest tests/ -q`

---

## Phase 3: Refactor _loop to use _run_stage_via_terminal   ← Conversation: 1

**File:** `src/pathly_orchestrator/supervisor.py`
**Done when:** `grep -n "_run_stage_via_terminal\|TERMINAL_SPAWN\|TERMINAL_SIGNAL" src/pathly_orchestrator/supervisor.py` returns matches; `python -m pytest tests/ -q` passes.
**Depends on:** Phase 1, Phase 2
**Enables:** Conv 2 — Studio can receive events and respond
**Details:**
- Add method `_run_stage_via_terminal(state, instructions, adapter, model, run_id) → dict`:
  1. Build `argv` via `resolve_argv(adapter, instructions, model, ...)`.
  2. Generate `tab_id = f"runner-{run_id[:8]}"`, `label = f"{adapter} — {state}"`.
  3. Broadcast `TERMINAL_SPAWN` SSE event (all fields per contract above).
  4. Wait on `started_event[run_id]` with `timeout=5`. If timeout: broadcast `RUNNER_WARNING`, call `invoke_agent()` as fallback, return its result dict.
  5. Wait on `result_event[run_id]` with no timeout (agent runs until done or abort).
  6. Return stored result dict `{cost_usd, session_id, tokens, exit_code}`.
- In `_loop()`: replace the `invoke_agent()` call with `_run_stage_via_terminal(...)`.
- Abort path: when `_abort_flag` is set and a run_id is active, broadcast `TERMINAL_SIGNAL {signal:"term"}` then set `_abort_flag` as before.
- Add `RUNNER_WARNING` to the existing broadcast enum/list.
**Verify:** `python -m pytest tests/ -q`

---

## Phase 4: CSS tokens   ← Conversation: 2

**File:** `studio/src/renderer/src/styles/tokens.css`
**Done when:** `grep -n "runner-bg\|runner-border" studio/src/renderer/src/styles/tokens.css` returns entries in both dark (`:root`) and light (`[data-theme="light"]`) theme blocks.
**Details:**
- Add in `:root` (dark theme): `--runner-bg: rgba(45, 212, 191, 0.10);` and `--runner-border: rgba(45, 212, 191, 0.35);`
- Add in `[data-theme="light"]`: `--runner-bg: rgba(15, 118, 110, 0.10);` and `--runner-border: rgba(15, 118, 110, 0.35);`
- Use `var(--runtime)` directly for `color` — do not add a `--runner-color` token (it already exists as `--runtime`).
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Phase 5: Add runnerOwned field to TerminalTab type   ← Conversation: 2

**File:** `studio/src/renderer/src/types/terminal.ts`
**Done when:** `grep -n "runnerOwned" studio/src/renderer/src/types/terminal.ts` returns the field definition.
**Details:**
- Add optional field `runnerOwned?: boolean` to the `TerminalTab` interface/type.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Phase 6: runnerStore additions   ← Conversation: 2

**File:** `studio/src/renderer/src/store/runnerStore.ts`
**Done when:** `grep -n "stageLog\|activeRunnerTabId\|logCardExpanded" studio/src/renderer/src/store/runnerStore.ts` returns 3+ matches.
**Depends on:** Phase 5
**Details:**
Add to RunnerState:
```typescript
stageLog: Array<{
  stage: string; adapter: string | null; tabId: string | null;
  startedAt: number; endedAt: number | null; exitCode: number | null;
}>
activeRunnerTabId: string | null
logCardExpanded: boolean
runStartedAt: number | null
```
Add actions:
- `recordStageStart(stage: string, adapter: string | null, tabId: string | null)` — pushes entry with `startedAt: Date.now()`, sets `activeRunnerTabId`, sets `runStartedAt` if `stageLog` was empty.
- `recordStageEnd(exitCode: number | null)` — updates last entry with `endedAt: Date.now()`, `exitCode`.
- `setActiveRunnerTabId(tabId: string | null)` — sets field.
- `setLogCardExpanded(expanded: boolean)` — sets field.
- `jumpToLiveTab()` — calls `useTerminalStore.getState().openTab(activeRunnerTabId)` if activeRunnerTabId is set.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Phase 7: useHQ — handle TERMINAL_SPAWN and TERMINAL_SIGNAL   ← Conversation: 2

**File:** `studio/src/renderer/src/components/HQ/useHQ.tsx`
**Done when:** `grep -n "TERMINAL_SPAWN\|TERMINAL_SIGNAL" studio/src/renderer/src/components/HQ/useHQ.tsx` returns 2+ matches.
**Depends on:** Phase 6
**Details:**
In the SSE event switch:
- `TERMINAL_SPAWN`: parse `{run_id, tab_id, label, adapter, cwd, prompt}` from `event.data`.
  1. Call `useTerminalStore.getState().addTab(tab_id, label, 'left', adapter as TerminalKind, undefined, undefined)` — tab opens as active.
  2. Mark tab as runner-owned: call `useTerminalStore.getState().setRunnerOwned(tab_id, true)` (new action, or patch tabs array).
     **Alternative if addTab API can't take runnerOwned**: patch tabs after add by reading `tabs`, finding the new tab, setting `runnerOwned: true`, and writing back via `set({ tabs: ... })` — builder to choose cleanest approach.
  3. Call `window.pathly.terminal.spawn(tab_id, cwd, adapter)` to start the PTY (no await needed — it's fire-and-forget for opening).
  4. After a 200ms delay (allow PTY to start), call `window.pathly.terminal.write(tab_id, prompt + '\n')` to send the prompt to the agent.
  5. Call `runnerStore.recordStageStart(stage from SSE data, adapter, tab_id)`.
  6. Call `runnerStore.setActiveRunnerTabId(tab_id)`.
  7. POST `{ topic, run_id, tab_id, pid: 0 }` to `http://127.0.0.1:8765/runner/terminal/started`. (pid=0 is acceptable; supervisor does not need the pid for signaling.)
- `TERMINAL_SIGNAL`: parse `{signal}`. If signal is `"term"`, call `window.pathly.terminal.kill(runnerStore.activeRunnerTabId)`.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Phase 8: terminal.ts — buffer + result POST on PTY exit   ← Conversation: 2

**File:** `studio/src/main/ipc/terminal.ts`
**Done when:** `grep -n "terminal/result\|lastJsonLine" studio/src/main/ipc/terminal.ts` returns matches in the exit handler.
**Depends on:** Phase 7
**Details:**
- Add a `ptyCombinedOutput: Map<string, string[]>` registry alongside `activePtys`.
- In the PTY `onData` handler: append each chunk to `ptyCombinedOutput.get(tabId)` (cap at last 500 lines to bound memory).
- On PTY `exit(exitCode)`:
  1. Walk `ptyCombinedOutput.get(tabId)` in reverse to find the last line that parses as valid JSON. Store as `finalJson` (or `null`).
  2. Write `\r\n\x1b[32m── [tab label] DONE  [duration]s ──\x1b[0m\r\n` directly to the xterm via `event.sender.send('terminal:data:' + tabId, ...)` if exit code is 0. Write in red with "aborted" if exit code is non-zero.
  3. POST to `http://127.0.0.1:8765/runner/terminal/result` with `{ topic: [from RunnerState or stored on spawn], run_id, exit_code: exitCode, final_json: finalJson, wall_seconds }`.
  4. Clear `ptyCombinedOutput` entry for this tabId.
- Store `{run_id, topic, spawnedAt}` per tabId when `terminal:spawn` fires for a runner tab (detect by checking if `tab_id` starts with `"runner-"`).
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.node.json`

---

## Phase 9: PaneTabBar runner tab styling   ← Conversation: 2

**File:** `studio/src/renderer/src/components/Terminal/PaneTabBar.tsx` and its `.module.css`
**Done when:** `grep -n "runnerOwned\|runnerTab" studio/src/renderer/src/components/Terminal/PaneTabBar.tsx` returns matches; `.runnerTab { border-left: 2px solid var(--runtime); }` exists in the CSS module.
**Depends on:** Phase 5
**Details:**
- In PaneTabBar render: when `tab.runnerOwned === true`, apply `styles.runnerTab` CSS class to the tab element.
- `.runnerTab` in `PaneTabBar.module.css`:
  ```css
  border-left: 2px solid var(--runtime);
  background: var(--runner-bg);
  ```
- `aria-label` for runner tabs: `"Runner: [label], [status]"`.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Phase 10: RunnerLogCard component   ← Conversation: 3

**File:** `studio/src/renderer/src/components/HQ/RunnerLogCard/RunnerLogCard.tsx` + `RunnerLogCard.module.css`
**Done when:** `ls studio/src/renderer/src/components/HQ/RunnerLogCard/` shows both files; `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` passes.
**Depends on:** Phase 6 (runnerStore stageLog)
**Details:**
- New component `RunnerLogCard.tsx` (≤ 150 lines; extract `RunnerLogRow` child if needed).
- Reads from `useRunnerStore`: `stageLog`, `status`, `cost`, `logCardExpanded`, `runStartedAt`, `activeRunnerTabId`.
- Layout: flat card with `border-left: 3px solid var(--runner-border)`, `background: var(--bg-surface0)`.
- Collapsed: status dot (reuse `.dotRunning` class) + `N stages done — [current stage]` + `[▾]` toggle + `[Jump ↗]` button.
- Expanded: table of stages (columns: stage name, adapter, timestamp, duration, status dot); footer row showing start time + total stages + `$cost`.
- `[▾]` / `[▴]` toggle calls `runnerStore.setLogCardExpanded(!logCardExpanded)`.
- `[Jump ↗]` calls `runnerStore.jumpToLiveTab()`.
- The card renders when `stageLog.length > 0`. Sticky (CSS `position: sticky; bottom: 0`) during run; `position: static` when `status === 'idle'`.
- No inline styles. All values from CSS tokens. All buttons have `type="button"`.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Phase 11: StageStatusStrip — live button   ← Conversation: 3

**File:** `studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.tsx` + `StageStatusStrip.module.css`
**Done when:** `grep -n "liveBtn\|jumpToLiveTab\|live" studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.tsx` returns matches; button renders only when `status === 'running'`.
**Depends on:** Phase 6 (jumpToLiveTab action), Phase 10 (pattern established)
**Details:**
- Import `useRunnerStore` (already imported) and read `activeRunnerTabId`.
- When `status === 'running'` and `activeRunnerTabId` is set, render a `<button type="button" className={styles.liveBtn} onClick={jumpToLiveTab}>live ↗</button>` after the adapter chip.
- `.liveBtn` in `StageStatusStrip.module.css`:
  ```css
  background: var(--runner-bg);
  border: 1px solid var(--runner-border);
  color: var(--runtime);
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  cursor: pointer;
  ```
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Phase 12: DECISION_MENU auto-expand + toast   ← Conversation: 3

**File:** `studio/src/renderer/src/components/HQ/useHQ.tsx`
**Done when:** `grep -n "DECISION_MENU\|logCardExpanded\|waiting for your decision" studio/src/renderer/src/components/HQ/useHQ.tsx` returns matches.
**Depends on:** Phase 6 (setLogCardExpanded), Phase 10 (RunnerLogCard reads the flag)
**Details:**
- In the SSE switch, add/update case for `DECISION_MENU`:
  - Call `useRunnerStore.getState().setLogCardExpanded(true)`.
  - Call `useToastStore.getState().push('Runner is waiting for your decision', 'info')`.
- Import `useToastStore` from `'../../../store/toastStore'` if not already imported.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Phase 13: Wire RunnerLogCard into HQ panel   ← Conversation: 3

**File:** `studio/src/renderer/src/components/HQ/HQPanel.tsx` (or whichever file contains the HQ chat column layout)
**Done when:** `grep -n "RunnerLogCard" studio/src/renderer/src/components/HQ/HQPanel.tsx` returns a match.
**Depends on:** Phase 10
**Details:**
- Import `RunnerLogCard` and render it as a `flex-shrink: 0` sibling of the message list and above the input bar.
- No inline styles — placement is via the existing flex column layout of HQPanel.
- The card's own sticky positioning handles behavior during an active run.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`
