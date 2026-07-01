# Conversation Prompts — pathly-entity-model

_Last updated: 2026-06-29_

Each prompt below is self-contained. A builder can execute it without reading any other plan file.

---

## Conversation 0 — Guard: `_safe_topic` + slug column

**Stories:** S0.1, S0.2
**Phase:** Phase 0

### What to build

Add a fail-fast guard (`_safe_topic`) to the FSM and a nullable `slug` column + UNIQUE index to `comms_messages`. No behavioral change to working flows. The guard raises immediately on already-broken calls (absolute paths, empty strings, path separators).

### Context

The production bug (project-goal consultation looping forever) is caused by passing an absolute
path as the FSM topic. pathlib discards left operands when the right is absolute, collapsing the
storage path to the project root. The PO_NOTES gate never matches and the FSM loops forever.

The fix is a 4-phase plan. Phase 0 ships the guard and the DB column so the next phase can use
them. Phase 0 alone does not fix the bug — it makes the bug loud instead of silent.

### Files to touch

**`src/pathly_orchestrator/fsm_ops.py` — at line `:68` (top of `_resolve_storage_path`)**

Add `_safe_topic` function and call it at the very top of `_resolve_storage_path`:

```python
import os, re
from pathlib import Path

def _safe_topic(topic: str) -> str:
    """Raise ValueError if topic is not a bare slug.
    Called at the top of _resolve_storage_path and in argv._storage_path."""
    if (not topic or os.path.isabs(topic) or topic in (".", "..")
            or re.search(r'[\\/:]', topic) or '..' in Path(topic).parts):
        raise ValueError(
            f"unsafe FSM topic {topic!r}: must be a bare slug, not a path/scope")
    return topic

# At the top of _resolve_storage_path (line :68):
def _resolve_storage_path(root, topic, ...):
    topic = _safe_topic(topic)   # ADD THIS LINE
    ...
```

**`src/pathly_orchestrator/runner/argv.py` — at line `:13` inside `_storage_path`**

Add `_safe_topic` guard for defense-in-depth:

```python
from pathly_orchestrator.fsm_ops import _safe_topic

def _storage_path(root, topic):
    topic = _safe_topic(topic)   # ADD THIS LINE
    ...
```

**`src/pathly_orchestrator/db/migrations.py` — append to migrations**

Add idempotent migration for the `slug` column and UNIQUE index on `comms_messages`:

```python
# Pattern: try/except per ALTER TABLE, catch "duplicate column" OperationalError
try:
    conn.execute("ALTER TABLE comms_messages ADD COLUMN slug TEXT")
except OperationalError as e:
    if "duplicate column" not in str(e):
        raise

conn.execute(
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_comms_messages_slug "
    "ON comms_messages(slug) WHERE slug IS NOT NULL"
)
```

Follow the exact pattern used by the existing `migrations_incremental.py` idempotent columns.

**`tests/test_fsm_ops.py` — new or extend**

Write or extend with these test cases:

```python
from pathly_orchestrator.fsm_ops import _safe_topic
import pytest

def test_safe_topic_empty():
    with pytest.raises(ValueError):
        _safe_topic("")

def test_safe_topic_abs_windows():
    with pytest.raises(ValueError):
        _safe_topic("C:/Users/Yafit/pathly-adapters")

def test_safe_topic_abs_posix():
    with pytest.raises(ValueError):
        _safe_topic("/home/user/project")

def test_safe_topic_dotdot():
    with pytest.raises(ValueError):
        _safe_topic("..")

def test_safe_topic_slash():
    with pytest.raises(ValueError):
        _safe_topic("a/b")

def test_safe_topic_colon():
    with pytest.raises(ValueError):
        _safe_topic("a:b")

def test_safe_topic_valid():
    assert _safe_topic("my-feature-slug") == "my-feature-slug"

def test_slug_column_migration(tmp_db):
    # column exists
    cols = [row[1] for row in tmp_db.execute("PRAGMA table_info(comms_messages)")]
    assert "slug" in cols
    # duplicate slug raises
    tmp_db.execute("INSERT INTO comms_messages(id, board, type, slug) VALUES ('a','b','goal','dup-slug')")
    with pytest.raises(Exception):
        tmp_db.execute("INSERT INTO comms_messages(id, board, type, slug) VALUES ('b','b','goal','dup-slug')")
    # NULL slug is allowed
    tmp_db.execute("INSERT INTO comms_messages(id, board, type) VALUES ('c','b','goal')")
    tmp_db.commit()
```

### Acceptance test (run this before marking DONE)

```bash
cd C:\Users\Yafit\pathly-adapters
pytest tests/test_fsm_ops.py -v
pytest tests/ -q   # full regression — must pass
python -c "from pathly_orchestrator.fsm_ops import _safe_topic; _safe_topic('good-slug')"
python -c "from pathly_orchestrator.db.migrations import run_migrations; ..."
# Verify slug column via sqlite3
```

### Done when

- All 8 test cases in `test_fsm_ops.py` pass (7 `_safe_topic` + 1 `test_slug_column_migration`).
- `pytest tests/ -q` shows no new failures.
- `_safe_topic` is importable from `pathly_orchestrator.fsm_ops`.
- The `comms_messages.slug` column and UNIQUE index exist after migration.

---

## Conversation 1 — Bug Fix: slug routing + RESERVED set + terminal split

**Stories:** S1.1, S1.2, S1.3, S1.4, S1.5
**Phase:** Phase 1
**Prerequisite:** Conversation 0 merged and passing

### What to build

Fix the production bug where project-goal consultation loops forever on `PO_DISCUSSING`. The
fix has five parts: (A) split `terminal.py` to comply with the 400-line SOLID limit, (B) create
`supervisor/slug.py` with `ensure_goal_slug`, (C) route `topic=slug` at every collapse site,
(D) add the `goals/` probe to `_resolve_storage_path`, (E) extend the Studio RESERVED set.

**Execute in this order — do not skip steps or reorder.**

### Step A — Split terminal.py (do this FIRST, before any other change)

`src/pathly_orchestrator/supervisor/terminal.py` is 407 lines — over the 400-line SOLID limit.
Split it before adding new code:

1. Read `terminal.py` in full.
2. Identify extraction candidates: the summary-write helpers at `:39`, the path-reconstruction
   logic at `:269` and `:307`, and any shared utilities.
3. Create `supervisor/terminal_write.py` (or an appropriate name) and move the extracted helpers there.
4. Keep the following in `terminal.py` WITHOUT MODIFICATION:
   - Line `:86` the `_agent_done_watcher` function, specifically the line
     `project_root = feature_dir.parent.parent.parent` — this MUST be preserved verbatim.
   - PTY lifecycle functions.
5. After the split: `wc -l terminal.py terminal_write.py` — both must be under 400 lines.
6. Run `pytest tests/ -q` — must pass before proceeding to Step B.

### Step B — Create supervisor/slug.py

Create `src/pathly_orchestrator/supervisor/slug.py`:

```python
"""Stable slug identity for goal board messages."""
import re
from sqlite3 import OperationalError
# Import the process-wide write-lock — find _get_write_lock in the existing codebase
# (likely in db/_helpers.py or a similar module)

def ensure_goal_slug(conn, goal_id: str) -> str:
    """Return the stable slug for goal_id, creating it if absent.
    Idempotent: second call returns the same slug.
    Runs inside the process-wide write-lock. UNIQUE index is the DB-level backstop.
    The returned slug passes _safe_topic validation."""
    with _get_write_lock():
        row = conn.execute(
            "SELECT slug, text FROM comms_messages WHERE id = ?", (goal_id,)
        ).fetchone()
        if row and row["slug"]:
            return row["slug"]
        goal_text = (row["text"] if row else None) or goal_id
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

Verify: the returned slug passes `_safe_topic("my-goal-text-3f9a1c22")` — no path separators.

### Step C — Thread topic=slug at all collapse sites

For each site below: import `ensure_goal_slug` from `supervisor/slug.py` and replace
`topic=scope` with `topic=ensure_goal_slug(conn, goal_id)`. The `conn` and `goal_id` are
available at each call site — read the surrounding code to confirm the variable names.

Sites (all verified against working tree 2026-06-29):

| File | Line | What changes |
|---|---|---|
| `supervisor/goal_decomposer.py` | `:239` | reset call before consultation: `topic=scope` → `topic=slug` |
| `supervisor/goal_decomposer.py` | `:246` | `_decompose_consultation` `_start(topic=scope)` → `topic=slug` |
| `supervisor/goal_executor.py` | `:52` | `_reset_fsm_state_for_flow` resolver call |
| `supervisor/goal_executor.py` | `:223` | `_run_loop` `RunnerState(topic=scope, …)` |
| `supervisor/goal_executor.py` | `:317` | `_run_team` reset call |
| `supervisor/goal_executor.py` | `:321` | `_run_team` `_start(topic=scope)` |
| `supervisor/orchestrator.py` | `:336` | topic= in RunnerState |
| `supervisor/terminal.py` / `terminal_write.py` | `:39, :269, :307` | thread `storage_path` from the caller; do not reconstruct the path inline |
| `supervisor/board_run.py` | `:147` | add `slug` parameter to `start_board_run` signature |
| `supervisor/board_run.py` | `:247` | extend `where_line` probe: currently `board=='feature'` only; add `goals/<slug>/` branch for all tiers |
| `supervisor/registry.py` | `:148-149` | `feature_dir` construction: use slug, not scope |

For `goal_executor.py` (347 lines) and `board_run.py` (335 lines): if adding these changes
pushes either file over 400 lines, extract helpers into `supervisor/_helpers.py` first.

After all changes: grep the supervisor package for `topic=scope` and `topic = scope`
(case-insensitive, excluding comments). The result must be zero.

### Step D — Add goals/ probe to _resolve_storage_path

In `src/pathly_orchestrator/fsm_ops.py` at `:68-74` (the existing two-probe logic), add a
`goals/<slug>` probe as a second option alongside `plans/<slug>`:

```python
def _resolve_storage_path(root, topic, ...):
    topic = _safe_topic(topic)   # from Phase 0 — already present
    # Probe 1: plans/<slug>/ (features — existing behavior, unchanged)
    plans_path = Path(root) / "pathly" / "plans" / topic
    if plans_path.exists():
        return plans_path
    # Probe 2: goals/<slug>/ (NEW — project/global goals)
    goals_path = Path(root) / "pathly" / "goals" / topic
    if goals_path.exists():
        return goals_path
    # Probe 3: template fallback (existing behavior)
    ...
```

Watcher depth invariant check: `pathly/goals/<slug>/` has exactly two components under `pathly`.
`feature_dir.parent.parent.parent` still resolves to the project root. Do not add sub-paths.

### Step E — Extend Studio RESERVED set

In `studio/src/renderer/src/store/commsStore.ts` at line `:140`:

```typescript
// Replace:
const RESERVED = new Set(['plans', '.archive'])

// With:
const RESERVED = new Set([
  'plans', '.archive', 'goals', 'lessons',
  'explorations', 'debugs', 'pipeline-walkthrough'
])
```

Then run: `cd studio && npx tsc --noEmit --project tsconfig.web.json` — must compile clean.

### Tests to write

Create `tests/test_goal_slug.py`:

```python
import threading
from pathly_orchestrator.supervisor.slug import ensure_goal_slug

def test_ensure_goal_slug_first_call(conn_with_goal):
    slug = ensure_goal_slug(conn_with_goal, "goal-id-123")
    assert slug.endswith("-goal-id1")   # last 8 chars of goal_id
    assert "/" not in slug
    assert "\\" not in slug

def test_ensure_goal_slug_idempotent(conn_with_goal):
    slug1 = ensure_goal_slug(conn_with_goal, "goal-id-123")
    slug2 = ensure_goal_slug(conn_with_goal, "goal-id-123")
    assert slug1 == slug2

def test_ensure_goal_slug_concurrent(conn_with_goal):
    results = []
    errors = []
    def call():
        try:
            results.append(ensure_goal_slug(conn_with_goal, "goal-id-456"))
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=call) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert not errors
    assert len(set(results)) == 1   # all threads got the same slug

def test_project_goal_consultation_end_to_end():
    # Drive a real consultation decompose for a project goal.
    # Use the actual FSM (not mocked transitions).
    # Verify FSM advances past PO_DISCUSSING.
    # Verify pathly/goals/<slug>/PO_NOTES.md exists.
    ...  # implement using the existing integration test harness
```

### Acceptance test (run before marking DONE)

```bash
cd C:\Users\Yafit\pathly-adapters
pytest tests/test_goal_slug.py -v
pytest tests/ -q   # no regressions
# Grep check — must return zero results:
grep -rn "topic=scope\|topic = scope" src/pathly_orchestrator/supervisor/ --include="*.py" | grep -v "#"
# Line count check — no file over 400 lines:
wc -l src/pathly_orchestrator/supervisor/*.py | grep -v total
# TypeScript check:
cd studio && npx tsc --noEmit --project tsconfig.web.json
```

Then run one real project-goal consultation decompose and confirm:
- FSM advances past `PO_DISCUSSING`.
- `pathly/goals/<slug>/PO_NOTES.md` exists (not at the project root).
- No `ValueError` from `_safe_topic`.

### Done when

- `pytest tests/test_goal_slug.py` passes (all 4 test cases).
- `pytest tests/ -q` — no regressions.
- Zero matches for `topic=scope` in supervisor source.
- No supervisor file over 400 lines.
- `pathly/goals/<slug>/PO_NOTES.md` written by a real consultation run.
- Studio RESERVED set has 7 entries; TypeScript compiles clean.

---

## Conversation 2 — Artifact Contract (ATOMIC: one commit, exactly 7 artifacts)

**Stories:** S2.1, S2.2, S2.3, S2.4, S2.5
**Phase:** Phase 2
**Prerequisite:** Conversation 1 merged and all its tests passing

### CRITICAL: this conversation must produce exactly ONE git commit

Do not commit incrementally during this conversation. Prepare all files locally, verify them,
then stage and commit all at once. A partial deploy makes the planner call `planning/dag-sketch`
before the skill file exists, which is a runtime error.

### The 7 artifacts (all must be in the single commit)

1. `src/pathly_data/core/skills/artifact-manifest.yaml` (NEW)
2. `src/pathly_data/core/skills/fragments/artifact-register.md` (NEW)
3. `src/pathly_data/core/skills/planning/dag-sketch.md` (NEW)
4. `src/pathly_data/core/skills/composition.yaml` (modified — new entry + per-skill attachments)
5. `src/pathly_orchestrator/supervisor/goal_decomposer.py` (modified — `_decompose_planner` edit)
6. `src/pathly_orchestrator/db/queries/comms_artifacts.py` (modified — add `ensure_attached`)
7. 4-adapter sync output from `pathly-setup claude --apply --repair` + `python -m build`

Also in the same commit (supporting — not atomicity core):
- `src/pathly_orchestrator/http_server/blueprints/fsm.py` — thread `board`/`scope` into `/complete_stage`
- `tests/test_compose.py` — regenerated snapshots
- `tests/test_artifact_reconcile.py` (NEW)

### Artifact 1: artifact-manifest.yaml

Create `src/pathly_data/core/skills/artifact-manifest.yaml`:

```yaml
# Single source of truth for role→artifact→gate.
# Read by: skill composer (composition.yaml attachment) AND FSM gates.
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

### Artifact 2: fragments/artifact-register.md

Create `src/pathly_data/core/skills/fragments/artifact-register.md`:

The fragment body must instruct the agent to:
1. Write the named artifact to the injected `<out_path>` variable (not agent-chosen).
2. Append exactly one JSON line to `<feature_path>/ARTIFACTS.jsonl` with keys:
   `{role, path, type, title, summary, ts}` where `ts` is an ISO timestamp.
3. Attempt an advisory board POST to `/comms/messages` (skip if unreachable — do not let
   board unavailability block the artifact write).

The fragment must NOT make the board POST blocking or mandatory.

### Artifact 3: planning/dag-sketch.md

Create `src/pathly_data/core/skills/planning/dag-sketch.md`:

The skill body must instruct the agent to:
1. Decompose the goal into 3–7 tasks.
2. Write `DAG_PLAN.md` with a `## Tasks` table (columns: task name, description, dependencies,
   estimated effort).
3. Post each task to the board via the fragment.

The skill must be role-agnostic (works for planner role in light decompose mode). It receives
`<out_path>` from the composition layer.

### Artifact 4: composition.yaml changes

In `src/pathly_data/core/skills/composition.yaml`:

Rules:
- Do NOT modify `defaults:` at line `:24`. It currently contains `[progress-logging]` only.
- Do NOT modify `planning/po` at line `:119`. It keeps its existing `comms-post`.
- Add a new entry for `planning/dag-sketch` with `artifact-register` in its `fragments:` list.
- Attach `artifact-register` to these pipeline skills (per-skill, not in defaults):
  `planning/plan`, `planning/consult`, `building/build`, `reviewing/review`,
  `testing/test`, `retro/retro`, `exploring/explore`.
- Do NOT attach to: `planning/po`, `planning/evaluate`, `planning/consolidate`.

### Artifact 5: goal_decomposer.py — _decompose_planner edit

In `src/pathly_orchestrator/supervisor/goal_decomposer.py`:

At `:113-135` — find the `_decompose_planner` function body:
- Remove the line containing "Do NOT create plan files" (or any equivalent instruction).
- At `:142` — change `skill=""` to `skill="planning/dag-sketch"`.

No other changes to `goal_decomposer.py` in this conversation (Conversation 1 already did the
slug-routing changes).

### Artifact 6: comms_artifacts.py — ensure_attached

In `src/pathly_orchestrator/db/queries/comms_artifacts.py`, add after `insert_artifact()`:

```python
def ensure_attached(conn, slug: str, board: str, scope: str,
                    artifact_path: str, role: str) -> bool:
    """Idempotent: insert comms_artifacts row keyed by (scope, artifact_path).
    Returns True if a new row was inserted, False if already existed.
    Emits SSE artifact_attached on first insert.
    Call this inside the process-wide write-lock at the call site."""
    existing = conn.execute(
        "SELECT id FROM comms_artifacts WHERE scope = ? AND path = ?",
        (scope, artifact_path)
    ).fetchone()
    if existing:
        return False
    artifact_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    conn.execute(
        """INSERT INTO comms_artifacts
           (id, scope, path, role, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (artifact_id, scope, artifact_path, role, now)
    )
    conn.commit()
    # Emit SSE artifact_attached — follow the existing SSE pattern in the codebase
    _emit_sse("artifact_attached", {"id": artifact_id, "scope": scope, "path": artifact_path})
    return True
```

Note: no DB UNIQUE constraint on `comms_artifacts` — idempotency is application-level
(check-before-insert, mirroring the existing `insert_artifact()` pattern from the Scout findings).

### Artifact 7: adapter sync

Run:
```bash
pathly-setup claude --apply --repair
python -m build
```

Both must exit 0. The build step runs `validate_composition` which must fail if
`planning/dag-sketch` is referenced in `composition.yaml` but the skill file is absent.
Include all modified adapter output files in the commit.

### /complete_stage wiring

In `src/pathly_orchestrator/http_server/blueprints/fsm.py`, make `/complete_stage` accept
optional `board` and `scope` fields in the request body:

```python
board = request.json.get("board", "feature")
scope = request.json.get("scope", topic)   # absent → derive feature default
```

Then: when the FSM gate detects the artifact file first appearing (`stat` succeeds), call:
```python
ensure_attached(conn, slug, board, scope, artifact_path, role)
```

This is additive. Existing callers that omit `board`/`scope` get the feature defaults.
`codex_subagent` stays frozen — do not add fields to it.

### Post-PTY reconciler wiring

In the supervisor's post-PTY handler (after a PTY exits): read `<storage_path>/ARTIFACTS.jsonl`
line by line; for each line call `ensure_attached`. Fallback when JSONL absent: look up the
run's role in `artifact-manifest.yaml`, stat `<storage_path>/<file>`, call `ensure_attached`
if the file is present.

### Tests to write

**`tests/test_artifact_reconcile.py`** (NEW):

```python
def test_ensure_attached_first_call(tmp_db):
    inserted = ensure_attached(tmp_db, "my-slug", "feature", "my-slug",
                               "IMPLEMENTATION_PLAN.md", "planner")
    assert inserted is True
    row = tmp_db.execute(
        "SELECT id FROM comms_artifacts WHERE scope = ? AND path = ?",
        ("my-slug", "IMPLEMENTATION_PLAN.md")
    ).fetchone()
    assert row is not None

def test_ensure_attached_idempotent(tmp_db):
    ensure_attached(tmp_db, "my-slug", "feature", "my-slug",
                    "IMPLEMENTATION_PLAN.md", "planner")
    inserted_again = ensure_attached(tmp_db, "my-slug", "feature", "my-slug",
                                     "IMPLEMENTATION_PLAN.md", "planner")
    assert inserted_again is False
    count = tmp_db.execute(
        "SELECT COUNT(*) FROM comms_artifacts WHERE scope = ? AND path = ?",
        ("my-slug", "IMPLEMENTATION_PLAN.md")
    ).fetchone()[0]
    assert count == 1

def test_artifact_reconcile_jsonl_path(tmp_storage_dir):
    # Write ARTIFACTS.jsonl then call post-PTY reconciler
    jsonl = tmp_storage_dir / "ARTIFACTS.jsonl"
    jsonl.write_text('{"role":"planner","path":"IMPLEMENTATION_PLAN.md","type":"plan","title":"Plan","summary":"s","ts":"2026-06-29T00:00:00"}\n')
    reconcile_post_pty(tmp_storage_dir, slug="test-slug", board="feature", scope="test-slug")
    # Verify ensure_attached was called
    ...

def test_artifact_reconcile_stat_fallback(tmp_storage_dir, tmp_db):
    # JSONL absent; file exists; fallback should attach it
    (tmp_storage_dir / "IMPLEMENTATION_PLAN.md").write_text("## Phase\n...")
    reconcile_post_pty(tmp_storage_dir, slug="test-slug", board="feature",
                       scope="test-slug", role="planner", db=tmp_db)
    count = tmp_db.execute(
        "SELECT COUNT(*) FROM comms_artifacts WHERE path = ?",
        ("IMPLEMENTATION_PLAN.md",)
    ).fetchone()[0]
    assert count == 1

def test_dag_sketch_produces_dag_plan_md(tmp_storage_dir):
    # Light planner run produces DAG_PLAN.md with ## Tasks
    # Use an integration fixture that calls _decompose_planner
    ...
```

**`tests/test_compose.py`**: regenerate snapshots after composition.yaml changes.

### Pre-commit checklist

Before staging the commit, verify:
- [ ] `artifact-manifest.yaml` exists and contains all 9 roles + override
- [ ] `artifact-register.md` exists and instructs write + JSONL append + advisory POST
- [ ] `dag-sketch.md` exists and instructs 3-7 task decompose + `## Tasks` table
- [ ] `composition.yaml` has `planning/dag-sketch` entry with `artifact-register`
- [ ] `composition.yaml` `defaults:` at `:24` is UNCHANGED
- [ ] `planning/po` at `:119` is UNCHANGED
- [ ] `goal_decomposer.py` `_decompose_planner` has `skill="planning/dag-sketch"`, no "Do NOT create plan files"
- [ ] `ensure_attached` added to `comms_artifacts.py`
- [ ] `pathly-setup claude --apply --repair` completed without error
- [ ] `python -m build` passes (and would fail with dag-sketch.md absent — verify by temporarily renaming it)
- [ ] `pytest tests/test_compose.py -v` passes with regenerated snapshots
- [ ] `pytest tests/test_artifact_reconcile.py -v` passes
- [ ] `git diff --staged` shows all 7+ files

### Acceptance test (run before marking DONE)

```bash
cd C:\Users\Yafit\pathly-adapters
pytest tests/test_artifact_reconcile.py -v
pytest tests/test_compose.py -v
pytest tests/ -q   # no regressions
# Verify one-commit landing:
git log --oneline -1
git show --stat HEAD
```

### Done when

- All tests pass.
- `git show --stat HEAD` shows all 7 core artifacts in one commit.
- `python -m build` succeeds on the committed state.
- A light-mode decompose writes `pathly/goals/<slug>/DAG_PLAN.md` with a `## Tasks` section.
- `ensure_attached` inserts exactly one row for duplicate calls (idempotent).

---

## Conversation 3 — Sidebar: CardSidebar + loadCards store split

**Stories:** S3.1, S3.2, S3.3, S3.4
**Phase:** Phase 3
**Prerequisite:** Conversation 1 merged (RESERVED set must be extended before goals/ exists on disk)
**Renderer-only:** no Python changes

### What to build

Replace `FeatureSidebar` with a grouped `CardSidebar` that shows Features, Goals, Lessons, and
Explorations as collapsible sections. Split the store's `cards` slice from a derived `features`
getter. Add `CardKind` types. Gate `CardSidebar` behind a flag with `FeatureSidebar` fallback.

### Step 1 — types.ts

In `studio/src/renderer/src/types.ts`:

Add:
```typescript
export type CardKind = 'feature' | 'goal' | 'lesson' | 'exploration'

export interface Card {
  id: string
  slug: string
  kind: CardKind
  stage?: string       // features and goals
  label: string        // display name
  last: string         // ISO timestamp
  // extend with kind-specific optional fields as needed
}

// Keep Feature as a subtype for backward compatibility
export type Feature = Card & { kind: 'feature' }
```

Verify: existing `FeatureSidebar` props that use `Feature` still compile (Feature is a subtype of Card).

### Step 2 — commsStore.ts

In `studio/src/renderer/src/store/commsStore.ts`:

Replace `features: Feature[]` with `cards: Card[]`. Add a derived `features` getter:

```typescript
// Store state
cards: [] as Card[],

// Derived getter (not a top-level key — avoids the set({features}) erase bug)
get features(): Feature[] {
  return this.cards.filter((c): c is Feature => c.kind === 'feature')
},

// Rename loadFeatures → loadCards
async loadCards(projectPath: string): Promise<void> {
  // ... existing logic that was in loadFeatures ...
  // Now reads all card kinds from pathly/<domain>/<slug>/
  set({ cards: allCards })   // set cards, not features
},
```

The `set({features})` pattern must NOT appear anywhere in the store after this change.
Update any call sites that call `loadFeatures(...)` to call `loadCards(...)`.
Verify all components that read `store.features` still compile (the getter returns Feature[]).

### Step 3 — CardSidebar component

Create folder: `studio/src/renderer/src/components/CommandCenter/CardSidebar/`

Create `CardSidebar.tsx`:

```tsx
import React, { useState, useEffect } from 'react'
import styles from './CardSidebar.module.css'
import type { Card, CardKind } from '../../types'

interface Section {
  kind: CardKind
  label: string
  items: Card[]
}

interface CardSidebarProps {
  cards: Card[]
  activeId?: string
  collapsed: boolean
  onSelect: (card: Card) => void
  onDecompose?: (card: Card) => void
  onRun?: (card: Card) => void
}

const KIND_LABELS: Record<CardKind, string> = {
  feature: 'Features',
  goal: 'Goals',
  lesson: 'Lessons',
  exploration: 'Explorations',
}

const KIND_ORDER: CardKind[] = ['feature', 'goal', 'lesson', 'exploration']

export function CardSidebar({ cards, activeId, collapsed, onSelect, onDecompose, onRun }: CardSidebarProps) {
  const [openSections, setOpenSections] = useState<Record<CardKind, boolean>>(() => {
    // Restore from localStorage per-kind
    ...
  })

  const sections: Section[] = KIND_ORDER
    .map(kind => ({ kind, label: KIND_LABELS[kind], items: cards.filter(c => c.kind === kind) }))
    .filter(s => s.items.length > 0)   // empty groups hidden

  return (
    <nav className={styles.rail} data-collapsed={collapsed}>
      {sections.map(section => (
        <section key={section.kind} className={styles.group} data-kind={section.kind}>
          <button
            className={styles.groupHeader}
            aria-expanded={openSections[section.kind]}
            onClick={() => toggleSection(section.kind)}
          >
            {/* KindIcon, label (hidden when collapsed), ChevronIcon */}
          </button>
          {collapsed
            ? <DotCluster items={section.items} activeId={activeId} kind={section.kind} />
            : (
              <ul role="list" hidden={!openSections[section.kind]}>
                {section.items.map(item => (
                  <li key={item.slug}>
                    <a
                      className={item.id === activeId ? `${styles.item} ${styles.active}` : styles.item}
                      aria-current={item.id === activeId ? 'page' : undefined}
                      onClick={() => onSelect(item)}
                    >
                      {item.label}
                    </a>
                    {item.kind === 'goal' && (
                      <>
                        <button onClick={() => onDecompose?.(item)} disabled={!onDecompose}>Decompose</button>
                        <button onClick={() => onRun?.(item)} disabled={!onRun}>Run</button>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            )
          }
        </section>
      ))}
    </nav>
  )
}
```

Create `CardSidebar.module.css` with the design tokens from DESIGN.md:
- CSS variables for all color tokens (`--color-sidebar-bg`, `--color-kind-feature`, etc.)
- `[data-kind="feature"] .item.active { color: var(--color-kind-feature); border-left: 2px solid var(--color-kind-feature); }`
- Dot cluster styles for collapsed rail
- `min-width: 0` on flex children; NO `overflow: hidden` on `.rail`
- Rail width: 220px expanded, 48px collapsed
- Override any token that conflicts with existing Studio styles in `studio/src/renderer/src/styles/`

### Step 4 — Wire into CommandCenter.tsx

In `studio/src/renderer/src/components/CommandCenter/CommandCenter.tsx`:

Add a feature flag (read from `localStorage.getItem('pathly_card_sidebar')` === `'true'`):

```tsx
const useCardSidebar = localStorage.getItem('pathly_card_sidebar') === 'true'

// In render:
{useCardSidebar
  ? <CardSidebar cards={store.cards} ... />
  : <FeatureSidebar features={store.features} ... />
}
```

Keep all existing `FeatureSidebar` props unchanged. The fallback must compile and work.

### Step 5 — Lesson click → MarkdownEditor

When a user clicks a lesson card, open its `.md` file in the MarkdownEditor panel. Find the
existing IPC or store action that opens files in MarkdownEditor (likely `mdEditorOpen` or similar
based on the MD Editor naming notes) and call it with the lesson file path.

### Acceptance test (run before marking DONE)

```bash
cd C:\Users\Yafit\pathly-adapters\studio
npx tsc --noEmit --project tsconfig.web.json   # must produce zero errors
```

Visual check (run studio in dev mode):
- With `pathly/goals/<slug>/` on disk: sidebar shows a Goals section with the slug as a card.
- With no goals: Goals section is absent.
- Goals section shows Decompose and Run buttons.
- Clicking a lesson card opens the `.md` in the MarkdownEditor panel.
- Collapsed rail shows dot clusters for each non-empty section.
- `localStorage.getItem('pathly_card_sidebar')` set to `'false'` renders `FeatureSidebar`.

### Done when

- TypeScript compiles clean: `tsc --noEmit --project tsconfig.web.json` zero errors.
- `CardSidebar` component exists in its own folder with a CSS module.
- `store.features` returns only `kind === 'feature'` cards.
- `loadCards` replaces `loadFeatures`; no `set({features})` pattern in the store.
- Goal cards show Decompose and Run buttons.
- Lesson click opens MarkdownEditor.
- Empty groups not rendered.
- `FeatureSidebar` still mounts and compiles as a fallback when flag is false.
