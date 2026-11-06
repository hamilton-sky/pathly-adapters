# Learnings: chief-autopilot-round-two

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.
- (01) `python scripts/gen_test_index.py --check` goes stale when you add a test to an existing file too (the INDEX counts tests): rerun the generator after any test edit.
