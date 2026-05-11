# Conversation Prompts — hook-security-fixes

---

## Conversation 1 — Python security fixes and tests

**Stories:** 1, 2, 3, 4, 5
**Done when:** `pytest -q` passes with all new tests collected and green.

---

You are implementing security fixes and tests for the `pathly-adapters` project.
Work in the repository at the path you are given. Do not create documentation
files. Run `pytest -q` at the end to confirm all tests pass.

### Context

`pathly-adapters` is a Python CLI (`pathly-setup`) that installs Pathly
agent/skill files into AI host tools (Claude Code, Codex, Copilot). The security
gaps you are fixing are documented in `docs/SECURITY.md`.

Read these files before starting:
- `docs/SECURITY.md`
- `src/install_cli/materialize.py`
- `src/install_cli/mcp_config.py`
- `tests/test_setup.py`

### Task 1 — Locate hook scripts (Phase 1)

**You must search before creating anything.** Run a full-repo search for
`classify_feedback` and `inject_feedback_ttl` across all file types
(`.py`, `.yaml`, `.json`, `.toml`, and any other config format).

Act based on what you find:

**Case A — Found as standalone `.py` files:**
Edit them in place. Do not move or copy them.

**Case B — Found embedded inline in YAML or other config (e.g., `.claude/settings.json` hooks):**
Extract the inline content into `hooks/classify_feedback.py` and
`hooks/inject_feedback_ttl.py`, then update the hook registration in that
config to point to the new file paths.

**Case C — Not found anywhere (scripts do not exist):**
Create minimal stub scripts in `hooks/classify_feedback.py` and
`hooks/inject_feedback_ttl.py`. Each stub must:
- Read JSON from stdin.
- Extract a file path from the parsed payload.
- Perform its intended action (path validation guard will be added in Task 2).

Then update `src/pathly_data/adapters/claude/_meta/install.yaml` and the
codex equivalent to register these hooks so they are actually installed and
used by the pipeline.

Do not invent behavior beyond what is described in `docs/SECURITY.md` —
keep stubs minimal and correct.

**Important:** Do not create hook scripts that are not referenced by the
install pipeline — hooks that are never registered deliver no security value.
If you are in Case C, the install.yaml update is mandatory, not optional.

### Task 2 — Hook path canonicalization (Phase 2, Story 1)

Add path canonicalization to both hook scripts:

1. After parsing JSON from stdin, extract the file path from the payload.
2. Resolve it: `resolved = Path(raw_path).resolve()`.
3. Determine the `plans/` directory exclusively via the `PATHLY_PROJECT_ROOT`
   environment variable: `plans_dir = Path(os.environ["PATHLY_PROJECT_ROOT"]) / "plans"`.
   If `PATHLY_PROJECT_ROOT` is not set, print to stderr:
   `pathly-hook: PATHLY_PROJECT_ROOT not set`
   and call `sys.exit(1)`. Do not use any path-derivation fallback (e.g., "two
   levels above the hook script") — the env var is the only mechanism.
4. Guard: if `resolved.is_relative_to(plans_dir)` is false, print to stderr:
   `pathly-hook: rejected path outside plans/: <resolved_path>`
   then call `sys.exit(1)`.
5. Only proceed with hook logic if the guard passes.

Acceptance check: a path containing `../../` that escapes `plans/` must cause
`sys.exit(1)` and stderr must contain `pathly-hook: rejected path outside plans/:`.
A valid path under `plans/` must proceed normally.

### Task 3 — Verify manifest traversal guard (Phase 3, Story 2)

Read `src/install_cli/materialize.py` `uninstall()` carefully.

If the two-pass guard (validate-all entries before deleting any) is already
present, leave it untouched and move to Task 4.

If the guard is absent, add it:
- Pass 1: for every name in `manifest["files"]`, resolve `dest / name` and
  assert it is relative to `dest.resolve()`. Raise `ValueError` with the
  offending path if any entry escapes.
- Pass 2: perform deletions only after Pass 1 completes without error.

### Task 4 — tests/test_hooks.py (Phase 4, Story 3)

Create `tests/test_hooks.py`. Use `subprocess.run` to invoke the hook scripts,
or import and call their entry-point functions directly.

Required tests:
1. `test_hook_rejects_path_outside_plans` — supply a path like
   `/tmp/../../etc/passwd` in the JSON payload; assert the process exits
   non-zero.
2. `test_hook_accepts_valid_path` — supply a path that is under a `tmp_path /
   "plans"` directory; assert the process exits zero (or produces expected
   output).
3. `test_hook_malformed_json` — send `"not json"` on stdin; assert process exits
   non-zero without an unhandled Python traceback reaching stdout.
4. `test_hook_already_tagged_file` — supply a file that already has the expected
   tags/TTL frontmatter; assert the process exits zero and the file is unchanged.
5. `test_hook_missing_api_key` — unset `ANTHROPIC_API_KEY` in the subprocess
   environment; assert `classify_feedback.py` exits zero (classification
   skipped, not an error).
6. `test_hook_missing_project_root` — omit `PATHLY_PROJECT_ROOT` from the
   subprocess environment entirely; assert the hook exits non-zero and stderr
   contains `pathly-hook: PATHLY_PROJECT_ROOT not set`.

No network calls. No real API key. Use `tmp_path` for all files.

### Task 5 — Manifest traversal test (Phase 5, Story 4)

Add tests to `tests/test_setup.py` (preferred) or create `tests/test_materialize.py`:

1. `test_uninstall_rejects_traversal_in_manifest` — write a manifest that
   contains an entry like `"../../evil_file"`, call `uninstall(dest)`, and
   assert `ValueError` is raised with no files deleted.
2. `test_uninstall_clean_manifest` — write a valid manifest with one tracked
   file, call `uninstall(dest)`, and assert the file is removed and the
   function returns the correct list.

Use `tmp_path`. Write the manifest file programmatically — do not rely on a
pre-existing manifest on disk.

### Task 6 — tests/test_mcp_config.py (Phase 6, Story 5)

Create `tests/test_mcp_config.py`. Redirect `_CLAUDE_SETTINGS` and
`_CODEX_CONFIG` to temp files using `monkeypatch.setattr` on the
`install_cli.mcp_config` module.

Required tests (cover both `"claude"` and `"codex"` hosts):
1. `test_install_adds_entry_claude` — install adds `pathly-telemetry` to
   `settings.json`.
2. `test_uninstall_removes_entry_claude` — uninstall removes the entry.
3. `test_dry_run_no_changes_claude` — `dry_run=True` leaves the file unchanged.
4. `test_missing_config_file_claude` — config file absent; function returns
   cleanly with no exception.
5. Repeat the above four for `"codex"` with a `config.toml` temp file.

Additional edge cases:
6. `test_install_invalid_json_claude` — `settings.json` contains invalid JSON;
   `install_mcp_config` prints a warning to stderr and returns without raising.
7. `test_install_idempotent_claude` — calling `install_mcp_config` twice does
   not create a duplicate entry. Idempotency means: skip if an entry with the
   name `pathly-telemetry` already exists, regardless of its contents.
8. `test_install_idempotent_different_args` — install once, then manually
   modify the `pathly-telemetry` entry's args in the config file, then call
   `install_mcp_config` again. Assert the manually modified entry is preserved
   unchanged (not overwritten by the second install call).
9. `test_uninstall_missing_entry_claude` — entry is absent; `uninstall_mcp_config`
   returns cleanly.

### Completion check

Run `pytest -q` and confirm:
- All new tests are collected.
- All tests pass.
- No existing tests are broken.

If any test fails, fix the implementation or test before finishing.

---

## Conversation 2 — README Known Limitations

**Stories:** 6
**Done when:** `README.md` contains `## Known Limitations` with all four items,
and `pytest -q` still passes.

---

You are making a single documentation change to `README.md` in the
`pathly-adapters` project.

### Context

Read `README.md` end-to-end before writing. Confirm that a `## Known
Limitations` section does not already exist.

Also read:
- `docs/SECURITY.md` — for accurate hook and Python version constraints.
- `docs/PRODUCTION_READINESS.md` — for Codex and Copilot status details.

### Task — Add Known Limitations section (Story 6)

Append a `## Known Limitations` section to `README.md`. Place it after the
last existing section and before any "Contributing" or project-footer section,
or at the end if neither exists.

The section must document these four items accurately (verify each against the
codebase before writing):

1. **Codex install unverified on a clean machine** — the Codex adapter is
   committed and the install command works, but a clean-machine smoke run has
   not been completed. Use Codex support at your own risk until this is
   confirmed.

2. **Copilot paths may need `--repair` after a VS Code update** — Copilot
   destination paths follow the VS Code Copilot agent spec, which may change
   between VS Code versions. Run `pathly-setup --repair` after a VS Code update
   if Copilot agents stop appearing.

3. **Hook path validation requires Python 3.9+** — Hook path validation uses
   `Path.is_relative_to()`, which requires Python 3.9+. The project already
   requires Python 3.11+ so this is always satisfied.

4. **No Windows hook support** — verify this by searching for any Windows-
   specific hook handling in the codebase. If hooks do not run on Windows,
   document it. If they do, omit this item or document the correct status.

Do not remove, reword, or reformat any existing README content.

### Completion check

- Confirm `## Known Limitations` appears exactly once in `README.md`.
- Run `pytest -q` and confirm all tests still pass.
