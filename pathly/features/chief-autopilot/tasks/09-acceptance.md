# Acceptance: a chief left alone runs a goal safely

Type: task
Status: open
Blocked by: 01, 02, 03, 04, 05, 06, 07, 08
Test first: no

Write `tests/comms_board/test_autopilot_round_one_acceptance.py` (fake spawn host, fake agent
processes, the server in process, as `tests/comms_board/test_chief_acceptance.py` does) that runs
round one's story end to end:

1. Open an Operator chief: its argv carries `--permission-mode dontAsk`, its settings deny `Read`,
   `Grep` and `Glob` on `~/.pathly/**` and the redirect forms.
2. Through the chief's token: post a goal and a task, start the goal (`POST /runs` kind `goal`).
   The fake agent posts a `question` to `human`, prints `PATHLY_RUN_TOKEN: <its token>`, and exits
   without finishing its task.
3. The run ends with `outcome: failed`, `error: waiting_for_answer`; the task is `blocked` on the
   question; no stored text (events, invocation rows, board rows) contains the raw token.
4. `GET /chief/notices` lists the run with one question waiting.
5. A human message is recorded through the hook; the chief answers with its cite. The task is
   `pending`; the chief starts the goal again; the fake agent's prompt holds the question and the
   answer; it finishes the task; the run ends `success`.
6. A chief-token post whose text holds the hook secret is 400. `POST /runs` kind `flow` (`team`)
   reaches the spawn host headless and lists as `kind: flow`.

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
