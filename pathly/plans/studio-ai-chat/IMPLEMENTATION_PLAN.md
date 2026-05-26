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

## Phase 0a: Fix ALLOWED_SHELLS   ← Conversation 0

**File:** `studio/src/main/ipc/terminal.ts` — MODIFY
**Done when:** Clicking `A Claude` and `✳ Codex` buttons in Studio launches terminal tabs without error
**Delivers:** S0.3
**Details:**
- Line 13: `ALLOWED_SHELLS` only contains bash/zsh/shell variants — add `'claude'` and `'codex'`
- This is an existing bug: the PaneTabBar passes `'claude'`/`'codex'` as the command to `terminal:spawn`,
  which the allowlist rejects with "Shell not allowed"
- After this fix, Claude Code and Codex tabs will open correctly

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

Renderer ──IPC 'chat:write-terminal'──► Electron Main
                                              │  node-pty.write("/pathly <skill>\n")
                                              ▼
                                    Claude Code terminal tab
                                         OR
                                    Codex terminal tab
```

---

## Phase 1: POST /chat SSE endpoint skeleton + GET /status   ← Conversation 1

**File:** `src/pathly_orchestrator/http_server.py` — MODIFY
**Done when:** `curl -X POST http://127.0.0.1:8765/chat ...` returns 200 AND `curl http://127.0.0.1:8765/status` returns current FSM stage without mutating state
**Delivers:** S1.1 (partial), S1.2 (partial)
**Details:**
- Add route `/chat` accepting POST: `{ message, matchedSkill, skillDescription, history, context }`
- Return `Content-Type: text/event-stream`
- Static placeholder: `data: {"text": "chat endpoint ready"}\n\n`
- Add `ollama>=0.3` to `pyproject.toml`
- **Add route `GET /status`** — read-only FSM state endpoint:
  - Calls `read_state()` from `fsm_ops.py` (pure read, no write)
  - Returns `{ "current_state": str, "feature": str, "project_root": str }`
  - Returns `{ "current_state": "unknown" }` if no project loaded
  - **DO NOT call `/next_action` for context** — it writes `conv_start_sha` to disk on every call
  - This endpoint is the safe replacement for context reads throughout the feature

---

## Phase 2: phi4-mini explainer agent   ← Conversation 1

**File:** `src/pathly_orchestrator/chat_agent.py` — CREATE
**Done when:** `/chat` streams a 2-3 sentence explanation referencing the matched skill and FSM stage
**Delivers:** S1.1
**Details:**
- `ChatAgent` class with `stream(message, matchedSkill, context, history) -> AsyncGenerator[str]`
- System prompt: **explainer role** (see DESIGN_SPEC.md → phi4-mini System Prompt)
- Calls `ollama.AsyncClient().chat()` with model from `PATHLY_CHAT_MODEL` (default `phi4-mini`)
- Streams chunks as SSE: `data: {"text": "..."}\n\n`
- On Ollama error: yield `data: {"error": "Ollama offline"}\n\n` — MatchCard still works without this

---

## Phase 3: Context injection   ← Conversation 1

**File:** `src/pathly_orchestrator/chat_tools.py` — CREATE
**Done when:** phi4-mini explanation mentions the current FSM stage by name
**Delivers:** S1.2
**Details:**
- `get_fsm_state(project_root) -> dict` — calls `read_state()` from `fsm_ops.py` directly (pure read)
  **DO NOT call `/next_action`** — it writes `conv_start_sha` to disk. Use `read_state()` only.
- `read_plan_summary(project_root) -> str` — reads most-recently-modified `plans/*/FEATURE_INDEX.md`
- Inject into system prompt: `Stage: {fsm_stage} | Feature: {feature_name} | Matched skill: {skill}`
- Total system prompt cap: 1,000 tokens (explainer context is smaller than general chat)

---

## Phase 4: Zustand chat store   ← Conversation 2

**File:** `studio/src/renderer/src/store/chatStore.ts` — CREATE
**Done when:** `useChatStore()` returns all fields without TypeScript errors
**Delivers:** S2.2 (partial)
**Details:**
- Follow pattern from existing `uiStore.ts`
- Full state shape in DESIGN_SPEC.md → Zustand Store Shape
- Key additions over a simple message store: `currentMatch`, `altMatches`, `isEmbedding`, `embedReady`
- Persist: `autoApprove` only (matches and messages are session-only)

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

## Phase 8: MessageList + ChatInput + Panel wiring   ← Conversation 2

**Files:** `MessageList.tsx`, `ChatInput.tsx`, `ChatPanel/index.tsx`, `App.tsx` — CREATE/MODIFY
**Done when:** User can type a message, see it in the list, and see a placeholder MatchCard (static for now)
**Delivers:** S2.1 (complete), S2.2
**Details:**
- `MessageList`: maps messages + renders MatchCard and OutputSnippet inline (not as separate bubbles)
- **EmptyState**: when `messages.length === 0`, render the empty state component instead of an empty list
  - If `fsmStage === "unknown"` or no active feature: show "What do you want to build?" with quick-start chips `[▸ po] [▸ plan] [▸ storm]`
  - If feature is active but no messages: show feature name + stage + "Describe what you want to do next"
  - Quick-start chips bypass embedding — clicking one immediately sets `currentMatch` to that skill
  - See DESIGN_SPEC.md → EmptyState for full visual spec
- `ChatInput`: textarea 1–3 rows, Enter = send, Shift+Enter = newline; `◈ MiniLM` pill (purple), `phi4-mini` pill (green); Send/Stop toggle
- `ChatPanel/index.tsx`: collapse animation `width 200ms ease-out`, 300px ↔ 36px
- `App.tsx`: add `<ChatPanel />` after `<MainPanel />` in body flex row
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

## Phase 11: IPC terminal write handler   ← Conversation 3

**Files:** `studio/src/main/ipc/chat.ts` — CREATE, `studio/src/main/index.ts` — MODIFY,
`studio/src/main/ipc/terminal.ts` — MODIFY (ALLOWED_SHELLS pre-flight fix)
**Done when:** `ipcRenderer.invoke('chat:write-terminal', { command, tabId })` writes to the correct PTY tab
**Delivers:** S3.2

**Pre-flight fix (do this first):**
Read `studio/src/main/ipc/terminal.ts` line 13. The `ALLOWED_SHELLS` set only contains bash/zsh/shell variants.
Add `'claude'` and `'codex'` to `ALLOWED_SHELLS` — they are valid execution targets.
Without this fix, the existing Claude Code and Codex terminal buttons are broken.

**IPC handler design:**
- `ipcMain.handle('chat:write-terminal', (event, { command, tabId }) => { ... })`
- PTYs are keyed by **UUID tabId** in `activePtys` — NOT by string names like "claude-code"
- The renderer is responsible for resolving `tabId` from `terminalStore` before calling this IPC
- Main process simply does: `activePtys.get(tabId)?.write(command + '\n')`
- Sanitize command before write: strip `;`, `&&`, `||`, `|`, `>`, `<`. Log warning if stripped.
- Return `{ ok: true }` or `{ error: string }`
- Expose on preload: `window.electronAPI.writeToTerminal(command: string, tabId: string): Promise<{ok?:boolean, error?:string}>`
- Register in `index.ts` alongside other IPC handlers

**Renderer side (in ChatPanel/index.tsx):**
- Before calling IPC, look up target tab from `terminalStore`:
  ```typescript
  const { tabs, activeTabIdLeft } = useTerminalStore()
  const claudeTab = tabs.find(t => t.kind === 'claude')
  ```
- **Auto-spawn if no claude tab:** call `handleLaunch('claude')` — this is the same function
  the terminal `+` button uses. It lives in the renderer (Terminal/index.tsx). Import or
  lift it so ChatPanel can call it. Wait for the tab to appear in terminalStore.
- Generate **host-correct command**:
  ```typescript
  const command = tab.kind === 'claude'
    ? `/pathly ${skill.name}`       // Claude Code: slash command
    : `Use Pathly ${skill.name}`    // Codex: natural-language plugin prompt
  ```
- Then call `window.electronAPI.writeToTerminal(command, tab.id)`
- **Result:** user can use Conductor with zero terminals open — Run opens one automatically

---

## Phase 12: pathlyContext builder   ← Conversation 4

**File:** `studio/src/renderer/src/lib/pathlyContext.ts` — CREATE
**Done when:** `buildPathlyContext()` returns `{ fsmStage, featureName, screenElements, skills }`
**Delivers:** S4.1, S4.2
**Details:**
- Fetch `http://127.0.0.1:8765/status` (GET) → extract `current_state` and `feature`
  **DO NOT use `/next_action`** — it mutates FSM state (writes `conv_start_sha` to disk)
  The `/status` endpoint was added in Phase 1 and is purely read-only.
- `KNOWN_SKILLS`: static list from skills.json (will be dynamic in Conv 5)
- Wrap FSM fetch in try/catch → fallback `fsmStage: "unknown"`
- Cap screen elements at 20 buttons + 10 forms + 10 text blocks

---

## Phase 13: Copy PageAnalyzer from BrightSky   ← Conversation 4

**File:** `studio/src/renderer/src/lib/pageAnalyzer/` — CREATE
**Done when:** `import { analyzePageDirect } from '../lib/pageAnalyzer/utils/analyzePageDirect'` compiles
**Delivers:** S4.1 (partial)
**Details:**
- Copy from `C:\Users\Yafit\brightsky-ai\frontend\src\components\PageAnalyzer\`:
  `analyzePageDirect.ts`, `CacheManager.ts`, `DOMAnalyzer2.ts`, `ButtonAnalyzer.ts`,
  `FormAnalyzer.ts`, `TextAnalyzer.ts`, `LinkAnalyzer.ts`
- Fix imports referencing `@brightsky-ai/shared` — replace with inline types
- Do NOT copy Redux-dependent files

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

## Phase 19: usePageAnalyzer hook   ← Conversation 6

**File:** `studio/src/renderer/src/hooks/usePageAnalyzer.ts` — CREATE
**Done when:** Any component calling `usePageAnalyzer({ id, type, label })` appears in the registry
**Delivers:** S6.1
**Details:**
- `usePageAnalyzer(meta: ElementMeta): void` — registers element on mount, unregisters on unmount
- `ElementMeta: { id: string; type: 'button' | 'input' | 'select' | 'link' | 'panel'; label: string; value?: string; disabled?: boolean; visible?: boolean }`
- On mount: `pageAnalyzerStore.register(meta)`
- On unmount: `pageAnalyzerStore.unregister(meta.id)`
- On value/disabled change: `pageAnalyzerStore.update(id, patch)` — called via `useEffect` deps

---

## Phase 20: pageAnalyzerStore + getPageContext()   ← Conversation 6

**Files:** `studio/src/renderer/src/store/pageAnalyzerStore.ts` — CREATE,
`studio/src/renderer/src/lib/pageAnalyzer/index.ts` — CREATE
**Done when:** `getPageContext()` returns a JSON snapshot of all currently registered elements
**Delivers:** S6.2, S6.3
**Details:**
- Zustand store: `elements: Map<string, ElementMeta>`, `register()`, `unregister()`, `update()`
- `getPageContext(): PageContext` — reads store, returns `{ elements: ElementMeta[], timestamp: number }`
- Cap at 50 elements — if more registered, prioritize by `type` order: input > button > select > panel > link
- Add `usePageAnalyzer` calls to key Studio components:
  - `FlowEditor`: register flow canvas panel + "New Flow" button
  - `StepEditor`: register all step form inputs + "Add Step" button + step type selector
  - `ChatPanel`: register send button + input textarea
  - Any modal or dialog that opens — register its CTA buttons

---

## Phase 21: Inject page context into pathlyContext   ← Conversation 6

**File:** `studio/src/renderer/src/lib/pathlyContext.ts` — MODIFY
**Done when:** `buildPathlyContext()` includes `pageContext` in its return value
**Delivers:** S6.2 (complete)
**Details:**
- Import `getPageContext` from `pageAnalyzer/index.ts`
- Add `pageContext: PageContext` to the return type
- Pass `pageContext` in the POST /chat body alongside `fsmStage`, `featureName`, `skills`
- System prompt in `chat_agent.py`: add section `## Current UI Elements` listing registered elements
- Cap page context contribution at 300 tokens

---

## Phase 22: Action Executor — IPC handler   ← Conversation 7

**File:** `studio/src/main/ipc/uiActions.ts` — CREATE, `studio/src/main/index.ts` — MODIFY
**Done when:** `ipcRenderer.invoke('ui:execute-action', action)` clicks/fills the target element
**Delivers:** S7.1, S7.2, S7.3
**Details:**
- `ipcMain.handle('ui:execute-action', (event, action: UIAction) => { ... })`
- `UIAction: { type: 'click' | 'fill' | 'select'; elementId: string; value?: string }`
- Main process forwards to renderer via `webContents.executeJavaScript`:
  ```ts
  `window.__uiExecutor?.execute(${JSON.stringify(action)})`
  ```
- Expose on preload: `window.electronAPI.executeUIAction(action: UIAction): Promise<{ok: boolean; error?: string}>`
- Register in `index.ts` alongside other IPC handlers

---

## Phase 23: Action Executor — renderer side   ← Conversation 7

**File:** `studio/src/renderer/src/lib/actionExecutor.ts` — CREATE
**Done when:** `executeAction({ type: 'click', elementId: 'btn-add-step' })` clicks the matching DOM element
**Delivers:** S7.1, S7.2, S7.3 (complete)
**Details:**
- `window.__uiExecutor = { execute(action: UIAction): { ok: boolean; error?: string } }`
- Look up element via `document.querySelector(`[data-conductor-id="${action.elementId}"]`)`
- For `click`: call `.click()` on the element
- For `fill`: set `.value`, dispatch `input` + `change` events (React synthetic event compat)
- For `select`: set `.value`, dispatch `change` event
- Each Studio component that calls `usePageAnalyzer` must add `data-conductor-id={id}` to its DOM node
- Return `{ ok: false, error: 'element not found' }` if querySelector returns null
- Register `window.__uiExecutor` in a top-level `useEffect` in `App.tsx`

---

## Phase 24: automationStore + step queue state   ← Conversation 8

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
- Extend `POST /chat` request to include `pageContext` and `mode: 'automation'` flag
- When `mode === 'automation'`: `chat_agent.py` returns structured JSON steps instead of plain text:
  ```json
  { "type": "automation", "intent": "...", "steps": [{ "description": "...", "action": {...} }] }
  ```
- On receive: parse steps → `automationStore.setSteps(steps)` → render `AutomationCard` in message list
- Staged: `StepQueue` calls `executeAction()` → advances to next step on approve
- Auto: loop through all steps calling `executeAction()` with 300ms delay between each
- After all steps done: AI sends summary message "Flow created — 5 steps executed"

---

## Phase 27: WebLLM models data + engine   ← Conversation 9

**Files:** `studio/src/renderer/src/data/models.ts` — CREATE,
`studio/src/renderer/src/lib/webLLMEngine.ts` — CREATE
**Done when:** `getEngine()` loads Phi-4 Mini in Electron and `askWebLLM("hello")` streams a response
**Delivers:** S9.3 (partial)
**Details:**
- Port `WebLLMModels.js` from zakamurai (`src/components/AI/WebLLMModels.js`) to TypeScript:
  - `Model: { id: string; name: string; description: string; useCase: string; system: string; storage: string; speed: string; recommended?: boolean }`
  - 4 models: Qwen2.5-Coder-7B-Instruct-q4f16_1-MLC, Qwen3-4B-q4f16_1-MLC, Phi-4-mini-instruct-q4f16_1-MLC (recommended), Llama-3.2-3B-Instruct-q4f16_1-MLC
- Port `WebLLMAPI.js` from zakamurai to TypeScript:
  - `getEngine(modelId, onProgress): Promise<MLCEngine>` — singleton, recreates if model changes
  - `getCachedWebLLMModelIds(): Promise<string[]>` — checks browser cache storage
  - `cacheWebLLMModel(modelId, onProgress): Promise<void>` — download + cache
  - `deleteCachedWebLLMModel(modelId): Promise<void>`
  - `askWebLLM(prompt, system, onChunk): Promise<string>` — streaming via callback
- Add `@mlc-ai/web-llm` to `studio/package.json`

---

## Phase 28: modelStore + ModelSelector UI   ← Conversation 9

**Files:** `studio/src/renderer/src/store/modelStore.ts` — CREATE,
`studio/src/renderer/src/components/ChatPanel/ModelSelector.tsx` — CREATE
**Done when:** Model selector UI renders; selecting Phi-4 Mini downloads it with progress; selection persists
**Delivers:** S9.1, S9.2, S9.4
**Details:**
- `modelStore`: `selectedModelId: string`, `cachedModelIds: string[]`, `downloadProgress: Record<string, number>`, `setSelectedModel(id)`, `setCached(ids)`, `setProgress(id, pct)`
- Persist: `selectedModelId` only
- `ModelSelector` UI (matches your screenshots):
  - Dropdown trigger showing current model name + `▼` chevron + `ℹ` info button
  - Dropdown panel: each model as an expandable card showing name, description, SYSTEM / STORAGE / SPEED rows
  - Badges: `Recommended` (teal), `Cached` (green), `Selected` (blue)
  - `Cache` toggle per model — calls `cacheWebLLMModel()` / `deleteCachedWebLLMModel()`
  - Download progress: linear progress bar under the model card while downloading
  - Wired into `ConductorHeader` — replace the `phi4-mini` pill with the `ModelSelector` dropdown

---

## Phase 29: Wire WebLLM into chat flow   ← Conversation 9

**Files:** `src/pathly_orchestrator/chat_agent.py` — MODIFY (make Ollama optional),
`ChatPanel/index.tsx` — MODIFY, `chatStore.ts` — MODIFY
**Done when:** phi4-mini explanation comes from WebLLM (selected model) instead of Ollama
**Delivers:** S9.3 (complete)
**Details:**
- Replace `POST /chat` SSE call with local `askWebLLM()` call in the renderer (no server round-trip)
- The Python `chat_agent.py` stays for teams using Ollama — make it optional via `PATHLY_CHAT_BACKEND=ollama|webllm`
- Default to `webllm` — `askWebLLM(prompt, systemPrompt, onChunk)` streams into chatStore directly
- Update `ChatInput` model pill: was `phi4-mini` hardcoded → now reads `modelStore.selectedModelId` short name
- If WebLLM engine not loaded yet: show spinner in explanation area (same as "Ollama offline" fallback)

---

## Prerequisites
- MiniLM will auto-download via transformers.js (~22MB, first launch only)
- WebLLM models download on first cache (Phi-4 Mini ~2GB, Qwen3 4B ~3GB, Qwen2.5 Coder ~5GB)
- Pathly FSM server running on port 8765 before testing Conv 1
- Ollama optional (legacy backend) — not required for Conv 9+

## Key Decisions
- **Embedding over LLM for routing:** Zero hallucination, 22ms, deterministic. See ARCHITECTURE_PROPOSAL.md Decision 1.
- **phi4-mini as explainer only:** Routing and explaining are separate concerns with different latency needs.
- **Skills are the command vocabulary:** All commands are Pathly skills. Claude Code and Codex are terminal surfaces, not routing targets.
- **Pre-embed at startup:** Ensures first-message latency is instant. 14 skills × ~384 dimensions = negligible memory.
- **Confidence threshold UI:** Users need to see and understand match quality to trust the system.
