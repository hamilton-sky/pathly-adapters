# Learnings: chief-agent

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- (01) Lint chain from `commands.md` takes about a minute; piping it through `tail` hides its exit code, so read `${PIPESTATUS[0]}` or run it unpiped. The Test command takes about 5 minutes here: run it in the background and wait on its log.
- (01) `gen_test_index.py` rewrites `tests/INDEX.md` and `tests/<domain>/INDEX.md` when a test file is added, so a "test-only" commit leaves those two files for the final commit, and `gen_test_index.py --check` in Lint fails until they are committed.
- (02) Flask's test client serves a request on the test's own thread, so a route and the test share one thread-local `get_db()` connection: a per-connection pragma or open transaction a route leaves behind is visible to the test (and to the next test step) directly.
- (02) `python3.11`, `python3.12` and `python3.13` all exist in `/usr/bin` here, but only the venv's 3.12 has the project deps; to check a stdlib behaviour on all three, run a tiny script with `python3.NN -I script.py` (no pytest).
- (03) `black` reflows a long tuple in a moved/edited function and can push a file one line past 400 after the edit looks fine: run `black` before judging the size, then use the ticket's split fallback.
- (03) The floor guard flags any added `# noqa` (also on a re-export line copied from its neighbour) and reads only the committed diff `base..HEAD`: run `python3 scripts/floor-guard.py chief-agent NN <base>` after committing, not before. The repo has no flake8 or ruff step, so a re-export needs no `noqa`.
- (04) `skills/prompt_files.py::_ID_RE` ends in `$`, which also matches before a trailing newline, so `read_prompt_file("chief/x\n")` passes the id check (and then finds no file because the row id compare is exact): match names exactly after it, never `strip()` them.
- (04) The `skills` package imports nothing from the orchestrator layers, so `supervisor/` modules can import `skills.*` at module top without a cycle (existing ones import lazily by habit); the autouse conftest fixture patches `Path.home()` to `tmp_path`, so `write_prompt_file(..., scope="global")` in a test lands in a temp dir.
