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
node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json

# Main process
node_modules/.bin/tsc --noEmit -p studio/tsconfig.node.json

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
- `BottomNav` (`sidebar/shell/BottomNav.tsx`) — the **PANELS** nav, pinned at the foot of the sidebar above `BrightskyProfile` and **outside** the scrolling `treeContainer` so it never scrolls away and is identical in the Workspace and Library tabs. Lists all six panels: Command Center, Pipeline (laid out as a ROW — the GLOBAL live engine board is the MAIN content on the left with only the conditional `OutputBanner` output→modal banner above it; the old feature-scoped header stack (`HeaderBar` / `RunCostBadge` / `HealthCheck`) is UNMOUNTED — a feature title over a global board was incongruous — with `RunCostBadge` re-homed into the flow dock; the selected flow's stage stepper + runner controls live in `FlowStepsPanel`, a collapsible RIGHT dock — a vertical flow-aware stepper built by `deriveFlowSteps` from the running flow's own `pipelineStates`/`stageRoles` (so ANY flow, built-in or user-created, renders its real phases; gate states like `NO_DAG_SEEDED` filtered out), the `TabBar` flow tabs inside it toggling which running flow the dock steps through — sessions/tabs are seeded from the LIVE spawn gate (`useLiveFlowSessions`: every `category:'flow'` engine registers a session keyed by its run slug, the topic basename = the FSM/db-row key, and fronts its tab once at spawn, so a goal team run appears the moment it starts) plus a DB scan of non-terminal plan folders as idle `isRunning:false` tabs (running tabs sort first; only engine-backed sessions show the pulsing dot; `upsertSessionByTopic` dedupes a topic whose guessed flow name is later corrected by the DB row), and `FlowControlBar` re-homed into its footer; clicking a step opens the Configure-phase modal; collapses to a ~34px rail persisted under `pathly:flowDockCollapsed`; internal panel id is still `monitor`, e.g. `sidebar-nav-monitor`), DB Explorer, Markdown Editor, Canvas, Settings. Canvas restores the last-used flow via `openCanvas` in `Sidebar.tsx`.

## CLI-engine spawn scheduler (`src/main/ipc/terminal.ts`)

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

**Rate-limit backoff:** when a headless run exits non-zero and its output matches the `RATE_LIMIT_RE` pattern (429, "rate limit", "overloaded", etc.), a 15-second cooldown (`RATE_LIMIT_COOLDOWN_MS`) is armed. Subsequent queued headless runs wait out the cooldown before starting.

**`SPAWN_DEBUG` logging:** when `SPAWN_DEBUG = true` (default), every spawn lifecycle event is logged to the main-process console with a `[spawn]` prefix.

**SpawnQueuePanel** (`src/renderer/src/components/CliMonitorBar/SpawnQueuePanel.tsx`): revealed inside the `CliMonitorBar` dock via its footer **Manage queue** button; shows the live queue, pause/resume controls, and an editable cap form (global / headless / chat). Caps are persisted to `localStorage` under the key `pathly:spawnCaps`.

**CliMonitorBar dock** (`src/renderer/src/components/CliMonitorBar/`): the floating "Engines" dock — a pure engine monitor. Per-engine rows grouped by category (`DockCollapsed` glanceable pill ↔ `DockExpanded` rows + mini filter), each row's contextual controls (`rowControls`) wired to open/stop/cancel/move-up; the ⤢ button opens the full Pipeline-panel board. Run-start (`FlowControlBar`) and the Code-Intel toggles were removed from the dock — runs now start from the board's goal/task Run controls; `FlowControlBar` remains in `HQ/FlowControlBar/` (unmounted) for possible relocation.

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

**Append-array contract (shared by Analyze + Diagram):** the AGENT owns appends (`{ version:1, source, <items>:[] }`); the renderer never appends — it reads (`readSidecar`), removes by id, and marks-on-board. The prompt presets carry the full append instruction and resolve `{{FILE}}`/`{{SIDECAR}}` at spawn time (`resolvePrompt`); these actions do NOT route through `composeClientSkill`. Each feature is a self-contained folder mirroring the other: `AnalysisGalleryPanel/` ↔ `DiagramGalleryPanel/` (sidecar I/O + `use*Sidecar` data hook + `use*Generation` panel-local hook + `use*Hydrate` on-open chip + gallery panel + card). Analyze's four **lenses** (full / clarity / gaps / redundancy) each append their own report, so they coexist instead of clobbering. `useAnalysisHydrate` also folds a pre-gallery `<file>.analysis` into the array once, then deletes it. Header run state for all three actions lives in `uiStore.mdEditorActions[file].{split|analyze|diagram}`.

**Prompt library (`PromptActionConfig`).** Every prompt-config surface renders one shared component — `shared/PromptActionConfig/` — behind the preset dropdown. Its presets **merge** the host's built-ins with the user's saved prompts via `useMergedPresets(builtins, {kind:'preset', category, projectRoot})` → `services/promptLibrary.ts` → `GET /skills/prompts`. Those `kind='preset'` prompts are now FILES (`pathly/prompts/<category>/<name>.md` + `~/.pathly/prompts/`, mirroring abilities — so they open in the MD editor and carry a `path`), not DB rows; the client contract is unchanged. a `PresetAddRow` "＋ Save current as prompt" (`onAddPreset`) persists the current text back (`POST /skills/prompts`). Wired categories: `diagram` / `analyze` / `split` (via `PromptPeekModal`'s `library` prop — the merged array drives both the dropdown and selection, and the modal spawns the editable text) and `comment` (`CommentConfigButton` + `CommentModal`; the send resolves the picked verb from the merged list in `Editor/index.tsx`). Fail-soft: an unreachable server → just the built-ins, behavior-identical.

## Key Zustand stores

| Store | File | Purpose |
|---|---|---|
| `runnerStore` | `store/runnerStore.ts` | pipeline status, stage, adapter, cost, error — driven by SSE |
| `terminalStore` | `store/terminalStore.ts` | terminal tabs registry; `addTab` registers, `openTab` reveals panel; also holds `spawnQueue: SpawnState` pushed from main via `spawn:state` IPC |
| `markdownEditorStore` | `store/markdownEditorStore.ts` | cells, dirty state, and load/save logic for the Markdown Editor panel |

`RunnerStatus` union: `'idle' | 'running' | 'paused' | 'blocked' | 'error' | 'done' | 'aborted' | 'finalizing'`

---

## Flow gate preview (`components/shared/FlowGatePreview/`)

The board's Run modal (`CommsPanel/SingleAgentButton/`) → Flow tab no longer starts a flow
immediately: "Run flow" opens `FlowGatePreview`, a run-agnostic gate modeled on the
single-agent gate (`SendPreviewModal`) but with a vertical stage stepper (`FlowGateStepper`,
built on the same pure `deriveFlowSteps` the Pipeline-panel `FlowStepsPanel` dock uses) on
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
