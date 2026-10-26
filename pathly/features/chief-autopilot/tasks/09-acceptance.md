# Acceptance: a claude chief left alone runs a goal safely

Type: task
Status: open
Blocked by: 01, 02, 03, 04, 05, 06, 07, 08, 10, 11, 12, 13
Test first: no
Level: 1
Touches: tests/comms_board/test_autopilot_round_one_acceptance.py, tests/comms_board/autopilot_acceptance_support.py, tests/INDEX.md, tests/comms_board/INDEX.md

Write `tests/comms_board/test_autopilot_round_one_acceptance.py` (new; fake spawn host, fake agent
processes, the server in process, as `tests/comms_board/test_chief_acceptance.py` does) that runs
round one's story end to end:

1. Open an Operator chief (claude): its argv carries `--permission-mode dontAsk`; its settings deny
   `Read`, `Grep` and `Glob` on `~/.pathly/**` and block reads outside the working directories.
2. Through the chief's token: post a goal and a task, start the goal (`POST /runs` kind `goal`,
   default `single` executor). The fake agent claims with drain-dag's literal body
   (`"$GOAL_ID-single"`), posts a `question` to `human`, prints
   `PATHLY_RUN_TOKEN: <its token>`, and exits without finishing.
3. The task's `claimed_by` was the run's id; the run ends failed with `waiting_for_answer`; the
   task is `blocked` on the question; no row in `fsm_events`, `run_log` or `comms_messages`
   contains the raw token.
4. `GET /chief/notices` lists the run with one question waiting.
5. A human message is recorded through the hook; the chief answers with its cite. The task is
   `pending`; the chief starts the goal again; the fake agent sees the question and answer in its
   ready-task row, finishes the task; the run ends `success`.
6. A loop goal (`executor: loop`) whose fake agent asks a question is parked the same way and
   resumes with the answer in its prompt.
7. A chief-token post whose text holds the hook secret is 400. A request with a revoked token is
   401. A chief `POST /runs` kind `flow` (`team`) reaches the spawn host headless and lists as
   `kind: flow`.

Then run the whole suite once.

## Not in this ticket

- A real claude: the person re-measures spike question 1 on their machine (map Open questions).

## Done when

- `python -m pytest tests/comms_board/test_autopilot_round_one_acceptance.py -q -p no:cacheprovider` passes.
- `python -m pytest tests/ -q -p no:cacheprovider` passes.

```check
$ python -m pytest tests/comms_board/test_autopilot_round_one_acceptance.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/ -q -p no:cacheprovider
exit 0
```

## Reference

- map.md § The bar, spec.md § Happy path
- `tests/comms_board/test_chief_acceptance.py`, `tests/comms_board/chief_acceptance_support.py`

## Answer
