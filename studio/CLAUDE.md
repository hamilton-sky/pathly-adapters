# Studio — Frontend Layer

Electron + React + Vite desktop app. **Studio is the board-driven Command Center**: a human supervises *headless* multi-agent runs while the app drives CLI engines step-by-step. The visual flow builder and AI chat panel are surfaces within it.

## Directory structure

```
studio/
  src/main/        Electron main process — IPC handlers, window management
  src/renderer/    React UI — components, stores (Zustand), styles
  tsconfig.web.json    renderer TypeScript config (used for type-checking)
  tsconfig.node.json   main-process TypeScript config
```

## Type-checking

Always run from the **repo root**, not from `studio/`:

```bash
# Renderer (React)
studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json

# Main process
studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.node.json

# Renderer only (npm script — runs tsconfig.web.json)
npm run typecheck
```

> `npm run typecheck` checks **only the renderer** (`tsc --noEmit -p tsconfig.web.json`).
> There is no script that covers the main process — run the `tsconfig.node.json` command
> above explicitly to typecheck `src/main/`.

`tsconfig.web.json` is the renderer config. `tsconfig.node.json` is for the Electron main process. They are separate — passing the wrong one gives misleading errors.

## Build

```bash
npx electron-vite build    # full Electron build (run from repo root)
```

**Tests & dead-code (npm scripts, run from `studio/`):** `npm test` (Vitest) · `npm run test:coverage` (V8 coverage via `@vitest/coverage-v8`) · `npm run knip` (dead-code / unused-export audit).

## Build artifacts — do not commit

`studio/tsconfig.web.tsbuildinfo` and `studio/tsconfig.node.tsbuildinfo` are incremental build caches. Both are in `.gitignore` — never stage them.

## IPC pattern

Main process exposes handlers via `ipcMain.handle(...)`. Renderer calls them via `window.pathly.*` (contextBridge). When adding a new IPC channel, register it in `src/main/ipc/`, the preload (`src/main/preload/index.ts`), and the type declaration (`src/renderer/src/types/global.d.ts`).

## Terminal IPC — runner mode

`terminal:spawn` accepts an optional `argv` array for non-interactive (runner) mode:

```ts
// Interactive — opens a shell session the user can type into
window.pathly.terminal.spawn(tabId, cwd, 'claude')

// Runner — spawns claude non-interactively; exits when done
window.pathly.terminal.spawn(tabId, cwd, undefined, ['claude', '-p', '...', '--print', '--dangerously-skip-permissions'])
```

On Windows, `terminal.ts` writes a UTF-8 BOM `.ps1` temp script to handle newlines, quotes, and other special characters in the prompt safely (PowerShell `-EncodedCommand` has a ~32KB limit; stage prompts regularly exceed it). The script is deleted when the PTY exits.

**Runner tab lifecycle:**
1. `terminal:register-runner(tabId, topic, runId, label)` — called before spawn to link the tab to a pipeline run
2. `terminal:spawn(tabId, cwd, undefined, argv)` — spawns the PTY
3. PTY exits → `terminal.ts` POSTs `/runner/terminal/result` automatically (exit code, stdout tail, wall time)

## FSM server lifecycle

On every app launch, `index.ts` ensures a clean FSM server:
1. Check if port 8765 is occupied (`isFsmRunning`)
2. If yes → POST `/shutdown` (graceful, 800ms timeout)
3. Re-check; if still occupied → `forceKillPort` via `netstat -ano` + `taskkill /F` (Windows) or `lsof | kill -9` (macOS/Linux)
4. Start fresh FSM server process

This guarantees the new server always starts, even against old server versions that predate the `/shutdown` endpoint.

## Topbar and sidebar (redesigned)

**Topbar** (`src/renderer/src/components/topbar/`):
- `PathlyLogo` — corner brand button; clicking it calls `setProjectPath('')` to return to the project picker (replaces the old 'Projects' text button). No hamburger sidebar toggle in the topbar.
- `ProjectSelector` — dropdown to switch projects, open a project in a new window (per-row ExternalLink icon), or open a folder. Replaced the old `TopicSelector`.
- CLI Engines toggle uses the `Cpu` icon from lucide-react (was `Activity`).
- Uniform 28px bar height; topbar content is left (`PathlyLogo`), center (`ProjectSelector`, `EditorLauncher`), right (engine monitor, HQ chat, theme, terminal, publish). Panel switching is **not** in the header — it lives in the sidebar's pinned PANELS nav (`BottomNav`).

**Sidebar collapse/expand** lives inside the sidebar, not the topbar:
- `TabBar` (`sidebar/shell/TabBar.tsx`) — renders WORKSPACE / LIBRARY tabs plus a `PanelLeft` collapse button at the right of the tab bar.
- `IconStrip` (`sidebar/shell/IconStrip.tsx`) — the collapsed sidebar; shows a `PanelLeft` expand button at the top plus icon shortcuts mirroring the six PANELS entries (Markdown Editor uses `FileText` here to avoid clashing with Library's `BookOpen`).
- `BottomNav` (`sidebar/shell/BottomNav.tsx`) — the **PANELS** nav, pinned at the foot of the sidebar above `BrightskyProfile` and **outside** the scrolling `treeContainer` so it never scrolls away and is identical in the Workspace and Library tabs. Lists all six panels: Command Center, Pipeline (a single FULL-WIDTH column, internal panel id still `monitor`, e.g. `sidebar-nav-monitor`: the GLOBAL engine board (`MonitorBoard`) with its **Live / Runs** mode toggle, the conditional `OutputBanner` output→modal banner above it, and — ONLY while a run is active — the global runner controls (`FlowControlBar`) as a slim top bar. The old right-side `FlowStepsPanel` dock (stage stepper + flow tabs + per-stage configure) was REMOVED from the panel: the stepper's job is now the `RunDetailPage` **Stages** tab, per-stage config is a flow-AUTHORING concern (flow editor, not a run monitor), and the runner controls act on the single active FSM run — not a `run_id` — so they live at the panel level, not on a per-run page. The old `FlowStepsPanel` dock files were DELETED as dead code (knip); only its pure `deriveFlowSteps` helper (`Monitor/FlowStepsPanel/flowSteps.ts`) survives, still imported by `FlowGatePreview`. The likewise-unmounted `HeaderBar`/`RunCostBadge`/`HealthCheck`/`FsmView` were deleted too), DB Explorer, Markdown Editor, Canvas, Settings. Canvas restores the last-used flow via `openCanvas` in `Sidebar.tsx`.

## CLI-engine spawn scheduler (`src/main/ipc/terminal.ts` + `src/main/ipc/terminal/`)

`terminal.ts` orchestrates; it no longer implements. The pieces live in `src/main/ipc/terminal/`,
one concern each (split 2026-08-18 under the 400-line ratchet — the file was 1248 lines):

| Module | Owns |
|---|---|
| `shells.ts` | command/argv → `(shell, args)`, launcher resolution, `enrichedPath`, Windows temp script, `isValidCwd` |
| `spawnGate.ts` | caps, queue, engine registry (`activeEngines`/`queuedEngines`/`recentEngines`), `spawn:state` broadcast, rate-limit cooldown, transient-retry bookkeeping |
| `ptyRegistry.ts` | the live per-tab maps (`activePtys`/`ptyWindows`/`ptyOwners`/`ptyOutput`/`runnerTabMeta`/`runnerScripts`), `sendToWindow`, `killPtyTree`, `killAllPtys` |
| `promptInjector.ts` | startup-gate answering + the interactive bracketed-paste injector |
| `spawnReporting.ts` | the post-exit POSTs (`/runner/terminal/result`, `/db/invocation`) |
| `preflight.ts` | is this engine installed? |
| `popout.ts` | detach a tab into its own BrowserWindow |
| `log.ts` | `slog` |

Dependency direction is one-way — `log` ← `shells` ← {`preflight`, `spawnGate`} ← `ptyRegistry` ←
`spawnReporting`/`popout` ← `terminal.ts`. `killAllPtys` is re-exported from `terminal.ts` so
`main/index.ts` keeps one import site. Because `queuePaused` / `rateLimitedUntil` / `spawnStateWin`
are module-private `let`s, the gate exposes `setQueuePaused` / `armRateLimitCooldown` /
`setSpawnStateWindow` / `rateLimitCooldownRemaining` / `listActiveEngines` rather than raw bindings.

Every `terminal:spawn` call for a CLI engine goes through a dual-cap concurrency gate. Two classes:

| Class | Behaviour when over cap |
|---|---|
| **Headless one-shots** (runner/board stages, editor actions) | QUEUED (FIFO with priority; pipeline tabs get priority=10) |
| **Interactive sessions** (manual `claude`, chat mode) | REJECTED — error thrown; Studio shows a toast |

Default caps (all configurable at runtime via `terminal:queue-control` with `type:'set-caps'`):

```
global:      8   // max sum of headless + interactive running
headless:    5   // max headless one-shots running simultaneously
interactive: 5   // max interactive CLI sessions open simultaneously
```

Queue management IPC: `terminal:queue-control` accepts `pause | resume | cancel | reorder | set-caps`.
`spawn:state` IPC event is broadcast to the renderer after every state change — `terminalStore.spawnQueue` holds the latest snapshot.

**The gate is the single source of truth for engine liveness.** Its `spawn:state` payload carries `engines: RunningEngine[]` — every identified live engine (`{ tabId, adapter, label, startedAt, category, feature?, role?, runId? }`; `category`/`feature`/`role`/`runId` are derived at the `activeEngines.set` site from the runner topic (`runnerTabMeta`) or `meta.telemetry` so consumers can group cards, scope cost, and open the per-flow rollup — a registered runner tab → `flow`, anything else → `single`; `runId` keys `/db/runs/<run_id>/cost`), added right after `pty.spawn` (queued-but-not-yet-running engines are registered in a parallel `queuedEngines` map at request time so a paused/queued run is visible as a row, not just a count) and removed in `releaseEngineSlot` (the one place exit/kill/cancel converge). the floating `CliMonitorBar` dock (`useDockEngines`, global — all features), the topbar CLI-engine dot, and the Pipeline panel's embedded engine board (`Monitor/EngineBoard/`, projected via `useMonitorEngines` — **GLOBAL**, every engine, in parity with the dock; NOT feature-scoped, and rendered even with no feature selected so an editor/one-shot engine is never invisible in the section) all project THIS list, **not** per-tab `terminalStore` status — so board/runner runs, editor one-shots, and manual REPLs all appear identically, the header count and the dock share one source, and the list survives a renderer reload (engines live in the main process; the renderer store does not). `terminalStore` is joined in only to enrich a row with scrollback/prompt and to enable "open terminal".

**Transient-failure classification** (`src/main/ipc/engineFailure.ts`): `classifyEngineFailure(exitCode, tail)` separates a *provider* refusal (rate limit, quota, "at capacity", overloaded, 5xx) from a real agent/auth failure. `transient` requires a matching phrase **and** evidence the run actually failed — a non-zero exit **or** an engine abort marker (`ENGINE_ABORT_RE`: codex's `"type":"turn.failed"`, claude's `"is_error":true`), because some CLIs report a failed turn in their JSON stream and still exit 0. The second condition is what stops an agent that merely *writes about* rate limits from being misread as rate-limited.

**Rate-limit backoff:** a headless run classified `transient` arms a 15-second cooldown (`RATE_LIMIT_COOLDOWN_MS`). Subsequent queued headless runs wait out the cooldown before starting.

**Transient retry:** the same classification also re-runs the failed spawn, up to `MAX_TRANSIENT_RETRIES` (2) with exponential backoff (`retryDelayMs` — 4s, 12s). The spawn path is the named `handleSpawn` function (in `terminal.ts`) precisely so the retry can re-enter the whole gate — queue slot, caps, priority and cooldown all apply again rather than being bypassed. The retry returns from `onExit` **before** `terminal:exit` and the telemetry / `/runner/terminal/result` POSTs fire, so consumers see ONE exit for the whole attempt chain (no duplicate invocation rows, no premature "no file produced"); the terminal shows an inline `engine unavailable — retrying (n/2)` banner between attempts. `ptyOutput` is cleared between attempts so each is judged on its own output. A user **Stop** always wins — `terminal:kill` sets `ptyKilledByUser` in BOTH of its branches (after the ownership check when a PTY is live, and unguarded when there is none), because during a retry backoff there is no live PTY to kill and that window must still be stoppable. Interactive sessions are never retried.

**`SPAWN_DEBUG` logging:** when `SPAWN_DEBUG = true` (default), every spawn lifecycle event is logged to the main-process console with a `[spawn]` prefix.

**SpawnQueuePanel** (`src/renderer/src/components/CliMonitorBar/SpawnQueuePanel.tsx`): revealed inside the `CliMonitorBar` dock via its footer **Manage queue** button; shows the live queue, pause/resume controls, and an editable cap form (global / headless / chat). Caps are persisted to `localStorage` under the key `pathly:spawnCaps`.

**CliMonitorBar dock** (`src/renderer/src/components/CliMonitorBar/`): the floating "Engines" dock. Per-engine rows grouped by category (`DockCollapsed` glanceable pill ↔ `DockExpanded` rows + mini filter), each row's contextual controls (`rowControls`) wired to open/stop/cancel/move-up; the ⤢ button opens the full Pipeline-panel board. `DockExpanded` shows the LIVE gate engines (`useDockEngines`) plus a **Recent** history section (`useRecentSpawns` → `/db/recent`, polled only while the dock is open, deduped against the live list) — so a run that has EXITED (incl. a renderer one-shot: ai-router summary, editor action) is still visible as history, not only while its engine is live. This mirrors the full Monitor board (`useMonitorEngines` + `useRecentEngines`). Opening a row is graceful (`openEngine`): a LIVE engine reveals its terminal tab; a finished Recent row (terminal tab gone → `openTab` no-ops) jumps to the full Monitor panel instead of a dead click. The full-panel per-run detail view now exists (`RunDetailPage`, P0e entrance #1 — see below). Run-start (`FlowControlBar`) and the Code-Intel toggles were removed from the dock — runs now start from the board's goal/task Run controls; `FlowControlBar` (still in `HQ/FlowControlBar/`) is now mounted in the **Monitor panel** as a slim top bar shown only while a run is active, re-homed there when the `FlowStepsPanel` right dock was removed.

**RunDetailPage** (`src/renderer/src/components/RunDetailPage/`, unified-control-plane P0e): a shared full-page run view keyed by `run_id`, data via `useRunDetail` → `GET /runs/<id>`, polled every 8s AND live-refreshed (unified-control-plane T4) via an `EventSource` subscription to `GET /events/runs?run_id=<id>` — any runner/comms event tagged with the run_id triggers an immediate re-fetch so the Logs/Board tabs update without waiting on the poll; no auth header is sent (the server's secret middleware exempts every `/events/*` path), mirroring the same localhost-open `EventSource` pattern as `useCommsPanel`/`pathlyContext.subscribeToMenuUpdates`; the 8s poll keeps running as a fallback if the stream errors, closes, or is unavailable. Shell mirrors DBExplorerRedesign's `FeatureDetailPage` (back · header `KindBadge`/`AdapterBadge`/`StatusBadge` + **`RunControls`** (`RunDetailPage/RunControls/`, T2) · `refresh` · big-stats · tab bar · body); tabs = **Stages · Phases · Logs · Board · Cost** (each its own component; stages/cost reconcile from `agent_invocations`). The **Phases** tab (`PhasesTab`) is a timeline of the run's PHASE_START/DONE markers — `type='phase'` board posts filtered OUT of the Board tab (which keeps decisions/discoveries/artifacts); they stream in live now that `_phase_board.post_phase_to_board` stamps the live run's run_id (`run_history.latest_running_run_id_for_feature`) so the T3 per-run feed tees them. `KindBadge`/`StatusBadge` are LOCAL — they carry `decompose`/`error`/`aborted`, which Monitor's `EngineCategory`/`EngineStatus` unions don't (AC-7: don't touch Monitor). **`RunControls`** (unified-control-plane T2) is capability-gated by `run.kind` + `run.status`: a **■ Stop** button for any active run (running/paused/awaiting_decision) → `apiStopRun` → `POST /runs/<id>/stop`; for a `kind==='flow'` run only, additional pause/resume/advance/reroute/retry buttons → the new `apiRunAction(runId, action, body?)` → `POST /runs/<id>/<action>` (single/loop/other kinds see only Stop — the server's board-lock resolver supports no other action). Which flow buttons show is a pure, unit-tested gate (`runControlsUtils.ts::visibleFlowActions`) mirroring the server's own ACTIVE_STATUSES gate: running → Pause+Reroute, paused → Resume+Advance+Reroute, awaiting_decision → Reroute, finished (done/aborted/error) → Retry (defaults `max_iterations`/`max_cost_usd` to `apiStartFlow`'s own 50/$10 — RunDetail doesn't carry the original run's caps — and reads the flow name off `run.adapter`, which IS the flow name for a `kind==='flow'` row per run-identity). Reroute opens a local `RerouteMenu` adapter picker (mirrors `HQ/FlowControlBar`'s `ReroutePopover`: same `ADAPTERS` source, outside-click/Escape dismiss) instead of acting immediately. Every action funnels through one `pending`-state dispatch hook (`hooks/useRunControls.ts`) and calls `refresh` after it lands. **Entrance #1 is wired:** `EngineDetailModal` gained an `Open run →` button (`onOpenRun`, threaded `MonitorBoard` → `Monitor/index.tsx`), and `Monitor` swaps its panel body to `RunDetailPage` when `detailRunId` is set (the app shell stays). A 404 (`run_id` not yet in `run_history` — e.g. a live flow stage whose card id is a tabId, or a run predating tracking) renders a friendly not-found state. **Entrance #2 is built** as a **Live / Runs** mode toggle in the Monitor board header (`MonitorBoardHeader`'s `SegmentedControl`, extracted so `MonitorBoard` stays within the size cap): Runs mode renders `RunList` (`Monitor/RunList/`) — the folded one-row-per-top-level-run list from `useRuns` → `GET /runs` (lazy-polled only while Runs mode is open), honoring the header's **grid/rows layout toggle** (now un-gated to apply to BOTH modes, not Live-only): `banner` → `RunRow` list, `grid` → `RunCard` responsive card grid (mirrors the Live board's RECENT cards) — both reuse `KindBadge`/`StatusBadge` and open `RunDetailPage`. Category/adapter/scope filters + their counts recompute from the ACTIVE mode's rows; the status pill flips to `polls · 8s` (the P0 run list is DB-on-mount, never SSE) and a note points queued items back to the Live board (the gate queue has no `run_history` row). `Monitor/index.tsx` now always mounts `MonitorBoard` (so the toggle is reachable with nothing live, and each mode owns its empty state). **The P2 launcher is built** (unified-control-plane T6): Runs mode shows a **New run** button (`Monitor/RunList/NewRunButton/` — `NewRunButton` → `NewRunModal` → `NewRunForm` + `hooks/useNewRunForm.ts`) opening a modal to pick a RunSpec `{kind (flow|single|evaluator|goal), board, scope, flow?, goal_id?}` → `apiCreateRun` (`store/commsApi.ts`) → `POST /runs` (the T5 launcher, which routes to the existing `start_run`/`start_board_run`/`start_goal_run` facades). `useNewRunForm`'s `canSubmit` mirrors the server's per-kind requirements (flow → scope+flow, single/evaluator → scope, goal → goal_id) so Start stays disabled instead of round-tripping a 400; on success `useRuns` gained a `refetch()` (nonce bump) so the just-started run appears without waiting for the 8s poll.

## Dash-safe prompt (`src/renderer/src/services/cliEngine.ts`)

`dashSafePrompt(prompt)` strips any leading YAML frontmatter block (`---…---`) from a prompt before it is passed to a CLI as a positional argument. Without this, `claude -p '---...'` is parsed as an unknown option and errors. Applied in `buildHeadlessArgv` before constructing argv. Mirrors `_dash_safe_prompt` in `src/pathly_orchestrator/adapters.py`.

**Codex headless shape:** `codex exec --skip-git-repo-check --sandbox workspace-write -- <prompt>`. On Windows, `terminal.ts` pipes `$null` to stdin to prevent `codex exec` from stalling while waiting for additional stdin input.

**One-shot cost capture (`codexJson.ts`):** editor Diagram/Analyze one-shots post their own telemetry to `/db/invocation` from the spawn gate. claude reports cost+tokens+result in one JSON envelope (`parseClaudeJsonResult`); codex emits JSONL with tokens but **never a dollar cost**, which the claude parser can't read — so `parseCodexResult` (a pure mirror of the Python `_codex_usage`) scans the codex stream for token usage + the final agent message. The gate sends the tokens (cost stays `0`); the server then estimates the dollar cost from them (`runner/telemetry.py::project_agent_done` → `db/pricing.py::estimate_cost_for`). Without this a codex one-shot recorded `$0 / 0 tokens`.

**Batch-shim guard (`resolveRunnerShell`):** a resolved launcher ending in `.cmd`/`.bat` is a cmd.exe batch shim, and cmd's batch parser **shreds any argument containing a newline** — it truncates at the first CR/LF and the escaped remainder makes cmd print "The system cannot find the path specified", yet the chain still exits 0 (a silent false success — this was the `agy.cmd` diagram-run failure). Mitigation: for claude/codex a multi-line prompt through a batch shim is moved onto **stdin** regardless of length (there is a channel); for an engine with **no** stdin path (agy), a still-on-command-line newline arg **throws** so the run surfaces as an error instead of a false success. `agy` resolves to `%LOCALAPPDATA%\agy\bin\agy.exe` first — the `.cmd` fallback only bites during an agy self-update rename window. Full spec (all three agy failure modes, the adapter capability matrix, and the upstream fix paths): [../docs/ADAPTER_PROMPT_DELIVERY.md](../docs/ADAPTER_PROMPT_DELIVERY.md).

## Markdown Editor (formerly Notebook)

The component formerly called "Notebook" is now fully renamed:
- Component: `MarkdownEditor` (`src/renderer/src/components/MarkdownEditor/MarkdownEditor.tsx`)
- Panel id: `'markdown-editor'`
- Store: `markdownEditorStore` (`src/renderer/src/store/markdownEditorStore.ts`)
- State key prefix: `mdEditor*`

### Editor AI actions — two storage models

The header pills spawn one-shot CLI agents against the open file. There are two result shapes:

| Model | Actions | Sidecar | Behaviour |
|---|---|---|---|
| **Overwrite** (one at a time) | AI Split | `<file>.split.draft` | agent rewrites the whole draft; shown as a diff |
| **Append array** (accumulate → gallery) | AI Analyze, Diagram | `<file>.analyses.json`, `<file>.diagrams.json` | agent appends ONE entry per run; a right-docked gallery lists all entries; renderer only reads/removes |

**Append-array contract (shared by Analyze + Diagram):** the AGENT owns appends (`{ version:1, source, <items>:[] }`); the renderer never appends — it reads (`readSidecar`), removes by id, and marks-on-board. The prompt presets carry the full append instruction and resolve `{{FILE}}`/`{{SIDECAR}}` at spawn time (`resolvePrompt`); these actions do NOT route through `composeClientSkill`. Each feature is a self-contained folder mirroring the other: `AnalysisGalleryPanel/` ↔ `DiagramGalleryPanel/` (sidecar I/O + `use*Sidecar` data hook + `use*Generation` panel-local hook + `use*Hydrate` on-open chip + gallery panel + card). Analyze's four **lenses** (full / clarity / gaps / redundancy) each append their own report, so they coexist instead of clobbering. `useAnalysisHydrate` also folds a pre-gallery `<file>.analysis` into the array once, then deletes it. Header run state for all three actions lives in `uiStore.mdEditorActions[file].{split|analyze|diagram}`. That map is now **persisted** (running slots only — `pickRunningActions`) so a run survives a full renderer reload; `useOneShotReconcile` (`EditorHeader/hooks/`) then re-verifies each restored `running` slot against the LIVE gate engines via the `terminal:get-engines` IPC (a synchronous main-process snapshot that survives reload, unlike the racy async `spawn:state` push) and clears it if the run is no longer alive — grace-period guarded so a normal in-session completion (whose `onExit` sets success/error on a separate IPC tick) is never clobbered. Fail-safe: worst case a pill CLEARS (as before persistence), never sticks.

**Prompt library (`PromptActionConfig`).** Every prompt-config surface renders one shared component — `shared/PromptActionConfig/` — behind the preset dropdown. Its presets **merge** the host's built-ins with the user's saved prompts via `useMergedPresets(builtins, {kind:'preset', category, projectRoot})` → `services/promptLibrary.ts` → `GET /skills/prompts`. Those `kind='preset'` prompts are now FILES (`pathly/prompts/<category>/<name>.md` + `~/.pathly/prompts/`, mirroring abilities — so they open in the MD editor and carry a `path`), not DB rows; the client contract is unchanged. a `PresetAddRow` "＋ Save current as prompt" (`onAddPreset`) persists the current text back (`POST /skills/prompts`). Wired categories: `diagram` / `analyze` / `split` (via `PromptPeekModal`'s `library` prop — the merged array drives both the dropdown and selection, and the modal spawns the editable text) and `comment` (`CommentConfigButton` + `CommentModal`; the send resolves the picked verb from the merged list in `Editor/index.tsx`). Fail-soft: an unreachable server → just the built-ins, behavior-identical.

## Settings panel (`components/Settings/`)

`SettingsPanel` is a left nav rail (`SettingsNav`, ARIA vertical tabs) + a content panel that swaps
on the active group. Groups: **Appearance · Runs · Agents · Intelligence · System**. Each group is
a component that renders one or more `Settings.module.css` `.section` blocks and owns its own
state/hooks — the panel only tracks the active group. Add a group by extending the `SettingsGroup`
union + `ITEMS` (`SettingsNav`) and the `PANELS` map (`SettingsPanel`).

**Agents** (`AgentsSettings/` → `ModelsSettings/`) is the **spawn-policy** model config (feature:
`pathly/features/spawn-policy/`) — DB-backed, read by BOTH the renderer gate and the Python
resolver so every spawn obeys one policy. It holds **Models only**: a global default + grouped
per-agent overrides. The **Agents** group is registry-driven (`useAgents` → `GET /db/agents`,
seeded from `core/agents/`) so a newly-created agent appears automatically; **Editor / one-shot**
is a fixed group (split/analyze/diagram/comment/summarize — app actions, not agents); **Custom**
shows any other configured key plus an `AddRoleRow` "+ Add override" that accepts ANY role string
(the resolver keys by arbitrary string). Each `ModelRow` = a company picker (`ADAPTER_META`,
headless-only) + a `ModelPicker` (a `GET /telemetry/pricing` dropdown with `$in/$out per MTok`
hints + a "Custom model…" free-text escape hatch). Empty company = inherit/unset. Hooks
`ModelsSettings/hooks/{useModelPolicy,usePricing,useAgents}.ts` → `apiGet/Set/ClearModelPolicy` +
`apiGetPricing` + `apiGetAgents` (`store/commsApi.ts`) → `GET/POST /comms/model-policy`. Fail-safe:
an older FSM server 404s → empty policy / no pricing / built-in agent fallback.

**The policy TAKES EFFECT for renderer one-shots** via `services/spawnPolicy.ts::effectiveModel(role,
adapter)` — a client mirror of the Python `supervisor/spawn_policy.effective_model` (explicit model
wins; else the per-role → global-default model applies only WITHIN the same company). It reads a
cached policy (`warmModelPolicy`, warmed on module load + re-warmed by `useModelPolicy`'s setters so
resolution is synchronous at spawn). Threaded into all five one-shot spawn sites: editor **Split**
(`useEditorAgentActions`, role `split`), **Analyze** (`analyze`), **Diagram** (`diagram`), **Comment**
(`CommentsPanel`, `comment`) via `editorCli.buildCliArgv(cli, prompt, model)`, and artifact
**summaries** (`aiRouter` engine path, role `summarize`). No policy → no `--model` (engine default),
byte-identical to before. (These roles match the Models UI "Editor / one-shot" group.) Each site
also stamps `telemetry.feature = featureFromPath(<file>)` (`utils/featureFromPath` → the slug under
`pathly/features/<slug>/`) so the one-shot **attributes to its feature board** in the Pipeline
(`GET /runs`) instead of the generic `(project)`; a non-feature file stays `(project)`. The
`telemetry.feature` → `/db/invocation` plumbing already existed (`terminal.ts`); the callers just
never set it. (summaries thread it via `AiJob.feature` → `runEngine`.)

**Logging is deliberately NOT a setting.** Per the unified-control-plane separation of concerns:
the **Pipeline** section is the operational plane (observe + control every run — logs, cost,
tokens, `run_id` — for EVERY agent spawn anywhere in the app); the **board** is context governance
(decisions/artifacts/questions the governance agents own); **Settings** is config ("the rest").
So there is no board-narration on/off or verbosity control here — board posting is intrinsic to the
governance agents, and run observability is always-on in the Pipeline, never a toggle. (The inert
`/comms/logging-config` backend route from the first spawn-policy pass is now unexposed.)

## Key Zustand stores

**Two of these were split under the 400-line ratchet (2026-08-18), import sites unchanged:**
`store/commsApi.ts` is now a **barrel** (16 lines) over `store/commsApi/` — one file per backend
domain (`rows`, `scope`, `messages`, `artifacts`, `modelPolicy`, `runnerControl`, `search`,
`boardRun`, `goalRun`, `features`), so all 36 `from '../store/commsApi'` imports still resolve.
`commsStore.ts` gave up its declaration + pure helpers to `store/commsStore/{types,keys}.ts`
(`CommsState`/`GlobalSearchHit` are re-exported from `commsStore.ts` for existing importers);
its ~700-line action object is NOT yet sliced — see the note under the table.

| Store | File | Purpose |
|---|---|---|
| `runnerStore` | `store/runnerStore.ts` | pipeline status, stage, adapter, cost, error — driven by SSE |
| `terminalStore` | `store/terminalStore.ts` | terminal tabs registry; `addTab` registers, `openTab` reveals panel; also holds `spawnQueue: SpawnState` pushed from main via `spawn:state` IPC |
| `markdownEditorStore` | `store/markdownEditorStore.ts` | cells, dirty state, and load/save logic for the Markdown Editor panel |
| `runRegistryStore` | `store/runRegistryStore.ts` | **PERSISTED** (`localStorage` `pathly:active-runs`) run_id spine for the board's RunPills — target (`goal:`/`board:`/`flow:`) → `{runId, kind, startedAt, projectRoot, board, scope}`. `commsStore` registers at every board/goal/flow run-start and clears on completion; `commsStore.rehydrateActiveRuns(projectRoot)` (called on `CommandCenter` mount) re-verifies each entry against the backend (board-lock holder / FSM runner status; hiccup-safe — a null status keeps the entry, never false-clears) and repopulates the pill or clears it, so a run still alive after a full renderer reload reappears with its original elapsed clock. The `editor`/`summary` kinds are reserved for the MD-editor one-shots + summarizer (NOT yet wired — those still live in `uiStore.mdEditorActions` / `commsStore.summaryStatus` and survive navigation but not reload). |

**`commsStore`'s action object is deliberately still one block.** Slicing it into zustand slices
is the only way to get the file under 400, but the store has **no test coverage** and 18 importers,
and its run-watchers close over `useCommsStore` itself (a slice extraction has to break that cycle
via injection, not a plain import). Write characterization tests for the board/goal run lifecycle
FIRST; until then the ratchet just freezes it.

`RunnerStatus` union: `'idle' | 'running' | 'paused' | 'blocked' | 'error' | 'done' | 'aborted' | 'finalizing'`

---

## Flow gate preview (`components/shared/FlowGatePreview/`)

The board's Run modal (`CommsPanel/SingleAgentButton/`) → Flow tab no longer starts a flow
immediately: "Run flow" opens `FlowGatePreview`, a run-agnostic gate modeled on the
single-agent gate (`SendPreviewModal`) but with a vertical stage stepper (`FlowGateStepper`,
built on the same pure `deriveFlowSteps` (`Monitor/FlowStepsPanel/flowSteps.ts`)) on
top of a per-stage `PromptBanner` + `Sections` (`SkillSplitModal`, assemble mode). Every
stage is pre-composed up front via `composeSkillPrompt` (`useFlowGateStages`); clicking a
step swaps the banner/Sections to that stage. Confirming collects a `{state: prompt}` map
from ONLY the Sections-confirmed stages (`useFlowGateState.buildOverrides`) and threads it as
`stageOverrides` through `FlowForm.onRunFlow` → `CommsPanel.handleRunFlow` →
`commsStore.startBoardFlow` → `commsApi.apiStartFlow` (body `stage_overrides`, sent only when
non-empty). It is a **transient, per-run** override — see
`src/pathly_orchestrator/CLAUDE.md`'s `stage_overrides` entry for the server side.

The same gate + channel is now reused from two more entry points (no new channel):
- **Team goal Run** — `GoalRunButton` opens `FlowGatePreview(flow='team-build', interactive=false)`
  only when the goal's executor is `team` (single/loop run unchanged, ungated); confirming calls
  `runGoal(goalId, executor, { stageOverrides })` → `apiRunGoal` → `POST /comms/goals/run`.
- **Consultation-in-Evaluate** — `EvaluateBoardButton`'s two consultation confirms (goal-target
  and whole-board decompose) now render `FlowGatePreview` instead of `ConfirmModal`: goal target
  → flow `consultation`; whole-board → `feature-consultation` or `project-consultation` (board
  scope). `useEvaluateBoardButton`'s `confirmGoal`/`confirmFeature`/`dispatchFeatureDecompose`
  thread `stageOverrides` into `decomposeGoal`/`decomposeFeature`/`decomposeProject` → the matching
  `/comms/*/decompose` route. The whole-board EVALUATE path (`SendPreviewModal`) is unchanged.

---

## UI coding rules — non-negotiable

### Responsive to container — always

Every component and every button must resize gracefully as its container changes width. Non-negotiable rules:

- **No fixed `width` on containers** — use `width: 100%`, `flex: 1`, or `min-width: 0` instead.
- **Flex children that must shrink need `min-width: 0`** — without it a flex item won't shrink below its content width, causing overflow.
- **Buttons must use `min-width` only as a floor, never a fixed width** — they must be allowed to shrink or wrap.
- **`flex-shrink: 0` is reserved for elements that must never shrink** (icons, single-char badges). Do not apply it to input fields or buttons that contain text.
- **Every panel layout must be verified at ≤200px wide** — use `overflow: hidden` on section containers so nothing escapes the panel bounds.
- **Never use `overflow: visible` on a scroll container** — use `overflow: hidden` or `overflow: auto`.

### No inline styles
Never use `style={{ ... }}` props. All styling goes in the component's `.module.css` file.

**The only accepted exceptions** — values that are genuinely impossible to express in static CSS:
- Dynamic progress bar width: `style={{ width: \`${pct}%\` }}` → use `<progress value={pct} max={100} />` instead (no style prop needed)
- CSS custom properties injected per-element: `style={{ '--anim-delay': `${index * 55}ms` } as React.CSSProperties}` — the value feeds a `var(--anim-delay)` reference in the CSS module; the style prop carries data, not presentation
- Non-standard properties with no TypeScript-safe CSS alternative: `style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}` for Electron drag regions
- Imperative setProperty when the value changes after mount: `ref.current.style.setProperty('--offset', `${y}px`)` inside a `useEffect`

Theme colors and spacing always come from CSS custom properties defined in `tokens.css` (`var(--bg-mantle)`, `var(--accent)`, `var(--text-primary)`, etc.) — never from a `useTheme()` call in JSX.

### Single responsibility — one component, one job
Every component does exactly one thing. If a component needs a comment to explain which "section" it is rendering, it should be a separate component.

**Size guide:**
- Hard limit: ~150 lines per component file
- If a file exceeds this, extract the next logical sub-section into its own file in the same folder

**Folder rule (non-negotiable):** every component lives in its own subfolder alongside its CSS module. Flat `.tsx` + `.module.css` pairs at the feature-folder level are a violation — always create the subfolder:
```
ComponentName/
  ComponentName.tsx
  ComponentName.module.css
```
No exceptions for "small" or "simple" components. If a component is too small to warrant a folder, ask whether it should be inlined into its only consumer instead.

**What to extract:**
- A repeated render block → named sub-component in the same folder
- All state + effects + handlers for a large component → a `useComponentName` hook file
- Pure utility functions (no React) → a `utils.ts` or `componentNameUtils.ts` file
- Standalone SVG icons with no CSS → a shared `icons.tsx` file in the feature folder (no subfolder, no `.module.css`); size/color via Lucide `size` prop or `currentColor`, never a `style` prop

**Hook naming and location:**
```
ComponentName/
  hooks/
    useComponentName.ts   ← UI state + event handlers (tab, viewMode, open/close)
    useFeatureName.ts     ← data fetching and side effects (async loads, subscriptions)
```
One hook per concern. UI state hooks return named state + setters + derived handlers. Data hooks return data only — no setters exposed to callers.

### CSS variant pattern — data attributes over class proliferation

When an element has 3+ visual states that differ only in color or decoration, use a `data-*` attribute instead of a cascade of conditional class names. The CSS module handles all variants with attribute selectors:

```tsx
// Instead of: className={`${s.badge} ${isBlocked ? s.blocked : isActive ? s.active : s.idle}`}
<span className={styles.badge} data-status={status}>{label}</span>
```
```css
.badge[data-status='blocked'] { color: var(--red); animation: pulseRed 1.8s infinite; }
.badge[data-status='active']  { color: var(--accent); }
.badge[data-status='idle']    { color: var(--text-muted); }
```

Use `.className` modifiers (`.active`, `.pinned`) for simple binary states. Use `data-*` attributes when there are 3+ mutually exclusive states or when the same element accepts values from an enum/union type.

### Hover state — CSS first, JS only when it must cross a component boundary

| Hover reach | Pattern |
|---|---|
| Affects only the element itself | CSS `:hover` pseudo-class — no JS |
| Shows/hides a child of the same element | CSS `.parent:hover .child { opacity: 1; }` — no JS |
| Shows/hides a sibling in a **different component file** | `const [isHovered, setIsHovered] = useState(false)` in the shared parent → pass as `isHovered: boolean` prop → child applies a CSS class (`.visible`) |

Never put hover state in Zustand. It is ephemeral UI state that belongs to the component that renders the hovered element.

### Buttons
Every `<button>` must have an explicit `type="button"` (or `type="submit"` if it submits a form). No exceptions.

### ARIA
Use `aria-expanded`, `aria-label`, and other ARIA attributes on interactive elements. For dynamic boolean attributes, use the spread pattern to avoid static-analysis false positives:
```tsx
{...(isOpen ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
```

### External links
Any `<a target="_blank">` must include `rel="noopener noreferrer"`.

### Timestamps — one shared util, never hand-rolled
Every rendered timestamp goes through `src/renderer/src/utils/timestamp.ts` or the
`<Timestamp>` component (`components/Timestamp/`). Do **not** write a new
`Date.now()`-diff "ago" formatter or a bare `toLocaleTimeString()`/`toTimeString()` —
that ad-hoc fragmentation (six divergent formatters) is exactly what this replaced.

- Pure functions: `formatRelative` (owns its ` ago` suffix; one ladder —
  `just now` → `Nm ago` → `Nh ago` → `Nd ago` → flips to an absolute date at **7 days**),
  `formatAbsolute` (full datetime for tooltips/audit), `formatClock` (`HH:MM:SS` for dense
  log rows), `formatDateShort` (`Jul 6`), `dayKey` (YYYY-MM-DD for log day-dividers).
  All accept `string | number | Date | null`,
  are locale-aware via `Intl` with explicit options, and return a sentinel — **never throw**.
- Prefer `<Timestamp value={…} mode="relative|absolute|clock" />` in JSX — it renders a
  semantic `<time dateTime>` with the absolute time in a hover `title` for free. Use the
  pure functions only where JSX isn't possible (composing a log line, a window title).
- Never append `" ago"` in JSX and never pre-format a timestamp into a string field on a
  store model — pass the raw `ts` through and let the util format at the render edge.
