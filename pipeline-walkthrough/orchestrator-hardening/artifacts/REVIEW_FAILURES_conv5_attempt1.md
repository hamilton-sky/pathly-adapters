# Review Failures — orchestrator-hardening Conv 4+5

## Violations

### [ARCH] src/install_cli/materialize.py:1,12 — _hook_script_path bypasses resources.py abstraction
`_hook_script_path` calls `importlib.resources.files("pathly_hooks")` directly. `resources.py` exports `hooks_path()` which is the project-mandated abstraction for this. `setup_command.py` already uses `hooks_path()` correctly (line ~106). Fix: import `hooks_path` from `.resources` and rewrite `_hook_script_path` to call it.

### [IMPL] src/pathly_orchestrator/state.py:12 — Docstring uses "name" key instead of "current"
Inline schema block shows `"name": "<FSM state name>"`. The authoritative required key in `schemas/state.schema.json` is `"current"`. Fix: rename `"name"` → `"current"` in the docstring example.

### [IMPL] src/pathly_orchestrator/state.py:65 — Example comment uses "name" key instead of "current"
Example STATE.json comment block shows `"name": "REVIEWING"`. Fix: rename to `"current": "REVIEWING"`.

### [IMPL] src/install_cli/setup_command.py:217-225 — Hook deploy not rolled back in except handler
`deploy_codex_hooks` / `deploy_copilot_hooks` calls sit inside the `try` block but the `except` block has no corresponding `remove_codex_hooks` / `remove_copilot_hooks` calls. A failure after hook deployment leaves hooks written while the rest of the install is rolled back. Fix: add `remove_codex_hooks()` / `remove_copilot_hooks()` calls to the `except` block for the respective hosts.

## Warnings (non-blocking)
- `materialize.py:103` — `dest: Path = None` should be `dest: Path | None = None`
- `test_materialize_hooks.py` — `test_deploy_codex_hooks_writes_pathly_key` only exercises dry_run, not the actual write path
