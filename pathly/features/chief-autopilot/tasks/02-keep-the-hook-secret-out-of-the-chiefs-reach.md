# Keep the hook secret out of the chief's reach

Type: task
Status: resolved
Blocked by: 01, 03, 10
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/runner/chief_argv.py, src/pathly_orchestrator/http_server/chief_secret_text.py (new), src/pathly_orchestrator/http_server/chief_gate.py, tests/runner_supervisor/test_chief_secret_reach.py, tests/runner_supervisor/test_chief_session.py, tests/http_api/test_chief_secret_in_body.py, src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/runner_supervisor/INDEX.md, tests/http_api/INDEX.md

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

Started at d69e033df372e46f4603317626a8a712f1a6cf2b. Failing tests committed alone as 0e7256ec.

**Built**
- `src/pathly_orchestrator/runner/chief_argv.py`: `Grep(~/.pathly/**)` and `Glob(~/.pathly/**)` in `_CLAUDE_DENY` right after `Read(~/.pathly/**)`; `claude_settings` sets `permissions.blockReadsOutsideWorkingDirectories: true` (inside `permissions`, so the top-level keys stay `permissions`, `env`, `hooks`); docstring says why and why no redirect rule.
- `src/pathly_orchestrator/http_server/chief_secret_text.py` (new): `secret_refusal(session, bodies)` walks every string value (dicts and lists, any depth; keys not) of every reading of the body and returns `SECRET_IN_BODY` when `contains_secret_hash` matches `session["hook_secret_hash"]`; no stored hash means no check. Docstring says a re-encoded secret is not caught and this is not the guarantee.
- `src/pathly_orchestrator/http_server/chief_gate.py`: for a non-GET chief request, after the per-body `_refusal` loop and before `_cite_refusal` and `_budget_refusal`, answers 400 `{"error": "the body contains this chief's hook secret"}`; module docstring updated.
- Tests: `tests/runner_supervisor/test_chief_secret_reach.py`, `tests/http_api/test_chief_secret_in_body.py` (new); `tests/runner_supervisor/test_chief_session.py` `DENY` gains the two rules; INDEX files regenerated.
- `src/pathly_orchestrator/CLAUDE.md`: chief settings paragraph, `contains_secret_hash` note, a "Hook secret in a body" bullet under "Chief gate", the `chief_argv.py` entry and a new `chief_secret_text.py` entry.

**Proof**
- `python -m pytest tests/runner_supervisor/test_chief_secret_reach.py tests/http_api/test_chief_secret_in_body.py -q -p no:cacheprovider`: `20 passed`, exit 0. Covers deny Read/Grep/Glob on `~/.pathly/**` and the block flag; `/comms/post` with the secret alone, as `x<secret>`, inside `ab-<secret>_cd` and inside prose: 400 with the exact body and no new `comms_messages` row; the same in `summary` and inside an `options` list; the same four for `/comms/directives`; ordinary posts (`hello`, `a < b and c > d`, `x<y`, `<<EOF`) and directives with `<` store a row; another random secret passes; a builder token posting the secret stores its row. At the test-only commit 4 http tests and 3 settings tests failed (200/201 where 400 was expected; rules and flag missing).
- `python -m pytest tests/http_api tests/runner_supervisor -q -p no:cacheprovider -k chief`: `2413 passed, 500 deselected in 968.31s`, exit 0.
- Lint chain parts run: black --check (716 files unchanged), mypy on the three changed source files (no issues), `check_file_size.py` OK, `check_no_mirror_reads.py` OK, `gen_test_index.py --check` OK, `lint-imports` 1 kept 0 broken, bandit exit 0.

**Decisions**
- The scan runs on every non-GET chief request, not only on the four routes the ticket names: those are the routes a chief can write, and a superset is no weaker; a GET has no body (`[{}]`).
- It runs after the per-body 403 checks (so a call the tier may not make still gets its 403 with `allowed`) and before the cite check, so a refused answer does not spend its citation, and before the budget check, so no run slot is taken.
- Values only, not keys: a key holding the secret is refused by `chief_keys` (403) anyway.

**Shortcuts taken**: none.

**For later tickets**
- `_passed()` in `chief_gate_support.py` counts the new 400 as passed (no `allowed` key); a test that wants to tell it apart must compare the body with the exact error.
