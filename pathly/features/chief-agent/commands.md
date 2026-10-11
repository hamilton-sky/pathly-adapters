# Commands: chief-agent

The real commands for this project, read from its own CI (`.github/workflows/test.yml`,
`lint.yml`) and the root `CLAUDE.md`. Approved by a human when the plan is approved. Workers read
this file and must not change it.

The flow runs Smoke before every ticket and Build, Test and Lint after every ticket, so each
must run without asking anything and exit non zero on failure. Only `python`, `&&` and Studio's
local `tsc` are used, so they run under `cmd.exe` and `bash -c` alike. Run from the repo root with
the dev install active (`pip install -e ".[dev]"`) and `studio/node_modules` installed.

Smoke also proves the prerequisite: it imports the modules role-read-policy (RRP-1..3) builds, so
the run stops before spending anything if that plan has not been built yet.

The full suite takes about 10 minutes; Test covers the domains this feature touches, and ticket 13
runs the full suite once.

Build: `python -m compileall -q src/pathly_orchestrator && studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json && studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.node.json`
Test: `python -m pytest tests/comms_board tests/db tests/runner_supervisor tests/http_api tests/install_skills -q -x -p no:cacheprovider`
Lint: `black --check src/ tests/ && python scripts/check_file_size.py && python scripts/check_no_mirror_reads.py && python scripts/gen_test_index.py --check && lint-imports && python scripts/check_adapters.py`
Smoke: `python -c "import pathly_orchestrator.http_server.app, pathly_orchestrator.runner.read_policy, pathly_orchestrator.runner.provenance, pathly_orchestrator.db.queries.run_tokens"`
