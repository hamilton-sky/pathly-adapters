# User Stories — hook-security-fixes

## Context

pathly-adapters installs Pathly agent/skill files into AI host tools. Hooks
(`classify_feedback.py`, `inject_feedback_ttl.py`) run as post-tool-call scripts
and receive file paths via JSON on stdin. The installer tracks installed files
in a manifest and supports `--uninstall` to remove them.

Security gaps in `docs/SECURITY.md` require code hardening and new tests before
the project can be labelled production-ready.

---

## Story 1 — Hook path canonicalization

**Delivered by:** Conversation 1

As a developer running Pathly on a shared or CI machine,
I want hook scripts to reject any file path that resolves outside the active
project's `plans/` directory,
so that a malformed or crafted JSON payload cannot cause the hook to write files
to an arbitrary location on the filesystem.

### Acceptance criteria

- [ ] Both `classify_feedback.py` and `inject_feedback_ttl.py` call
  `Path.resolve()` on any path received from stdin before using it.
- [ ] If the resolved path is not relative to the project's `plans/` directory,
  the hook exits with a non-zero exit code and stderr contains exactly:
  `pathly-hook: rejected path outside plans/: <resolved_path>`
  (acceptance check: `stderr contains "pathly-hook: rejected path outside plans/:"`).
- [ ] A valid path under `plans/` proceeds normally — no regression in happy-path
  behavior.

### Edge cases

- Path contains `../` sequences that appear valid as a string but escape `plans/`
  after resolution.
- Symlink pointing outside `plans/` is treated as an escape (resolve follows
  symlinks by default in Python's `Path.resolve()`).
- `plans/` directory itself does not exist — hook exits cleanly rather than
  crashing with an unhandled exception.

---

## Story 2 — Manifest path traversal guard on uninstall

**Delivered by:** Conversation 1

As a user running `pathly-setup --uninstall`,
I want the uninstaller to verify that every path in the manifest resolves within
the expected destination directory before deleting anything,
so that a tampered or stale manifest cannot trick the uninstaller into deleting
files outside the Pathly-managed destination.

### Acceptance criteria

- [ ] `uninstall()` in `src/install_cli/materialize.py` resolves every manifest
  entry against `dest` before any deletion occurs.

  NOTE: Reading `materialize.py` shows this guard is already implemented
  (two-pass: validate-then-delete). The builder must verify the guard is
  present and write the test that confirms it (Story 4). If the guard is absent
  the builder adds it; if already present the builder leaves it and focuses on
  the test coverage.

- [ ] If any entry resolves outside `dest`, `uninstall()` raises `ValueError`
  with a message that includes the offending path, and no files are deleted.
- [ ] Entries that resolve cleanly within `dest` are deleted as normal.

### Edge cases

- Manifest contains a relative path with `../../` that escapes `dest`.
- Manifest file itself is missing — existing warn-and-return behavior is
  preserved.
- `dest` directory does not exist — guard should not raise an unrelated
  `FileNotFoundError` before reaching the traversal check.

---

## Story 3 — Hook path-safety tests

**Delivered by:** Conversation 1

As a maintainer,
I want a test file `tests/test_hooks.py` that exercises the hook path-validation
logic,
so that regressions in hook security are caught automatically by `pytest`.

### Acceptance criteria

- [ ] `tests/test_hooks.py` exists and is collected by `pytest -q` with no
  errors.
- [ ] Test: hook rejects a path that resolves outside `plans/` — the hook
  process exits non-zero.
- [ ] Test: hook accepts a valid path under `plans/` — the hook process exits
  zero (or produces expected output).
- [ ] Test: hook handles malformed JSON on stdin — exits non-zero without
  raising an unhandled exception.
- [ ] Test: hook handles a file that is already tagged (idempotency) — exits
  zero with no duplicate tags written.
- [ ] Test: hook handles a missing `ANTHROPIC_API_KEY` environment variable —
  exits zero (classification is skipped, not an error).

### Edge cases

- Hook scripts may not exist yet as `.py` files (they may be embedded in YAML
  or generated). Builder must locate or create them before writing tests.
- Tests must not require a real Anthropic API key or network access.

---

## Story 4 — Manifest uninstall traversal tests

**Delivered by:** Conversation 1

As a maintainer,
I want the existing test suite to include a test that confirms `uninstall()`
rejects a tampered manifest,
so that the path-traversal guard in `materialize.py` is regression-tested.

### Acceptance criteria

- [ ] `tests/test_setup.py` (or a new `tests/test_materialize.py`) includes a
  test that passes a manifest entry containing `../../` to `uninstall()` and
  asserts that `ValueError` is raised.
- [ ] A complementary test confirms that a clean manifest uninstalls correctly
  and returns the expected file list.
- [ ] `pytest -q` passes with all new tests.

### Edge cases

- `dest` is a `tmp_path` fixture — no real filesystem locations are used.
- Manifest file is written programmatically in the test, not loaded from disk.

---

## Story 5 — MCP config tests

**Delivered by:** Conversation 1

As a maintainer,
I want a test file `tests/test_mcp_config.py` that exercises
`src/install_cli/mcp_config.py`,
so that install and uninstall behavior for the MCP server entry is verified
automatically.

### Acceptance criteria

- [ ] `tests/test_mcp_config.py` exists and is collected by `pytest -q` with no
  errors.
- [ ] Test: `install_mcp_config("claude")` adds a `pathly-telemetry` entry to a
  temp `settings.json` file.
- [ ] Test: `uninstall_mcp_config("claude")` removes the entry from a temp
  `settings.json` file.
- [ ] Test: calling either function with `dry_run=True` makes no changes to the
  file on disk.
- [ ] Test: calling either function when the config file does not exist produces
  a warning on stderr and returns cleanly (no exception).
- [ ] All four scenarios are also covered for the `"codex"` host using a temp
  `config.toml` file.

### Edge cases

- Settings file exists but contains invalid JSON — `install_mcp_config` warns
  and returns without crashing.
- `pathly-telemetry` entry is already present — `install_mcp_config` is
  idempotent: skip if an entry with the name `pathly-telemetry` already exists,
  regardless of its contents (do not overwrite).
- Entry is absent — `uninstall_mcp_config` returns cleanly without error.
- `test_install_idempotent_different_args`: install once, manually modify the
  entry's args, install again — assert the manually modified entry is preserved
  unchanged (not overwritten).

---

## Story 6 — Known Limitations section in README

**Delivered by:** Conversation 2

As a new user evaluating pathly-adapters,
I want a "Known Limitations" section in `README.md`,
so that I understand the constraints before installing and do not file bugs for
documented behavior.

### Acceptance criteria

- [ ] `README.md` contains a section titled `## Known Limitations`.
- [ ] The section documents at minimum:
  - Codex install is unverified on a clean machine (as of current release).
  - Copilot destination paths may need `--repair` after a VS Code update.
  - Hook path validation uses `Path.is_relative_to()`, which requires Python
    3.9+. The project already requires Python 3.11+ so this is always
    satisfied.
  - Hook support is not available on Windows (if applicable — builder should
    verify).
- [ ] The section is placed after the existing content and before any
  "Contributing" or footer section (or at the end if neither exists).
- [ ] No existing README content is removed or reworded.

### Edge cases

- The section already exists — builder checks before adding to avoid
  duplication.
