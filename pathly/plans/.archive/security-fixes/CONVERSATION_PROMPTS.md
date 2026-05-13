# Conversation Prompts — security-fixes

## Conversation 1 — Code fixes

Delivers stories: 1, 2, 3a, 3b, 4

---

Apply four security fixes to the pathly-adapters codebase. All changes are surgical — do not refactor anything beyond what is described. After each file is changed, the codebase must remain importable and the CLI must remain runnable.

**Fix 1 — Host allowlist in `src/install_cli/setup_command.py` (Story 1)**

Add `ALLOWED_HOSTS = {"claude", "codex", "copilot"}` as a module-level constant after the existing imports.

In `main()`, immediately after the line `hosts = [args.host] if args.host else detect_hosts()`, insert a validation loop:

```python
for h in hosts:
    if h not in ALLOWED_HOSTS:
        print(f"Error: unsupported host {h!r}. Allowed: {', '.join(sorted(ALLOWED_HOSTS))}", file=sys.stderr)
        sys.exit(1)
```

This must execute before either the `args.uninstall` branch or the `args.dry_run` / `args.apply` branches.

**Fix 2 — Path-traversal guard in `src/install_cli/materialize.py` (Story 2)**

In the `uninstall()` function, inside the `for name in list(manifest["files"]):` loop, add a path-traversal check before `removed.append(name)`:

```python
target = dest / name
if not target.resolve().is_relative_to(dest.resolve()):
    raise ValueError(
        f"Path traversal detected in manifest: {name!r} escapes destination {dest}"
    )
```

Note: the loop currently computes `target = dest / name` only inside the `if not dry_run:` block. Move or duplicate that assignment so it is available for the check regardless of `dry_run`.

**Fix 3 — Content-Length safety in `src/pathly_telemetry/server.py` (Stories 3a and 3b)**

Add a module-level constant:

```python
_MAX_BODY = 1_048_576  # 1 MiB
```

Replace the current bare `int()` call in `_read_message()`:

```python
length = int(headers.get("content-length", 0))
```

With:

```python
try:
    length = int(headers.get("content-length", 0))
except ValueError:
    return None
if length > _MAX_BODY:
    return None
```

**Fix 4 — Subprocess timeout in `src/install_cli/setup_command.py` (Story 4)**

In `_uninstall_package()`, change `subprocess.run(cmd)` to `subprocess.run(cmd, timeout=60)`. No other call sites need changing.

After all changes: verify the files are valid Python (no syntax errors) by reading them back. Do not write any tests — tests are out of scope for this conversation.

---

## Conversation 2 — Docs/config fixes

Delivers stories: 5, 6

---

Apply two documentation and configuration fixes. Do not touch any Python files.

**Fix 5 — .env patterns in `.gitignore` (Story 5)**

Append the following block to `.gitignore` (at the end of the file, after the last existing line):

```
# Environment / secrets
.env
.env.*
*.env
```

**Fix 6 — New sections in `docs/SECURITY.md` (Story 6)**

Add two new sections to `docs/SECURITY.md`. Insert them after the existing `## Subprocess Calls in Installer` section and before the existing `## File Write Safety` section. Match the document's existing style exactly (Risk / Mitigation / Recommendation paragraphs, no bullet nesting beyond one level).

Section A — `## CLI Host Allowlist Bypass`:

> Risk: The `--host` CLI argument was passed directly to `adapter_meta_path(host)` and `adapter_install_yaml(host)` without validation. An attacker or misconfigured caller could supply an arbitrary string that is used as a file-system path component, potentially reading from unintended locations.
>
> Mitigation applied (security-fixes): `ALLOWED_HOSTS = {"claude", "codex", "copilot"}` is now defined at module level in `install_cli/setup_command.py`. `main()` validates every host in the resolved host list against `ALLOWED_HOSTS` before any file-system access. Invalid hosts cause an immediate exit with a descriptive error message.
>
> Production recommendation: Keep `ALLOWED_HOSTS` as the single source of truth. Any new supported host must be added there explicitly.

Section B — `## Telemetry Server DoS via Content-Length`:

> Risk: `_read_message()` in `pathly_telemetry/server.py` called `stdin.read(length)` with no upper bound on `length`. A caller advertising `Content-Length: 2GB` would cause the server to attempt a 2 GB allocation, hanging or OOM-killing the process. Additionally, `int(headers.get("content-length", 0))` raised `ValueError` on non-integer header values, crashing the server loop.
>
> Mitigation applied (security-fixes): Reads are capped at `_MAX_BODY = 1_048_576` (1 MiB). Messages advertising a larger body are dropped without reading. The `int()` parse is wrapped in `try/except ValueError`; malformed `Content-Length` headers cause the message to be silently dropped and the server loop continues.
>
> Production recommendation: Consider logging dropped oversized or malformed messages to a diagnostic sink so operators can detect probing attempts.

After both edits: read each changed file back to confirm correct placement and no accidental deletions.
