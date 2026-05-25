# Studio AI Chat — Conversation Prompts

Split into **5 conversations**. Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

**Before building any UI:** read `pathly/plans/studio-ai-chat/DESIGN_SPEC.md` — it is the builder's bible: ASCII layouts, design tokens, component specs, interaction model, and what NOT to build.

A live HTML mockup showing the target layout lives at: `studio-chat-mockup/index.html`

---

## Conversation 1: Python Chat Agent Server (Phases 1–3)

**Stories delivered:** S1.1, S1.2
**Verify:** `curl -X POST http://127.0.0.1:8765/chat -H "Content-Type: application/json" -d '{"message":"explain build","matchedSkill":"build","history":[]}'` returns 200 and streams SSE

**Prompt to paste:**
```
Read pathly/plans/studio-ai-chat/FEATURE_INDEX.md first to orient yourself and verify codebase paths.
Read pathly/plans/studio-ai-chat/IMPLEMENTATION_PLAN.md Phases 1–3 for full details.

Implement Studio AI Chat Conversation 1 (Phases 1–3).

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `src/pathly_orchestrator/http_server.py` — MODIFY: add POST /chat SSE endpoint
- `src/pathly_orchestrator/chat_agent.py` — CREATE: phi4-mini explainer agent
- `src/pathly_orchestrator/chat_tools.py` — CREATE: get_fsm_state, read_plan_summary
- `pyproject.toml` — MODIFY: add ollama>=0.3 dependency

Scope:
- Phase 1: Add POST /chat route to http_server.py returning Content-Type: text/event-stream.
  Request body: { message, matchedSkill, skillDescription, history, context }.
  Static placeholder first: data: {"text": "chat endpoint ready"}\n\n
  Add ollama>=0.3 to pyproject.toml.

- Phase 2: Create chat_agent.py with ChatAgent class.
  Method: stream(message, matchedSkill, context, history) -> AsyncGenerator[str].
  System prompt is the EXPLAINER role (see DESIGN_SPEC.md — phi4-mini System Prompt section).
  phi4-mini is an EXPLAINER ONLY — it never decides which skill to use.
  Calls ollama.AsyncClient().chat() with model from PATHLY_CHAT_MODEL env var (default phi4-mini).
  Streams chunks as SSE: data: {"text": "..."}\n\n
  On Ollama offline: yield data: {"error": "Ollama offline"}\n\n — MatchCard still works without explanation.
  On model not found: yield data: {"error": "Model 'phi4-mini' not found — run: ollama pull phi4-mini"}\n\n

- Phase 3: Create chat_tools.py.
  get_fsm_state(project_root) -> dict — reads FSM state or calls /next_action internally.
  read_plan_summary(project_root) -> str — reads most-recently-modified plans/*/FEATURE_INDEX.md.
  Inject into system prompt: Stage: {fsm_stage} | Feature: {feature_name} | Matched skill: {skill}.
  System prompt token cap: 1,000 tokens. Truncate plan summary if exceeded — append [...truncated].

Architectural rules:
- Do NOT modify any FSM logic, /next_action, /complete_stage, or /events/stream endpoints.
- phi4-mini is an EXPLAINER. Routing is done by MiniLM in the renderer — NOT by phi4-mini.
- PATHLY_CHAT_MODEL env var (default phi4-mini) must be respected.
- Do NOT touch studio/ (frontend), IPC handlers, or anything outside the Python backend.

Verify: curl -X POST http://127.0.0.1:8765/chat -H "Content-Type: application/json" -d '{"message":"explain build","matchedSkill":"build","history":[]}' --no-buffer
Expected: streaming SSE chunks, explanation references the matched skill name.

After done, update pathly/plans/studio-ai-chat/PROGRESS.md phases 1–3 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `POST /chat` streams a 2-3 sentence explanation of why the matched skill fits the user's intent.
**Files touched:** `http_server.py`, `chat_agent.py`, `chat_tools.py`, `pyproject.toml`

---

## Conversation 2: Conductor UI Shell (Phases 4–8)

**Stories delivered:** S2.1, S2.2, S2.3
**Requires:** Conversation 1 complete and FSM server running on port 8765.
**Verify:** `cd studio && npm run typecheck` — zero errors. Studio launches with Conductor panel visible on the right.

**Prompt to paste:**
```
Read pathly/plans/studio-ai-chat/FEATURE_INDEX.md first to orient yourself and verify codebase paths.
Read pathly/plans/studio-ai-chat/DESIGN_SPEC.md — REQUIRED before writing any UI code.
Read pathly/plans/studio-ai-chat/IMPLEMENTATION_PLAN.md Phases 4–8 for full details.

A live HTML mockup exists at studio-chat-mockup/index.html — it shows the exact target layout.

Implement Studio AI Chat Conversation 2 (Phases 4–8).

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/store/chatStore.ts` — CREATE: Zustand store (messages + match state)
- `studio/src/renderer/src/store/uiStore.ts` — MODIFY: add chatOpen, skillsPanelOpen
- `studio/src/renderer/src/components/ChatPanel/index.tsx` — CREATE: collapsible panel container
- `studio/src/renderer/src/components/ChatPanel/ConductorHeader.tsx` — CREATE: header + CLI pills
- `studio/src/renderer/src/components/ChatPanel/SkillsPanel.tsx` — CREATE: skill chips grid
- `studio/src/renderer/src/components/ChatPanel/MessageList.tsx` — CREATE: scrollable messages
- `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx` — CREATE: input + model pills
- `studio/src/renderer/src/components/ChatPanel/ChatPanel.module.css` — CREATE: all chat styles
- `studio/src/renderer/src/App.tsx` — MODIFY: add <ChatPanel /> as right sidebar

Scope:
- Phase 4: Create chatStore.ts following uiStore.ts pattern (Zustand + persist middleware).
  Full store shape in DESIGN_SPEC.md — Zustand Store Shape section.
  Key fields: messages, isStreaming, currentMatch, altMatches, isEmbedding, embedReady, pendingCommand, autoApprove.
  Persist: autoApprove only. Messages and matches are session-only.

- Phase 5: Modify uiStore.ts — add chatOpen: boolean (default true), skillsPanelOpen: boolean (default true).
  Add toggleChat() and toggleSkillsPanel() actions.

- Phase 6: Create ConductorHeader.tsx.
  "⚡ Conductor" title — JetBrains Mono, accent #22C55E.
  [Manual] / [Auto] toggle reads from chatStore.autoApprove.
  CLI pills: Claude Code (#38BDF8), Codex (#F59E0B). Active = colored dot, idle = grey dot 0.45 opacity.
  [›] collapse button calls uiStore.toggleChat().
  See DESIGN_SPEC.md ConductorHeader section for exact ASCII layout.

- Phase 7: Create SkillsPanel.tsx.
  Static fallback skill list: ['plan','po','storm','build','review','test','retro','explore','debug','design','fix','status','log','end'].
  (This will be replaced by skillsManifest in Conv 5 — use static array for now.)
  Chip: JetBrains Mono 10px, surface bg, border #475569.
  Highlighted chip (when chatStore.currentMatch?.skill.name === chip): accent border + accent text.
  Collapse toggle reads uiStore.skillsPanelOpen.
  Clicking a chip creates a stub MatchCard entry in chatStore (placeholder for now — wired fully in Conv 5).

- Phase 8: Create MessageList.tsx, ChatInput.tsx, ChatPanel/index.tsx, modify App.tsx.
  MessageList: maps messages array from chatStore. User messages right-aligned, AI messages left-aligned.
  Renders MatchCard placeholder (renders null for now — component created in Conv 3) and OutputSnippet placeholder inline.
  Auto-scroll to bottom on new message.
  EMPTY STATE (when messages.length === 0): render EmptyState component instead of empty list.
    - No active feature (fsmStage === "unknown"): show "⚡ What do you want to build?" + quick-start chips [▸ po] [▸ plan] [▸ storm]
    - Active feature: show "⚡ <featureName> · <stage>" + "Describe what you want to do next."
    - Quick-start chip click: sets chatStore.currentMatch to that skill (bypasses embedding), fires phi4-mini explanation
    - Empty state disappears on first message send
    - See DESIGN_SPEC.md → EmptyState for exact visual spec and ASCII layout
  ChatInput: textarea 1-3 rows auto-resize. Enter = send, Shift+Enter = newline.
  "◈ MiniLM" pill (purple #C084FC), "phi4-mini" pill (accent #22C55E). Send/Stop toggle.
  ChatPanel/index.tsx: collapse animation width 200ms ease-out. 300px expanded ↔ 36px collapsed.
  App.tsx: add <ChatPanel /> after <MainPanel /> in body flex row.

Design tokens to use (see DESIGN_SPEC.md for full token list):
- --bg: #0F172A, --surface: #1E293B, --surface2: #334155
- --accent: #22C55E, --fg: #F8FAFC, --muted: #94A3B8, --border: #475569
- --destructive: #EF4444, --claude-blue: #38BDF8, --codex-amber: #F59E0B, --embed-purple: #C084FC
- --mono: 'JetBrains Mono', monospace (commands, skill names, chips, headers)
- --sans: 'Inter', sans-serif (message text, labels)
- Panel width: 300px expanded, 36px collapsed. Chat panel border-left: 1px solid #475569.

Architectural rules:
- No Redux. No WebSocket. No Chrome extension APIs. No Tailwind.
- Use Zustand for all state. Use CSS Modules (match existing studio pattern).
- Do not touch any IPC handlers, main process files, or Python backend.
- Do not touch the terminal, left sidebar, or any existing Studio components beyond App.tsx layout.

Verify: cd studio && npm run typecheck
Expected: zero TypeScript errors. Studio launches with Conductor panel visible on the right as a right sidebar.

After done, update pathly/plans/studio-ai-chat/PROGRESS.md phases 4–8 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Studio has a Conductor panel on the right — ConductorHeader, 14 skill chips, message list, input bar with model pills. Typing a message sends it to phi4-mini and streams the response.
**Files touched:** `chatStore.ts`, `uiStore.ts`, `ChatPanel/` (6 files), `App.tsx`

---

## Conversation 3: MatchCard + OutputSnippet + IPC (Phases 9–11)

**Stories delivered:** S3.1, S3.2
**Requires:** Conversation 2 complete (Conductor panel showing in Studio).
**Verify:** `cd studio && npm run typecheck` — zero errors. MatchCard renders with green/amber states.

**Prompt to paste:**
```
Read pathly/plans/studio-ai-chat/FEATURE_INDEX.md first to orient yourself and verify codebase paths.
Read pathly/plans/studio-ai-chat/DESIGN_SPEC.md — REQUIRED before writing any UI code.
Read pathly/plans/studio-ai-chat/IMPLEMENTATION_PLAN.md Phases 9–11 for full details.

Implement Studio AI Chat Conversation 3 (Phases 9–11).

**Before editing anything:** glob/read the live repo to confirm every file path below exists.
Also read studio/src/main/ipc/terminal.ts to understand how activePtys map and activeTabId are exported — match that exact pattern in the new chat.ts handler.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/components/ChatPanel/MatchCard.tsx` — CREATE
- `studio/src/renderer/src/components/ChatPanel/OutputSnippet.tsx` — CREATE
- `studio/src/main/ipc/chat.ts` — CREATE: IPC terminal write handler
- `studio/src/main/index.ts` — MODIFY: register chat IPC handler
- `studio/src/renderer/src/components/ChatPanel/index.tsx` — MODIFY: subscribe to IPC output

Scope:
- Phase 9: Create MatchCard.tsx.
  Props: match: MatchResult, alts: MatchResult[], onRun: () => void, onReject: () => void, onSelectAlt: (skill) => void.
  Confidence bar: CSS width = score * 100%, green (≥65%) or amber (<65%).
  Status label: ✓ MATCHED (green) or ~ UNSURE (amber).
  Alt chips: clickable, calls onSelectAlt — replaces current match.
  Sent state: opacity 0.4, shows ✓ Sent label, Run/Not this hidden.
  No-match state (score < 0.4): text message instead of card.
  See DESIGN_SPEC.md MatchCard section for full visual spec and ASCII layout.
  Wire MatchCard into MessageList.tsx — render it inline when chatStore.currentMatch is set.

- Phase 10: Create OutputSnippet.tsx.
  Props: target: "claude-code" | "codex", status: "running" | "done" | "error", lines: string[].
  Shows last 5 lines from PTY output (ANSI stripped — use strip-ansi or inline regex).
  Status color: running = amber #F59E0B, done = green #22C55E, error = red #EF4444.
  ChatPanel/index.tsx subscribes to an IPC output event and pipes lines to chatStore.
  See DESIGN_SPEC.md OutputSnippet section for ASCII layout.

- Phase 11: Create studio/src/main/ipc/chat.ts.
  ipcMain.handle('chat:write-terminal', (event, { command, target }) => { ... })
  Find PTY by target name — read terminal.ts first to understand the map structure.
  AUTO-SPAWN: if no PTY found for target, call the same tab-creation logic used by the + button
  (find it in terminal.ts) to open a new Claude Code or Codex tab. Wait for PTY ready, then write.
  This means the user NEVER needs to manually open a terminal — clicking Run is enough.
  Sanitize command before write: strip ;, &&, ||, |, >, < characters. Log warning if stripped.
  Return { ok: true, spawned?: boolean } or { error: string }.
  spawned: true tells the renderer a new tab was opened (show a brief hint in ChatPanel).
  Expose on preload: window.electronAPI.writeToTerminal(command, target): Promise<{ok?:boolean, spawned?:boolean, error?:string}>
  Register in index.ts alongside other IPC handlers.

Architectural rules:
- MatchCard replaces the old TerminalApproval concept entirely — do NOT create a TerminalApproval component.
- Read terminal.ts before writing chat.ts — the PTY map keying must match exactly.
- Preload must be updated if window.electronAPI doesn't already have writeToTerminal.
- Do NOT modify FSM IPC handlers or Python backend.

Verify: cd studio && npm run typecheck
Expected: zero TypeScript errors. A MatchCard renders in the panel. Clicking Run writes to the terminal.

After done, update pathly/plans/studio-ai-chat/PROGRESS.md phases 9–11 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** MatchCard shows matched skill + confidence + Run/"Not this" buttons. Run writes the `/pathly <skill>` command to the correct terminal tab. OutputSnippet shows live PTY lines.
**Files touched:** `MatchCard.tsx`, `OutputSnippet.tsx`, `ipc/chat.ts`, `main/index.ts`, `ChatPanel/index.tsx`

---

## Conversation 4: Context Injection (Phases 12–14)

**Stories delivered:** S4.1, S4.2
**Requires:** Conversation 3 complete.
**Verify:** `cd studio && npm run typecheck` — zero errors. phi4-mini explanation references FSM stage by name.

**Prompt to paste:**
```
Read pathly/plans/studio-ai-chat/FEATURE_INDEX.md first to orient yourself and verify codebase paths.
Read pathly/plans/studio-ai-chat/IMPLEMENTATION_PLAN.md Phases 12–14 for full details.

Implement Studio AI Chat Conversation 4 (Phases 12–14).

**Before editing anything:** glob/read the live repo to confirm every file path below exists.
Also read the source files in C:\Users\Yafit\brightsky-ai\frontend\src\components\PageAnalyzer\ to understand which files to copy.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/lib/pageAnalyzer/` — CREATE directory + copy pure TS analyzers from BrightSky
- `studio/src/renderer/src/lib/pathlyContext.ts` — CREATE: context builder
- `studio/src/renderer/src/components/ChatPanel/index.tsx` — MODIFY: inject context per message

Scope:
- Phase 12: Create studio/src/renderer/src/lib/pathlyContext.ts.
  buildPathlyContext() fetches FSM state from http://127.0.0.1:8765/next_action → extract stage name.
  KNOWN_SKILLS: static list for now (will be dynamic in Conv 5).
  Wrap FSM fetch in try/catch → fallback fsmStage: "unknown".
  Cap screen elements at 20 buttons + 10 forms + 10 text blocks.
  Returns: { fsmStage, featureName, screenElements, skills }

- Phase 13: Copy these files from C:\Users\Yafit\brightsky-ai\frontend\src\components\PageAnalyzer\
  to studio/src/renderer/src/lib/pageAnalyzer/:
  analyzePageDirect.ts, CacheManager.ts, DOMAnalyzer2.ts, ButtonAnalyzer.ts,
  FormAnalyzer.ts, TextAnalyzer.ts, LinkAnalyzer.ts
  Replace any @brightsky-ai/shared imports with inline type definitions.
  Do NOT copy Redux-dependent files.
  Verify: import { analyzePageDirect } from '../lib/pageAnalyzer/analyzePageDirect' compiles.

- Phase 14: Modify ChatPanel/index.tsx.
  Call buildPathlyContext() before each POST /chat.
  Add context field to request body.
  phi4-mini explanation should now reference the current FSM stage and feature.

Architectural rules:
- Only copy pure TS files — no Chrome extension APIs, no Redux, no @brightsky-ai/shared.
- Screen context cap: 500 tokens max. Truncate items list if exceeded.
- Do NOT add new IPC calls. Context is gathered in the renderer via fetch + DOM APIs only.
- Do NOT touch MatchCard, chatStore approval logic, or any Conv 3 work.

Verify: cd studio && npm run typecheck
Expected: zero TypeScript errors. phi4-mini explanation mentions current FSM stage by name.

After done, update pathly/plans/studio-ai-chat/PROGRESS.md phases 12–14 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** phi4-mini explanation knows the current FSM stage, feature name, and available skills.
**Files touched:** `lib/pageAnalyzer/` (7 files), `pathlyContext.ts`, `ChatPanel/index.tsx`

---

## Conversation 5: Embedding Router (Phases 15–18)

**Stories delivered:** S5.1, S5.2, S5.3
**Requires:** Conversation 4 complete.
**Verify:** `cd studio && npm run typecheck` — zero errors. MatchCard renders < 50ms after send.

**Prompt to paste:**
```
Read pathly/plans/studio-ai-chat/FEATURE_INDEX.md first to orient yourself and verify codebase paths.
Read pathly/plans/studio-ai-chat/DESIGN_SPEC.md — REQUIRED before writing any UI code.
Read pathly/plans/studio-ai-chat/IMPLEMENTATION_PLAN.md Phases 15–18 for full details.

Implement Studio AI Chat Conversation 5 (Phases 15–18) — the embedding router.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/data/skills.json` — CREATE: 14 skills with name+command+description
- `studio/src/renderer/src/lib/skillsManifest.ts` — CREATE: typed loader for skills.json
- `studio/src/renderer/src/lib/embedRouter.ts` — CREATE: MiniLM wrapper + matchIntent()
- `studio/src/renderer/src/components/ChatPanel/index.tsx` — MODIFY: wire embedding into send flow
- `studio/src/renderer/src/store/chatStore.ts` — MODIFY: connect embedReady state

Scope:
- Phase 15: Create studio/src/renderer/src/data/skills.json.
  14 skills: plan, po, storm, build, review, test, retro, explore, debug, design, fix, status, log, end.
  Each skill: { "name": string, "command": string, "description": string }
  Descriptions must be SPECIFIC (1-2 sentences, include WHEN to use it).
  Example: { "name": "build", "command": "/pathly build", "description": "Spawn the builder agent to implement the feature. Use when the implementation plan is written and approved and you are ready to write code." }
  Poor descriptions cause poor embedding matches — be specific.

- Phase 16: Create skillsManifest.ts.
  interface Skill { name: string; command: string; description: string; vector?: number[] }
  loadSkills(): Skill[] — imports skills.json, returns typed array.
  vector field is populated by embedRouter at startup, not stored in JSON.

- Phase 17: Create embedRouter.ts.
  Load model at startup: const embedder = await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2')
  preEmbedSkills(skills: Skill[]): Promise<void> — embeds all skill descriptions at startup. Stores vectors on skill objects in memory.
  matchIntent(input: string): MatchResult[] — embeds input, cosine similarity against all skills, returns top 3 sorted by score.
  cosineSim(a: number[], b: number[]): number — dot product / (|a| * |b|).
  Call chatStore.setEmbedReady(true) when preEmbedSkills completes.
  Show "◈ Loading model…" in MiniLM pill (check embedReady state in ChatInput) until ready.
  Install dependency: @xenova/transformers

- Phase 18: Modify ChatPanel/index.tsx and chatStore.ts.
  On message send: call matchIntent(input) → chatStore.setMatch(topMatch, altMatches).
  MatchCard renders from chatStore.currentMatch immediately — no waiting for phi4-mini.
  POST /chat fires async in parallel with MatchCard render — add { matchedSkill, skillDescription } to body.
  If topMatch.score < 0.4: show no-match message, skip MatchCard, still send to phi4-mini.
  If autoApprove && topMatch.score >= 0.65: auto-invoke Run after phi4-mini explanation completes.
  Disable send button if embedReady === false (model still loading).

Test these 5 phrases — expected matches:
- "I want to build" → build (score ≥ 0.75)
- "check the code" → review (score ≥ 0.70)
- "something is broken" → debug (score ≥ 0.70)
- "write the plan" → plan (score ≥ 0.75)
- "run tests" → test (score ≥ 0.75)

Architectural rules:
- embedRouter runs in the renderer process — no server needed, no API calls, fully offline.
- MiniLM auto-downloads on first launch (~22MB from HuggingFace CDN). This is expected.
- phi4-mini is the EXPLAINER. MiniLM is the ROUTER. These are separate concerns — never swap them.
- Do NOT use phi4-mini or any LLM to decide which skill to route to.

Verify: cd studio && npm run typecheck
Expected: zero TypeScript errors. MatchCard renders in < 50ms after send. Test all 5 phrases.

After done, update pathly/plans/studio-ai-chat/PROGRESS.md phases 15–18 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** MatchCard renders instantly on send (~22ms), MiniLM routes to the correct skill, phi4-mini explains async. All 5 test phrases match correctly.
**Files touched:** `skills.json`, `skillsManifest.ts`, `embedRouter.ts`, `ChatPanel/index.tsx`, `chatStore.ts`
