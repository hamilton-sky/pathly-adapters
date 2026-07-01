# skill-notebook-editor — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## What this feature is

A Jupyter/Colab-style three-panel skill editor embedded in Pathly Studio:
- **Fragment Catalog** (sidebar, 240px) — draggable capability cards grouped by CORE / FLOW / INTEGRATION
- **Notebook Canvas** (flex) — skill body cells (locked) + fragment cells (draggable, deletable), native HTML5 DnD
- **Preview Panel** (320px) — live assembled prompt via `POST /skills/preview`, `<feature_path>` substitution, `[BODY]`/`[FRAG]` badges

Visual mockup: `preview.html` (open in browser)
Design system: `DESIGN.md`
Technical architecture: `DESIGN_SPEC.md`

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | **This file** — single entry point for feature context |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria (US-01 → US-08) — the contract |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Architecture decisions, data model, component tree, conversation breakdown |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts — one section per conversation |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status — the checkpoint |
| `DESIGN.md` | Designer | Builder | Design system: tokens, typography, component map, builder notes |
| `DESIGN_SPEC.md` | Architect | Builder | Technical spec: data model, IPC contract, body parser, serialization |
| `preview.html` | Designer | Builder, Reviewer | Self-contained visual mockup — reference for exact appearance |

### Optional plan files

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | no | (covered by DESIGN_SPEC.md) |
| `EDGE_CASES.md` | no | |
| `HAPPY_FLOW.md` | no | |
| `FLOW_DIAGRAM.md` | no | |

---

## Codebase touchpoints

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

### Conv 1 — Python (new files + additions)

| Codebase file | What changes |
|---|---|
| `src/pathly_orchestrator/skill_parser.py` | NEW — body parser: splits skill `.md` on `##` headings |
| `src/pathly_orchestrator/skill_catalog.py` | NEW — reads fragment `.md` files, parses YAML frontmatter |
| `src/pathly_orchestrator/` (routes file) | ADD — 3 new routes: `GET /skills/catalog`, `POST /skills/parse`, `POST /skills/preview`, `PUT /skills/export` |
| `src/pathly_data/core/skills/fragments/` | READ ONLY — fragment source files |
| `src/pathly_data/core/skills/composition.yaml` | READ + WRITE — export updates fragment order |

### Conv 2 — TypeScript (store + routing + sidebar)

| Codebase file | What changes |
|---|---|
| `studio/src/renderer/src/store/uiStore.ts` | ADD `'skill-notebook'` to ActivePanel union + `skillNotebookPath` state |
| `studio/src/renderer/src/store/skillNotebookStore.ts` | NEW — cells[], history ring, featurePath, preview state |
| `studio/src/renderer/src/App.tsx` | ADD `case 'skill-notebook'` to MainPanel switch |
| `studio/src/renderer/src/components/SkillNotebook/SkillNotebook.tsx` | NEW — placeholder shell |
| `studio/src/renderer/src/components/sidebar/Sidebar.tsx` | ADD CATALOG mode: when activePanel === 'skill-notebook' show [CATALOG\|FILES] tabs |
| `studio/src/renderer/src/components/sidebar/panels/CatalogPanel/CatalogPanel.tsx` | NEW |
| `studio/src/renderer/src/components/sidebar/panels/CatalogPanel/FragmentCard/FragmentCard.tsx` | NEW |

### Conv 3 — TypeScript (notebook canvas + DnD)

| Codebase file | What changes |
|---|---|
| `studio/src/renderer/src/store/skillNotebookStore.ts` | FILL OUT — loadSkill, insertFragment, removeCell, moveCell, undo/redo |
| `studio/src/renderer/src/components/SkillNotebook/SkillNotebook.tsx` | REPLACE placeholder with real layout |
| `studio/src/renderer/src/components/SkillNotebook/NotebookCanvas/NotebookCanvas.tsx` | NEW |
| `studio/src/renderer/src/components/SkillNotebook/NotebookCanvas/BodyCell/BodyCell.tsx` | NEW |
| `studio/src/renderer/src/components/SkillNotebook/NotebookCanvas/FragmentCell/FragmentCell.tsx` | NEW |
| `studio/src/renderer/src/components/SkillNotebook/NotebookCanvas/InsertZone/InsertZone.tsx` | NEW |

### Conv 4 — TypeScript (preview + header + export)

| Codebase file | What changes |
|---|---|
| `studio/src/renderer/src/components/SkillNotebook/NotebookHeader/NotebookHeader.tsx` | NEW — follows Monitor/HeaderBar.tsx pattern |
| `studio/src/renderer/src/components/SkillNotebook/PreviewPanel/PreviewPanel.tsx` | NEW |
| `studio/src/renderer/src/components/SkillNotebook/PreviewPanel/PreviewSection/PreviewSection.tsx` | NEW |
| `studio/src/renderer/src/styles/tokens.css` | ADD 3 semantic aliases: `--cell-body-border`, `--cell-fragment-border`, `--cell-variable-highlight` |

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Python: FSM endpoints + body parser | US-06, US-07 | TODO | `skill_parser.py`, `skill_catalog.py`, FSM routes |
| 2 | TS: Store + routing + Sidebar CATALOG + CatalogPanel | US-01, US-02 | TODO | `uiStore.ts`, `Sidebar.tsx`, `CatalogPanel/` |
| 3 | TS: skillNotebookStore + NotebookCanvas + cells + DnD | US-03, US-04, US-05, US-08 | TODO | `NotebookCanvas/`, `skillNotebookStore.ts` |
| 4 | TS: PreviewPanel + NotebookHeader + Export | US-06, US-07 | TODO | `PreviewPanel/`, `NotebookHeader/`, `tokens.css` |

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/skill-notebook-editor/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |

---

## Key design decisions (locked — do not override without discussion)

- **No external DnD library** — native HTML5 only (linear list is sufficient)
- **No inline styles** — all CSS in `.module.css` files
- **Preview via FSM** — `POST /skills/preview` routes through `compose_skill()` + `_inject_prompt_vars()`, NOT reimplemented in TypeScript
- **Body cells are read-only in V1** — notebook = composition order only, not body editing
- **Sidebar stays at 240px** — swaps content (CATALOG ↔ FILES tabs), does not collapse
- **Panel header follows Monitor/HeaderBar.tsx pattern** — same CSS class names, same spacing
- **All colors from tokens.css** — zero hardcoded hex values in component CSS
