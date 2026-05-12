# Implementation Plan — security-fixes

## Conversation 1 — Code fixes (Stories 1–4)

### Fix 1: Host allowlist in setup_command.py (Story 1)

File: `src/install_cli/setup_command.py`

Add at module level, after existing imports:

```python
ALLOWED_HOSTS = {"claude", "codex", "copilot"}
```

In `main()`, after `hosts = [args.host] if args.host else detect_hosts()`, insert a guard:

```python
for h in hosts:
    if h not in ALLOWED_HOSTS:
        print(f"Error: unsupported host {h!r}. Allowed: {', '.join(sorted(ALLOWED_HOSTS))}", file=sys.stderr)
        sys.exit(1)
```

This guard must execute before any call to `_run_host()` or `_run_host_uninstall()`, so it must come immediately after the host list is determined and before the uninstall/apply branches.

---

### Fix 2: Path-traversal guard in uninstall() (Story 2)

File: `src/install_cli/materialize.py`

In the `uninstall()` function, inside the `for name in list(manifest["files"]):` loop, add the same guard that `materialize()` already applies to writes:

```python
target = dest / name
if not target.resolve().is_relative_to(dest.resolve()):
    raise ValueError(
        f"Path traversal detected in manifest: {name!r} escapes destination {dest}"
    )
```

This check must appear before `removed.append(name)` and before any `target.unlink()` call. If any name fails the check, the `ValueError` propagates and no files are deleted.

---

### Fix 3a: Cap Content-Length in server.py (Story 3a)

File: `src/pathly_telemetry/server.py`

Add at module level:

```python
_MAX_BODY = 1_048_576  # 1 MiB
```

In `_read_message()`, after the length is parsed, add:

```python
if length > _MAX_BODY:
    return None
```

This must come before `stdin.read(length)`.

---

### Fix 3b: Safe Content-Length parse in server.py (Story 3b)

File: `src/pathly_telemetry/server.py`

Replace the bare `int()` call:

```python
# Before
length = int(headers.get("content-length", 0))
```

With a try/except:

```python
try:
    length = int(headers.get("content-length", 0))
except ValueError:
    return None
```

This combines naturally with Fix 3a — both changes apply to the same block in `_read_message()`.

---

### Fix 4: Subprocess timeout in setup_command.py (Story 4)

File: `src/install_cli/setup_command.py`

In `_uninstall_package()`, change:

```python
result = subprocess.run(cmd)
```

To:

```python
result = subprocess.run(cmd, timeout=60)
```

No other call sites exist in this file. `TimeoutExpired` is intentionally allowed to propagate so the caller sees the failure.

---

## Conversation 2 — Docs/config fixes (Stories 5–6)

### Fix 5: .env patterns in .gitignore (Story 5)

File: `.gitignore`

Append the following three lines (in a block, with a comment for clarity):

```
# Environment / secrets
.env
.env.*
*.env
```

These lines must be added as-is. Do not modify any existing lines.

---

### Fix 6: New sections in docs/SECURITY.md (Story 6)

File: `docs/SECURITY.md`

Add two new sections after the existing "## Subprocess Calls in Installer" section and before "## File Write Safety". The exact placement keeps CLI/installer topics grouped together.

**Section A — CLI Host Allowlist Bypass:**

```markdown
## CLI Host Allowlist Bypass

Risk:

- The `--host` CLI argument was passed directly to `adapter_meta_path(host)` and
  `adapter_install_yaml(host)` without validation. An attacker or misconfigured
  caller could supply an arbitrary string that is used as a file-system path
  component, potentially reading from unintended locations.

Mitigation applied (security-fixes):

- `ALLOWED_HOSTS = {"claude", "codex", "copilot"}` is now defined at module level
  in `install_cli/setup_command.py`.
- `main()` validates every host in the resolved host list against `ALLOWED_HOSTS`
  before any file-system access. Invalid hosts cause an immediate exit with a
  descriptive error message.

Production recommendation:

- Keep `ALLOWED_HOSTS` as the single source of truth. Any new supported host must
  be added there explicitly.
```

**Section B — Telemetry Server DoS via Content-Length:**

```markdown
## Telemetry Server DoS via Content-Length

Risk:

- `_read_message()` in `pathly_telemetry/server.py` called `stdin.read(length)`
  with no upper bound on `length`. A caller advertising `Content-Length: 2GB`
  would cause the server to attempt a 2 GB allocation, hanging or OOM-killing
  the process.
- `int(headers.get("content-length", 0))` raised `ValueError` on non-integer
  header values, crashing the server loop.

Mitigation applied (security-fixes):

- Reads are capped at `_MAX_BODY = 1_048_576` (1 MiB). Messages that advertise a
  larger body are dropped (`_read_message()` returns `None`) without reading the body.
- The `int()` parse is wrapped in `try/except ValueError`; malformed
  `Content-Length` headers cause the message to be silently dropped and the server
  loop continues.

Production recommendation:

- Consider logging dropped oversized or malformed messages to a diagnostic sink so
  operators can detect probing attempts.
```
