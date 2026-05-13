# User Stories — security-fixes

## Story 1 — Host allowlist guard on --host flag

**As** a developer running `pathly-setup`,
**I want** the `--host` CLI argument to be validated against a known allowlist before it is used,
**So that** an attacker or misconfigured script cannot supply an arbitrary string that gets used as a file-system path component.

**Acceptance criteria:**
- Running `pathly-setup some-unknown-host --dry-run` exits with a non-zero code and prints a clear error naming the invalid host.
- Running `pathly-setup claude --dry-run` succeeds as before.
- The allowlist `{"claude", "codex", "copilot"}` is defined as a named constant `ALLOWED_HOSTS` at module level in `setup_command.py`.
- No path under `adapter_meta_path()` or `adapter_install_yaml()` is accessed for a host that is not in `ALLOWED_HOSTS`.

**Delivered by:** Conversation 1

---

## Story 2 — Path-traversal guard in uninstall()

**As** a user running `pathly-setup --uninstall`,
**I want** the uninstaller to verify that every file name read from the manifest resolves to a path inside the destination directory,
**So that** a corrupted or maliciously crafted `.pathly-manifest.json` cannot delete files outside the intended directory.

**Acceptance criteria:**
- If any file name in the manifest resolves outside `dest`, `uninstall()` raises `ValueError` with a message identifying the offending path, and does not delete any files.
- File names that resolve inside `dest` are unlinked as before.
- The guard uses `(dest / name).resolve().is_relative_to(dest.resolve())`, matching the existing check in `materialize()`.

**Delivered by:** Conversation 1

---

## Story 3a — Telemetry server: cap Content-Length reads

**As** a system operator running the telemetry MCP server,
**I want** the server to reject messages whose `Content-Length` exceeds 1 MB,
**So that** a caller cannot exhaust memory by advertising an arbitrarily large body size.

**Acceptance criteria:**
- A message with `Content-Length: 2000000` (> 1 MB) causes `_read_message()` to return `None` without reading the body.
- A message with `Content-Length: 1000000` (= 1 MB) is processed normally.
- The cap constant is defined as `_MAX_BODY = 1_048_576` (1 MiB) at module level in `server.py`.

**Delivered by:** Conversation 1

---

## Story 3b — Telemetry server: safe Content-Length parse

**As** a system operator running the telemetry MCP server,
**I want** the server to handle a non-integer `Content-Length` header without crashing,
**So that** a malformed or adversarial request cannot bring down the server process.

**Acceptance criteria:**
- A message with `Content-Length: not-a-number` causes `_read_message()` to return `None` without raising an exception.
- The server process terminates cleanly on a malformed `Content-Length` — it does not crash with an unhandled exception.
- The `int()` parse is wrapped in a `try/except ValueError` that returns `None` on failure.

**Delivered by:** Conversation 1

---

## Story 4 — Subprocess timeout in _uninstall_package()

**As** a developer running the interactive uninstall flow,
**I want** the `subprocess.run()` call in `_uninstall_package()` to have an explicit timeout,
**So that** a hung pip or pipx process cannot block the terminal indefinitely.

**Acceptance criteria:**
- `subprocess.run(cmd)` in `_uninstall_package()` is called with `timeout=60`.
- If the subprocess exceeds 60 seconds, a `subprocess.TimeoutExpired` exception propagates (no silent swallow).
- No other call sites of `subprocess.run` are changed unless they also lack a timeout.

**Delivered by:** Conversation 1

---

## Story 5 — .gitignore covers .env files

**As** a contributor to the pathly-adapters repository,
**I want** `.env`, `.env.*`, and `*.env` patterns in `.gitignore`,
**So that** secrets or local environment files are never accidentally committed.

**Acceptance criteria:**
- `.gitignore` contains exactly the lines `.env`, `.env.*`, and `*.env`.
- `git check-ignore -v .env` reports the file as ignored.
- `git check-ignore -v .env.local` reports the file as ignored.
- `git check-ignore -v secrets.env` reports the file as ignored.

**Delivered by:** Conversation 2

---

## Story 6 — SECURITY.md documents --host bypass and telemetry DoS vectors

**As** a security auditor or contributor reviewing the project,
**I want** `docs/SECURITY.md` to explicitly document the `--host` allowlist bypass and the telemetry server DoS vectors,
**So that** the risk and its mitigation are visible to anyone reviewing the project's security posture.

**Acceptance criteria:**
- `docs/SECURITY.md` contains a section titled `## CLI Host Allowlist Bypass` that describes: the vector (unvalidated `--host` value flows into file-system path construction), and the mitigation applied (ALLOWED_HOSTS guard in `setup_command.py`).
- `docs/SECURITY.md` contains a section titled `## Telemetry Server DoS via Content-Length` that describes: both sub-vectors (unbounded read and non-integer parse crash), and the mitigations applied (1 MiB cap and try/except).
- Both new sections follow the existing document style (Risk / Mitigation / Recommendation paragraphs).

**Delivered by:** Conversation 2
