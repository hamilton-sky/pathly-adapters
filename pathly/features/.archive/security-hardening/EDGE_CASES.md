---
name: Edge Cases
---
# security-hardening — Edge Cases

## Terminal IPC

| Case | Input | Expected behavior |
|---|---|---|
| Attacker command | `command = "/tmp/malicious"` | `terminal:error` returned; no PTY spawned |
| PowerShell injection | `command = "powershell.exe"` with extra args string | Allowed shell, but args stripped — only `['powershell.exe']` passed, no `-Command <user-string>` |
| Path traversal cwd | `cwd = "/etc"` | Rejected by `isValidProjectPath`; `terminal:error` returned |
| Unknown tabId write | `terminal:write(tabId='xyz', data='ls')` | Silent no-op — PTY not in `ptyOwners` |
| Popout writes to main PTY | Popout window sends `terminal:write` with a main-window tabId | `ptyOwners.get(tabId) !== event.sender.id` → silent no-op |
| Valid fish shell | `command = "fish"` | Not in ALLOWED_SHELLS → rejected (user can add fish if desired) |

## Telemetry

| Case | Expected behavior |
|---|---|
| `PATHLY_FF_TELEMETRY` unset | Default `'1'` — telemetry writes as before |
| `PATHLY_FF_TELEMETRY=0` | `record()` returns immediately; no file created or appended |
| Log file exactly 5 MB | Rotation does NOT trigger (threshold is strictly > 5 MB) |
| Log file 5 MB + 1 byte | Rotation triggers; `.bak` created; fresh file opened |
| `.bak` already exists | Overwritten silently |

## Manifest

| Case | Expected behavior |
|---|---|
| Corrupt JSON in manifest | `json.JSONDecodeError` caught by existing handler; treated as missing manifest |
| Correct hash | No ValueError; install proceeds |
| Tampered hash | `ValueError` → `RuntimeError` with clear message; exits non-zero |
| Rollback fails after partial install | Error logged to stderr; original exception re-raised so caller knows install failed |

## Dependencies

| Case | Expected behavior |
|---|---|
| `http` package not installed (old wheel) | `server.py` raises `ImportError` with message "run: pip install http" |
| `http` installed but wrong version | pip dependency resolver handles at install time |
