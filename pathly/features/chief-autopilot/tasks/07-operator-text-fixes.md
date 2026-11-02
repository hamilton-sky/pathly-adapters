# Fix the Operator text where the spike's chief misread it

Type: task
Status: resolved
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

**Built** (work started at b9327688, the merge on top of 482f71c8 with the same tree; failing
test af03642c):
- `supervisor/chief_presets.py` (`OPERATOR` only, 2758 -> 3797 characters; `test_chief_cli.py`
  holds a built-in style under 4000, so the old prose was tightened to make room): the full
  `POST /comms/post` goal and task bodies as fenced `pathly api` examples (`"from": "chief"`,
  project board); a rule that a refusal by Pathly or the tab is reported and the chief stops,
  never suggesting a way around a deny, a different token or a permission-settings change;
  `team` (planner, designer, builder, reviewer, tester) and `team-build` (the same from the
  builder on) as headless flows; that only a flow start (body shown) and the `retry` verb take
  `max_cost_usd`, that goal, board and task runs are bounded by the run count only, and to read
  `GET /chief/session?project_root=<root>` again before quoting a limit; a waiting task
  (`blocked`, `fail_reason` `waiting_for_answer:<question ids>`, a `GET /comms/tasks` example,
  its questions the pending `question` rows), that answering frees it and the user may then
  start the goal again.
- `http_server/chief_gate.py`: the 403 is now `a chief posts as 'chief': send "from": "chief"`.
- `chief_cli.py` (`HELP`): the `/comms/post` line says the type picks the action:
  `{"type": "goal"}`/`task` plan, `decision`/`constraint` decide, any other type post (the
  gate's `POST_TYPE_ACTIONS`). Written as `{"type": "..."}` because
  `test_chief_help_routes.py` reads a bare quoted word on a help line as a body key.
- `tests/http_api/test_operator_text_fixes.py` (new, 11 tests) + `tests/INDEX.md`,
  `tests/http_api/INDEX.md`.

**Proof**:
- `python -m pytest tests/http_api/test_chief_prompt_text.py tests/http_api/test_operator_text_fixes.py -q -p no:cacheprovider`:
  35 passed, exit 0. At af03642c the new file was 11 failed (e.g. `assert '"from": "chief"' in
  "a chief posts as 'chief'"`, "the Operator text shows no flow start body").
- `python -m pytest tests/http_api -q -p no:cacheprovider -k chief`: 2335 passed, 240 deselected, exit 0 (a first run before the text was shortened failed `test_chief_cli.py` on the 4000-character limit and `test_chief_help_routes.py` on quoted type words in the help line; both fixed).
- `python -m pytest tests/runner_supervisor -q -p no:cacheprovider -k chief`: 82 passed.
- Lint chain (black, mypy, check_file_size "none new, none grown", mirror reads, INDEX check,
  lint-imports 1 kept, bandit): exit 0.

**Decisions**:
- The flow start body is shown in prose, not as a `pathly api` example:
  `test_chief_prompt_text.py` runs every example as an operator chief against a real server and
  asserts no spawn, and a flow start would start a run. The new test holds that body to the same
  gate tables (`problems`). The retry body is not shown (length); `retry` is named as the verb.
- `team-build` starts at BUILDING (its flow yaml has no planner or designer state), so the text
  says `team` is the full pipeline and `team-build` the same from the builder on, rather than
  calling both the full pipeline as the ticket worded it.
- The decompose example body and the pending-question read were left out of the Operator text
  to stay under the 4000-character limit (the `chief-connect` fragment already shows that read).

**Shortcuts taken**: none.

**For later tickets**: the Operator text is at 3797 of the 4000 characters
`test_chief_cli.py::test_a_built_in_style_is_short_plain_text_that_starts_without_front_matter`
allows; a later addition has to cut something. The gate's 403 for a wrong `from` changed text.
`src/pathly_orchestrator/CLAUDE.md` needed no change: it says only that a wrong `from` is 403 and
that the texts name no cost number, both still true.
