# board-grid — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point for feature context |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria — the contract |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design — the what and how |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts — one section per conversation |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status — the checkpoint |
| `HAPPY_FLOW.md` | Planner | Builder | Golden-path narrative |
| `EDGE_CASES.md` | Planner | Builder, Reviewer | Failure modes and risk scenarios |
| `ARCHITECTURE_PROPOSAL.md` | Planner | Builder, Architect | Key design decisions from the architect consult |
| `FLOW_DIAGRAM.md` | Planner | Builder | Data flow diagram |

### Optional plan files (present if signals fired)

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Cross-layer design decisions |
| `EDGE_CASES.md` | yes | Failure modes and risk scenarios |
| `HAPPY_FLOW.md` | yes | Golden-path narrative |
| `FLOW_DIAGRAM.md` | yes | Multi-component interaction diagram |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `studio/src/renderer/src/components/CommandCenter/CommsPanel/GridView/gridBands.ts` | Conv 1 | CREATE — pure split function: Message[] → { goals, tasks, messages, artifacts } |
| `studio/src/renderer/src/components/CommandCenter/CommsPanel/GridView/Tile/Tile.tsx` | Conv 1 | CREATE — compact tile: badge + 2-line title + meta row |
| `studio/src/renderer/src/components/CommandCenter/CommsPanel/GridView/Tile/Tile.module.css` | Conv 1 | CREATE — tile layout + data-type left-accent tints |
| `studio/src/renderer/src/components/CommandCenter/CommsPanel/MessageDetailModal/MessageDetailModal.tsx` | Conv 1 | CREATE — MsgCard in a portal modal shell |
| `studio/src/renderer/src/components/CommandCenter/CommsPanel/MessageDetailModal/MessageDetailModal.module.css` | Conv 1 | CREATE — backdrop + modal box styles |
| `studio/src/renderer/src/components/CommandCenter/CommsPanel/GridView/GridView.tsx` | Conv 2 | CREATE — band host + state owner (modal wiring + resize observer) |
| `studio/src/renderer/src/components/CommandCenter/CommsPanel/GridView/GridView.module.css` | Conv 2 | CREATE — responsive container-query grid + sticky band headers |
| `studio/src/renderer/src/components/CommandCenter/CommsPanel/BoardViewToggle/BoardViewToggle.tsx` | Conv 2 | EDIT — widen BoardView union to include 'grid'; add 4th VIEWS entry (LayoutGrid icon) |
| `studio/src/renderer/src/components/CommandCenter/CommsPanel/CommsPanel/CommsPanel.tsx` | Conv 2 | EDIT — rightAction null branch for 'grid'; GridView conditional render |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Leaf components | S1, S2, S3 | TODO | `gridBands.ts`, `Tile.tsx`, `Tile.module.css`, `MessageDetailModal.tsx`, `MessageDetailModal.module.css` |
| 2 | GridView assembly + wiring | S4, S5, S6 | TODO | `GridView.tsx`, `GridView.module.css`, `BoardViewToggle.tsx`, `CommsPanel.tsx` |

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/features/board-grid/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
