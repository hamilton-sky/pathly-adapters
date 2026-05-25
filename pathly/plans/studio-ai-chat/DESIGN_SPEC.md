# Studio AI Chat — Design Specification
> **Builder reference.** Read this before writing any UI code for this feature.
> Contains: UI layout, component inventory, design tokens, interaction states, and user story flow.
> A live HTML mockup also exists at: `studio-chat-mockup/index.html`

---

## Concept: The Conductor

The chat panel is not a general assistant. It is a **Conductor** — it interprets plain-English
intent, finds the matching Pathly skill via embedding similarity, explains the match, and
writes the command to the right terminal tab with user approval.

The metaphor: an orchestra conductor doesn't play any instrument. It interprets the composer's
intent and directs the ensemble. Same here — phi4-mini doesn't write code, it routes.

### Core design principle: terminal-optional

The user never needs to open or manage a terminal tab. The Conductor is the **only interface
they need to touch**. When Run is clicked, if no terminal tab is open, one is spawned
automatically. The terminal is an execution surface — not a prerequisite.

```
Open Studio → open Conductor → type intent → click Run
                                              ↓
                              terminal opens automatically if needed
                              command runs, output streams back to chat
```

---

## Two-Model Architecture

```
User types intent (plain English)
         │
         ▼
┌─────────────────────────────────┐
│  MiniLM (transformers.js)       │  ← runs in Electron renderer
│  all-MiniLM-L6-v2 (~22MB)       │  ← no server, no API, ~22ms
│  Cosine similarity vs skills    │  ← returns top-k matches + scores
└─────────────────────────────────┘
         │
         │  top match + score + alternatives
         ▼
┌─────────────────────────────────┐
│  Match Card renders instantly   │  ← no waiting for LLM
│  green (≥65%) or amber (<65%)   │
└─────────────────────────────────┘
         │
         │  (async, after match card)
         ▼
┌─────────────────────────────────┐
│  phi4-mini (Ollama :11434)      │  ← explains WHY this skill fits
│  System prompt: "You are an     │  ← 2-3 sentence max explanation
│  explainer, not a router"       │  ← does NOT decide the skill
└─────────────────────────────────┘
         │
         │  user clicks ▶ Run
         ▼
┌─────────────────────────────────┐
│  IPC: chat:write-terminal       │  ← Electron main process
│  node-pty.write(cmd + '\n')     │  ← writes to named terminal tab
│  target: Claude Code OR Codex   │  ← based on active tab
└─────────────────────────────────┘
```

---

## Full UI Layout (ASCII)

Matches the live mockup at `studio-chat-mockup/index.html` (AFTER scene).

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  ● ● ● ≡  ● studio-ai-chat ▾   Canvas  Plan  ⚡ Monitor   · syncing  + >_ ⚡ Publish │
│                                                                    ↑             │
│                                              toggle Conductor ─────┘             │
├──────────────────┬─────────────────────────────────────┬────────────────────────┤
│ WORKSPACE LIBRARY│  studio-ai-chat                     │ ⚡ Conductor  [Manual][›]│
│──────────────────│  ● Health  ● FSM  ● State  Events   │  ● Claude  ● Codex     │
│ Filter...        │─────────────────────────────────────├────────────────────────┤
│                  │  FSM progress bar                   │ ⬡ SKILLS  14        ▲  │
│ WORKSPACE        │  ●──●──●──●──●──●──●──◌            │ [plan] [po]  [storm]   │
│ ▸ Plan [...]     │  STORM PLANN DESIG BUILD REVIE RETRO│ [build][review][test]  │
│ ▸ security-hard  │─────────────────────────────────────│ [retro][explore][debug]│
│ ▾ studio-ai-chat │  EVENT LOG                          │ [design][fix][status]  │
│   ▸ Debugs       │  16:40:56 TRANSITION PLAN→DESIGNING │ [log]  [end]           │
│   ▸ Explorations │  ——:——:—— FILE_CREATED  DESIGN.md   ├────────────────────────┤
│   ▸ Lessons      │  ——:——:—— STAGE_COMPLETE DESIGN→BLD │ MESSAGES (scrollable)  │
│                  │                                     │                        │
│ ⚡ Monitor        │                                     │ ┌──────────────────┐   │
│ ○ Settings       │                                     │ │              You │   │
│                  │                                     │ │  plan is ready,  │   │
│                  │                                     │ │  time to build ──►   │
│                  │                                     │ └──────────────────┘   │
│                  │                                     │                        │
│                  │                                     │ ┌─ MATCH CARD ───────┐ │
│                  │                                     │ │ ✓ MATCHED    92%██ │ │
│                  │                                     │ │ /pathly build      │ │
│                  │                                     │ │ Spawn builder...   │ │
│                  │                                     │ │ $ /pathly build    │ │
│                  │                                     │ │ [plan 34%][fix 18%]│ │
│                  │                                     │ │ [▶ Run]  [Not this]│ │
│                  │                                     │ └────────────────────┘ │
│                  │                                     │                        │
│                  │                                     │ ┌─ phi4-mini ────────┐ │
│                  │                                     │ │ Your plan is done. │ │
│                  │                                     │ │ Build starts here. │ │
│                  │                                     │ └────────────────────┘ │
│                  │                                     │                        │
│                  │                                     │ ┌─ OUTPUT SNIPPET ───┐ │
│                  │                                     │ │ ◈ Claude  ●Running │ │
│                  │                                     │ │ Scouting 6 files…  │ │
│                  │                                     │ └────────────────────┘ │
│                  │                                     ├────────────────────────┤
│                  │                                     │[What do you want...?] ➤│
│                  │                                     │[◈ MiniLM·22ms][●phi4]  │
├──────────────────┴─────────────────────────────────────┴────────────────────────┤
│  + Shell  ● A CLaude  ● Codex                                      ⊡  ⤢  ×    │
│  ── Claude Code · studio-ai-chat ──────────────────────────────────────────── │
│  $ /pathly build                                                               │
│  • Phase 1: Creating chat_agent.py                                             │
│  ✓ Phase 1 complete · 3.2s                                                     │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Key layout rules
- **Terminal is at the BOTTOM** — spans the full width below all three columns
- **Left sidebar** — full-height workspace tree (WORKSPACE / LIBRARY tabs, project list, Monitor, Settings)
- **Main area** — shows Canvas / FSM progress / Event log (not the terminal)
- **Conductor** — right sidebar, same height as main content area (does NOT extend into terminal)
- **⚡ button in top bar** — toggles Conductor open/closed (sits between >_ and Publish)
- **Terminal tabs** (+ Shell, ● A CLaude, ● Codex) — live in the bottom terminal bar, not top bar

### Panel dimensions
| Element           | Value                              |
|-------------------|------------------------------------|
| Conductor width   | 290px expanded, 32px collapsed     |
| Skills panel      | ~80px tall, collapsible            |
| Message list      | flex: 1, overflow-y: auto          |
| Input area        | ~72px, fixed at bottom of panel    |
| Terminal height   | ~180px, fixed at viewport bottom   |
| Left sidebar      | 160px fixed                        |
| Studio height     | fills viewport                     |

---

## Component Inventory

### ConductorHeader
Location: top of ChatPanel, fixed
```
┌─────────────────────────────────────────┐
│  ⚡ Conductor            [Manual]  [›]  │
│  [◉ Claude Code]  [◉ Codex]            │
└─────────────────────────────────────────┘
```
- `⚡ Conductor` title — JetBrains Mono, accent #22C55E
- `[Manual]` / `[Auto]` toggle — persisted in chatStore
- `[›]` collapse button — toggles uiStore.chatOpen
- CLI status pills: `[◉ Claude Code]` blue, `[◉ Codex]` amber
  - Active: colored dot + colored border
  - Idle: grey dot, 0.45 opacity
  - Pulsing animation when command is running

### SkillsPanel
Location: below ConductorHeader, collapsible
```
⬡ SKILLS  14                              ▲
[plan] [po] [storm] [build] [review] [test]
[retro] [explore] [debug] [design] [fix]
[status] [log] [end]
```
- Chip: 10px JetBrains Mono, surface bg, border #475569
- Highlighted chip: accent border + accent text (matched skill)
- Clicking a chip bypasses embedding — sends that skill directly to MatchCard
- Collapse: `▲`/`▼` toggle, stores state in uiStore

### MessageList
- User messages: right-aligned, surface2 bg, border-bottom-right-radius: 3px
- AI messages: left-aligned, surface bg, border-bottom-left-radius: 3px
- Font: Inter 12.5px, line-height 1.55
- Auto-scroll to bottom on new message

### MatchCard
The core UI element. Replaces old "TerminalApproval" concept entirely.
```
┌──────────────────────────────────────────┐
│  ✓ MATCHED                    92%  ████  │  ← green when ≥65%
│  /pathly build                           │  ← skill name, bold 15px mono
│  Spawn the builder agent…               │  ← description, 11.5px muted
│  ──────────────────────────────          │
│  $ /pathly build                         │  ← command preview, code block
│  ──────────────────────────────          │
│  Other possibilities:                    │
│  [/pathly plan 34%]  [/pathly fix 21%]  │  ← alt chips, clickable
│  ──────────────────────────────          │
│  [▶ Run]                  [Not this]    │
└──────────────────────────────────────────┘
```
States:
- `✓ MATCHED` green, border-left #22C55E — confidence ≥65%
- `~ UNSURE` amber, border-left #F59E0B — confidence <65%
- `✓ Sent` dimmed, opacity 0.4 — after Run clicked

### OutputSnippet
Appears below MatchCard after Run is clicked:
```
┌──────────────────────────────────────────┐
│  ◈ Claude Code — review      ● Running  │
│  ┌────────────────────────────────────┐ │
│  │  Spawning reviewer agent…         │ │
│  │  Scouting 8 modified files…       │ │
│  │  > Checking chatStore.ts…         │ │
│  └────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```
- Shows last 4–5 lines of PTY output
- Status: `● Running` amber, `✓ Done` green, `✗ Error` red
- When done: AI automatically embed-matches next suggested action

### EmptyState
Shown in MessageList when `messages.length === 0` (no active flow OR fresh session).
Detects via FSM: if `fsmStage === "unknown"` or no feature open → show new-feature prompt.
If a feature IS active but no messages yet → show in-flow prompt.

```
┌──────────────────────────────────────────┐
│                                          │
│   ⚡ What do you want to build?          │  ← no active feature
│                                          │
│   Describe it and I'll route you to      │
│   the right starting point.             │
│                                          │
│   [▸ po]  [▸ plan]  [▸ storm]           │  ← quick-start chips
│                                          │
└──────────────────────────────────────────┘

   — OR, when a feature IS active —

┌──────────────────────────────────────────┐
│                                          │
│   ⚡ studio-ai-chat · DESIGNING          │  ← feature + stage
│                                          │
│   Describe what you want to do next.     │
│   I'll find the right skill.             │
│                                          │
└──────────────────────────────────────────┘
```

- Quick-start chips (`po`, `plan`, `storm`) bypass embedding — clicking one immediately sets `currentMatch` to that skill and fires phi4-mini explanation
- Feature name + stage pulled from `buildPathlyContext()` on panel open
- Empty state disappears as soon as the first message is sent

### ChatInput
```
┌──────────────────────────────────────┬───┐
│  What do you want to do?             │ ➤ │
│                                      │   │
└──────────────────────────────────────┴───┘
[◈ MiniLM · 22ms]          [● phi4-mini]
```
- Textarea: auto-resize 1–3 rows, Enter = send, Shift+Enter = newline
- Send button: accent #22C55E background
- Stop button: replaces Send when streaming (destructive red)
- `◈ MiniLM` pill: purple #C084FC — router status
- `phi4-mini` pill: accent green — explainer status

---

## Design Tokens

```css
/* All tokens as CSS custom properties */
--bg:          #0F172A;   /* panel background, darkest */
--surface:     #1E293B;   /* message bubbles, cards */
--surface2:    #334155;   /* user messages, hover states */
--accent:      #22C55E;   /* primary CTA, Pathly, success */
--fg:          #F8FAFC;   /* primary text */
--muted:       #94A3B8;   /* secondary text, timestamps */
--border:      #475569;   /* all borders */
--destructive: #EF4444;   /* stop button, error state */
--claude-blue: #38BDF8;   /* Claude Code CLI color */
--codex-amber: #F59E0B;   /* Codex CLI color */
--embed-purple:#C084FC;   /* MiniLM / embedding color */

/* Typography */
--mono: 'JetBrains Mono', monospace;   /* commands, skill names, chips */
--sans: 'Inter', sans-serif;            /* message text, labels */

/* Animation */
--transition-fast: 150ms ease-out;
--transition-panel: 200ms ease-out;    /* collapse/expand */
```

---

## Confidence Thresholds

| Score    | State      | Card color  | Label      | Behavior               |
|----------|------------|-------------|------------|------------------------|
| ≥ 80%    | High       | Green       | ✓ MATCHED  | Auto-suggest Run       |
| 65–79%   | Medium     | Green       | ✓ MATCHED  | Show alts              |
| 40–64%   | Low        | Amber       | ~ UNSURE   | Prominent alts, no Run label emphasis |
| < 40%    | No match   | —           | —          | Show "I couldn't match this — try rephrasing or pick from Skills" |

---

## User Story Flow (5 steps)

```
Step 1  Studio opens
        → ChatPanel visible (300px), SkillsPanel expanded showing 14 chips
        → ConductorHeader shows Claude Code (active) + Codex (active)
        → Empty state: "Describe what you want to do. I'll find the right skill."

Step 2  User types intent
        → "my plan is ready, i want to start building"
        → MiniLM embeds intent, cosine-matches against skills.json
        → MatchCard appears in ~22ms
        → Matched skill chip highlights in SkillsPanel
        → phi4-mini starts streaming explanation (async, non-blocking)

Step 3  User reviews MatchCard
        → /pathly build at 92% (green)
        → Description: "Spawn the builder agent…"
        → Command preview: $ /pathly build
        → Alternatives: [/pathly plan 34%] [/pathly fix 21%]
        → phi4-mini explanation appears below card
        → User clicks ▶ Run

Step 4  Command executes — no terminal needed upfront
        → IPC: chat:write-terminal('/pathly build', 'claude-code')
        → If no Claude Code tab open: Electron main auto-spawns one (same as clicking +)
        → Waits for PTY ready, then writes command
        → IPC returns { ok: true, spawned: true }
        → ChatPanel shows hint: "Opened a Claude Code tab to run this command."
        → MatchCard dims to "✓ Sent"
        → OutputSnippet appears with live PTY lines
        → Claude Code pill pulses (active)

Step 5  Command completes
        → OutputSnippet status → ✓ Done
        → AI reads last N lines of PTY output
        → Embeds output context, finds next suggested skill
        → New MatchCard appears automatically
```

---

## Embedding Implementation Notes (for builder)

### Library
```typescript
// In renderer — no server needed
import { pipeline } from '@xenova/transformers'

const embedder = await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2')
```

### Skills vector DB (pre-computed at startup)
```typescript
// skills.json shape — each skill needs name + description
interface Skill {
  name: string          // "build"
  command: string       // "/pathly build"
  description: string   // "Spawn the builder agent — reads IMPLEMENTATION_PLAN.md..."
  vector?: number[]     // pre-computed at startup, stored in memory
}
```

### Matching function
```typescript
async function matchIntent(input: string, skills: Skill[]): Promise<MatchResult[]> {
  const inputVec = await embed(input)
  return skills
    .map(skill => ({ skill, score: cosineSim(inputVec, skill.vector!) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 3)  // top 3
}
```

### Cold-start loading state
- Show "◈ Loading model…" in the MiniLM pill on first launch
- Pre-embed all skills at startup (not on first message)
- After loading: pill shows "◈ MiniLM · ready"

---

## phi4-mini System Prompt (explainer role)

```
You are the Pathly Conductor explainer.

The routing system has already matched the user's intent to a Pathly skill using embedding
similarity. Your ONLY job is to explain in 2-3 sentences:
1. What the matched skill does
2. Why it fits what the user asked for
3. What will happen when they click Run

DO NOT suggest a different skill. DO NOT write code.
DO NOT mention "embedding" or "similarity score".
Be concise and direct. Use the current FSM stage and feature name in your explanation.

Current context:
- FSM stage: {fsm_stage}
- Feature: {feature_name}
- Matched skill: {skill_name}
- Skill description: {skill_description}
```

---

## Zustand Store Shape

```typescript
// chatStore.ts additions for Conductor
interface MatchResult {
  skill: Skill
  score: number       // 0–1
  command: string     // "/pathly build"
}

interface ChatStore {
  // existing
  messages: Message[]
  isStreaming: boolean

  // new for Conductor
  currentMatch: MatchResult | null
  altMatches: MatchResult[]
  isEmbedding: boolean           // MiniLM running
  embedReady: boolean            // model loaded
  pendingCommand: string | null  // after Run clicked, before IPC confirms
  autoApprove: boolean           // persisted

  // actions
  setMatch: (match: MatchResult, alts: MatchResult[]) => void
  clearMatch: () => void
  setEmbedReady: (v: boolean) => void
}
```

---

## File Map (all files this feature touches)

| File | Conv | Action |
|------|------|--------|
| `src/pathly_orchestrator/http_server.py` | 1 | Add POST /chat SSE endpoint |
| `src/pathly_orchestrator/chat_agent.py` | 1 | phi4-mini explainer, NOT router |
| `src/pathly_orchestrator/chat_tools.py` | 1 | get_fsm_state, read_plan_summary |
| `pyproject.toml` | 1 | Add ollama>=0.3 |
| `studio/src/renderer/src/store/chatStore.ts` | 2 | Messages + streaming state |
| `studio/src/renderer/src/store/uiStore.ts` | 2 | chatOpen, skillsPanelOpen |
| `studio/src/renderer/src/components/ChatPanel/index.tsx` | 2 | Panel container, collapse |
| `studio/src/renderer/src/components/ChatPanel/ConductorHeader.tsx` | 2 | Header + CLI pills |
| `studio/src/renderer/src/components/ChatPanel/SkillsPanel.tsx` | 2 | Chips grid |
| `studio/src/renderer/src/components/ChatPanel/MessageList.tsx` | 2 | Scrollable messages |
| `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx` | 2 | Input + model pills |
| `studio/src/renderer/src/components/ChatPanel/MatchCard.tsx` | 3 | Match result card |
| `studio/src/renderer/src/components/ChatPanel/OutputSnippet.tsx` | 3 | PTY output reader |
| `studio/src/renderer/src/components/ChatPanel/ChatPanel.module.css` | 2 | All chat styles |
| `studio/src/main/ipc/chat.ts` | 3 | IPC terminal write |
| `studio/src/main/index.ts` | 3 | Register IPC handler |
| `studio/src/renderer/src/lib/embedRouter.ts` | 5 | MiniLM wrapper + matchIntent() |
| `studio/src/renderer/src/lib/skillsManifest.ts` | 5 | Typed skills.json loader |
| `studio/src/renderer/src/data/skills.json` | 5 | Skills name+command+description |
| `studio/src/renderer/src/lib/pathlyContext.ts` | 4 | FSM + screen context builder |
| `studio/src/renderer/src/App.tsx` | 2 | Add ChatPanel to layout |

---

## What NOT to build (out of scope)

- ❌ API key inputs for Claude or OpenAI — both CLIs are already authenticated in terminal
- ❌ Pathly CLI as a routing target — skills ARE the commands, executed via Claude Code or Codex terminals
- ❌ Web search / internet access — everything runs offline
- ❌ Multi-turn memory beyond localStorage — no database
- ❌ Resizable panel — fixed 300px for v1
- ❌ Chat export — v1 only
- ❌ "Open a terminal first" error message — auto-spawn instead, never block the user
