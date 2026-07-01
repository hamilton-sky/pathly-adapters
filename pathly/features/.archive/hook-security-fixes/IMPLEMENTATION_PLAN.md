# Implementation Plan — hook-security-fixes

## Overview

Security hardening for pathly-adapters across two focused conversations.
Conversation 1 handles all Python code changes. Conversation 2 handles the
README documentation update only.

---

## Conversation 1 — Python security fixes and tests

**Stories fulfilled:** 1, 2, 3, 4, 5

**Goal:** Harden hook scripts against path traversal, confirm the manifest
uninstall guard exists and is tested, and add test coverage for hooks and
`http_config.py`. The codebase must pass `pytest -q` at the end of this
conversation.

### Phase 1 — Locate hook scripts

Search the full repository for `classify_feedback` and `inject_feedback_ttl`
across all file types before creating anything. Three outcomes:

- **Found as `.py` files:** edit in place.
- **Found embedded in YAML or other config:** extract to `hooks/classify_feedback.py`
  and `hooks/inject_feedback_ttl.py`; update the hook registration to point at
  the new paths.
- **Not found anywhere:** create minimal stubs in `hooks/`, then update
  `src/pathly_data/adapters/claude/_meta/install.yaml` and the codex equivalent
  to register the hooks. Hook scripts that are not referenced by the install
  pipeline deliver no security value.

**Leaves codebase:** runnable (no half-done state).

### Phase 2 — Hook path canonicalization (Story 1)

Add `Path.resolve()` canonicalization to both hook scripts:

1. Parse JSON from stdin.
2. Extract the target file path from the parsed payload.
3. Resolve the path: `resolved = Path(raw_path).resolve()`.
4. Determine the project root's `plans/` directory exclusively via the
   `PATHLY_PROJECT_ROOT` environment variable. If the env var is not set,
   print `pathly-hook: PATHLY_PROJECT_ROOT not set` to stderr and exit 1.
5. Assert `resolved.is_relative_to(plans_dir)`. If not, print
   `pathly-hook: rejected path outside plans/: <resolved_path>` to stderr
   and `sys.exit(1)`.
6. Proceed with normal hook logic only if the guard passes.

**Leaves codebase:** runnable.

### Phase 3 — Verify / add manifest traversal guard (Story 2)

Read `src/install_cli/materialize.py` `uninstall()`. The two-pass guard
(validate-all-then-delete) should already be present. If it is:
- Leave it as-is.
- Proceed to Phase 4.

If it is absent:
- Add a validation pass before deletions: resolve each manifest entry against
  `dest`, raise `ValueError` with the offending path if any entry escapes.

**Leaves codebase:** runnable.

### Phase 4 — New test file: `tests/test_hooks.py` (Story 3)

Create `tests/test_hooks.py`. Use `subprocess` to invoke the hook scripts as
child processes (or import and call their main functions directly if structured
that way). Cover:

- Path outside `plans/` is rejected (non-zero exit).
- Valid path under `plans/` is accepted (zero exit or expected output).
- Malformed JSON on stdin exits non-zero without traceback.
- Already-tagged file is handled idempotently (zero exit, no duplicate tag).
- Missing `ANTHROPIC_API_KEY` skips classification and exits zero.

All tests must be runnable without network access or a real API key.

**Leaves codebase:** `pytest -q` passes.

### Phase 5 — Manifest traversal test (Story 4)

Add to `tests/test_setup.py` (or create `tests/test_materialize.py`):

- Test that `uninstall()` raises `ValueError` when the manifest contains a
  `../../`-style traversal entry.
- Test that `uninstall()` returns the correct file list for a clean manifest
  and deletes the tracked files.

Use `tmp_path` for all filesystem operations.

**Leaves codebase:** `pytest -q` passes.

### Phase 6 — New test file: `tests/test_http_config.py` (Story 5)

Create `tests/test_http_config.py`. Patch `_CLAUDE_SETTINGS` and `_CODEX_CONFIG`
module-level constants (or use `monkeypatch`) to point at temp files.

Cover for both `"claude"` and `"codex"` hosts:
- Install adds entry to temp config file.
- Uninstall removes entry from temp config file.
- `dry_run=True` makes no file changes.
- Missing config file produces a stderr warning and no exception.

Additional edge cases:
- `settings.json` contains invalid JSON — `install_http_config` warns and returns.
- `install_http_config` is idempotent when entry already exists: skip if an
  entry with the name `pathly-telemetry` already exists, regardless of its
  contents. Test `test_install_idempotent_different_args` verifies the entry
  is not overwritten even if its args differ from the default.
- `uninstall_http_config` returns cleanly when entry is absent.

**Leaves codebase:** `pytest -q` passes.

---

## Conversation 2 — README Known Limitations (Story 6)

**Stories fulfilled:** 6

**Goal:** Add a `## Known Limitations` section to `README.md`. No Python changes.

### Phase 1 — Verify no section exists yet

Read `README.md` end-to-end to confirm `## Known Limitations` is absent before
writing.

### Phase 2 — Add Known Limitations section

Append the section to `README.md` with the four documented limitations:
1. Codex unverified on a clean machine.
2. Copilot paths may need `--repair` after a VS Code update.
3. Hook path validation uses `Path.is_relative_to()` (Python 3.9+; project
   already requires 3.11+ so this is always satisfied).
4. Windows hook support status (check the codebase before writing — document
   accurately).

Do not remove or reword existing content.

**Leaves codebase:** `README.md` is valid Markdown, `pytest -q` still passes.

---

## Out of Scope

The following items are explicitly deferred and must not be implemented in this
feature:

- **Partial install / rollback end-to-end test** — deferred to a separate
  security-hardening feature.
- **Hook observability / diagnostic log** — deferred. `docs/SECURITY.md`
  recommends logging hook failures to a project-local diagnostic file; that work
  is out of scope here.

---

## Cross-reference

| Story | Phase(s) | Conversation |
|-------|----------|--------------|
| 1 — Hook path canonicalization | Conv 1 Phase 2 | 1 |
| 2 — Manifest traversal guard | Conv 1 Phase 3 | 1 |
| 3 — Hook path-safety tests | Conv 1 Phase 4 | 1 |
| 4 — Manifest uninstall traversal tests | Conv 1 Phase 5 | 1 |
| 5 — HTTP config tests | Conv 1 Phase 6 | 1 |
| 6 — Known Limitations in README | Conv 2 Phase 2 | 2 |

---

## Files expected to change

**Conversation 1:**
- `hooks/classify_feedback.py` — new or modified
- `hooks/inject_feedback_ttl.py` — new or modified
- `src/install_cli/materialize.py` — may require no change if guard already present
- `tests/test_hooks.py` — new
- `tests/test_setup.py` or `tests/test_materialize.py` — new tests added
- `tests/test_http_config.py` — new

**Conversation 2:**
- `README.md` — Known Limitations section added
