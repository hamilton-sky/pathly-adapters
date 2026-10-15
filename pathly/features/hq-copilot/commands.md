# Commands: hq-copilot

The real commands for this project, read from the repo's CI
(`.github/workflows/test.yml`, `lint.yml`, `studio-ci.yml`) and the root
`CLAUDE.md` — same as `pathly/features/chief-agent/commands.md`. Approved
by a human when the plan is approved. Workers read this file and must not
change it.

Run from the repo root with the dev install active (`pip install -e
".[dev]"`). Only `python`, the installed tools and `&&` are used, so
they work under `bash -c` and `cmd.exe`.

This plan touches server Python and (ticket 06) Studio TSX. The full
Studio typecheck/vitest runs only in ticket 06 and the acceptance ticket;
per-ticket Test stays on the Python domains this plan touches.

Build: `python -m build --wheel`
Test: `python -m pytest tests/comms_board tests/db tests/http_api tests/hq_copilot -q -x -p no:cacheprovider`
Lint: `black --check src/ tests/ && mypy src/ --ignore-missing-imports --no-strict-optional && python scripts/check_file_size.py && python scripts/check_no_mirror_reads.py && python scripts/gen_test_index.py --check && lint-imports && bandit -q -r src/ -ll -x src/pathly_data/ && python scripts/check_adapters.py && python scripts/check_entry_points.py`
Smoke: `python -c "import pathly_orchestrator.chat_agent, pathly_orchestrator.hq_context"`
