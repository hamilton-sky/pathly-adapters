---
name: Implementation Plan
---
# security-hardening — Implementation Plan

## Overview
Hardens three attack surfaces identified in the codebase analysis: the Electron terminal IPC (command injection + cwd validation + tabId ownership), the Python package dependency graph (missing `mcp`), and the installer's error handling (unhandled ValueError on manifest corruption, swallowed rollback exceptions). Also adds telemetry opt-out and removes committed build artifacts.

## Layer Architecture

```
Electron Main Process (IPC handlers)
  terminal.ts  ← command allowlist + cwd guard + tabId ownership
  fs.ts        ← already safe, verify only

Python Package
  pyproject.toml       ← add mcp dependency
  pathly_telemetry/    ← opt-out flag + rotation
  install_cli/materialize.py  ← ValueError → RuntimeError
  install_cli/setup_command.py ← log rollback failures

Git
  .gitignore + git rm --cached build/lib/
```

## Prerequisite (pre-flight)
Run existing tests before any change and record failures as baseline:
```
cd studio && npm test 2>&1 | head -40
cd .. && python -m pytest tests/ -q 2>&1 | head -40
```

## Phases

### Phase 1: Terminal IPC — command allowlist   ← Conversation: 1
**File:** `studio/src/main/ipc/terminal.ts`
**Done when:** `terminal:spawn` throws/returns error for any `command` not in the allowlist; valid commands spawn as before.
**Delivers stories:** S1
**Depends on:** nothing
**Enables:** Phase 2
**Details:**
- Define `const ALLOWED_SHELLS = new Set(['bash','zsh','sh','pwsh','powershell.exe','cmd.exe'])` at top of file
- On Windows the auto-shell is always `powershell.exe`; on Unix it is `bash` (these are always allowed)
- If renderer passes a `command` that is not in `ALLOWED_SHELLS`, return early with `event.reply('terminal:error', tabId, 'Shell not allowed')` — do NOT spawn
- Strip the `['-NoExit', '-Command', command]` PowerShell injection vector: if `command` is truthy on Windows, pass only the shell executable — never pass user-supplied string as `-Command` argument
**Verify:** `npm run build:main` in studio/ compiles without errors

### Phase 2: Terminal IPC — cwd validation + tabId ownership   ← Conversation: 1
**File:** `studio/src/main/ipc/terminal.ts`
**Done when:** `terminal:spawn` with a `cwd` outside the home directory returns an error; `terminal:write` with an unowned tabId is silently ignored.
**Delivers stories:** S1, S2
**Depends on:** Phase 1
**Enables:** Phase 3 (Phase 1+2 together = Conv 1 complete)
**Details:**
- Import `isValidProjectPath` from `../ipc/fs` (already used in `shell.ts`) — or inline the same `realpathSync + startsWith(home)` check
- In `terminal:spawn` handler: validate `resolvedCwd` with the same guard before spawning PTY
- Add `ptyOwners: Map<string, number>` tracking `tabId → webContentsId` (use `event.sender.id`)
- Populate `ptyOwners` on spawn; delete on kill/exit
- In `terminal:write` handler: if `ptyOwners.get(tabId) !== event.sender.id`, return without writing
**Verify:** `npm run build:main` compiles; manually launch Studio and verify terminal opens normally

### Phase 3: Delete dead MCP telemetry server + add log rotation   ← Conversation: 2
**File:** `src/pathly_telemetry/server.py` (DELETE), `src/pathly_telemetry/__main__.py` (DELETE), `src/pathly_telemetry/storage.py` (MODIFY)
**Done when:** `server.py` and `__main__.py` are deleted; `python -m pytest tests/ -q` passes; `storage.py` rotates at 5 MB.
**Delivers stories:** S3
**Depends on:** nothing (independent of Conv 1)
**Enables:** Phase 4
**Context:** Telemetry is already all-HTTP. Agents call `curl POST http://127.0.0.1:8765/record_activity` (see `_TELEMETRY_FOOTER` in `setup_command.py`). The HTTP endpoint lives in `http_server.py:369` and calls `storage.append_activity()` directly. The opt-out (`PATHLY_FF_TELEMETRY`) is already implemented in `feature_flags.py:38-40`. The MCP `server.py` and `__main__.py` are dead code — nothing registers or calls them.
**Details:**
- Delete `src/pathly_telemetry/server.py` — dead MCP implementation, never invoked
- Delete `src/pathly_telemetry/__main__.py` — its only purpose was to run the dead server
- `storage.py`: add 5 MB rotation before the `open()` call:
  ```python
  if ACTIVITY_FILE.exists() and ACTIVITY_FILE.stat().st_size > 5 * 1024 * 1024:
      ACTIVITY_FILE.rename(ACTIVITY_FILE.with_suffix('.jsonl.bak'))
  ```
- Update `src/pathly_telemetry/__init__.py` comment to say "HTTP telemetry endpoint + CLI reporter" (remove "MCP server")
**Verify:** `python -m pytest tests/ -q` passes; `python -c "import pathly_telemetry"` succeeds with no import errors

### Phase 4: Remove build/lib/ from git   ← Conversation: 2
**File:** `.gitignore`
**Done when:** `git status` shows no tracked files under `build/`; `.gitignore` covers the patterns.
**Delivers stories:** S5
**Depends on:** nothing
**Details:**
- Add to `.gitignore`:
  ```
  build/lib/
  build/bdist*/
  build/temp*/
  ```
- Run `git rm -r --cached build/lib/` (builder must run this manually — note in conversation prompt)
**Verify:** `git status` output does not list any `build/lib/` files as tracked

### Phase 5: Manifest ValueError + rollback logging   ← Conversation: 3
**File:** `src/install_cli/materialize.py`, `src/install_cli/setup_command.py`
**Done when:** A corrupt manifest hash halts the installer with a clear RuntimeError message; rollback failures are logged to stderr instead of silently swallowed.
**Delivers stories:** S6
**Depends on:** nothing
**Details:**
- `materialize.py`: find the `_load_manifest` function (or inline call site); surround the `_hash_files_dict` comparison block with `except ValueError as e: raise RuntimeError(f"Manifest integrity check failed for {dest}: {e} — use --force to bypass") from e`
- `setup_command.py`: in the rollback `except Exception: pass` block (lines ~277-279), replace `pass` with `import sys; print(f"[rollback error] {e}", file=sys.stderr)` — then re-raise or continue depending on the existing pattern
**Verify:** `python -m pytest tests/ -q` passes; specifically `test_rollback.py` and `test_manifests.py`

## Key Decisions
- Terminal: allowlist approach (not denylist) — adding new legitimate shells is a conscious opt-in
- Telemetry: env-var opt-out matches `.env.example` contract already documented
- Manifest: `RuntimeError` (not `SystemExit`) so callers can catch and handle programmatically
