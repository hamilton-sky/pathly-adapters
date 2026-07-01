# DESIGN_SPEC — Skill Notebook Editor

Stage: DESIGN
Author: architect
Scope: technical architecture only. Requirements and user stories live with the planner.

---

## 0. Position summary (TL;DR — what I am recommending)

| # | Decision | Recommendation |
|---|---|---|
| 1 | Notebook in-memory model | Flat ordered list of cell objects, each with stable `uuid` ID and discriminated `kind` |
| 2 | Body parsing | Single-pass line scanner, fenced-block aware, frontmatter skipped, `##`-only as section boundary |
| 3 | Serialization | Body stays as `.md`, fragments stay external — **the notebook never inlines fragment text**. Mid-body insertion is expressed via a new `ordered_cells:` schema in `composition.yaml` |
| 4 | Mid-body insertion in `compose_skill()` | Add `ordered_cells:` field (sibling to `fragments:`). When present, composer interleaves body sections by `section_id` with fragments. `fragments:` continues to work unchanged |
| 5 | Runtime preview | Reuse Python via a new `POST /skills/preview` FSM endpoint — do **not** reimplement composer in TS |
| 6 | IPC contract | Six new channels under `skill:*`, all main-process pass-throughs to the FSM HTTP server |
| 7 | Fragment metadata | Frontmatter inside each fragment `.md` file, validated by `compose.validate_composition()` extension. No new YAML file |
| 8 | Renderer state | Single Zustand store `skillNotebookStore`. Cells held in an `array` plus an `idIndex` map. Undo/redo via bounded history of patches |

The three highest-risk decisions are (3), (4), and (5). Risk analysis in §10.

---

## 1. Data model

### 1.1 Cell types — discriminated union

```ts
type CellId = string  // uuid v4, stable across drag-reorder

type BodyCell = {
  id: CellId
  kind: 'body'
  section_id: string     // slug derived from the heading, stable across edits
  heading: string        // "## Role" — raw with prefix
  level: 2               // only ## is a section boundary
  body: string           // raw markdown between this heading and the next ##
  read_only: true        // notebook surface; editing happens elsewhere
}

type FragmentCell = {
  id: CellId
  kind: 'fragment'
  fragment_name: string  // matches a .md file under skills/fragments/
  requires?: string      // optional capability gate, e.g. "can_spawn"
  // No body — name + requires are the only persistent fields.
  // Display content is fetched live from the fragment file.
}

type DividerCell = {
  id: CellId
  kind: 'divider'        // visual only; not serialized
  label?: string
}

type Cell = BodyCell | FragmentCell | DividerCell
```

### 1.2 Notebook document

```ts
type SkillNotebook = {
  skill: string              // "team/build" — manifest key, no .md
  adapter: 'claude' | 'codex' | 'copilot' | 'antigravity'  // for preview caps
  cells: Cell[]              // ordered; the SOLE source of order truth
  dirty: boolean
  source_hash: string        // hash of (body.md + composition.yaml slice) at load
}
```

### 1.3 Mapping to existing files

```
on-disk                              notebook in-memory
─────────────────────────────────    ──────────────────────────────────
core/skills/team/build.md            cells[].filter(kind==='body')
  ## Role                              { section_id: 'role',    body: ... }
  ## FSM operations                    { section_id: 'fsm-ops', body: ... }
  ## Subagents                         { section_id: 'subagents', body: ... }
  ...

composition.yaml                     cells[].filter(kind==='fragment')
  skills:
    team/build:
      fragments:
        - completion-report  ───►    { kind: 'fragment', fragment_name: 'completion-report' }
        - { name: spawn-rules,       { kind: 'fragment', fragment_name: 'spawn-rules',
            requires: can_spawn }      requires: 'can_spawn' }
```

When the skill currently uses the legacy `fragments: []` form, **all body cells come first, then all fragment cells** — that is the bit-identical view of today's behavior. The editor only diverges from `fragments:` once the user reorders cells; then it switches the YAML to `ordered_cells:` on export (see §4).

---

## 2. Body parsing — canonical algorithm

### 2.1 Why a hand-rolled scanner, not a markdown AST

Pulling in `remark` or `markdown-it` doubles renderer bundle weight for a 60-line problem. Skills are author-controlled markdown — the surface is small and stable. A scanner is also trivially reversible on export, which an AST is not.

### 2.2 Edge cases the algorithm must handle

| Case | Rule |
|---|---|
| YAML frontmatter (`---\n…\n---`) at top of file | Capture verbatim into `notebook.frontmatter`, do not split |
| `## Heading` inside fenced code block (```` ``` ````) | NOT a section boundary |
| `## Heading` inside indented code (4 spaces) | NOT a section boundary |
| `#` (H1) | Treated as preamble of the first body cell, not a section |
| `###`, `####` (H3+) | Stay inside the parent `##` section as plain content |
| Text before the first `##` | Becomes a synthetic "preamble" body cell with `section_id: '__preamble__'` |
| Trailing blank lines | Trimmed in cells, restored on serialize |

### 2.3 Algorithm (pseudocode)

```
parse_body(text):
    lines = text.splitlines()
    i = 0
    frontmatter = ""
    if lines[0] == "---":
        end = find_next("---", lines, from=1)
        frontmatter = lines[0..end].join("\n")
        i = end + 1

    cells = []
    current = { section_id: "__preamble__", heading: "", body: [] }
    in_fence = false

    while i < len(lines):
        line = lines[i]
        if FENCE_RE.match(line):
            in_fence = !in_fence
            current.body.push(line)
        elif not in_fence and H2_RE.match(line):  # ^## (?!#)
            cells.push(finalize(current))
            current = {
                section_id: slugify(line[3:].strip()),
                heading: line,
                body: []
            }
        else:
            current.body.push(line)
        i += 1
    cells.push(finalize(current))
    return { frontmatter, cells }
```

`slugify("FSM operations") -> "fsm-operations"`. Collisions get `-2`, `-3` suffixes. `section_id` is what gets persisted to YAML and what makes round-trips stable.

### 2.4 Where the parser lives

Python only: `src/pathly_orchestrator/skill_notebook.py`. The renderer never parses markdown. This keeps section identity authoritative on the backend and prevents drift between preview, export, and the runner.

---

## 3. Serialization strategy

### 3.1 The decision: stay split, never inline

**Fragments stay external references in `composition.yaml`. The notebook never writes fragment text into the skill `.md`.**

Why:

```
Inline approach                     Split approach (recommended)
──────────────────────              ──────────────────────────────
fragments are duplicated            fragments edited once → all skills update
across every skill .md              automatically
                                    
fragment edits require              fragment edits = 1 file touched
N file rewrites
                                    
git diff = noisy; touching          git diff = surgical; clear what changed
scout-choreography rewrites
12 skills

compose.py becomes a no-op          compose.py stays the single composer
(or two parallel composers)         used by both runner and pathly-setup

runner mode can skip                runner mode still calls compose_skill()
compose.py entirely (a regression)  with zero change

```

The split approach also preserves the manifest's stated invariant — *"every shared section appears exactly once (body OR fragment, never both)"* — which inlining would silently violate the moment a user edits a body cell that overlaps a fragment.

### 3.2 On export — what the notebook writes

Given a notebook with cells in order `[body, body, fragment, body, fragment, fragment]`:

1. **Body `.md` file** — concatenate `BodyCell.heading + "\n" + BodyCell.body` for body cells **in their notebook order** (which may differ from the original file order if the user reordered sections). Frontmatter restored verbatim at top.

2. **`composition.yaml` entry** — write the new `ordered_cells:` form (see §4):
   ```yaml
   team/build:
     ordered_cells:
       - { body: role }
       - { body: fsm-operations }
       - { fragment: completion-report }
       - { body: subagents }
       - { fragment: scout-choreography }
       - { fragment: spawn-rules, requires: can_spawn }
   ```

3. **Backward-compat shortcut** — if the notebook's cell order is `[all bodies in original order] + [all fragments]`, write the legacy `fragments: []` form instead. This keeps existing skills unchanged on disk for users who never reorder.

### 3.3 Round-trip safety

The hash recorded at load (`source_hash`) is checked on export. If the disk file changed since load (another process edited it, or the runner ran), Studio shows a merge prompt. No silent overwrites.

---

## 4. Mid-body insertion — `compose_skill()` change

### 4.1 The change

Extend the per-skill spec with an optional `ordered_cells:` field. When present, **it wins over `fragments:`**.

```yaml
skills:
  team/build:
    # NEW — optional, takes precedence over `fragments`
    ordered_cells:
      - { body: role }
      - { body: fsm-operations }
      - { fragment: completion-report }
      - { body: subagents }
      - { fragment: scout-choreography }
      - { body: execution }
      - { fragment: spawn-rules, requires: can_spawn }
      - { body: transition-to-review }
```

Composer change (minimal diff to `compose.py`):

```
if "ordered_cells" in spec:
    # NEW PATH
    sections = parse_body(raw).cells_by_section_id
    parts = []
    defaults_emitted = False
    for entry in spec["ordered_cells"]:
        if "body" in entry:
            section = sections.get(entry["body"])
            if section is None:
                raise ValueError(f"missing body section {entry['body']!r}")
            parts.append(section.text.rstrip())
            # First body cell triggers default fragments (preserves existing semantics)
            if not defaults_emitted:
                for d in manifest.get("defaults") or []:
                    parts.append(_read_fragment(...).rstrip())
                defaults_emitted = True
        elif "fragment" in entry:
            name = entry["fragment"]
            requires = entry.get("requires")
            if requires and not caps.get(requires): continue
            parts.append(_read_fragment(fragments_dir, name).rstrip())
    return "\n\n".join(parts) + "\n"
else:
    # EXISTING PATH — unchanged
    ...
```

### 4.2 Why this over the alternatives

| Option | Verdict | Reason |
|---|---|---|
| `<!--slot:name-->` markers in body | Reject | Markers are invisible in rendered markdown, easy to drop on copy-paste, force compose.py to do string surgery on every load. Body files stop being meaningful as standalone skills. |
| `ordered_cells:` (recommended) | Accept | Body file stays canonical and readable on its own. All composition logic stays in one place (`compose.py`). Backward-compatible — legacy `fragments:` keeps working. Round-trips cleanly because section IDs are stable. |
| Pre-split named sections in body (`role.md`, `fsm-ops.md`) | Reject | Multiplies file count by ~6 per skill (around 50 new files). Loses the human read of a skill as one document. Git history fragments. Breaks `_read_skill_body` consumers. |

### 4.3 Compatibility matrix

```
                              runner (FSM)    pathly-setup   Studio notebook
fragments: [...] (legacy)     works           works          read+show as
                                                             [body][fragments]
ordered_cells: [...] (new)    works           works          full reorder UI
both present                  ordered_cells   ordered_cells  validator rejects
                              wins, warn      wins, warn     before save
```

`validate_composition()` gets one new rule: *both fields present → error*. Body section IDs referenced in `ordered_cells` must exist in the parsed body.

---

## 5. Runtime preview — Python wins

### 5.1 The decision: new HTTP endpoint on the FSM server

```
POST http://127.0.0.1:8765/skills/preview
{
  "skill": "team/build",
  "adapter": "claude",
  "draft": {                       // optional: preview unsaved notebook state
    "body_sections": [ { "section_id": "...", "heading": "...", "body": "..." }, ... ],
    "ordered_cells": [ { "body": "role" }, { "fragment": "completion-report" }, ... ]
  },
  "feature": "demo-feature"        // for variable injection
}

response: {
  "assembled": "<full markdown>",
  "warnings": ["missing section 'foobar'", ...]
}
```

When `draft` is omitted, the server reads from disk — same as the runner. When `draft` is present, it composes against the in-memory cells **without writing anything**.

### 5.2 Why not reimplement in TypeScript

```
TS reimplementation                  Python endpoint (recommended)
─────────────────────                ─────────────────────────────
Two composers to keep in sync        One composer, one truth
Drift = silent prompt corruption     Drift impossible
TS must duplicate YAML parsing,      Reuses existing code paths
caps resolution, frontmatter         (_inject_prompt_vars, etc.)
substitution
Renderer bundles js-yaml,            Renderer stays small
markdown utilities
Adapter caps logic gets forked       Caps stay in compose.py
into ~/.codex/, ~/.copilot/, etc.    
                                     
Preview can drift from what          Preview is bit-identical to runner
the runner actually sends            output
```

The one cost — a 30-50ms HTTP round-trip per preview refresh — is a non-issue. Debounce keystrokes at 250ms; the user perceives nothing.

### 5.3 Fallback

If the FSM server is down (Studio launched it but it crashed), the preview panel shows a clear "FSM server unreachable" state with a retry button — same pattern Studio already uses for `fsm:ping`.

---

## 6. IPC contract

Six new channels, all in a new file `studio/src/main/ipc/skills.ts`. All are thin pass-throughs to the FSM HTTP server. No business logic in the main process.

### 6.1 Channel list

```
skill:list                      list all skills (manifest keys)
skill:load-notebook             load a skill as a notebook
skill:list-fragments            catalog with metadata
skill:preview                   render assembled markdown (with optional draft)
skill:export                    write body.md + composition.yaml updates
skill:validate                  dry-run validator on a draft
```

### 6.2 Shapes

```ts
// skill:list — for the picker
window.pathly.skill.list(): Promise<{
  skills: Array<{
    key: string                   // "team/build"
    body_path: string             // absolute
    has_ordered_cells: boolean
    fragment_count: number
  }>
}>

// skill:load-notebook
window.pathly.skill.loadNotebook(key: string): Promise<{
  notebook: SkillNotebook         // §1
  source_hash: string
  warnings: string[]
}>

// skill:list-fragments
window.pathly.skill.listFragments(): Promise<{
  fragments: Array<{
    name: string                  // "scout-choreography"
    description: string           // from frontmatter
    category: 'core' | 'flow' | 'integration' | 'misc'
    requires?: string
    body_preview: string          // first ~200 chars for the catalog card
  }>
}>

// skill:preview
window.pathly.skill.preview(req: {
  skill: string
  adapter: string
  feature?: string                // default "demo-feature"
  draft?: {                       // omit to preview saved-on-disk
    body_sections: BodyCell[]
    ordered_cells: Array<{ body: string } | { fragment: string; requires?: string }>
  }
}): Promise<{ assembled: string; warnings: string[] }>

// skill:export
window.pathly.skill.export(req: {
  skill: string
  notebook: SkillNotebook
  expected_source_hash: string    // optimistic concurrency check
}): Promise<
  | { ok: true; written: string[] }
  | { ok: false; reason: 'stale' | 'validation'; details: string[] }
>

// skill:validate
window.pathly.skill.validate(notebook: SkillNotebook):
  Promise<{ ok: boolean; errors: string[]; warnings: string[] }>
```

### 6.3 Wiring per Studio convention

For each channel:
1. `ipcMain.handle('skill:<x>', ...)` in `studio/src/main/ipc/skills.ts`
2. Bridge in `studio/src/main/preload/index.ts` under `window.pathly.skill.*`
3. Types in `studio/src/renderer/src/types/global.d.ts`

Same pattern as the existing `fsm.ts`. Each handler is ~10 lines: fetch, return.

---

## 7. Fragment metadata — frontmatter wins

### 7.1 The decision

Fragment files get YAML frontmatter. No new top-level file. No extension of `composition.yaml`.

```markdown
---
description: Scout/quick analyze→scout→compress pattern shared across stages
category: flow
requires: can_spawn   # optional — informational only, gate still lives in composition.yaml
---

## Scout choreography (analyze → scout → compress)
...
```

### 7.2 Why frontmatter

| Option | Verdict | Why |
|---|---|---|
| (a) Frontmatter per fragment | Accept | Metadata sits with the asset it describes. No second file to keep in sync. The body-parser already needs to recognize frontmatter for skill files — reuse that path. |
| (b) New `fragment-catalog.yaml` | Reject | Adds a second source of truth. Fragment additions must touch two files. New `pathly-setup` validation rule. Drift risk. |
| (c) Extend `composition.yaml` | Reject | `composition.yaml` is per-skill wiring; mixing in catalog-level metadata muddies its purpose. Validation rules already complex. |

### 7.3 What `validate_composition()` gains

A new check: every fragment file in `fragments/` must have parseable frontmatter with at least `description` and `category`. Missing → error. This catches accidental commits of fragments without catalog info.

### 7.4 Category values

Initial enum: `core | flow | integration | misc`. Renderer uses these to group the catalog sidebar:

```
┌─ Catalog ──────────────┐
│ ▼ Core                 │
│   • completion-report  │
│   • progress-logging   │
│ ▼ Flow                 │
│   • scout-choreography │
│   • feedback-protocol  │
│ ▼ Integration          │
│   • spawn-rules        │
│ ▶ Misc                 │
└────────────────────────┘
```

---

## 8. Renderer state — Zustand shape

### 8.1 Store

A single new store `studio/src/renderer/src/store/skillNotebookStore.ts`. Other stores stay untouched.

```ts
type SkillNotebookState = {
  // Loaded notebook
  notebook: SkillNotebook | null
  loading: boolean
  error: string | null

  // O(1) lookup by cell ID — derived but cached
  idIndex: Map<CellId, number>

  // Catalog
  catalog: FragmentCatalogEntry[]
  catalogLoading: boolean

  // Preview
  previewMarkdown: string
  previewStale: boolean

  // Undo/redo
  history: NotebookPatch[]        // bounded ring buffer, cap 50
  historyCursor: number

  // Actions
  loadNotebook: (key: string) => Promise<void>
  moveCell: (id: CellId, toIndex: number) => void
  insertFragment: (name: string, atIndex: number) => void
  deleteCell: (id: CellId) => void
  setBodyContent: (id: CellId, body: string) => void   // for future inline edit
  refreshPreview: () => Promise<void>
  exportNotebook: () => Promise<ExportResult>
  undo: () => void
  redo: () => void
}
```

### 8.2 Cell IDs and React keys

**Cell IDs are uuid v4 minted at parse time (Python) for body cells and on insert (renderer) for fragment cells.** They persist in memory only — they are NOT serialized to YAML or markdown. On reload, body cells get fresh IDs.

Why this works for `react-beautiful-dnd` / `@dnd-kit`:

```
problem                            fix
───────                            ───
array index as key → drag          uuid as key → identity stable
reorder remounts every item        across reorder; React diff is
(state loss, animation jank)       minimal
                                   
two fragment cells with same       each insert mints a new uuid;
name collide                       same fragment name can appear N
                                   times safely
```

### 8.3 Undo/redo via patches, not snapshots

Snapshotting the whole notebook on every reorder is fine for 20 cells but wasteful and obscures intent. Patches are explicit:

```ts
type NotebookPatch =
  | { op: 'move'; id: CellId; from: number; to: number }
  | { op: 'insert'; cell: Cell; at: number }
  | { op: 'delete'; cell: Cell; at: number }
  | { op: 'setBody'; id: CellId; before: string; after: string }
```

Each patch is invertible. Ring buffer of 50 patches. `undo()` walks back, `redo()` walks forward. Editing past the cursor truncates the redo tail. This also gives a future "operation log" view for debugging or replay.

### 8.4 Preview debounce

```
user drags cell  ──►  store.moveCell()  ──►  previewStale = true
                                              │
                                              ▼
                                       debounce 250ms
                                              │
                                              ▼
                                       skill.preview() IPC
                                              │
                                              ▼
                                       previewMarkdown updated
```

---

## 9. End-to-end flow

```
┌───────────────────────────────────────────────────────────────────┐
│ Studio renderer (React)                                           │
│                                                                   │
│  ┌─────────────┐   ┌──────────────┐   ┌───────────────────────┐  │
│  │  Catalog    │   │   Notebook   │   │   Preview pane        │  │
│  │  sidebar    │──►│   (cells)    │──►│   (assembled .md)     │  │
│  └─────────────┘   └──────────────┘   └───────────────────────┘  │
│         │                 │                       │              │
│         │                 ▼                       │              │
│         │         skillNotebookStore              │              │
│         │         (Zustand)                       │              │
│         │                 │                       │              │
└─────────┼─────────────────┼───────────────────────┼──────────────┘
          │                 │                       │
          │ skill.list      │ skill.export          │ skill.preview
          │ Fragments       │                       │
          ▼                 ▼                       ▼
┌───────────────────────────────────────────────────────────────────┐
│ Electron main process — ipc/skills.ts                             │
│   thin HTTP pass-through, no business logic                       │
└───────────────────────────────────────────────────────────────────┘
          │                 │                       │
          ▼                 ▼                       ▼
┌───────────────────────────────────────────────────────────────────┐
│ FSM HTTP server (Python, :8765)                                   │
│                                                                   │
│   /skills/list  /skills/load  /skills/fragments                   │
│   /skills/preview  /skills/export  /skills/validate               │
│        │                                                          │
│        ▼                                                          │
│   compose.py  +  skill_notebook.py (parser, splitter, writer)     │
│        │                                                          │
│        ▼                                                          │
│   core/skills/*.md  +  composition.yaml  (on disk)                │
└───────────────────────────────────────────────────────────────────┘
```

The runner path (`supervisor.py` → `build_prompt` → `compose_skill`) is **unchanged**. The notebook is purely an authoring surface that writes to the same files the runner already reads.

---

## 10. Highest-risk decisions

### Risk 1 — `ordered_cells` schema split (Decision 4)

We now have two ways to express the same skill (`fragments:` vs `ordered_cells:`). The validator catches "both present" but cannot catch *semantic* drift if a third tool (manual yaml edit, scripted migration) writes a malformed cell list.

**Mitigation:**
- `validate_composition()` runs as part of `python -m build` and `pathly-setup --apply` — bad YAML fails the build.
- `compose_skill()` raises on missing section IDs rather than silently dropping.
- Migration helper: `pathly-skill migrate <skill>` converts `fragments:` → `ordered_cells:` deterministically, so users do not hand-write the new form.

### Risk 2 — Body parser fidelity (Decision 2 + 3)

The whole round-trip rests on `parse_body(serialize(parse_body(x))) == parse_body(x)` for any skill `x`. A bug here means the editor silently mangles author intent.

**Mitigation:**
- Property test in `tests/test_skill_notebook.py`: for every `.md` under `core/skills/`, parse → serialize → re-parse → assert identical cell list.
- Run this in CI on the existing 30+ skill bodies before shipping the editor.
- Refuse to load a skill where the round-trip is not bit-identical; surface a clear "unsupported markdown shape" error rather than corrupting it.

### Risk 3 — Preview = runner assumption (Decision 5)

The preview is only trustworthy if it goes through the exact same code path as `supervisor.py` does. If `/skills/preview` and `build_prompt` diverge (e.g., different variable injection), the user authors against a fiction.

**Mitigation:**
- `/skills/preview` is a thin wrapper that calls the **same** `compose_skill()` plus the **same** `_inject_prompt_vars()` the runner uses — no parallel implementation.
- Snapshot test: assert preview output for a sample skill equals what `build_prompt()` produces for that same skill with matching inputs.
- Display the `feature`, `adapter`, and `caps` actually used in a header strip on the preview pane, so the user can see the substitution context.

---

## 11. Out of scope for this design

- Multi-user concurrent editing — single-author assumption holds.
- Editing fragment bodies from inside the notebook — separate concern; a fragment editor is a follow-up. The notebook can `Open fragment in editor` link out.
- Skill creation (new skill from scratch) — phase-2 feature. v1 edits existing skills only.
- Custom cell types beyond body/fragment/divider — locked enum until v1 is shipped.

---

## 12. Open questions for the planner

None blocking the design. The planner should decide v1 scope on these UX points before BUILDING:

1. Do body cells get edited in-notebook in v1, or is the body read-only with an "Open in VS Code" affordance?
2. Should the catalog support search/filter in v1, or just grouping by category?
3. Is the adapter selector inside the notebook (per-preview) or a global Studio setting?
