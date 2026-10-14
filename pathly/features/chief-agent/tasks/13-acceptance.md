# Prove the chief core end to end

Type: task
Status: open
Blocked by: 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 14, 15, 16, 17
Test first: no

Write `tests/comms_board/test_chief_acceptance.py`: the brief's bar, run against the real Flask
app and the real supervisor, with a fake spawn host: a thread reading a queue registered in
`sse._spawn_clients` (what `/events/spawn` clients get) that records every payload and, for a
worker `TERMINAL_SPAWN`, marks the run started and finished the way
`tests/comms_board/test_rrp_acceptance.py` does. One scenario per bar item:

1. Open: `POST /chief/open` with engine `claude`, preset `operator` and a prompt that starts with
   front matter → 201 with `tier: "operator"`; the recorded `TERMINAL_SPAWN` has
   `interactive: true` and `submit: false`, its `prompt` is the text without front matter
   followed by the `chief-connect` fragment and contains no token, its `argv` starts claude in
   restricted mode with `--session-id`, and its `run_token` resolves to role `chief` with the
   session's run id.
2. Operator acts through the API: with that token, `POST /comms/post` creates a `goal` on the
   project board, and `POST /runs` starts a single run; the fake host sees a second
   `TERMINAL_SPAWN` whose token resolves to the worker's role (not `chief`), proving the run went
   through `_run_stage_via_terminal`. Resolve it in the host thread before marking the run
   finished: the spawn revokes its token when it settles.
3. Status is read-only: close the operator, open with preset `status`; `GET /comms?feature=<f>`
   is 200 and `POST /comms/post` is 403.
4. Cited answers: with a `RunnerState` waiting in `_await_agent_question`, an uncited chief answer
   is 403 and the question stays pending; a chief answer that cites a later human message but
   carries its own `answer` text is 403; citing that message alone delivers the message's text
   to the agent, and citing it again for a second question is 403. A `to_agent: "human"`
   escalation is acknowledged by the chief only with a cite recorded after it. The test states
   the limit in a comment: Pathly relays the user's real words, but to the question the chief
   picked.
5. Binding directive: an operator chief posts a `*` directive, `/comms/acknowledge` marks it, and
   `fsm_compose.build_prompt` for the `team/build`, `team/review` and `team/test` agents of a
   feature in the project carries its text in the standing-orders block. A project-board run
   token's `supersedes` naming it, and a token-less `/comms/supersede` of it, leave it in place.
6. Limits: an operator chief's `POST /runs` above `chief.max_cost_usd_per_run` is 403, and a run
   control call on a run of another project is 403.
7. Usable from the tab: `pathly api GET /chief/session?project_root=…`, run as a subprocess with
   the chief's token in `PATHLY_RUN_TOKEN`, exits 0.
8. Token stays off the open streams: queues registered on `/events/runner` (the chief's topic and a
   worker's) and on `/events/runs` receive the spawns without `run_token`; the `/events/spawn`
   queue receives it.

Then the release notes: a CHANGELOG "Unreleased" entry whose heading ends in `(chief-agent)`, in
the style of the role-read-policy entry: what exists, what is refused, the three holes closed,
and the gaps that wait for round two and RRP-2b. Check every living doc touched by tickets 01 to
12 and 14 to 17 against the code once more (verify-then-fix, do not rewrite).
Regenerate the test indexes and run the full suite.

## Not in this ticket

- Studio, the friendly `pathly` commands, the overview and inbox calls, the badge and the
  re-queue: round two.

## Done when

- `python -m pytest tests/comms_board/test_chief_acceptance.py -q -p no:cacheprovider` passes.
- `python -m pytest tests/ -q -p no:cacheprovider` passes in full.
- `python scripts/gen_test_index.py --check` exits 0.
- `CHANGELOG.md` has a `### ... (chief-agent)` entry under "Unreleased".

```check
$ python -m pytest tests/comms_board/test_chief_acceptance.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/ -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/gen_test_index.py --check
exit 0
$ grep -n "(chief-agent)" CHANGELOG.md
exit 0
prints (chief-agent)
```

## Reference

- map.md (the bar), spec.md § Goal and the bar, § Happy path
- `tests/comms_board/test_rrp_acceptance.py` (fake host, `client` fixture, token helpers)
- `tests/conftest.py` (fresh temporary DB per test; `get_db()` is per thread)

## Answer
