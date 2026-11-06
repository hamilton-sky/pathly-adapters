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
