# Learnings: build-proof

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.
- (01) The conductor test-first check counts anything under `tests/` as a test file, so the regenerated `tests/**/INDEX.md` can ride in the test-only commit. The full Test command took 7m20s here (2389 passed); run it in the background and poll its log.
