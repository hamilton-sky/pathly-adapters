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

Phase 0a — Fix Claude/Codex spawning (do this first, it unblocks everything):
  There are TWO bugs in terminal.ts — both must be fixed:

  Bug 1 — ALLOWED_SHELLS (line 13): Add 'claude' and 'codex' to the set.
  PaneTabBar passes these as command to terminal:spawn; without them it returns "Shell not allowed".

  Bug 2 — Windows always spawns powershell.exe (line 71):
    CURRENT: const shell = process.platform === 'win32' ? 'powershell.exe' : (command ?? 'bash')
    This ignores command on Windows. A Claude tab will open PowerShell, not Claude Code.
  Fix by adding a resolveShell helper:
    function resolveShell(command?: string): { shell: string; args: string[] } {
      if (process.platform !== 'win32') return { shell: command ?? 'bash', args: [] }
      if (command === 'claude') return { shell: 'cmd.exe', args: ['/k', 'claude'] }
      if (command === 'codex')  return { shell: 'cmd.exe', args: ['/k', 'codex'] }
      return { shell: 'powershell.exe', args: [] }
    }
  Replace the const shell/shellArgs lines with: const { shell, args: shellArgs } = resolveShell(command)
  The rest of pty.spawn(...) is unchanged.

  Done when: On Windows, A Claude tab opens Claude Code CLI and Codex tab opens Codex CLI.

  Mac/Linux note: resolveShell spawns 'claude'/'codex' directly — no wrapper needed. But
  Electron's main process has a restricted PATH (not the user's full shell PATH). If the CLI
  is in a user-local path (e.g. /opt/homebrew/bin, ~/.npm-global/bin) and the spawn fails
  with "command not found", see the fallback in Phase 0a: resolve the full path with `which`
  at startup and cache it. Only add this if bare-name spawn fails in testing.

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
  - Do NOT touch PTY spawning logic beyond the resolveShell fix in Phase 0a
  - Do NOT touch any other IPC handlers, data flow, or FSM code
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
    Calls read_state() from eventlog.py (pure read, NO write).
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
  get_fsm_state(project_root) -> dict — calls read_state() from eventlog.py directly (pure read).
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
- `studio/src/renderer/src/components/TopBar.tsx` — MODIFY: add Brain icon toggle for Conductor

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
Read studio/src/main/preload/index.ts — the actual terminal API surface is `window.pathly.terminal.*`.
Read studio/src/renderer/src/store/terminalStore.ts and store/projectStore.ts — needed for launchTerminal.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/components/ChatPanel/MatchCard.tsx` — CREATE
- `studio/src/renderer/src/components/ChatPanel/OutputSnippet.tsx` — CREATE
- `studio/src/renderer/src/lib/launchTerminal.ts` — CREATE: shared auto-spawn utility
- `studio/src/renderer/src/components/ChatPanel/index.tsx` — MODIFY: Run action + PTY subscription
- `studio/src/renderer/src/store/chatStore.ts` — MODIFY: add targetKind field
- `studio/src/renderer/src/components/ChatPanel/ConductorHeader.tsx` — MODIFY: host pill toggles targetKind

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

- Phase 11: Read terminal.ts, preload/index.ts, and terminalStore.ts before writing anything.

  NOTE: ALLOWED_SHELLS and Windows spawning were fixed in Phase 0a (Conv 0). Do not repeat here.
  NO new Electron main-process IPC file (chat.ts) is needed — the existing terminal API covers everything.

  KEY FACTS about the existing API (read preload/index.ts to verify):
  - window.pathly.terminal.spawn(tabId, cwd, command?) — spawns a PTY
  - window.pathly.terminal.write(tabId, data) — writes to a PTY (ipcRenderer.send, not invoke)
  - window.pathly.terminal.onData(tabId, cb) — subscribes to PTY output
  - window.pathly.terminal.onExit(cb) — subscribes to tab exit events
  ChatPanel is in the same BrowserWindow renderer as Terminal — same webContentsId — so
  terminal:write's ptyOwners check (terminal.ts:103) passes transparently. No bypass needed.

  CREATE studio/src/renderer/src/lib/launchTerminal.ts:
    import { useTerminalStore } from '../store/terminalStore'
    import { useProjectStore } from '../store/projectStore'
    export async function launchTerminal(kind: 'claude' | 'codex'): Promise<string> {
      const { open, toggle, addTab } = useTerminalStore.getState()
      if (!open) toggle()                              // open dock (mirrors Terminal/index.tsx:77)
      const tabId = crypto.randomUUID()               // no uuid package — already in codebase
      const label = kind === 'claude' ? 'A Claude' : '✳ Codex'
      const cwd = useProjectStore.getState().projectPath  // must be project root, not userHome
      addTab(tabId, label, 'left', kind)
      await window.pathly.terminal.spawn(tabId, cwd, kind)
      return tabId
    }
  Calling addTab() before spawn() ensures the tab is in the store before PTY data starts flowing.

  RENDERER SIDE (ChatPanel/index.tsx):
  const { targetKind } = useChatStore()           // targetKind driven by ConductorHeader host pill
  const { tabs } = useTerminalStore()             // tabs live in terminalStore, not chatStore
  let targetTab = tabs.find(t => t.kind === targetKind)
  if (!targetTab) {
    const tabId = await launchTerminal(targetKind)
    targetTab = useTerminalStore.getState().tabs.find(t => t.id === tabId)!
  }
  // Sanitize command (renderer-side):
  const safe = skill.command.replace(/[;&|><]/g, '').trim()
  // Host-correct format:
  const cmd = targetTab.kind === 'claude' ? `/pathly ${safe}` : `Use Pathly ${safe}`
  window.pathly.terminal.write(targetTab.id, cmd + '\n')

  OutputSnippet PTY subscription:
  useEffect(() => {
    if (!activeTabId) return
    return window.pathly.terminal.onData(activeTabId, (data) => {
      // strip ANSI codes, append to outputLines in chatStore
    })
  }, [activeTabId])

Architectural rules:
- MatchCard replaces the old TerminalApproval concept — do NOT create a TerminalApproval component.
- Do NOT create main/ipc/chat.ts — no new main-process IPC is needed.
- Do NOT modify terminal.ts in this conversation — Phase 0a already handled it.
- Do NOT modify FSM IPC handlers or Python backend.

Verify: cd studio && npm run typecheck
Expected: zero TypeScript errors. A MatchCard renders in the panel. Clicking Run writes to the terminal.

After done, update pathly/plans/studio-ai-chat/PROGRESS.md phases 9–11 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** MatchCard shows matched skill + confidence + Run/"Not this" buttons. Run writes the host-correct command (`/pathly <skill>` or `Use Pathly <skill>`) to the correct terminal tab via `window.pathly.terminal.write`. OutputSnippet shows live PTY lines.
**Files touched:** `MatchCard.tsx`, `OutputSnippet.tsx`, `launchTerminal.ts`, `ChatPanel/index.tsx`, `chatStore.ts`, `ConductorHeader.tsx`

---

## Conversation 4: Context Injection (Phases 12–14)

**Stories delivered:** S4.1, S4.2
**Requires:** Conversation 3 complete.
**Verify:** `cd studio && npm run typecheck` — zero errors. phi4-mini explanation references FSM stage by name.

**Prompt to paste:**
```
Read pathly/plans/studio-ai-chat/FEATURE_INDEX.md first to orient yourself and verify codebase paths.
Read pathly/plans/studio-ai-chat/IMPLEMENTATION_PLAN.md Phases 12–14 for full details.

Implement Studio AI Chat Conversation 4 (Phases 12 and 14 only — Phase 13 is removed).

**Before editing anything:** glob/read every file path below to confirm it exists.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/lib/pathlyContext.ts` — CREATE: FSM context builder
- `studio/src/renderer/src/components/ChatPanel/index.tsx` — MODIFY: inject context per message

**Phase 13 is intentionally skipped — do not implement it.**
Phase 13 was a PageAnalyzer copy from BrightSky. The architecture moved to a static Studio
schema (Conv 6, Phase 19) and Playwright executor (Conv 7). Do NOT create a pageAnalyzer/
directory, do NOT copy any BrightSky files, do NOT add usePageAnalyzer hooks or
data-conductor-id attributes anywhere.

Scope:
- Phase 12: Create studio/src/renderer/src/lib/pathlyContext.ts.
  export async function buildPathlyContext(): Promise<PathlyContext>
  Fetch FSM state from GET http://127.0.0.1:8765/status → extract current_state and feature.
  CRITICAL: DO NOT call /next_action — it writes conv_start_sha to disk on every call.
  /status is the read-only replacement (added in Conv 1 Phase 1).
  KNOWN_SKILLS: static list for now (will be MiniLM-powered in Conv 5).
  Wrap FSM fetch in try/catch → fallback { fsmStage: "unknown", featureName: "" }.
  Returns: { fsmStage: string, featureName: string, skills: string[] }
  Note: NO screenElements field — static schema (Conv 6) handles UI layout separately.

- Phase 14: Modify ChatPanel/index.tsx.
  Call buildPathlyContext() before each POST /chat.
  Add context field to the request body sent to /chat.
  phi4-mini explanation should now reference the current FSM stage and feature.

Architectural rules:
- Do NOT create pageAnalyzer/, lib/pageAnalyzer/, or any runtime DOM scanner.
- Do NOT add screenElements to PathlyContext — it was removed from the architecture.
- Do NOT add new IPC calls.
- Do NOT touch MatchCard, chatStore approval logic, or any Conv 3 work.

Verify: cd studio && npm run typecheck
Expected: zero TypeScript errors. phi4-mini explanation mentions current FSM stage by name.

After done, update pathly/plans/studio-ai-chat/PROGRESS.md phases 12 and 14 to DONE (13 stays as REMOVED).

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** phi4-mini explanation knows the current FSM stage, feature name, and available skills.
**Files touched:** `pathlyContext.ts`, `ChatPanel/index.tsx`

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

## Conversation 6: Static Studio Schema + Context Injection (Phases 19–20) — Track A

**Stories delivered:** S6.1, S6.2
**Requires:** Conversation 5 complete.
**Verify:** `cd studio && npm run typecheck` — zero errors. Send a message, check POST /chat body includes `studioSchema` array with 10+ elements.

**Prompt to paste:**
```
Read pathly/plans/studio-ai-chat/FEATURE_INDEX.md first.
Read pathly/plans/studio-ai-chat/IMPLEMENTATION_PLAN.md Phases 19–20.

Implement Studio AI Chat Conversation 6 (Phases 19–20) — Static Studio Schema.

Files:
- studio/src/renderer/src/data/studioSchema.ts — CREATE
- studio/src/renderer/src/lib/pathlyContext.ts — MODIFY

Phase 19 — studioSchema.ts:
  interface StudioElement { id: string; screen: string; type: 'button'|'input'|'select'|'panel'; label: string; description: string }

  Define elements for these screens (read the actual Studio source to get real labels):
    FlowEditor screen: "New Flow" button, flow name input, flow list panel
    StepEditor screen: "Add Step" button, step type selector, step name input, URL input field, "Save" button
    ChatPanel screen: send button, message input
    Modals: "Save" button, "Cancel" button, "Delete" button

  export function getStudioSchema(): StudioElement[]
  export function getSchemaForScreen(screen: string): StudioElement[]

Phase 20 — pathlyContext.ts:
  Import getStudioSchema from data/studioSchema.ts
  Add studioSchema to buildPathlyContext() return type and value
  Pass studioSchema in POST /chat body

  In src/pathly_orchestrator/chat_agent.py:
    Add ## Studio UI Elements section to system prompt
    List elements grouped by screen: "FlowEditor: [New Flow (button)], [Flow Name (input)]..."
    Cap at 400 tokens
    AI instruction: "When generating automation steps, use only labels from this list"

Architectural rules:
- This is a static constant, NOT a runtime registry — no hooks, no subscriptions
- Read actual Studio component source to find real button/input labels before writing the schema
- Do NOT add usePageAnalyzer hooks or data-conductor-id anywhere
- Do NOT touch MatchCard, embedRouter, or any Conv 1–5 work

Verify: npm run typecheck. Send a message to /chat, inspect request body — studioSchema must be present.
After done, update PROGRESS.md phases 19–20 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
```

**Expected output:** `studioSchema.ts` exports a typed constant describing all key Studio UI elements. AI system prompt includes a `## Studio UI Elements` section. POST /chat body includes the schema.
**Files touched:** `data/studioSchema.ts`, `lib/pathlyContext.ts`, `src/pathly_orchestrator/chat_agent.py`

---

## Conversation 7: Playwright Executor (Phases 21–21.5–22) — Track A

**Stories delivered:** S7.1, S7.2, S7.3
**Requires:** Conversation 6 complete.
**Verify:** `cd studio && npm run typecheck` — zero errors. Open Studio devtools console: `window.electronAPI.executeAutomationStep({ type: 'click', label: 'New Flow' })` — New Flow button clicks.

**Prompt to paste:**
```
Read pathly/plans/studio-ai-chat/FEATURE_INDEX.md first.
Read pathly/plans/studio-ai-chat/IMPLEMENTATION_PLAN.md Phases 21, 21.5, and 22.

Implement Studio AI Chat Conversation 7 (Phases 21–21.5–22) — Playwright Executor with 3-tier element resolution.

Files to create/modify:
- studio/package.json — MODIFY: add @playwright/test
- studio/src/main/automation/playwrightExecutor.ts — CREATE
- studio/src/renderer/src/lib/elementResolver.ts — CREATE
- studio/src/main/ipc/automation.ts — CREATE
- studio/src/preload/index.ts (or equivalent preload file) — MODIFY: expose executeAutomationStep
- studio/src/main/index.ts — MODIFY: init Playwright + register IPC

---

Phase 21 — playwrightExecutor.ts:

  import { chromium, Page, Locator } from '@playwright/test'

  export type AutomationStep = { type: 'click'|'fill'|'select'; label: string; value?: string; screen?: string }
  export type StepResult = { ok: boolean; error?: string; attempts?: number }

  export class PlaywrightExecutor {
    private page: Page | null = null

    constructor(
      private semanticResolve: (candidates: string[], target: string) => Promise<{label: string; score: number}> = async () => ({ label: '', score: 0 }),
      private llmResolve: (candidates: string[], target: string) => Promise<{label: string | null}> = async () => ({ label: null })
    ) {}

    async connect(cdpUrl: string): Promise<void> {
      const browser = await chromium.connectOverCDP(cdpUrl)
      const context = browser.contexts()[0]
      this.page = context.pages()[0]
    }

    async executeStep(step: AutomationStep): Promise<StepResult> {
      if (!this.page) return { ok: false, error: 'Playwright not connected' }
      const backoffs = [500, 1000, 1500]
      for (let attempt = 1; attempt <= 3; attempt++) {
        const locator = await this.resolveElement(step.label)
        if (!locator) {
          if (attempt < 3) { await this.sleep(backoffs[attempt - 1]); continue }
          return { ok: false, error: `element not found after all tiers: ${step.label}`, attempts: 3 }
        }
        if (await locator.isDisabled()) {
          await this.sleep(800)
          continue
        }
        if (step.type === 'click') await locator.click()
        if (step.type === 'fill') await locator.fill(step.value ?? '')
        if (step.type === 'select') await locator.selectOption(step.value ?? '')
        return { ok: true, attempts: attempt }
      }
      return { ok: false, error: `element not found after all tiers: ${step.label}`, attempts: 3 }
    }

    private async resolveElement(label: string): Promise<Locator | null> {
      if (!this.page) return null

      // Tier 1: deterministic Playwright locator strategies
      const tier1Strategies: Array<() => Locator> = [
        () => this.page!.getByRole('button', { name: label }),
        () => this.page!.getByRole('combobox', { name: label }),
        () => this.page!.getByRole('textbox', { name: label }),
        () => this.page!.getByRole('link', { name: label }),
        () => this.page!.getByRole('tab', { name: label }),
        () => this.page!.getByLabel(label),
        () => this.page!.getByPlaceholder(label),
        () => this.page!.getByText(label, { exact: true }),
        () => this.page!.getByText(label, { exact: false }),
        () => this.page!.locator(`[title="${label}"]`),
      ]
      for (const strategy of tier1Strategies) {
        try {
          let loc = strategy()
          const count = await loc.count()
          if (count === 1) return loc
          if (count > 1) {
            const visible = loc.filter({ hasNot: this.page!.locator('[hidden]') })
            if (await visible.count() === 1) return visible
          }
        } catch {}
      }

      // Tier 2: MiniLM semantic similarity via renderer round-trip
      const snapshot = await this.page.accessibility.snapshot()
      const candidates: Array<{ name: string; role: string }> = []
      const walk = (node: any) => {
        if (node?.name && node?.role) candidates.push({ name: node.name, role: node.role })
        for (const child of node?.children ?? []) walk(child)
      }
      walk(snapshot)
      const names = candidates.map(c => c.name)
      const { label: semanticLabel, score } = await this.semanticResolve(names, label)
      if (score >= 0.65 && semanticLabel) {
        const match = candidates.find(c => c.name === semanticLabel)
        if (match) {
          try {
            return this.page.getByRole(match.role as any, { name: match.name })
          } catch {}
        }
      }

      // Tier 3: phi4-mini LLM fallback (stub in Conv 7 — always returns null until Conv 9)
      const { label: llmLabel } = await this.llmResolve(names, label)
      if (llmLabel) {
        try { return this.page.getByText(llmLabel, { exact: true }) } catch {}
      }

      return null
    }

    private sleep(ms: number) { return new Promise(r => setTimeout(r, ms)) }
  }

---

Phase 21.5 — studio/src/renderer/src/lib/elementResolver.ts:

  // Renderer-side handlers for semantic and LLM element resolution.
  // Called by the main process via IPC round-trip (main sends a request channel,
  // renderer replies on the :result channel).

  import { ipcRenderer } from 'electron'
  // Re-use the MiniLM pipeline singleton from embedRouter.ts
  import { getPipeline, cosineSim } from './embedRouter'

  export async function handleSemanticResolve(
    candidates: string[],
    target: string
  ): Promise<{ label: string; score: number }> {
    const pipe = await getPipeline()
    const targetEmb = await pipe(target, { pooling: 'mean', normalize: true })
    let best = { label: '', score: -1 }
    for (const c of candidates) {
      const emb = await pipe(c, { pooling: 'mean', normalize: true })
      const score = cosineSim(targetEmb.data, emb.data)
      if (score > best.score) best = { label: c, score }
    }
    return best
  }

  export async function handleLLMResolve(
    candidates: string[],
    target: string
  ): Promise<{ label: string | null }> {
    // Placeholder until Conv 9 ships WebLLM.
    // Conv 9 will: import { webLLMEngine } from './webLLMEngine' and call generate().
    return { label: null }
  }

  // Register IPC listeners once at renderer startup.
  // Call registerElementResolverListeners() from renderer main.tsx or equivalent init.
  export function registerElementResolverListeners() {
    ipcRenderer.on('automation:semantic-resolve', async (_event, { candidates, target }) => {
      const result = await handleSemanticResolve(candidates, target)
      ipcRenderer.send('automation:semantic-resolve:result', result)
    })
    ipcRenderer.on('automation:llm-resolve', async (_event, { candidates, target }) => {
      const result = await handleLLMResolve(candidates, target)
      ipcRenderer.send('automation:llm-resolve:result', result)
    })
  }

Call registerElementResolverListeners() near the top of the renderer entry point (before any user interaction).

---

Phase 22 — studio/src/main/ipc/automation.ts + index.ts:

  // automation.ts (main process)
  import { ipcMain, BrowserWindow } from 'electron'
  import { PlaywrightExecutor, AutomationStep } from '../automation/playwrightExecutor'

  // Main → renderer round-trip helper
  function makeRendererCaller(channel: string) {
    return (candidates: string[], target: string): Promise<any> =>
      new Promise((resolve) => {
        const win = BrowserWindow.getAllWindows()[0]
        win.webContents.send(channel, { candidates, target })
        ipcMain.once(`${channel}:result`, (_e, result) => resolve(result))
      })
  }

  const semanticResolve = makeRendererCaller('automation:semantic-resolve')
  const llmResolve      = makeRendererCaller('automation:llm-resolve')

  // Singleton created here so callbacks are injected at construction time
  export const playwrightExecutor = new PlaywrightExecutor(semanticResolve, llmResolve)

  export function registerAutomationIPC() {
    ipcMain.handle('automation:execute-step', async (_event, step: AutomationStep) =>
      playwrightExecutor.executeStep(step)
    )
  }

  In index.ts:
    app.commandLine.appendSwitch('remote-debugging-port', '9222')  // MUST be before BrowserWindow creation
    // After app ready + window created:
    import { playwrightExecutor, registerAutomationIPC } from './ipc/automation'
    await playwrightExecutor.connect('http://localhost:9222')
    registerAutomationIPC()

  Preload (expose to renderer):
    window.electronAPI.executeAutomationStep(step: AutomationStep): Promise<StepResult>
    // uses ipcRenderer.invoke('automation:execute-step', step)

  // automation:semantic-resolve and automation:llm-resolve are main→renderer pushes.
  // They do NOT need preload exposure — main sends them directly via webContents.send.

Architectural rules:
- Playwright runs in main process (Node.js) — not renderer
- CDP remote debugging port MUST be set BEFORE BrowserWindow is created
- Do NOT use executeJavaScript, data-conductor-id, or any DOM manipulation
- Do NOT modify the existing terminal IPC or FSM IPC
- Tier 3 LLM fallback is a stub in this conversation — handleLLMResolve always returns null
  The interface is final; Conv 9 will fill in the body without touching any other file

Verify: npm run typecheck — zero errors. Open Studio devtools console:
  window.electronAPI.executeAutomationStep({ type: 'click', label: 'New Flow' })
  The New Flow button should click.
After done, update PROGRESS.md phases 21–22 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
```

**Expected output:** Playwright connects to the Electron window via CDP. `resolveElement` runs a 3-tier cascade: (1) 10 deterministic Playwright locator strategies with multi-match filtering, (2) MiniLM semantic similarity via renderer round-trip IPC, (3) phi4-mini LLM fallback stub returning null. Self-healing retries up to 3 times with exponential backoff. IPC bridge exposes `executeAutomationStep` to the renderer.
**Files touched:** `studio/package.json`, `main/automation/playwrightExecutor.ts`, `renderer/src/lib/elementResolver.ts`, `main/ipc/automation.ts`, `preload/index.ts`, `main/index.ts`

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
  type AutomationStep = { id: string; description: string; action: { type: 'click'|'fill'|'select'; label: string; value?: string; screen?: string }; status: 'pending'|'approved'|'skipped'|'done'|'error'; errorMessage?: string }
  state: steps[], currentStepIndex, mode: 'staged'|'auto', status: 'idle'|'running'|'paused'|'done'|'error'
  actions: setSteps, approveStep, skipStep, setMode, advanceToNext, reset
  persist: mode only

Phase 25 — AutomationCard + StepQueue:
  AutomationCard:
    Shows: intent description + step count ("5 steps planned")
    [▶ Run All] button → setMode('auto') + start execution
    [Step by Step] button → setMode('staged') + show StepQueue
    [▶ Run All] disabled when studioSchema is not present in context (tooltip: "Studio schema unavailable")
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
  Extend POST /chat request: add studioSchema and mode: 'automation' when intent seems like flow creation
  Detection heuristic: if message contains "create", "make", "build a flow", "add a step" → mode automation
  Otherwise → mode chat (existing explain behavior)
  chat_agent.py automation response format:
    { "type": "automation", "intent": "...", "steps": [{ "id": "step-1", "description": "...", "action": { "type": "click", "label": "New Flow", "screen": "FlowEditor" } }] }
  AI must only use labels from studioSchema — include this constraint in system prompt
  Chat response format (existing):
    { "type": "chat", "text": "..." }
  On receive:
    If type === 'automation': automationStore.setSteps(steps) → render AutomationCard in MessageList
    If type === 'chat': existing message append behavior
  Staged execution: approveStep(id) → window.electronAPI.executeAutomationStep(step.action) → advance index
  Auto execution: loop steps with 300ms delay, calling window.electronAPI.executeAutomationStep, updating status each step
  After all done: AI sends summary "Flow created — N steps executed" as a chat message

Architectural rules:
- studioSchema is REQUIRED context for automation mode — never generate action steps without it
- AI must reference only labels from studioSchema — add this to system prompt
- Do NOT use executeAction(), actionExecutor.ts, data-conductor-id, or window.__uiExecutor
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

CRITICAL PRE-FLIGHT — WebGPU must be enabled in Electron before any WebLLM code will work:
Electron disables WebGPU by default. Without this, CreateMLCEngine() throws immediately.
In studio/src/main/index.ts, add before app.whenReady():
  app.commandLine.appendSwitch('enable-unsafe-webgpu')
  app.commandLine.appendSwitch('enable-features', 'Vulkan')
Also add experimentalFeatures: true to the BrowserWindow webPreferences.
Do this FIRST, before writing any WebLLM code. Verify with: navigator.gpu !== undefined === true in renderer devtools.

Source files to port (read these before writing anything):
  C:\Users\Yafit\brightsky-ai (check if WebLLM files exist) OR
  https://github.com/zakaihamilton/zakamurai/blob/main/src/components/AI/WebLLMModels.js
  https://github.com/zakaihamilton/zakamurai/blob/main/src/components/AI/WebLLMAPI.js
Read both files fully before writing any TypeScript.

**Before editing anything:** glob/read every file path below.

**Codebase files this conversation touches:**
- `studio/src/main/index.ts` — MODIFY: add WebGPU command-line switches (pre-flight)
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
