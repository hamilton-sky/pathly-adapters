# Commands: chief-agent

The real commands for this project, read from its own CI (`.github/workflows/test.yml`,
`lint.yml`, `publish.yml`, `studio-ci.yml`) and the root `CLAUDE.md`. Approved by a human when the
plan is approved. Workers read this file and must not change it.

The flow runs Smoke before every ticket and Build, Test and Lint after every ticket, so each
must run without asking anything and exit non zero on failure. Run them from the repo root with
the dev install active (`pip install -e ".[dev]"` and `import-linter==2.14`, as CI does). Only
`python`, the installed tools and `&&` are used, so they work under `bash -c` and `cmd.exe`.

Build is the project's own package build (`python -m build` in the root `CLAUDE.md` and
`publish.yml`), limited to the wheel so the sdist already in `dist/` is left alone. It writes only
gitignored paths (`build/`, `dist/`, `src/*.egg-info/`) and needs package-index access for its
isolated build environment (measured here: 4 s, exit 0).

Round one changes no Studio code, so Build and Test leave out the Studio typechecks and vitest;
round two's commands add them. The full suite takes 6 to 8 minutes here, so Test after each
ticket covers the four domains this plan touches (measured: the superset with `install_skills`
and `consistency` took 7m25s and passed); ticket 13 runs the full suite once.

Build: `python -m build --wheel`
Test: `python -m pytest tests/comms_board tests/db tests/runner_supervisor tests/http_api -q -x -p no:cacheprovider`
Lint: `black --check src/ tests/ && mypy src/ --ignore-missing-imports --no-strict-optional && python scripts/check_file_size.py && python scripts/check_no_mirror_reads.py && python scripts/gen_test_index.py --check && lint-imports && bandit -q -r src/ -ll -x src/pathly_data/ && python scripts/check_adapters.py && python scripts/check_entry_points.py`
Smoke: `python -c "import pathly_orchestrator.http_server.app, pathly_orchestrator.supervisor.terminal, pathly_orchestrator.runner.read_policy, pathly_orchestrator.db.queries.run_tokens"`
