# Commands: role-read-policy

The real commands for this project, read from its own CI (`.github/workflows/test.yml`,
`lint.yml`) and the root `CLAUDE.md`. Approved by a human when the plan is approved. Workers read
this file and must not change it.

The flow runs Smoke before every ticket and Build, Test and Lint after every ticket, so each
must run without asking anything and exit non zero on failure. They run through `cmd.exe` on
Windows and `bash -c` elsewhere: only `python` and `&&` are used, so both work. Run from the repo
root with the dev install active (`pip install -e ".[dev]"`).

The full suite takes about 10 minutes, so Test after each ticket covers the four test domains
this feature touches. Ticket 10 runs the full suite once.

Build: `python -m compileall -q src/pathly_orchestrator`
Test: `python -m pytest tests/comms_board tests/db tests/runner_supervisor tests/http_api -q -x -p no:cacheprovider`
Lint: `black --check src/ tests/ && python scripts/check_file_size.py && python scripts/check_no_mirror_reads.py && python scripts/gen_test_index.py --check && lint-imports`
Smoke: `python -c "import pathly_orchestrator.http_server.app, pathly_orchestrator.supervisor.terminal"`
