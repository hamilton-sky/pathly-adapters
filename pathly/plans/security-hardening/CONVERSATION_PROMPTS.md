---
name: Conversation Guide
---
# security-hardening — Conversation Guide

Split into 3 conversations. Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Terminal IPC hardening (Phases 1-2)

**Stories delivered:** S1, S2

**Prompt to paste:**
```
Read pathly/plans/security-hardening/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement security-hardening Conversation 1 (Phases 1-2) from pathly/plans/security-hardening/IMPLEMENTATION_PLAN.md.

**Before editing anything:** read studio/src/main/ipc/terminal.ts in full. Confirm the file exists and note the actual structure before making any changes.

**Codebase files this conversation touches:**
- `studio/src/main/ipc/terminal.ts` — add command allowlist, cwd validation, tabId ownership

**Phase 1 — Command allowlist:**
- Define `const ALLOWED_SHELLS = new Set(['bash','zsh','sh','pwsh','powershell.exe','cmd.exe'])` at the top of the file
- In the `terminal:spawn` handler: if `command` is provided and is NOT in `ALLOWED_SHELLS`, send a `terminal:error` event back to the renderer and return without spawning
- On Windows (process.platform === 'win32'): use only `powershell.exe` as the shell — do NOT pass the renderer-supplied `command` string as a `-Command` argument; that is the injection vector. Remove the `['-NoExit', '-Command', command]` args pattern entirely.
- On non-Windows: shell defaults to `bash`; only allow switching to entries in ALLOWED_SHELLS

**Phase 2 — cwd validation + tabId ownership:**
- Add cwd validation: import or inline the same `realpathSync + startsWith(homedir)` check used in shell.ts. If `cwd` is outside the home directory, send `terminal:error` and return.
- Add `const ptyOwners = new Map<string, number>()` (tabId → webContentsId)
- On successful PTY spawn: `ptyOwners.set(tabId, event.sender.id)`
- On `terminal:kill` / PTY exit: `ptyOwners.delete(tabId)`
- In `terminal:write` handler: if `ptyOwners.get(tabId) !== event.sender.id`, return silently (no write, no error)

Architectural rules:
- Only touch terminal.ts. Do not change fs.ts, shell.ts, or any renderer files.
- Keep the allowlist as a module-level constant, not inline in the handler.

Do NOT touch the renderer, FlowEditor, or Python files yet.
Verify: `npm run build:main` in studio/ compiles without TypeScript errors.
After done, update pathly/plans/security-hardening/PROGRESS.md phases 1-2 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** terminal.ts hardened; allowlist + cwd guard + tabId ownership all in place; main process builds clean.
**Files touched:** `studio/src/main/ipc/terminal.ts`

---

## Conversation 2: Delete dead MCP server + log rotation + git hygiene (Phases 3-4)

**Stories delivered:** S3, S5

**Prompt to paste:**
```
Read pathly/plans/security-hardening/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement security-hardening Conversation 2 (Phases 3-4) from pathly/plans/security-hardening/IMPLEMENTATION_PLAN.md.

**Architecture context (read this before touching anything):**
Telemetry is fully HTTP — agents POST to http://127.0.0.1:8765/record_activity (see setup_command.py line ~37 for the _TELEMETRY_FOOTER). The HTTP endpoint is in http_server.py:369 and calls storage.append_activity() directly. The PATHLY_FF_TELEMETRY opt-out is already implemented in feature_flags.py. The MCP server.py and __main__.py files are dead code — nothing registers or calls them.

**Before editing anything:** confirm by reading:
- `src/pathly_telemetry/server.py` — verify it's MCP-only, no other callers
- `src/pathly_telemetry/__main__.py` — verify it only calls server.run()
- `src/pathly_orchestrator/http_server.py` lines ~369-445 — the real telemetry endpoint
- `.gitignore` — current contents

**Phase 3 — Delete dead MCP telemetry files:**
- Delete `src/pathly_telemetry/server.py` (use the file deletion tool or git rm)
- Delete `src/pathly_telemetry/__main__.py`
- Update `src/pathly_telemetry/__init__.py`: change the comment to read "# pathly_telemetry — HTTP telemetry storage + CLI reporter"
- In `src/pathly_telemetry/storage.py` `append_activity()`: add 5 MB rotation before the `open()` call:
  ```python
  if ACTIVITY_FILE.exists() and ACTIVITY_FILE.stat().st_size > 5 * 1024 * 1024:
      ACTIVITY_FILE.rename(ACTIVITY_FILE.with_suffix('.jsonl.bak'))
  ```

**Phase 4 — Remove build/lib from git:**
- Add to `.gitignore` (after existing entries):
  ```
  build/lib/
  build/bdist*/
  build/temp*/
  ```
- Run: `git rm -r --cached build/lib/`
  Confirm the output shows files being removed from tracking.

Architectural rules:
- Only touch the files listed above. Do not change http_server.py, feature_flags.py, install_cli/, studio/, or adapter YAML files.
- The telemetry opt-out (PATHLY_FF_TELEMETRY) is already correctly implemented in http_server.py via feature_flags — do NOT add a second check in storage.py.

Do NOT touch terminal.ts, materialize.py, or any adapter files yet.
Verify: `python -m pytest tests/ -q` — all pre-existing tests still pass; `python -c "import pathly_telemetry"` succeeds.
After done, update pathly/plans/security-hardening/PROGRESS.md phases 3-4 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `server.py` and `__main__.py` deleted; `storage.py` has 5 MB rotation; `build/lib/` untracked.
**Files touched:** `src/pathly_telemetry/server.py` (deleted), `src/pathly_telemetry/__main__.py` (deleted), `src/pathly_telemetry/__init__.py`, `src/pathly_telemetry/storage.py`, `.gitignore`

---

## Conversation 3: Installer error handling (Phase 5)

**Stories delivered:** S6

**Prompt to paste:**
```
Read pathly/plans/security-hardening/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement security-hardening Conversation 3 (Phase 5) from pathly/plans/security-hardening/IMPLEMENTATION_PLAN.md.

**Before editing anything:** read src/install_cli/materialize.py and src/install_cli/setup_command.py in full. Note the exact location of: (1) the manifest hash comparison that raises ValueError, (2) the rollback except block that silently swallows exceptions.

**Codebase files this conversation touches:**
- `src/install_cli/materialize.py` — catch ValueError, re-raise as RuntimeError with clear message
- `src/install_cli/setup_command.py` — log rollback exceptions to stderr instead of swallowing

**Phase 5 — Manifest ValueError + rollback logging:**
- `materialize.py`: find where `_hash_files_dict(files)` is compared to `data['_manifest_hash']`. The ValueError that fires when they don't match should be caught and re-raised:
  ```python
  except ValueError as e:
      raise RuntimeError(
          f"Manifest integrity check failed for {dest}: {e} — use --force to bypass"
      ) from e
  ```
- `setup_command.py`: find the rollback `except Exception: pass` block (inside the outer except in `_run_host`). Replace `pass` with:
  ```python
  import sys
  print(f"[pathly rollback error] {e}", file=sys.stderr)
  ```
  Keep any existing re-raise or continue statement — only replace the silent `pass`.

Architectural rules:
- Only touch these two files. Do not change stitch.py, detect.py, or any adapter files.
- The RuntimeError message must include the destination path and the word "force" so users know how to recover.

Do NOT touch terminal.ts, telemetry files, or adapter YAML files.
Verify: `python -m pytest tests/ -q` — specifically confirm test_rollback.py and test_manifests.py pass.
After done, update pathly/plans/security-hardening/PROGRESS.md phase 5 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Corrupt manifest halts with RuntimeError; rollback failures logged to stderr.
**Files touched:** `src/install_cli/materialize.py`, `src/install_cli/setup_command.py`
