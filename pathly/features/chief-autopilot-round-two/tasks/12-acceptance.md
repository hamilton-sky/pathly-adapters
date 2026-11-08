# Acceptance: agents answer agents, and only the person's questions reach the person

Type: task
Status: open
Blocked by: 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 14, 15, 16, 17, 18
Test first: no
Level: 1
Touches: tests/comms_board/test_autopilot_round_two_acceptance.py (new), tests/comms_board/autopilot_round_two_support.py (new), tests/INDEX.md, tests/comms_board/INDEX.md

Write `tests/comms_board/test_autopilot_round_two_acceptance.py` (new; fake spawn host, fake
agent processes, the server in process, as `tests/comms_board/test_autopilot_round_one_acceptance.py`
does, reusing `tests/comms_board/autopilot_acceptance_support.py`'s `AgentHost` and readers). Put
the new fake agents in `tests/comms_board/autopilot_round_two_support.py` (new): a loop task agent
and a drain-dag agent that post a question `to: architect` with their run token, and a fake
consult agent for `consult-` spawns that writes its `AGENT_DONE` with a summary the test chooses
(`ANSWER: ...`, `ANSWER: USER ...`, or an answer after editing a source file).

Run the bar end to end, through the real routes, router and supervisor:

1. A **loop** goal (`executor: loop`) whose task's first attempt asks the architect: exactly one
   consult run (`consult-…`, category `consult`, one `agent_invocations` row) answers; the router
   posts the answer (`from: architect`, `reply_to` the question); the task is run again in the
   same goal-loop run as `sched-<task>#2` with the question and answer in its prompt, and the run
   ends `success`.
2. A **single** goal whose drain-dag agent asks the architect and leaves its task unfinished: one
   consult run answers; the task is `pending` with `answered_questions` and the run reads
   `answer_ready` (or `waiting_for_answer` when the answer comes after the run settled, then the
   answer frees it); the chief starts the goal again and the agent's ready row carries the
   question and answer; it finishes.
3. A second question that the architect answers `ANSWER: USER <why>`: the question is `to: human`,
   the task is parked, and `GET /chief/notices` lists the run with that consult `to_person` and
   `waiting_for_person: 1`.
4. A fourth routed question on one task goes to the person with no consult spawn.
5. A consult agent that edits a source file: no answer row, route `withheld`, an escalation lists
   the file, the task stays parked for the person.
6. The parked loop run of step 3 reads `outcome: failed`, `error: waiting_for_answer` in
   `GET /runs/<id>`; `GET /runs` lists the consult runs as `kind: consult`.
7. A planner-token decompose post of a task with no check block is 422 and stores nothing.

Then run the whole suite once.

## Not in this ticket

- A real claude or codex: the person re-measures one consult on their machine (map Open
  questions).

## Done when

- `python -m pytest tests/comms_board/test_autopilot_round_two_acceptance.py -q -p no:cacheprovider` passes.
- `python -m pytest tests/ -q -p no:cacheprovider` passes.

```check
$ python -m pytest tests/comms_board/test_autopilot_round_two_acceptance.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/ -q -p no:cacheprovider
exit 0
```

## Reference

- map.md § The bar, spec.md § Happy path
- `tests/comms_board/test_autopilot_round_one_acceptance.py`, `tests/comms_board/chief_acceptance_support.py`
- round one learnings (09): a Flask test client used from another thread needs its own `app.test_client()`

## Answer

## Attempt note

Attempt 1 (2026-11-08, base 619eb87): the acceptance test was written (support module + 6 tests
for the 7 steps; steps 3 and 6 share one test) and it fails on three real bugs outside Touches.
Nothing is committed but this note: the draft test would turn `tests/comms_board` red for every
later ticket. A scratch run with the three bugs patched in the test only (patches not kept)
passes all 6 tests in ~7 s, so the draft is right and these three bugs are all that stand in its way.

1. **Every server-routed consult dies with a TypeError.**
   `src/pathly_orchestrator/http_server/consult_trigger.py:57` passes
   `broadcast_fn=sse._broadcast_spawn`, which takes one argument (`sse.py:176`,
   `_broadcast_spawn(payload)`), but the consult's spawn calls `broadcast_fn(state.topic, payload)`
   (`supervisor/terminal.py:176`). Log: `consult consult-… failed: _broadcast_spawn() takes 1
   positional argument but 2 were given`; route `failed`, the question goes to the person, no
   consult spawn ever reaches a host. Fix: pass `sse._broadcast_runner` (what `/comms/goals/run`
   and the decompose routes pass; it mirrors TERMINAL_SPAWN to `/events/spawn`). Note that
   `tests/comms_board/test_consult_router.py:178` asserts `broadcast_fn is sse._broadcast_spawn`,
   so it pins the bug and changes with the fix (its line 366 too).
2. **A run's role question is handed to the person when the run's token board is not the
   board the prompt makes it post on.** The `consult` fragment's post
   (`src/pathly_data/core/skills/fragments/consult.md:16-18`) has no `"board"`, so
   `POST /comms/post` stores it on `board: feature` (`messages_write.py:73`) with scope = the
   project root. A drain-dag (single) run's token is `project`/<root> (board_run sets
   `scope_tier`), so `consult_router._asker_refusal` (`consult_router.py:102`) refuses it:
   "the question is on board feature//<root>, the asking run's is project//<root>". A goal-loop
   task's (`sched-…`) token is `feature`/<root> even for a project-board goal (the FSM run never
   sets `RunnerState.scope_tier`, default `"feature"`, `state.py:101`, minted at
   `terminal_identity.py:96`), so the literal fragment body routes there, but the same loop
   prompt tells the agent `"board": "project"` everywhere else, and a question posted that way
   is refused. No single body routes for both executors. Fix: give the fragment
   `"board": "<board_tier>"` and mint a loop task's token with the goal's board tier (set
   `scope_tier` for goal-loop runs from the goal's board). Failing assertions: step 2
   `len(agents.consults) == 1` (0) and step 4 `route_ended(q)["status"] == "answered"`
   (`to_person`).
3. **A project-board consult is billed twice (two `agent_invocations` rows).**
   `runner/events.py:97-99` `read_last_agent_done` takes the project root as
   `storage_path.parent.parent.parent`, right for `<root>/pathly/features/<f>` but one level too
   high for project storage `<root>/pathly/project`. So
   `terminal_reconcile._synthesize_agent_done_if_missing` (`:219-226`) never sees the consult's
   own AGENT_DONE and writes a synthetic one too: step 1's
   `invocations(consult) == [{"agent_role": "architect", "category": "consult"}]` gets two rows
   (source_seq of the agent's AGENT_DONE and of the synthetic one). Same miss for every
   executor-owned project-board run (single runs: `settle_run_tasks` gets `own=None`). Ticket
   16's test used a feature board, so it did not see it.

Needed: a fix ticket (or three) for the files named above; then ticket 12 is built again from the
draft (`tests/comms_board/test_autopilot_round_two_acceptance.py`,
`tests/comms_board/autopilot_round_two_support.py`, kept by the conductor) unchanged.
