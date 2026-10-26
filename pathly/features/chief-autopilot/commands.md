# Commands: chief-autopilot

The real commands for this project, read from its own CI (`.github/workflows/test.yml`,
`lint.yml`, `studio-ci.yml`) and the root `CLAUDE.md`, the same as `chief-agent/commands.md` with
Studio and `tests/install_skills` added (ticket 13 changes Studio; ticket 03 changes a fragment
that the golden snapshots in `tests/install_skills` compose). Approved by a human when the plan is
approved. Workers read this file and must not change it.

The flow runs Smoke before every ticket and Build, Test (or Quick mid-plan) and Lint after every
ticket, so each must run without asking anything and exit non zero on failure. Run them from the
repo root after Setup (the dev install, `import-linter==2.14` as CI pins it, and Studio's
packages). Only installed tools and `&&` are used, so they work under `bash -c` and `cmd.exe`.

Build is the wheel build plus Studio's renderer typecheck (`npm run typecheck`,
`tsconfig.web.json`); ticket 13 changes only renderer code, and `studio-ci.yml` still runs the
main-process typecheck on the PR. Test covers the domains this plan touches; ticket 09 runs the
full suite once. Quick is Test's Python part without Studio and the snapshots, for the tickets in
the middle of the plan. Measured here: Smoke exits 0 after Setup.

Build: `python -m build --wheel && npm --prefix studio run typecheck`
Test: `python -m pytest tests/comms_board tests/db tests/runner_supervisor tests/http_api tests/dag_goals tests/install_skills -q -x -p no:cacheprovider && npm --prefix studio run test`
Quick: `python -m pytest tests/comms_board tests/db tests/runner_supervisor tests/http_api tests/dag_goals -q -x -p no:cacheprovider`
Lint: `black --check src/ tests/ && mypy src/ --ignore-missing-imports --no-strict-optional && python scripts/check_file_size.py && python scripts/check_no_mirror_reads.py && python scripts/gen_test_index.py --check && lint-imports && bandit -q -r src/ -ll -x src/pathly_data/ && python scripts/check_adapters.py && python scripts/check_entry_points.py`
Smoke: `python -c "import pathly_orchestrator.http_server.app, pathly_orchestrator.supervisor.terminal, pathly_orchestrator.runner.chief_argv, pathly_orchestrator.supervisor.terminal_reconcile"`
Setup: `pip install -e ".[dev]" "import-linter==2.14" && npm --prefix studio ci`
Shared: CHANGELOG.md, src/pathly_orchestrator/CLAUDE.md, studio/CLAUDE.md, tests/INDEX.md, tests/*/INDEX.md, scripts/file_size_baseline.txt
Sensitive: src/pathly_orchestrator/http_server/chief_*, src/pathly_orchestrator/http_server/middleware.py, src/pathly_orchestrator/http_server/run_identity.py, src/pathly_orchestrator/runner/chief_argv.py, src/pathly_orchestrator/supervisor/chief_session.py, *token*, *secret*
