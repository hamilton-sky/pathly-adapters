# Start a consult run for a routed question and post its answer

Type: task
Status: open
Blocked by: 01
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/supervisor/consult_run.py (new), src/pathly_data/core/skills/planning/consult-answer.md (new), src/pathly_data/core/skills/composition.yaml, tests/runner_supervisor/test_consult_run.py (new), src/pathly_orchestrator/CLAUDE.md, src/pathly_data/CLAUDE.md, tests/INDEX.md, tests/runner_supervisor/INDEX.md, src/pathly_orchestrator/runner/provenance.py, tests/comms_board/test_comms_provenance.py

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
