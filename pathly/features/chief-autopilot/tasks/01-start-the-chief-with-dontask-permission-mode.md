# Start a claude chief with `--permission-mode dontAsk`

Type: task
Status: resolved
Blocked by: —
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/runner/chief_argv.py, tests/runner_supervisor/test_chief_permission_mode.py, tests/runner_supervisor/test_chief_session.py, src/pathly_orchestrator/CLAUDE.md, CHANGELOG.md, tests/INDEX.md, tests/runner_supervisor/INDEX.md

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

Work starts at `abc974f8f92f59ac3382dccc69b60d3adfcf0067`; test-only commit `4c95b64a`.

- **Built**: `src/pathly_orchestrator/runner/chief_argv.py` (new `CLAUDE_PERMISSION_MODE = "dontAsk"`
  with a spike 19 / claude 2.1.310 comment; claude argv gains `--permission-mode`,
  `CLAUDE_PERMISSION_MODE` right after `--tools CLAUDE_TOOLS`, before `--settings`; `chief_argv` and
  `claude_settings` docstrings corrected: other Bash commands are denied, read-only ones still run);
  new `tests/runner_supervisor/test_chief_permission_mode.py` (10 tests);
  `tests/runner_supervisor/test_chief_session.py` (exact claude argv list gains the pair);
  `src/pathly_orchestrator/CLAUDE.md` (the `pathly api` chief paragraph names the mode, why and
  that read-only commands still run; the `chief_argv.py` tree line lists the flag); `CHANGELOG.md`
  (one bullet in the chief-agent Unreleased section); `tests/INDEX.md`,
  `tests/runner_supervisor/INDEX.md` regenerated.
- **Proof**:
  - `python -m pytest tests/runner_supervisor/test_chief_permission_mode.py -q -p no:cacheprovider`:
    `10 passed`, exit 0. Covers: `--permission-mode` count 1 followed by `dontAsk` (count 1), with
    and without a model; index before `--settings`; the constant equals `dontAsk` and is in the
    argv; codex argv (with and without model) has no `--permission-mode`/`dontAsk`; no claude or
    codex argv contains `auto`, `bypassPermissions` or `--dangerously-skip-permissions`. At the
    test-only commit 4 of those tests failed (no flag / no constant), the codex and forbidden ones
    passed.
  - `python -m pytest tests/runner_supervisor -q -p no:cacheprovider`: `356 passed in 182.09s`, exit 0.
  - Also ran: `tests/comms_board/test_chief_acceptance.py` 15 passed (its `argv[:2]` check holds);
    `gen_test_index.py --check`, `check_file_size.py`, black, mypy on the module all clean.
- **Decisions**: the pair goes right after `--tools` so `argv[:2] == ["claude", "--restricted"]`
  (comms_board acceptance) and the trailing `--model` pair stay true. The spike's record line in
  `CHANGELOG.md` ("the argv passes no `--permission-mode`") is a dated measurement and was left as
  is; the new bullet says what changed.
- **Shortcuts taken**: none. The flag is not measured in a real claude tab here (map Open
  questions: the person's machine re-measures).
- **Review fixes**:
  - Round 1, gate (quick), Build failed with `error TS2688: Cannot find type definition file for
    'vite/client'`: not caused by this ticket (it changes no Studio file). The container had no
    `studio/node_modules`; the session ran the commands.md Setup step `npm --prefix studio ci`.
    Re-ran the Build command fresh at `59ea9452`: `python -m build --wheel` exit 0 (`Successfully
    built pathly_adapters-2.24.1-py3-none-any.whl`), `npm --prefix studio run typecheck` (`tsc
    --noEmit -p tsconfig.web.json`) exit 0 with no errors. No code change was needed. Re-ran Done
    when: `test_chief_permission_mode.py` 10 passed, exit 0; `tests/runner_supervisor` 356 passed
    in 76.44s, exit 0.
  - Round 2, gate (quick), `tests/http_api/test_chief_routes.py::test_main_closes_a_session_the_last_process_left_open_before_serving`
    failed with `Error: Flask not installed`: environmental, not this ticket (it changes no
    http_server file). The test runs a subprocess with `HOME` set to a temp folder, which hides the
    user site-packages (`~/.local/lib/python3.13/site-packages`), where markupsafe, jinja2 and pyyaml
    were installed only, so `import flask` failed. The session installed them system-wide. Confirmed
    at `fcf00836`: `HOME=/tmp/x python -c 'import flask, markupsafe, jinja2, yaml'` resolves all four
    from `/usr/local/lib/python3.13/dist-packages` / `/usr/lib/python3/dist-packages`;
    `python -m pytest tests/http_api/test_chief_routes.py -q -p no:cacheprovider` 64 passed;
    `HOME=/tmp/x ... -k main` 2 passed. No code change. Re-ran Done when:
    `test_chief_permission_mode.py` 10 passed, exit 0; `tests/runner_supervisor` 356 passed in
    82.35s, exit 0. The full Quick suite is left to the conductor.
- **For later tickets**: `CLAUDE_PERMISSION_MODE` is importable from `runner/chief_argv.py`
  for ticket 09's acceptance test.

## Attempt note

Attempt 1 stopped before any code change: `tests/runner_supervisor/test_chief_session.py::test_claude_argv_is_restricted_with_its_own_tools_settings_mcp_and_session`
pins the whole claude argv with `==`, and the file was not in `Touches:`. Plan fix (the person's
OK, 2026-10-29): the file is now in `Touches:`, so its expected list gains
`"--permission-mode", "dontAsk"` between `"Bash,Read,Glob,Grep"` and `"--settings"`.

## Review findings (round 1, gate (quick))

gate: Build: python -m build --wheel && npm --prefix studio run typecheck
gate: Build failed. the last lines of its output:
adding 'pathly_orchestrator/supervisor/run_budget.py'
adding 'pathly_orchestrator/supervisor/scheduler.py'
adding 'pathly_orchestrator/supervisor/slug.py'
adding 'pathly_orchestrator/supervisor/spawn_policy.py'
adding 'pathly_orchestrator/supervisor/spawn_window.py'
adding 'pathly_orchestrator/supervisor/state.py'
adding 'pathly_orchestrator/supervisor/task_dependencies.py'
adding 'pathly_orchestrator/supervisor/task_prompt.py'
adding 'pathly_orchestrator/supervisor/task_proof.py'
adding 'pathly_orchestrator/supervisor/task_retry.py'
adding 'pathly_orchestrator/supervisor/terminal.py'
adding 'pathly_orchestrator/supervisor/terminal_argv.py'
adding 'pathly_orchestrator/supervisor/terminal_billing.py'
adding 'pathly_orchestrator/supervisor/terminal_identity.py'
adding 'pathly_orchestrator/supervisor/terminal_phase.py'
adding 'pathly_orchestrator/supervisor/terminal_reconcile.py'
adding 'pathly_studio_cli/__init__.py'
adding 'pathly_studio_cli/install.py'
adding 'pathly_telemetry/__init__.py'
adding 'pathly_telemetry/report.py'
adding 'pathly_telemetry/storage.py'
adding 'pathly_adapters-2.24.1.dist-info/METADATA'
adding 'pathly_adapters-2.24.1.dist-info/WHEEL'
adding 'pathly_adapters-2.24.1.dist-info/entry_points.txt'
adding 'pathly_adapters-2.24.1.dist-info/top_level.txt'
adding 'pathly_adapters-2.24.1.dist-info/RECORD'
removing build/bdist.linux-x86_64/wheel
Successfully built pathly_adapters-2.24.1-py3-none-any.whl

> pathly-studio@2.24.1 typecheck
> tsc --noEmit -p tsconfig.web.json

error TS2688: Cannot find type definition file for 'vite/client'.
  The file is in the program because:
    Entry point of type library 'vite/client' specified in compilerOptions
npm notice
npm notice New major version of npm available! 10.9.4 -> 12.2.1
npm notice Changelog: https://github.com/npm/cli/releases/tag/v12.2.1
npm notice To update run: npm install -g npm@12.2.1
npm notice

## Review findings (round 2, gate (quick))

gate: Build: python -m build --wheel && npm --prefix studio run typecheck
gate: Quick: python -m pytest tests/comms_board tests/db tests/runner_supervisor tests/http_api tests/dag_goals -q -x -p no:cacheprovider
gate: Quick failed. the last lines of its output:
>       report, _ = _run_main(tmp_path, "ok")
                    ^^^^^^^^^^^^^^^^^^^^^^^^^

tests/http_api/test_chief_routes.py:572: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

tmp_path = PosixPath('/tmp/pathly-tests/tmp1dob7pmr'), mode = 'ok'

    def _run_main(tmp_path: Path, mode: str) -> tuple[dict, str]:
        """``main()`` serves on a free port: it leaves the sessions alone when something already
        answers on the one it would serve (chief-agent 20), and the default is a server that other
        tests, or a developer, may have running."""
        home = tmp_path / "main-home"
        home.mkdir()
        env = {
            **os.environ,
            "HOME": str(home),
            "USERPROFILE": str(home),
            "PYTHONPATH": str(SRC),
            "PATHLY_FSM_HTTP_PORT": str(_free_port()),
        }
        done = subprocess.run(
            [sys.executable, "-c", MAIN_SCRIPT, mode],
            env=env,
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=120,
        )
>       assert done.returncode == 0, done.stderr
E       AssertionError: Error: Flask not installed. Install with: pip install flask
E         
E       assert 1 == 0
E        +  where 1 = CompletedProcess(args=['/usr/bin/python', '-c', '\nimport importlib, json, sys\napp_module = importlib.import_module("... None,\n}))\n', 'ok'], returncode=1, stdout='', stderr='Error: Flask not installed. Install with: pip install flask\n').returncode

tests/http_api/test_chief_routes.py:567: AssertionError
=========================== short test summary info ============================
FAILED tests/http_api/test_chief_routes.py::test_main_closes_a_session_the_last_process_left_open_before_serving
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 4301 passed, 2 skipped in 1224.90s (0:20:24)
