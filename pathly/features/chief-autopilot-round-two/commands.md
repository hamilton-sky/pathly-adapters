# Commands: chief-autopilot-round-two

The real commands for this project, read from its own CI (`.github/workflows/test.yml`,
`lint.yml`, `studio-ci.yml`) and the root `CLAUDE.md`: round one's
`pathly/features/chief-autopilot/commands.md`, unchanged except `Shared:` (adds the golden
snapshots, which tickets 07 and 08 both regenerate, `src/pathly_orchestrator/http_server/app.py`,
where tickets 04 and 17 register hooks, and the skill composition and data-layer `CLAUDE.md`,
which tickets 02 and 07 both change, and `studio/src/main/ipc/terminal.ts`, which tickets 10 and
18 both change) and `Sensitive:` (adds the consult modules, which spawn paid agents, the
provenance values, and the chief hook, child-environment, secret-claim and prompt-injector files tickets 14, 15 and 18 change). Approved by a human when the plan is approved. Workers read this file and must
not change it.

The flow runs Smoke before every ticket and Build, Test (or Quick mid-plan) and Lint after every
ticket, so each must run without asking anything and exit non zero on failure. Run them from the
repo root after Setup (the dev install, `import-linter==2.14` as CI pins it, `bandit` as CI uses
it, and Studio's packages). Only installed tools and `&&` are used, so they work under `bash -c`
and `cmd.exe`.

Build is the wheel build plus Studio's renderer typecheck (`npm run typecheck`,
`tsconfig.web.json`); ticket 10 also runs the main-process typecheck (`tsconfig.node.json`) in its
own check block, as `studio-ci.yml` does on the PR. Test covers the domains this plan touches;
ticket 12 runs the full suite once. Quick is Test's Python part without Studio and `tests/install_skills`
(the golden snapshots), for the tickets in the middle of the plan; the tickets that change a
snapshot (07, 08) or Studio (10, 14, 18) run those in their own check blocks. Test and Quick include
`tests/fsm_flows` (ticket 05 changes `supervisor/orchestrator.py`), `tests/telemetry` (ticket 16
changes the billing and category path) and `tests/consistency` (`test_fragments_run_token.py`
scans the skill and fragment markdown tickets 02, 07 and 08 change; `test_chief_tests_use_the_guard.py`
covers the new chief tests of tickets 09, 12, 15 and 18).

Smoke, Build, Test and Lint need Setup first: without it Smoke exits 1 (`pathly_orchestrator` is
not installed and Flask is missing), which is the base being unhealthy, not a wrong command.

Build: `python -m build --wheel && npm --prefix studio run typecheck`
Test: `python -m pytest tests/comms_board tests/db tests/runner_supervisor tests/http_api tests/dag_goals tests/fsm_flows tests/telemetry tests/consistency tests/install_skills -q -x -p no:cacheprovider && npm --prefix studio run test`
Quick: `python -m pytest tests/comms_board tests/db tests/runner_supervisor tests/http_api tests/dag_goals tests/fsm_flows tests/telemetry tests/consistency -q -x -p no:cacheprovider`
Lint: `black --check src/ tests/ && mypy src/ --ignore-missing-imports --no-strict-optional && python scripts/check_file_size.py && python scripts/check_no_mirror_reads.py && python scripts/gen_test_index.py --check && lint-imports && bandit -q -r src/ -ll -x src/pathly_data/ && python scripts/check_adapters.py && python scripts/check_entry_points.py`
Smoke: `python -c "import pathly_orchestrator.http_server.app, pathly_orchestrator.supervisor.terminal, pathly_orchestrator.runner.chief_argv, pathly_orchestrator.supervisor.terminal_reconcile"`
Setup: `pip install -e ".[dev]" "import-linter==2.14" "bandit==1.9.4" && npm --prefix studio ci`
Shared: CHANGELOG.md, src/pathly_orchestrator/CLAUDE.md, studio/CLAUDE.md, tests/INDEX.md, tests/*/INDEX.md, scripts/file_size_baseline.txt, tests/snapshots/, src/pathly_orchestrator/http_server/app.py, src/pathly_data/core/skills/composition.yaml, src/pathly_data/CLAUDE.md, studio/src/main/ipc/terminal.ts
Sensitive: src/pathly_orchestrator/http_server/chief_*, src/pathly_orchestrator/http_server/middleware.py, src/pathly_orchestrator/http_server/run_identity.py, src/pathly_orchestrator/runner/chief_argv.py, src/pathly_orchestrator/supervisor/chief_session.py, src/pathly_orchestrator/supervisor/consult_*, src/pathly_orchestrator/http_server/consult_*, src/pathly_orchestrator/db/queries/consult_routes.py, src/pathly_orchestrator/db/provenance_values.py, src/pathly_hooks/chief_prompt.py, src/pathly_orchestrator/pty_host/host.py, studio/src/main/ipc/terminal/spawnEnv.ts, studio/src/main/ipc/terminal/promptInjector.ts, studio/src/main/ipc/terminal/chiefSecret.ts, *token*, *secret*
