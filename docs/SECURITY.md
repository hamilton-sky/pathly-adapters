# Pathly Adapters Security and Reliability Review

This document records the security/reliability posture for pathly-adapters and
the remaining hardening work before a production-ready label.

Current status: public beta candidate (core install path stable at 2.21.1).

The adapter architecture has good safety properties: thin adapters, an explicit
stitch pipeline, dry-run support, a Pathly-owned-file manifest, and atomic
installs with rollback. The main gaps are hook injection risks, file-write
scope enforcement, and marketplace manifest integrity checks.

---

## FSM Server Authentication

The FSM HTTP server requires a shared secret on mutating endpoints from browser-origin or non-loopback callers.

**How it works:**

- On first start, `~/.pathly/server_secret.txt` is created with a random 64-char hex token.
- The token is loaded into `Settings.api_secret` at startup and injected into `middleware.configure()`.
- A `POST` from a **browser origin** (a request carrying an `Origin` header) or from a **non-loopback** client must carry `X-Pathly-Secret: <token>` (header, or `?token=` query arg) or receive a `401 Unauthorized`. A **loopback non-browser** caller (Pathly's own agents hitting `/comms/*` via `curl`, which send no `Origin` header) is allowed through **without** the secret — the token lives in a user-readable file and never guarded against same-user local processes, so the check targets browser CSRF and off-machine callers.
- `GET /events/*` endpoints are **exempt** — the browser `EventSource` API cannot send custom headers, so SSE streams are auth-by-IP-binding (127.0.0.1 only) rather than by header.
- Studio's Electron main process reads the same file via `studio/src/main/apiConfig.ts`, exposes it to the renderer over IPC (`shell:apiConfig`), and injects it into every `apiFetch()` call via `lib/config.ts`.
- PTY result callbacks (`POST /runner/terminal/result`) also include the header, injected in `studio/src/main/ipc/terminal.ts`.

**Trust model:** the secret's real job is blocking **browser CSRF** (browser requests always carry an `Origin` header) and **non-loopback** callers. It does not protect against another local process running as the same OS user — such a process can read `~/.pathly/server_secret.txt`, and as a loopback non-browser client it can reach the mutating endpoints without the secret at all. The server must only be bound to a loopback interface — this is now **enforced at startup** (see below).

**Bind-host enforcement:** `Settings.from_env()` (config.py) rejects any non-loopback value for `PATHLY_FSM_HTTP_HOST` with a hard `sys.exit(1)`. The only way to bind a non-loopback address is to also set `PATHLY_EXPOSE_HOST=true`, which prints a loud warning to stderr about the unauthenticated `/events/*` surface. This enforces the invariant that the SSE streams are never silently exposed on a network interface.

**Rotation:** delete `~/.pathly/server_secret.txt` and restart both the FSM server and Studio. Both will generate/read the new value on next start.

Remaining gap:

- The token is stored in plaintext. OS-level file permissions (`chmod 600`) are the only protection.
- No token expiry or rotation schedule is enforced automatically.

---

## Database Concurrency Safety

The FSM server uses SQLite in WAL mode at `~/.pathly/pathly.db`.

**Design:**

- Each Flask thread gets its own `sqlite3.Connection` via `threading.local()`; there is no shared connection pool. A single process-wide `threading.RLock` (`_global_write_lock`, reentrant) serializes all in-process writers (added in 2.16.2).
- `PRAGMA journal_mode=WAL` — readers never block writers; writers never block readers.
- `PRAGMA busy_timeout=5000` — a write that finds the WAL locked will retry for up to 5 seconds before raising `SQLITE_BUSY`.
- `PRAGMA foreign_keys=ON` — referential integrity enforced at the DB layer.
- A background daemon thread runs `PRAGMA wal_checkpoint(TRUNCATE)` every 5 minutes to keep the WAL file from growing unbounded.

**Risk:**

- Concurrent writes from multiple threads are serialized by SQLite's file-level WAL lock. Under very high write concurrency the 5-second busy timeout may expire; callers will see a `500` response.
- The DB file is user-owned and not encrypted. Anyone with read access to `~/.pathly/` can read pipeline state.

---

## Hook Injection Risks

Feedback-file classification and TTL injection run as an in-process file
watcher inside the FSM HTTP server (`_feedback_watcher` in
`pathly_orchestrator/http_server/feedback.py`), gated on `PATHLY_PROJECT_ROOT`
being set for the `pathly-fsm-http` process. This replaced the earlier design
of installing Python scripts into host tool hook-event systems (Claude/Codex/
Copilot) — that install-time hook deployment was removed from the installer.

Risk:

- The watcher reads file paths from the project's own `pathly/features/**`
  and `pathly/plans/**` (legacy) directories on a polling loop and rewrites
  matched files.
- A path-matching bug could rewrite a file outside the intended feedback
  directory.
- Watcher failures could silently leave feedback unclassified or without TTL
  metadata.

Mitigation today:

- The watcher is narrow: it only globs `*/feedback/*.md` under each feature's
  directory and only rewrites files it already found via that glob.
- Classification is a deterministic regex/keyword match
  (`_classify_content` in `feedback.py`) — no external API call, so there is
  no network egress or key-handling risk in this path.
- TTL injection only fires when the file lacks a `ttl_hours` frontmatter key.

Remaining gap:

- File path validation is string-based (glob match, not canonicalized path
  resolution). A production hardening pass should resolve paths and ensure
  writes stay under the active project's `pathly/features/` (or legacy
  `pathly/plans/`) directory.
- Watcher failures are intentionally non-blocking (caught and logged), but
  not strongly observable outside the server's own log stream.

Production recommendation:

- Add path canonicalization before every watcher write.
- Add unit tests for ignored paths, already-tagged files, and TTL frontmatter
  injection.
- Log watcher failures in a project-local diagnostic file or clearly visible
  server output.
- Document that the watcher requires `PATHLY_PROJECT_ROOT` and the pipeline
  must remain correct without it running.

Allowed hook behavior:

- Validate paths.
- Add TTL metadata to known feedback files.
- Classify `IMPL_QUESTIONS.md` into `[REQ]` / `[ARCH]` tags.
- Emit diagnostics for stale state or malformed payloads.
- Run fast FSM consistency checks.

Prohibited hook behavior:

- Long-running workflows.
- Lifecycle agent spawning.
- Source edits.
- Hidden state advancement.
- Unsupported host schemas presented as working.

Hook failures must be visible and recoverable. They must not corrupt workflow
state.

---

## Subprocess Calls in Installer

Files reviewed:

- `src/install_cli/detect.py`
- `src/install_cli/materialize.py`
- `src/install_cli/setup_command.py`

Risk:

- `detect.py` may invoke shell commands to locate host tool config directories.
- `materialize.py` writes files to user-level config directories.

Mitigation today:

- Subprocess calls in installer use argument lists rather than shell string
  interpolation.
- `--dry-run` mode never writes any files.

Production recommendation:

- Subprocess calls in installer should set timeouts.
- Installer subprocess failures should produce clear diagnostics, not silent
  fallback.

---

## CLI Host Allowlist Bypass

Risk:

- The `--host` CLI argument was passed directly to `adapter_meta_path(host)` and
  `adapter_install_yaml(host)` without validation. A caller could supply an arbitrary
  string used as a filesystem path component, potentially reading from unintended locations.

Mitigation applied (security-fixes):

- `ALLOWED_HOSTS = {"claude", "codex", "copilot", "antigravity"}` is defined at module level
  in `install_cli/orchestrate.py`.
- `main()` validates every host in the resolved host list against `ALLOWED_HOSTS` before
  any filesystem access. Invalid hosts cause an immediate exit with a descriptive error.

Production recommendation:

- Keep `ALLOWED_HOSTS` as the single source of truth. Any new supported host must be
  added there explicitly (and also to `_KNOWN_ADAPTERS` in `pathly_orchestrator/fsm/state.py`
  if it should be allowed in `adapter_map` flow YAML).

---

## Telemetry Server DoS via Content-Length — removed surface

The stdin telemetry server this section described (`pathly_telemetry/server.py`,
`_read_message()` / `_MAX_BODY`) **no longer exists.** Telemetry was superseded by the DB
event-projection architecture — `agent_invocations` is a projection of the `AGENT_DONE` event
stream — so there is no hand-rolled `Content-Length` reader to bound; the FSM's HTTP body
limits are handled by Flask/Werkzeug. The stdin `Content-Length` DoS surface documented here
is therefore gone. Kept as a historical note.

---

## File Write Safety

Risk:

- Installer writes to `~/.claude/`, `~/.codex/`, Copilot workspace paths, and `~/.gemini/antigravity-cli/`.
- `--force` could overwrite user-owned files not created by Pathly.
- A stale manifest could misidentify non-Pathly files as Pathly-owned.

Mitigation today:

- A Pathly-owned-file manifest tracks what `materialize.py` wrote.
- `--repair` only overwrites files listed in the manifest.
- `--force` is an explicit opt-in that overwrites everything.
- Install is atomic — if anything fails, already-written files are rolled back.
- `--uninstall` only removes files tracked in the manifest.

Remaining gap:

- Manifest integrity is not verified on load (could be edited externally).
- Rollback completeness needs an end-to-end test for partial-failure scenarios.

Production recommendation:

- Add tests for partial install failure and rollback correctness.
- Document explicitly which files are Pathly-owned vs. user-owned.
- `--uninstall` should confirm the manifest is intact before deleting files.

---

## Trust Boundaries (Adapter Side)

The adapter layer operates before any AI tool processes Pathly's files. Its
trust responsibilities:

- `core/` content is trusted workflow behavior. It is never modified by the
  installer.
- `adapters/<tool>/_meta/*.yaml` files are trusted adapter metadata, also
  never modified by the installer.
- Files written to `~/.claude/`, `~/.codex/`, etc. are Pathly-generated and
  must not contain user-provided free text that could inject instructions into
  a host tool context.
- The stitch pipeline combines fixed core content with fixed adapter metadata.
  It does not interpolate user input into the stitched output.

Production hardening still needed:

- Confirm stitch output is deterministic and contains no user-controlled
  content.
- Adapter-specific checks that prevent host-only instructions from leaking
  into core prompts during a future stitch implementation change.

---

## Marketplace Manifest Integrity

Risk:

- `src/pathly_data/adapters/claude/.claude-plugin/plugin.json`, `src/pathly_data/adapters/codex/.codex-plugin/plugin.json`,
  and `.agents/plugins/marketplace.json` are trusted by Claude Code and Codex.
- A malformed or tampered manifest could cause the host tool to load the wrong
  files or fail silently.

Mitigation today:

- Manifests are committed to version control.
- CI validates manifests parse as JSON.

Production recommendation:

- Add schema validation for manifests in CI, not just JSON parse checks.
- Pin manifest schema versions where host tools support versioning.
- Document what each manifest field controls and what is safe to change.

---

## Hook surface coverage

Feedback classification and TTL injection are no longer host-tool hooks — they
run inside the FSM HTTP server as a file watcher (`_feedback_watcher`), so
coverage is uniform across every host that runs `pathly-fsm-http` with
`PATHLY_PROJECT_ROOT` set, not deployed per adapter. The one per-host hook
still installed into a tool's own settings is Claude Code's `Stop` telemetry
hook:

| Host | Status | Deployed by installer | Notes |
|---|---|---|---|
| **Claude Code** | Supported | ✅ (`pathly-setup claude --apply`) | Writes a `Stop` hook entry (`python -m pathly_hooks.stop_telemetry`) into `~/.claude/settings.json`. Feedback classification/TTL is handled by the FSM server watcher, not a Claude hook. |
| **Codex** | N/A | — | No host-tool hooks are installed for Codex. Feedback classification/TTL works the same as any other host via the FSM server watcher. |
| **Copilot VS Code** | N/A | — | No host-tool hooks are installed for Copilot. Feedback classification/TTL works the same as any other host via the FSM server watcher. |
| **Antigravity** | N/A | — | No host-tool hooks are installed for Antigravity. Feedback classification/TTL works the same as any other host via the FSM server watcher. |

---

## Production Readiness Checklist

Required before production-ready:

- Hook unit tests for path validation and failure modes.
- Partial install / rollback test.
- Plugin manifests parse as valid JSON (CI-enforced).
- No install command writes files during `--dry-run`.
- `--uninstall` leaves no Pathly residue.
- Stitch pipeline output contains no user-controlled content.

Recommended before public beta:

- Schema validation for plugin manifests in CI.
- Hook path canonicalization.
- Manual smoke-test guide for Claude Code install, Codex install, and Copilot
  install.
