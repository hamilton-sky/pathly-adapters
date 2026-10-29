# Learnings: chief-autopilot

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- (01) `python -m pytest tests/runner_supervisor -q` takes about 3 minutes (356 tests): run it in the background or with a long timeout.
- (01) A fresh container has no `studio/node_modules`, so Build's typecheck fails with TS2688 'vite/client': run Setup's `npm --prefix studio ci` first.
- (01) Tests that spawn a subprocess with `HOME` set to a temp dir (e.g. `test_chief_routes.py -k main`) cannot see user site-packages: deps installed only with `pip install --user` fail there with "Flask not installed"; install them system-wide.
- (01) The Lint chain needs `bandit` on PATH (CI uses 1.9.4); a fresh container may lack it and Lint ends with "bandit: command not found": `pip install bandit==1.9.4`.
