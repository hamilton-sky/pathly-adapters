# Implementation Plan — pathly-entity-model

_Last updated: 2026-06-29_

## Overview

Four independently shippable phases. Each phase is backward-compatible with live features.
Phase 1 is gated on Phase 0; Phase 2 is gated on Phase 1 tests passing; Phase 3 is renderer-only
and can proceed in parallel with Phase 2 (no shared code).

Stories fulfilled: S0.1, S0.2 (Phase 0) | S1.1–S1.5 (Phase 1) | S2.1–S2.5 (Phase 2) | S3.1–S3.4 (Phase 3)

---

## Phase 0 — Guard

**Fulfills stories:** S0.1, S0.2

### Scope

Ship the `_safe_topic` guard and the `slug` DB column. This phase makes no behavioral change to
working flows. The guard fires only on already-broken calls (those are already looping forever).
Per user decision (board message): `_safe_topic` RAISES immediately, not WARN.

### Files changed

| File | Lines | Change |
|---|---|---|
| `src/pathly_orchestrator/fsm_ops.py` | `:68` top of `_resolve_storage_path` | Add `_safe_topic(topic)` call; define `_safe_topic` in the same file |
| `src/pathly_orchestrator/runner/argv.py` | `:13-21` `_storage_path` | Add `_safe_topic(topic)` call (defense-in-depth; not the active collapse site) |
| `src/pathly_orchestrator/db/migrations.py` | append | Idempotent `ALTER TABLE comms_messages ADD COLUMN slug TEXT`; then `CREATE UNIQUE INDEX IF NOT EXISTS idx_comms_messages_slug ON comms_messages(slug) WHERE slug IS NOT NULL` |
| `tests/test_fsm_ops.py` | new | Test `_safe_topic`: empty string, absolute path (Windows + POSIX), `..`, `a/b`, `a:b`, valid slug all covered |

### `_safe_topic` reference implementation

```python
import os, re
from pathlib import Path

def _safe_topic(topic: str) -> str:
    if (not topic or os.path.isabs(topic) or topic in (".", "..")
            or re.search(r'[\\/:]', topic) or '..' in Path(topic).parts):
        raise ValueError(
            f"unsafe FSM topic {topic!r}: must be a bare slug, not a path/scope")
    return topic
```

Called at the top of `_resolve_storage_path` (`fsm_ops.py:68`) and in `argv._storage_path`.

### Migration pattern

Follow the existing pattern in `migrations_incremental.py`: one `try/except` per `ALTER TABLE`
statement; catch `OperationalError` with "duplicate column" in the message and silently pass.
The UNIQUE index uses `CREATE UNIQUE INDEX IF NOT EXISTS`.

### Test requirements

- `test_safe_topic_empty` — raises `ValueError`
- `test_safe_topic_abs_windows` — raises `ValueError` for `"C:/Users/Yafit/pathly-adapters"`
- `test_safe_topic_abs_posix` — raises `ValueError` for `"/home/user/project"`
- `test_safe_topic_dotdot` — raises `ValueError` for `".."`
- `test_safe_topic_slash` — raises `ValueError` for `"a/b"`
- `test_safe_topic_colon` — raises `ValueError` for `"a:b"`
- `test_safe_topic_valid` — returns the slug unchanged for `"my-feature-slug"`
- `test_slug_column_migration` — column and index exist; duplicate slug raises; NULL slug inserts

### Done criteria

- `pytest tests/test_fsm_ops.py` passes.
- `_safe_topic` function is importable from `fsm_ops`.
- `comms_messages.slug` column and UNIQUE index exist in the DB after migration.
- No existing test suite failures (regression check: `pytest tests/ -q`).

### Builder notes

- `terminal.py` is at 407 lines. Do NOT touch it in Phase 0. The split is Phase 1's first task.
- The `goals/` probe branch in `_resolve_storage_path` is Phase 1 work — Phase 0 only adds the guard and the DB column.
- Do not add `_safe_topic` to `supervisor/slug.py` — that file does not exist yet. Define it in `fsm_ops.py` and import from there in Phase 1.

---

## Phase 1 — Bug Fix

**Fulfills stories:** S1.1, S1.2, S1.3, S1.4, S1.5
**Gates:** Phase 2

### Scope

Fix the production bug. Route `topic=slug` at every verified collapse site. Create
`supervisor/slug.py` with `ensure_goal_slug`. Split `terminal.py` before adding new code.
Extend the Studio RESERVED set. Flip `_safe_topic` to RAISE (already done in Phase 0 per user
decision — confirm it is RAISE, not WARN).

### Pre-condition: terminal.py split

`terminal.py` is at 407 lines — over the 400-line SOLID limit. It MUST be split before adding
the storage-path threading code. Extract into two files:
- `supervisor/terminal.py` — keep `_agent_done_watcher` (`:86`, `parent.parent.parent` MUST be preserved verbatim) and PTY lifecycle logic
- `supervisor/terminal_write.py` (or similar name) — extract the summary-write and path-reconstruction logic at `:39`, `:269`, `:307`

After the split, each file must be under 400 lines. All existing tests must pass before proceeding.

### Files changed

| File | Lines | Change |
|---|---|---|
| `src/pathly_orchestrator/supervisor/terminal.py` | split first | Extract to stay under 400 lines; PRESERVE `:86` watcher verbatim |
| `src/pathly_orchestrator/supervisor/slug.py` | NEW | `ensure_goal_slug(conn, goal_id) -> str` under the process-wide write-lock |
| `src/pathly_orchestrator/supervisor/goal_decomposer.py` | `:239`, `:246` | Reset call at `:239`: pass slug; `_decompose_consultation:246`: `topic=slug` |
| `src/pathly_orchestrator/supervisor/goal_executor.py` | `:52`, `:223`, `:317`, `:321` | All four sites: `topic=scope` → `topic=slug`; extract helpers into `_helpers.py` if needed to stay under 400 lines |
| `src/pathly_orchestrator/supervisor/board_run.py` | `:147`, `:247` | Add `slug` param to `start_board_run`; extend `where_line` probe to all tiers + `goals/<slug>/` branch; extract helpers if needed |
| `src/pathly_orchestrator/supervisor/orchestrator.py` | `:336` | `topic=scope` → `topic=slug` |
| `src/pathly_orchestrator/supervisor/registry.py` | `:148-149` | Slug-aware `feature_dir` construction |
| `src/pathly_orchestrator/supervisor/_helpers.py` | create if needed | Shared helpers extracted from near-limit files |
| `src/pathly_orchestrator/fsm_ops.py` | `:68-74` | Add `goals/<slug>` probe branch (sibling to `plans/<slug>`) |
| `studio/src/renderer/src/store/commsStore.ts` | `:140` | Extend RESERVED set with `goals`, `lessons`, `explorations`, `debugs`, `pipeline-walkthrough` |
| `tests/test_goal_slug.py` | NEW | `ensure_goal_slug` idempotency + concurrency test |

### `ensure_goal_slug` contract

```python
# supervisor/slug.py
import re
from db._helpers import _get_write_lock   # reuse the existing process-wide lock

def ensure_goal_slug(conn, goal_id: str) -> str:
    """Return the stable slug for goal_id, creating it if absent.
    Runs inside the process-wide write-lock. UNIQUE index is the DB-level backstop."""
    with _get_write_lock():
        row = conn.execute(
            "SELECT slug, text FROM comms_messages WHERE id = ?", (goal_id,)
        ).fetchone()
        if row and row["slug"]:
            return row["slug"]
        goal_text = row["text"] if row else goal_id
        slug = _slugify(goal_text)[:48] + "-" + goal_id[:8]
        conn.execute(
            "UPDATE comms_messages SET slug = ? WHERE id = ?", (slug, goal_id)
        )
        conn.commit()
        return slug

def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[\s_-]+', '-', text).strip('-')
```

The returned slug must pass `_safe_topic` validation (bare slug, no path separators).

### `_resolve_storage_path` goals probe

After Phase 0 adds the guard at the top of `_resolve_storage_path`, Phase 1 adds the `goals/`
probe branch. The existing two-probe pattern (new-style path → template fallback) becomes a
three-probe pattern: `plans/<slug>/` → `goals/<slug>/` → template fallback. All three paths
satisfy the watcher depth invariant (`pathly/<domain>/<slug>/`).

### Collapse site checklist (exhaustive)

Every instance of `topic=scope` that reaches `_resolve_storage_path` must be converted to
`topic=slug`. Grep the working tree for `topic=scope` and `topic = scope` before committing;
the result must be zero (excluding comments and test fixtures).

Sites confirmed in the architecture doc:
- `goal_decomposer.py:246` (`_decompose_consultation` `_start` call)
- `goal_decomposer.py:239` (reset call before consultation)
- `goal_executor.py:52` (`_reset_fsm_state_for_flow` resolver call)
- `goal_executor.py:223` (`_run_loop` `RunnerState`)
- `goal_executor.py:317` (`_run_team` reset call)
- `goal_executor.py:321` (`_run_team` `_start`)
- `orchestrator.py:336`
- `terminal.py:39, 269, 307` (thread `storage_path` from caller — do not reconstruct inline)
- `board_run.py:147, 247`
- `registry.py:148-149`

### RESERVED set change

In `studio/src/renderer/src/store/commsStore.ts` at `:140`:

```typescript
// Before
const RESERVED = new Set(['plans', '.archive'])

// After
const RESERVED = new Set([
  'plans', '.archive', 'goals', 'lessons',
  'explorations', 'debugs', 'pipeline-walkthrough'
])
```

This is a one-line → multi-line constant change. TypeScript must compile clean after the change.

### Test requirements

- `test_ensure_goal_slug_first_call` — generates correct slug from goal text
- `test_ensure_goal_slug_idempotent` — second call returns same slug
- `test_ensure_goal_slug_concurrent` — two threads calling simultaneously, one wins; no exception
- `test_project_goal_consultation_end_to_end` — drive ONE REAL consultation decompose for a project goal and confirm FSM advances past `PO_DISCUSSING` (no mocked FSM transitions; real state machine)
- `test_feature_regression` — feature run still creates `pathly/plans/<slug>/` (not `pathly/goals/`)
- `test_reserved_set` — sidebar does not list `goals` as a feature when `pathly/goals/<slug>/` exists

### Done criteria

- `pytest tests/test_goal_slug.py` passes.
- A real project-goal consultation decompose advances past `PO_DISCUSSING`.
- `pathly/goals/<slug>/PO_NOTES.md` exists after the run.
- Grep for `topic=scope` returns zero matches in supervisor source.
- No file in the supervisor package exceeds 400 lines.
- `commsStore.ts` RESERVED set contains all 7 entries.
- TypeScript compiles clean.
- Existing test suite passes: `pytest tests/ -q`.

### Builder notes

- Split `terminal.py` first. Do not touch any other file until the split passes tests.
- After the split, confirm `_agent_done_watcher` still uses `feature_dir.parent.parent.parent` — if this line is missing the watcher will target the wrong root.
- `goal_executor.py` (347 lines) and `board_run.py` (335 lines) are near the 400-line limit. Extract helpers before adding code.
- The slug is resolved BEFORE any FSM call. The call sites that receive `scope` must call `ensure_goal_slug` to get the slug and pass that instead.
- Import `ensure_goal_slug` from `supervisor/slug.py` (the new file). Do not define it inline at a call site.

---

## Phase 2 — Artifact Contract

**Fulfills stories:** S2.1, S2.2, S2.3, S2.4, S2.5
**Gates:** Phase 1 tests passing
**ATOMIC CONSTRAINT:** all 7 artifacts must land in ONE git commit

### Scope

Add the artifact contract infrastructure: manifest (single source of truth for role→file→gate),
the `artifact-register` fragment (instruction to agents), the `planning/dag-sketch` skill (light
planner with a real artifact), the `ensure_attached` reconciler in `comms_artifacts.py`, and the
wiring in `complete_stage` and the supervisor post-PTY path.

### The 7 artifacts that must land in ONE commit

1. `src/pathly_data/core/skills/artifact-manifest.yaml` (NEW)
2. `src/pathly_data/core/skills/fragments/artifact-register.md` (NEW)
3. `src/pathly_data/core/skills/planning/dag-sketch.md` (NEW)
4. `src/pathly_data/core/skills/composition.yaml` — new `planning/dag-sketch` entry + per-skill `artifact-register` attachments for pipeline roles only
5. `src/pathly_orchestrator/supervisor/goal_decomposer.py` — `_decompose_planner` edit: `skill="" → "planning/dag-sketch"`; delete "Do NOT create plan files" instruction
6. `src/pathly_orchestrator/db/queries/comms_artifacts.py` — add `ensure_attached`
7. 4-adapter sync output — produced by `pathly-setup claude --apply --repair` + `python -m build`; verify all four adapter output dirs are modified

Additionally in the same commit (supporting files, not the atomicity core):
- `src/pathly_orchestrator/http_server/blueprints/fsm.py` — thread optional `board`/`scope` into `/complete_stage` body (additive; absent → derive `board='feature', scope=topic`)
- `tests/test_compose.py` — regenerate snapshots
- `tests/test_artifact_reconcile.py` — new

### artifact-manifest.yaml shape

```yaml
# src/pathly_data/core/skills/artifact-manifest.yaml
roles:
  po:             { file: PO_NOTES.md,                 gate: '#' }
  architect:      { file: ARCHITECTURE_PROPOSAL.md,    gate: '## ' }
  web-researcher: { file: RESEARCH.md,                 gate: '## ' }
  designer:       { file: DESIGN.md,                   gate: '## Design System Output' }
  planner:        { file: IMPLEMENTATION_PLAN.md,      gate: '## Phase' }
  reviewer:       { file: feedback/REVIEW_FAILURES.md, gate: '#' }
  tester:         { file: feedback/TEST_FAILURES.md,   gate: '#' }
  retro:          { file: RETRO.md,                    gate: '#' }
  explorer:       { file: CONCLUSIONS.md,              gate: '#' }
overrides:
  planner.planning/dag-sketch: { file: DAG_PLAN.md, gate: '## Tasks' }
```

### composition.yaml rules

- Do NOT touch `defaults:` at `:24` (currently `[progress-logging]`). The manifest `roles:` map is the allow-list for `artifact-register`.
- Add one entry for `planning/dag-sketch` with `artifact-register` in its `fragments:` list.
- Attach `artifact-register` per-skill to: `planning/plan`, `planning/consult`, `building/build`, `reviewing/review`, `testing/test`, `retro/retro`, `exploring/explore`. Do NOT attach to `planning/po`, `planning/evaluate`, `planning/consolidate`.
- `planning/po` (`:119`) keeps its existing `comms-post` entry; do not change it.
- `planning/dag-sketch` entry must pass `validate_composition` (the skill file must exist when referenced).

### ensure_attached contract

```python
# db/queries/comms_artifacts.py  — add after existing insert_artifact()
def ensure_attached(conn, slug: str, board: str, scope: str,
                    artifact_path: str, role: str) -> bool:
    """Idempotent: insert comms_artifacts row keyed by (scope, artifact_path).
    Returns True if a new row was inserted, False if it already existed.
    Emits SSE artifact_attached on insert.
    Must be called inside the process-wide write-lock."""
    existing = conn.execute(
        "SELECT id FROM comms_artifacts WHERE scope = ? AND path = ?",
        (scope, artifact_path)
    ).fetchone()
    if existing:
        return False
    # insert + SSE emit (follow insert_artifact() pattern for id, created_at, etc.)
    ...
    return True
```

Key constraints:
- No DB UNIQUE constraint on `comms_artifacts` (by design — idempotency is application-level).
- `ensure_attached` must call `_get_write_lock()` at the call site, not internally, to compose
  with other write operations without deadlock.
- The reconciler resolves paths through the slug-aware resolver (same as FSM) — not raw topic.

### Fallback path (post-PTY, non-FSM modes)

When the supervisor's post-PTY handler fires (after a single-agent or light-DAG PTY exits):
1. Read `<storage_path>/ARTIFACTS.jsonl` line by line.
2. For each line: call `ensure_attached(slug, board, scope, line["path"], line["role"])`.
3. Fallback when JSONL absent: look up the run's role in `artifact-manifest.yaml`, `stat`
   `<storage_path>/<file>`, call `ensure_attached` if present.

### validate_composition build check

Add or extend `validate_composition` to assert: for every skill referenced in a `fragments:` list,
the skill file exists under `core/skills/`. A missing `planning/dag-sketch.md` with a composition
entry referencing it must cause `python -m build` to fail (not a silent no-op).

### Test requirements

- `test_ensure_attached_first_call` — inserts row, emits SSE, returns True
- `test_ensure_attached_idempotent` — second call returns False, row count unchanged
- `test_artifact_reconcile_jsonl_path` — supervisor post-PTY reads JSONL and calls ensure_attached
- `test_artifact_reconcile_stat_fallback` — JSONL absent, stat path, attach if present
- `test_dag_sketch_produces_dag_plan_md` — light planner writes `DAG_PLAN.md` with `## Tasks`
- `test_compose_snapshots` — regenerated `test_compose.py` snapshots pass

### Done criteria

- All 7 artifacts in one commit (verify with `git show --stat HEAD`).
- `pytest tests/test_artifact_reconcile.py` passes.
- `pytest tests/test_compose.py` passes with regenerated snapshots.
- After a light-mode decompose, `goals/<slug>/DAG_PLAN.md` exists with a `## Tasks` section.
- `ensure_attached` inserts exactly one row for duplicate calls.
- `python -m build` fails if `planning/dag-sketch` is referenced but the skill file is absent.
- Adapter sync completes: `pathly-setup claude --apply --repair` exits 0.

### Builder notes

- Phase 2 is the most risky phase for partial-deploy bugs. Do not start it without Phase 1 tests passing.
- Write the 7 files into a local branch, run `python -m build` to confirm the build gate, then commit all at once.
- Do not add `artifact-register` to `composition.yaml defaults:` — this would inject the fragment into `planning/po`, `planning/evaluate`, and `planning/consolidate`, which do not have manifest entries and should not write named artifacts.
- The `codex_subagent` field in the FSM contract must remain frozen — do not add fields to it.
- The `/complete_stage` change is additive: `board`/`scope` are optional; absent → derive `board='feature', scope=topic`. Existing callers that omit these fields must continue to work.

---

## Phase 3 — Sidebar

**Fulfills stories:** S3.1, S3.2, S3.3, S3.4
**Dependency:** Phase 1 (RESERVED set must be extended before `pathly/goals/` exists on disk)
**Renderer-only:** no Python changes

### Scope

Replace `FeatureSidebar` with `CardSidebar` behind a feature flag. Split the store's `cards`
slice from the `features` getter. Add `CardKind` types. Wire goal actions and lesson click.

### Files changed

| File | Change |
|---|---|
| `studio/src/renderer/src/types.ts` | Add `CardKind`, `Card` superset, keep `Feature = Card & {kind:'feature'}` |
| `studio/src/renderer/src/store/commsStore.ts` | `loadFeatures → loadCards`; `cards: Card[]` slice; `features` as derived getter (`cards.filter(c => c.kind === 'feature')`) |
| `studio/src/renderer/src/components/CommandCenter/CardSidebar/` | NEW folder: `CardSidebar.tsx` + `CardSidebar.module.css` |
| `studio/src/renderer/src/components/CommandCenter/CommandCenter.tsx` | Wire `CardSidebar` behind flag; keep `FeatureSidebar` as fallback |

### CardSidebar design contract (from DESIGN.md)

- `data-kind` attribute drives all per-kind CSS: color, dot, accent border.
- Section header: 11px/500 weight/all-caps label + `ChevronIcon`; `aria-expanded`.
- Item row: 32px height; 12px left padding; 16px icon; 8px gap.
- Active item: kind-color text + 2px left border; `aria-current="page"`.
- Empty groups: `hidden` (not rendered, not shown as "No items").
- Collapsed rail (48px): dot clusters (6px dots, gap 4px, up to 5 per group then `+N`).
- State preservation: collapse/expand state in `localStorage` per-kind key.
- Responsiveness: `min-width: 0` on flex children; no `overflow: hidden` on sidebar container.
- No WebGPU/WebLLM (Electron renderer constraint).

See DESIGN.md for the full component spec, CSS patterns, accessibility checklist, and color tokens.

### store shape migration

```typescript
// Before (causes erase bug)
set({ features: cards.filter(c => c.kind === 'feature') })

// After (correct)
// cards is the authoritative slice; features is a derived getter
get features() { return this.cards.filter(c => c.kind === 'feature') }
```

The `set({features})` pattern must not appear in the new store code.

### Feature flag

The flag is a boolean in the store or a localStorage key. When `false` (default): render
`FeatureSidebar` exactly as today. When `true`: render `CardSidebar`. The flag can be toggled
from the Command Center settings panel or via `localStorage`.

### Test requirements

- TypeScript compile: `tsc --noEmit` with `tsconfig.web.json` passes.
- `test_card_sidebar_renders_features` — features section renders with correct kind label.
- `test_card_sidebar_hides_empty_goals` — goals section absent when no goals exist.
- `test_card_sidebar_dot_cluster` — collapsed rail shows dot clusters for non-empty sections.
- `test_load_cards_derived_features` — `store.features` returns only `kind === 'feature'` cards.
- `test_feature_sidebar_fallback` — flag=false renders `FeatureSidebar`; existing props still accepted.

### Done criteria

- `CardSidebar` component exists and renders correctly for all four card kinds.
- Empty groups are not rendered.
- Collapsed rail shows dot clusters.
- `store.features` getter returns the correct subset.
- `FeatureSidebar` still mounts and compiles as a fallback.
- TypeScript compiles clean: `tsc --noEmit` with `tsconfig.web.json`.
- Goal cards show Decompose and Run buttons.
- Lesson card click opens the `.md` file in the MarkdownEditor panel.

### Builder notes

- Follow the one-component-one-folder rule: `CardSidebar/CardSidebar.tsx` + `CardSidebar.module.css`.
- Use CSS Modules or Tailwind (per DESIGN.md builder notes); do not use inline styles for kind-specific colors.
- The `data-kind` attribute is the CSS hook — no per-kind className overrides needed in JS.
- The sidebar container must use CSS Grid (`grid-template-columns`), not `position: fixed`.
- Do not make board POST a hard dependency of sidebar rendering — degrade gracefully if `/comms` is unreachable.
- Override any design token recommendation that conflicts with existing Studio tokens in `studio/src/renderer/src/styles/`.
