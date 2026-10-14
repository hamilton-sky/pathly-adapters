# Parse and run task check blocks with a shared command runner

Type: task
Status: resolved
Blocked by: —
Test first: yes

Create the package `src/pathly_orchestrator/proof/` (an `__init__.py` with a one-line docstring)
with two modules. Both are stdlib only and import nothing else from `pathly_orchestrator`.

`proof/command.py` is the one way this feature runs a command, extracted from
`fsm/gates/command.py`:

- `to_argv(command)`: today's `_to_argv`. `shlex.split`, or a JSON list when the text starts
  with `[`.
- `clip(text)`: today's `_clip`, head 3000 and tail 5000.
- `run_command(command, cwd, timeout, extra_env=None) -> CommandResult`. This is the
  `subprocess.run` call now inside `check_command_gate`: no shell, `capture_output`,
  `text=True`, the timeout, and `env={**os.environ, **extra_env}`. A `TimeoutExpired` gives
  `timed_out=True` with whatever output was captured (keep `_decode`). An `OSError` or
  `ValueError` gives `code=None` and `error=str(exc)`. It never raises.

Then make `check_command_gate` call `to_argv` and `run_command`. Its skip, fail-closed and
feedback text stay exactly as they are; `PATHLY_VERIFY_GATE=1` is passed through `extra_env`.
Keep the names `_clip` and `_to_argv` importable from `fsm/gates/command.py` (an import alias is
enough). `tests/fsm_flows/test_command_gate.py` imports them.

`proof/checks.py` ports feature-flow's `proof.checks_in` and `_run_checks`
(`/home/claude/hamilton-sky/feature-flow/feature_flow/proof.py`), with two differences:

- `checks_in(text)` reads every ```check fence anywhere in the text, not only under
  `## Done when`.
- Commands run through `run_command` with `cwd` given by the caller, not through `bash -c`.

The grammar and the `ParseError` messages stay feature-flow's: `$ <command>`, `exit <N>` or
`exit nonzero` (default `exit 0`), `prints <text>`, `#` comments and blank lines.
`run_checks(checks, cwd, timeout)` runs every check (it does not stop at the first failure) and
returns `(ok, report)`. The report has one block per failing check: `$ <command>`,
`wanted: exit 0 and output containing '…'`, `got: exit 3` (or `timed out after <N>s`, or
`could not run: <error>`), and the `clip`ped output.

Living docs: in `src/pathly_orchestrator/CLAUDE.md`, next to the `command_gate` description, one
line saying commands run through `proof/command.py`, and a short paragraph on the check-block
grammar.

## Not in this ticket

- Running check blocks after a task reports success: ticket 05 (goal-loop) and ticket 07 (team
  flows).
- Teaching the planner to write check blocks: ticket 13.

## Done when

- `python -m pytest tests/fsm_flows/test_proof_checks.py -q -p no:cacheprovider` passes. It
  covers: two fences in one text parse into the right `Check` list; `exit nonzero` and two
  `prints` lines; a `prints` before any `$` line and an unclosed fence raise `ParseError`; a
  check that exits 3 gives `ok=False` with `$ `, `wanted: exit 0` and `got: exit 3` in the
  report; a command that does not exist gives `could not run`; a 1-second timeout on a sleeping
  command is reported as timed out; a passing block gives `(True, "")`.
- `python -m pytest tests/fsm_flows/test_command_gate.py -q -p no:cacheprovider` still passes.
- `src/pathly_orchestrator/proof/` imports nothing from `pathly_orchestrator`: `lint-imports`
  passes (Lint) and
  `python -c "import ast,pathlib;bad=[str(p) for p in pathlib.Path('src/pathly_orchestrator/proof').glob('*.py') for n in ast.walk(ast.parse(p.read_text())) if (isinstance(n,ast.ImportFrom) and (n.level>1 or (n.level==0 and (n.module or '').startswith('pathly')))) or (isinstance(n,ast.Import) and any(a.name.startswith('pathly') for a in n.names))];print('clean' if not bad else bad)"`
  prints `clean`.

```check
# The conductor runs this block before review.
$ python -m pytest tests/fsm_flows/test_proof_checks.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/fsm_flows/test_command_gate.py -q -p no:cacheprovider
exit 0
prints passed
$ python -c "import ast,pathlib;bad=[str(p) for p in pathlib.Path('src/pathly_orchestrator/proof').glob('*.py') for n in ast.walk(ast.parse(p.read_text())) if (isinstance(n,ast.ImportFrom) and (n.level>1 or (n.level==0 and (n.module or '').startswith('pathly')))) or (isinstance(n,ast.Import) and any(a.name.startswith('pathly') for a in n.names))];print('clean' if not bad else bad)"
exit 0
prints clean
```

## Reference

- spec.md § Decisions ("Where a check block lives", "How a check command runs"), § Interfaces
- `src/pathly_orchestrator/fsm/gates/command.py` (`check_command_gate`, `_to_argv`, `_clip`,
  `_decode`)
- `/home/claude/hamilton-sky/feature-flow/feature_flow/proof.py` (read-only)

## Answer

Work started at commit `43993d9a40c4b92bb3491e17519945a773eff5a0`. Test-only commit:
`8eabb4a` (`test(build-proof): 01 failing test`). At that commit the new test fails at
collection with `ModuleNotFoundError: No module named 'pathly_orchestrator.proof'` (exit 2).

**Built**

- `src/pathly_orchestrator/proof/__init__.py` (new): a one-line docstring.
- `src/pathly_orchestrator/proof/command.py` (new): `CommandResult(code, output, timed_out,
  error)`, `to_argv(command: str | list[str])`, `clip(text)`, `run_command(command, cwd,
  timeout, extra_env=None)` and `_decode`. Stdlib only.
- `src/pathly_orchestrator/proof/checks.py` (new): `Check`, `ParseError`, `checks_in(text)`,
  `run_checks(checks, cwd, timeout)`. Imports only `.command` (relative, level 1).
- `src/pathly_orchestrator/fsm/gates/command.py`: `check_command_gate` now calls `_to_argv`
  and `run_command(argv, cwd, timeout, extra_env={"PATHLY_VERIFY_GATE": "1"})`. `_clip` and
  `_to_argv` are import aliases of `proof.command.clip` / `to_argv`. The local `_to_argv`,
  `_clip`, `_decode`, `_HEAD_CHARS`, `_TAIL_CHARS` and the unused `os`/`shlex`/`subprocess`
  imports are gone (moved). Skip, fail-closed and feedback text are unchanged.
- `src/pathly_orchestrator/CLAUDE.md`, § Transition gates: one line saying the gate's command
  runs through `proof/command.py`, and a paragraph on the check-block grammar.
- `tests/fsm_flows/test_proof_checks.py` (new, 18 tests) and the regenerated
  `tests/fsm_flows/INDEX.md`, `tests/INDEX.md`.

**Proof** (each run fresh after the last edit)

- `python -m pytest tests/fsm_flows/test_proof_checks.py -q -p no:cacheprovider`:
  `18 passed in 1.31s`, exit 0. Covers two fences in one text (one before any heading, one
  after a `## Notes` heading, with a non-check fence between them that is skipped) ->
  `[Check("python -m pytest tests/test_widget.py -q", 0, ("passed",)), Check('python -c "print(1)"', 2, ())]`;
  `exit nonzero` + two `prints` lines; `prints` before `$` -> `ParseError` ("comes before the
  first"); unclosed fence -> `ParseError` ("never closed"); exit 3 -> `ok=False` with
  `$ <cmd>`, `wanted: exit 0`, `got: exit 3` and the command's output in the report; a missing
  binary -> `could not run`; `time.sleep(30)` with timeout 1 -> `timed out after 1s`; a
  passing block -> `(True, "")`. Also: every check runs after a failure, a `prints` miss on
  exit 0, the cwd is honoured, second-`exit`/bad-exit/unreadable lines raise, `run_command`
  passes `extra_env` and captures both streams, and never raises on an unparseable command.
- `python -m pytest tests/fsm_flows/test_command_gate.py -q -p no:cacheprovider`:
  `21 passed in 6.09s`, exit 0.
- The AST import check printed `clean`, exit 0. `lint-imports`: `Contracts: 1 kept, 0 broken.`,
  exit 0.
- Full Lint command from `commands.md`: exit 0 (black 491 files unchanged; mypy
  `Success: no issues found in 279 source files`; file size `none new, none grown`; mirror reads
  OK; test INDEX up to date; lint-imports kept; bandit no findings; adapters OK; entry points OK).
- Smoke: exit 0. Build (`python -m build --wheel`): `Successfully built
  pathly_adapters-2.24.1-py3-none-any.whl`, exit 0, and the wheel lists
  `pathly_orchestrator/proof/{__init__,checks,command}.py`.
- Test (`python -m pytest tests/ -q -x -p no:cacheprovider`): `2389 passed, 14 skipped in
  440.12s`, exit 0.

**Decisions**

- `run_command` calls `to_argv` itself, so it accepts a string or an argv list and a parse
  error becomes `code=None, error=...` (it never raises). The gate still calls `_to_argv` first
  so an unparseable setting keeps its own "could not be parsed" feedback; it then passes the
  argv list, which `to_argv` returns as is.
- `CommandResult.code` is `None` both on timeout (`timed_out=True`, `error=None`) and when the
  command could not run (`timed_out=False`, `error=str(exc)`). The gate checks `timed_out` first.
- `checks_in` keeps feature-flow's line loop and its exact `ParseError` messages, but holds the
  current check in typed locals instead of feature-flow's mixed list (mypy reads that list as
  `list[object]` and rejects `.append`).
- Report block: `$ <command>`, `  wanted: ...`, `  got: ...`, `  its output:` and the
  `clip`ped output (`(no output)` when empty), blocks joined by a newline as in feature-flow.
  `wanted` keeps feature-flow's `output containing %r` quoting. `run_checks`'s timeout is in
  seconds and is reported with `format(timeout, "g")`, so `1` reads `timed out after 1s`.
- The test file uses `pytestmark = pytest.mark.no_pathly_autouse`: the code under test touches
  no DB, so the DB/rate-limit autouse fixtures are not needed.

**Shortcuts taken**

- `run_checks` passes `timeout` straight to `subprocess.run`, so `0` means "time out at once",
  not "no timeout" as in feature-flow. Every caller in this plan gives a positive timeout; if a
  caller ever needs "no limit" it should pass `None` (the type would need widening).
- No size cap on the combined report: each block is clipped to 8000 characters, but a task
  with many failing checks yields many blocks. Tickets 05/07 append it to prompts and feedback
  files and must clip the whole report if that matters (map.md: argv cap).

**For later tickets**

- Import as `from pathly_orchestrator.proof.checks import Check, ParseError, checks_in,
  run_checks` and `from pathly_orchestrator.proof.command import CommandResult, clip,
  run_command, to_argv`. `checks_in` raises `ParseError`; callers (05, 07) must catch it and
  treat it as a failed check (`TASK_PROOF checks: "error"` per spec), not let it escape.
- `src/pathly_orchestrator/CLAUDE.md`'s check-block paragraph ends with "Nothing runs them
  yet." Ticket 05 or 07 should change that sentence when it wires `run_checks` in.
- Floor scans (ticket 02) should not flag `proof/command.py` or the gate: neither has a
  suppression comment, and the gate's `# type: ignore[arg-type]` in `_resolve_timeout` is
  pre-existing and untouched.
