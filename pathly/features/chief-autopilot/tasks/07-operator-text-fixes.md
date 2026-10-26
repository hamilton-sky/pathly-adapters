# Fix the Operator text where the spike's chief misread it

Type: task
Status: open
Blocked by: 04, 06
Test first: yes

Spike S8, S9, S10, and two facts that change in this round:

- The Operator text says "write the goal and its tasks the way the Planner style does" but shows
  no post body; the chief guessed `from_agent` and `agent`. Show the full `POST /comms/post` goal
  and task bodies in `OPERATOR` (`supervisor/chief_presets.py`), and make the gate's 403 `a chief
  posts as 'chief'` say `send "from": "chief"`.
- The chief said a goal run is "capped at $10". Say that only a flow start and `retry` take
  `max_cost_usd`, that goal, board and task runs are bounded by the run count only, and to re-read
  `GET /chief/session` before quoting a limit.
- After the curl deny it offered `! curl` and changing the permission settings. Say: when Pathly
  or the tab refuses something, tell the person what was refused and stop; never suggest a way
  around a deny.
- After ticket 04, a flow started with `POST /runs` runs headless; name `team` and `team-build`
  as the full pipeline (planner, designer, builder, reviewer, tester) next to goal runs.
- After ticket 06, a task can be `blocked` waiting for an answer: say how to find those
  (`GET /comms/tasks?...` with the blocked status) and that answering lets the person start the
  goal again.

`tests/http_api/test_chief_prompt_text.py` already checks every `pathly api` example against the
gate's tables; the new examples must pass it.

## Not in this ticket

- The Planner and Status texts, beyond the post body the Planner already shows.
- `pathly help` output: unchanged unless it disagrees with the new text.

## Done when

- `python -m pytest tests/http_api/test_chief_prompt_text.py tests/http_api/test_operator_text_fixes.py -q -p no:cacheprovider`
  passes; the new test checks that the Operator text contains a goal post body with
  `"from": "chief"`, names `max_cost_usd` only with flow starts and retry, contains the "never
  suggest a way around a deny" rule, names `team-build`, and that the 403 for a wrong author names
  `"from": "chief"`.

```check
$ python -m pytest tests/http_api/test_chief_prompt_text.py tests/http_api/test_operator_text_fixes.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spike19-part-b-report.md § 7
- `src/pathly_orchestrator/supervisor/chief_presets.py`, `src/pathly_orchestrator/http_server/chief_gate.py`

## Answer
