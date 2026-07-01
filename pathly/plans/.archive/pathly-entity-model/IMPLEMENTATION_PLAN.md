# IMPLEMENTATION_PLAN — scope/slug split + composition hygiene + artifact contract

## Intro — the core insight, what already shipped, and the build order

### The core bug this plan fixes

Pathly conflates two different things into one `topic` value:

```
   scope  =  WHICH BOARD TIER a message lives on   (feature | project | global)
             — may legitimately be an ABSOLUTE PATH, e.g. 'C:/Users/Yafit/pathly-adapters'
   slug   =  WHERE ON DISK the FSM/board reads & writes state
             — must be a filesystem-safe, TWO-component dir: pathly/<domain>/<slug>
```

Today the decompose/run paths pass `topic = scope` straight into
`fsm_ops._resolve_storage_path` (`src/pathly_orchestrator/fsm_ops.py:68-74`), which does
`Path(project_root) / "pathly" / topic`. When `topic` is an **absolute path** that join
**collapses back to the project root**, so the consultation flow's `PO_NOTES.md` gate never
resolves to the right directory → `PO_DISCUSSING` re-spawns forever. **Feature goals** (slug
scope) work only by accident, because their scope already looks like a slug.

The fix: **split scope from slug.** `scope` keeps flowing for board posts and the board-tier
advisory lock; a new per-goal **slug** becomes the on-disk key everywhere the FSM/terminal
resolves storage.

### What already shipped this session (do NOT redo — build on these)

- **Fix A** — `planning/plan` emits `AGENT_DONE` as a NEW Step 8, AFTER Step 6 (Post Tasks to
  Comms Board), so early-advance can't end the stage before the DAG seeds.
- The **completion-report fragment now OWNS the ordering invariant** ("AGENT_DONE is your FINAL
  action, after every file AND every board write"). Skills keep only a data-bearing invocation.
- The timer/user_initiated abort fix and the planner DAG-seeding race fix.

This plan's **Fix B** is the *structural backstop* to Fix A: it gates consultation
`PLANNING → DONE` on the **actual seeded DAG count** (a board query), not on prose-sniffing
`IMPLEMENTATION_PLAN.md '## Phase'`.

### Dependency order

```
   P0  ──►  P1  ──►  GATE2  ──►  P2
              └───────────────►  P2
   (P0 before P1; P1 before BOTH GATE2 and P2; GATE2 before P2 — P2 needs planning/dag-sketch)
```

- **P0** — behavior-neutral foundation: a shared `_safe_topic` guard in **WARN** mode + the
  nullable `comms_messages.slug` column + UNIQUE index. Nothing changes at runtime.
- **P1** — the slug/scope split itself: `ensure_goal_slug`, reroute every goal call site to
  `topic=slug`, extend the resolver to `pathly/goals/<slug>`, flip the guard to **RAISE**,
  patch the Studio RESERVED set. This closes the project-goal loop.
- **GATE2** — composition hygiene: new `planning/dag-sketch` skill + `task-dag-post` /
  `board-start-context` fragments, the `goal_id` capability, `build_adapter_caps`, the
  caps-threading seam through `start_board_run`, the `_decompose_planner` reroute, the plan.md
  Step-6 move, and the Summary-pill error parity. **P2 depends on `planning/dag-sketch`.**
- **P2** — the structural guarantee: `artifact-manifest.yaml` (single source for role→file→gate),
  a per-skill `artifact-register` fragment, an idempotent `ensure_attached` reconciler,
  board/scope/goal_id threaded into `/complete_stage`, and **Fix B** (the `on_board_count` FSM
  gate that asserts the seeded DAG).

### Hard rules in force for every task

- **400-line files; SOLID; no upward layer imports** (`db ← runner ← supervisor ← http_server`).
  `db/` imports nothing internal; broadcasters reach `db/` only as **injected callables**.
- **Fragment agnosticism** — skill body = the WHAT (no `/comms/*`, `/runner/*`, FSM transitions);
  the HOW (board CRUD, FSM, completion ordering) lives in fragments.
- Any **core skill/fragment/manifest** change MUST run `pathly-setup claude --apply --repair`
  **and** `python -m build`, and regenerate `tests/snapshots/*.claude.md` for affected composed
  skills. Pure-Python tasks under `src/pathly_orchestrator/` do NOT (confirm no `.claude.md`
  snapshot is affected).
- **completion-report stays LAST** in any skill's fragment list (it owns the AGENT_DONE-is-final
  invariant). Any new fragment (`task-dag-post`, `artifact-register`) goes BEFORE it.

---

## Phase 0 — _safe_topic guard (WARN) + comms_messages.slug column + UNIQUE index

Smallest, behavior-neutral foundation. A shared importable guard (WARN-only — logs, never
raises) wired into both storage-path resolvers, plus the additive slug column + UNIQUE index
that P1's `ensure_goal_slug` relies on. Zero runtime behavior change.

### T1 — Shared `_safe_topic` / `_is_unsafe_topic` guard (WARN-only leaf module)

**Files:** `src/pathly_orchestrator/storage_paths.py` (NEW), `tests/test_storage_paths.py` (NEW)

Create a NEW leaf module importing ONLY stdlib (`os`, `logging`) — no internal imports, so both
`fsm_ops` and `runner/argv` can import it with zero cycle risk (verified: `runner/argv.py`
currently imports only `pathly_orchestrator.adapters`). Define `logger = logging.getLogger("pathly.storage")`
(mirrors the `pathly.<name>` convention in eventlog/event_bus/invoke).

- `_is_unsafe_topic(topic: str) -> str | None` — return a short reason when unsafe, else None.
  Unsafe if: (a) falsy/whitespace-only → `"empty"`; (b) `os.path.isabs(topic)` → `"absolute path"`;
  (c) contains a **backslash or colon** (`any(c in topic for c in ("\\", ":"))`) →
  `"contains path separator"`. **Do NOT flag forward-slash here** — slash is covered by
  `os.path.isabs` in (b); flagging bare `/` would false-positive a working POSIX sub-path topic
  and break P0's behavior-neutrality (adversarial correction folded in). (d) splitting on both
  separators (`topic.replace("\\", "/").split("/")`) yields any part `==` `".."` →
  `"contains traversal segment"`.
- `_safe_topic(topic: str) -> str` — call `_is_unsafe_topic`; if a reason returns,
  `logger.warning("unsafe topic %r (%s); P0 WARN mode — using unchanged", topic, reason)` and
  return `topic` **UNCHANGED** (do NOT raise — this is the WARN release; P1 flips to raise). Pure
  pass-through; its only side effect is the warning. **Do NOT add `__all__` with private names** —
  omit `__all__` (adversarial note folded in).

Tests (guard only, no DB/FSM): normal-slug pass-through + `_is_unsafe_topic` None;
absolute forward-slash path WARNs once and returns unchanged; absolute **backslash** path same;
`_is_unsafe_topic("../escape")`, `("a/../b")`, `("")` truthy; `("goal-abc12345")` None.

**Acceptance:** module exists, imports only stdlib, `_safe_topic` never raises in P0 (returns input
unchanged for every input), absolute/traversal/empty flagged, plain slug not, forward-slash not
WARNed unless absolute. **Verify:** `PYTHONPATH=src python -m pytest tests/test_storage_paths.py -q`

### T2 — Wire `_safe_topic` into both storage-path resolvers (behavior-neutral)

**Files:** `src/pathly_orchestrator/fsm_ops.py`, `src/pathly_orchestrator/runner/argv.py`,
`tests/test_fsm_ops.py`

Add `from pathly_orchestrator.storage_paths import _safe_topic` to both modules. In
`fsm_ops._resolve_storage_path` (lines 68-74) make `topic = _safe_topic(topic)` the FIRST
statement before `new_style = Path(project_root) / "pathly" / topic` — do NOT alter the two-probe
logic at 69-74 (the collapse is P1's fix). In `runner/argv._storage_path` (lines 13-21) make
`topic = _safe_topic(topic)` the FIRST statement. Because T1's guard is a pass-through this is
ZERO behavior change; only a WARNING is logged on an unsafe topic.

Extend the `# ── _resolve_storage_path tests ──` section in `tests/test_fsm_ops.py`:
- `test_resolve_storage_path_warns_on_absolute_topic_but_resolves_unchanged` — pass an absolute
  topic; assert exactly one `pathly.storage` WARNING AND assert the returned value is **byte-identical
  to the pre-P0 collapse result** (compute the same `Path(project_root)/"pathly"/topic` expectation
  explicitly — do not leave it as "returns a Path"; adversarial correction folded in) and does not raise.
- `test_resolve_storage_path_normal_slug_no_warning` — plain slug with the new-style dir created
  (mirror `test_resolve_storage_path_prefers_new_style`); assert NO `pathly.storage` warning and the
  result equals the new-style dir.

Add `import logging` to the test module if absent.

**Acceptance:** both resolvers call `_safe_topic` first; normal slug → no warning + byte-identical
path (existing `prefers_new_style`/`falls_back_to_plans`/`legacy_not_shadowed` tests still pass);
absolute topic → one WARNING, no raise; no import cycle. **Verify:**
`PYTHONPATH=src python -m pytest tests/test_fsm_ops.py -q && PYTHONPATH=src python -c "import pathly_orchestrator.fsm_ops, pathly_orchestrator.runner.argv; print('import-ok')"`

### T3 — Additive migration: nullable `comms_messages.slug` + partial UNIQUE index

**Files:** `src/pathly_orchestrator/db/migrations_incremental.py`, `tests/test_migrations_slug.py` (NEW)

In `_add_additive_migrations` (lines 43-110), append to the column-add list (after line 104, before
the closing `]`) a comment + tuple:
```
# slug/scope split: per-goal on-disk slug, distinct from board scope. Nullable; added
# shape-only here (no writes). UNIQUE partial index below is the collision backstop.
("comms_messages", "slug", "TEXT"),
```
(Comment says the column is added here, not "P1" — adversarial note folded in.) The existing
try/except ADD COLUMN loop (106-110) silently skips an already-present column — no loop change.

**AFTER** the column-add `for` loop completes (after line 110, still inside `_add_additive_migrations`,
so the column exists before the index references it) create a **partial** UNIQUE index:
```
try:
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_comms_messages_slug "
        "ON comms_messages(slug) WHERE slug IS NOT NULL"
    )
    conn.commit()
except sqlite3.OperationalError:
    pass
```
The `WHERE slug IS NOT NULL` clause is REQUIRED (explicit + future-proof). Idempotent via `IF NOT EXISTS`.

New test file `tests/test_migrations_slug.py`. Build an isolated in-memory DB using the SAME import
path existing tests use — `from pathly_orchestrator.db import _run_migrations` (match `tests/test_db.py`
which imports from the `db` package `__init__`, not directly from `migrations`; adversarial note folded
in). `conn = sqlite3.connect(":memory:"); conn.row_factory = sqlite3.Row; _run_migrations(conn)`.
- `test_slug_column_exists` — `slug` in `PRAGMA table_info(comms_messages)`.
- `test_slug_unique_index_exists` — `idx_comms_messages_slug` in `PRAGMA index_list(comms_messages)`.
- `test_slug_unique_constraint_enforced` — insert two rows with the SAME non-null slug → second raises
  `sqlite3.IntegrityError`; insert two rows with `slug` NULL → BOTH succeed (partial index). **Every
  INSERT MUST supply all NOT NULL columns: `id, board, scope, from_agent, type, text, ts`** (`type` is
  NOT NULL with no default; `to_agent` defaults `'*'`) — adversarial correction folded in.
- `test_migration_idempotent` — call `_run_migrations` a SECOND time on the same conn → no raise,
  column + index still present exactly once.

**Acceptance:** after migration `slug TEXT` nullable column + `idx_comms_messages_slug` exist; same
non-null slug → IntegrityError, two NULLs both insert; second migration run idempotent; no row writes
set `slug` in P0 (grep confirms slug only in migration + tests). **Verify:**
`PYTHONPATH=src python -m pytest tests/test_migrations_slug.py -q`

---

## Phase 1 — slug/scope split (fixes the project-goal decompose loop)

Splits `topic`=`scope` into independent values. Introduces `ensure_goal_slug`, routes
`topic=slug` at every goal call site (scope still flows for board posts + the board lock),
extends the resolver to probe/create `pathly/goals/<slug>`, threads the resolved storage path
through board_run/terminal, flips `_safe_topic` to RAISE, and patches the Studio RESERVED set.
Depends on **P0** (the slug column + UNIQUE index + the `_safe_topic` leaf helper must exist).

### T4 — `ensure_goal_slug`: collision-safe goal→slug under the process write-lock

**Files:** `src/pathly_orchestrator/supervisor/slug.py` (NEW),
`src/pathly_orchestrator/db/queries/comms_messages.py`,
`src/pathly_orchestrator/db/queries/comms.py`, `tests/test_goal_slug.py` (NEW)

NEW `supervisor/slug.py` (supervisor layer — may import db; MUST NOT import http_server):
- `_slugify(text: str) -> str` — lowercase; replace runs of non-`[a-z0-9]` with `-`; strip leading/
  trailing `-`; cap to 48 chars. Small pure helper (do NOT import `runner/sections.py` — avoids a
  runner→supervisor read coupling). Empty result → `"goal"`. Note a **max total slug length cap of
  64 chars** so a uuid-tailed fallback can never overflow (adversarial note folded in).
- `ensure_goal_slug(conn, goal_id: str) -> str` — read-then-write under ONE write-lock so racing
  callers converge on one slug. `from pathly_orchestrator.db.connection import _get_write_lock`
  (this returns a `_WriteGuard` **context manager** — use ONLY the `with _get_write_lock(conn):`
  form; do NOT call `.acquire()`; adversarial correction folded in). Inside the block:
  1. read the goal row's `slug` and `text` via a db-layer helper (below) — the SELECT MUST be
     `WHERE id=goal_id AND type='goal'` (adversarial missing-item folded in: never slug a non-goal
     row). If `slug` already non-empty → return it (idempotent reuse).
  2. `base = _slugify(text)[:48]`; `candidate = f"{base}-{goal_id[:8]}"`.
  3. persist via `set_message_slug`. The P0 UNIQUE partial index is the backstop: catch
     `sqlite3.IntegrityError`; on collision retry with longer id tails (`goal_id[:10]`, `[:12]`) up
     to 3 times, then append a uuid4 hex tail (truncating the whole slug to the 64-char cap).
  All read+write stay inside the single `with _get_write_lock(conn):` block (the RLock under the
  guard is reentrant so nesting is safe).

In `db/queries/comms_messages.py` add two helpers mirroring `set_goal_executor` (lines 71-78):
- `set_message_slug(conn, message_id, slug)` — `with _get_write_lock(conn):` → `UPDATE comms_messages
  SET slug=? WHERE id=?`.
- `read_message_slug(conn, message_id) -> dict | None` — read-only SELECT of `slug, text` for the row
  `WHERE id=? AND type='goal'`. Keep ALL comms_messages column access in the db layer; `slug.py`
  contains NO inline SQL (adversarial inconsistency folded in — the SELECT also lives in db/).

In `db/queries/comms.py` (the re-export shim) add `set_message_slug` and `read_message_slug` to the
re-exports so `from ...db.queries.comms import set_message_slug` works for existing-style callers
(adversarial missing-item folded in).

Tests: idempotent (twice → same slug, one write); format `_slugify(text)[:48]+'-'+goal_id[:8]`; empty/
symbol-only text → base `"goal"`; two threads racing on the same goal_id converge on ONE slug (no
IntegrityError escapes).

**Acceptance:** slug.py exports `_slugify` + `ensure_goal_slug`; the latter acquires the write-lock
around SELECT+UPDATE and short-circuits on a persisted slug; concurrency converges; comms_messages.py
gains `set_message_slug` + `read_message_slug`; slug.py has no inline SQL; no http_server import.
**Verify:** `PYTHONPATH=src python -m pytest tests/test_goal_slug.py -q`

### T5 — Resolver: `goals/` probe + create, `_safe_topic` RAISE, thread storage_path through board_run/terminal

**Files:** `src/pathly_orchestrator/fsm_ops.py`, `src/pathly_orchestrator/runner/argv.py`,
`src/pathly_orchestrator/storage_paths.py`, `src/pathly_orchestrator/supervisor/board_run.py`,
`src/pathly_orchestrator/supervisor/state.py`, `src/pathly_orchestrator/supervisor/terminal.py`,
`tests/test_resolve_storage_path.py` (NEW)

1. **`_resolve_storage_path` (fsm_ops.py:68-74)** — extend the probe to multi-tier. The CURRENT code
   probes ONLY `pathly/<topic>` (`new_style`). New probe order (adversarial correction — narrative
   reversed (1)/(3) before; use this exact order): **(1) `pathly/<topic>`** [existing new_style],
   **(2) `pathly/goals/<topic>`** [new goal tier], **(3) `pathly/plans/<topic>`** [legacy feature dir].
   Build the candidate list, return the first `.is_dir()`. **If none exists:** fall through to the
   existing template join `Path(project_root)/template.format(topic=topic)` — this is the unchanged
   default and is what feature runs rely on (do NOT branch on a non-existent board arg). Goal-tier
   directory **creation** is the **caller's** job in T6 (which knows it is a goal and calls
   `mkdir(parents=True, exist_ok=True)` on `pathly/goals/<slug>`), NOT inside `_resolve_storage_path`
   — this resolves the self-contradiction the spec flagged (adversarial correction folded in).
   **Storage stays exactly two components under `pathly` (`pathly/<domain>/<slug>`)** — terminal.py's
   watcher derives project_root via `feature_dir.parent.parent.parent` (terminal.py:86); never nest
   deeper. Make `topic = _safe_topic(topic)` the first statement.
2. **Flip `_safe_topic` to RAISE** in `storage_paths.py`: when `_is_unsafe_topic(topic)` returns a
   reason, raise `ValueError(f"unsafe topic {topic!r} ({reason}); slug/scope split requires a "
   "filesystem-safe slug")` instead of logging. One-line comment noting this is the P1 flip. The
   guard at `fsm_ops._resolve_storage_path` AND `runner/argv._storage_path` now both raise on an
   absolute Windows path / `\` / `:` / `..`. Feature runs (topic already == slug) never hit the
   guard because their topic is safe.
3. **`board_run.py` where_line (246-255)** — add an optional `storage_path: str = ""` param to
   `start_board_run`; when provided, `where_line` uses it directly. **Also broaden the where_line
   condition**: it is currently gated on `if board == "feature" and project_root`, so goal-tier
   boards (`project`/`global`) never enter it. Change the guard so that **when `storage_path` is
   supplied** (goal-tier path from T6) the where_line is emitted regardless of board, while the
   existing feature inline-fallback (`pathly/<scope>` else `pathly/plans/<scope>`) is byte-identical
   when `storage_path` is absent (adversarial correction folded in).
4. **`supervisor/state.py` RunnerState** — add a `storage_path: str = ""` field. **Also add
   `storage_path` to `public_dict()`** (state.py:101-129) so `/runner/status` + STATUS SSE do not
   silently omit it (adversarial gap folded in). Set it once when a run starts.
5. **`terminal.py` three hardcoded `pathly/plans/<topic>` sites** (`:39` `_write_supervisor_phase_summary`,
   `:269` early_advance `feature_dir`, `:307` agent_done `storage_path`): replace the hardcoded
   `'plans'` with the resolved storage dir. Sites :269 and :307 read `RunnerState.storage_path` (set
   at run start). **Site :39** builds `feature_dir` from `(project_root, topic)` with no RunnerState
   in scope and early-returns if it does not exist — change it to resolve via a lazy
   `from pathly_orchestrator.fsm_ops import _load_flow, _resolve_storage_path` so a goal run's
   phase-summary writes under `pathly/goals/<slug>` instead of silently no-op'ing (adversarial
   asymmetry folded in). Wrap the resolve in try/except so a resolve hiccup keeps the existing
   early-return semantics. Keep the watcher `parent.parent.parent` derivation valid (still two
   components under pathly).

T5 introduces the param/probe/RAISE but does NOT yet route slugs at call sites — feature runs keep
passing because `pathly/<topic>` + `pathly/plans/<topic>` remain in the probe order; the project-goal
behavior change lands in **T6**.

Tests (`tests/test_resolve_storage_path.py`): (a) goal-tier slug → `pathly/goals/<slug>` returned when
the dir is pre-created (two components under pathly); (b) absolute topic → `ValueError`; (c) feature
slug → resolves `pathly/plans/<slug>` or `pathly/<slug>` exactly as before (no regression).

**Acceptance:** probe order `pathly/<topic>` → `pathly/goals/<topic>` → `pathly/plans/<topic>`;
`_safe_topic` RAISES on absolute/`\`/`:`/`..` at both resolvers; `start_board_run` gains optional
`storage_path` (where_line emitted for goal-tier when set, byte-identical feature fallback when
absent); RunnerState gains `storage_path` field + public_dict entry; terminal.py no longer hardcodes
`plans` for goal runs (all three sites incl. :39 resolve correctly); watcher project_root unchanged.
**Verify:** `PYTHONPATH=src python -m pytest tests/test_resolve_storage_path.py -q`

### T6 — Route topic=slug at every goal call site + thread storage_path + Studio RESERVED set (closes the loop)

**Files:** `src/pathly_orchestrator/supervisor/goal_decomposer.py`,
`src/pathly_orchestrator/supervisor/goal_executor.py`,
`src/pathly_orchestrator/supervisor/board_run.py`,
`studio/src/renderer/src/store/commsStore.ts`, `tests/test_project_goal_decompose.py` (NEW)

Reroute every goal-tier FSM/board call so the on-disk topic is the SLUG; `scope` keeps flowing for
board posts and the board-tier lock.

1. **goal_decomposer `_decompose_consultation` (:244-257)** — before `_start(...)`, add lazy imports
   `from pathly_orchestrator.db.connection import get_db` and
   `from pathly_orchestrator.supervisor.slug import ensure_goal_slug` (the `get_db` import is required
   and was omitted by the spec — adversarial correction folded in), resolve
   `slug = ensure_goal_slug(get_db(project_root or None), goal_id)`, **create the goal dir**
   `Path(project_root)/"pathly"/"goals"/slug` with `mkdir(parents=True, exist_ok=True)`, then call
   `_start(topic=slug, ...)` instead of `topic=scope`. The `_reset_fsm_state_for_flow(...)` call at
   :242 must ALSO receive `slug` (see step 3).
2. **goal_executor `_run_team` (:317 reset + :320-334 _start)** — resolve `slug` at the top of
   `_run_team` (same `get_db` + `ensure_goal_slug` lazy imports + the goals/ mkdir); pass `slug` to
   `_reset_fsm_state_for_flow(flow, slug, project_root)` (:317) AND `_start(topic=slug, ...)` (:321).
   Leave the `board_lock.holder(board, scope)` / `get_state(scope)` busy checks (:292-300) keyed on
   **scope** — the board-tier lock is per-board/scope, NOT per-disk-dir. Do the same for `_run_loop`:
   set `RunnerState.topic=slug` (currently `topic=scope` at :223-231); `scheduler_loop(state, board,
   scope, ...)` at :249 keeps board/scope as scope (scheduler scopes its frontier by goal_id; the
   topic change is the load-bearing per-task storage key).
3. **goal_executor `_reset_fsm_state_for_flow` (:23-65)** — rename the 2nd positional param from
   `scope` to `topic` (it is the disk key; it already forwards into `_resolve_storage_path` at :52).
   No body change beyond the name + docstring. Update its callers (steps 1-2) accordingly — the
   signature is unchanged in arity so existing positional calls keep working (adversarial note: the
   import in goal_decomposer stays valid).
4. **goal_decomposer `_decompose_planner` + `_decompose_plan`** — resolve `slug` (same pattern) and
   pass `storage_path=str(Path(project_root)/"pathly"/"goals"/slug)` (created above) into
   `start_board_run(...)` (the kwarg added in T5). The first two positional args stay `(board, scope)`
   — the board-POST scope is unchanged; only the new `storage_path` kwarg carries the disk location.
5. **board_run `start_board_run`** — use the `storage_path` kwarg for where_line (the broadened guard
   from T5 emits it for goal-tier boards too).
6. **`commsStore.ts:140`** — extend the RESERVED set from `new Set(['plans', '.archive'])` to
   `new Set(['plans', '.archive', 'goals', 'lessons', 'explorations', 'debugs', 'pipeline-walkthrough'])`
   so `pathly/goals/` (and sibling domains) never surfaces as a phantom feature in `loadFeatures`'s
   `newStyleIds` scan (verified: RESERVED only filters the top-level `pathly/` scan at line 143; the
   `pathly/plans/` legacyIds scan at line 136 is unaffected because goals live at `pathly/goals/`,
   not `pathly/plans/goals/`).

No core skill/fragment changed → no `pathly-setup`/`python -m build`/snapshot regen for T6.

**The FSM-boundary test (mandatory).** `tests/test_project_goal_decompose.py` (NEW) MUST drive the
**REAL FSM** through ≥1 real transition for an **absolute-path-scoped** goal (a mock on each side of
the FSM↔driver boundary hides exactly this collapse class — see MEMORY `project_fsm_next_state_contract_bug`).
Scaffold: create a tmp project_root, seed a `type='goal'` comms_messages row with `scope=str(tmp_path)`
(an absolute path) into a temp DB, run the consultation decompose (or directly drive
`_resolve_storage_path` + the PO stage transition with the resolved slug), then assert: (a)
`pathly/goals/<slug>/` was created, (b) writing `PO_NOTES.md` with a `#` under that dir makes the
`PO_DISCUSSING → ARCHITECTING` content gate fire (the stage advances PAST `PO_DISCUSSING`, no infinite
re-spawn), (c) a feature goal (slug scope) still resolves `pathly/plans/<slug>` unchanged.

**Acceptance:** every goal call site (`_decompose_consultation`, `_run_team` both calls, `_run_loop`
RunnerState.topic, `_reset_fsm_state_for_flow`, `_decompose_planner`, `_decompose_plan`) passes the
slug as the on-disk topic; scope still flows as board-post scope + lock key; the real-FSM project-goal
test advances past `PO_DISCUSSING`; `start_board_run` threads storage_path for goal-tier planner/plan
runs; commsStore RESERVED extended; renderer typechecks clean. **Verify:**
`PYTHONPATH=src python -m pytest tests/test_project_goal_decompose.py -q && node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Phase GATE2 — amended unified-cli-composition (dag-sketch + fragments + decompose routing)

Composition hygiene that P2 depends on. Adds the `goal_id` capability + `build_adapter_caps` + the
**caps-threading seam** through `start_board_run` (the blocking seam the spec missed — without it
goal_id-gated fragments are silently dropped), the new `planning/dag-sketch` skill + `task-dag-post`
/ `board-start-context` fragments, the `_decompose_planner` reroute, the plan.md Step-6 move, and the
Summary-pill error parity. Depends on **P1**; **P2 depends on `planning/dag-sketch`.**

### T7 — `goal_id` capability + `build_adapter_caps` + caps-threading seam through start_board_run

**Files:** `src/pathly_orchestrator/skills/compose.py`, `src/pathly_orchestrator/skills/__init__.py`,
`src/pathly_orchestrator/supervisor/board_run.py`, `src/pathly_orchestrator/supervisor/goal_decomposer.py`,
`src/pathly_orchestrator/http_server/blueprints/skills/editor_render.py`, `tests/test_compose.py`

1. **compose.py** — extend `_KNOWN_CAPABILITIES` (line 28) from `{"can_spawn"}` to
   `{"can_spawn", "goal_id"}`. Gating is boolean truthiness (`caps.get("goal_id")`), so `goal_id`
   doubles as a gate flag AND a value the fragment body needs. `_coerce_caps` already passes extra
   dict keys through untouched.
2. **`build_adapter_caps(adapter, *, goal_id="", executor="", kind="") -> dict`** (NEW, near
   `adapter_caps_for`, ~line 165) — calls `adapter_caps_for(adapter)` for `can_spawn` then merges
   `{"goal_id": goal_id or "", "executor": executor or "", "kind": kind or ""}`. Export from
   `skills/__init__.py` (import list + re-export list alongside `adapter_caps_for`).
3. **THE CAPS-THREADING SEAM (the blocking fix the spec missed — adversarial correction folded in).**
   `board_run._compose_skill_body(skill, adapter)` (lines 104-115) currently calls
   `compose_skill(skill, adapter or "claude")` — passing only the adapter STRING, so every goal_id-gated
   fragment is unconditionally dropped and the whole GATE2 feature is dead on arrival. Add a
   `caps: dict | None = None` parameter: `compose_skill(skill, caps if caps is not None else (adapter or "claude"))`.
   Add a `caps: dict | None = None` kwarg to `start_board_run` and forward it into `_compose_skill_body`.
4. **goal_decomposer** — in `_decompose_planner` and `_decompose_plan`, build caps once via
   `build_adapter_caps(adapter or "claude", goal_id=goal_id, executor="", kind="dag")` (lazy import,
   mirroring the existing `from ...board_run import start_board_run`) and pass `caps=<that dict>` into
   `start_board_run`. (Routing/skill changes are T9; T7 only threads caps so the seam is exercised.)
5. **editor_render.py** — replace inline `adapter_caps={"can_spawn": True}` (line 201, `skills_preview`)
   with `build_adapter_caps("claude")`. **Also update the high-traffic `/skills/compose` endpoint
   (~line 260)** which currently calls `compose_skill(skill, adapter)` with a raw adapter string:
   read an optional `goal_id` from the request body and pass `build_adapter_caps(adapter, goal_id=goal_id)`
   (default empty → behavior-equivalent for non-goal previews) — adversarial false-completeness
   correction folded in.
6. **tests/test_compose.py** — `test_build_adapter_caps_merges_goal_context` (the two equalities);
   `test_goal_id_gate_known_capability` — a synthetic manifest with `{name: comms-post, requires: goal_id}`
   passes `validate_composition` (call it AFTER `_KNOWN_CAPABILITIES` is patched — adversarial sequencing
   note folded in) and `compose_skill` keeps the fragment with `caps={"goal_id":"g1"}`, drops it with
   `caps={"goal_id":""}`.

**Acceptance:** `_KNOWN_CAPABILITIES` includes `goal_id`; `requires: goal_id` validates;
`build_adapter_caps` merges + is exported; **`_compose_skill_body`/`start_board_run` accept & forward
a `caps` dict so goal_id reaches `compose_skill`**; `compose_skill` keeps/drops a `requires: goal_id`
fragment by caps; no existing test regresses (`test_task_dag_post_block_retired` green). **Verify:**
`PYTHONPATH=src python -m pytest tests/test_compose.py -q`

### T8 — Create `task-dag-post` + `board-start-context` fragments and the `planning/dag-sketch` skill; wire composition.yaml

**Files:** `src/pathly_data/core/skills/fragments/task-dag-post.md` (NEW),
`src/pathly_data/core/skills/fragments/board-start-context.md` (NEW),
`src/pathly_data/core/skills/planning/dag-sketch.md` (NEW),
`src/pathly_data/core/skills/composition.yaml`, `tests/test_compose.py`

1. **`fragments/task-dag-post.md`** — the SINGLE board-task-POST mechanism (extracted from plan.md
   Step 6; canonical home). Structure like `comms-post.md` (H2 + curl + skip-if-down). H2:
   `## Posting the task DAG to the Comms Board`. Body assumes `$GOAL_ID` is known (the goal already
   exists — do NOT post `type=goal`): (a) the idempotency guard
   `curl -s "http://127.0.0.1:8765/comms/tasks?goal_id=$GOAL_ID"` + the skip-only-if-THIS-goal-has-tasks
   rule (port the exact wording from plan.md lines 294-301); (b) the per-task POST shape — `type:'task'`,
   `goal_id:'$GOAL_ID'`, self-contained `text` (builder prompt), `board`, `scope`, `stage`, optional
   integer `conv`, `depends_on` array, optional `artifact_path`/`context_refs`, plus the "executor is
   NOT on the task" note (port plan.md lines 423-448); (c) skip-if-down advisory (connection-refused /
   non-200 → don't fail; record the miss in the completion summary — port plan.md lines 452-456). Keep
   it AGNOSTIC of where titles come from (works for both `planning/plan` phase-derived and `dag-sketch`
   free-form tasks). Do NOT include the advisory-artifact POST block (stays in plan.md Step 6).
2. **`fragments/board-start-context.md`** — read-only board context pull at decompose start, gated on
   `goal_id`. H2: `## Reading the board before you decompose`. Body: a **`POST http://127.0.0.1:8765/comms/agent-context`**
   (the registered method is **POST**, not GET — GET returns 405; adversarial correction folded in)
   scoped to `{scope, goal_id}`, instructing the agent to read existing goal text + open questions
   before producing tasks; explicit skip-if-down (server unreachable → proceed with the prompt's inline
   goal text). Keep ≤30 lines, advisory, never blocks.
3. **`planning/dag-sketch.md`** — AGNOSTIC body only (NO `http://127.0.0.1:8765`/`/comms/` strings).
   Leading `---\n\n---` block is fine (`_strip_leading_frontmatter` removes it). Body: "Decompose the
   goal into 3-7 concrete, independently-runnable tasks. Each title actionable + specific. Write a
   one-page `DAG_PLAN.md` with a `## Tasks` table `[id | title | depends_on]`. Then post each task."
   No curl/POST mechanics (the fragment owns that); no heavy plan phases/templates; end BEFORE any
   completion prose (the fragment supplies it).
4. **composition.yaml** — add a `skills:` entry for `planning/dag-sketch` composing exactly:
   `- { name: board-start-context, requires: goal_id }`, `- { name: task-dag-post, requires: goal_id }`,
   `- completion-report` (in that order; completion-report LAST). The `progress-logging` default applies
   automatically. Do NOT add a `consultation-plan` block (keep `test_task_dag_post_block_retired` green).
5. **tests/test_compose.py** — `test_dag_sketch_composes_task_post_and_completion`:
   `compose_skill("planning/dag-sketch", build_adapter_caps("claude", goal_id="g1"))` contains the
   `task-dag-post` + `board-start-context` H2 markers + `## Completion report`; with
   `build_adapter_caps("claude")` (no goal_id) the two gated sections are absent but completion-report
   + progress-logging remain. Leave `test_task_dag_post_block_retired` UNCHANGED.

After editing core files run the propagation commands (verify line). **Confirm the new skill is
auto-discovered by `pathly-setup` (no per-adapter `_meta/skills/dag-sketch.yaml` required); if the
build errors on a missing `_meta` entry, add `_meta/skills/dag-sketch.yaml` to all four adapters**
(adversarial missing-item folded in).

**Acceptance:** the three new files exist with the specified structure; the skill body has NO
`http://127.0.0.1:8765`/`/comms/` strings; `validate_composition()` passes with the new entry;
`compose_skill("planning/dag-sketch", build_adapter_caps("claude", goal_id="g1"))` includes the three
sections, drops the two gated ones with no goal_id; `test_task_dag_post_block_retired` green; after
`pathly-setup claude --apply --repair` + `python -m build` the four adapter `_meta` trees build and the
new files appear in claude install output. **Verify:**
`PYTHONPATH=src python -m pytest tests/test_compose.py -q && PYTHONPATH=src python -c "from pathly_orchestrator.skills.compose import validate_composition; validate_composition(); print('manifest ok')"`

### T9 — Route `_decompose_planner` → composed `planning/dag-sketch`; keep `_decompose_plan` on `planning/plan`; move plan.md Step 6 task-POST into the fragment

**Files:** `src/pathly_orchestrator/supervisor/goal_decomposer.py`,
`src/pathly_data/core/skills/planning/plan.md`, `src/pathly_data/core/skills/composition.yaml`,
`tests/test_compose.py`, `tests/snapshots/` (regenerate affected)

1. **`_decompose_planner` (lines 93-154)** — REPLACE the inline `instructions` string (113-135) and
   `skill=""` (line 142) with a SHORT goal-context `instructions` (e.g. `f"Decompose this goal into
   3-7 tasks. Goal: {goal_text}. The goal already exists with goal_id={goal_id!r} — post task children
   only, do NOT post a new goal."`), `skill="planning/dag-sketch"`, `agent="planner"`, and `caps=`
   from T7. DELETE the inline `POST {post_url}` JSON block (mechanics now come from the composed
   `task-dag-post` fragment). Keep `result["mode"]="planner"` / `goal_id` tagging; read the result from
   `AGENT_DONE.summary` as today.
2. **`_decompose_plan` (lines 157-203)** — NO routing change; stays `skill="planning/plan"`. Deliberate
   amendment: do NOT force the light path onto planning/plan (it remains the full-plan decomposer that
   derives context_refs + depends_on). Pass `caps=build_adapter_caps(adapter or "claude", goal_id=goal_id, kind="plan")`.
3. Do NOT touch `_decompose_consultation` routing.
4. **plan.md Step 6 (lines 277-456)** — MOVE the per-task POST mechanics OUT. Replace the inline
   idempotency-guard + per-task curl block (the prose at ~382-456) with a short pointer:
   "The composed `task-dag-post` fragment owns the per-task POST mechanics (idempotency guard, the task
   JSON shape, **depends_on** resolution, skip-if-down). For each phase: extract N/title/Purpose/File/
   Done-when/Depends-on, compose the self-contained task `text`, **derive `context_refs` from the phase
   number**, and post via the fragment." **The surviving prose MUST keep the literal token `context_refs`**
   (and `depends_on`) so that `compose_skill("planning/plan", "claude")` — called with no goal_id, which
   drops the gated `task-dag-post` fragment — still contains `context_refs`, keeping
   `test_task_dag_post_block_retired` (line 346) green WITHOUT editing it (adversarial contradiction
   resolved). KEEP in plan.md Step 6: the advisory artifact-heading convention (285-292), the
   Find-OR-create-goal block (303-328 — goal creation stays in the skill), and the advisory-artifact
   POST block (330-380).
5. **composition.yaml `planning/plan` (lines 123-125)** — change `fragments: [completion-report]` to
   `fragments: [{ name: task-dag-post, requires: goal_id }, completion-report]` — task-dag-post BEFORE
   completion-report (completion-report stays LAST). Validator still passes (a fragment referenced by
   two skills is fine; duplicate-include is per-skill).
6. **Snapshots** — the 6 existing snapshots (team/dev build/review/test) should be UNCHANGED (only
   composition.yaml + plan.md changed; no shared fragment edited). Re-run the snapshot-generation step;
   commit any diff. Optionally ADD `tests/snapshots/planning__plan.claude.md` from
   `compose_skill("planning/plan", build_adapter_caps("claude", goal_id="g1"))` with a parametrized
   test. After editing core skill/manifest files run `pathly-setup claude --apply --repair` + `python -m build`.
7. **tests/test_compose.py** — `test_plan_composes_task_dag_post_before_completion`:
   `compose_skill("planning/plan", build_adapter_caps("claude", goal_id="g1"))` contains both the
   `task-dag-post` H2 and `## Completion report`, and the completion-report index > the task-dag-post
   index; with no goal_id the task-dag-post section drops but completion-report stays.

**Acceptance:** `_decompose_planner` uses `skill="planning/dag-sketch"` + short instructions + NO inline
POST block + caps; `_decompose_plan` still `planning/plan`; `planning/plan` composes `task-dag-post`
BEFORE `completion-report` (POST shape appears exactly once, from the fragment) and plan.md Step 6 no
longer carries the inline per-task curl but RETAINS `context_refs`; `validate_composition()` passes; the
6 golden snapshots pass; after propagation the claude skills carry the moved sections. **Verify:**
`PYTHONPATH=src python -m pytest tests/test_compose.py -q && PYTHONPATH=src python -c "from pathly_orchestrator.skills.compose import compose_skill, build_adapter_caps; out=compose_skill('planning/plan', build_adapter_caps('claude', goal_id='g1')); assert out.count('## Completion report')==1; print('plan composes task-dag-post + completion ok')"`

### T10 — Harden the Summary ActionPill error state (`ERROR:`-prefixed capture → pill='error', parity with Analyze/Split)

**Files:** `studio/src/renderer/src/components/CommandCenter/CommsPanel/hooks/useResummarize.ts`,
`studio/src/renderer/src/components/CommandCenter/CommsPanel/ArtifactsView/summarizeArtifact.ts`

Renderer-only. Ensure the Summary path treats an `ERROR:`-prefixed capture file as a hard failure
driving the pill to `state='error'`, matching the Analyze/Split contract. Most wiring exists — verify
and lock it, do not rebuild:
1. **useResummarize.ts `run()` (204-268)** — confirm the engine path reads the sibling `.summary` file,
   that `/^ERROR:/i` (line 229) THROWS into the catch (255-267) → `markStatus(messageId, 'failed', msg)`
   + `setPillState('error')` (262-264) + 2.5s auto-reset (265); the thrown message strips the `ERROR:`
   prefix (line 230) so the toast shows the agent's reason. Restore any drift.
2. **summarizeArtifact.ts `summarizeArtifactById` (84-149)** — confirm the engine path's `/^ERROR:/i`
   (line 119) throws + is caught (142-148) → a `Summary failed: <reason>` toast, and the file is NOT
   written back as a real summary (auto path has no pill).
3. If renderer test infra exists (`__tests__`/`*.test.ts`), add a guard feeding a `.summary` whose first
   line is `ERROR: boom` and asserting pill→'error' (not 'done') + toast `Summary failed: boom`.
   Otherwise acceptance is the typecheck + a manual-trace note in the PR.

No core/skill change → no `pathly-setup`/`python -m build`/snapshot. No inline styles (logic-only).
**Do NOT pull in CardKind/loadCards work — that is the deferred Studio package.**

**Acceptance:** Re-summarize engine path: `ERROR:`-prefixed file → pill `state='error'` + stripped-prefix
`Summary failed: <reason>` toast + auto-reset (parity with Analyze/Split); auto-summary path throws +
toasts + does NOT write back; no `style={{...}}`; renderer typechecks. **Verify:**
`node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Phase 2 — artifact contract + reconciler + Fix B (on_board_count gate)

Makes the pipeline's artifact + DAG state STRUCTURAL, not prose-sniffed. Adds a single
source-of-truth `artifact-manifest.yaml` (role→file→gate) read by BOTH composer and FSM gates, a
per-skill `artifact-register` fragment (allow-list — NEVER in `defaults:`), an idempotent
`ensure_attached` reconciler, board/scope/goal_id threaded additively into `/complete_stage`, and
**Fix B** (`on_board_count` gate). Depends on **GATE2** (`planning/dag-sketch` + `task-dag-post`
must exist) and **P1** (complete_stage now meaningfully carries scope vs slug).

### T11 — `artifact-manifest.yaml` (role→file→gate single source) + per-skill `artifact-register` fragment

**Files:** `src/pathly_data/core/skills/artifact-manifest.yaml` (NEW),
`src/pathly_data/core/skills/fragments/artifact-register.md` (NEW),
`src/pathly_data/core/skills/composition.yaml`, `src/pathly_orchestrator/skills/compose.py`,
`tests/test_compose.py`, `tests/snapshots/` (regenerate affected)

> **Ordering note:** T11 references `planning/dag-sketch` in composition.yaml, which exists only after
> GATE2. T11 therefore depends on GATE2 (T8/T9) — its `validate_composition()` would fail on
> `unknown skill 'planning/dag-sketch'` otherwise (adversarial sequencing error folded into the DAG
> `depends_on`).

1. **`artifact-manifest.yaml`** — single source read by BOTH composer and FSM gates:
```
version: 1
roles:
  po:            {file: PO_NOTES.md,                gate: '#'}
  architect:     {file: ARCHITECTURE_PROPOSAL.md,   gate: '#'}
  web-researcher:{file: RESEARCH.md,                gate: '#'}
  designer:      {file: DESIGN.md,                  gate: '## Design System Output'}
  planner:       {file: IMPLEMENTATION_PLAN.md,     gate: '## Phase'}
  reviewer:      {file: feedback/REVIEW_FAILURES.md, gate: '#'}
  tester:        {file: feedback/TEST_FAILURES.md,  gate: '#'}
  retro:         {file: RETRO.md,                   gate: '#'}
  explorer:      {file: CONCLUSIONS.md,             gate: '#'}
overrides:
  planner.planning/dag-sketch: {file: DAG_PLAN.md, gate: '## Tasks'}
```
   Override key form `<role>.<skill-name>`. `roles` keys MUST match the `role_map` strings used across
   flows. **The manifest gate strings MUST stay consistent with the existing `on_content` markers in
   the flow YAMLs** (`PO_NOTES '#'`, `DESIGN '## Design System Output'`, etc.) during the migration
   window — only consultation `PLANNING` switches to `on_board_count` in T13.
2. **compose.py loaders** — `load_artifact_manifest() -> dict` (reads `_skills_root()/'artifact-manifest.yaml'`,
   mirrors `load_manifest`) and `manifest_role_file(role, skill=None) -> tuple[str,str] | None`
   (`overrides['<role>.<skill>']` first, else `roles[role]`, else None). Keep PURE (no DB) so the FSM
   gate path imports it without a layer violation. (`skills/` is a sibling of `fsm/` — `fsm → skills`
   is allowed; the CLAUDE.md layer DAG governs db/runner/supervisor/http_server only.)
3. **`fragments/artifact-register.md`** — agnostic-to-role HOW fragment owning THREE mechanics: (a)
   write the role's named output file to `<out_path>`; (b) append ONE line to
   `<feature_path>/ARTIFACTS.jsonl` `{role, path, type, title, summary, ts}` via a `python3 -c` heredoc
   (create if absent, append-only, never rewrite); (c) advisory board POST `type='artifact'` to
   `http://127.0.0.1:8765/comms/post` with skip-if-down (connection-refused / non-200 → skip silently;
   the file is the authority). Body MUST state: runs AFTER the output file is written and BEFORE the
   completion report (so AGENT_DONE stays final). NO `/complete_stage` / FSM transition. **Substitution:
   the runner pre-substitutes `<out_path>` and `<feature_path>` exactly as `client-file-output.md` does
   for `<out_path>` — cite/reuse that same substitution site so the tokens resolve at runtime**
   (adversarial missing-item: confirm the existing substitution function and feed `<feature_path>` =
   the resolved storage dir from T5).
4. **composition.yaml** — attach `- artifact-register` PER-SKILL to pipeline-role skills ONLY (the
   manifest `roles` map is the allow-list): `team/build`, `team/review`, `team/test`, `team/design`,
   `team/retro`, `planning/plan`, and `planning/dag-sketch`. **For `team/design` and `team/retro`,
   which today carry only `comms-post` (no `completion-report`), do NOT let `artifact-register` become
   the last fragment** — these two stages do not currently compose completion-report; insert
   `artifact-register` BEFORE `comms-post` (or before completion-report where present) so no
   ordering-invariant skill ends on `artifact-register` (adversarial ordering correction folded in).
   Do NOT add to `defaults:`, nor to `planning/po`, `planning/evaluate`, `planning/consolidate`, or any
   `development/summarize*|analyze|split` entry (overspray guard).
5. **tests/test_compose.py** — `test_artifact_manifest_loads`;
   `test_manifest_role_file_override` (`('planner','planning/dag-sketch')==('DAG_PLAN.md','## Tasks')`;
   `('planner')==('IMPLEMENTATION_PLAN.md','## Phase')`; `('designer')==('DESIGN.md','## Design System Output')`);
   `test_artifact_register_composed` (`compose_skill('team/build','claude')` contains the artifact-register
   heading); `test_artifact_register_not_in_po` (`compose_skill('planning/po','claude')` does NOT).
   **Extend the snapshot parametrize lists** to cover `team/design`, `team/retro`, `planning/plan` (and
   `planning/dag-sketch`) since `_CONVERTED_TEAM_SKILLS` currently covers only build/review/test
   (adversarial missing-item folded in).
6. Run `pathly-setup claude --apply --repair` + `python -m build`; regenerate
   `tests/snapshots/*.claude.md` for the 7 composed skills now including artifact-register (confirm the
   diff is only the fragment insertion, completion-report still LAST where present).

**Acceptance:** `artifact-manifest.yaml` exists with the roles map + override;
`manifest_role_file` resolves override/default/designer; `artifact-register.md` writes `<out_path>`,
appends to `<feature_path>/ARTIFACTS.jsonl`, does an advisory skip-if-down POST, has NO `/complete_stage`/
FSM call; composition.yaml lists artifact-register under the 7 skills and NOWHERE in defaults / po /
evaluate / consolidate / summarize* / analyze / split, with no skill ending on artifact-register;
`validate_composition()` passes; new tests pass; the 7 snapshots regenerated. **Verify:**
`PYTHONPATH=src python -m pytest tests/test_compose.py -q && pathly-setup claude --apply --repair && python -m build`

### T12 — Thread board/scope/goal_id into `/complete_stage` + `ensure_attached` reconciler with manifest/JSONL fallback

**Files:** `src/pathly_orchestrator/db/queries/comms_artifacts.py`,
`src/pathly_orchestrator/db/queries/comms.py`, `src/pathly_orchestrator/db/queries/__init__.py`,
`src/pathly_orchestrator/http_server/blueprints/core/fsm.py`,
`src/pathly_orchestrator/fsm_ops_complete.py`,
`src/pathly_orchestrator/supervisor/orchestrator_stage.py`,
`src/pathly_orchestrator/supervisor/terminal.py`, `tests/test_artifact_reconcile.py` (NEW)

1. **comms_artifacts.py `ensure_attached(conn, scope, board, artifact_path, role, *, title=None,
   summary=None, artifact_type='md', broadcast_fn=None) -> str`** — idempotent UPSERT keyed on
   `(scope, artifact_path)`. Resolve via `find_or_create_artifact_by_path(conn, scope, artifact_path)`.
   **`find_or_create_artifact_by_path` (line 175) currently only creates a sentinel when the path
   contains `/pathly/plans/`** — goal-tier artifacts live under `pathly/goals/<slug>/` and would be
   silently dropped. **Broaden that path check to accept `/pathly/goals/` as well** (adversarial
   correction folded in) — or, if minimizing the blast radius, inline the broader-path sentinel creation
   inside `ensure_attached`. When no row + not creatable, `post_message(conn, board=board, scope=scope,
   from_agent=role, type='artifact', text=title or <basename>, artifact_path=artifact_path,
   artifact_type=artifact_type)` then `insert_artifact(...)`. Wrap writes in `with _get_write_lock(conn):`.
   Return the artifact id. Idempotency: two calls for the same `(scope, artifact_path)` → SAME id, one
   `comms_artifacts` row. After a fresh attach, best-effort `broadcast_fn({"type":"COMMS_UPDATE",
   "event":"artifact_attached", "board":board, "scope":scope, "artifact_type":artifact_type})` —
   **broadcaster is an INJECTED callable** (the http_server/supervisor caller supplies it); the db layer
   imports NO http_server. **Be explicit about which value populates the `scope` column** on a created
   sentinel — it is the board `scope` (the board-tier key), NOT the slug (adversarial note folded in).
   Re-export `ensure_attached` from `db/queries/comms.py` (the shim) AND `db/queries/__init__.py` (and
   `db/__init__.py` if it has its own import list) so the standard import path works and the shim stays
   consistent (adversarial inconsistency folded in).
2. **fsm.py `complete_stage_endpoint`** — KEEP `required={flow,topic,project_root}`; additively forward
   the full JSON body (already passed) so `board/scope/goal_id` reach `complete_stage` with NO
   validation change + NO 400 when absent.
3. **fsm_ops_complete.py `complete_stage(args)`** — read `board = args.get('board') or 'feature'`;
   `scope = args.get('scope') or topic`; `goal_id = args.get('goal_id')` (derived defaults →
   behavior-identical for existing feature runs). AFTER a successful transition (around the existing
   STATE_TRANSITION append, before building the next prompt) reconcile the gating artifact: resolve the
   prev-state role's file via `compose.manifest_role_file(role, skill)` (role from `role_map[prev_state]`,
   skill from `agent_map[prev_state]`); if `(storage_path / file).exists()`, call
   `ensure_attached(get_db(project_root), scope=scope, board=board, artifact_path=str(storage_path/file),
   role=role, broadcast_fn=<lazy _broadcast_comms>)` inside try/except (never block the transition). Pass
   `goal_id` into `evaluate_transition_rules` (consumed in T13).
4. **orchestrator_stage.py** — at the two `fhc.complete_stage(...)` call sites (`:48` primary, `:108`
   the decide-resolution path) additively include `board/scope/goal_id` from RunnerState. **Only the
   primary :48 call needs the goal-scoped fields for the on_board_count gate; the :108 decide-result
   call may pass them but the gate is goal-scoped and harmless either way** — do NOT introduce new
   semantics on the decide path (adversarial precision note folded in). For plain feature runs leave
   them None/absent.
5. **terminal.py non-FSM / post-PTY path** — after a stage's PTY exits in a mode that does NOT go
   through complete_stage, add a best-effort `_reconcile_artifacts(feature_dir, scope, board, role)`
   helper (≤30 lines): read `<feature_dir>/ARTIFACTS.jsonl` if present and `ensure_attached` each line;
   FALLBACK when absent — stat the role's manifest file (`compose.manifest_role_file`) under feature_dir
   and `ensure_attached` if it exists. Wrap in try/except + `logger.debug`; must never affect PTY result
   handling. **Note:** consultation stages `team/architect` (ARCHITECTING) and `team/research`
   (RESEARCHING) are NOT in the artifact-register allow-list and write no ARTIFACTS.jsonl — the
   manifest-stat fallback covers them (`architect→ARCHITECTURE_PROPOSAL.md`, `web-researcher→RESEARCH.md`)
   provided the reconcile pass is invoked for those stages' roles too (adversarial gap folded in:
   ensure the fallback runs for every stage role, not only allow-list ones).
6. **tests/test_artifact_reconcile.py** — (a) JSONL path → one row for `(scope, path)`; (b) manifest-stat
   fallback (no JSONL but the role's file on disk) → attached; (c) idempotency (twice → one row, same
   id); (d) complete_stage carries scope/board through (drive complete_stage with board+scope, assert no
   error + the gating artifact attached). **Use a REAL temp SQLite DB via the test_gates.py harness
   pattern (`_db.get_db(project_root)` with `project_root = storage.parent.parent.parent`) — do NOT
   write to the shared live `~/.pathly/pathly.db`** (adversarial isolation risk folded in: pass an
   explicit tmp project_root so `get_db` resolves a temp DB).

**Acceptance:** `ensure_attached` idempotent on `(scope, artifact_path)` (two calls → one row, same id)
+ emits the artifact_attached shape via the injected `broadcast_fn`; db layer imports NO http_server
(`python -c 'import pathly_orchestrator.db.queries.comms_artifacts'` clean); `find_or_create_artifact_by_path`
accepts `/pathly/goals/` paths; `/complete_stage` accepts optional board/scope/goal_id with no 400;
complete_stage derives feature/topic/None defaults (behavior-identical) + best-effort attaches the
prev-state manifest file without blocking; terminal.py reconciles via JSONL-or-manifest-stat fully
wrapped; the four reconcile tests + existing `tests/test_gates.py` pass. **Verify:**
`PYTHONPATH=src python -m pytest tests/test_artifact_reconcile.py tests/test_gates.py -q`

### T13 — FIX B: new `on_board_count` FSM gate type + switch consultation `PLANNING → DONE` to assert the seeded DAG

**Files:** `src/pathly_orchestrator/fsm/engine_transitions.py`,
`src/pathly_orchestrator/fsm_ops_complete.py`, `src/pathly_orchestrator/db/queries/comms_tasks.py`,
`src/pathly_orchestrator/db/queries/__init__.py`,
`src/pathly_data/core/flows/consultation.flow.yaml`, `tests/test_gates.py`

1. **comms_tasks.py `count_tasks_for_goal(conn, goal_id, *, boards=None, scopes=None) -> int`** —
   count non-deleted `type='task'` messages with the given goal_id (optional board/scope filter). Pure
   wrapped read; mirror `get_ready_tasks` param style. Re-export from `db/queries/__init__.py` (and the
   `comms.py` shim for consistency).
2. **engine_transitions.py** — change the signature to
   `evaluate_transition_rules(flow, current_state, storage_path, *, goal_id: str | None = None)`. Add
   **Level 2.6 — `on_board_count`**, evaluated AFTER `on_state_counter` (line 95) and BEFORE `decide`
   (line 97). YAML shape:
```
on_board_count:
  goal_scoped: true
  op: gt            # one of lt|lte|eq|gte|gt|ne (reuse the _ops table)
  compare_to: 0
  next: DONE
```
   **CRITICAL — `on_board_count`'s `compare_to` is a RAW INTEGER, NOT a state-doc field key.**
   `on_state_counter` does `int(state_doc[compare_to])` (line 91) and guards with `and compare_to`
   (line 85, truthy) — both would break a literal `compare_to: 0`. For `on_board_count`: read
   `compare_to` as `int(rule_value)` directly, and guard with `compare_to is not None` (NOT `and
   compare_to`), so `compare_to: 0` is honored (both adversarial corrections folded in). Implementation:
   if `goal_id is None` → SKIP (fall through; never blocks non-goal flows). Else lazily
   `from pathly_orchestrator.db.connection import get_db` +
   `from pathly_orchestrator.db.queries.comms_tasks import count_tasks_for_goal`; derive project_root
   via `storage_path.parent.parent.parent` (valid because storage is two components under pathly, incl.
   `pathly/goals/<slug>`); `count = count_tasks_for_goal(get_db(project_root), goal_id)`; if
   `op_fn(count, compare_to)` → return the rule's `next`. Wrap the DB call in try/except → on ANY error
   do NOT advance (fail-closed; a DB hiccup can't false-positive the gate). Still returns `str | dict`.
3. **fsm_ops_complete.py** — pass `goal_id` (read in T12) into `evaluate_transition_rules(flow_config,
   current_state, storage_path, goal_id=goal_id)`. No other caller changes (param is keyword-only with a
   None default); if `next_action`'s path also evaluates, pass `goal_id=None` there.
4. **consultation.flow.yaml** — switch the `PLANNING` rule (currently `on_content IMPLEMENTATION_PLAN.md
   '## Phase' -> DONE`) to assert the DELIVERABLE:
```
PLANNING:
  on_board_count:
    goal_scoped: true
    op: gt
    compare_to: 0
    next: DONE
  default: PLANNING
```
   **`transition_rules.PLANNING` and `transition_actions` are SIBLINGS** (consultation.flow.yaml:73-76)
   — replacing the PLANNING rule block must NOT drop the `transition_actions: PLANNING->DONE: [skill:
   archive-artifacts]` key (adversarial structure note folded in). Add a leading comment: Fix A removed
   the early-advance race; Fix B is the structural backstop — PLANNING completes only once the planner
   seeded >0 tasks for this goal, regardless of whether IMPLEMENTATION_PLAN.md or DAG_PLAN.md was the
   artifact.
5. **tests/test_gates.py** — `test_on_board_count_advances` (seed 1 `type='task'` row with goal_id=G via
   the comms_tasks/db helpers, call `evaluate_transition_rules(flow, 'PLANNING', storage, goal_id=G)`
   with the `on_board_count` rule → returns `'DONE'`); `test_on_board_count_blocks_when_zero` (no tasks →
   `'PLANNING'`); `test_on_board_count_skips_without_goal_id` (goal_id=None → skipped, falls to default,
   never raises); `test_on_board_count_db_error_does_not_advance` (monkeypatch count to raise → returns
   default). Use the existing `db.get_db()` harness with a tmp project_root.
6. Run `pathly-setup claude --apply --repair` + `python -m build` (consultation.flow.yaml is a seeded
   flow re-synced into the DB on server start; rebuild so all four adapters carry the updated seed).

**Acceptance:** `count_tasks_for_goal` returns the task count + re-exported; `evaluate_transition_rules`
gains keyword-only `goal_id`; Level 2.6 `on_board_count` evaluates between `on_state_counter` and
`decide`, reads `compare_to` as a raw int + guards `is not None` (honors `0`); `goal_id=None` skips, DB
error fails-closed; consultation `PLANNING->DONE` uses `on_board_count` (op gt, compare_to 0) and keeps
`archive-artifacts`; fsm_ops_complete passes goal_id through; all gate tests + existing test_gates pass;
adapters rebuilt. **Verify:**
`PYTHONPATH=src python -m pytest tests/test_gates.py -q && pathly-setup claude --apply --repair && python -m build`

---

## Deferred — PKG STUDIO: CardKind sidebar (renderer-only)

NOT authored in detail here. After the backend slug/scope split + artifact contract land, a
renderer-only package converts `loadFeatures` → `loadCards` and replaces the feature list with a
`CardSidebar` that distinguishes goal cards (`pathly/goals/<slug>`) from feature cards
(`pathly/plans/<slug>`) and other domains (`lessons`, `explorations`, `debugs`,
`pipeline-walkthrough`). No FSM/db changes; consumes the RESERVED-set + storage layout this plan
establishes. Scope it as a single Studio package when prioritized.
