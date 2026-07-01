# Edge Cases — pathly-entity-model

_Last updated: 2026-06-29_

---

## 1. Guard edge cases — `_safe_topic`

Each row is a distinct test case. All "raises" cases must raise `ValueError` with a message
that includes the literal input value.

| Input | Expected | Reason |
|---|---|---|
| `""` | raises `ValueError` | empty string: `not topic` branch |
| `"C:/Users/Yafit/pathly-adapters"` | raises `ValueError` | absolute Windows path: `os.path.isabs` fires |
| `"/home/user/project"` | raises `ValueError` | absolute POSIX path: `os.path.isabs` fires |
| `"."` | raises `ValueError` | single-dot: `topic in (".", "..")` branch |
| `".."` | raises `ValueError` | double-dot: `topic in (".", "..")` branch |
| `"a/b"` | raises `ValueError` | forward slash: `re.search(r'[\\/:]')` fires |
| `"a\\b"` | raises `ValueError` | backslash: same regex |
| `"a:b"` | raises `ValueError` | colon (drive-letter fragment): same regex |
| `"a/../b"` | raises `ValueError` | `..` in `Path(topic).parts` |
| `"./relative"` | raises `ValueError` | `.` in `Path(topic).parts` |
| `"my-feature-slug"` | returns `"my-feature-slug"` | valid: no separators, not absolute, not dot |
| `"my-feature-2"` | returns `"my-feature-2"` | valid: numeric suffix is fine |
| `"goal-fix-loop-3f9a1c22"` | returns `"goal-fix-loop-3f9a1c22"` | valid: hex suffix, no separator |

**Cases that must NOT raise (common false-positive risk):**

- A slug that starts with a digit: `"2026-plan"` — valid; `os.path.isabs` is False on Windows
  for strings that begin with a digit; the regex does not match.
- A slug with a numeric-only suffix separated by `-`: `"my-feature-123"` — valid.
- A slug that starts with a letter followed by `-`: `"a-b-c"` — valid; the regex `[\\/:]`
  does not match `-`.

**Slug starting with `-`:**
A slug like `"-bad-slug"` passes `_safe_topic` (no separators, not absolute, not dot). It is
not a guard violation. However `_slugify` in `slug.py` strips leading `-` via `.strip('-')`,
so `ensure_goal_slug` will never produce such a slug in practice. If a caller constructs one
manually and passes it, the guard accepts it. This is acceptable — the guard's job is to
reject paths, not to enforce naming aesthetics.

---

## 2. `ensure_goal_slug` — concurrency

**Scenario:** Two threads (or processes sharing the same DB via WAL) call
`ensure_goal_slug(conn, goal_id)` simultaneously for the same `goal_id`, with no slug stored
yet.

**What must happen:**
1. Both threads enter the function.
2. One acquires the process-wide write-lock first and performs the check-then-write.
3. It finds no existing slug, generates one, writes it, and commits.
4. It releases the lock. The second thread acquires the lock.
5. The second thread performs the check again (inside the lock): the slug now exists.
6. It returns the already-stored slug without attempting a write.

**Result:** Both callers receive the identical slug string. No `IntegrityError` surfaces.

**DB-level backstop:** The `UNIQUE` index on `comms_messages.slug` (`WHERE slug IS NOT NULL`)
is the second line of defense. If two processes (not sharing the same write-lock) race:
- One `UPDATE` wins and commits.
- The other `UPDATE` targets the same row and would set the slug to a different value — but
  since `UPDATE` does not touch the UNIQUE index directly (the index is on the column value),
  the UNIQUE constraint does not fire here. However, the check-before-write inside the lock
  prevents the second process from overwriting a value.

**Cross-process note:** The write-lock is process-wide (`_get_write_lock`). Two separate OS
processes (e.g., supervisor + a test runner) do not share the same lock. SQLite's WAL mode
serializes writes at the DB level, so the second process will either read the slug already
written (and skip) or write a different (but equally valid) slug for the same row and trigger
a UNIQUE violation. The UNIQUE index then surfaces as an `IntegrityError` to the second
process. The caller (in `goal_decomposer.py`) must wrap `ensure_goal_slug` in a try/except
for `IntegrityError` and, on catch, re-read the slug from the DB. The test must cover this
cross-process case.

---

## 3. Migration idempotency

**Scenario A — slug column already present (re-running on an existing DB):**
- `ALTER TABLE comms_messages ADD COLUMN slug TEXT` → SQLite raises `OperationalError:
  duplicate column name: slug`.
- The migration wrapper catches `OperationalError` where `"duplicate column"` appears in the
  message and silently passes. The migration continues to the next statement.
- Verified: `pytest tests/test_fsm_ops.py::test_slug_column_migration` runs twice; second run
  does not raise.

**Scenario B — UNIQUE index already present:**
- `CREATE UNIQUE INDEX IF NOT EXISTS idx_comms_messages_slug ON comms_messages(slug) WHERE slug IS NOT NULL`
- `IF NOT EXISTS` is a native SQLite guard. No error is raised. Idempotent by definition.

**Scenario C — startup runs migrations on every boot:**
- The orchestrator HTTP server runs migrations at startup. Every cold boot executes both the
  `ALTER TABLE` and `CREATE UNIQUE INDEX IF NOT EXISTS`. Scenario A and B above apply on every
  restart after the first deploy. Confirmed safe.

**Scenario D — empty DB (first install):**
- Neither the column nor the index exists. Both statements execute cleanly. Column is nullable
  (`NULL` default); existing rows (if any, from a prior `comms_messages` table) get `slug=NULL`.
  No existing row is broken.

---

## 4. `ensure_attached` idempotency

**No DB-level UNIQUE constraint** exists on `comms_artifacts`. Idempotency is application-level.

**Scenario — called twice for the same `(scope, artifact_path)`:**
1. First call: `SELECT id FROM comms_artifacts WHERE scope = ? AND path = ?` returns no row.
   → Insert proceeds. SSE `artifact_attached` fires. Returns `True`.
2. Second call: same SELECT now returns the row from step 1.
   → Insert is skipped. No SSE event. Returns `False`.
3. Row count after both calls: exactly 1.

**Scenario — called with `scope` and `artifact_path` that differ only in path separator
style** (Windows `\` vs POSIX `/`):
- The `artifact_path` stored in step 1 is whatever string the caller passed.
- Step 2 must normalize `artifact_path` the same way before the SELECT. If the caller
  normalizes to forward-slash (POSIX style) on both calls, the match is clean.
- Risk: if one call passes `feedback/REVIEW_FAILURES.md` and another passes
  `feedback\\REVIEW_FAILURES.md`, they will not match. The reconciler must normalize to
  forward-slash before calling `ensure_attached`. This is a call-site responsibility, not
  enforced inside `ensure_attached`.

**Scenario — concurrent calls from two threads:**
- Both threads read "no existing row" before either inserts. Both proceed to insert.
- Result: two rows for the same `(scope, artifact_path)`. This is an idempotency violation.
- Mitigation: `ensure_attached` must be called inside the process-wide write-lock at the
  call site (per the contract in IMPLEMENTATION_PLAN.md). The lock serializes concurrent
  calls within a process.
- Cross-process: no protection. Acceptable because `ensure_attached` rows are idempotent in
  effect (both rows represent the same artifact); the board read-path deduplicates by
  `(scope, path)` at query time.

---

## 5. `terminal.py` split

**Invariant that must survive the split:**

The `_agent_done_watcher` function at `terminal.py:86` contains:
```python
project_root = feature_dir.parent.parent.parent
```
This computation is correct only when `feature_dir` is exactly `<root>/pathly/<domain>/<slug>`.
It must stay in whichever file has `feature_dir` in scope. If the watcher is moved to a
helper that receives `project_root` as a parameter instead, the `parent.parent.parent` line
must be computed by the caller before passing.

**Import breakage risk:**
Any file that imports a symbol from `terminal.py` will break if that symbol moves to
`terminal_write.py` (or equivalent) without a re-export. Mitigation:
- After the split, add `from supervisor.terminal_write import <symbols>` to `terminal.py`
  so existing `from supervisor.terminal import X` imports continue to resolve.
- Alternatively, update all import sites explicitly. The test suite is the verification.

**Specific symbols at risk:**
- `_write_supervisor_phase_summary` (`:39`) — used by callers in `goal_executor.py` and
  `board_run.py`. If it moves, update those import sites or re-export.
- `_agent_done_watcher` (`:86`) — must stay in the file that owns `feature_dir`.

---

## 6. Phase 2 atomic commit — missing artifact scenarios

The 7-artifact atomic constraint exists to prevent a partial-deploy runtime error. What breaks
if each artifact is absent independently:

| Missing artifact | Immediate failure mode |
|---|---|
| `planning/dag-sketch.md` | `_decompose_planner` calls `skill="planning/dag-sketch"` → composer raises `SkillNotFound` (or equivalent) → goal decompose fails at runtime with no useful error to the user |
| `composition.yaml` entry for `planning/dag-sketch` | Skill file exists but is never composed into the agent prompt → agent receives no DAG-sketch instructions → no `DAG_PLAN.md` is written → `artifact_attached` never fires for that goal |
| `artifact-register.md` | Fragment missing → per-skill `fragments: [artifact-register]` entries in `composition.yaml` silently no-op (file not found) OR raise at composition time — depends on how the composer handles missing fragments |
| `artifact-manifest.yaml` | FSM gate and reconciler cannot load the manifest → both fall back to hardcoded defaults or raise `FileNotFoundError` at startup |
| `_decompose_planner` edit (still passes `skill=""`) | Even if `planning/dag-sketch.md` exists, `skill=""` means no skill is composed → agent still receives "Do NOT create plan files" instruction → `DAG_PLAN.md` never written |
| `comms_artifacts.ensure_attached` | `complete_stage` and the post-PTY reconciler cannot call it → artifacts are never inserted → board has no `comms_artifacts` rows even when files exist |
| 4-adapter sync output stale | Installed skill/fragment files are the old version → running agents receive the pre-Phase-2 prompts → `artifact-register` instructions never reach the agent |

**Build gate:** `validate_composition` must catch the `dag-sketch.md` absent case at build
time (`python -m build`), not at runtime. This covers the single most dangerous case.

---

## 7. Watcher depth invariant

**The invariant:** every storage path must be `pathly/<domain>/<slug>/` — exactly two
components under `pathly`.

**What breaks with a 3-component path** such as `pathly/goals/sub/slug/`:

```
feature_dir = <root>/pathly/goals/sub/slug

feature_dir.parent          → <root>/pathly/goals/sub
feature_dir.parent.parent   → <root>/pathly/goals
feature_dir.parent.parent.parent  → <root>/pathly   ← WRONG (expected <root>)
```

`project_root` points at `<root>/pathly` instead of `<root>`. Any path construction using
`project_root / "pathly" / ...` then produces `<root>/pathly/pathly/...` — a non-existent
directory. File writes go to the wrong location silently.

**How this could be introduced accidentally:**
- A goal whose `goal_text` slugifies to something containing a `/` (prevented by `_slugify`).
- A future nested-goal feature that creates `pathly/goals/<parent-slug>/<child-slug>/`.
- A manual `mkdir` call that creates an extra subdirectory level.

**Enforcement:** `_safe_topic` already rejects slugs containing `/`. The `ensure_goal_slug`
function uses `_slugify` which strips separators. The risk is in manual or future-code paths
that bypass both guards.

---

## 8. Phantom feature regression

**Scenario:** `pathly/goals/` directory exists on disk (created by Phase 1), but the Studio
RESERVED set is still `{'plans', '.archive'}` (the pre-Phase-1 value).

**What happens:** `loadFeatures` (later `loadCards`) scans the `pathly/` directory. It finds
`goals/` as a child directory. Since `goals` is not in the RESERVED set, it is treated as a
feature and added to the features list. The sidebar shows a feature named `goals` with no
STATE.json, no progress, no stages.

**Test to verify the fix:**
1. Create `pathly/goals/test-slug/` on disk (empty or with a stub `STATE.json`).
2. Render the sidebar.
3. Assert: the features list does NOT contain an entry with `name === 'goals'`.
4. Assert: the features list DOES contain an entry with `name === 'test-slug'` in the Goals
   section (Phase 3 concern; in Phase 1, just assert it is not a phantom feature).

**Fix:** Extend the RESERVED set in Phase 1 (not Phase 3). The IMPLEMENTATION_PLAN.md
Phase 1 RESERVED set change is the mitigation. The test above is the regression guard.

**Also at risk:** `lessons`, `explorations`, `debugs`, `pipeline-walkthrough`. If any of these
directories already exist on disk in a production install and the RESERVED set has not been
extended, they too will surface as phantom features. The Phase 1 fix covers all five.
