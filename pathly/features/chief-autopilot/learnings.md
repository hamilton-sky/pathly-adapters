# Learnings: chief-autopilot

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- (01) `python -m pytest tests/runner_supervisor -q` takes about 3 minutes (356 tests): run it in the background or with a long timeout.
- (01) A fresh container has no `studio/node_modules`, so Build's typecheck fails with TS2688 'vite/client': run Setup's `npm --prefix studio ci` first.
- (01) Tests that spawn a subprocess with `HOME` set to a temp dir (e.g. `test_chief_routes.py -k main`) cannot see user site-packages: deps installed only with `pip install --user` fail there with "Flask not installed"; install them system-wide.
- (01) The Lint chain needs `bandit` on PATH (CI uses 1.9.4); a fresh container may lack it and Lint ends with "bandit: command not found": `pip install bandit==1.9.4`.
- (03) Golden snapshots have no regen script: write `compose_skill(skill, "claude")` into each `tests/snapshots/<skill with / as __>.claude.md` that differs (sys.path src + tests for `_paths.SNAPSHOT_DIR`).
- (03) To re-export a moved function without a `# noqa`, give the old module an `__all__` listing its public functions plus the re-export; `check_file_size.py --update` also lowers any other baseline that shrank on the branch.
- (10) A test that audits file opens can see `pipe:[N]` from `/proc/self/fd` readlink when torch is first imported in the process (`ctypes.util.find_library` runs `ldconfig` through a pipe): treat a non-absolute readlink target as no file.
- (02) `python -m pytest tests/http_api tests/runner_supervisor -q -k chief` takes about 16 minutes (2413 tests): run it in the background.
- (05) To drive a whole board spawn in a test, call `_run_stage_via_terminal` with a broadcast that acts on TERMINAL_SPAWN (claim with `payload['run_token']`, then `get_run(run_id).mark_started()` + `mark_pty_result`); for early-advance skip the PTY result, set `state.interactive=False` and monkeypatch `terminal._reconciliation_window`.
- (06) To post a question as the run in a test, POST /comms/post with the TERMINAL_SPAWN payload's `run_token` in `X-Pathly-Run-Token`; `stamp` sets `author_run_id` to the run. `tests/dag_goals tests/comms_board tests/install_skills` takes about 7 minutes.
- (07) A built-in chief style must stay under 4000 characters (`test_chief_cli.py`), a quoted bare word on a `pathly help` line is read as a body key (`test_chief_help_routes.py`), and every `pathly api` example in a style is really run by an operator chief with no spawn allowed, so a flow start or retry cannot be an example.
- (08) Flask runs `after_request` hooks in reverse registration order; a hook that needs `g.chief_run_slot` must be registered after `refund_run_slot`, which pops it. A retry answers 200 `ok: false` with the old run id.
- (08) `run_history.status = parked` is final for that run id (resume mints a new one), so treat it as an end. `comms_messages` has no project column: a board is its scope string, shared by same-named features of different projects. `tests/http_api -k "chief_gate or chief_notices"` takes about 9 minutes.
- (12) To drive a real goal-loop run in a test without the fsm_flows harness: git-init a tmp project, set `code_context.backend` off, patch `fsm_http_client.next_action`/`complete_stage` to `fsm_ops.next_action`/`fsm_ops_complete.complete_stage` and `supervisor._run_stage_via_terminal` to a fake, then `supervisor.start_run(flow="goal-loop", interactive=False, on_done=...)` (see `tests/dag_goals/test_loop_task_waits.py`).
- (14) To drive a loop goal end to end in a test, call `goal_executor.start_goal_run(goal_id, executor_override="loop", project_root=..., on_done=...)` after the (12) patches; the run's registry key is its topic, so find it by `run_id` to pop it. The sentence-transformers 403 ProxyError in captured logs is noise.
