# Learnings: build-proof

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.
- (01) The conductor test-first check counts anything under `tests/` as a test file, so the regenerated `tests/**/INDEX.md` can ride in the test-only commit. The full Test command took 7m20s here (2389 passed); run it in the background and poll its log.
- (02) git refuses a 0-byte `GIT_INDEX_FILE` ("index file smaller than expected"): a private index for a repo with no index yet must be absent, not empty. `git diff` ends a `---`/`+++` name that holds a space with a TAB, and an added line `++ x` prints as `+++ x`, so read names only before a file's first `@@` (`floor._file_diffs` does).
