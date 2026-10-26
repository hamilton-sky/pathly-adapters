# Keep the hook secret out of the chief's reach

Type: task
Status: open
Blocked by: 01, 03, 10
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/runner/chief_argv.py, src/pathly_orchestrator/http_server/chief_secret_text.py (new), src/pathly_orchestrator/http_server/chief_gate.py, tests/runner_supervisor/test_chief_secret_reach.py, tests/http_api/test_chief_secret_in_body.py, src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/runner_supervisor/INDEX.md, tests/http_api/INDEX.md

Spike S2. A chief's session folder `~/.pathly/chief/<run_id>/`
(`src/pathly_orchestrator/supervisor/chief_session.py::_write_session_folder`) holds
`hook_secret`, which the `UserPromptSubmit` hook sends with each prompt it records as typed by the
person. A chief that reads it could post a forged "human" message and cite it.

The guarantee is (a) no read path for the chief and (b) no way for it to call Pathly as anyone but
itself (ticket 10 and `dontAsk`'s env-prefix rule, map Decisions so far). This ticket does (a) and
adds a defence in depth:

1. In `src/pathly_orchestrator/runner/chief_argv.py`: add `Grep(~/.pathly/**)` and
   `Glob(~/.pathly/**)` to `_CLAUDE_DENY` beside `Read(~/.pathly/**)` (docs say Read rules already
   reach Grep and Glob best-effort; the explicit rules cost nothing), and set
   `"blockReadsOutsideWorkingDirectories": true` under `permissions` in `claude_settings`. No
   redirect deny rules: an input redirect is checked against `Read` deny rules (docs), and
   `Bash(pathly *<*)` would deny ordinary bodies containing `<` (spec Decisions).
2. New `src/pathly_orchestrator/http_server/chief_secret_text.py`: for a chief-token request,
   refuse (400, `{"error": "the body contains this chief's hook secret"}`) a body any of whose
   text fields contains the session's hook secret, using ticket 03's
   `db/secret_scan.py::contains_secret_hash` against `chief_sessions.hook_secret_hash` (a sliding
   43-character window, so `x<secret>` is caught). Fields: every string value of the JSON body on
   the routes the chief can write (`/comms/post` text and its goal and task fields,
   `/comms/directives` text, `/comms/acknowledge`, `/runner/agent-answer`). Call it from
   `src/pathly_orchestrator/http_server/chief_gate.py` before the budget check. Say in the module
   docstring that a re-encoded secret is not caught: this is not the guarantee.

## Not in this ticket

- Headless agents and a codex chief, which are same-user processes that can read the file: round
  two (map), with a server-held secret.
- Run tokens in stored text: ticket 03.

## Done when

- `python -m pytest tests/runner_supervisor/test_chief_secret_reach.py tests/http_api/test_chief_secret_in_body.py -q -p no:cacheprovider`
  passes and covers: the settings deny `Read`, `Grep` and `Glob` on `~/.pathly/**` and set
  `blockReadsOutsideWorkingDirectories`; a chief-token `/comms/post` whose text holds the secret,
  alone or inside a longer token-like run, is 400 and stores nothing; the same for
  `/comms/directives`; an ordinary body, and one with `<` in it, is unaffected; a builder token is
  unaffected.
- All existing chief tests still pass.

```check
$ python -m pytest tests/runner_supervisor/test_chief_secret_reach.py tests/http_api/test_chief_secret_in_body.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/http_api tests/runner_supervisor -q -p no:cacheprovider -k chief
exit 0
```

## Reference

- spec.md § Decisions ("Hook-secret protection"), review M2, M3
- `src/pathly_orchestrator/http_server/chief_cite.py`, `src/pathly_orchestrator/http_server/blueprints/chief/human.py` (docstring on same-user processes)

## Answer
