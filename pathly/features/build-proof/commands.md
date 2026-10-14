# Commands: build-proof

The real commands for this project, read from its own CI (`.github/workflows/test.yml`,
`lint.yml`, `publish.yml`) and the root `CLAUDE.md`. Approved by a human when the plan is
approved. Workers read this file and must not change it.

The flow runs Smoke before every ticket and Build, Test and Lint after every ticket, so each
must run without asking anything and exit non zero on failure. Run them from the repo root with
the dev install active (`pip install -e ".[dev]"` plus `bandit`, as CI does). Only `python`, the
installed tools and `&&` are used, so they work under `bash -c` and `cmd.exe`.

Build is the project's own package build (`python -m build` in the root `CLAUDE.md` and
`publish.yml`), limited to the wheel. It writes only gitignored paths (`build/`, `dist/`,
`src/*.egg-info/`) and needs package-index access for its isolated build environment (measured
here: 9 s, exit 0).

This plan changes no Studio code, so Studio's typechecks and vitest are left out. Test is the
full Python suite: the seven domain folders this plan touches took 5m48s on their own, and the
full suite took 6m20s (2371 passed), so the subset would save almost nothing.

Build: `python -m build --wheel`
Test: `python -m pytest tests/ -q -x -p no:cacheprovider`
Lint: `black --check src/ tests/ && mypy src/ --ignore-missing-imports --no-strict-optional && python scripts/check_file_size.py && python scripts/check_no_mirror_reads.py && python scripts/gen_test_index.py --check && lint-imports && bandit -q -r src/ -ll -x src/pathly_data/ && python scripts/check_adapters.py && python scripts/check_entry_points.py`
Smoke: `python scripts/check_file_size.py && python -c "import sys; sys.path.insert(0, 'src'); import pathly_orchestrator.http_server.app, pathly_orchestrator.supervisor.orchestrator, pathly_orchestrator.fsm.gates, pathly_orchestrator.fsm_ops, pathly_orchestrator.skills.compose"`
