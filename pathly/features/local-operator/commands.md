# Commands: local-operator

The real commands for this project, read from the repo's CI
(`.github/workflows/test.yml`, `lint.yml`, `studio-ci.yml`) and the root
`CLAUDE.md`. Approved by a human when the plan is approved. Workers read
this file and must not change it.

Run from the repo root with the dev install active (`pip install -e
".[dev]"`). Only `python`, the installed tools and `&&` are used, so
they work under `bash -c` and `cmd.exe`.

This plan touches server Python (endpoint verification/wrappers) and
Studio TS (tool loop + picker UI). The Studio typecheck/vitest run in
tickets 03, 04 and the acceptance ticket; per-ticket Test stays on the
Python domains unless the ticket says otherwise.

Build: `python -m build --wheel`
Test: `python -m pytest tests/comms_board tests/db tests/http_api tests/local_operator -q -x -p no:cacheprovider`
Lint: `black --check src/ tests/ && mypy src/ --ignore-missing-imports --no-strict-optional && python scripts/check_file_size.py && python scripts/check_no_mirror_reads.py && python scripts/gen_test_index.py --check && lint-imports && bandit -q -r src/ -ll -x src/pathly_data/ && python scripts/check_adapters.py && python scripts/check_entry_points.py`
Smoke: `python -c "import pathly_orchestrator.chat_agent"`
