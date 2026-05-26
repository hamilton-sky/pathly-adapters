# Studio AI Chat — Conversation Prompts

Split into **10 conversations** (Conv 0 through Conv 9). Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

**Two parallel build tracks after Conv 5:**
- **Track A** (Convs 6–8): UI Automation — page analyzer, action executor, staged/auto mode
- **Track B** (Conv 9): Model Selector — WebLLM engine + model picker UI (independent, no dependencies on Track A)

**Before building any UI:** read `pathly/plans/studio-ai-chat/DESIGN_SPEC.md` — it is the builder's bible: ASCII layouts, design tokens, component specs, interaction model, and what NOT to build.

A live HTML mockup showing the target layout lives at: `studio-chat-mockup/index.html`

---

## Conversation 0: Terminal Dock Improvements (Phases 0a–0c)

**Stories delivered:** S0.1, S0.2, S0.3
**Requires:** Nothing — this is the foundation.
**Verify:** `cd studio && npm run typecheck` — zero new errors. Launch Studio and confirm:
- Claude Code and Codex terminal tabs open without error
- Empty terminal area is compact (72px), not a large blank zone
- Session tabs and launcher buttons are visually distinct

**Prompt to paste:**
```
Read pathly/plans/studio-ai-chat/IMPLEMENTATION_PLAN.md Phases 0a–0c before touching any file.

Implement Studio AI Chat Conversation 0 (Phases 0a–0c) — terminal dock improvements.

**Before editing anything:**
1. Run: cd studio && npm run typecheck — record any pre-existing errors as baseline
2. Read studio/src/main/ipc/terminal.ts fully (especially lines 13–100)
3. Read studio/src/renderer/src/components/Terminal/index.tsx fully
4. Read studio/src/renderer/src/components/Terminal/PaneTabBar.tsx fully
5. Confirm file paths and CSS module names before editing

**Codebase files this conversation touches:**
- `studio/src/main/ipc/terminal.ts` — MODIFY: add claude+codex to ALLOWED_SHELLS
- `studio/src/renderer/src/components/Terminal/index.tsx` — MODIFY: compact height + empty state
- `studio/src/renderer/src/components/Terminal/PaneTabBar.tsx` — MODIFY: sessions vs launchers hierarchy
- Terminal CSS module(s) — MODIFY: active tab style, compact empty state style

Scope:

Phase 0a — Fix ALLOWED_SHELLS (do this first, it unblocks everything):
  Read terminal.ts line 13. ALLOWED_SHELLS only contains shell variants (bash, zsh, etc).
  Add 'claude' and 'codex' to the set.
  This is an existing bug: PaneTabBar passes 'claude'/'codex' as the command to terminal:spawn,
  which the allowlist currently rejects with "Shell not allowed".

Phase 0b — Compact terminal dock height:
  Find where terminal height is set (reportedly 260px in index.tsx) — confirm the actual value.
  Change default open height to 180px.
  Empty state (no open tabs): shrink to 72px tall.
  Replace "Press + to open a terminal" centered text with a compact inline row:
    No terminal open.   [+ Shell]  [Open Claude]  [Open Codex]
  These buttons call the existing handleLaunch function.
  Add height transition: 150ms ease-out between empty (72px) and active (180px).
  Do NOT change any PTY logic, spawning, IPC, or data flow.

Phase 0c — Session vs launcher hierarchy in PaneTabBar:
  Current problem: + Shell, A Claude, Codex all look identical whether they are live sessions
  or launch buttons. No visual hierarchy.
  New layout:
    Left: open session tabs — filled bg, colored dot (blue=Claude amber=Codex), × close per tab,
          active tab has accent-colored bottom border (border-bottom: 2px solid var(--accent))
    Divider: │ or spacing
    Right: launcher buttons — muted/secondary style, clearly different from session tabs
  Active session tab: background var(--surface2), label full opacity
  Inactive session tab: transparent bg, 60% opacity
  If no sessions open: only launchers visible — no empty tab strip taking up space
  Split mode: one shared dock header; each pane has its own compact session strip
  Use existing Studio design tokens only — do not introduce new colors or font sizes

Design tokens already in Studio (use these, do not invent new ones):
  --bg: #0F172A, --surface: #1E293B, --surface2: #334155
  --accent: #22C55E, --fg: #F8FAFC, --muted: #94A3B8, --border: #475569
  --claude-blue: #38BDF8 (or check what the existing Claude tab uses)
  --codex-amber: #F59E0B (or check what the existing Codex tab uses)

Architectural rules:
  - Do NOT touch any IPC handlers beyond the ALLOWED_SHELLS line
  - Do NOT touch PTY spawning logic, data flow, or FSM code
  - Do NOT touch App.tsx, the sidebar, main content area, or any Conductor/chat files
  - Match the existing CSS Modules pattern — no inline styles, no Tailwind

Verify: cd studio && npm run typecheck
Expected: zero NEW TypeScript errors (pre-existing baseline is acceptable).
Visual check: launch Studio — no blank dead zone, Claude/Codex tabs open, sessions vs launchers clear.

After done, update pathly/plans/studio-ai-chat/PROGRESS.md phases 0a–0c to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Terminal dock is compact and IDE-style. ALLOWED_SHELLS bug fixed. Conductor can build on a solid terminal foundation from Conv 3 onward.
**Files touched:** `terminal.ts`, `Terminal/index.tsx`, `Terminal/PaneTabBar.tsx`, CSS module(s)

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
  ALSO add GET /status endpoint — read-only FSM state:
    Calls read_state() from fsm_ops.py (pure read, NO write).
    Returns { "current_state": str, "feature": str, "project_root": str } or { "current_state": "unknown" }.
    DO NOT call next_action() here — it writes conv_start_sha to disk on every invocation.
    This endpoint replaces /next_action for all context reads in this feature.

- Phase 2: Create chat_agent.py with ChatAgent class.
  Method: stream(message, matchedSkill, context, history) -> AsyncGenerator[str].
  System prompt is the EXPLAINER role (see DESIGN_SPEC.md — phi4-mini System Prompt section).
  phi4-mini is an EXPLAINER ONLY — it never decides which skill to use.
  Calls ollama.AsyncClient().chat() with model from PATHLY_CHAT_MODEL env var (default phi4-mini).
  Streams chunks as SSE: data: {"text": "..."}\n\n
  On Ollama offline: yield data: {"error": "Ollama offline"}\n\n — MatchCard still works without explanation.
  On model not found: yield data: {"error": "Model 'phi4-mini' not found — run: ollama pull phi4-mini"}\n\n

- Phase 3: Create chat_tools.py.
  get_fsm_state(project_root) -> dict — calls read_state() from fsm_ops.py directly (pure read).
  DO NOT call next_action() — it mutates FSM state by writing conv_start_sha to disk.
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

- Phase 11: Read terminal.ts and Terminal/index.tsx thoroughly before writing anything.

  PRE-FLIGHT FIX (do this first):
  Read studio/src/main/ipc/terminal.ts line 13 — ALLOWED_SHELLS set.
  Add 'claude' and 'codex' to ALLOWED_SHELLS. Without this, the existing Claude Code and
  Codex terminal buttons are broken (they pass 'claude'/'codex' as the command, which the
  allowlist rejects with "Shell not allowed").

  IPC HANDLER (studio/src/main/ipc/chat.ts):
  ipcMain.handle('chat:write-terminal', (event, { command, tabId }) => { ... })
  PTYs are keyed by UUID tabId (NOT by string names like "claude-code").
  The renderer resolves tabId BEFORE calling this IPC — main process just does activePtys.get(tabId)?.write(command + '\n').
  Sanitize command before write: strip ;, &&, ||, |, >, < characters. Log warning if stripped.
  Return { ok: true } or { error: string }.
  Expose on preload: window.electronAPI.writeToTerminal(command: string, tabId: string): Promise<{ok?:boolean, error?:string}>
  Register in index.ts alongside other IPC handlers.

  RENDERER SIDE (ChatPanel/index.tsx):
  Before calling IPC, resolve the tab: const claudeTab = terminalStore.tabs.find(t => t.kind === 'claude')
  AUTO-SPAWN if no tab found: call handleLaunch('claude') — same function the + button uses,
  lives in Terminal/index.tsx. Lift or export it so ChatPanel can call it.
  Wait for tab to appear in terminalStore (watch with useEffect + tabs dependency).
  HOST-CORRECT COMMAND:
    Claude Code tab (kind === 'claude') → "/pathly <skill>"
    Codex tab (kind === 'codex')        → "Use Pathly <skill>"
  Then call window.electronAPI.writeToTerminal(command, tab.id).

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
  buildPathlyContext() fetches FSM state from GET http://127.0.0.1:8765/status → extract current_state and feature.
  DO NOT use /next_action — it mutates FSM state. Use /status (added in Conv 1 Phase 1).
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

---

## Conversation 6: Page Analyzer (Phases 19–21) — Track A

**Stories delivered:** S6.1, S6.2, S6.3
**Requires:** Conversation 5 complete.
**Verify:** `cd studio && npm run typecheck` — zero errors. Send a message and confirm `pageContext.elements` is populated in the request body.

**Prompt to paste:**
```
Read pathly/plans/studio-ai-chat/FEATURE_INDEX.md first to orient yourself and verify codebase paths.
Read pathly/plans/studio-ai-chat/IMPLEMENTATION_PLAN.md Phases 19–21 for full details.

Implement Studio AI Chat Conversation 6 (Phases 19–21) — Page Analyzer.

**Before editing anything:** glob/read the live repo to confirm every file path below exists.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/hooks/usePageAnalyzer.ts` — CREATE: self-registration hook
- `studio/src/renderer/src/store/pageAnalyzerStore.ts` — CREATE: live element registry
- `studio/src/renderer/src/lib/pageAnalyzer/index.ts` — CREATE: getPageContext()
- `studio/src/renderer/src/lib/pathlyContext.ts` — MODIFY: include pageContext
- Key Studio components (FlowEditor, StepEditor, ChatPanel, modals) — MODIFY: add usePageAnalyzer calls + data-conductor-id attributes

Scope:

Phase 19 — usePageAnalyzer hook:
  interface ElementMeta { id: string; type: 'button'|'input'|'select'|'link'|'panel'; label: string; value?: string; disabled?: boolean; visible?: boolean }
  usePageAnalyzer(meta: ElementMeta): void
  On mount: pageAnalyzerStore.register(meta)
  On unmount: pageAnalyzerStore.unregister(meta.id)
  On value/disabled changes: pageAnalyzerStore.update(id, patch) via useEffect deps

Phase 20 — pageAnalyzerStore + getPageContext():
  Zustand store: elements: Map<string, ElementMeta>, register(), unregister(), update()
  getPageContext(): PageContext — reads store, returns { elements: ElementMeta[], timestamp: number }
  Cap at 50 elements — prioritize: input > button > select > panel > link
  Add usePageAnalyzer calls to these Studio components (read each component first to find correct IDs):
    - FlowEditor: register flow canvas panel + "New Flow" button
    - StepEditor: register step form inputs + "Add Step" button + step type selector
    - ChatPanel: register send button + input textarea
    - Any modal/dialog: register CTA buttons
  Each registered DOM node must have data-conductor-id={id} attribute

Phase 21 — Inject page context into pathlyContext:
  Import getPageContext from lib/pageAnalyzer/index.ts
  Add pageContext: PageContext to buildPathlyContext() return type
  Pass pageContext in POST /chat body
  In chat_agent.py: add ## Current UI Elements section to system prompt (elements list, capped at 300 tokens)

Architectural rules:
- pageAnalyzerStore is renderer-only — no IPC, no server roundtrip
- The registry is the ground truth — never scrape DOM directly
- Do NOT copy BrightSky's PageAnalyzer files (that was the OLD approach for external pages)
- Do NOT touch MatchCard, embedRouter, or any Conv 1–5 work

Verify: cd studio && npm run typecheck
Check: open browser devtools → Application → look at pageAnalyzerStore state → confirm elements populate on Studio render.
Check: POST /chat request body includes pageContext.elements array.

After done, update pathly/plans/studio-ai-chat/PROGRESS.md phases 19–21 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
```

**Expected output:** Every key Studio component registers its interactive elements. `getPageContext()` returns a live JSON map. AI receives element context with every message.
**Files touched:** `usePageAnalyzer.ts`, `pageAnalyzerStore.ts`, `pageAnalyzer/index.ts`, `pathlyContext.ts`, Studio component files (FlowEditor, StepEditor, etc.)

---

## Conversation 7: Action Executor (Phases 22–23) — Track A

**Stories delivered:** S7.1, S7.2, S7.3
**Requires:** Conversation 6 complete (elements registered with `data-conductor-id`).
**Verify:** `cd studio && npm run typecheck` — zero errors. Call `window.electronAPI.executeUIAction({ type: 'click', elementId: 'btn-new-flow' })` from devtools console — "New Flow" button clicks.

**Prompt to paste:**
```
Read pathly/plans/studio-ai-chat/FEATURE_INDEX.md first to orient yourself and verify codebase paths.
Read pathly/plans/studio-ai-chat/IMPLEMENTATION_PLAN.md Phases 22–23 for full details.

Implement Studio AI Chat Conversation 7 (Phases 22–23) — Action Executor.

**Before editing anything:** glob/read every file path below. Read studio/src/main/index.ts to understand how IPC handlers are registered — match that pattern exactly.

**Codebase files this conversation touches:**
- `studio/src/main/ipc/uiActions.ts` — CREATE: IPC handler for click/fill/select
- `studio/src/main/index.ts` — MODIFY: register uiActions IPC handler
- `studio/src/renderer/src/lib/actionExecutor.ts` — CREATE: renderer-side executor
- `studio/src/renderer/src/App.tsx` — MODIFY: register window.__uiExecutor on mount

Scope:

Phase 22 — IPC handler (main process):
  ipcMain.handle('ui:execute-action', (event, action: UIAction) => { ... })
  UIAction: { type: 'click' | 'fill' | 'select'; elementId: string; value?: string }
  Main process forwards to renderer via:
    webContents.executeJavaScript(`window.__uiExecutor?.execute(${JSON.stringify(action)})`)
  This returns the result from the renderer executor.
  Expose on preload: window.electronAPI.executeUIAction(action: UIAction): Promise<{ok:boolean; error?:string}>
  Register in index.ts alongside other IPC handlers.

Phase 23 — Renderer executor (actionExecutor.ts):
  export function createUIExecutor() {
    return {
      execute(action: UIAction): { ok: boolean; error?: string } {
        const el = document.querySelector(`[data-conductor-id="${action.elementId}"]`)
        if (!el) return { ok: false, error: 'element not found' }
        if ((el as HTMLButtonElement).disabled) return { ok: false, error: 'element disabled' }
        switch (action.type) {
          case 'click': (el as HTMLElement).click(); break
          case 'fill': {
            // React controlled input: use nativeInputValueSetter
            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set
            nativeInputValueSetter?.call(el, action.value)
            el.dispatchEvent(new Event('input', { bubbles: true }))
            el.dispatchEvent(new Event('change', { bubbles: true }))
            break
          }
          case 'select': {
            (el as HTMLSelectElement).value = action.value!
            el.dispatchEvent(new Event('change', { bubbles: true }))
            break
          }
        }
        // Flash accent color for 400ms
        (el as HTMLElement).style.outline = '2px solid #22C55E'
        setTimeout(() => { (el as HTMLElement).style.outline = '' }, 400)
        return { ok: true }
      }
    }
  }
  In App.tsx: useEffect(() => { window.__uiExecutor = createUIExecutor() }, [])
  Add to window type declarations: window.__uiExecutor: { execute(action: UIAction): {...} }

Architectural rules:
- Main process NEVER directly manipulates DOM — it only forwards via executeJavaScript
- Renderer executor works ONLY on elements with data-conductor-id attribute
- Do NOT use coordinates or pixel positions — always use elementId
- Do NOT modify any existing IPC handlers

Verify: cd studio && npm run typecheck
Manual test: open Studio devtools console → window.electronAPI.executeUIAction({ type: 'click', elementId: '<a real id from devtools>' }) → element should click and flash green.

After done, update pathly/plans/studio-ai-chat/PROGRESS.md phases 22–23 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
```

**Expected output:** AI can click, fill, and select any registered Studio element via IPC. Element flashes accent color as visual confirmation.
**Files touched:** `ipc/uiActions.ts`, `main/index.ts`, `actionExecutor.ts`, `App.tsx`

---

## Conversation 8: Staged / Auto Automation Mode (Phases 24–26) — Track A

**Stories delivered:** S8.1, S8.2, S8.3, S8.4
**Requires:** Conversations 6 + 7 complete.
**Verify:** Type "create a test flow" → AutomationCard appears → approve each step → flow created in Studio.

**Prompt to paste:**
```
Read pathly/plans/studio-ai-chat/FEATURE_INDEX.md first to orient yourself and verify codebase paths.
Read pathly/plans/studio-ai-chat/IMPLEMENTATION_PLAN.md Phases 24–26 for full details.
Read pathly/plans/studio-ai-chat/DESIGN_SPEC.md — REQUIRED for StepQueue and AutomationCard visual spec.

Implement Studio AI Chat Conversation 8 (Phases 24–26) — Staged/Auto Automation Mode.

**Before editing anything:** glob/read every file path below.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/store/automationStore.ts` — CREATE: step queue state
- `studio/src/renderer/src/components/ChatPanel/StepQueue.tsx` — CREATE: staged/auto UI
- `studio/src/renderer/src/components/ChatPanel/AutomationCard.tsx` — CREATE: plan summary
- `studio/src/renderer/src/components/ChatPanel/ChatPanel.module.css` — MODIFY: add automation styles
- `studio/src/renderer/src/components/ChatPanel/index.tsx` — MODIFY: wire plan flow
- `studio/src/renderer/src/store/chatStore.ts` — MODIFY: add mode: 'chat'|'automation' to message shape
- `src/pathly_orchestrator/chat_agent.py` — MODIFY: add automation response type

Scope:

Phase 24 — automationStore:
  type AutomationStep = { id: string; description: string; action: UIAction; status: 'pending'|'approved'|'skipped'|'done'|'error'; errorMessage?: string }
  state: steps[], currentStepIndex, mode: 'staged'|'auto', status: 'idle'|'running'|'paused'|'done'|'error'
  actions: setSteps, approveStep, skipStep, setMode, advanceToNext, reset
  persist: mode only

Phase 25 — AutomationCard + StepQueue:
  AutomationCard:
    Shows: intent description + step count ("5 steps planned")
    [▶ Run All] button → setMode('auto') + start execution
    [Step by Step] button → setMode('staged') + show StepQueue
    [▶ Run All] disabled when pageContext.elements.length === 0 (tooltip: "No UI elements registered")
  StepQueue (staged mode):
    Each step as a card: step number, description, action preview ("click 'Add Step'")
    Current step (index === currentStepIndex): highlighted surface2 bg, [✓ Approve] [→ Skip] buttons
    Done step: dimmed opacity 0.5, ✓ badge (green) or → badge (muted)
    Pending step: surface bg, no buttons, muted text
  StepQueue (auto mode):
    Single progress bar: "2 / 5 steps" label + linear bar fill
    [■ Stop] button calls automationStore.status = 'paused'
  Both: show inline error for failed steps: "Step 4 failed — element not found"
  See DESIGN_SPEC.md for token/typography rules — match existing Conductor visual system

Phase 26 — Wire AI → action plan in chat flow:
  Extend POST /chat request: add pageContext and mode: 'automation' when intent seems like flow creation
  Detection heuristic: if message contains "create", "make", "build a flow", "add a step" → mode automation
  Otherwise → mode chat (existing explain behavior)
  chat_agent.py automation response format:
    { "type": "automation", "intent": "...", "steps": [{ "id": "step-1", "description": "...", "action": { "type": "click", "elementId": "btn-new-flow" } }] }
  AI must only use elementIds present in pageContext.elements — include this constraint in system prompt
  Chat response format (existing):
    { "type": "chat", "text": "..." }
  On receive:
    If type === 'automation': automationStore.setSteps(steps) → render AutomationCard in MessageList
    If type === 'chat': existing message append behavior
  Staged execution: approveStep(id) → executeAction(step.action) → advance index → render next step
  Auto execution: loop steps with 300ms delay, calling executeAction, updating status each step
  After all done: AI sends summary "Flow created — N steps executed" as a chat message

Architectural rules:
- pageContext is REQUIRED for automation mode — never generate action steps without it
- AI must reference only elementIds from the current pageContext — add this to system prompt
- Do NOT change the existing chat flow for normal skill-routing messages
- Do NOT add new IPC beyond what Conv 7 established

Verify: cd studio && npm run typecheck
E2E test: type "create a simple test flow" → AutomationCard appears → [Step by Step] → approve each step → flow visible in Studio.

After done, update pathly/plans/studio-ai-chat/PROGRESS.md phases 24–26 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
```

**Expected output:** User can describe a flow in plain English, see an action plan, approve steps one by one or run all at once, and see the flow created live in Studio.
**Files touched:** `automationStore.ts`, `StepQueue.tsx`, `AutomationCard.tsx`, `ChatPanel.module.css`, `ChatPanel/index.tsx`, `chatStore.ts`, `chat_agent.py`

---

## Conversation 9: Model Selector + WebLLM (Phases 27–29) — Track B

**Stories delivered:** S9.1, S9.2, S9.3, S9.4
**Requires:** Conversations 1–5 complete (can run in parallel with Track A after Conv 5).
**Source:** Port `WebLLMModels.js` and `WebLLMAPI.js` from `https://github.com/zakaihamilton/zakamurai` (`src/components/AI/`).
**Verify:** Select Phi-4 Mini → download/cache → send message → response streams from WebLLM (not Ollama).

**Prompt to paste:**
```
Read pathly/plans/studio-ai-chat/FEATURE_INDEX.md first to orient yourself and verify codebase paths.
Read pathly/plans/studio-ai-chat/IMPLEMENTATION_PLAN.md Phases 27–29 for full details.
Read pathly/plans/studio-ai-chat/DESIGN_SPEC.md — REQUIRED for ModelSelector visual spec.

Implement Studio AI Chat Conversation 9 (Phases 27–29) — Model Selector + WebLLM.

Source files to port (read these before writing anything):
  C:\Users\Yafit\brightsky-ai (check if WebLLM files exist) OR
  https://github.com/zakaihamilton/zakamurai/blob/main/src/components/AI/WebLLMModels.js
  https://github.com/zakaihamilton/zakamurai/blob/main/src/components/AI/WebLLMAPI.js
Read both files fully before writing any TypeScript.

**Before editing anything:** glob/read every file path below.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/data/models.ts` — CREATE: model definitions (ported from WebLLMModels.js)
- `studio/src/renderer/src/lib/webLLMEngine.ts` — CREATE: engine wrapper (ported from WebLLMAPI.js)
- `studio/src/renderer/src/store/modelStore.ts` — CREATE: selected model + cache state
- `studio/src/renderer/src/components/ChatPanel/ModelSelector.tsx` — CREATE: model picker UI
- `studio/src/renderer/src/components/ChatPanel/ConductorHeader.tsx` — MODIFY: add ModelSelector
- `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx` — MODIFY: model pill reads modelStore
- `studio/src/renderer/src/components/ChatPanel/index.tsx` — MODIFY: replace Ollama SSE with WebLLM
- `studio/package.json` — MODIFY: add @mlc-ai/web-llm

Scope:

Phase 27 — models.ts + webLLMEngine.ts:
  models.ts (port from WebLLMModels.js):
    interface Model { id: string; name: string; description: string; useCase: string; system: string; storage: string; speed: string; recommended?: boolean }
    4 models (use exact MLC model IDs):
      Qwen2.5-Coder-7B-Instruct-q4f16_1-MLC — best code quality
      Qwen3-4B-q4f16_1-MLC — balanced
      Phi-4-mini-instruct-q4f16_1-MLC — recommended, lower memory
      Llama-3.2-3B-Instruct-q4f16_1-MLC — small fallback
    export RECOMMENDED_MODEL_ID = 'Phi-4-mini-instruct-q4f16_1-MLC'

  webLLMEngine.ts (port from WebLLMAPI.js to TypeScript):
    getEngine(modelId: string, onProgress?: (pct: number) => void): Promise<MLCEngine> — singleton
    getCachedWebLLMModelIds(): Promise<string[]>
    cacheWebLLMModel(modelId: string, onProgress: (pct: number) => void): Promise<void>
    deleteCachedWebLLMModel(modelId: string): Promise<void>
    askWebLLM(prompt: string, systemPrompt: string, onChunk: (text: string) => void): Promise<string>
    Handle WebGPU not available: catch CreateMLCEngine error → throw { error: 'WebGPU not supported' }

Phase 28 — modelStore + ModelSelector UI:
  modelStore:
    selectedModelId: string (default RECOMMENDED_MODEL_ID)
    cachedModelIds: string[]
    downloadProgress: Record<string, number>
    setSelectedModel(id), setCached(ids), setProgress(id, pct)
    Persist: selectedModelId only

  ModelSelector (match the screenshots provided by user):
    Dropdown trigger in ConductorHeader: shows selected model short name + ▼ chevron + ℹ button
    Dropdown panel:
      Each model as a collapsible card: name, description, SYSTEM / STORAGE / SPEED rows (table)
      Badges: Recommended (teal), Cached (green), Selected (blue highlight on card)
      Cache toggle per card — on: calls cacheWebLLMModel() → shows linear progress bar
      Toggling off: calls deleteCachedWebLLMModel() after confirm
    Close on outside click
    Design tokens: match existing Conductor system (--bg, --surface, --accent, --border, --mono/--sans)
    Badges: use small pill style consistent with CLI pills in ConductorHeader

Phase 29 — Wire WebLLM into chat flow:
  Modify ChatPanel/index.tsx:
    Replace POST /chat SSE flow with local WebLLM call:
      const response = await askWebLLM(userMessage, buildSystemPrompt(context), onChunk)
      onChunk updates chatStore message stream (same as SSE chunks did)
    Keep POST /chat path as fallback when PATHLY_CHAT_BACKEND=ollama env var is set
    Default to WebLLM (no env var needed)
  ChatInput.tsx: model pill reads modelStore.selectedModelId short name
    If not cached: pill shows "[model] — download required" at 0.5 opacity, send disabled
  Handle WebGPU unavailable gracefully: show "WebGPU required" in explanation area

Architectural rules:
- WebLLM runs entirely in the renderer — no main process involvement
- Do NOT remove the Ollama/Python backend — keep it as optional legacy (PATHLY_CHAT_BACKEND=ollama)
- Do NOT change the MiniLM embedding router — it stays as-is
- Match the visual design from the screenshots: expandable model cards, SYSTEM/STORAGE/SPEED table rows

Verify: cd studio && npm run typecheck
Test: open ModelSelector → verify all 4 models listed with correct spec info → toggle Cache on Phi-4 Mini → wait for download → select it → send a message → response streams from WebLLM.

After done, update pathly/plans/studio-ai-chat/PROGRESS.md phases 27–29 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
```

**Expected output:** User can pick their local AI model, download it with one toggle, and all Conductor responses stream from WebLLM with no Ollama required.
**Files touched:** `models.ts`, `webLLMEngine.ts`, `modelStore.ts`, `ModelSelector.tsx`, `ConductorHeader.tsx`, `ChatInput.tsx`, `ChatPanel/index.tsx`, `studio/package.json`
