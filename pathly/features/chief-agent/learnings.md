# Learnings: chief-agent

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- (01) Lint chain from `commands.md` takes about a minute; piping it through `tail` hides its exit code, so read `${PIPESTATUS[0]}` or run it unpiped. The Test command takes about 5 minutes here: run it in the background and wait on its log.
- (01) `gen_test_index.py` rewrites `tests/INDEX.md` and `tests/<domain>/INDEX.md` when a test file is added, so a "test-only" commit leaves those two files for the final commit, and `gen_test_index.py --check` in Lint fails until they are committed.
