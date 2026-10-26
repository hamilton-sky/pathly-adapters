# Start a claude chief with `--permission-mode dontAsk`

Type: task
Status: open
Blocked by: —
Test first: yes

Spike 19 question 1 (spike S1): claude 2.1.310 started the chief in auto mode despite
`--restricted`, and auto mode approved `ls`, `git status` and `python3`. `runner/chief_argv.py::chief_argv`
passes no permission mode, so the mode is whatever claude defaults to.

Add `--permission-mode dontAsk` to the claude argv in `chief_argv`, before `--settings`. Under
`dontAsk` claude denies every tool call the settings do not allow ahead of time, and the only
Bash allow is `Bash(pathly *)` (`_CLAUDE_ALLOW`), so the chief runs `pathly` commands and Read,
Glob and Grep within the deny rules, and nothing else, without asking anyone. Keep the value in
one module constant (for example `CLAUDE_PERMISSION_MODE = "dontAsk"`) so a test and the docs name
the same string. The codex argv is unchanged (`--sandbox read-only --ask-for-approval
on-request`).

Update the `claude_settings` docstring: it says claude's own rule asks for every other Bash
command; under `dontAsk` it denies them. Living docs: the chief paragraph of
`src/pathly_orchestrator/CLAUDE.md` names the permission mode and that it was chosen after spike
19 (claude 2.1.310), and `CHANGELOG.md` gets one line.

## Not in this ticket

- The hook secret's reachability through the tools still allowed: ticket 02.
- A re-measure in a real claude tab: the person's machine (map Open questions).

## Done when

- `python -m pytest tests/runner_supervisor/test_chief_permission_mode.py -q -p no:cacheprovider`
  passes and covers: the claude argv carries `--permission-mode` followed by `dontAsk` exactly
  once, before `--settings`; the codex argv carries no `--permission-mode`; no claude argv
  carries `auto`, `bypassPermissions` or `--dangerously-skip-permissions`.
- All existing tests under `tests/runner_supervisor` still pass.

```check
$ python -m pytest tests/runner_supervisor/test_chief_permission_mode.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/runner_supervisor -q -p no:cacheprovider
exit 0
```

## Reference

- spec.md § Decisions ("Where the chief is locked down")
- `pathly/features/chief-agent/spike19-part-b-report.md` § 1 and "Proposed tickets" 1
- `src/pathly_orchestrator/runner/chief_argv.py`, `tests/runner_supervisor/test_chief_session.py`

## Answer
