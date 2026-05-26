# Studio AI Chat — Design Specification
> **Builder reference.** Read this before writing any UI code for this feature.
> Contains: UI layout, component inventory, design tokens, interaction states, and user story flow.
> A live HTML mockup also exists at: `studio-chat-mockup/index.html`
>
> **Last updated:** 2026-05-26 — folded in UI/UX Pro Max audit, Linear redesign principles,
> BrightSky StepCard patterns, Zakamurai reductive aesthetic, and 2025/2026 AI chat UX research.

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

## Design Inspiration & Principles

The Conductor draws from three validated sources:

### 1. Linear UI Redesign (layout + chrome reduction)
Linear's 2024 redesign established the core principle for dense developer sidebars:
- **Reduce visual chrome**: limit decorative color to functional signals only. Blue appears only
  for Claude Code status. Amber only for Codex. Green only for success/accent. Nothing else.
- **Three-variable theme**: every visual decision derives from `base / accent / contrast` —
  not 20 one-off color choices.
- **Hierarchy through alignment and density**, not through shadows, gradients, or blur.
- **Inverted-L shell**: fixed top bar + fixed left sidebar + scrollable main = same structure
  the Conductor panel lives inside.

### 2. BrightSky StepCard patterns (state iconography + card hierarchy)
BrightSky's workflow UI established a proven iconography system for card states that the
MatchCard borrows directly:

| Icon | Meaning | Conductor equivalent |
|------|---------|----------------------|
| `○` | Pending / unmatched | No MatchCard yet |
| `◐` | Executing / in-progress | MiniLM running, card loading |
| `✓` | Success / high confidence | MATCHED ≥ 65% |
| `~` | Unsure / low confidence | UNSURE < 65% |
| `✗` | Failed / no match | No match found |
| `–` | Sent / dismissed | After Run clicked |

The BrightSky pattern of **graduated button hierarchy** (primary → secondary → tertiary in one
card) also applies to MatchCard: `[▶ Run]` is primary, `[Not this]` is tertiary (muted text,
no border), never a destructive red.

The **progressive disclosure** pattern from BrightSky StepCards (collapsed by default,
expand to see detail) is adopted for OutputSnippet: show 2 lines by default, expand to 8.

### 3. Zakamurai reductive aesthetic (copy + minimalism)
Zakamurai's interface opens with `"Initializing workspace..."` — terminal boot language used as
UI copy. This philosophy applies to the Conductor's empty states and loading messages:
- Empty state copy: `"Ready."` or `"Workspace loaded. Describe what you want to do."`
- MiniLM loading: `"Loading router..."` (not spinner text like "Please wait")
- phi4-mini offline: `"Explainer offline."` (not a paragraph of explanation)
- Strip every word that doesn't carry information. Short sentences only.

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
│                  │                                     │   Your plan is done.   │
│                  │                                     │   Build starts here.   │
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

## Design Tokens

All tokens as CSS custom properties. Three-variable origin (Linear principle):
`--bg` (base) · `--accent` (accent) · `--fg` (contrast). Everything else derives from these.

```css
/* Backgrounds — no pure black; darkest is midnight navy */
--bg:          #0F172A;   /* panel background, darkest */
--surface:     #1E293B;   /* message bubbles, cards */
--surface2:    #334155;   /* user messages, hover states */

/* Accent — one green, used ONLY for: Run button, success, Pathly brand */
--accent:      #22C55E;

/* Text */
--fg:          #F8FAFC;   /* primary text — 14.5:1 on --bg */
--muted:       #94A3B8;   /* secondary text, timestamps — 4.8:1 on --bg */

/* Borders & separators */
--border:      #475569;   /* all visible borders */
--border-soft: rgba(71,85,105,0.4); /* section dividers, non-structural */

/* Functional colors — each used for ONE meaning only */
--destructive: #EF4444;   /* stop button, error state ONLY */
--claude-blue: #38BDF8;   /* Claude Code CLI color ONLY */
--codex-amber: #F59E0B;   /* Codex CLI color ONLY */
--embed-purple:#C084FC;   /* MiniLM / embedding color ONLY */

/* Zero-depth surface — for separating sections without adding visual weight */
--muted-surface: rgba(255,255,255,0.04);

/* Typography */
--mono: 'JetBrains Mono', 'Geist Mono', monospace;
--sans: 'Inter', system-ui, sans-serif;

/* Animation — all durations reference these tokens */
--t-fast:  150ms;               /* hover states, chip highlights */
--t-card:  220ms;               /* card mount/unmount */
--t-bar:   400ms;               /* confidence bar fill */
--t-pulse: 1400ms;              /* CLI pill running pulse */
--ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);  /* all primary transitions */
--ease-in:       cubic-bezier(0.4, 0, 1, 1);      /* exit animations */
```

### Chrome reduction rules (from Linear principle)
- `--claude-blue` appears ONLY in Claude Code status pill and its dot. Nowhere else.
- `--codex-amber` appears ONLY in Codex status pill. Nowhere else.
- `--embed-purple` appears ONLY in MiniLM pill. Nowhere else.
- `--accent` (#22C55E) is the Run button background, MATCHED border-left, and ✓ Done status. Nowhere else.
- **No gradients anywhere in the panel.** Flat surfaces only.
- **No box-shadow anywhere.** Border + background contrast does all elevation work.
- **No backdrop-filter/blur.** 290px panel has no background to blur against.

---

## Typography Scale

At 290px width, strict size discipline prevents claustrophobia.
Rule from Terminal CLI Monospace pattern: **12 / 11 / 10.5 — three sizes only for mono.**

| Element | Font | Size | Weight | Line-height | Color |
|---|---|---|---|---|---|
| Header title "Conductor" | `--mono` | 13px | 500 | 1.2 | `--fg` |
| CLI pill labels | `--mono` | 10px | 400 | 1.0 | `--claude-blue` / `--codex-amber` |
| Skill chips | `--mono` | 10px | 400 | 1.0 | `--muted` |
| Matched skill name | `--mono` | 14px | 500 | 1.2 | `--fg` |
| Command preview `$ /pathly build` | `--mono` | 11px | 400 | 1.3 | `--fg` |
| phi4-mini explanation text | `--sans` | 11.5px | 400 | 1.55 | `--muted` |
| User messages | `--sans` | 12px | 400 | 1.5 | `--fg` |
| OutputSnippet lines | `--mono` | 10.5px | 400 | 1.3 | `--muted` |
| Timestamps / labels | `--sans` | 10px | 400 | 1.2 | `--muted` |
| Run button | `--mono` | 11px | 500 | 1.0 | `#0F172A` (on accent bg) |
| Section headers (SKILLS, MESSAGES) | `--mono` | 9px | 500 | 1.0 | `--muted` |
| Confidence score "92%" | `--mono` | 10px | 500 | 1.0 | `--fg` |

**Never go below 10px.** `--muted` (#94A3B8) on `--bg` (#0F172A) passes WCAG AA at 10px+.
**phi4-mini explanation uses `--sans`** (Inter), not mono — prose gets sans, commands get mono.
**Do NOT truncate phi4-mini text.** At 290px / 11.5px Inter, ~38 chars/line wraps cleanly.

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

**Spec:**
- `⚡` — replace with Lucide `<Zap size={12} />` SVG icon. Not a Unicode glyph.
- `Conductor` title — `--mono` 13px 500, color `--fg`
- `[Manual]` / `[Auto]` — 10px `--mono`, surface2 bg, border `--border`. Toggle persists in chatStore.
- `[›]` — Lucide `<ChevronRight size={14} />`. `aria-label="Collapse Conductor"`.
- CLI pills: `[◉ Claude Code]` and `[◉ Codex]` — both use the same pill shape.
  - Active idle: dot colored + label muted, border `--border`
  - Running: dot pulses (see Animation section), border matches dot color
  - Offline: opacity 0.35, dot grey
- **Both pills always visible.** The active one is not hidden when the other is running.
- Header has `border-bottom: 1px solid var(--border)` separating it from SkillsPanel.

**Host-specific command format (critical):**
| CLI | Command format | Example |
|-----|---------------|---------|
| Claude Code | `/pathly <skill>` | `/pathly build` |
| Codex | `Use Pathly <skill>` | `Use Pathly build` |

### SkillsPanel
Location: below ConductorHeader, collapsible
```
⬡ SKILLS  14                              ▲
[plan] [po] [storm] [build] [review] [test]
[retro] [explore] [debug] [design] [fix]
[status] [log] [end]
```

**Spec:**
- `⬡` — replace with Lucide `<Hexagon size={10} />`. Not a Unicode glyph.
- Section header: 9px `--mono` 500, color `--muted`, uppercase, letter-spacing 0.05em
- Chip: `--mono` 10px, `--surface` bg, `1px solid var(--border)`, border-radius 4px,
  padding `3px 6px`, min-height 22px (desktop; 44px is mobile floor, not applicable here)
- Chip hover: bg → `--surface2`, transition `var(--t-fast)`
- Chip highlighted (matched skill): border → `--accent`, color → `--accent`
- Clicking a chip bypasses embedding — sends skill directly to MatchCard
- `▲`/`▼` collapse toggle — Lucide `<ChevronUp>` / `<ChevronDown>`, 12px. State in uiStore.
- Panel has `max-height` transition on collapse (not `height` — avoids layout thrashing):
  ```css
  .skillsPanel { overflow: hidden; transition: max-height var(--t-card) var(--ease-out-expo); }
  .skillsPanel--collapsed { max-height: 0; }
  .skillsPanel--open { max-height: 200px; }
  ```

### MessageList — Visual Hierarchy (updated)

**Do NOT use nested cards.** Use indentation + left-gutter + typography role to separate layers.
Inspired by BrightSky's progressive disclosure and Zakamurai's reductive approach.

```
[user bubble]                ← right-aligned, --surface2 bg, border-radius 10px 10px 3px 10px
──────────────────────────── ← 1px --border-soft divider, 8px v-margin
[MatchCard]                  ← full-width, left-accent border (see below)
  [phi4-mini explanation]    ← 8px left-indent, no border, --muted color, --sans font
    [OutputSnippet]          ← 16px left-indent, --bg bg, left-border 2px --border
```

CSS:
```css
.messageGroup {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-soft);
}

.userMessage {
  align-self: flex-end;
  max-width: 85%;
  background: var(--surface2);
  border-radius: 10px 10px 3px 10px;
  padding: 6px 10px;
  font-family: var(--sans);
  font-size: 12px;
  line-height: 1.5;
  color: var(--fg);
}

.phiExplanation {
  margin-left: 8px;
  padding: 5px 0;
  font-family: var(--sans);
  font-size: 11.5px;
  color: var(--muted);
  line-height: 1.55;
  /* No card, no border — it's a continuation */
}

.outputSnippet {
  margin-left: 16px;
  background: var(--bg);
  border-left: 2px solid var(--border);
  padding: 5px 8px;
  font-family: var(--mono);
  font-size: 10.5px;
  color: var(--muted);
  line-height: 1.3;
  border-radius: 0 4px 4px 0;
}
```

**Anti-patterns for MessageList:**
- Do NOT wrap phi4-mini in a surface card — two nested cards at 290px = claustrophobic
- Do NOT make user bubbles full-width — right-aligned 85% max creates clear sender identity
- Do NOT put timestamps on every message — only on the first message of each group

### MatchCard — The Core UI Element

Replaces old "TerminalApproval" concept entirely. Draws from BrightSky StepCard state iconography.

```
┌──────────────────────────────────────────┐  ← border-left: 3px solid (state color)
│  ✓ MATCHED                    92%  ████  │  ← state icon + label + score + bar
│  /pathly build                           │  ← skill name, --mono 14px 500
│  Spawn the builder agent…               │  ← description, --sans 11px --muted
│  ──────────────────────────────          │  ← 1px --border-soft hr
│  $ /pathly build                         │  ← command preview, code block
│  ──────────────────────────────          │  ← 1px --border-soft hr
│  Other possibilities:                    │  ← --sans 10px --muted
│  [/pathly plan 34%]  [/pathly fix 21%]  │  ← alt chips, clickable
│  ──────────────────────────────          │  ← 1px --border-soft hr
│  [▶ Run]                  [Not this]    │
└──────────────────────────────────────────┘
```

**States (from BrightSky icon system):**

| State | Icon | Label | Left-border | Score bar |
|-------|------|-------|-------------|-----------|
| High confidence ≥80% | `✓` | `MATCHED` | `--accent` #22C55E | green |
| Medium confidence 65–79% | `✓` | `MATCHED` | `--accent` #22C55E | green, show alts |
| Low confidence 40–64% | `~` | `UNSURE` | `--codex-amber` #F59E0B | amber, prominent alts |
| No match <40% | `✗` | `NO MATCH` | `--destructive` #EF4444 | — (no bar) |
| Sent (after Run) | `–` | `SENT` | `--border` #475569 | — (opacity 0.4 whole card) |

**CSS:**
```css
.matchCard {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent); /* overridden by state modifier */
  border-radius: 6px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.matchCard--unsure  { border-left-color: var(--codex-amber); }
.matchCard--noMatch { border-left-color: var(--destructive); }
.matchCard--sent    { border-left-color: var(--border); opacity: 0.4; pointer-events: none; }

/* Command preview */
.commandPreview {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--fg);
  background: var(--bg);       /* darker than surface — code block feel */
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 5px 8px;
  user-select: all;            /* one-click select for copy */
}

/* Confidence bar */
.confidenceBar { height: 3px; background: var(--surface2); border-radius: 2px; overflow: hidden; }
.confidenceFill {
  height: 100%;
  border-radius: 2px;
  transition: width var(--t-bar) var(--ease-out-expo);
}
.confidenceFill--high   { background: var(--accent); }
.confidenceFill--unsure { background: var(--codex-amber); }

/* Run button */
.runButton {
  background: var(--accent);
  color: #0F172A;              /* dark text on green — 8.5:1 contrast */
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 500;
  border: none;
  border-radius: 4px;
  padding: 6px 12px;
  cursor: pointer;
  transition: opacity var(--t-fast);
}
.runButton:hover { opacity: 0.88; }
.runButton:disabled { opacity: 0.4; cursor: not-allowed; }

/* Not This — muted text link, NOT a button with border */
.notThisButton {
  background: none;
  border: none;
  color: var(--muted);
  font-family: var(--sans);
  font-size: 11px;
  cursor: pointer;
  padding: 6px 4px;
  transition: color var(--t-fast);
}
.notThisButton:hover { color: var(--fg); }
```

**Feedback capture (AI UX 2025 pattern):**
Add a thumbs up/down row below Run after card is in SENT state:
```
– SENT  · Was this right?  👍  👎
```
Use Lucide `<ThumbsUp size={11} />` / `<ThumbsDown size={11} />`. Store in chatStore for
future skill description improvement. This is the "feedback mechanism" flagged by 2025 AI
chat UX research as essential for trust.

**Anti-patterns for MatchCard:**
- Do NOT animate `background-color` on state change — use `opacity` for Sent transition
- Do NOT make "Not this" red or bordered — it's a correction, not a destructive action
- Do NOT put Run button at top — it must be last, after user reads context (Progressive disclosure)
- Do NOT hide the MatchCard if phi4-mini is still loading — card appears immediately, explanation streams below it

### OutputSnippet
Appears below phi4-mini explanation after Run is clicked.

```
┌─────────────────────────── (16px left-indented, no top border)
│  ◈ Claude Code — review      ● Running  │
│  ┌────────────────────────────────────┐ │
│  │  Spawning reviewer agent…         │ │
│  │  Scouting 8 modified files…       │ │
│  └────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

- `◈` — replace with Lucide `<Diamond size={10} />`. Not Unicode.
- Shows last **2 lines** by default. Click to expand to 8 lines (BrightSky progressive disclosure).
- ANSI codes stripped before display. Wrap in `<pre role="log" aria-live="polite">` for screen readers.
- Status indicators: `● Running` amber pulse · `✓ Done` green · `✗ Error` red
- Status uses Lucide `<Circle>` filled for dot, not Unicode `●`
- When done: AI automatically embed-matches next suggested skill → new MatchCard appears

### EmptyState
Two variants. Copy style from Zakamurai reductive aesthetic: minimal words, terminal tone.

**Variant A — No active feature:**
```
┌──────────────────────────────────────────┐
│                                          │
│   Ready.                                 │
│                                          │
│   Describe what you want to do.          │
│   I'll find the right skill.             │
│                                          │
│   [▸ po]  [▸ plan]  [▸ storm]           │
│                                          │
└──────────────────────────────────────────┘
```

**Variant B — Feature active, no messages yet:**
```
┌──────────────────────────────────────────┐
│                                          │
│   studio-ai-chat · DESIGNING             │
│                                          │
│   What's next?                           │
│                                          │
└──────────────────────────────────────────┘
```

- Quick-start chips (`po`, `plan`, `storm`) bypass embedding — clicking one fires phi4-mini immediately
- Feature name + stage from `buildPathlyContext()` on panel open
- Empty state animates out (`opacity: 0, transform: translateY(-8px)`) on first message send
  using `AnimatePresence` from Framer Motion

### ChatInput
```
┌──────────────────────────────────────┬───┐
│  What do you want to do?             │ ➤ │
│                                      │   │
└──────────────────────────────────────┴───┘
[◈ MiniLM · 22ms]          [● phi4-mini]
```

- Textarea: auto-resize 1–3 rows, `Enter` = send, `Shift+Enter` = newline
- `➤` — Lucide `<Send size={14} />`. `aria-label="Send message"`.
- Send button: `--accent` background, `#0F172A` text (dark on green)
- Stop button: replaces Send when streaming. Lucide `<Square size={14} />`. `--destructive` bg.
- `◈ MiniLM` pill: `--embed-purple` border + text
  - Loading state: shimmer animation (see Animation section)
  - Ready: `◈ MiniLM · ready`
  - Active: `◈ MiniLM · 22ms`
- `● phi4-mini` pill: `--accent` border + text
  - Streaming: pulse animation
  - Offline: `● phi4-mini offline` — opacity 0.35, no pulse

---

## Animation Specification

All animations reference the token variables. All must respect `prefers-reduced-motion`.

### Confidence bar fill
```css
.confidenceFill {
  transition: width var(--t-bar) var(--ease-out-expo);
  /* expo-out: fills fast, lands gently — feels like a measurement snapping to place */
}
@media (prefers-reduced-motion: reduce) {
  .confidenceFill { transition: none; }
}
```

### CLI pill pulse (Running state)
```css
@keyframes pillPulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.4; }
}
.pill--running .dot {
  animation: pillPulse var(--t-pulse) ease-in-out infinite;
  /* 1400ms = "breathing" cadence, not "alerting" */
}
@media (prefers-reduced-motion: reduce) {
  .pill--running .dot { animation: none; opacity: 1; }
}
```

### MiniLM loading shimmer
```css
@keyframes shimmer {
  0%   { background-position: -200px 0; }
  100% { background-position: 200px 0; }
}
.pill--loading {
  background: linear-gradient(
    90deg,
    var(--surface) 25%,
    var(--surface2) 50%,
    var(--surface) 75%
  );
  background-size: 400px;
  animation: shimmer 1200ms ease-in-out infinite;
}
@media (prefers-reduced-motion: reduce) {
  .pill--loading { animation: none; background: var(--surface); }
}
```

### MatchCard mount/unmount (Framer Motion)
```tsx
// Use AnimatePresence wrapping MessageList
<motion.div
  initial={{ opacity: 0, y: 6 }}
  animate={{ opacity: 1, y: 0 }}
  exit={{ opacity: 0, y: -4 }}
  transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
>
  <MatchCard ... />
</motion.div>
```
Exit is shorter than enter (0.14s vs 0.22s) — exit animations should feel 60–70% of enter duration.

### Skill chip hover
```css
.skillChip { transition: background var(--t-fast), border-color var(--t-fast), color var(--t-fast); }
```

### Panel collapse/expand (SkillsPanel)
```css
/* Animate max-height, not height — avoids layout thrashing */
transition: max-height var(--t-card) var(--ease-out-expo);
```

---

## Accessibility

### Required aria attributes
```tsx
// Collapse button
<button aria-label="Collapse Conductor panel" aria-expanded={isOpen}>
  <ChevronRight size={14} />
</button>

// Send button
<button aria-label="Send message" disabled={isStreaming}>
  <Send size={14} />
</button>

// Stop button
<button aria-label="Stop streaming" aria-live="polite">
  <Square size={14} />
</button>

// MatchCard Run
<button aria-label={`Run ${matchedSkill.command}`} disabled={isSent}>
  ▶ Run
</button>

// OutputSnippet — screen readers announce new PTY lines
<pre role="log" aria-live="polite" aria-label="Command output">
  {outputLines.join('\n')}
</pre>

// MatchCard Sent state
<div aria-disabled="true" aria-label="Command sent — card inactive">
```

### Contrast verification
| Pair | Ratio | WCAG |
|------|-------|------|
| `--fg` (#F8FAFC) on `--bg` (#0F172A) | 14.5:1 | AAA |
| `--muted` (#94A3B8) on `--bg` (#0F172A) | 4.8:1 | AA |
| `--muted` (#94A3B8) on `--surface` (#1E293B) | 3.9:1 | AA Large |
| `#0F172A` on `--accent` (#22C55E) — Run button | 8.5:1 | AAA |
| `--accent` (#22C55E) on `--bg` (#0F172A) | 5.2:1 | AA |
| `--codex-amber` (#F59E0B) on `--surface` (#1E293B) | 3.1:1 | AA Large |
| `--claude-blue` (#38BDF8) on `--surface` (#1E293B) | 4.9:1 | AA |

**Note:** `--codex-amber` on surface only passes AA Large (18px+ or 14px bold). Keep Codex pill
labels at `--fg` color and use amber only for the dot + border, not the label text.

### Icon replacement (UX engine pre-delivery requirement)
Replace all Unicode/emoji structural icons with Lucide SVGs:

| Current | Replace with | Size |
|---------|-------------|------|
| `⚡` Conductor | `<Zap />` | 12px |
| `⬡` Skills | `<Hexagon />` | 10px |
| `◈` MiniLM | `<Diamond />` | 10px |
| `●` dot | `<Circle fill />` | 8px |
| `➤` send | `<Send />` | 14px |
| `▶` Run | keep as text (it's a label, not an icon) | — |
| `›` collapse | `<ChevronRight />` | 14px |
| `▲`/`▼` skills | `<ChevronUp />` / `<ChevronDown />` | 12px |

---

## Confidence Thresholds

| Score    | State      | Card color  | Icon | Label      | Behavior               |
|----------|------------|-------------|------|------------|------------------------|
| ≥ 80%    | High       | Green       | `✓`  | MATCHED    | Auto-suggest Run       |
| 65–79%   | Medium     | Green       | `✓`  | MATCHED    | Show alts              |
| 40–64%   | Low        | Amber       | `~`  | UNSURE     | Prominent alts, no Run emphasis |
| < 40%    | No match   | Red         | `✗`  | NO MATCH   | "Try rephrasing or pick from Skills" |

Auto-approve (if enabled) is **disabled for scores < 65%** regardless of user setting.
This is enforced in both UI (hide toggle below threshold) and chatStore action.

---

## Technology Stack — Final Decisions

| Layer | Choice | Reason |
|---|---|---|
| Styles | **CSS Modules** + tiny utility helpers | Best fit for named states + design token system. Utility layer only for flex/gap. |
| Mount animation | **Framer Motion** (AnimatePresence only) | For MatchCard/EmptyState enter/exit. No other uses. |
| Icons | **Lucide React** | Single consistent SVG set. Replace all Unicode structural glyphs. |
| Embedding | **@xenova/transformers pinned to 2.17.x** | Later versions changed pipeline API |
| State | **Zustand** | Flat store, no selectors overhead |
| Fonts | **JetBrains Mono + Inter** | Confirmed by Terminal CLI Monospace typography pattern |
| No Tailwind | — | Fights the token system; CSS Modules + custom properties is cleaner here |
| No glassmorphism | — | No background to blur against at 290px; GPU overdraw for zero UX gain |
| No pure black | — | #0F172A midnight navy is softer and correct (2025 dark mode best practice) |

---

## User Story Flow (5 steps)

```
Step 1  Studio opens
        → ChatPanel visible (290px), SkillsPanel expanded showing 14 chips
        → ConductorHeader shows Claude Code (active) + Codex (active)
        → EmptyState Variant A: "Ready. Describe what you want to do."

Step 2  User types intent
        → "my plan is ready, i want to start building"
        → MiniLM pill shows shimmer → "◈ MiniLM · 22ms"
        → MatchCard mounts with motion.div (y: 6→0, opacity: 0→1, 220ms expo-out)
        → Confidence bar fills from 0 to 92% (400ms expo-out)
        → Matched skill chip highlights in SkillsPanel (border + text → --accent)
        → phi4-mini starts streaming explanation below MatchCard (async, non-blocking)

Step 3  User reviews MatchCard
        → ✓ MATCHED · /pathly build · 92% (green left-border, green bar)
        → Description: "Spawn the builder agent…" (--sans 11px --muted)
        → Command preview: $ /pathly build (code block, --bg, user-select:all)
        → Alternatives: [/pathly plan 34%] [/pathly fix 21%]
        → phi4-mini explanation appears below card (8px indent, --muted, no card)
        → User clicks ▶ Run

Step 4  Command executes
        → Renderer looks up terminalStore.tabs for tab with kind === 'claude'
        → If no claude tab: renderer calls handleLaunch('claude') → addTab()
        → Gets UUID tabId from that tab
        → Generates host-correct command (Claude Code: "/pathly build", Codex: "Use Pathly build")
        → IPC: chat:write-terminal({ command, tabId })
        → MatchCard transitions to SENT state: opacity → 0.4, pointer-events: none
        → OutputSnippet mounts (16px indent, --bg, left-border 2px --border)
        → Claude Code pill pulses (--t-pulse 1400ms ease-in-out)

Step 5  Command completes
        → OutputSnippet status → ✓ Done (green)
        → Feedback row appears: "Was this right?  👍  👎"
        → AI reads last N lines of PTY output via embed-match
        → New MatchCard mounts for next suggested skill
```

---

## Embedding Implementation Notes (for builder)

### Library
```typescript
import { pipeline } from '@xenova/transformers'  // pin to 2.17.x
const embedder = await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2')
```

### Skills vector DB
```typescript
interface Skill {
  name: string          // "build"
  command: string       // "/pathly build"
  description: string   // specific 1-2 sentence description including when to use
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
    .slice(0, 3)
}
```

### Cold-start
- MiniLM pill shows shimmer on first launch: `"◈ Loading router..."`
- Pre-embed all skills at startup (not on first message)
- After loading: pill shows `"◈ MiniLM · ready"`
- Copy style: Zakamurai terminal-boot language. Short, functional.

---

## phi4-mini System Prompt

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
interface MatchResult {
  skill: Skill
  score: number
  command: string
}

interface FeedbackEntry {
  skillName: string
  userIntent: string
  wasCorrect: boolean  // from thumbs up/down
  timestamp: number
}

interface ChatStore {
  messages: Message[]
  isStreaming: boolean

  currentMatch: MatchResult | null
  altMatches: MatchResult[]
  isEmbedding: boolean
  embedReady: boolean
  pendingCommand: string | null
  autoApprove: boolean

  feedback: FeedbackEntry[]          // new — for match quality tracking

  setMatch: (match: MatchResult, alts: MatchResult[]) => void
  clearMatch: () => void
  setEmbedReady: (v: boolean) => void
  recordFeedback: (entry: FeedbackEntry) => void  // new
}
```

---

## File Map

| File | Conv | Action |
|------|------|--------|
| `src/pathly_orchestrator/http_server.py` | 1 | Add POST /chat SSE endpoint |
| `src/pathly_orchestrator/chat_agent.py` | 1 | phi4-mini explainer, NOT router |
| `src/pathly_orchestrator/chat_tools.py` | 1 | get_fsm_state, read_plan_summary |
| `pyproject.toml` | 1 | Add ollama>=0.3 |
| `studio/src/renderer/src/store/chatStore.ts` | 2 | Messages + streaming + feedback state |
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
| `studio/src/renderer/src/data/studioSchema.ts` | 6 | Static Studio UI element definitions |
| `studio/src/renderer/src/lib/pathlyContext.ts` | 6 | MODIFY — inject studioSchema into AI context |
| `studio/src/main/automation/playwrightExecutor.ts` | 7 | Playwright element resolver + executor |
| `studio/src/main/ipc/automation.ts` | 7 | IPC handler for step execution |
| `studio/package.json` | 7 | MODIFY — add @playwright/test |
| `studio/src/renderer/src/store/automationStore.ts` | 8 | Step queue state |
| `studio/src/renderer/src/components/ChatPanel/StepQueue.tsx` | 8 | Staged/auto step UI |
| `studio/src/renderer/src/components/ChatPanel/AutomationCard.tsx` | 8 | Plan summary card |
| `studio/src/renderer/src/data/models.ts` | 9 | WebLLM model definitions |
| `studio/src/renderer/src/lib/webLLMEngine.ts` | 9 | WebLLM engine wrapper |
| `studio/src/renderer/src/store/modelStore.ts` | 9 | Model selection + cache state |
| `studio/src/renderer/src/components/ChatPanel/ModelSelector.tsx` | 9 | Model picker UI |

---

### AutomationCard
Appears in MessageList after AI generates an action plan. Shows intent + step count + mode buttons.

```
┌──────────────────────────────────────────┐  ← border-left: 3px solid --embed-purple
│  ⚡ Action Plan                    5 steps│
│  Create checkout flow with HTTP + cond…  │  ← intent, --sans 11px --muted
│  ──────────────────────────────────────  │
│  [▶ Run All]          [Step by Step]     │
└──────────────────────────────────────────┘
```

- Border-left: `--embed-purple` (#C084FC) — distinct from MatchCard (green) and UNSURE (amber)
- `[▶ Run All]`: accent bg, same style as MatchCard Run button
- `[Step by Step]`: surface2 bg, --fg text, --border border
- `[▶ Run All]` disabled when no page context: tooltip "No UI elements registered"

### StepQueue
Renders below AutomationCard when staged or auto mode is active.

**Staged mode:**
```
┌──────────────────────────────────────────┐
│  Step 1 of 5                             │
│  ┌──────────────────────────────────┐    │
│  │ ▶ click "New Flow"               │    │  ← current step, --surface2 bg
│  │ Creates a new flow in the editor │    │
│  │ [✓ Approve]        [→ Skip]      │    │
│  └──────────────────────────────────┘    │
│  ┌──────────────────────────────────┐    │
│  │ ✓ fill "Checkout Flow"           │    │  ← done step, opacity 0.5
│  └──────────────────────────────────┘    │
│  ┌──────────────────────────────────┐    │
│  │ ○ click "Add Step"               │    │  ← pending step, --surface bg
│  └──────────────────────────────────┘    │
└──────────────────────────────────────────┘
```

**Auto mode:**
```
┌──────────────────────────────────────────┐
│  Running — 2 / 5 steps                   │
│  ████████░░░░░░░░░░░░░░░░░░░░░░░░  40%   │
│                             [■ Stop]     │
└──────────────────────────────────────────┘
```

- Step icons: `▶` pending (muted), `✓` done (green), `→` skipped (muted), `✗` error (red)
- [✓ Approve]: accent bg, same as Run button
- [→ Skip]: muted text link, no border — same pattern as "Not this" in MatchCard
- [■ Stop]: destructive bg, --fg text
- Progress bar: same token as confidence bar (`--t-bar` transition, `--ease-out-expo`)

### ModelSelector
Replaces the `phi4-mini` pill in ConductorHeader. Opens as an inline dropdown panel.

**Trigger (in ConductorHeader):**
```
[Phi-4 Mini  ▼]  [ℹ]
```
- Shows selected model short name + chevron
- `ℹ` button toggles model info tooltip
- Matches CLI pill style (--mono 10px, --surface bg, --border)

**Dropdown panel (matches user screenshots):**
```
┌──────────────────────────────────────────────┐
│  AI Models                               [×]  │
│                                              │
│  ╔══════════════════════════════════════╗    │
│  ║ ^ Qwen2.5 Coder 7B              [Cache]║   │  ← collapsed header
│  ║   Qwen2.5-Coder-7B-Instruct...        ║   │
│  ║   Best code quality…                  ║   │
│  ║   Complex refactors, multi-file edits ║   │
│  ║  ┌───────────────────────────────┐   ║   │
│  ║  │ SYSTEM  High-end, WebGPU      │   ║   │
│  ║  │ STORAGE Largest footprint     │   ║   │
│  ║  │ SPEED   Slower, strongest     │   ║   │
│  ║  └───────────────────────────────┘   ║   │
│  ╚══════════════════════════════════════╝    │
│                                              │
│  ╔══════════════════════════════════════╗    │
│  ║ ^ Phi-4 Mini  [Recommended] [Cached] ║   │  ← selected + expanded
│  ║  ...                            [▓▓▓]║   │  ← download progress if active
│  ╚══════════════════════════════════════╝    │
└──────────────────────────────────────────────┘
```

- Each model card: `--surface` bg, `1px solid --border`, border-radius 6px
- Selected card: `border-color: --accent`, slightly elevated bg (`--surface2`)
- Badges:
  - `Recommended`: teal (#2DD4BF) bg, dark text — used only on the recommended model
  - `Cached`: `--accent` (#22C55E) bg, dark text
  - `Selected`: `--claude-blue` bg, dark text
- `Cache` toggle: matches existing Studio toggle pattern
- Download progress: `--accent` fill, same progress bar component as confidence bar
- Spec table rows (SYSTEM / STORAGE / SPEED): `--mono` 10px, `--muted` labels, `--fg` values

---

## UI Automation — Interaction Model

### How the AI knows what to click

The AI receives a static schema of Studio's key UI elements with every message. This schema is a typed constant in `studioSchema.ts` — not a runtime registry, not DOM scanning.

The AI must only reference labels from this schema when generating steps. If a user requests something that requires an element not in the schema, the AI says so instead of inventing a label.

```
studioSchema.ts → getStudioSchema() → injected into pathlyContext → POST /chat body
→ AI system prompt: "## Studio UI Elements: [New Flow (button, FlowEditor)], ..."
→ AI generates: { "action": "click", "label": "New Flow", "screen": "FlowEditor" }
```

### How steps are executed

Playwright runs in the Electron main process. It connects to the app window via CDP (remote debugging). Element resolution uses a semantic cascade — no brittle IDs, no DOM attribute pollution:

1. `getByRole(type, { name: label })` — most reliable
2. `getByLabel(label)` — form elements
3. `getByPlaceholder(label)` — inputs with placeholder text
4. `getByText(label, { exact: false })` — visible text fallback

This is the same pattern as playwright-stepper-framework's ElementResolver, implemented in TypeScript using Playwright's native locator API.

### Automation modes

| Mode | Trigger | Behavior |
|------|---------|----------|
| Staged | `[Step by Step]` | Shows each step card, waits for user `[✓ Approve]` or `[→ Skip]` |
| Auto | `[▶ Run All]` | Executes all steps with 300ms delay between each, shows progress bar |

### Automation vs Skill Routing

The same chat input triggers different behavior based on intent:

| User types | Detected as | Response |
|---|---|---|
| "I want to build" | skill routing | MatchCard + phi4-mini explanation |
| "create a checkout flow" | automation | AutomationCard + StepQueue |

Detection heuristic: presence of creation/modification verbs + Studio nouns ("flow", "step", "create", "add"). When ambiguous, show MatchCard (safer default).

---

## What NOT to Build (Out of Scope)

- API key inputs — CLIs already authenticated in terminal
- Pathly CLI as routing target — skills ARE the commands
- Web search / internet access — offline only
- Multi-turn memory beyond localStorage — no database
- Resizable panel — fixed 290px for v1
- Chat export — v1 only
- "Open a terminal first" error — auto-spawn, never block
- Looking up PTY by string name in main — use UUID tabId from renderer
- Writing `/pathly <skill>` to Codex — use `"Use Pathly <skill>"`
- Calling `/next_action` for read context — use read-only `/status` GET instead
- Glassmorphism / backdrop-filter — no background to blur, GPU overdraw
- Tailwind — fights the CSS custom property token system
- Gradient backgrounds — flat surfaces only, per Linear chrome-reduction principle
- Runtime DOM scanning for automation context — use the static `studioSchema.ts` constant, not DOM queries
- `usePageAnalyzer` hooks on Studio components — the static schema replaces runtime registration entirely
- `data-conductor-id` attributes on DOM nodes — Playwright resolves elements by semantic label, not injected IDs
- `webContents.executeJavaScript` for automation — Playwright CDP connection is the execution path
- `window.__uiExecutor` or renderer-side action dispatch — execution happens in main process via Playwright
- Drag-and-drop automation — click/fill/select only for v1
- Generating automation steps without studioSchema — AI must see the schema before generating actions
- Ollama as required dependency — it is optional/legacy; WebLLM is the default from Conv 9
- Removing the Python backend — keep for teams that prefer Ollama
