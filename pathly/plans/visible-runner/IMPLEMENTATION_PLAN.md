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
- Confirm `node_modules/node-pty` is listed in `asarUnpack` in `electron-builder.yml` (required for `winpty.dll` to resolve on Windows at runtime).
- **SSE reliability (pre-flight):** The Python `/events/runner` SSE endpoint should emit `id:` fields on every event (e.g. `id: {run_id}-{seq}`) so the `EventSource` client sends `Last-Event-ID` on reconnect and missed events can be replayed. Add 15-second keep-alive comment lines (`:\n\n`) to prevent OS-level TCP idle timeouts on long agent runs.

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
  "prompt": "<str>", "stage": "<str>" }

{ "type": "TERMINAL_SIGNAL", "topic": "<str>", "run_id": "<str>",
  "signal": "term", "tab_id": "<str>" }

{ "type": "TERMINAL_CLAIMED", "topic": "<str>", "run_id": "<str>",
  "tab_id": "<str>", "claimed_by_window": "<uuid>" }

{ "type": "RUNNER_WARNING", "topic": "<str>", "run_id": "<str>",
  "reason": "terminal_spawn_timeout", "stage": "<str>" }
```

### New HTTP endpoints (Studio → supervisor)

```
POST /runner/terminal/started
  Body: { "topic": "<str>", "run_id": "<str>", "tab_id": "<str>", "pid": <int>,
          "studio_window_id": "<uuid>" }
  Response: { "ok": true }
  Error:    { "error": "already_headless", "code": 409 }  ← if fallback already fired

POST /runner/terminal/result
  Body: { "topic": "<str>", "run_id": "<str>", "exit_code": <int>,
          "stdout_tail": "<str>", "wall_seconds": <float>,
          "user_initiated": <bool> }
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
- Extract the output parsing logic from `invoke_agent()` into a new standalone function `parse_result(adapter: str, raw_output: str) → dict[str, Any]` that locates the result JSON and returns `{"cost_usd": ..., "session_id": ...}`. For PTY-sourced output, the caller strips ANSI before passing; for headless subprocess output, raw stdout is already clean.
- `invoke_agent()` calls both `resolve_argv()` and `parse_result()` internally — no behavior change on the headless path.
- For the claude adapter, use `--print --output-format=json` (single clean JSON object to stdout) rather than `--output-format=stream-json` (NDJSON stream) so `parse_result` can reliably find the result without scanning multiple lines.
- The function must include the `--output-format=json` flag (or adapter equivalent) so PTY and headless modes share the same argv.
**Verify:** `python -m pytest tests/ -q`

---

## Phase 2: New HTTP callback endpoints in http_server.py   ← Conversation: 1

**File:** `src/pathly_orchestrator/http_server.py`
**Done when:** `curl -s -X POST http://127.0.0.1:8765/runner/terminal/started -H 'Content-Type: application/json' -d '{"topic":"test","run_id":"x","tab_id":"t1","pid":0}'` returns `{"ok":true}`.
**Depends on:** Phase 0
**Enables:** Phase 3 can wait for the callback to set the threading.Event
**Details:**
- Add `POST /runner/terminal/started`: looks up active `RunnerState` by topic, checks `RunnerState.terminal_mode` — if already `"headless"` return `{"error": "already_headless", "code": 409}`. Otherwise sets the `threading.Event` keyed by `run_id` to signal "Studio is connected". Stores `(run_id, tab_id, pid, studio_window_id)` in a dict on RunnerState. Broadcasts `TERMINAL_CLAIMED {run_id, tab_id, claimed_by_window: studio_window_id}` so competing windows close their orphan PTYs.
- Add `POST /runner/terminal/result`: looks up RunnerState by topic + run_id, stores `exit_code`, `stdout_tail`, `user_initiated`, and `wall_seconds` on a result dict keyed by run_id, sets the result Event to unblock `_run_stage_via_terminal`. Supervisor calls `runner.parse_result(adapter, stdout_tail)` to extract cost/session — the renderer never parses agent output.
- **Thread safety:** `_terminal_started_events`, `_terminal_result_events`, and `_terminal_result_data` are module-level dicts in `supervisor.py`. All reads and writes from Flask request threads must be performed under `supervisor._lock` to prevent dict-resize races.
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
- `TERMINAL_SPAWN` broadcast is gated on env var `PATHLY_TERMINAL_MODE=1`. If unset, `_run_stage_via_terminal` skips the broadcast entirely and falls through directly to `invoke_agent()`. This prevents a 5-second dead-wait per stage between Conv 1 merge and Conv 2 merge in production.
- Add method `_run_stage_via_terminal(state, instructions, adapter, model, run_id) → dict`:
  1. Build `argv` via `resolve_argv(adapter, instructions, model, ...)`.
  2. Generate `tab_id = f"runner-{run_id[:8]}"`, `label = f"{adapter} — {state}"`.
  3. **Broadcast ordering:** call `_set_status(state=state)` first (emits `STAGE_CHANGE` so renderer initialises the stageLog entry before the terminal arrives), then immediately broadcast `TERMINAL_SPAWN`.
  4. Under `supervisor._lock`: insert new `threading.Event()` into `_terminal_started_events[run_id]` and `_terminal_result_events[run_id]`. Set `RunnerState.terminal_mode = "pending"`.
  5. Wait on `_terminal_started_events[run_id]` with `timeout=5`. If timeout: under `_lock` pop both events, set `RunnerState.terminal_mode = "headless"`, broadcast `RUNNER_WARNING`, call `invoke_agent()` as fallback, return its result dict.
  6. Wait on `_terminal_result_events[run_id]` with no timeout (agent runs until done or abort).
  7. Call `runner.parse_result(adapter, result_data[run_id]["stdout_tail"])` to extract `cost_usd`, `session_id`. Return merged dict `{cost_usd, session_id, exit_code, wall_seconds}`.
- In `_loop()`: replace the `invoke_agent()` call with `_run_stage_via_terminal(...)`.
- Abort path: when `_abort_flag` is set and a run_id is active, broadcast `TERMINAL_SIGNAL {signal:"term", tab_id}`. The renderer kills the PTY; PTY exit triggers a POST to `/runner/terminal/result` with `user_initiated: true`. Supervisor treats `user_initiated: true` as a clean abort (not stage failure) and does not increment feedback counter.
- Add `RUNNER_WARNING` and `TERMINAL_CLAIMED` to the existing broadcast enum/list.
**Verify:** `python -m pytest tests/ -q`

---

## Phase 4: CSS tokens   ← Conversation: 2

**File:** `studio/src/renderer/src/styles/tokens.css`
**Done when:** `grep -n "runner-bg\|runner-border" studio/src/renderer/src/styles/tokens.css` returns entries in both dark (`:root`) and light (`[data-theme="light"]`) theme blocks.
**Details:**
- Add in `:root` (dark): `--runner-bg: rgba(45, 212, 191, 0.08);`, `--runner-border: rgba(45, 212, 191, 0.30);`, `--runner-bg-hover: rgba(45, 212, 191, 0.14);`
- Add in `[data-theme="light"]`: `--runner-bg: rgba(15, 118, 110, 0.08);`, `--runner-border: rgba(15, 118, 110, 0.30);`, `--runner-bg-hover: rgba(15, 118, 110, 0.14);`
- Add matching entries to all remaining theme blocks (nord, mocha, solarized, dracula, rosé-pine, solarized-light, latte, paper, rosé-pine-dawn) using the same 8% / 30% / 14% opacity ratios applied to each theme's `--runtime` hex value. CSS does not support `rgba(var(--runtime), 0.08)` natively, so per-theme explicit values are required.
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
  mode: 'terminal' | 'headless' | null;
  startedAt: number; endedAt: number | null; exitCode: number | null;
}>
activeRunnerTabId: string | null
logCardExpanded: boolean
runStartedAt: number | null
```
Add actions:
- `recordStageStart(stage: string, adapter: string | null, tabId: string | null)` — pushes entry with `startedAt: Date.now()`, `mode: null`, sets `activeRunnerTabId`, sets `runStartedAt` if `stageLog` was empty. **Ownership note:** this action is called by the existing `STAGE_CHANGE` SSE handler (Phase 7 update), not by `TERMINAL_SPAWN`. Every stage gets an entry; `TERMINAL_SPAWN` later attaches `tabId` and sets `mode: 'terminal'`.
- `attachTerminalToStage(tabId: string, mode: 'terminal' | 'headless')` — updates last stageLog entry's `tabId` and `mode`. Called by the `TERMINAL_SPAWN` handler. If `RUNNER_WARNING` arrives instead, caller passes `mode: 'headless'`.
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
**Note on SSE ordering:** Supervisor always broadcasts `STAGE_CHANGE` before `TERMINAL_SPAWN` for the same stage (Phase 3). The `STAGE_CHANGE` handler must call `recordStageStart(stage, adapter, null)` to initialise the stageLog entry before `TERMINAL_SPAWN` arrives. Update the existing `STAGE_CHANGE` case to add this call.

In the SSE event switch:
- `STAGE_CHANGE`: existing handler — add call to `runnerStore.recordStageStart(stage, adapter, null)` here (previously missing).
- `TERMINAL_SPAWN`: parse `{run_id, tab_id, label, adapter, cwd, prompt, stage}` from `event.data`.
  1. Call `useTerminalStore.getState().addTab(tab_id, label, 'left', adapter as TerminalKind, undefined, undefined)` — tab opens as active.
  2. Mark tab as runner-owned: call `useTerminalStore.getState().setRunnerOwned(tab_id, true)` (new action, or patch tabs array).
     **Alternative if addTab API can't take runnerOwned**: patch tabs after add by reading `tabs`, finding the new tab, setting `runnerOwned: true`, and writing back via `set({ tabs: ... })` — builder to choose cleanest approach.
  3. Call `window.pathly.terminal.spawn(tab_id, cwd, adapter)` to start the PTY (no await needed — it's fire-and-forget for opening).
  4. After a 200ms delay (allow PTY to start), call `window.pathly.terminal.write(tab_id, prompt + '\n')` to send the prompt to the agent.
  5. Call `runnerStore.attachTerminalToStage(tab_id, 'terminal')` to attach tabId to the stageLog entry created by STAGE_CHANGE.
  6. Call `runnerStore.setActiveRunnerTabId(tab_id)`.
  7. Generate a `studio_window_id` UUID once at Studio startup (store in a module-level constant). POST `{ topic, run_id, tab_id, pid: 0, studio_window_id }` to `http://127.0.0.1:8765/runner/terminal/started`. Handle 409 response: close the just-opened tab via `window.pathly.terminal.kill(tab_id)`.
- `TERMINAL_CLAIMED`: parse `{claimed_by_window}`. If `claimed_by_window !== studio_window_id`, this window lost the race — call `window.pathly.terminal.kill(tab_id)` to close the orphan PTY.
- `RUNNER_WARNING {reason: "terminal_spawn_timeout"}`: call `runnerStore.attachTerminalToStage(null, 'headless')` to record that this stage ran headless.
- `TERMINAL_SIGNAL`: parse `{signal, tab_id}`. If signal is `"term"`, call `window.pathly.terminal.kill(tab_id)`.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Phase 8: terminal.ts — buffer + result POST on PTY exit   ← Conversation: 2

**File:** `studio/src/main/ipc/terminal.ts`
**Done when:** `grep -n "terminal/result\|stdout_tail\|ptyOutputBuf" studio/src/main/ipc/terminal.ts` returns matches in the exit handler.
**Depends on:** Phase 7
**Details:**

**Output buffering (flow-controlled):**
- Add `ptyOutputBuf: Map<string, string>` alongside `activePtys`. Stores raw concatenated PTY output per tabId.
- Implement high/low watermark flow control on the PTY `onData` handler: accumulate bytes, call `pty.pause()` when pending > 100 KB (HIGH), resume inside the `term.write(chunk, callback)` callback only when pending drops below 10 KB (LOW). This prevents xterm.js buffer overflow (50 MB ceiling) on verbose AI CLI output.
- Cap `ptyOutputBuf` at the last 64 KB per tabId (slice on each append) to bound memory.

**FitAddon guard:**
- When a runner tab becomes active (tab-switch event), guard `fitAddon.fit()` with a non-zero container dimension check before calling. Never call `fit()` while the container is `display: none` or has `height: 0` (xterm.js issue #3029 — throws "only accepts integers").

**On PTY exit:**
  1. Compute `userInitiated: boolean` — true if the exit was triggered by `terminal:kill` called from a `TERMINAL_SIGNAL` handler (track via a `ptyKilledByRunner: Set<string>`).
  2. Write the completion banner directly to xterm (not to PTY stdin):
     - Success: `\r\n\x1b[2m──\x1b[0m \x1b[1;32m[label] DONE\x1b[0m \x1b[2m──────────────────────────────\x1b[0m\r\n`
     - Abort/error: `\r\n\x1b[2m──\x1b[0m \x1b[1;31m[label] ABORTED\x1b[0m \x1b[2m──────────────────────────────\x1b[0m\r\n`
     - Use `──` (U+2500) flanking characters, ASCII hyphens for padding, ~72 chars total width.
  3. POST to `http://127.0.0.1:8765/runner/terminal/result` with `{ topic, run_id, exit_code, stdout_tail: ptyOutputBuf.get(tabId) ?? '', wall_seconds, user_initiated: userInitiated }`. Python's `runner.parse_result(adapter, stdout_tail)` handles all JSON extraction — terminal.ts does not attempt to parse the output.
  4. Clear `ptyOutputBuf` and `ptyKilledByRunner` entries for this tabId.

**Runner tab metadata:**
- Store `{run_id, topic, adapter, spawnedAt}` per tabId in a `runnerTabMeta: Map<string, {...}>` when `terminal:spawn` fires for a runner-owned tab (use the `runnerOwned` flag from terminalStore, not a string prefix check — prefix-sniffing is fragile).

**Windows / node-pty:**
- Set `useConpty: false` as a configurable fallback (env var `PATHLY_CONPTY=0`). ConPTY on Windows has a documented hang where the process does not exit after PTY close, which would prevent the exit handler from firing and the result POST from being sent.
- Confirm `node_modules/node-pty` is in `asarUnpack` in `electron-builder.yml` — required for `winpty.dll` to resolve at runtime.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.node.json`

---

## Phase 9: PaneTabBar runner tab styling   ← Conversation: 2

**File:** `studio/src/renderer/src/components/Terminal/PaneTabBar.tsx` (logic) + `studio/src/renderer/src/components/Terminal/Terminal.module.css` (styles — one shared CSS file, no separate PaneTabBar.module.css exists)
**Done when:** `grep -n "runnerOwned\|tabRunner" studio/src/renderer/src/components/Terminal/PaneTabBar.tsx` returns matches; `grep -n "tabRunner" studio/src/renderer/src/components/Terminal/Terminal.module.css` returns the class definition.
**Depends on:** Phase 5
**Details:**
- In PaneTabBar render: when `tab.runnerOwned === true`, apply `styles.runnerTab` CSS class to the tab element.
- Add `.tabRunner` and `.tabRunnerActive` to `Terminal.module.css` alongside (not replacing) the existing `.tab`, `.tabActive`, `.tabInactive` classes. Apply both classes together in PaneTabBar render: `cn(styles.tab, tab.runnerOwned && styles.tabRunner, isActive ? styles.tabActive : styles.tabInactive)`.
- `.tabRunner` in `Terminal.module.css`:
  ```css
  border-left: 2px solid var(--runtime);  /* tab container, not the icon button */
  background: var(--runner-bg);
  transition: background 120ms ease-out;
  opacity: 1 !important;  /* override .tabInactive opacity:0.6 — runner tabs stay visible even when not focused */
  ```
- `.tabRunner:hover`:
  ```css
  background: var(--runner-bg-hover);
  ```
- **Existing border-left on `.iconBtnClaude` / `.iconBtnCodex` / `.iconBtnAntigravity`** — these are on the brand icon button element *inside* the tab, not the tab container. The plan's `border-left` goes on the tab container. Different DOM nodes, no collision.
- **Existing `.tabActive` `border-bottom: 2px solid var(--t-accent)`** — coexists with the runner `border-left` on the same element. Both borders stack fine.
- The border does NOT pulse or animate — it is a static ownership marker. The existing `.statusRunning` dot pulse is sufficient as a live indicator.
- Do not add a runner-specific icon. The brand icon (Claude/Codex/AGY) from `TERMINAL_OPTIONS` already identifies the adapter; a second icon creates visual ambiguity.
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
- Card shell:
  ```css
  border-radius: 6px;
  background: var(--bg-surface0);
  border: 1px solid var(--border);
  border-left: 3px solid var(--runner-border);
  transition: border-left-color 200ms ease-out;
  overflow: hidden;
  animation: cardEnter 180ms ease-out both;
  ```
  When `status === 'running'`, apply an additional class that promotes `border-left-color` to `var(--runtime)` (full teal). On run end it transitions back to `var(--runner-border)`. This fires once on run start / once on run end — not a continuous animation.
  ```css
  @keyframes cardEnter { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
  @media (prefers-reduced-motion: reduce) { .card { animation: none; } }
  ```
- Collapsed: status dot (reuse `.dotRunning` pulse class) + `N stages done — [current stage]` + `[▾]` toggle + `[Jump ↗]` button.
- Expanded: table of stages (columns: stage name, adapter, timestamp, duration, status dot; use `<colgroup>` for explicit widths: stage flex-1, adapter 60px, timestamp 58px, duration 52px, status 24px); footer row showing run start time + total stages + `$cost`. Table font-size 11px, `font-variant-numeric: tabular-nums`.
- Expand/collapse animation: CSS `max-height` transition, `0 → 600px`, 200ms ease-out. Do NOT use a JS-driven height animation. Guard `bodyOpen` class toggle on the expand/collapse state.
- `[▾]` / `[▴]` toggle: rotate a single chevron icon via `data-open="true/false"` → `transform: rotate(180deg/0deg)`, `transition: transform 150ms ease-out`. Calls `runnerStore.setLogCardExpanded(!logCardExpanded)`.
- `[Jump ↗]` and `[live ↗]` share the same visual language: same border-radius (3px), same font-size (10px), same `var(--runtime)` color.
  ```css
  .jumpBtn { background: transparent; border: 1px solid var(--runner-border); color: var(--runtime);
             border-radius: 3px; font-size: 10px; font-weight: 600; padding: 1px 7px; cursor: pointer; }
  .jumpBtn:hover { background: var(--runner-bg-hover); border-color: var(--runtime); }
  ```
- The card renders when `stageLog.length > 0`. Sticky (`position: sticky; bottom: 0`) during run; `position: static` when `status === 'idle'`.
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
  white-space: nowrap;
  flex-shrink: 0;
  transition: background 120ms ease-out, border-color 120ms ease-out;
  animation: pillEnter 150ms ease-out both;
  }
  .liveBtn:hover { background: var(--runner-bg-hover); border-color: var(--runtime); }
  .liveBtn:active { background: rgba(45, 212, 191, 0.20); }
  @keyframes pillEnter { from { opacity: 0; transform: scale(0.85); } to { opacity: 1; transform: scale(1); } }
  ```
- The pill does NOT pulse. The status dot in the same strip already pulses; two independent pulse animations create visual interference. The pill is a navigation affordance, not a live-state indicator.
- No exit animation — conditional rendering handles removal. A CSS exit animation would require keeping the element in the DOM with unmount delay, adding complexity for negligible benefit.
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
