# Fix the Operator text where the spike's chief misread it

Type: task
Status: open
Blocked by: 04, 06
Test first: yes
Level: 1
Touches: src/pathly_orchestrator/supervisor/chief_presets.py, src/pathly_orchestrator/http_server/chief_gate.py, src/pathly_orchestrator/chief_cli.py, tests/http_api/test_operator_text_fixes.py, tests/INDEX.md, tests/http_api/INDEX.md

Spike S8, S9, S10, and two facts this round changes. In `src/pathly_orchestrator/supervisor/chief_presets.py`:

- The Operator text says "write the goal and its tasks the way the Planner style does" but shows
  no post body; the chief guessed `from_agent` and `agent`. Show the full `POST /comms/post` goal
  and task bodies in `OPERATOR`, and make the gate's 403 `a chief posts as 'chief'`
  (`src/pathly_orchestrator/http_server/chief_gate.py`) say `send "from": "chief"`.
- The chief said a goal run is "capped at $10". Say that only a flow start and `retry` take
  `max_cost_usd`, that goal, board and task runs are bounded by the run count only, and to re-read
  `GET /chief/session` before quoting a limit.
- After the curl deny it offered `! curl` and changing the permission settings. Say: when Pathly or
  the tab refuses something, tell the person what was refused and stop; never suggest a way around
  a deny, a different token, or a setting change.
- After ticket 04, a flow the chief starts with `POST /runs` runs headless: name `team` and
  `team-build` as the full pipeline (planner, designer, builder, reviewer, tester).
- After ticket 06, a task can be `blocked` waiting for an answer: say how to find those (the
  question rows; the task's `fail_reason`), that answering frees the task, and that the person
  then starts the goal again.

`pathly help` (`src/pathly_orchestrator/chief_cli.py`) lists post types as "a message, goal or
task"; make it match what the gate accepts. `tests/http_api/test_chief_prompt_text.py` already
checks every `pathly api` example against the gate's tables; the new examples must pass it.

## Not in this ticket

- The Planner and Status texts, beyond the post body the Planner already shows.

## Done when

- `python -m pytest tests/http_api/test_chief_prompt_text.py tests/http_api/test_operator_text_fixes.py -q -p no:cacheprovider`
  passes; the new test checks that the Operator text contains a goal post body with
  `"from": "chief"`, names `max_cost_usd` only with flow starts and retry, has the rule against
  suggesting a way around a deny, names `team-build` and `waiting_for_answer`, and that the 403 for
  a wrong author names `"from": "chief"`.

```check
$ python -m pytest tests/http_api/test_chief_prompt_text.py tests/http_api/test_operator_text_fixes.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spike19-part-b-report.md § 7
- `src/pathly_orchestrator/http_server/chief_routes.py`

## Answer
