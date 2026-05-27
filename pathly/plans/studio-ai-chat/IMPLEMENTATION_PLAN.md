# Studio AI Chat — Implementation Plan

## Overview

Adds the **Conductor** — a local AI chat panel to Pathly Studio (Electron). The Conductor
interprets plain-English intent, matches it to the right Pathly skill via embedding similarity
(MiniLM, ~22ms, offline), explains the match with phi4-mini, and writes the skill command to
the Claude Code or Codex terminal tab with user approval.

**Read DESIGN_SPEC.md before building any UI.** It contains ASCII layouts, design tokens,
component specs, and the interaction model.

## Pre-flight

Before Conversation 0:
```
cd studio && npm run typecheck
```
Record any pre-existing failures as baseline. Conv 0 must not introduce new errors.

---

## Phase 0a: Fix Claude/Codex spawning on Windows   ← Conversation 0

**File:** `studio/src/main/ipc/terminal.ts` — MODIFY
**Done when:** Clicking `A Claude` and `✳ Codex` buttons in Studio opens a real Claude Code / Codex session (not PowerShell) on Windows
**Delivers:** S0.3

**There are two bugs to fix — both are required:**

**Bug 1 — ALLOWED_SHELLS rejects 'claude'/'codex' (line 13):**
Add `'claude'` and `'codex'` to the `ALLOWED_SHELLS` set.
PaneTabBar passes these as the `command` argument to `terminal:spawn`; without them in the set
the handler returns `'Shell not allowed'` before spawning anything.

**Bug 2 — Windows always spawns powershell.exe regardless of command (line 71):**
```ts
// CURRENT (broken on Windows):
const shell = process.platform === 'win32' ? 'powershell.exe' : (command ?? 'bash')
```
This ignores `command` on Windows entirely. Fix by resolving the correct binary per command:
```ts
function resolveShell(command: string | undefined): { shell: string; args: string[] } {
  if (process.platform !== 'win32') return { shell: command ?? 'bash', args: [] }
  // On Windows, CLI tools need cmd.exe /k so the window stays open after launch
  if (command === 'claude') return { shell: 'cmd.exe', args: ['/k', 'claude'] }
  if (command === 'codex')  return { shell: 'cmd.exe', args: ['/k', 'codex'] }
  return { shell: 'powershell.exe', args: [] }
}
const { shell, args: shellArgs } = resolveShell(command)  // replace the hardcoded shell/shellArgs lines
```
Replace the existing `const shell = ...` and `const shellArgs: string[] = []` lines with a call to `resolveShell`.
The rest of the `pty.spawn(shell, shellArgs, ...)` call is unchanged.

**Done when:** On Windows, A Claude tab opens Claude Code CLI (not PowerShell), Codex tab opens Codex CLI.

**Mac/Linux note — PATH may be restricted:**
On Mac and Linux, `resolveShell` spawns `claude`/`codex` directly (no wrapper needed).
However, Electron's main process inherits a restricted PATH — not the user's full shell PATH.
If the CLI was installed to a user-local path (e.g. `~/.npm-global/bin/claude`, `/opt/homebrew/bin/claude`)
that isn't in the system PATH, the spawn will fail with "command not found" even after this fix.
This is a pre-existing issue, not introduced here. If it surfaces during testing, the fix is to
resolve the full binary path at startup and pass it to `resolveShell`:
```ts
import { execSync } from 'child_process'
function findBin(name: string): string {
  try { return execSync(`which ${name}`, { encoding: 'utf8' }).trim() } catch { return name }
}
// Call once at app startup, cache results:
const CLAUDE_BIN = process.platform !== 'win32' ? findBin('claude') : 'claude'
const CODEX_BIN  = process.platform !== 'win32' ? findBin('codex')  : 'codex'
```
Then use `CLAUDE_BIN`/`CODEX_BIN` in `resolveShell` instead of the bare string `'claude'`/`'codex'`.
Only implement this if bare-name spawning fails in testing — don't pre-optimise.

---

## Phase 0b: Compact terminal dock   ← Conversation 0

**Files:** `studio/src/renderer/src/components/Terminal/index.tsx` — MODIFY,
`studio/src/renderer/src/components/Terminal/Terminal.module.css` (or equivalent) — MODIFY
**Done when:** Terminal area is 180px tall when a session is open; 72px when no session is open; no large blank dead zone
**Delivers:** S0.1
**Details:**
- Read the current height value (index.tsx line 18 is reportedly 260px) — confirm and change to 180px
- **Empty state (no open tabs):** shrink terminal area to 72px tall; replace "Press + to open a terminal"
  centered text with a compact inline row:
  ```
  No terminal open.    [+ Shell]  [Open Claude]  [Open Codex]
  ```
  Buttons call the existing `handleLaunch` function directly
- **Active state:** full 180px height, normal terminal output
- Transition: `height 150ms ease-out` when switching between empty and active states
- Do NOT change any PTY logic, spawning, or data flow

---

## Phase 0c: Session vs launcher hierarchy in tab bar   ← Conversation 0

**Files:** `studio/src/renderer/src/components/Terminal/PaneTabBar.tsx` — MODIFY,
CSS module — MODIFY
**Done when:** Active session tabs and new-session launcher buttons are visually distinct; active tab is clearly legible
**Delivers:** S0.2
**Details:**
- **Current problem:** `+ Shell`, `A Claude`, `✳ Codex` all look like identical tabs whether they are
  live sessions or launch buttons — no visual hierarchy
- **New layout:**
  ```
  Sessions: [● A Claude  ×]  [✳ Codex  ×]     │  New: [+ Shell] [+ Claude] [+ Codex]
  ```
  - Left side: open session tabs — filled background, colored dot (blue=Claude, amber=Codex),
    close `×` button per tab, active tab has accent-colored bottom border
  - Right side: launcher buttons — muted style, clearly secondary, separated by a `│` divider
  - If no sessions open: only launcher buttons visible (no empty tab strip)
- **Active tab style:** `background: var(--surface2)`, `border-bottom: 2px solid var(--accent)`,
  label full opacity; inactive tabs: `background: transparent`, 60% opacity
- **Split mode:** one shared dock header row; each pane has its own compact session tab strip
  below it (no duplicate full tab bars)
- Use existing Studio design tokens — do not introduce new colors

## Layer Architecture

```
Studio Renderer (React + Zustand + CSS Modules)
     │  matchIntent() — MiniLM via transformers.js (~22ms)
     │  POST /chat — phi4-mini explanation (SSE streaming)
     ▼
Pathly Python Server (http_server.py :8765)
     │  chat_agent.py — explainer only, NOT router
     ▼
Ollama (:11434) — phi4-mini
     │  streams 2-3 sentence explanation
     ▼
Back to Renderer → MatchCard + explanation bubble

Renderer calls window.pathly.terminal.write(tabId, "/pathly <skill>\n")
  OR                window.pathly.terminal.write(tabId, "Use Pathly <skill>\n")
                                              │  (same renderer → ptyOwners check passes)
                                              ▼
                                    Claude Code terminal tab
                                         OR
                                    Codex terminal tab
```

---

## Phase 1: GET /status endpoint   ← Conversation 1

> **ARCHITECTURE CORRECTION (post Conv 9):** The earlier claim that "WebGPU was validated" was
> incorrect. WebLLM (which relies on WebGPU) does not work in Electron's renderer process —
> Chromium inside Electron has WebGPU disabled by default, and the flags added (--enable-unsafe-webgpu
> etc.) are insufficient for the WebGPU compute shaders WebLLM needs. `webLLMEngine.ts` was
> removed in Conv 9. The replacement (`node-llama-cpp`) requires Electron 33+ / Node 22 for its
> native module loading to work; the current project targets Electron 28.
>
> **Correct LLM architecture (as of Conv 10 hotfix):**
> - **Primary backend: Ollama** (auto-detected at localhost:11434). Works on any Electron version.
>   Install via https://ollama.ai, then `ollama pull phi4-mini`. All 4 models supported.
> - **Secondary backend: node-llama-cpp** (GGUF local files). Requires upgrading to Electron 33+
>   in `devDependencies`. The IPC handlers already exist; the v3 API is already wired.
> - **Fallback: skill-only mode** (always works). MiniLM embedding routes intents to skills.
>   Chat responds with match information even with no LLM. Never blank.
>
> The Python server is only needed for FSM state (`/status`). No `chat_agent.py` needed.

**File:** `src/pathly_orchestrator/http_server.py` — MODIFY
**Done when:** `curl http://127.0.0.1:8765/status` returns current FSM stage without mutating state
**Delivers:** S1.2
**Details:**
- **Add route `GET /status`** — read-only FSM state endpoint:
  - Calls `read_state()` from `eventlog.py` (pure read, no write)
  - Returns `{ "current_state": str, "feature": str, "project_root": str }`
  - Returns `{ "current_state": "unknown" }` if no project loaded
  - **DO NOT call `/next_action` for context** — it writes `conv_start_sha` to disk on every call

---

## ~~Phase 2: phi4-mini explainer agent~~   ← REMOVED

> **Dead code — do not implement.**
> Explanation layer is handled by Ollama (or node-llama-cpp on Electron 33+) directly from the
> Electron main process via IPC. `chat_agent.py`, `chat_tools.py` are not needed.
> The Python server's only job is the read-only `/status` endpoint.

---

## ~~Phase 3: Context injection (Python side)~~   ← REMOVED

> **Dead code — do not implement.**
> Context (FSM stage, feature name, matched skill) is injected into the WebLLM system prompt
> directly in the renderer via `pathlyContext.ts` (Phase 12/14). No Python-side prompt building needed.

---

## Phase 4: Zustand chat store + model store   ← Conversation 2

**Files:** `studio/src/renderer/src/store/chatStore.ts` — CREATE,
`studio/src/renderer/src/store/modelStore.ts` — CREATE
**Done when:** `useChatStore()` and `useModelStore()` return all fields without TypeScript errors
**Delivers:** S2.2 (partial), S9.1 (partial)
**Details:**
- `chatStore`: follow pattern from existing `uiStore.ts`
  - Full state shape in DESIGN_SPEC.md → Zustand Store Shape
  - Key fields: `currentMatch`, `altMatches`, `isEmbedding`, `embedReady`
  - Persist: `autoApprove` only (matches and messages are session-only)
- `modelStore`: `selectedModelId: string`, `cachedModelIds: string[]`, `downloadProgress: Record<string, number>`
  - Actions: `setSelectedModel(id)`, `setCached(ids)`, `setProgress(id, pct)`
  - Persist: `selectedModelId` only (default `'Phi-4-mini-instruct-q4f16_1-MLC'`)

---

## Phase 5: uiStore additions   ← Conversation 2

**File:** `studio/src/renderer/src/store/uiStore.ts` — MODIFY
**Done when:** `chatOpen` and `skillsPanelOpen` toggle and persist across remounts
**Delivers:** S2.1 (partial)
**Details:**
- Add `chatOpen: boolean` (default `true`)
- Add `skillsPanelOpen: boolean` (default `true`)
- Add `toggleChat()` and `toggleSkillsPanel()` actions

---

## Phase 6: ConductorHeader component   ← Conversation 2

**File:** `studio/src/renderer/src/components/ChatPanel/ConductorHeader.tsx` — CREATE
**Done when:** Header renders with title, Manual/Auto toggle, Claude Code + Codex pills showing correct active/idle state
**Delivers:** S2.1 (partial)
**Details:**
- `⚡ Conductor` title in JetBrains Mono, accent #22C55E
- `[Manual]` / `[Auto]` toggle reads from `chatStore.autoApprove`
- CLI pills: Claude Code (#38BDF8), Codex (#F59E0B) — active = colored dot, idle = grey dot 0.45 opacity
- Collapse `[›]` button calls `uiStore.toggleChat()`

---

## Phase 7: SkillsPanel component   ← Conversation 2

**File:** `studio/src/renderer/src/components/ChatPanel/SkillsPanel.tsx` — CREATE
**Done when:** All 14 skill chips render; chip click creates a MatchCard for that skill; matched chip highlights
**Delivers:** S2.3
**Details:**
- Reads skills from `skillsManifest` (will be created in Conv 5; use a static fallback list for Conv 2)
- Static fallback list: `['plan','po','storm','build','review','test','retro','explore','debug','design','fix','status','log','end']`
- Chip: JetBrains Mono 10px, surface bg, border #475569
- Highlighted chip (when `chatStore.currentMatch?.skill.name === chip`): accent border + accent text
- Collapse toggle reads `uiStore.skillsPanelOpen`

---

## Phase 8: MessageList + ChatInput + Panel wiring + WebLLM engine   ← Conversation 2

> **Resize added (post-Conv 6 hotfix):** `ChatPanel/useChatResize.ts` was created and wired into
> `ChatPanel/index.tsx`. The panel has a draggable left-edge handle (260px–720px, persisted in
> `localStorage['chat-panel-width']`). The CSS variable `--chat-width` drives the width.
> No plan changes needed for Conv 7+; the resize is transparent to all other components.

**Files:** `MessageList.tsx`, `ChatInput.tsx`, `ChatPanel/index.tsx`, `App.tsx` — CREATE/MODIFY,
`studio/src/renderer/src/data/models.ts` — CREATE,
`studio/src/renderer/src/lib/webLLMEngine.ts` — CREATE
**Done when:** User can type a message, see it in the list, and receive a streaming WebLLM explanation (no Ollama, no placeholder)
**Delivers:** S2.1 (complete), S2.2, S9.3 (partial)
**Details:**
- `MessageList`: maps messages + renders MatchCard and OutputSnippet inline (not as separate bubbles)
- **EmptyState**: when `messages.length === 0`, render the empty state component instead of an empty list
  - If `fsmStage === "unknown"` or no active feature: show "What do you want to build?" with quick-start chips `[▸ po] [▸ plan] [▸ storm]`
  - If feature is active but no messages: show feature name + stage + "Describe what you want to do next"
  - Quick-start chips bypass embedding — clicking one immediately sets `currentMatch` to that skill
  - See DESIGN_SPEC.md → EmptyState for full visual spec
- `ChatInput`: textarea 1–3 rows, Enter = send, Shift+Enter = newline; `◈ MiniLM` pill (purple), model name pill (green, reads `modelStore.selectedModelId` short name); Send/Stop toggle
- `ChatPanel/index.tsx`: collapse animation `width 200ms ease-out`, 300px ↔ 36px
- `App.tsx`: add `<ChatPanel />` after `<MainPanel />` in body flex row
- **`data/models.ts`**: 4 model definitions — `Phi-4-mini-instruct-q4f16_1-MLC` (recommended, default), `Qwen3-4B-q4f16_1-MLC`, `Qwen2.5-Coder-7B-Instruct-q4f16_1-MLC`, `Llama-3.2-3B-Instruct-q4f16_1-MLC`
  - Each: `{ id, name, description, useCase, storage, speed, recommended? }`
- **`lib/llmBridge.ts`**: `askOllama(prompt, system, ollamaModelId, onChunk)` streaming via Ollama IPC,
  `askLlm(prompt, system, onChunk)` for node-llama-cpp (Electron 33+)
  - On message send: check Ollama availability → stream response via `llm:ollamaChat` IPC
  - On message send (no Ollama): check node-llama-cpp availability → stream via `llm:chat` IPC
  - On message send (neither): show skill-match fallback immediately — never blank
- **`lib/webLLMEngine.ts` is DELETED** — WebLLM does not work in Electron renderer
- Design: see DESIGN_SPEC.md → Full UI Layout (ASCII)

---

## Phase 9: MatchCard component   ← Conversation 3

**File:** `studio/src/renderer/src/components/ChatPanel/MatchCard.tsx` — CREATE
**Done when:** MatchCard renders green (≥65%) and amber (<65%) states; Run and Not this work
**Delivers:** S3.1
**Details:**
- Props: `match: MatchResult`, `alts: MatchResult[]`, `onRun: () => void`, `onReject: () => void`, `onSelectAlt: (skill) => void`
- Confidence bar: CSS width = `score * 100%`, green when ≥65%, amber when <65%
- Status label: `✓ MATCHED` (green) or `~ UNSURE` (amber)
- Alt chips: clickable, calls `onSelectAlt` — replaces current match
- Sent state: `opacity: 0.4`, shows `✓ Sent` label, Run/Not this hidden
- No match state (score < 0.4): text message instead of card
- See DESIGN_SPEC.md → MatchCard for full visual spec

---

## Phase 10: OutputSnippet component   ← Conversation 3

**File:** `studio/src/renderer/src/components/ChatPanel/OutputSnippet.tsx` — CREATE
**Done when:** After Run, OutputSnippet shows live PTY lines with ● Running / ✓ Done / ✗ Error status
**Delivers:** S3.2 (partial)
**Details:**
- Props: `target: "claude-code" | "codex"`, `status: "running" | "done" | "error"`, `lines: string[]`
- Shows last 5 lines from PTY output (ANSI stripped)
- Status color: running = amber, done = green, error = red
- `ChatPanel/index.tsx` subscribes to IPC output event and pipes to store

---

## Phase 11: Terminal write + launchTerminal utility   ← Conversation 3

**Files:** `studio/src/renderer/src/lib/launchTerminal.ts` — CREATE,
`studio/src/renderer/src/components/ChatPanel/index.tsx` — MODIFY
**Done when:** Clicking Run in MatchCard writes the correct host command to a terminal tab; auto-spawns if none exists
**Delivers:** S3.2

> Note: `ALLOWED_SHELLS` and Windows spawning were fixed in Phase 0a (Conv 0).
> No new Electron main-process IPC file needed — `window.pathly.terminal.*` already covers everything.
> ChatPanel is in the same renderer as Terminal (same `webContentsId`), so the existing
> `terminal:write` ownership check in `terminal.ts:103` passes transparently.

**Why no new IPC channel:**
The preload already exposes the full terminal API at `window.pathly.terminal`:
- `window.pathly.terminal.spawn(tabId, cwd, command?)` — spawns a PTY
- `window.pathly.terminal.write(tabId, data)` — writes to a PTY
- `window.pathly.terminal.onData(tabId, cb)` — subscribes to PTY output
ChatPanel can call these directly. The `ptyOwners` check in `terminal:write` passes because
ChatPanel and Terminal share the same `webContents.id` (same BrowserWindow renderer).

**Create `launchTerminal.ts` (shared renderer utility):**

Mirrors exactly what `Terminal/index.tsx handleLaunch` does (lines 77–87):
opens the dock if closed, generates a UUID, adds tab to store, spawns PTY.
```typescript
import { useTerminalStore } from '../store/terminalStore'
import { useProjectStore } from '../store/projectStore'

export async function launchTerminal(kind: 'claude' | 'codex'): Promise<string> {
  const { open, toggle, addTab } = useTerminalStore.getState()
  if (!open) toggle()                             // open the dock (mirrors handleLaunch:77)
  const tabId = crypto.randomUUID()              // matches Terminal/index.tsx:78 — no uuid package
  const label = kind === 'claude' ? 'A Claude' : '✳ Codex'
  const cwd = useProjectStore.getState().projectPath  // must match project root (not userHome)
  addTab(tabId, label, 'left', kind)
  await window.pathly.terminal.spawn(tabId, cwd, kind)
  return tabId
}
```
`cwd` must be `projectPath` — Claude Code needs to run in the project root for `/pathly` commands
to find the right FSM state. `userHome()` would disconnect commands from the active project.
`crypto.randomUUID()` is already used in Terminal/index.tsx — do NOT add a `uuid` package.

**Target terminal selection — chatStore `targetKind`:**
Add `targetKind: 'claude' | 'codex'` to `chatStore` (default `'claude'`).
The ConductorHeader host pill toggles it. The Run action reads it:
```typescript
// In chatStore:
targetKind: 'claude' as 'claude' | 'codex',
setTargetKind: (k) => set({ targetKind: k }),
```
This makes the pill the single source of truth — no ambiguity about which terminal Run targets.

**Renderer side (ChatPanel/index.tsx):**
```typescript
import { launchTerminal } from '../../lib/launchTerminal'

// On Run click:
const { targetKind } = useChatStore()              // targetKind driven by host pill
const { tabs } = useTerminalStore()                // tabs live in terminalStore, not chatStore
let targetTab = tabs.find(t => t.kind === targetKind)

if (!targetTab) {
  const tabId = await launchTerminal(targetKind)
  targetTab = useTerminalStore.getState().tabs.find(t => t.id === tabId)!
}

// Sanitize: strip ;, &&, ||, |, >, <
const safe = skill.command.replace(/[;&|><]/g, '').trim()

// Host-correct format:
const cmd = targetTab.kind === 'claude'
  ? `/pathly ${safe}`           // Claude Code: slash command
  : `Use Pathly ${safe}`        // Codex: natural-language plugin prompt

window.pathly.terminal.write(targetTab.id, cmd + '\n')
```

**OutputSnippet PTY subscription:**
```typescript
useEffect(() => {
  if (!activeTabId) return
  const unsub = window.pathly.terminal.onData(activeTabId, (data) => {
    // strip ANSI, append to outputLines in chatStore
  })
  return unsub
}, [activeTabId])
```

---

## Phase 12: pathlyContext builder   ← Conversation 4

**File:** `studio/src/renderer/src/lib/pathlyContext.ts` — CREATE
**Done when:** `buildPathlyContext()` returns `{ fsmStage, featureName, skills }` (no `screenElements` — static schema handles UI layout from Conv 6)
**Delivers:** S4.1, S4.2
**Details:**
- Fetch `http://127.0.0.1:8765/status` (GET) → extract `current_state` and `feature`
  **DO NOT use `/next_action`** — it mutates FSM state (writes `conv_start_sha` to disk)
  The `/status` endpoint was added in Phase 1 and is purely read-only.
- `KNOWN_SKILLS`: static list from skills.json (will be dynamic in Conv 5)
- Wrap FSM fetch in try/catch → fallback `fsmStage: "unknown"`

---

## ~~Phase 13: Copy PageAnalyzer from BrightSky~~   ← REMOVED

> **Dead code — do not implement.**
> The architecture moved to a static Studio schema (Phase 19, Conv 6) and Playwright CDP
> executor (Phase 21, Conv 7). `screenElements` (DOM-based) is no longer returned by
> `buildPathlyContext()` and nothing in the final architecture consumes it.
> `usePageAnalyzer`, `analyzePageDirect`, and `data-conductor-id` are explicitly prohibited
> — see "What NOT to Build" in DESIGN_SPEC.md.

---

## Phase 14: Inject context per message   ← Conversation 4

**File:** `studio/src/renderer/src/components/ChatPanel/index.tsx` — MODIFY
**Done when:** phi4-mini explanation correctly names the FSM stage and feature
**Delivers:** S4.1, S4.2 (complete)
**Details:**
- Call `buildPathlyContext()` before each POST /chat
- Add `context` field to request body

---

## Phase 15: skills.json data file   ← Conversation 5

**File:** `studio/src/renderer/src/data/skills.json` — CREATE
**Done when:** File is valid JSON with 14 skills, each with `name`, `command`, `description`
**Delivers:** S5.2 (partial)
**Details:**
- 14 skills: plan, po, storm, build, review, test, retro, explore, debug, design, fix, status, log, end
- Each skill needs a **specific** description (1–2 sentences, includes WHEN to use it)
- Example: `{ "name": "build", "command": "/pathly build", "description": "Spawn the builder agent to implement the feature. Use when the implementation plan is written and approved and you're ready to write code." }`

---

## Phase 16: skillsManifest loader   ← Conversation 5

**File:** `studio/src/renderer/src/lib/skillsManifest.ts` — CREATE
**Done when:** `loadSkills()` returns typed `Skill[]` without errors
**Delivers:** S5.1 (partial)
**Details:**
- `interface Skill { name: string; command: string; description: string; vector?: number[] }`
- `loadSkills(): Skill[]` — imports skills.json, returns typed array
- `vector` field is populated by embedRouter at startup, not stored in JSON

---

## Phase 17: embedRouter — MiniLM wrapper   ← Conversation 5

**File:** `studio/src/renderer/src/lib/embedRouter.ts` — CREATE
**Done when:** `matchIntent("I want to build")` returns `[{ skill: "build", score: ~0.92, command: "/pathly build" }, ...]`
**Delivers:** S5.1, S5.2
**Details:**
- Load model at startup: `const embedder = await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2')`
- `preEmbedSkills(skills: Skill[]): Promise<void>` — embeds all skill descriptions at startup
- `matchIntent(input: string): MatchResult[]` — embeds input, cosine similarity, returns top 3
- `cosineSim(a: number[], b: number[]): number` — utility function
- Signal `embedReady: true` to chatStore when preEmbedSkills completes

---

## Phase 18: Wire embedding into send flow   ← Conversation 5

**Files:** `ChatPanel/index.tsx` — MODIFY, `chatStore.ts` — MODIFY
**Done when:** MatchCard renders < 50ms after send; all 5 test phrases match correctly (see S5.2)
**Delivers:** S5.2, S5.3 (complete)
**Details:**
- On message send: call `matchIntent(input)` → `setMatch(topMatch, altMatches)`
- MatchCard renders from `chatStore.currentMatch` — no waiting for phi4-mini
- POST /chat fires async in parallel with MatchCard render
- Add `{ matchedSkill, skillDescription }` to POST /chat body
- If `topMatch.score < 0.4`: show no-match message, skip MatchCard, still send to phi4-mini
- If `autoApprove && topMatch.score >= 0.65`: auto-invoke Run after phi4-mini explanation completes

---

---

## Phase 19: Static Studio schema   ← Conversation 6 ✓ DONE

**Files (actual locations after Conv 6 review):**
- `studio/src/renderer/src/lib/studioSchema.ts` — created (canonical location)
- `studio/src/renderer/src/types/studio.ts` — created (`StudioElement` interface)
- `studio/src/renderer/src/data/studioSchema.ts` — backward-compat re-export shim
**Done when:** `getStudioSchema()` returns typed description of all key Studio UI elements
**Delivers:** S6.1
**Details:**
- `StudioElement: { id: string; screen: string; type: 'button'|'input'|'select'|'panel'; label: string; description: string }`
- Define elements for these screens (read the actual Studio source to get real labels):
  - `FlowEditor` screen: "New Flow" button, flow name input, flow list panel
  - `StepEditor` screen: "Add Step" button, step type selector, step name input, URL input field, "Save" button
  - `ChatPanel` screen: send button, message input
  - Modals: "Save" button, "Cancel" button, "Delete" button
- `getStudioSchema(): StudioElement[]` — returns the full static list
- `getSchemaForScreen(screen: string): StudioElement[]` — filters by screen name
- This is NOT a runtime registry — it is a typed constant that describes the app
- Do NOT add `usePageAnalyzer` hooks or `data-conductor-id` attributes anywhere

---

## Phase 20: Inject schema into AI context   ← Conversation 6 ✓ DONE

**File:** `studio/src/renderer/src/lib/pathlyContext.ts` — MODIFY
**Done when:** POST /chat includes `studioSchema` and AI system prompt references element labels
**Delivers:** S6.2
**Details:**
- Import `getStudioSchema` from `./studioSchema` (i.e., `lib/studioSchema.ts`) — the `data/` shim re-exports it but use the canonical `lib/` path
- Add `studioSchema: StudioElement[]` to `buildPathlyContext()` return type and value
- Pass `studioSchema` in POST /chat body
- In `src/pathly_orchestrator/chat_agent.py`: add `## Studio UI Elements` section to system prompt listing elements grouped by screen: "FlowEditor: [New Flow (button)], [Flow Name (input)]..."
- AI instruction in prompt: "When generating automation steps, use only labels from this list"
- Cap schema contribution at 400 tokens

---

## Phase 21: Playwright executor — 3-tier cascade   ← Conversation 7

**Files:** `studio/src/main/automation/playwrightExecutor.ts` — CREATE, `studio/src/main/index.ts` — MODIFY
**Done when:** `executeStep({ type: 'click', label: 'New Flow' })` clicks the matching element in Studio
**Delivers:** S7.1, S7.2, S7.3
**Details:**
- Add `@playwright/test` to `studio/package.json` (Electron support via `_electron`)
- `PlaywrightExecutor` class in main process:
  - `connect(cdpUrl: string): Promise<void>` — connects Playwright to the Electron window using `chromium.connectOverCDP`
  - `executeStep(step: AutomationStep): Promise<StepResult>` — delegates to `resolveElement` then performs the action
  - For `click`: `.click()`, for `fill`: `.fill(value)`, for `select`: `.selectOption(value)`
  - `resolveElement(label: string)` implements the 3-tier cascade (see below); wrapped in self-healing loop
- `AutomationStep: { type: 'click'|'fill'|'select'; label: string; value?: string; screen?: string }`
- `StepResult: { ok: boolean; error?: string; attempts?: number }`
- `export const playwrightExecutor = new PlaywrightExecutor()` — singleton
- Initialize after app is ready in `index.ts`: `app.commandLine.appendSwitch('remote-debugging-port', '9222')` BEFORE BrowserWindow creation, then `await playwrightExecutor.connect('http://localhost:9222')` after app ready

**Self-healing wrapper (wraps all 3 tiers):**
- Max 3 attempts; exponential backoff: 500ms → 1000ms → 1500ms
- On each retry: re-run full cascade from Tier 1 (page may have re-rendered)
- If element found but `isDisabled()`: wait 800ms and retry (disabled → enabled transition)
- On final failure: return `{ ok: false, error: '...', attempts: 3 }`

**Tier 1 — Deterministic (0–5ms, always runs first):**
Try each strategy in order; return the first that yields exactly 1 match.
1. `getByRole('button', { name: label })`
2. `getByRole('combobox', { name: label })`
3. `getByRole('textbox', { name: label })`
4. `getByRole('link', { name: label })`
5. `getByRole('tab', { name: label })`
6. `getByLabel(label)` — aria-label attribute
7. `getByPlaceholder(label)`
8. `getByText(label, { exact: true })`
9. `getByText(label, { exact: false })`
10. `locator('[title="${label}"]')`

If a strategy returns multiple matches → filter to `.filter({ hasNot: page.locator('[hidden]') })` (visible only). If still multiple → continue to next strategy.
If Tier 1 yields exactly 1 match → use it. If 0 or ambiguous after all 10 → fall through to Tier 2.

**Tier 2 — MiniLM semantic similarity (~50ms, runs when Tier 1 finds 0 or ambiguous):**
1. Get page accessibility snapshot: `await page.accessibility.snapshot()`
2. Walk snapshot recursively; collect all `{ name, role }` pairs for interactable nodes
3. Call `semanticResolve` callback (injected from IPC layer, see Phase 22): `await semanticResolve(candidates, target)` → `{ label: string; score: number }`
4. If score ≥ 0.65: locate via `page.getByRole(role, { name: label })`
5. If score < 0.65: fall through to Tier 3

**Tier 3 — phi4-mini LLM fallback (~2–5s, last resort — stub in Conv 7, filled in Conv 9):**
1. Call `llmResolve` callback (injected from IPC layer): `await llmResolve(candidates, target)` → `{ label: string | null }`
2. If label returned: locate by name
3. If null: return `{ ok: false, error: 'element not found after all tiers: ${target}' }`

Note: In Conv 7, `llmResolve` is wired as a stub that always returns `{ label: null }`. The interface is defined now so Conv 9 can fill it in without touching this file.

**Constructor injection pattern:**
`PlaywrightExecutor` accepts optional callbacks:
```
constructor(
  private semanticResolve: (candidates: string[], target: string) => Promise<{label: string; score: number}> = async () => ({ label: '', score: 0 }),
  private llmResolve: (candidates: string[], target: string) => Promise<{label: string | null}> = async () => ({ label: null })
) {}
```
The IPC layer (Phase 22) creates the singleton with real callbacks wired to the round-trip IPC pattern.

---

## Phase 21.5: elementResolver.ts (renderer-side semantic + LLM resolution)   ← Conversation 7

**File:** `studio/src/renderer/src/lib/elementResolver.ts` — CREATE
**Done when:** File exports `handleSemanticResolve` and `handleLLMResolve`; no TS errors
**Delivers:** S7.2 (semantic tier), S7.3 (LLM tier stub)
**Details:**

`handleSemanticResolve(candidates: string[], target: string): Promise<{label: string; score: number}>`
- Uses `embed(text)` exported from `embedRouter.ts` (shares the same MiniLM singleton — no double-init)
- Embeds `target` and all `candidates`, computes cosine similarity using `cosineSim` from `embedRouter.ts`
- Returns `{ label, score }` for the top match

`handleLLMResolve(candidates: string[], target: string): Promise<{label: string | null}>`
- Placeholder in Conv 7: checks if WebLLM engine is loaded (from Conv 9's `webLLMEngine.ts`); returns `{ label: null }` if not
- When Conv 9 ships: builds prompt `"Page elements: [list]. Which element should I interact with to '${target}'? Reply with just the element name."` and calls `webLLMEngine.generate(prompt)`

**IPC listener registration (called once at renderer startup):**
```
ipcRenderer.on('automation:semantic-resolve', async (event, { candidates, target }) => {
  const result = await handleSemanticResolve(candidates, target)
  event.sender.send('automation:semantic-resolve:result', result)
})
ipcRenderer.on('automation:llm-resolve', async (event, { candidates, target }) => {
  const result = await handleLLMResolve(candidates, target)
  event.sender.send('automation:llm-resolve:result', result)
})
```
Register these listeners in the renderer entry point (e.g., `main.tsx` or a dedicated init call).

---

## Phase 22: IPC automation handler   ← Conversation 7

**Files:** `studio/src/main/ipc/automation.ts` — CREATE, `studio/src/main/index.ts` — MODIFY
**Done when:** `ipcRenderer.invoke('automation:execute-step', step)` executes via Playwright
**Delivers:** S7.1, S7.2, S7.3 (complete)
**Details:**
- `ipcMain.handle('automation:execute-step', async (event, step: AutomationStep) => playwrightExecutor.executeStep(step))`
- Expose on preload: `window.electronAPI.executeAutomationStep(step: AutomationStep): Promise<StepResult>`
- Register in `index.ts` alongside other IPC handlers
- Do NOT use `webContents.executeJavaScript`, `data-conductor-id`, or `window.__uiExecutor`

**Main → renderer round-trip IPC for Tiers 2 and 3:**
Use the send/once pattern so main can call renderer-side logic:
```
// In automation.ts (main side)
function makeRendererCaller(channel: string) {
  return (candidates: string[], target: string) =>
    new Promise<any>((resolve) => {
      const win = BrowserWindow.getAllWindows()[0]
      win.webContents.send(`${channel}`, { candidates, target })
      ipcMain.once(`${channel}:result`, (_e, result) => resolve(result))
    })
}

const semanticResolve = makeRendererCaller('automation:semantic-resolve')
const llmResolve      = makeRendererCaller('automation:llm-resolve')

export const playwrightExecutor = new PlaywrightExecutor(semanticResolve, llmResolve)
```
Note: the singleton is created here (not in `playwrightExecutor.ts`) so callbacks are available at construction time. `playwrightExecutor.ts` exports only the class.

**Preload additions:**
- `automation:semantic-resolve` and `automation:llm-resolve` are main→renderer pushes, not invokes — no preload exposure needed for these channels
- `automation:execute-step` remains the only invoke the renderer calls

---

## Phase 23: automationStore + step queue state   ← Conversation 8

**File:** `studio/src/renderer/src/store/automationStore.ts` — CREATE
**Done when:** `useAutomationStore()` returns typed state without TS errors
**Delivers:** S8.1 (partial)
**Details:**
- State: `steps: AutomationStep[]`, `currentStepIndex: number`, `mode: 'staged' | 'auto'`, `status: 'idle' | 'running' | 'paused' | 'done' | 'error'`
- `AutomationStep: { id: string; description: string; action: UIAction; status: 'pending' | 'approved' | 'skipped' | 'done' | 'error' }`
- Actions: `setSteps(steps)`, `approveStep(id)`, `skipStep(id)`, `setMode(mode)`, `reset()`
- Persist: `mode` only — steps are session-only

---

## Phase 25: StepQueue + AutomationCard components   ← Conversation 8

**Files:** `studio/src/renderer/src/components/ChatPanel/StepQueue.tsx` — CREATE,
`studio/src/renderer/src/components/ChatPanel/AutomationCard.tsx` — CREATE
**Done when:** Staged mode shows step cards with Approve/Skip; Auto mode runs silently with a progress bar
**Delivers:** S8.1, S8.2, S8.3
**Details:**
- `AutomationCard`: shows AI's action plan summary (step count, intent description), `[▶ Run All]` and `[Step by Step]` buttons — sets `automationStore.mode`
- `StepQueue` (staged mode):
  - Shows all steps as cards: step number, description, action preview (`click "Add Step"`)
  - Current step: highlighted, `[✓ Approve]` `[→ Skip]` buttons
  - Completed steps: dimmed with `✓` or `→` badge
  - Pending steps: grey, no buttons
- `StepQueue` (auto mode): single progress bar, step count `2 / 5`, `[■ Stop]` button
- Both modes: live feedback when each action executes — element flashes accent color for 400ms

---

## Phase 26: Wire AI → action plan in chat flow   ← Conversation 8

**Files:** `ChatPanel/index.tsx` — MODIFY, `chatStore.ts` — MODIFY,
`src/pathly_orchestrator/chat_agent.py` — MODIFY
**Done when:** User types "create a checkout flow" → AI returns action steps → AutomationCard appears → Approve executes actions
**Delivers:** S8.4 (complete)
**Details:**
- Extend `POST /chat` request to include `studioSchema` and `mode: 'automation'` flag
- `AutomationStep: { type: 'click'|'fill'|'select'; label: string; value?: string; screen?: string }` — use `label` not `elementId`
- When `mode === 'automation'`: `chat_agent.py` returns structured JSON steps instead of plain text:
  ```json
  { "type": "automation", "intent": "...", "steps": [{ "description": "...", "action": { "type": "click", "label": "New Flow", "screen": "FlowEditor" } }] }
  ```
- AI must only use labels from `studioSchema` when generating steps — enforce via system prompt
- On receive: parse steps → `automationStore.setSteps(steps)` → render `AutomationCard` in message list
- Staged: `StepQueue` calls `window.electronAPI.executeAutomationStep(step)` → advances to next step on approve
- Auto: loop through all steps calling `window.electronAPI.executeAutomationStep(step)` with 300ms delay between each
- After all steps done: AI sends summary message "Flow created — 5 steps executed"
- Remove all references to `executeAction()`, `actionExecutor.ts`, `data-conductor-id`, `window.__uiExecutor`

---

## ~~Phase 27–29: WebLLM engine + model store + wire into chat~~   ← MERGED INTO CONV 2

> **WebGPU validated before Conv 1.** WebLLM engine, model definitions, and modelStore were
> moved into Phase 8 (Conv 2) so the explanation layer is local from the very first message.
> Conv 9 no longer exists as a separate track — it has been fully absorbed.
> `chat_agent.py`, `chat_tools.py`, and Ollama are not part of this plan.

---

## Prerequisites
- MiniLM auto-downloads via transformers.js (~22MB, first launch only) — always works
- **Ollama (recommended):** Install from https://ollama.ai, then `ollama pull phi4-mini`.
  Ollama is auto-detected at localhost:11434. No env-var needed.
  Available models: `phi4-mini:latest` (~2.5GB), `qwen3:4b` (~2.6GB), `qwen2.5-coder:7b` (~4.7GB), `llama3.2:3b` (~2GB)
- **node-llama-cpp (future):** Requires upgrading `electron` to `^33.0.0` in devDependencies.
  Run `npm install` after upgrade. All IPC handlers already exist in `studio/src/main/ipc/llm.ts`.
- **WebGPU / WebLLM: NOT usable.** WebLLM was removed — WebGPU is disabled inside Electron's
  renderer process and cannot run the compute shaders required by WebLLM. Do not re-add WebLLM.
- Pathly FSM server running on port 8765 before testing Conv 1

## Key Decisions
- **Embedding over LLM for routing:** Zero hallucination, 22ms, deterministic. See ARCHITECTURE_PROPOSAL.md Decision 1.
- **phi4-mini as explainer only:** Routing and explaining are separate concerns with different latency needs.
- **Skills are the command vocabulary:** All commands are Pathly skills. Claude Code and Codex are terminal surfaces, not routing targets.
- **Pre-embed at startup:** Ensures first-message latency is instant. 14 skills × ~384 dimensions = negligible memory.
- **Confidence threshold UI:** Users need to see and understand match quality to trust the system.
