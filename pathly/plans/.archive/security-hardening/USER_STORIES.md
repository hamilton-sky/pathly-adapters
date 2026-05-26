---
name: User Stories
---
# security-hardening — User Stories

## S1: Terminal command injection is blocked

**As a** user running Pathly Studio,
**I want** the terminal IPC to reject any renderer-supplied shell command that is not on an explicit allowlist,
**so that** a compromised renderer window cannot execute arbitrary binaries.

**Acceptance criteria:**
- `terminal:spawn` rejects `command` values not in `['bash','zsh','sh','pwsh','powershell.exe','cmd.exe']`; returns an error string instead of spawning
- A renderer-supplied `command` of `/tmp/malicious` causes an IPC error, not a PTY spawn
- A renderer-supplied `cwd` outside the home directory is rejected with a path-safety error

## S2: terminal:write ownership is enforced

**As a** user,
**I want** only the renderer window that spawned a PTY tab to write to it,
**so that** a popout terminal window cannot inject keystrokes into a tab it doesn't own.

**Acceptance criteria:**
- `terminal:write` with a `tabId` not owned by the calling window returns a silent no-op (does not throw, does not write)
- The PTY ownership map is populated on `terminal:spawn` and cleared on `terminal:kill`

## S3: Dead HTTP telemetry server is removed; log rotates at 5 MB

**As a** developer maintaining pathly-adapters,
**I want** the dead `server.py` and `__main__.py` HTTP files removed,
**so that** the codebase doesn't suggest an HTTP dependency that doesn't exist and the `http` package is never accidentally required.

**Context:** Telemetry is fully HTTP. Agents post to `http://127.0.0.1:8765/record_activity` (the FSM HTTP server). The `PATHLY_FF_TELEMETRY` opt-out is already implemented in `feature_flags.py`. `server.py` is dead code.

**Acceptance criteria:**
- `src/pathly_telemetry/server.py` does not exist
- `src/pathly_telemetry/__main__.py` does not exist
- `python -c "import pathly_telemetry"` succeeds without any `http` import
- `storage.py` rotates `activity.jsonl` to `activity.jsonl.bak` when the file exceeds 5 MB
- A bad input with `server.py` — `/tmp/malicious-server` — causes `pathly_telemetry server` invocation to fail (the entrypoint simply no longer exists)

## S5: `build/lib/` is absent from the git repository

**As a** developer,
**I want** build artifacts excluded from the repo,
**so that** stale `build/lib/` files do not shadow source files during `pip install -e .`.

**Acceptance criteria:**
- `.gitignore` contains entries for `build/lib/`, `build/bdist*/`, and `build/temp*/`
- `build/lib/` directory is removed from git tracking (`git rm -r --cached build/lib/`)
- `git status` shows no files under `build/` as tracked after the change

## S6: Manifest hash mismatch gives a clear error and halts install

**As a** developer running `pathly-setup --repair`,
**I want** a tampered or corrupt manifest to halt with an explicit message,
**so that** the installer does not silently continue with wrong state.

**Acceptance criteria:**
- `materialize.py` catches `ValueError` from `_load_manifest` and re-raises as `RuntimeError("Manifest integrity check failed: <path> — use --force to bypass")`
- The installer prints the RuntimeError message and exits non-zero
- A tampered `_manifest_hash` value in a real manifest file triggers this path
- Rollback swallowed exceptions in `setup_command.py` are logged to stderr, not silently eaten
