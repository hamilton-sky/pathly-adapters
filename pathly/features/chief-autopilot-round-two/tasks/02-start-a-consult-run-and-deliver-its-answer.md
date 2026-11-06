# Start a consult run for a routed question and post its answer

Type: task
Status: resolved
Blocked by: 01
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/supervisor/consult_run.py (new), src/pathly_data/core/skills/planning/consult-answer.md (new), src/pathly_data/core/skills/composition.yaml, tests/runner_supervisor/test_consult_run.py (new), src/pathly_orchestrator/CLAUDE.md, src/pathly_data/CLAUDE.md, tests/INDEX.md, tests/runner_supervisor/INDEX.md, src/pathly_orchestrator/runner/provenance.py, tests/comms_board/test_comms_provenance.py, tests/comms_board/INDEX.md

The consult run itself: given a question that ticket 01's `route_decision` said to route, start a
one-shot headless agent of the role, read its answer, and post it. Not through
`supervisor/board_run.start_board_run`: it takes the board lock the asking goal run already holds,
and `board_run.py` is at its ratchet baseline (spec Decisions, "How a consult is spawned").

New skill `src/pathly_data/core/skills/planning/consult-answer.md` (new), with an entry in
`src/pathly_data/core/skills/composition.yaml` (fragments `code-query`, `comms-post`,
`completion-report`, like `planning/evaluate`). It tells the agent: you are the `<agent>` consulted
on one question; read the question, the asking task and the board below, and the code if you need
to; change nothing (you may write only under the `feedback/` folder named below, and you must not
commit); post no `answer` row yourself; end with the completion report whose `summary` starts with
exactly one of

```
ANSWER: <your answer, concrete and advice-only>
ANSWER: USER <why only the person can decide this>
```

and, for architect, po or designer only, may add one line `DECISION: <the approach chosen> — <why>`.
Use `ANSWER: USER` when the question is about what the person wants, money, an outside account,
or anything the board and code cannot settle.

New `src/pathly_orchestrator/supervisor/consult_run.py` (new) with
`start_consult(question_id, *, project_root, broadcast_fn, spawn_fn=None, block=False) -> dict`:

1. Read the question row, its route (ticket 01) and `consult_routes.asking_task`. Run id
   `consult-` + `secrets.token_hex(6)`; `set_route_status(..., "running", consult_run_id=...)`.
2. Compose the prompt: the skill body (`skills/compose.compose_skill("planning/consult-answer",
   adapter)`), `## The question` (id, from, text), `## The asking task` (its text, when there is
   one), the board context (`runner/comms_context.board_context_for(board, scope, project_root,
   question text, role=role)`) and the feedback folder (`<the board's storage>/feedback/`, from
   `fsm_ops._resolve_storage_path`). Substitute the placeholders with
   `fsm_compose._inject_prompt_vars(..., run_category="consult")`.
3. Spawn it as `board_run._default_spawn` does, without the lock: a headless `RunnerState`
   (`flow="consult"`, `current_state=<role>`, `board_scope=<scope>`, `timeout=600`,
   `executor_owned_telemetry=True`, `scope_tier`, a new trace id) and
   `terminal._run_stage_via_terminal`. Engine (spec Decisions, "Which engine and model a consult
   uses"): the adapter is `run_history.adapter` of the question's `author_run_id` (read it with one
   literal `SELECT adapter FROM run_history WHERE run_id = ?`) when
   `adapters.headless_capable(adapter)`, else `claude`; the model is
   `spawn_policy.effective_model(role, adapter, "")`, else `claude-sonnet-4-6` for claude and `""`
   (the engine's own default) for any other adapter. The spawn itself records the adapter in the
   consult's own `run_history` row.
4. Read the consult run's own `AGENT_DONE` (by its run id) and parse its summary: `ANSWER: USER`
   → `hand_to_person(why or "no reason given", by=role)`; `ANSWER: <text>` → post it with
   `comms_messages.post_message` as `type: answer`, `reply_to` the question, `from_agent` the role,
   `to_agent` the question's `from_agent`, stamped `author_role=<role>`,
   `author_run_id=<consult run>`, `author_source=token` (its `release_on_answer` frees the parked
   tasks), route `answered`; a `DECISION:` line from architect, po or designer → a `decision` row
   (binding 0, `reply_to` the question, same stamp). No `ANSWER:` line, a spawn that raised or
   timed out → `hand_to_person("the <role> consult did not answer: <reason>")`, route `failed`.
   Leave one call, `_measured_ok(...) -> bool` returning True, right before delivery: ticket 03
   fills it.

Document the consult run in `src/pathly_orchestrator/CLAUDE.md` (file list, the summary format)
and the new skill in `src/pathly_data/CLAUDE.md` (runner-only, not installed, like
`planning/consolidate`).

## Not in this ticket

- The read-only tree check and withholding: ticket 03. Calling `start_consult` when a question is
  posted: ticket 04.
- The `consult` category on the spawn payload, the synthetic `AGENT_DONE` and the invocation row,
  and the run token's role: ticket 16. The 403 on a consult's own `answer` post: ticket 17.
- Studio's Monitor showing the `consult` category: ticket 10. `GET /runs` kind `consult`: ticket 09.
- The `consult` fragment's "When you are consulted" paragraph: ticket 07 (consult runs do not
  compose that fragment).

## Done when

- `python -m pytest tests/runner_supervisor/test_consult_run.py -q -p no:cacheprovider` passes and
  covers, with a fake `spawn_fn` that writes the consult's `AGENT_DONE`: an `ANSWER:` summary posts
  one answer row (`from` architect, `reply_to` the question, `author_run_id` the `consult-` run)
  and frees a task parked on the question; the route ends `answered`; a `DECISION:` line from the
  architect adds a decision row with `binding` 0 and the same line from a tester adds none;
  `ANSWER: USER` makes the question `to: human` with the reason posted and posts no answer;
  no `ANSWER:` line and a raising spawn both hand the question to the person with route `failed`;
  the prompt holds the question, the asking task's text and the feedback folder and no raw
  `<run_category>`.
- In the same file: a question whose asking run's `run_history.adapter` is `codex` spawns the
  consult with adapter `codex` and the role's configured codex model (or `""` when none is
  configured); an asking run with no `run_history` row, or with an adapter that has no headless
  mode, spawns on `claude` with `claude-sonnet-4-6`.
- All existing tests under `tests/runner_supervisor`, `tests/install_skills` and
  `tests/consistency` (it scans the new skill's markdown) still pass.

```check
$ python -m pytest tests/runner_supervisor/test_consult_run.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/runner_supervisor tests/install_skills tests/consistency -q -p no:cacheprovider
exit 0
```

## Reference

- spec.md § Decisions ("How a consult is spawned", "Where the answer comes from", "Which engine and model a consult uses")
- `src/pathly_orchestrator/supervisor/board_run.py` (read-only: `_default_spawn`, `_inject_board_prompt_vars`)
- `src/pathly_data/core/skills/planning/evaluate.md`, `src/pathly_data/core/skills/fragments/completion-report.md`
- round one learnings (05): driving a whole board spawn in a test

## Answer

Work started at `8ce520a67eff69d2573c166a11fa15a5ade268a5` (restart after Touches gained
`tests/comms_board/INDEX.md`). Test-only commit `99c421b`: attempt 2's `eaaa878` cherry-picked
unchanged (attempt 1's `af46ab3` plus the `consult_stamp` tests in
`tests/comms_board/test_comms_provenance.py`); the code commit is attempt 2's `7a12cd5`.
Re-confirmed at `99c421b`: at that commit
`test_consult_run.py` fails at collection (`ImportError: cannot import name 'consult_run'`) and
the provenance file fails 7 tests (`cannot import name 'consult_stamp'`, and the new "only in
consult_run.py" scan finds no caller), 99 passing.

**Built**

- `src/pathly_orchestrator/supervisor/consult_run.py` (new, 357 lines), from attempt 1's
  `c9365f0`: `start_consult`, `parse_summary`, `consult_engine`, `build_prompt`, `_default_spawn`,
  `_measured_ok` (returns True), `_agent_done`, `_deliver`, `_fail`. Lazy imports only. Changed
  from attempt 1: `_deliver._post` stamps both rows with `**consult_stamp(role, run_id)` instead of
  three `author_*` keywords.
- `src/pathly_orchestrator/runner/provenance.py`: `consult_stamp(role, run_id) -> dict` beside
  `system_stamp` (role, run, `SOURCE_TOKEN`; `ValueError` unless the run id starts with
  `CONSULT_RUN_PREFIX` and the role is in `CONSULT_ROLES`, both imported lazily from
  `db/queries/consult_routes`); module docstring names it.
- `tests/comms_board/test_comms_provenance.py`: `_is_stamp_expr` accepts `consult_stamp` with
  exactly two positional (non-starred) arguments and no keywords; new
  `test_consult_stamp_is_called_only_where_the_consult_run_is_started` (every `.py` under the
  package; the set of calling files must be exactly `supervisor/consult_run.py`); five negative
  call-scan cases (one arg, three args, a keyword, `*args`, an extra `author_role=`) and one
  positive; `consult_stamp` unit tests (the dict; `ValueError` for `sched-T1#1`, `""`, `builder`,
  `human`, `""` role). `_UNSTAMPED_ALLOW` unchanged.
- `src/pathly_data/core/skills/planning/consult-answer.md` (new, runner-only, empty front matter,
  no `/comms` calls) and its `composition.yaml` entry (`code-query`, `comms-post`,
  `completion-report`).
- `tests/runner_supervisor/test_consult_run.py` (new, 10 functions / 13 cases).
- `src/pathly_orchestrator/CLAUDE.md`: file-list entry, a "Consult runs" section (summary format,
  delivery, engine), and `consult_stamp` in the author-provenance paragraph.
  `src/pathly_data/CLAUDE.md`: planning tree line, the manifest list, a runner-only note.
- `tests/INDEX.md`, `tests/runner_supervisor/INDEX.md`, `tests/comms_board/INDEX.md`: regenerated
  (the test count of `test_comms_provenance.py` changed, 58 -> 61). The changed-file set is
  exactly Touches plus this ticket, `map.md` and `learnings.md`.

**Proof**

- `python -m pytest tests/runner_supervisor/test_consult_run.py -q -p no:cacheprovider`:
  `13 passed`, exit 0. Covers: an `ANSWER:` summary posts one answer row (from architect, to
  builder, `reply_to` the question, `author_run_id` the `consult-` + 12 hex run, source `token`),
  the parked task goes `pending`, route `answered` with its `consult_run_id`; an architect
  `DECISION:` adds one decision row, binding 0, same stamp; a tester's adds none; `ANSWER: USER
  <why>` sets `to_agent` `human`, posts one status with the reason, no answer, task still
  `blocked` (and "no reason given" without a why); no `ANSWER:` line, no AGENT_DONE and a raising
  spawn each hand to the person with route `failed`; the prompt holds the question id and text,
  the task text, `<storage>/feedback`, no `<run_category>`, does not start with `---`.
- Same file, engine: codex asking run -> adapter `codex`, model `gpt-5-codex` (configured) or
  `""` (none); no `run_history` row and `copilot` -> `claude` + `claude-sonnet-4-6`.
- `python -m pytest tests/runner_supervisor tests/install_skills tests/consistency -q -p no:cacheprovider`:
  `893 passed, 2 skipped`, exit 0.
- `python -m pytest tests/comms_board/test_comms_provenance.py -q -p no:cacheprovider` (with the
  consult tests): `106 passed`, exit 0.
- Quick (commands.md), fresh at this restart: `5879 passed, 11 skipped`, exit 0. Lint chain exit 0 (black, mypy no issues, file size
  "none new, none grown", mirror reads OK, indexes up to date, lint-imports 1 kept 0 broken,
  bandit no findings, adapters + entry points OK). Smoke exit 0. Build exit 0 (wheel built, web
  typecheck clean).

**Decisions**

- Architect ruling (Consulted, recorded on `backup-02-attempt1`): the answer and decision rows are
  stamped by a named server stamp `runner/provenance.consult_stamp(role, run_id)` with
  `author_source=token`, not `system_stamp()` (it would set `author_run_id` None and lose the
  role as author) and not the token path (needs ticket 16, conflicts with ticket 17). The scan's
  `_is_stamp_expr` stays file-blind; a separate test pins the only caller to
  `supervisor/consult_run.py`; negative cases for a wrong arg count or keyword; `_UNSTAMPED_ALLOW`
  unchanged.
- `consult_stamp` also rejects `*args` in the scan (a starred argument could hide the count).
- Everything else as attempt 1 decided: only a `queued` route starts (else `{"started": False,
  "reason"}`); `spawn_fn` keywords `board, scope, prompt, run_id, project_root, model, adapter,
  agent, broadcast_fn`; the asking task is the route's `task_id` row, else `asking_task`; the
  AGENT_DONE is the newest one whose `run_id` is the consult run (one literal query); the first
  `ANSWER:` line, `USER` as the whole first word; empty answer = no answer; decision row first,
  then the answer, then route `answered`; on failure `set_route_status(failed)` then
  `hand_to_person(..., by="the server")`; `ANSWER: USER` uses `by=<role>`; placeholders are filled
  in the skill body only, never in board text.

**Shortcuts taken**

- The `queued` check and the switch to `running` are two statements; two concurrent
  `start_consult` calls for one question could both start. Ticket 04 is the only caller (once per
  recorded route). A conditional `UPDATE ... WHERE status='queued'` would make it exact.
- `_measured_ok` returning False only returns `withheld` (ticket 03 owns that branch).

**For later tickets**

- 03: `_measured_ok(question_id, run_id, *, role, project_root)` runs after parsing, before
  `_deliver`, in `_run_consult`; open the measuring window before `spawn_fn` there; the
  `withheld` branch needs its own route status and hand-off.
- 04: call `start_consult(qid, project_root=..., broadcast_fn=...)` after `record_route` returned
  True; the route must be `queued`.
- 11 (edits `test_comms_provenance.py` too): this ticket changed only `_is_stamp_expr`, the
  call-scan parametrize lists, and added the `consult_stamp` tests after the accept-list test and
  one scan test before `test_every_post_message_call_is_stamped_or_on_the_allow_list`. Any new
  caller of `consult_stamp` must be added to `_CONSULT_STAMP_FILES` (a reviewed guard change).
- 16: TERMINAL_SPAWN `category` is still `flow` for `flow="consult"`; the synthetic AGENT_DONE
  says `single`.
- 12/person: a real agent may put `DECISION:` on the same line as `ANSWER:` inside the
  completion-report string; it is then part of the answer text, not a decision row.
