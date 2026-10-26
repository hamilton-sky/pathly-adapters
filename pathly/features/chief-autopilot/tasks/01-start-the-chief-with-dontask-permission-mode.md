# Start a claude chief with `--permission-mode dontAsk`

Type: task
Status: open
Blocked by: —
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/runner/chief_argv.py, tests/runner_supervisor/test_chief_permission_mode.py, src/pathly_orchestrator/CLAUDE.md, CHANGELOG.md, tests/INDEX.md, tests/runner_supervisor/INDEX.md

Spike 19 question 1 (spike S1): claude 2.1.310 started the chief in auto mode despite
`--restricted`, and auto mode ran `python3` without asking. `src/pathly_orchestrator/runner/chief_argv.py::chief_argv`
passes no permission mode, and auto mode is claude's built-in starting mode for interactive
sessions from v2.1.283 (map Decisions so far).

Add `--permission-mode dontAsk` to the claude argv in `chief_argv`, before `--settings`, from one
module constant (`CLAUDE_PERMISSION_MODE = "dontAsk"`) so a test and the docs name the same
string. Under `dontAsk` claude denies every call that would otherwise prompt: the chief runs
`pathly` commands (`_CLAUDE_ALLOW`), claude's built-in read-only commands inside the project, and
Read, Glob and Grep inside the project; anything else is denied without asking. The codex argv is
unchanged.

Correct the `claude_settings` docstring, which says every other Bash command asks the human: under
`dontAsk` they are denied, while claude's read-only set still runs in every mode. Living docs: the
chief paragraph of `src/pathly_orchestrator/CLAUDE.md` names the mode, why (spike 19, claude
2.1.310) and that read-only commands still run; `CHANGELOG.md` gets one line.

## Not in this ticket

- `~/.pathly/` and paths outside the project: ticket 02.
- Unknown run tokens: ticket 10.
- The re-measure in a real claude tab: the person's machine (map Open questions).

## Done when

- `python -m pytest tests/runner_supervisor/test_chief_permission_mode.py -q -p no:cacheprovider`
  passes and covers: the claude argv carries `--permission-mode` followed by `dontAsk` exactly
  once, before `--settings`; the codex argv carries no `--permission-mode`; no chief argv carries
  `auto`, `bypassPermissions` or `--dangerously-skip-permissions`.
- All existing tests under `tests/runner_supervisor` still pass.

```check
$ python -m pytest tests/runner_supervisor/test_chief_permission_mode.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/runner_supervisor -q -p no:cacheprovider
exit 0
```

## Reference

- spec.md § Decisions ("Where the chief is locked down"), map.md § Decisions so far
- `pathly/features/chief-agent/spike19-part-b-report.md` § 1 and "Proposed tickets" 1
- `src/pathly_orchestrator/runner/chief_argv.py`, `tests/runner_supervisor/test_chief_session.py`

## Answer

## Attempt note

Attempt 1 (auto, from 430c6aacf1b39b8fb59c38858ecb212ecdc58d67): stopped before any code change, Status left open.

The two Done when bullets cannot both hold inside `Touches:`. The second ("All existing tests
under `tests/runner_supervisor` still pass") fails as soon as `chief_argv` does what the ticket
asks, because
`tests/runner_supervisor/test_chief_session.py::test_claude_argv_is_restricted_with_its_own_tools_settings_mcp_and_session`
compares the whole claude argv with `==` (lines 141-155), and that file is not in `Touches:`.
Measured: with `"--permission-mode", "dontAsk"` added after `CLAUDE_TOOLS` and before
`"--settings"` (then reverted), `python -m pytest tests/runner_supervisor -q -p no:cacheprovider`
gave `1 failed, 345 passed`, and the failure was that test (AssertionError at line 143). Any
insertion anywhere in the claude argv breaks an `==` check, so placing it differently does not help.
No other test pins the whole list (`tests/comms_board/test_chief_acceptance.py:126` checks only
`argv[:2]`, and the rest look flags up by name).

What is needed: add `tests/runner_supervisor/test_chief_session.py` to `Touches:` so the expected
list in that one test gains `"--permission-mode", "dontAsk"` between `"Bash,Read,Glob,Grep"` and
`"--settings"`. That updates the pin to the new contract; it does not weaken it. Everything else
the ticket asks for fits inside the current `Touches:`.
