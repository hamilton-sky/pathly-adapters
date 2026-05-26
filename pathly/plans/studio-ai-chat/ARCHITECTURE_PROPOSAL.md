---

---
# Studio AI Chat — Architecture Proposal

## Problem Statement

Pathly Studio users need to run Pathly pipeline skills (`/pathly build`, `/pathly review`, etc.)
through Claude Code or Codex CLIs in embedded terminals. Currently they must remember skill names
and type them manually. The Conductor panel removes this by translating plain-English intent into
the correct skill command automatically.

## Proposed Solution

A three-layer system: Python explainer server, React + Zustand Conductor UI, and Electron IPC bridge.
Routing is done by a local embedding model (MiniLM) — not by the LLM — which makes it fast,
accurate, and unable to hallucinate skill names.

## Two-Model Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ROUTING LAYER (fast, deterministic, no hallucination)                      │
│                                                                             │
│  User intent (text)                                                         │
│       │                                                                     │
│       ▼                                                                     │
│  MiniLM (all-MiniLM-L6-v2)  ←  transformers.js in Electron renderer        │
│       │  ~22ms, runs offline, no server                                     │
│       │  cosine similarity vs pre-embedded skills.json                      │
│       ▼                                                                     │
│  Top-k matches: [ {skill, score}, {skill, score}, {skill, score} ]         │
│       │                                                                     │
│       ▼                                                                     │
│  MatchCard renders instantly (before LLM responds)                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
           │  (async, parallel to MatchCard render)
           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  EXPLANATION LAYER (rich context, slower)                                   │
│                                                                             │
│  POST /chat → chat_agent.py → phi4-mini (Ollama :11434)                    │
│       │  system prompt: "explainer" role                                    │
│       │  context: { fsmStage, featureName, matchedSkill, skillDescription } │
│       │  output: 2–3 sentence explanation, streamed via SSE                 │
│       ▼                                                                     │
│  AI explanation bubble appears below MatchCard                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
           │  user clicks ▶ Run
           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  EXECUTION LAYER                                                            │
│                                                                             │
│  window.pathly.terminal.write(tabId, command + '\n')                        │
│       │  Claude Code tab: "/pathly build\n"                                 │
│       │  Codex tab:       "Use Pathly build\n"                              │
│       ▼                                                                     │
│  OutputSnippet reads PTY onData → shows last 5 lines in chat               │
│  When command completes → AI embed-matches next suggested skill             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Full System Diagram

```
Studio Renderer (React 18 + Zustand + CSS Modules + JetBrains Mono)
  ┌─ ConductorHeader ─────────────────────────────────────────────┐
  │  ⚡ Conductor · [Manual/Auto] · [Claude Code ●] [Codex ●]     │
  └───────────────────────────────────────────────────────────────┘
  ┌─ SkillsPanel ─────────────────────────────────────────────────┐
  │  [plan][po][storm][build][review][test][retro]...             │
  └───────────────────────────────────────────────────────────────┘
  ┌─ MessageList ─────────────────────────────────────────────────┐
  │  User message → MatchCard → phi4-mini explanation → Output    │
  └───────────────────────────────────────────────────────────────┘
  ┌─ ChatInput ───────────────────────────────────────────────────┐
  │  [intent textarea] [➤]  [◈ MiniLM] [● phi4-mini]            │
  └───────────────────────────────────────────────────────────────┘
         │                                    │
         │ matchIntent() ~22ms                │ POST /chat (SSE)
         ▼                                    ▼
  embedRouter.ts                   Pathly Python Server :8765
  (MiniLM, transformers.js)        chat_agent.py → Ollama :11434
  skills.json vectors              phi4-mini explainer
         │
         │ Run click
         ▼
  window.pathly.terminal.write(tabId, cmd + '\n')
  (renderer-side — no new main-process IPC needed;
   same webContentsId passes ptyOwners check)
         │
         ▼
  Claude Code tab: "/pathly <skill>\n"
  Codex tab:       "Use Pathly <skill>\n"
```

## Key Design Decisions

### Decision 1: Embedding similarity for routing, not LLM
- **Options:** phi4-mini decides the skill, regex matching, embedding similarity
- **Chosen:** Embedding similarity (MiniLM)
- **Rationale:** LLM routing hallucinates skill names, is slow (~2s), and is non-deterministic.
  Regex is brittle. MiniLM is 22ms, can't hallucinate (only ranks real skills), and improves
  automatically when skill descriptions improve. transformers.js runs in the Electron renderer
  with no extra server or process.

### Decision 2: phi4-mini as explainer only
- **Options:** phi4-mini routes AND explains, embedding routes + phi4-mini explains, no LLM
- **Chosen:** phi4-mini explains only; routing is always MiniLM
- **Rationale:** Each model does what it's best at. MiniLM is deterministic and fast for matching.
  phi4-mini is good at natural-language explanation with context. Mixing the two roles makes the
  system unpredictable — phi4-mini might suggest a different skill than MiniLM matched.

### Decision 3: Skills as the command vocabulary, host-correct format per terminal
- **Options:** Free-form CLI commands, fixed Pathly skills only, hybrid
- **Chosen:** Pathly skills only — but written in the format the target terminal understands:
  - Claude Code tab: `/pathly <skill>` (e.g. `/pathly review`)
  - Codex tab: `Use Pathly <skill>` (e.g. `Use Pathly review`)
- **Rationale:** All user actions in the pipeline are Pathly skills. Claude Code and Codex are
  the execution surfaces, not separate routing targets. The user says "I want to review the code"
  and the Conductor generates the right syntax for whichever terminal is active.

### Decision 4: Pre-embed skills at startup
- **Options:** Embed on first message, embed at startup, pre-computed and bundled
- **Chosen:** Embed at startup (lazy, on first render of ChatPanel)
- **Rationale:** First-message latency must feel instant. Startup embedding takes ~500ms for
  14 skills and happens in the background. Pre-computed vectors bundled at build time would
  need rebuilding every time skills.json changes — startup embedding is simpler and always fresh.

### Decision 5: Confidence threshold UI
- **Options:** Always show top match only, show confidence score, show multiple options
- **Chosen:** Show confidence score + visual state + alternatives
- **Rationale:** Trust is critical. Users won't use the panel if it silently runs wrong skills.
  The amber "~ UNSURE" state teaches users when to double-check. The alternatives chips let
  them self-correct in one tap without retyping.

## Component Architecture

| Component | File | Responsibility |
|---|---|---|
| `ConductorHeader` | `ChatPanel/ConductorHeader.tsx` | Title, Manual/Auto toggle, CLI status pills |
| `SkillsPanel` | `ChatPanel/SkillsPanel.tsx` | Skill chips, collapsible, handles chip click |
| `ChatPanel` | `ChatPanel/index.tsx` | Container, collapse/expand, wires subcomponents |
| `MessageList` | `ChatPanel/MessageList.tsx` | Scrollable message + card list |
| `MatchCard` | `ChatPanel/MatchCard.tsx` | Match result, confidence bar, alts, Run/Not this |
| `OutputSnippet` | `ChatPanel/OutputSnippet.tsx` | Live PTY output lines, status indicator |
| `ChatInput` | `ChatPanel/ChatInput.tsx` | Textarea, Send/Stop, MiniLM + phi4-mini pills |
| `embedRouter` | `lib/embedRouter.ts` | MiniLM wrapper, startup pre-embedding, matchIntent() |
| `skillsManifest` | `lib/skillsManifest.ts` | Typed loader for skills.json |
| `pathlyContext` | `lib/pathlyContext.ts` | FSM state context builder |
| `launchTerminal` | `lib/launchTerminal.ts` | Renderer utility: addTab + spawn in one call |
| `chatStore` | `store/chatStore.ts` | All chat state: messages, match, streaming, autoApprove |

## Risks

- **MiniLM cold-start (first launch):** Model downloads ~22MB on first run. Mitigate: show
  `◈ Loading…` pill, cache model in app data dir, pre-warm at app launch.
- **Poor skill descriptions:** Match quality depends on skill description text. Short or
  generic descriptions produce low-confidence matches. Mitigate: each skill in skills.json
  must have a specific 1–2 sentence description including when to use it.
- **phi4-mini offline:** Explanation is non-blocking — MatchCard appears without it.
  ChatPanel shows "Ollama offline — explanation unavailable" in the explanation area.
- **PTY output noise:** Some CLIs produce ANSI escape codes in output. Mitigate: strip
  ANSI from OutputSnippet display lines before showing in chat.
- **Auto-approve + wrong match:** If autoApprove is on and confidence is low, wrong skill
  runs. Mitigate: auto-approve is disabled for matches below 65% confidence regardless of setting.

---

## Automation Architecture (Track A — Convs 6–8)

### Static Studio schema (not a runtime registry)

Studio is our own app with a fixed layout. Rather than scanning the DOM at runtime or requiring
every component to register itself, we describe Studio's key UI elements once as a typed constant
in `studioSchema.ts`.

**Why static:**
- Fixed app — the layout doesn't change at runtime (no user-configurable panels, no plugin slots)
- Always accurate — no stale registry state, no mount/unmount race conditions
- Zero runtime overhead — no hooks, no Zustand subscriptions, no event bus
- One file to update — if a label changes, one edit in `studioSchema.ts` reflects everywhere

### Playwright in Electron main process

UI interactions are executed by Playwright's Node.js API (`@playwright/test`) running in the
Electron main process. Playwright connects to the live Electron window via Chrome DevTools
Protocol (CDP) on a fixed debug port.

**Why Playwright:**
- Semantic element resolution — no fragile DOM IDs, no `data-conductor-id` pollution
- Self-healing — if a label changes, the cascade tries alternatives before failing
- Reliable React input handling — Playwright's `.fill()` triggers React synthetic events correctly
- Native Electron support via `chromium.connectOverCDP`

### Element resolution cascade

When executing a step, Playwright tries each strategy in order until an element is found:

1. `page.getByRole(type, { name: label })` — most reliable; ARIA role + accessible name
2. `page.getByLabel(label)` — form elements with associated `<label>`
3. `page.getByPlaceholder(label)` — inputs with placeholder text
4. `page.getByText(label, { exact: false })` — visible text fallback

This pattern is inspired by the playwright-stepper-framework's ElementResolver, implemented
in TypeScript using Playwright's native locator API (no Python subprocess).

### Plan preview UX pattern

The AI generates all steps first. The user sees the complete plan in an `AutomationCard` before
any execution begins. This is the same pattern as Cursor's diff preview: show intent, get
approval, then act.

Two approval modes:
- **Auto** (`[▶ Run All]`): executes all steps with 300ms delay between each
- **Staged** (`[Step by Step]`): user approves each step individually via `[✓ Approve]` / `[→ Skip]`

**Why plan-first:** Trust before execution. Users who can see and cancel a plan are far more
willing to use automation than users who watch actions happen without warning.

### Decision: No page analyzer hook

**Previous approach:** `usePageAnalyzer` hook on every React component — registers elements on
mount, unregisters on unmount. Requires `data-conductor-id` DOM attributes everywhere.

**Rejected because:**
- Invasive — every component needs to be modified
- Brittle — registry can be stale if a component doesn't unregister cleanly
- Unnecessary — Studio is our own app; we know what's in it without scanning at runtime

**New approach:** Static schema in `studioSchema.ts`. The AI knows what's in Studio because
we told it once, not because Studio told the AI at runtime. Playwright finds elements by
semantic label — no DOM attribute required.
