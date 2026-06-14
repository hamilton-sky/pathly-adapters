# Pathly — Production Readiness Findings

_Assessment date: 2026-06-11 · Branch: `claude/pathly-production-readiness-5ljxsx` · Version: 2.14.1_

## Verdict

**Not GA — strong public beta / technical preview.** This matches the repo's own
official position in `docs/PRODUCTION_READINESS.md`, which says to describe Pathly
publicly as a *"public beta / technical preview"* until its release gates are met.

Two items are genuine GA blockers:

1. **Security** — the FSM HTTP server bind address is not validated; a single env
   var (`PATHLY_FSM_HTTP_HOST=0.0.0.0`) silently exposes the server + DB on all
   interfaces and defeats SSE-by-IP auth.
2. **CI** — the Studio (Electron/TypeScript) half of the product runs neither
   typecheck nor tests in CI.

Everything else is grind on the repo's existing checklist (code signing, clean-machine
smoke runs, Codex/Copilot verification), not architectural work.

---

## What's ready ✅

| Area | Status | Evidence |
|---|---|---|
| Packaging / release | ✅ | PyPI publish via trusted OIDC, `scripts/check_version_sync.py` enforced, `electron-builder.yml` (Win/Mac/Linux), GitHub Releases |
| Security baseline | ✅ | `X-Pathly-Secret` auth on all POST routes (`secrets.token_hex(32)`, `0o600`), no `shell=True`, injection-safe argv/PTY encoding, host allowlist, path-traversal guards, defaults to `127.0.0.1` |
| DB safety | ✅ | Per-thread SQLite connections (`threading.local()`), WAL mode, `busy_timeout=5000`, background `wal_checkpoint(TRUNCATE)` |
| Docs | ✅ | README, DEPLOYMENT (systemd/launchd), ARCHITECTURE, SECURITY, RISK_ASSESSMENT — current and candid |
| Logging | ✅ | Structured JSON formatter, Prometheus metrics, rate limiting, non-serializable-arg protection |
| Python tests | ✅ | 37 test files covering FSM, HTTP server, runner, install CLI, DB (isolated fixtures), stitching, telemetry; CI matrix 3.11/3.12/3.13 |

---

## Blockers & gaps ⚠️

### Security

| Severity | Finding | Location |
|---|---|---|
| 🔴 HIGH | Bind address not validated — `PATHLY_FSM_HTTP_HOST=0.0.0.0` exposes FSM + DB; SSE endpoints rely on loopback binding for auth, so this silently defeats it | `src/pathly_orchestrator/config.py:51` |
| 🟡 MEDIUM | Electron `sandbox: false` + `webSecurity: false`; confirm production builds don't ship `webSecurity: false` | `studio/src/main/index.ts:135-142` |
| 🟡 MEDIUM | No secret rotation; token never expires | `src/pathly_orchestrator/config.py` |
| 🟡 MEDIUM | Plaintext SQLite DB at rest (relies on OS user isolation) | `src/pathly_orchestrator/db/connection.py` |
| 🟢 LOW | `db/query` endpoint has no query cost limit (SELECT-only, not injection) | `db_api.py` |

> Note: subprocess/argv handling and Electron PTY encoding were reviewed and are
> **well-designed** — no `shell=True`, prompts passed as single argv elements,
> shell-escaped / base64-encoded across platforms. Not a concern.

### Testing & CI

| Severity | Finding | Location |
|---|---|---|
| 🔴 HIGH | Studio TypeScript tests not run in CI — Vitest configured but no `npm run test` workflow step | `.github/workflows/studio-release.yml` (build only) |
| 🔴 HIGH | Studio typecheck not enforced in CI — strict-mode renderer + main process never validated on PR | `studio/tsconfig.web.json`, `studio/tsconfig.node.json` |
| 🟡 MEDIUM | No coverage threshold enforced (XML uploaded, never gated) | `.github/workflows/test.yml` |
| 🟡 MEDIUM | No Windows e2e (only ubuntu + macOS) | `.github/workflows/e2e.yml` |
| 🟡 MEDIUM | Bandit skips B603/B607 (subprocess checks) — notable for a subprocess-spawning app; pyright configured but unused in CI; no ESLint for studio | `pyproject.toml`, `pyrightconfig.json` |
| 🟢 LOW | mypy `no_strict_optional` + excludes `pathly_data` (undocumented) | `mypy.ini` |

Only 2 frontend unit tests exist (`useFlowFile.test.ts`, `validateFlow.test.ts`); the
IPC layer, terminal spawning, PTY lifecycle, and Zustand stores are untested.

### Release gates still open (per `docs/PRODUCTION_READINESS.md`)

- Code signing / notarization infra exists but **secrets not filled in** → unsigned installers today.
- Clean-machine smoke runs (install + uninstall) for Claude and Codex not yet done.
- Codex / Copilot adapters are testing-stage, not verified on clean environments.
- `pytest -q` pass + CI green on 3.11/3.12/3.13 is a listed gate (pass result not verifiable in this container — pytest not installed).
- README "latest tag" reference is stale (says v2.11.11; actual is 2.14.1).

---

## Recommended next steps

1. **(blocker)** Validate the FSM bind address — reject non-loopback hosts at startup. ~30 min.
2. **(blocker)** Add `npm run typecheck` + `npm run test` for Studio to `test.yml` / `lint.yml`. ~30 min.
3. Fill in code-signing secrets and run clean-machine smoke tests for Claude + Codex.
4. Add a coverage threshold and Windows e2e; broaden Studio frontend tests.

_Sources: codebase review of `src/pathly_orchestrator/`, `src/install_cli/`, `studio/`,
`.github/workflows/`, and `docs/` plus the repo's own SECURITY.md / RISK_ASSESSMENT.md /
PRODUCTION_READINESS.md._
