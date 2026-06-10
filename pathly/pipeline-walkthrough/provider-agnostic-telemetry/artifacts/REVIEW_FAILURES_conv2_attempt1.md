## Review Report — Conv 2 (provider-agnostic-telemetry)

### Violations

- `src/pathly_orchestrator/http_server/blueprints/telemetry.py:162-174` — S2.3 incomplete — `append_activity()` call omits `provider=_provider` and `cost_source=cost_source`; both values are resolved at lines 142 and 146-153 respectively but never forwarded, so every `activity.jsonl` entry is written with defaults (`provider="unknown"`, `cost_source="unpriced"`) regardless of what the caller supplied or the registry computed.

### Warnings (non-blocking)

None.

### Pass

- `src/pathly_orchestrator/db/migrations.py` — `_add_additive_migrations`: all five new columns (`agent_invocations.cost_source`, `agent_invocations.provider`, `agent_invocations.cache_read_tokens`, `agent_invocations.cache_write_tokens`, `run_history.cost_source`, `run_history.provider`) are present with correct types and defaults, wrapped in `try/except sqlite3.OperationalError: pass` per codebase convention. S2.1 satisfied.
- `src/pathly_telemetry/storage.py` — `append_activity` signature accepts `provider` and `cost_source` with correct defaults (`"unknown"` / `"unpriced"`), and writes both unconditionally to every entry. S2.3 storage-side satisfied.
- `src/pathly_orchestrator/events.py` — `AGENT_DONE` schema comment documents `cost_source`, `cache_read_tokens`, `cache_write_tokens` as optional fields with correct defaults. `BILLING_UPDATE` comment similarly updated. S2.2 satisfied. Backward compatibility preserved (all three fields are optional).
- `src/pathly_orchestrator/runner/events.py` — `_patch_last_agent_done` writes `BILLING_UPDATE` via `eventlog.append_event` only (no direct JSONL mutation). Consistent with Design Decision 4.
- Layer rules — no new upward imports introduced by Conv 2 changes.
