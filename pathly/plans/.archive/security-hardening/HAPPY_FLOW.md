---
name: Happy Flow
---
# security-hardening — Happy Flow

## Terminal spawn (after fix)
1. User opens a new terminal tab in Studio
2. Renderer calls `terminal:spawn(tabId, cwd, undefined)` — no custom command
3. Main process: `command` is undefined → default shell is `powershell.exe` (Win) or `bash` (Unix) — both are in ALLOWED_SHELLS → spawn proceeds
4. `resolvedCwd` resolves to a path inside the user's home dir → `isValidProjectPath` passes → PTY created
5. `ptyOwners.set(tabId, webContentsId)` recorded
6. User types commands → `terminal:write` fires → `ptyOwners.get(tabId) === event.sender.id` → write proceeds

## Install on fresh machine (after http fix)
1. `pip install pathly-adapters` → resolves `http>=1.0` as a dependency → installs alongside
2. `pathly-setup --apply` runs → telemetry HTTP server import succeeds
3. `PATHLY_FF_TELEMETRY=0 pathly-setup --apply` → telemetry storage.record() returns immediately → no activity.jsonl created

## Manifest integrity (after fix)
1. User runs `pathly-setup --repair` on an unmodified install
2. Manifest hash matches → install proceeds normally
3. Attacker tampers with `_manifest_hash` in `.pathly-manifest.json`
4. `_load_manifest` detects mismatch → raises `ValueError`
5. Caller catches it → re-raises `RuntimeError("Manifest integrity check failed for ... — use --force to bypass")`
6. Installer prints message and exits non-zero → user sees clear recovery instruction
