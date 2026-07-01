---
name: UI Direction
---
# Comms Board — UI Direction (canonical)

**Status:** Agreed design · 2026-06-11
**Supersedes:** SPEC.md §7 (single CommsPanel), §16 (three-panel command center),
§19 (flexible panel layout). Where this file and SPEC.md disagree, **this file wins.**
SPEC.md §16/§19 are kept for design history only.

---

## 1. Why this exists

SPEC.md described the Studio UI as a single feature CommsPanel (§7) plus a
three-equal-panel "command center" (§16) with "All Features" as a right-hand
column and freely toggled/resized equal panels (§19). In design review (2026-06-11)
that model was rejected for three reasons:

1. **Asymmetric usage, symmetric layout.** Real usage is ~80% feature board /
   ~15% project / ~5% global. Equal columns misrepresent that.
2. **Navigation mixed with content.** "All Features" is a *list of feature cards*
   (navigation). The board scopes are *message threads* (content). Putting a card
   list as an equal peer column beside two threads is visually incoherent.
3. **"Panel" was the wrong primitive.** What we want is a full-screen workspace
   with full-area content sections — not widgets docked inside the existing HQ.

This file is the replacement model.

---

## 2. Mental model

```
CommandCenter = a full-screen WORKSPACE (canvas), not a panel.
                You switch INTO it; it owns the view.

  ┌─ Left sidebar ────────┬─ Main area ───────────────────────────────┐
  │  ALL FEATURES         │  one or more full-area BOARD SECTIONS       │
  │  (navigation)         │  (content)                                  │
  │  resizable, collapsible│  Feature Board / Project Board / Global    │
  └───────────────────────┴────────────────────────────────────────────┘
```

| Primitive | Role | Form |
|---|---|---|
| **Left sidebar** | Navigation — *which feature am I working from* | Resizable, collapsible. Collapsed = icon strip + badges. Expanded = feature cards (accordion). |
| **Board section** | Content — a full-area view of one board scope | Feature Board, Project Board, Global Board. Each fills the main area; multiple active sections split it. |
| **Header tabs** | Which board sections are visible | `[🎯 Feature board] [📁 Project] [🌐 Global] [+ Add]` — multi-select. |
| **`[Presets ▾]`** | Quick layouts | Board view / Pipeline view / Focus / Custom. |
| **"Set as main feature ↗"** | The **bridge** | On an expanded sidebar feature card; swaps the Feature Board section to that feature without disturbing the rest of the layout. |

The old "three panels side by side" is now just **one preset** (Board view:
Global \| Project \| Feature Board), not *the* design.

---

## 3. Left sidebar — "All Features" (navigation)

Was: a right-hand column inside the three-panel layout (SPEC §16.3).
Now: a **resizable left sidebar**, the VS Code / Notion file-tree pattern.

- **Collapsed** → thin icon strip: board emoji per feature + pending/blocked badge
  counts, `[▸]` to expand.
- **Expanded** → feature cards. Cards collapse to thin header bars; clicking a card
  expands it inline (**accordion — one open at a time**, others collapse to bars).
- **Resize handle** on the sidebar's right edge.
- Each expanded card carries quick actions and the **"Set as main feature ↗"** action.

```
┌──────────────────────────────────────────────────────────────────────────┐
│  ◈ COMMAND CENTER           [Presets ▾]                      [Exit ×]   │
├──────┬─────────────────────────────────────────────────────────────────  │
│  📋  │  [🎯 Feature board ●]   [📁 Project ○]   [🌐 Global ○]  [+ Add]  │
├──────┼───────────────────────────────────────────────────────────────────┤
│      │                                                                   │
│  ●   │  🎯  FEATURE BOARD — send-to-agent-diff                          │
│  se  │  ──────────────────────────────────────────────────────────────  │
│  nd  │                                                                   │
│  ──  │  📌  Skip rename detection — that is v2 scope                    │
│  BU  │      human · REVIEWING · 2h ago                                  │
│  IL  │                                                                   │
│  DI  │  10:45  🤖 builder                                               │
│  NG  │  ┌─ question ────────────────────────────────────────────────┐  │
│  💬1 │  │  Scroll sync approach?                                    │  │
│  [↗] │  │    ○  CSS scroll-snap          simple, native             │  │
│      │  │    ○  JS IntersectionObserver  more control               │  │
│  ⚠   │  │                                        [Answer]  ⏳       │  │
│  ev  │  └────────────────────────────────────────────────────────────┘  │
│  en  │                                                                   │
│  ──  │  10:47  👤 you                                                    │
│  RE  │  ┌─ nudge ────────────────────────────────────────────────────┐  │
│  VI  │  │  Use scroll-snap. Keep it simple.                          │  │
│  EW  │  └────────────────────────────────────────────────────────────┘  │
│  ⚠bl │                                                                   │
│  ○   ├───────────────────────────────────────────────────────────────────┤
│  co  │  Reads: ☑ Feature  ☑ Project  ☑ Global                           │
│  mb  │  ┌──────────────────────────────────────────────────────┐        │
│  ──  │  │  Type a message...                                   │[nudge▾]│
│  PL  │  └──────────────────────────────────────────────────────┘ [Send] │
└──────┴───────────────────────────────────────────────────────────────────┘
  ↑ resize handle on sidebar's right edge
```

Sidebar collapsed:

```
├─┬──────────────────────────────────────────────────────────────────────  │
│📋│  [🎯 Feature board ●]   [📁 Project ○]   ...                          │
│●3│  🎯  FEATURE BOARD — ...                                              │
│⚠1│                                                                        │
│▸ │                                                                        │
└──┴──────────────────────────────────────────────────────────────────────  │
   icon strip: board emoji + badge counts, click ▸ to expand
```

Expanded feature card (accordion open) — carries the bridge action:

```
┌─────────────────────────────────────────────────────────────┐
│  ●  comms-board · PLANNING idle                  [Close ▴]  │
│  ─────────────────────────────────────────────────────────  │
│  architect: "Drafting schema..."                            │
│  no pending messages                                        │
│                    [Set as main feature ↗]  [Pause ⏸]      │
└─────────────────────────────────────────────────────────────┘
```

Clicking **"Set as main feature ↗"** swaps the Feature Board section to
`comms-board`; the sidebar accordion and every other section stay put. This is the
sole bridge between sidebar navigation and section content.

---

## 4. Board sections (content)

Each board scope is a **full-area section** below the header (like a Slack channel
or a Notion page), NOT a docked widget. Header tabs choose which sections are
visible; multiple visible sections split the main area.

- **Feature Board** — the message thread for the current *main* feature (set via
  the sidebar). 📌 decisions pin at top; question cards with option pickers;
  nudge / status / warning / escalation styling; `Reads: ☑F ☑P ☑G` scope toggles
  and a compose bar with a type picker at the bottom.
- **Project Board** — project-scoped messages + decisions.
- **Global Board** — org-wide decisions; low-volume, high-signal, rarely written.

**Asymmetric default widths** when all three are visible (replaces SPEC §19's equal
panels): **Feature 50% · Project 30% · Global 20%.** Drag handles still resize;
minimum 280px per section; below that the narrowest collapses to a strip.

### 4.1 Layout options — three-up and stacked are first-class (retained from SPEC §19)

The board sections are flexible — this is **not** a fixed single layout:

- **How many:** show **1, 2, or 3** board sections at once (header tabs toggle each).
- **Direction:** **side-by-side (columns)** OR **stacked (rows)** — the
  `[⊞ side by side] ↔ [☰ stacked]` toggle from SPEC §19.3 carries over unchanged.
- **Sizing:** every section is drag-resizable. Asymmetric widths are only the *default*
  of the "Board view" preset; drag to equal-width (or any split) freely.
- **The classic "three-panel"** = all 3 board sections side-by-side = the **"Board view"**
  preset. It is fully supported — the only change from SPEC §16 is that the third column
  is now the Feature *thread* (Global \| Project \| Feature board), because the feature
  *list* moved to the left sidebar.

```
Side-by-side (3 board sections)        Stacked (3 board sections)
┌──────┬──────────┬──────────┐         ┌────────────────────────┐
│ 🌐   │ 📁       │ 🎯       │         │ 🌐 GLOBAL              │
│GLOBAL│ PROJECT  │ FEATURE  │         ├────────────────────────┤
│      │          │ board    │         │ 📁 PROJECT             │
│      │          │ (thread) │         ├────────────────────────┤
└──────┴──────────┴──────────┘         │ 🎯 FEATURE board       │
   (+ left sidebar for All Features)    └────────────────────────┘
                                          (+ left sidebar)
```

The left **sidebar** (All Features) is independent of this — it sits beside whatever
section layout is active, and collapses on its own.

---

## 5. Header — section tabs + presets

```
[🎯 Feature board ●]  [📁 Project ○]  [🌐 Global ○]  [+ Add]        [Presets ▾]
```

- **Section tabs** are multi-select toggles (filled = visible). Click order = left-
  to-right order (carried over from SPEC §19.1, but now they toggle *sections*, not
  equal panels).
- **`[Presets ▾]`** quick layouts:
  - **Board view** — Global \| Project \| Feature Board (the old three-panel)
  - **Pipeline view** — Feature Board, with the All-Features sidebar prominent
  - **Focus** — Feature Board only, full width
  - **Custom** — whatever the user arranged (persisted to `localStorage`)

---

## 6. Build order (supersedes SPEC §22 Phase 2 / Phase 4 step lists)

The user does not want a standalone single-feature CommsPanel wired as a tab into
the existing HQ (SPEC §7). Instead:

1. **CommsPanel components, standalone — no HQ tab wiring.** Build the component
   files + `commsStore`, verify them against the **live SSE stream** (`/events/comms`)
   in isolation. These components are reused by both the CommandCenter and Phase 5
   ConsultPanel, so they must exist regardless — they simply skip the standalone tab
   home that §7 described.
2. **Move straight into the CommandCenter** (sidebar + full-area board sections +
   presets, this file). No intermediate one-board-at-a-time HQ tab.
3. **Phase 5 ConsultPanel reuses CommsPanel** as its shell (unchanged from SPEC).

So Phase 2 and Phase 4 effectively merge at the UI layer: there is no separate
"ship a single CommsPanel tab" milestone. Phase 2 delivers the *verified component
library*; Phase 4 delivers the *CommandCenter workspace* that hosts it.

---

## 7. Component structure (reconciles SPEC §21.9)

Unchanged, reusable building blocks (build + verify standalone first):

```
CommsPanel/                  ← the reusable board-thread building block
  CommsPanel.tsx             ← thread shell: pinned decisions, scope toggles, send bar
  CommsMsgList.tsx           ← message thread  (pattern: MessageList/)
  CommsMsgCard.tsx           ← per-type card    (pattern: AgentQuestionCard/)
  CommsInput.tsx             ← compose bar + type picker  (pattern: ChatInput/)
  useCommsPanel.ts           ← SSE subscription, send handlers, pending count
  *.module.css
store/commsStore.ts          ← messages, board, scope, pendingCount  (pattern: chatStore.ts)
```

CommandCenter (the workspace — revised from SPEC §21.9 to add the sidebar and drop
the equal-panel slot model):

```
CommandCenter/
  CommandCenter.tsx          ← workspace shell: header tabs, presets, sidebar + sections
  FeatureSidebar.tsx         ← NEW: left nav — feature cards, accordion, "Set as main ↗"
  FeatureSidebar.module.css
  BoardSection.tsx           ← a full-area section hosting one CommsPanel (board scope)
  BoardSection.module.css
  useSectionResize.ts        ← drag-to-resize for sections AND the sidebar
  useCommandCenter.ts        ← which sections visible, order, preset, main feature
store/commandCenterStore.ts  ← sections[], order, sizes, preset, sidebarWidth,
                               sidebarCollapsed, mainFeature   (persist → localStorage)
```

Key deltas vs SPEC §21.9: `PanelSlot`/`usePanelResize` (the equal-panel slot model)
are replaced by `BoardSection` + a `FeatureSidebar`; `commandCenterStore` adds
`sidebarWidth`, `sidebarCollapsed`, and `mainFeature`.

---

## 8. What carries over unchanged from SPEC

- The board backend (Phase 1) — schema, embeddings, endpoints, SSE, FSM injection.
- Per-feature `board_scope` read toggles (`☑ Feature ☑ Project ☑ Global`) — SPEC §16.4.
- Message types, question cards, decision pinning, warning/escalation banners — SPEC §7.3.
- Cross-scope task dispatch and broadcast semantics — SPEC §16.5 (the *behavior*;
  the *layout* it lived in is superseded).
- Phase 5 Board-Storm / ConsultPanel reusing CommsPanel — SPEC §23.
```
