# Do not read another role's plan-file write as the builder's when a run recorded no spawn windows

Type: task
Status: resolved
Blocked by: —
Test first: yes

`floor_gate` calls a changed file under the run's board home a `plan-edit` unless the builder
stage may write it or a `SPAWN_WINDOW` whose role may write it explains it
(`fsm/gates/floor.py::_may_change`). Only the supervisor records `SPAWN_WINDOW` events
(`supervisor/spawn_window.py`), so an interactive `/pathly` run has none. There the reviewer's
`REVIEW.md`, a retro document or a planner's plan edit is never explained: the gate blocks
`REVIEWING->TESTING` with `FLOOR_FAILURES.md`, routed to the builder, who did not write the file
and cannot undo the reviewer's output. The only way out today is the `floor.enabled` setting set
to `false`, which turns off the whole guard (`src/pathly_orchestrator/CLAUDE.md`, "Floor gate",
Limits). Headless runs are not affected: every supervised single-path spawn records a window.

**The change.** In `_may_change` (`fsm/gates/floor.py`), `windows()` already has a fail-open
branch for windows that cannot be read: `may_change` returns `any_role(path)`, so a path some
role may write is excused and a note goes to `FLOOR_CHECKED.warnings`. Add the same branch for
windows that were read and are **empty**: when `_proof.windows_since(storage_path, started_at)`
returns no event at all, return `any_role(path)` and add one note, once, saying that the run
recorded no spawn windows, so plan files a role may write were not judged. Keep the two notes
distinct (unreadable windows versus none recorded).

What stays as it is:

- With one or more windows since the base, nothing changes: `_proof.explained` decides, so a
  builder's plan edit is still a finding even when another role's window exists (the existing
  `test_a_plan_edit_blocks_unless_a_planner_window_explains_it` and
  `test_a_builder_edit_after_the_planner_is_still_a_plan_edit` keep passing unchanged).
- A path no role may write (`_proof.any_role_writes` is false) is a `plan-edit` with or without
  windows.
- Every other category (`skip`, `suppress`, `test-delete`, `config`, `task-edit`, ...) is
  judged exactly as before in a run with no windows.
- A goal-loop drain records no windows either, and its tasks' own plan edits are already caught
  by the per-task proof (`supervisor/task_proof.py`, `protected=[board home]`, one failed
  attempt each), so skipping the join's plan-edit judgement for a drain with no feedback spawn
  loses nothing the proof did not see.

Living docs, same change:

- the third bullet of the module docstring of `fsm/gates/floor.py` (`plan-edit`);
- the `plan-edit` bullet and the Limits paragraph of "Floor gate" in
  `src/pathly_orchestrator/CLAUDE.md`: say what the gate does with no windows, drop "set
  `floor.enabled` to `false` for such a run", and keep the remaining limit (a plan edit by the
  builder in a run with no windows goes unseen, as `scope_gate` already says for its own case);
- the last "Known limits" sentence of the build-proof entry in `CHANGELOG.md` (it names
  `scope_gate` and `reviewer_unchanged` for interactive runs; add `floor_gate`'s plan files).

Tests go in a new file, `tests/fsm_flows/test_floor_gate_no_windows.py`
(`test_floor_gate.py` is at 393 lines). Reuse the helpers of `review_packet_support` and drive
the real `next_action` and `complete_stage` over `team-build` as `test_floor_gate.py` does,
but write the files with `_write`, not `_as(...)`, which records a window, so the run never
records one (the task `_claim()` posts declares `src/app.py`, which the BUILDING edit changes).
Do not put a skip marker, a `noqa` or any other text the floor guard matches into the test
source: this ticket has no `Floor:` line. The cases, each at `REVIEWING->TESTING` after a build
whose files were written directly:

1. `REVIEW.md` written: `floor_gate` does not block, no `FLOOR_FAILURES.md` exists, and the
   `FLOOR_CHECKED` event carries the "no spawn windows" note;
2. `USER_STORIES.md` (a plan document a planner may write) edited: the same;
3. the committed test file deleted: blocked with a `test-delete` finding;
4. a file nested one folder below the board home, which no role may write: blocked with a
   `plan-edit` finding;
5. one window recorded (a builder window over `src/app.py`, written with `_as(...)`), then a
   plan file edited outside any window: blocked with a `plan-edit` finding (windows exist, none
   explains it).

If a gate other than `floor_gate` blocks the edge for a reason of its own in a run with no
windows, say so in the Answer; do not widen this ticket to fix it.

## Not in this ticket

- Recording spawn windows for interactive runs: the `/pathly` skills would need a hook, and
  that is a separate decision.
- `scope_gate` and `reviewer_unchanged` in interactive runs: their own limits stay as written
  (map.md § Open questions).
- Any change to `floor.enabled`, to the floor categories or to the supervised flows.

## Done when

- `python -m pytest tests/fsm_flows/test_floor_gate_no_windows.py -q -p no:cacheprovider`
  passes.
- `python -m pytest tests/fsm_flows/test_floor_gate.py tests/fsm_flows/test_proof_base.py tests/dag_goals -q -p no:cacheprovider`
  still passes.
- `python scripts/check_file_size.py` exits 0 and `python scripts/gen_test_index.py --check`
  exits 0.
- The stale sentence is gone from `src/pathly_orchestrator/CLAUDE.md`.

```check
# The conductor runs this block before review.
$ python -m pytest tests/fsm_flows/test_floor_gate_no_windows.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/fsm_flows/test_floor_gate.py tests/fsm_flows/test_proof_base.py tests/dag_goals -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_file_size.py
exit 0
$ python scripts/gen_test_index.py --check
exit 0
$ python -c "import pathlib;t=pathlib.Path('src/pathly_orchestrator/CLAUDE.md').read_text(encoding='utf-8');print('clean' if 'set `floor.enabled` to `false` for such a run' not in t else 'still there')"
exit 0
prints clean
```

## Reference

- `src/pathly_orchestrator/fsm/gates/floor.py` (`_may_change`), `fsm/gates/_proof.py`
  (`windows_since`, `explained`, `any_role_writes`, `stage_writes`),
  `supervisor/spawn_window.py` (who records windows)
- `src/pathly_orchestrator/CLAUDE.md` § Spawn windows and stage writes, § Floor gate (Limits)
- `tests/fsm_flows/test_floor_gate.py` (`proj`, `_as`, `_edit`, `_events`, `_assert_floor_block`),
  `tests/fsm_flows/review_packet_support.py`
- map.md § Decisions so far (06), § Open questions

## Answer

**Built**

- `src/pathly_orchestrator/fsm/gates/floor.py`: in `_may_change`, `windows()` now adds one note
  ("the run recorded no spawn windows: plan files a role may write were not judged") when the
  windows were read and are empty, and `may_change` returns `any_role(path)` for both an
  unreadable (`None`) and an empty window list (`if not found`). The unreadable note is unchanged
  and distinct. With one window or more, `_proof.explained` decides as before. The function
  docstring and the third bullet of the module docstring say so.
- `src/pathly_orchestrator/CLAUDE.md`: the `plan-edit` bullet of "Floor gate" (what happens with
  no windows, the two warning texts, windows decide once one exists) and the Limits paragraph
  (the stale "set `floor.enabled` to `false` for such a run" sentence is gone; the remaining
  limit is a builder's plan edit going unseen in a run with no windows, as for `scope_gate`; the
  goal-loop drain case).
- `CHANGELOG.md`: the last "Known limits" sentence of the build-proof entry now names
  `floor_gate`'s plan files.
- `tests/fsm_flows/test_floor_gate_no_windows.py` (new, 169 lines) plus the regenerated
  `tests/INDEX.md` and `tests/fsm_flows/INDEX.md`. Test-only commit 19f743a ("test(build-proof):
  17 failing test"): 3 of its 6 tests failed there (the three "no windows, not a plan-edit"
  cases, each at its `next_state == "TESTING"` assertion); for the `REVIEW.md` case I read the
  block itself: `floor_gate` failed with `plan-edit: pathly/features/demo/REVIEW.md: a protected
  plan file was changed`, the right reason. The other 3 pin what must not change and passed at
  that commit.

**Proof**

- `python -m pytest tests/fsm_flows/test_floor_gate_no_windows.py -q -p no:cacheprovider`: exit 0,
  `6 passed`. The cases: `REVIEW.md` written, `USER_STORIES.md` edited and both together (one
  note, not two) pass with the note and no `FLOOR_FAILURES.md` and no `SPAWN_WINDOW`; the deleted
  committed test is blocked with `test-delete: tests/test_calc.py`; a file one folder below the
  board home (`pathly/features/demo/notes/NOTES.md`) is blocked with `plan-edit`; with one builder
  window recorded (`_as`), a plan file edited outside any window is blocked with `plan-edit` and
  `FLOOR_CHECKED` carries no "no spawn windows" note.
- `python -m pytest tests/fsm_flows/test_floor_gate.py tests/fsm_flows/test_proof_base.py tests/dag_goals -q -p no:cacheprovider`:
  exit 0, `285 passed in 77.40s`. The two tests the ticket names
  (`test_a_plan_edit_blocks_unless_a_planner_window_explains_it`,
  `test_a_builder_edit_after_the_planner_is_still_a_plan_edit`) are in that run, unchanged.
- `python scripts/check_file_size.py`: exit 0 (`19 known over 400 lines, none new, none grown`);
  `python scripts/gen_test_index.py --check`: exit 0 (`All test INDEX.md files up to date.`).
- The stale-sentence one-liner prints `clean`, exit 0.
- Beyond the Done when: the full Test command (`python -m pytest tests/ -q -x -p no:cacheprovider`)
  exit 0, `2924 passed, 14 skipped in 535.96s` (the 14 skips are existing tests); the whole Lint
  chain from `commands.md` exit 0 (black, mypy, file size, mirror reads, test index, lint-imports,
  bandit, adapters, entry points).

**Decisions**

- The no-windows note is added lazily, inside `windows()`, so it appears only when some path
  needed the windows (a plan file a role may write changed). A run with no windows and no changed
  plan file gets no note, which matches the existing unreadable note and keeps
  `test_a_clean_build_passes_and_records_the_check` (`warnings == []`) true.
- "No windows" means none since the base (`windows_since(storage, started_at)`), as the ticket
  says; a window recorded before the base does not count.
- The test fixture commits a passing `REVIEW.md` so that `verify_gate` passes without a
  `REVIEW.md` change, which isolates case 2 (the stories edit) from case 1 (the review write).
  Cases 1, 2 and 3-5 write files directly with `_write`; only case 5 uses `_as`.

**Shortcuts taken**

none.

**For later tickets**

- No other gate blocked `REVIEWING->TESTING` for a reason of its own in a run with no windows:
  `reviewer_unchanged` has no reviewer window to judge and `task_checks` finds no block. One
  correction to the ticket text: the task `_claim()` posts declares no `files`, so at
  `BUILDING->REVIEWING` `scope_gate` skips with `no_declared_scope` (and `command_gate` with
  `no_command_configured`); the BUILDING edit of `src/app.py` is not judged against a scope.
- The remaining limit, now written in the Limits paragraph: in a run with no windows (an
  interactive `/pathly` run, a goal-loop drain's join) a plan edit by the builder itself goes
  unseen by `floor_gate`, as `scope_gate` already says for its own case.
- Ticket 18 is independent of this one. No later ticket becomes wrong.
