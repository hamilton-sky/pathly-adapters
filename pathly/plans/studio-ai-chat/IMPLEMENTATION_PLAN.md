# Studio AI Chat — Implementation Plan

## Overview

Adds the **Conductor** — a local AI chat panel to Pathly Studio (Electron). The Conductor
interprets plain-English intent, matches it to the right Pathly skill via embedding similarity
(MiniLM, ~22ms, offline), explains the match with phi4-mini, and writes the skill command to
the Claude Code or Codex terminal tab with user approval.

**Read DESIGN_SPEC.md before building any UI.** It contains ASCII layouts, design tokens,
component specs, and the interaction model.

## Pre-flight

Before Conversation 1:
```
cd studio && npm run typecheck
```
Record any pre-existing failures as baseline.

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

## Phase 1: POST /chat SSE endpoint skeleton   ← Conversation 1

**File:** `src/pathly_orchestrator/http_server.py` — MODIFY
**Done when:** `curl -X POST http://127.0.0.1:8765/chat -H "Content-Type: application/json" -d '{"message":"explain build","matchedSkill":"build","history":[]}'` returns 200
**Delivers:** S1.1 (partial)
**Details:**
- Add route `/chat` accepting POST: `{ message, matchedSkill, skillDescription, history, context }`
- Return `Content-Type: text/event-stream`
- Static placeholder: `data: {"text": "chat endpoint ready"}\n\n`
- Add `ollama>=0.3` to `pyproject.toml`

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
- `get_fsm_state(project_root) -> dict` — reads FSM state or calls `/next_action` internally
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

**Files:** `studio/src/main/ipc/chat.ts` — CREATE, `studio/src/main/index.ts` — MODIFY
**Done when:** `ipcRenderer.invoke('chat:write-terminal', { command: '/pathly build', target: 'claude-code' })` writes to the correct PTY tab — auto-creating a tab if none is open
**Delivers:** S3.2
**Details:**
- `ipcMain.handle('chat:write-terminal', (event, { command, target }) => { ... })`
- Find PTY by target name (check how `activePtys` is keyed in `terminal.ts`)
- **Auto-spawn if no PTY found:** if `activePtys` has no entry for `target`, call the same
  tab-creation logic used by the `+` button (read `terminal.ts` to find that function) to
  spawn a new Claude Code or Codex tab, wait for it to be ready, then write the command.
  The new tab becomes visible in the terminal area — the user can watch execution there.
- Sanitize command before write: strip `;`, `&&`, `||`, `|`, `>`, `<`. Log warning if stripped.
- Return `{ ok: true, spawned?: boolean }` or `{ error: string }`
  - `spawned: true` signals to the renderer that a new tab was opened (ChatPanel can show a hint)
- Expose on preload: `window.electronAPI.writeToTerminal(command, target): Promise<{ok?:boolean, spawned?:boolean, error?:string}>`
- Register in `index.ts` alongside other IPC handlers
- **Result:** user can use the Conductor with zero terminals open — Run opens one automatically

---

## Phase 12: pathlyContext builder   ← Conversation 4

**File:** `studio/src/renderer/src/lib/pathlyContext.ts` — CREATE
**Done when:** `buildPathlyContext()` returns `{ fsmStage, featureName, screenElements, skills }`
**Delivers:** S4.1, S4.2
**Details:**
- Fetch `http://127.0.0.1:8765/next_action` → extract current stage name
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

## Prerequisites
- Ollama installed: `winget install Ollama.Ollama`
- Model pulled: `ollama pull phi4-mini`
- MiniLM will auto-download via transformers.js (~22MB, first launch only)
- Pathly FSM server running on port 8765 before testing Conv 1

## Key Decisions
- **Embedding over LLM for routing:** Zero hallucination, 22ms, deterministic. See ARCHITECTURE_PROPOSAL.md Decision 1.
- **phi4-mini as explainer only:** Routing and explaining are separate concerns with different latency needs.
- **Skills are the command vocabulary:** All commands are Pathly skills. Claude Code and Codex are terminal surfaces, not routing targets.
- **Pre-embed at startup:** Ensures first-message latency is instant. 14 skills × ~384 dimensions = negligible memory.
- **Confidence threshold UI:** Users need to see and understand match quality to trust the system.
