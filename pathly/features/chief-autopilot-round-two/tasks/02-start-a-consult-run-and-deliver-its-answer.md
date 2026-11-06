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

Rework (review round 1, quality) started at `26f8a2e`. Test-only commit `557b30d`: 9 new cases in
`test_consult_run.py`, all failing at that commit for the findings' reasons (an answer posted
despite a second AGENT_DONE or a hand-off meanwhile, a second answer, the synthetic AGENT_DONE
taken over the agent's, a lost claim still spawning, `failed` overwriting `to_person`, the reason
lacking the spawn's exit code or error); 13 passed. One test bug fixed after that commit
(`monkeypatch.undo()` before reading the route back; the assertion is unchanged).

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

- Rework: `consult_run.py` (398 lines): `_move` (compare-and-set route move keyed on the consult
  run id; the claim and every end), `_status`, `_spawn_said`; `_agent_done` returns `(payload,
  why)` and refuses two non-synthetic AGENT_DONEs; `_deliver` re-reads the route and drops the
  result when it moved on, ends the route before posting, posts the answer before the decision;
  `_fail` only acts when its own move wins. `test_consult_run.py` +9 cases (22).
  `src/pathly_orchestrator/CLAUDE.md` "Consult runs" updated. `tests/runner_supervisor/INDEX.md`,
  `tests/INDEX.md` regenerated.

**Proof (rework, fresh at the rework commit)**

- `python -m pytest tests/runner_supervisor/test_consult_run.py -q -p no:cacheprovider`:
  `22 passed`, exit 0.
- `python -m pytest tests/runner_supervisor tests/install_skills tests/consistency -q -p no:cacheprovider`:
  `902 passed, 2 skipped`, exit 0.
- `python -m pytest tests/comms_board/test_comms_provenance.py -q -p no:cacheprovider`:
  `106 passed`, exit 0.
- Lint chain exit 0: black clean, mypy "no issues found in 364 source files", file size "none new,
  none grown", mirror reads OK, indexes up to date, lint-imports 1 kept 0 broken, bandit clean,
  adapters OK, entry points OK.

**Proof (round 0)**

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

- (Rework) A forged `AGENT_DONE` for a consult whose own agent writes none is still read and
  delivered: `/runner/event` takes any payload with no token, and completion-report's fallback
  writes the DB directly. Closing it needs an `AGENT_DONE` bound to the consult's run token at
  `/runner/event` (and `completion-report` sending the token), outside this ticket's Touches; an
  architect call (see Review fixes 1).
- `consult_run.py` is at 398 lines (limit 400): ticket 03 adds `_measured_ok`'s body, so 03 will
  need to put its measuring code in its own module.
- `_measured_ok` returning False only returns `withheld` (ticket 03 owns that branch).

**Review fixes**

1. Forged answer (major): partly fixed inside Touches. `_agent_done` now takes the consult's
   AGENT_DONE only when the agent wrote exactly one (the supervisor's `synthetic: true` one is
   used only when the agent wrote none); a second one fails the consult (`more than one AGENT_DONE
   carries its run id`) and hands the question to the person. Tests:
   `test_a_second_agent_done_for_the_consult_run_fails_it`,
   `test_a_synthetic_agent_done_beside_the_agents_own_is_not_a_second_one`. Not closed: when the
   real agent writes none, a forged one is still read. The returned result of
   `_run_stage_via_terminal` is no independent source (on early advance it is itself read from the
   newest DB AGENT_DONE of the storage; on PTY exit it is the CLI envelope, not the summary), and
   binding AGENT_DONE to the run token needs `/runner/event` and `completion-report`, outside
   Touches and against spec Decisions "Where the answer comes from" as written. Raised for the
   architect (and tickets 16/17, which own the consult token's role and the 403).
2. Check-then-set start (major): fixed. The claim is `UPDATE ... SET status='running',
   consult_run_id=? WHERE question_id=? AND status='queued'`, rowcount checked; a lost claim
   returns `{"started": False, "reason": "another start claimed the route"}` and spawns nothing.
   Test: `test_a_start_that_loses_the_claim_spawns_nothing`.
3. Moved-on question (minor): fixed. Every end is a compare-and-set from this run's `running`;
   `_deliver` returns the current status without posting when the route is no longer `running`,
   and when an answer already replies to the question it ends the route `answered` and posts
   nothing; `_fail` hands nothing on when its move loses. Tests:
   `test_a_question_handed_to_the_person_meanwhile_gets_no_answer`,
   `test_a_question_answered_meanwhile_gets_no_second_answer`,
   `test_a_spawn_that_fails_after_the_question_moved_on_keeps_its_end`.
4. Orphan decision (minor): fixed. The answer is posted first; a failed answer post moves the route
   `answered` -> `failed` and hands the question on, and no decision is posted; a failed decision
   post after the answer only logs. Test: `test_a_failed_answer_post_leaves_no_decision_row`.
5. Spawn result ignored (minor): fixed. With no AGENT_DONE the reason adds the returned non-zero
   `exit_code` or `error` (`no AGENT_DONE (exit code 3)`). A non-zero exit already raised
   `terminal_exit_nonzero` in `_run_stage_via_terminal`, which the reason names. Test:
   `test_no_agent_done_names_what_the_spawn_returned`.

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

## Review findings (round 1, quality review)

Reviewed 8ce520a..b341060 (END is HEAD; no later commits left out). I read the ticket at the base commit, so I did not see its Answer. Both Done when commands passed when I re-ran them (13 passed; 893 passed, 2 skipped), and so did tests/comms_board/test_comms_provenance.py (106 passed). The tree is clean afterwards. This is a level 3 review. Inputs probed: the question row (text, from_agent, author_run_id), the route (status, task_id, role), the asking run's run_history.adapter, the consult's AGENT_DONE summary (ANSWER/USER/DECISION parsing), the question and task text placed in the prompt, and concurrent calls to start_consult.

QUALITY
1. major src/pathly_orchestrator/supervisor/consult_run.py: anyone can forge the answer. start_consult delivers the newest AGENT_DONE whose payload.run_id is the consult run. POST /runner/event has no authentication and accepts any payload, and the consult-<hex> run id can be read through run_history (GET /runs, GET /runs/<id>). So any agent on the machine, including the builder that asked, can append an AGENT_DONE with that run_id during the spawn's window, up to 600 s. The server then posts that text as the architect (or po, or designer), with author_source=token and an optional DECISION row, and frees the parked tasks. This gets around the very check that ticket 17's 403 is meant to protect, and it breaks consult_stamp's claim that the row comes from the consult run. Fix: take the summary only from a result the consult spawn itself produced. That can be the result _run_stage_via_terminal returns (it is ignored now), or an AGENT_DONE written with the consult's own run token. At the least, fail the consult when more than one AGENT_DONE carries the run id. If changing the spec's "Where the answer comes from" is out of scope here, raise it with the architect.
2. major src/pathly_orchestrator/supervisor/consult_run.py: start_consult reads status == "queued" and then calls set_route_status(..., "running"). That UPDATE has no condition, and its return value is ignored, so the check and the set are not atomic. Two callers for the same question, for example ticket 04's post hook racing a retry or a second post path, both pass the check. Both then spawn a consult (twice the cost, which gets past the consult caps) and both post an answer. Fix: claim the route with a compare-and-set (UPDATE ... SET status='running' ... WHERE question_id=? AND status='queued', checking rowcount) and return started False when the claim loses.
3. minor src/pathly_orchestrator/supervisor/consult_run.py: _deliver and _fail do not check that the route is still `running` with this consult_run_id before they post and set `answered` or `failed`. A question that was handed to the person or answered while the consult ran gets a second answer, and its end status is overwritten. Fix: re-read the route and the question before delivering, and drop the result if either has moved on.
4. minor src/pathly_orchestrator/supervisor/consult_run.py: the DECISION row is posted before the answer row. If the answer post then fails, the route becomes `failed` and the question goes to the person, but the orphan decision stays on the board. Fix: post the answer first, or remove the decision on failure.
5. minor src/pathly_orchestrator/supervisor/consult_run.py: _run_consult throws away the spawn's return value. A consult that exits non-zero with no AGENT_DONE is reported only as "no AGENT_DONE". Fix: put the exit code or error from the returned dict into the failure reason.

REVIEW: FAIL
