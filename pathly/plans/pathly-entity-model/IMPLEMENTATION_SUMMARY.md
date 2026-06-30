# Entity-Model DAG — Implementation Summary

**Goal:** `3434d44d` — *Implement: scope/slug split + composition hygiene + artifact contract + Fix B*
**Branch:** `fix/goal-executor-cwd` (LOCAL, unpushed — awaiting review)
**Status:** All 13 tasks complete. Full suite **963 passed / 5 skipped / 0 failed**.
**Date:** 2026-06-30

This goal is also the delivery vehicle for **unified-cli-composition Gate 2** (composition hygiene). The two old composition goals (`d4dcbb6d`, `cbb3462b`) are superseded into this one; shared deliverables live in `core/skills/`.

## The core bug fixed

`topic=scope` in `_resolve_storage_path` could be an absolute Windows path (e.g. `C:\Users\Yafit\pathly-adapters`). `Path(project_root) / "pathly" / topic` then collapsed back to that absolute path, so goal runs looped forever writing nowhere. The fix routes goal runs through a filesystem-safe **slug** that is distinct from the board **scope**.

## What shipped, by phase

### P0 — fail-safe foundation (T1–T3)
- **New leaf module** `src/pathly_orchestrator/storage_paths.py` (stdlib-only): `_is_unsafe_topic` / `_safe_topic`. Wired into both path resolvers (`fsm_ops._resolve_storage_path`, `runner/argv._storage_path`).
- **`comms_messages.slug`** TEXT column + partial UNIQUE index (`WHERE slug IS NOT NULL`) in `migrations_incremental.py`.
- Windows caveat handled: `os.path.isabs("/foo")` is `False` on Windows, so the guard also checks `topic.startswith("/")`.

### P1 — slug routing (T4–T6)
- **`supervisor/slug.py`** — `ensure_goal_slug` (collision-safe, idempotent under the write-lock).
- `_safe_topic` flipped **WARN → RAISE** (a guard hit = an already-looping run, so a loud escalate beats a silent forever-loop).
- `_resolve_storage_path` **3-tier probe**: `pathly/<topic>` → `pathly/goals/<topic>` → `pathly/plans/<topic>` (preserves the 2-component watcher-depth invariant).
- `storage_path` added to `RunnerState` + `public_dict()`; all goal call sites pass `topic=slug` (board-lock / `get_state` still use scope).
- Studio `commsStore.ts` **RESERVED** set extended (`goals`, `lessons`, `explorations`, `debugs`, `pipeline-walkthrough`) so goal dirs don't surface as phantom features.

### GATE2 — composition hygiene (T7–T10)
- **`build_adapter_caps(adapter, *, goal_id, executor, kind)`** + `goal_id` added to `_KNOWN_CAPABILITIES`; caps thread through `start_board_run` / `_compose_skill_body`.
- New fragments **`task-dag-post.md`** + **`board-start-context.md`** (both gated `requires: goal_id`).
- New agnostic skill **`planning/dag-sketch.md`** (no board strings in the body — connection comes only from fragments).
- `_decompose_planner` rerouted `skill="" → "planning/dag-sketch"`; `plan.md` Step 6 inline task-POST moved into the fragment.
- T10 (Summary ActionPill error state) was already implemented — board-marked only.

### P2 — artifact contract + Fix B (T11–T13)
- **`artifact-manifest.yaml`** (9-role allow-list + `planner.planning/dag-sketch → DAG_PLAN.md` override) + pure `manifest_role_file()` / `load_artifact_manifest()` (no DB — importable by FSM gates).
- **`fragments/artifact-register.md`** — write `<out_path>` + append `ARTIFACTS.jsonl` + advisory board POST, **no FSM call**. Attached to exactly 7 pipeline skills, never as the last fragment. `<out_path>` substitution wired in `fsm_compose._inject_prompt_vars`.
- **`ensure_attached`** idempotent reconciler (injected `broadcast_fn`; db layer imports no `http_server`) + **`reconcile_artifacts`** in a NEW `supervisor/artifact_reconcile.py` (terminal.py was already over the 400-line limit, so it was not grown). `find_or_create_artifact_by_path` now accepts `/pathly/goals/`. `board`/`scope`/`goal_id` threaded into `/complete_stage` (defaults `feature` / `topic` / `None`).
- **Fix B:** new Level-2.6 **`on_board_count`** FSM gate (`count_tasks_for_goal`; raw-int `compare_to` that honors `0`; `goal_id=None` skips; DB error fails-closed). Consultation `PLANNING → DONE` switched from "IMPLEMENTATION_PLAN.md exists" to "goal has tasks > 0" — killing the "decompose seeded 0 tasks" class of bug.

## Bonus fix (not in the DAG)
The pre-existing `fsm_ops ↔ fsm_ops_complete` circular import (a bottom-of-file `# noqa: E402` re-export that only worked when `fsm_ops` was imported first) was replaced with a PEP-562 module `__getattr__` lazy re-export of `complete_stage`. Both import orders now work; the 5+ `from ...fsm_ops import complete_stage` call sites are unaffected.

## Verification
- `tests/test_compose.py` 60 · `tests/test_gates.py` 25 · `tests/test_artifact_reconcile.py` 5 — all green.
- Full suite: **963 passed / 5 skipped / 0 failed** (`test_dag_scheduler::test_diamond_dag_parallelism` is a known flaky timing test under load — passes in isolation).
- Circular-import fix verified: `fsm_ops_complete`-first import now succeeds; re-export still resolves in every order.

## Not done (out of scope)
- No `pathly-setup --apply --repair` / `python -m build` run yet — deferred so adapter propagation is a single deliberate pass after review.
- Nothing pushed — branch is local pending your review.
