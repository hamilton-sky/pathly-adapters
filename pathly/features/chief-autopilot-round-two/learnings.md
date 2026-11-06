# Learnings: chief-autopilot-round-two

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.
- (01) `python scripts/gen_test_index.py --check` goes stale when you add a test to an existing file too (the INDEX counts tests): rerun the generator after any test edit.
- (02) To prove a consult without a spawn host, pass `spawn_fn` that `eventlog.append_event`s an AGENT_DONE carrying the given `run_id`, and call `start_consult(..., block=True)`. A parked single-run task has no claim, so `asking_task` misses it: read the route's `task_id`.
- (02) The provenance scan in `tests/comms_board/test_comms_provenance.py` rejects any `post_message` with a non-constant `author_*` keyword: a server row authored as a role goes through a named stamp (`consult_stamp`), and changing `tests/comms_board/test_comms_provenance.py` changes `tests/comms_board/INDEX.md` too.
- (02) A test that monkeypatches `consult_routes.routes_for_questions` (to fake a racing caller) must `monkeypatch.undo()` before reading the route back with the same function.
- (03) A consult test that needs git measuring builds its own repo under `tmp_path` (`git init`, a tracked file, one commit): `proof/tree.snapshot` returns None unless the project root is the git top, so 02's plain `tmp_path` project always takes the "not measured" path.
