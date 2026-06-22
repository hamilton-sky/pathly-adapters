# Architecture Risk Assessment

_Exploration: `architecture-risk-assessment` — conducted 2026-05-13_
_Full trace and conclusions: `pathly/explorations/architecture-risk-assessment/`_

---

> **Re-audit note (2026-06-22, v2.16.2):** several risks below are resolved — CI now exists (6 GitHub Actions workflows: `test.yml`, `studio-ci.yml`, `e2e.yml`, `lint.yml`, `publish.yml`, `studio-release.yml`), `check_version_sync.py` shipped, Codex and Antigravity adapters shipped.

---

## Risk 1 — Hook contract mismatch: spec says exit 0, code exits 1

### Description

Both hook scripts (`src/pathly_hooks/classify_feedback.py:34-37` and
`src/pathly_hooks/inject_feedback_ttl.py:54-57`) exit with code **1** when
`PATHLY_PROJECT_ROOT` is not set. The original design specification
(`pathly/plans/.archive/orchestrator-hardening/IMPLEMENTATION_PLAN.md:36`)
required a **silent exit 0** (no-op). The README (`line 126`) is ambiguous —
it says "exits immediately without performing any action" without specifying the
exit code.

Compounding this: the installer (`src/install_cli/setup_command.py`) never sets
`PATHLY_PROJECT_ROOT` and provides no guidance on how to set it persistently.
If the user's shell does not export it, every hook invocation fails silently from
the user's perspective (the host tool continues, but feedback classification and
TTL injection never happen).

**Severity: Moderate**

**Status (2026-06):** still open — hook exit-code contract and PATHLY_PROJECT_ROOT guidance not yet resolved.

### Proposed solution

**Decision required first:** choose one of two contracts and make everything consistent.

**Option A — Own exit 1 (failure is intentional):**
1. Keep hook code as-is (exit 1 on missing env var).
2. Update README to say explicitly: hooks exit 1 when `PATHLY_PROJECT_ROOT` is not set.
3. Add a post-install step in `setup_command.py` that emits a shell-profile snippet
   (`export PATHLY_PROJECT_ROOT=$(pwd)`) and tells the user to add it to `~/.bashrc`
   or `~/.zshrc`.
4. Optionally: add a `pathly-check` CLI command that validates the environment and
   reports whether hooks will fire.

**Option B — Revert to exit 0 (silent no-op, original spec):**
1. Change `classify_feedback.py:37` and `inject_feedback_ttl.py:57` from `sys.exit(1)`
   to `sys.exit(0)` on the missing-env-var branch.
2. Update `tests/test_hooks.py:193` assertion from `returncode != 0` to `returncode == 0`.
3. Write a one-line diagnostic to `~/.pathly/hook.log` on each silent skip, so failures
   are observable without being noisy.
4. Update README to state: hooks are silent no-ops when dependencies are missing;
   check `~/.pathly/hook.log` to verify they are firing.

---

## Risk 2 — Codex adapter unverified on a clean machine

### Description

The Codex adapter (`src/install_cli/codex_plugin_config.py`) is correctly coded
for the happy path — it handles a missing `~/.codex/config.toml` (creates it) and
a missing `codex` CLI (graceful fallback). However, four file-write calls at lines
40, 47, 96, and 148 have **no exception handling**: a permission error on `~/.codex/`
produces a raw `OSError` with no user-friendly message and an unconfirmed rollback.

No CI pipeline exists (`.github/` is absent). No end-to-end clean-machine smoke test
has been run. The README Known Limitations section (`line 120`) correctly flags this.

**Severity: Moderate (before any public Codex claim)**

**Status (2026-06):** partially resolved — CI now exists (6 workflows); Codex adapter shipped. Unguarded writes and clean-machine smoke test remain open.

### Proposed solution

1. **Wrap the four unguarded writes** in `codex_plugin_config.py` with try/except
   that raises a descriptive `RuntimeError`, e.g.:
   ```python
   try:
       plugin_root.mkdir(parents=True, exist_ok=True)
   except OSError as exc:
       raise RuntimeError(
           f"Cannot create Codex plugin directory {plugin_root}: {exc}\n"
           "Check that ~/.codex/ is writable."
       ) from exc
   ```
2. **Add two unit tests** to `tests/test_codex_plugin_config.py`:
   - `test_install_codex_plugin_no_codex_cli_in_path`: call `install_codex_plugin()`
     with `discover_cli=True` and `shutil.which` returning None — verify fallback
     to config.toml edit and exit 0.
   - `test_install_codex_plugin_permission_denied`: mock `Path.mkdir` to raise
     `PermissionError` — verify a `RuntimeError` with a readable message is raised.
3. **Add a CI workflow** (`.github/workflows/test.yml`) running `pytest` on
   Python 3.11–3.13 using a temp `$HOME` directory to simulate a clean machine.
4. **Remove the Known Limitations flag** from README only after a real
   clean-machine install is verified manually.

---

## Risk 3 — Event schema unversioned; public CLI has no migration story

### Description

`pathly-events` and `pathly-state` are registered as public `console_scripts`
in `pyproject.toml:18-19`. The CLI (`src/pathly_orchestrator/eventlog.py:138`)
reads raw EVENTS.jsonl and hard-codes field names (`type`, `agent`, `tokens_in`,
etc.). No `schema_version` field exists in any event. If a field is renamed,
the CLI silently returns wrong or empty output for all existing `.jsonl` files
on disk — no error, no warning, no recovery path.

`src/pathly_orchestrator/events.py` defines the schema only as comments; nothing
prevents a field rename from shipping without a migration step.

**Severity: Moderate (latent — no field renames planned, but no guard exists)**

**Status (2026-06):** still open — no schema_version field added yet.

### Proposed solution

1. **Add `schema_version: 1` to every appended event** in `eventlog.py:append_event()`:
   ```python
   event.setdefault("schema_version", 1)
   ```
2. **Add a version check in `read_events()`**: warn (do not fail) if
   `schema_version` is missing or higher than the current known version.
3. **Add a migration note to `events.py` module header**:
   > "CLI consumers depend on field names. Any field rename requires a `schema_version`
   > bump and a migration function here before merging."
4. **Document `pathly-events` and `pathly-state` as internal tools** in README —
   not stable public API. Add a note: "Field names and output format may change
   between minor versions."
5. **Future (when needed):** add a `migrate_events(feature, from_version, to_version)`
   utility that rewrites EVENTS.jsonl in place, preserving the original as
   `EVENTS.jsonl.bak`.

---

## Risk 4 — Version drift: stale docs, no CI gate

### Description

`pyproject.toml:7` was at version `2.3.0` at audit time (now `2.16.2`). Two files were out of date:
- `docs/SECURITY.md:6` — says `1.0.0` (2 major versions stale)
- `CHANGELOG.md:2` — last entry is `2.1.0`; versions 2.2.0 and 2.3.0 are undocumented

No automated check enforces version consistency between `pyproject.toml` and docs.
Version bumps are not gated on documentation updates.

**Severity: Low (no functional impact; erodes trust and loses release history)**

**Status (2026-06):** partially resolved — CI now exists (6 workflows); `scripts/check_version_sync.py` shipped. SECURITY.md and CHANGELOG backfill status unknown.

### Proposed solution

1. **Immediate fix:**
   - Update `docs/SECURITY.md:6` from `1.0.0` to `2.3.0`.
   - Backfill `CHANGELOG.md` with entries for 2.2.0 and 2.3.0
     (even brief: "Internal refactor, no breaking changes" is better than nothing).

2. **Process fix — `scripts/check_version_sync.py` (shipped):**
   ```python
   import re, sys
   from pathlib import Path
   version = re.search(r'^version = "(.+)"', Path("pyproject.toml").read_text(), re.M).group(1)
   stale = [p for p in ["README.md", "docs/SECURITY.md", "CHANGELOG.md"]
            if version not in Path(p).read_text()]
   if stale:
       print(f"VERSION MISMATCH ({version} not found in): {stale}")
       sys.exit(1)
   ```
   Run this as a pre-release step or wire it into CI (`on: push, tags: 'v*'`).
