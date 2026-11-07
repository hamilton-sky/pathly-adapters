# Refuse a decompose's task that has no check block and no `Check: none` reason

Type: task
Status: resolved
Blocked by: —
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/http_server/blueprints/comms/messages_write.py, src/pathly_orchestrator/http_server/blueprints/comms/_task_post_lint.py (new), src/pathly_data/core/skills/fragments/task-dag-post.md, src/pathly_data/core/skills/planning/dag-sketch.md, tests/snapshots/, tests/comms_board/test_decompose_check_lint.py (new), src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/comms_board/INDEX.md

Plan lint (feature-flow 0.8.0): every task the server will prove needs something to prove. Today a
planner can post a task with no ```check block and `task_checks` and `task_proof` simply have
nothing to run.

New `src/pathly_orchestrator/http_server/blueprints/comms/_task_post_lint.py` (new):

- `task_check_refusal(text: str) -> str | None`: None when the text holds at least one ```check
  block with at least one command (`proof/checks.checks_in`), or a line that starts with
  `Check: none` followed by a reason (any non-space text after an optional `-`, `—` or `:`);
  the `ParseError` message when a block does not parse; otherwise
  `task has no check block and no "Check: none <why>" line`.
- `ref_warning(data, context_refs) -> str | None`: the non-blocking `ref_warning` text that
  `messages_write.comms_post` builds today for a task with no `context_refs` and no `no_refs`,
  moved here unchanged.

In `messages_write.comms_post` (400 lines: moving the `ref_warning` block out pays for the new
lines), before `_post_message` and only for `type: task`: when `caller_identity(request)` is a live
run token whose role is `planner` (the `planning/dag-sketch` and `planning/plan` board runs carry
`agent="planner"`, and the consultation flow's planner stage resolves to `planner`), call
`task_check_refusal`; a refusal answers 422 `{"error": "<the refusal>", "reason": "a decompose
must post each task with its check block or a 'Check: none <why>' line", "task": "<the text's
first line, at most 80 characters>"}` and stores nothing. A tokenless caller (the person, an
interactive session), a chief token and any other role post as today (the brief's assumption).
Many tests post `"from": "planner"` with no token: they are unaffected, since the role is read from
the token, never from the body. A test whose fake planner posts with a planner run token and no
check gets a `Check: none - test fixture` line in its task text.

Fragments: `src/pathly_data/core/skills/fragments/task-dag-post.md` now says a phase marked
`Check: none - <why>` posts that line at the end of the task `text` (today: "posts no block"),
and that a task without either is refused with 422 and must be posted again with it.
`src/pathly_data/core/skills/planning/dag-sketch.md` says the same for its tasks. Regenerate the
golden snapshot that composes `task-dag-post` (`tests/snapshots/planning__plan.claude.md`; round
one learnings 03).

## Not in this ticket

- Tasks posted by hand by the person or the chief: unchanged.
- Re-running a decompose whose planner gave up after a 422: the decompose run ends as it does today
  and the person sees the refusals in the run's log.

## Done when

- `python -m pytest tests/comms_board/test_decompose_check_lint.py -q -p no:cacheprovider` passes
  and covers: a planner-token task with no block is 422 and no row is stored; with a check block
  it is 200; with `Check: none - docs only` it is 200; with `Check: none` and no reason it is 422;
  a block that does not parse is 422 with the parser's message; a tokenless, a chief-token and a
  builder-token checkless task are 200; a task with no `context_refs` still gets its
  `ref_warning`.
- `python -m pytest tests/install_skills -q -p no:cacheprovider` passes with the regenerated
  snapshot.
- All existing tests under `tests/comms_board`, `tests/dag_goals` and `tests/http_api` still pass.

```check
$ python -m pytest tests/comms_board/test_decompose_check_lint.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/install_skills -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/comms_board tests/dag_goals tests/http_api -q -p no:cacheprovider
exit 0
```

## Reference

- spec.md § Decisions ("Where the plan lint runs")
- `src/pathly_orchestrator/proof/checks.py`, `src/pathly_orchestrator/supervisor/goal_decomposer.py` (read-only)
- `src/pathly_data/core/skills/planning/plan.md` (its `Check: none - <why>` rule, read-only)

## Answer

- **Built**: new `src/pathly_orchestrator/http_server/blueprints/comms/_task_post_lint.py`
  (`task_check_refusal`, `ref_warning`, plus `decompose_refusal(identity, msg_type, text)` that
  builds the 422 body and `task_title`); `messages_write.comms_post` calls `decompose_refusal`
  before `_post_message` and `ref_warning` at the end (399 -> 398 lines, was 400);
  `fragments/task-dag-post.md` and `planning/dag-sketch.md` text; `src/pathly_orchestrator/CLAUDE.md`
  `POST /comms/post` line; new `tests/comms_board/test_decompose_check_lint.py` (17 tests);
  `tests/INDEX.md`, `tests/comms_board/INDEX.md` regenerated.
- **Proof**: `pytest tests/comms_board/test_decompose_check_lint.py` 17 passed (failing commit
  ec42dea: 8 failed for the missing module / no 422); it covers planner no-check 422 + no row,
  check block 200, `Check: none - docs only` 200 (and `—`, `:`), bare `Check: none` / `-` / `—` 422,
  empty block 422, unparseable block 422 with `str(ParseError)`, tokenless / chief / builder 200,
  planner non-task not linted, `ref_warning` on a refless task. `pytest tests/install_skills`
  419 passed, 2 skipped. `tests/comms_board tests/dag_goals tests/http_api`: 4450 passed, exit 0.
  Full `tests/`: 6795 passed, 1 failed (`test_build_proof_acceptance.py::test_8_happy_path_goal_loop_reaches_done`,
  FLOOR_CHECKED missing = the known event-mirror/`git add -A` floor flake, learnings 04/06; the
  previous full run passed it, and 3 isolated reruns of the file pass 11/11). black, mypy,
  check_file_size, gen_test_index --check, lint-imports, bandit clean.
- **Decisions**: the role comes only from `caller_identity(request)` (kind `run`, role
  `planner`). The route still calls `caller_identity(request)` inline in `stamp(...)` (a second
  lookup): the provenance scan (`test_every_post_message_call_is_stamped_or_on_the_allow_list`)
  accepts only the literal `stamp(caller_identity(request))` form. A ParseError wins over a
  `Check: none` line (a broken block is reported as such). An empty ```check block counts as no
  check. `Check: none` must be at a line start and followed by whitespace, a separator or the line
  end (`Check: nonesense` is no reason). `proof.checks` is imported lazily inside the function.
- **Shortcuts taken**: none. No snapshot changed: `task-dag-post` is gated on `goal_id` and no
  golden snapshot composes it, so none was regenerated.
- **For later tickets**: a test whose fake planner posts tasks over HTTP with a planner run token
  needs a check block or `Check: none - <why>` line in the text; none exists today.
