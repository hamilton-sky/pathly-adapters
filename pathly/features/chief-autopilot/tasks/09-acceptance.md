# Acceptance: a claude chief left alone runs a goal safely

Type: task
Status: resolved
Blocked by: 01, 02, 03, 04, 05, 06, 07, 08, 10, 11, 12, 13, 14
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
6. A loop goal (`executor: loop`) whose fake agent asks a question is parked the same way: the
   run ends with `waiting_for_answer`, and after the answer the task resumes under a new
   `sched-<task>#N` run id with the answer in its prompt. Both runs have exactly one
   `agent_invocations` row each.
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

Work started at commit `7c03124ec4c8a2888c71acf84dfed7c61ecee83b`.

- **Built**: `tests/comms_board/test_autopilot_round_one_acceptance.py` (new, 4 tests),
  `tests/comms_board/autopilot_acceptance_support.py` (new: `AgentHost`, a spawn host whose worker
  spawns run a fake agent with the spawn's own run token and report the exit through
  `POST /runner/terminal/result`; drain-dag and goal-loop fake agents; DB readers),
  `tests/INDEX.md`, `tests/comms_board/INDEX.md` (regenerated).
- **Proof**:
  - `python -m pytest tests/comms_board/test_autopilot_round_one_acceptance.py -q -p no:cacheprovider`
    → `4 passed in 2.29s`, exit 0.
  - `python -m pytest tests/ -q -p no:cacheprovider` → `6628 passed, 14 skipped in 1663.01s`, exit 0.
  - `black --check` clean on both files; `gen_test_index.py --check` up to date;
    `check_file_size.py` "none new, none grown" (274 and 318 lines).
- **Decisions**: one test per story slice (1; 2-5; 6; 7), each opening its own chief, so a failure
  names the step. Step 1 reads the chief's real `--settings` file. Step 3 checks the raw token is in
  no `fsm_events`/`run_log`/`comms_messages` row and that its redacted form `[run token]` is, so the
  token reached the store and was redacted rather than lost. Step 5 reads the notice by run id. Step 6
  runs on the project board, as the Operator text posts (needs ticket 14). Step 7 proves the 401 token
  was live during the stage and has `revoked_at` set afterwards, so the 401 is for a revoked token,
  not an unknown one.
- **Shortcuts taken**: step 6 reads `GET /runner/status` (`error_kind: waiting_for_answer`) for the
  parked loop run, because a parked goal-loop run writes no `RUN_OUTCOME`: `GET /runs/<id>` and so
  `GET /chief/notices` show `outcome`/`error` null for it. Non-blocking for round one; worth a ticket
  if the chief must see a parked loop run in its notices.
- **For later tickets**: the gap above (ticket 12's park writes no `RUN_OUTCOME` for goal-loop runs).
  The first build attempt was blocked on `fan_out._drain` hardcoding the `feature` board; ticket 14
  fixed it, and the test needed no change for it.
