# Parse and run task check blocks with a shared command runner

Type: task
Status: open
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
