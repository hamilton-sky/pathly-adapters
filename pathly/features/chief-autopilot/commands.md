# Commands: chief-autopilot

The real commands for this project, read from its own CI (`.github/workflows/test.yml`,
`lint.yml`, `studio-ci.yml`) and the root `CLAUDE.md`, the same as `chief-agent/commands.md` with
Studio added because ticket 08 changes Studio. Approved by a human when the plan is approved.
Workers read this file and must not change it.

The flow runs Smoke before every ticket and Build, Test and Lint after every ticket, so each must
run without asking anything and exit non zero on failure. Run them from the repo root with the dev
install active (`pip install -e ".[dev]"` and `import-linter==2.14`, as CI does) and Studio's
packages installed (`npm --prefix studio ci`). Only installed tools and `&&` are used, so they work
under `bash -c` and `cmd.exe`.

Build is the wheel build plus Studio's renderer typecheck (`npm run typecheck`, `tsconfig.web.json`); ticket 08 changes only renderer code, and `studio-ci.yml` still runs the main-process typecheck on the PR. Test covers the domains
this plan touches; ticket 09 runs the full suite once.

Build: `python -m build --wheel && npm --prefix studio run typecheck`
Test: `python -m pytest tests/comms_board tests/db tests/runner_supervisor tests/http_api tests/dag_goals -q -x -p no:cacheprovider && npm --prefix studio run test`
Lint: `black --check src/ tests/ && mypy src/ --ignore-missing-imports --no-strict-optional && python scripts/check_file_size.py && python scripts/check_no_mirror_reads.py && python scripts/gen_test_index.py --check && lint-imports && bandit -q -r src/ -ll -x src/pathly_data/ && python scripts/check_adapters.py && python scripts/check_entry_points.py`
Smoke: `python -c "import pathly_orchestrator.http_server.app, pathly_orchestrator.supervisor.terminal, pathly_orchestrator.runner.chief_argv, pathly_orchestrator.supervisor.terminal_reconcile"`
