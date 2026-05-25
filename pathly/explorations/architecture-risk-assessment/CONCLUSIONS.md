# CONCLUSIONS — architecture-risk-assessment

_Based on TRACE.md findings from 3 independent scouts._

---

## Risk 1 — Hooks silent failure
**Verdict: REAL — but the framing is wrong. The actual bug is a spec/code mismatch.**

The original claim was "hooks are silent no-ops." They are not — they exit 1 and print to stderr.
The real problem is a **contract ambiguity** between spec and code:

- Original design (`IMPLEMENTATION_PLAN.md:36`): exit 0 when PATHLY_PROJECT_ROOT missing (silent no-op)
- Current code (`classify_feedback.py:34-37`, `inject_feedback_ttl.py:54-57`): exit 1 (failure)
- Tests (`test_hooks.py:193`): validate exit 1 — tests and code agree, but both contradict the spec
- README (`line 126`): ambiguous — "exits immediately without performing any action" — doesn't say exit code

**The installer never sets PATHLY_PROJECT_ROOT.** This is the core operational risk: if the user's
shell doesn't export it, every hook call fails (exit 1). No guidance exists on how to set it persistently.

**Severity: MODERATE**
Hooks failing with exit 1 is recoverable (the host tool continues), but feedback classification and
TTL injection silently never happen. Silent degradation with no user-visible warning.

**Minimal fix — two options (decision required):**
- **Option A (keep exit 1):** Update README to say exit 1 explicitly. Add an install step that emits
  a shell-profile snippet (`export PATHLY_PROJECT_ROOT=...`) and tells the user to source it.
- **Option B (revert to exit 0):** Change both hooks to exit 0 on missing env var, update the test,
  update README. Add a one-time diagnostic log to `~/.pathly/hook.log` so failures are observable.

---

## Risk 2 — Codex clean-machine verification gap
**Verdict: REAL — confidence gap confirmed. Not launch-blocking, but not safe to market as supported.**

The adapter is correctly coded for the happy path:
- CLI absent → graceful fallback to config.toml edit ✓
- config.toml absent → creates it from scratch ✓

Uncovered failure modes (`codex_plugin_config.py:40,47,96,148`):
- Permission denied on `~/.codex/` — raw OSError, no user-friendly message
- Partial write failure — rollback attempted but unconfirmed
- No CI pipeline exists at all (`.github/` absent)

The README Known Limitations section (`line 120`) correctly flags this. That's honest and good.
But it remains unresolved.

**Severity: LOW-to-MODERATE for existing users; MODERATE for public claim**
Happy path works. The gap is corner cases and public confidence, not a data-loss or security risk.

**Minimal fix:**
1. Wrap file-write calls in `codex_plugin_config.py` with try/except → raise descriptive `RuntimeError`
2. Add 2 unit tests: (a) `install_codex_plugin` with `shutil.which` returning None (real, not mocked),
   (b) `_enable_in_codex_config` with read-only parent dir (mock `Path.write_text` to raise PermissionError)
3. Remove "Known Limitations" flag from README only after a real clean-machine run is confirmed

---

## Risk 3 — pathly_orchestrator dual role
**Verdict: REAL — schema is unversioned and CLI is publicly registered. Migration story is absent.**

`pathly-events` and `pathly-state` are registered in `pyproject.toml:18-19` as public console_scripts.
The CLI in `eventlog.py:138` hard-codes field name `type`. If any field is renamed:
- CLI returns empty or wrong output — no error, no warning
- Existing EVENTS.jsonl files on disk produce wrong summaries
- No migration utility exists anywhere in the codebase

The FSM state schema (`state.py`) is also unversioned but is less risky (Claude writes it live each run;
old files are only read for the current pipeline run, then archived).

**Severity: MODERATE**
No field renames are planned imminently, so this is a latent risk. But it's a process trap: once
the first user has EVENTS.jsonl files on disk and we rename a field, we have a silent data loss bug
with no recovery path.

**Minimal fix:**
1. Add `"schema_version": 1` to `append_event()` in `eventlog.py` — written on every event
2. Add a check in `read_events()`: warn (not fail) if `schema_version` is missing or unknown
3. Add a one-paragraph note to `events.py` module header: "CLI consumers depend on field names;
   renames require a migration step and schema_version bump"
4. Document `pathly-events` and `pathly-state` as **internal tools** (not stable public API) in README

---

## Risk 4 — Version drift
**Verdict: REAL — two files are stale, no CI gate.**

| File | Status |
|---|---|
| `README.md:114` | ✓ Current (2.3.0) |
| `docs/SYSTEM_REVIEW.md:23` | ✓ Current (2.3.0) |
| `docs/PRODUCTION_READINESS.md:10` | ✓ Current (2.3.0) |
| `docs/SECURITY.md:6` | ✗ **STALE — says 1.0.0** |
| `CHANGELOG.md:2` | ✗ **STALE — last entry 2.1.0; missing 2.2.0 and 2.3.0** |

**Severity: LOW**
No functionality is affected. But `SECURITY.md` referencing an obsolete version erodes trust,
and the CHANGELOG gap means release history is lost.

**Minimal fix:**
1. Update `docs/SECURITY.md:6` from `1.0.0` to `2.3.0`
2. Backfill CHANGELOG with 2.2.0 and 2.3.0 entries (even if brief)
3. Add a pre-release script `scripts/check-version-sync.sh`:
   ```bash
   VERSION=$(grep '^version' pyproject.toml | cut -d'"' -f2)
   grep -rL "$VERSION" docs/ README.md CHANGELOG.md && echo "VERSION MISMATCH — update docs before release"
   ```
   Wire into release process (or a pre-commit hook).

---

## Risk 5 — http_config.py opaque
**Verdict: PARTIALLY REAL — module purpose is clear from its own docstring, not from external docs.**

`http_config.py:1-6` has a clear module-level docstring explaining what it does.
`docs/PATHLY_ARCHITECTURE.md:125` lists it as "HTTP configuration support" — terse but not zero.
README does not mention it at all.

The telemetry server (`server.py:17-53`) exposes exactly one tool (`record_activity`) — well-scoped.

**Severity: LOW**
Anyone who opens the file immediately understands it. The gap is cross-reference: a new contributor
reading the architecture doc sees "HTTP configuration support" and doesn't know what HTTP server,
what config files, or what tools it registers.

**Minimal fix:**
1. Update `docs/PATHLY_ARCHITECTURE.md:125` module table entry to read:
   "Registers the `pathly-telemetry` HTTP server (`record_activity` tool) in `~/.claude/settings.json`
   and `~/.codex/config.toml`. No-op for Copilot."
2. Add a 2-sentence "Telemetry HTTP Server" subsection to README under the Install section.

---

## Priority Order

| # | Risk | Severity | Effort | Act now? |
|---|---|---|---|---|
| 1 | Hooks spec/code mismatch + no install guidance for PATHLY_PROJECT_ROOT | MODERATE | Small | ✅ Yes |
| 3 | Event schema unversioned, public CLI with no migration story | MODERATE | Small | ✅ Yes |
| 4 | SECURITY.md stale (1.0.0), CHANGELOG gap (2.2.0/2.3.0 missing) | LOW | Trivial | ✅ Yes (10 min fix) |
| 2 | Codex error handling + no CI | MODERATE | Medium | ⏳ Before public Codex claim |
| 5 | http_config.py not documented externally | LOW | Trivial | ⏳ Next doc pass |
