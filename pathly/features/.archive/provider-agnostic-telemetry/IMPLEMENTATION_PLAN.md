---
name: Implementation Plan
---
# Provider-Agnostic Telemetry — Implementation Plan

## Overview

Introduces a provider-agnostic telemetry layer across four conversations:
backend pricing registry and cost resolver (Conv 1), DB schema and storage extensions (Conv 2),
stop hook / OTel / skill-doc cleanup (Conv 3), and Studio frontend alignment (Conv 4).
No breaking changes to existing event consumers; all schema additions are additive.

## Layer Architecture

```
PricingRegistry (telemetry_registry.py)
     │  compute(provider, model, in, out) → (cost_usd, cost_source)
     ▼
telemetry.py blueprint       ←→  GET /telemetry/pricing endpoint
     │  record_activity writes cost_source to DB
     ▼
DB: agent_invocations + run_history   ←  cost_source, provider, cache tokens
     │
     ├── EVENTS.jsonl / eventlog.py   ←  AGENT_DONE carries cost_source
     ├── activity.jsonl / storage.py  ←  provider + cost_source per entry
     └── otel_export.py               ←  gen_ai.vendor span attribute

stop_telemetry.py  →  DB-only BILLING_UPDATE  (no JSONL patching)
log-agent-done.md  →  no inline pricing table

costUtils.ts  →  GET /telemetry/pricing  →  server-authoritative rates
```

---

## Phase 0: Pre-flight   ← Conversation: 1

**File:** `src/pathly_orchestrator/http_server/pricing.py`
**Done when:** Existing tests pass baseline (or known failures are documented); existing `compute_cost_usd` is verified to return correct values for Claude models before any edits.
**Delivers stories:** (none — baseline only)
**Depends on:** nothing
**Enables:** Phase 1
**Details:**
- Run `python -m pytest tests/ -q` and record any pre-existing failures.
- Call `compute_cost_usd("claude-sonnet-4-6", 10000, 2000, 0)` in a REPL and confirm result is non-zero.
- Document any failures in a comment at top of Phase 0 notes; do not fix pre-existing issues.
**Verify:** `python -m pytest tests/ -q 2>&1 | tail -5`

---

## Phase 1: Create PricingRegistry   ← Conversation: 1

**File:** `src/pathly_orchestrator/http_server/telemetry_registry.py` — CREATE
**Done when:** `PricingRegistry().compute("claude", "claude-sonnet-4-6", 800, 200)` returns a tuple `(cost_float > 0, "estimated")`.
**Delivers stories:** S1.1
**Depends on:** Phase 0
**Enables:** Phase 2, Phase 3
**Details:**
- Class `PricingRegistry` with `PRICING` dict keyed by provider slug → model-family-prefix → `{input: float, output: float}` ($/MTok).
- Initial entries:
  ```python
  "claude":       {"claude-opus-4": (15.00, 75.00), "claude-sonnet-4": (3.00, 15.00), "claude-haiku-4": (0.80, 4.00)}
  "codex":        {"gpt-4o": (2.50, 10.00), "o1": (15.00, 60.00), "o3": (10.00, 40.00)}
  "google":       {"gemini-2.5-pro": (1.25, 10.00), "gemini-2.5-flash": (0.075, 0.30)}
  "antigravity":  {"gemini-2.5-pro": (1.25, 10.00)}
  ```
- `compute(provider, model, tokens_in, tokens_out) -> (cost_usd: float, cost_source: str)`:
  - Match by prefix (longest matching key wins).
  - Returns `(computed_cost, "estimated")` on hit.
  - Returns `(0.0, "unpriced")` on miss — no exception.
- `all_providers() -> dict` — returns full pricing table for the API endpoint.
- No 80/20 split. If `tokens_in` and `tokens_out` are both 0, return `(0.0, "unpriced")`.
**Verify:** `python -c "from pathly_orchestrator.http_server.telemetry_registry import PricingRegistry; r=PricingRegistry(); print(r.compute('claude','claude-sonnet-4-6',800,200)); print(r.compute('unknown','x',100,50))"`

---

## Phase 2: Migrate pricing.py to delegate   ← Conversation: 1

**File:** `src/pathly_orchestrator/http_server/pricing.py` — MODIFY
**Done when:** `compute_cost_usd` in `pricing.py` delegates to `PricingRegistry` and all callers still work unchanged.
**Delivers stories:** S1.1 (partial)
**Depends on:** Phase 1
**Enables:** Phase 3
**Details:**
- Import `PricingRegistry` at module level.
- Rewrite `compute_cost_usd(model, tokens_in, tokens_out, total_tokens)` to:
  1. Infer provider from model prefix (keep existing `_ADAPTER_PREFIXES` logic here as a helper).
  2. Call `PricingRegistry().compute(provider, model, tokens_in, tokens_out)`.
  3. Return `cost_usd` float (keep existing signature for backward compat).
- Keep the existing `MODEL_PRICING` dict as a comment reference only (do not delete — aids review).
**Verify:** `python -c "from pathly_orchestrator.http_server.pricing import compute_cost_usd; print(compute_cost_usd('claude-sonnet-4-6', 800, 200, 1000))"`

---

## Phase 3: telemetry.py — cost_source + GET /telemetry/pricing   ← Conversation: 1

**File:** `src/pathly_orchestrator/http_server/blueprints/telemetry.py` — MODIFY
**Done when:** `POST /record_activity` response body includes `"cost_source"` key; `GET /telemetry/pricing` returns 200 with provider JSON; 80/20 split code is deleted.
**Delivers stories:** S1.2, S1.3
**Depends on:** Phase 2
**Enables:** Conv 2, Conv 4
**Details:**
- Accept optional `provider` field in `record_activity` request body (fall back to prefix inference if absent, log a warning).
- After cost computation, attach `cost_source` from `PricingRegistry.compute` return value.
  - Override to `"provider_reported"` when caller passes `cost_usd > 0.0` explicitly.
  - Keep as `"unpriced"` when `cost_usd == 0.0` even if caller passed it explicitly.
- **Remove** the `input_est = total_tokens * 0.80` / `output_est = total_tokens * 0.20` block entirely.
- Add `GET /telemetry/pricing` route — returns `{"providers": PricingRegistry().all_providers()}`.
- Include `cost_source` in the JSON response of `record_activity`.

**Event body schema (CANDIDATE-006):**
```
POST /record_activity
Required: agent, feature, summary, model, total_tokens, tool_uses, wall_seconds
Optional: cost_usd (float, provider-reported), tokens_in, tokens_out, provider
Response: { ..., cost_usd, cost_source }
```

**Verify:** `curl -s http://127.0.0.1:8765/telemetry/pricing | python -m json.tool | head -20`

---

## Phase 4: DB migration — new columns   ← Conversation: 2

**File:** `src/pathly_orchestrator/db/migrations.py` — MODIFY
**Done when:** A fresh DB opened after migration has `cost_source`, `provider`, `cache_read_tokens`, `cache_write_tokens` columns in `agent_invocations` and `run_history`.
**Delivers stories:** S2.1
**Depends on:** Phase 3
**Enables:** Phase 5, Phase 6
**Details:**
- Add a new migration step (use existing pattern — find the latest version number and increment).
- `agent_invocations`: add `cost_source TEXT DEFAULT 'unpriced'`, `provider TEXT`, `cache_read_tokens INTEGER DEFAULT 0`, `cache_write_tokens INTEGER DEFAULT 0`.
- `run_history`: add `cost_source TEXT DEFAULT 'unpriced'`, `provider TEXT`.
- Use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` or guard with `PRAGMA table_info` check to be safe on re-runs.
**Verify:** `python -c "from pathly_orchestrator.db.connection import get_db; db=get_db(':memory:'); c=db.cursor(); c.execute('PRAGMA table_info(agent_invocations)'); print([r[1] for r in c.fetchall()])"`

---

## Phase 5: AGENT_DONE / BILLING_UPDATE event schema   ← Conversation: 2

**File:** `src/pathly_orchestrator/events.py` — MODIFY
**Done when:** `AGENT_DONE` and `BILLING_UPDATE` TypedDicts/schemas include `cost_source`, `cache_read_tokens`, `cache_write_tokens` as optional fields with documented defaults.
**Delivers stories:** S2.2 (partial)
**Depends on:** Phase 4
**Enables:** Phase 6
**Details:**
- Read existing `AGENT_DONE` and `BILLING_UPDATE` definitions in `events.py`.
- Add optional fields `cost_source: str = "unpriced"`, `cache_read_tokens: int = 0`, `cache_write_tokens: int = 0`.
- Do NOT change required fields or field order — backward-compatible only.
- Add a comment block with the full schema for AGENT_DONE and BILLING_UPDATE (CANDIDATE-006 injection).

**Event schema reference block:**
```python
# AGENT_DONE required: agent, model, conversation, result, tokens_in, tokens_out,
#   total_tokens, cost_usd, tool_uses, wall_seconds, ts, schema_version
# AGENT_DONE optional: summary, trace_id, span_id,
#   cost_source (default "unpriced"), cache_read_tokens (default 0), cache_write_tokens (default 0)
#
# BILLING_UPDATE required: agent, conversation, cost_usd, tokens_in, tokens_out, total_tokens, wall_seconds, ts
# BILLING_UPDATE optional: tool_uses, cost_source, cache_read_tokens, cache_write_tokens
```
**Verify:** `python -c "from pathly_orchestrator.events import AGENT_DONE_FIELDS; print(AGENT_DONE_FIELDS)"` (or equivalent import for how events.py exposes the schema)

---

## Phase 6: eventlog.py — pass-through new fields   ← Conversation: 2

**File:** `src/pathly_orchestrator/eventlog.py` — MODIFY
**Done when:** `append_event` and any reader functions pass `cost_source`, `cache_read_tokens`, `cache_write_tokens` through without dropping them.
**Delivers stories:** S2.2
**Depends on:** Phase 5
**Enables:** Phase 8
**Details:**
- Read `eventlog.py` to understand its current read/write path.
- Ensure `append_event` does not strip unknown keys from event dicts (if it currently whitelists, add the new fields).
- If `eventlog.py` has a `read_last_event` or similar, confirm new optional fields survive a round-trip.
**Verify:** `python -c "from pathly_orchestrator.eventlog import append_event; import tempfile, pathlib; d=tempfile.mkdtemp(); append_event(d, {'type':'AGENT_DONE','cost_source':'estimated','cache_read_tokens':42}); print(open(pathlib.Path(d,'EVENTS.jsonl')).read())"`

---

## Phase 7: storage.py — provider + cost_source in activity.jsonl   ← Conversation: 2

**File:** `src/pathly_telemetry/storage.py` — MODIFY
**Done when:** `append_activity` writes `provider` and `cost_source` keys to activity.jsonl entries; existing entries without these fields still parse without error.
**Delivers stories:** S2.3
**Depends on:** Phase 6
**Enables:** Conv 3
**Details:**
- Add `provider: str = "unknown"` and `cost_source: str = "unpriced"` parameters to `append_activity`.
- Include both in the dict written to the JSONL line.
- Do not change field order of existing keys (append new keys at end for readability).
**Verify:** `python -c "from pathly_telemetry.storage import append_activity; import tempfile, os; d=tempfile.mkdtemp(); os.environ['PATHLY_ACTIVITY_FILE']=d+'/a.jsonl'; append_activity(agent='test',feature='x',summary='s',input_tokens=10,output_tokens=5,wall_seconds=1,tool_uses=0,cost_usd=0.01,total_tokens=15,model='claude-sonnet-4-6',provider='claude',cost_source='estimated'); print(open(d+'/a.jsonl').read())"`

---

## Phase 8: stop_telemetry.py — DB-only writes   ← Conversation: 3

**File:** `src/pathly_hooks/stop_telemetry.py` — MODIFY
**Done when:** The EVENTS.jsonl direct-patch code path is removed; all cost writes go through `POST /telemetry/billing_update` (primary) or `eventlog.append_event` (fallback); `cost_source` is included in the write.
**Delivers stories:** S3.1
**Depends on:** Phase 7
**Enables:** Phase 9
**Details:**
- Locate the EVENTS.jsonl patch block (reads file, modifies last AGENT_DONE line, rewrites).
- Delete it entirely — do not replace with a conditional.
- Ensure primary path: `POST http://127.0.0.1:8765/telemetry/billing_update` with `cost_source`.
- Ensure fallback path: `eventlog.append_event(feature_dir, billing_update_event)` with `cost_source`.
- Add `cost_source = "provider_reported"` when stop hook has explicit `cost_usd > 0`, else `"estimated"` or `"unpriced"` from registry.
**Verify:** Read the file after edits and confirm `EVENTS.jsonl` no longer appears in any write path; `grep -n "EVENTS.jsonl" src/pathly_hooks/stop_telemetry.py` should return 0 matches.

---

## Phase 9: otel_export.py — gen_ai.vendor attribute   ← Conversation: 3

**File:** `src/pathly_orchestrator/otel_export.py` — MODIFY
**Done when:** Every exported span includes `gen_ai.vendor` attribute; value is the canonical provider slug or `"unknown"`.
**Delivers stories:** S3.2
**Depends on:** Phase 8
**Enables:** Phase 10
**Details:**
- Read `otel_export.py` span attribute list.
- Add `gen_ai.vendor` derived from the event's `provider` field (from Phase 5/6 additions) or from model prefix inference using the same `_ADAPTER_PREFIXES` mapping as `telemetry.py`.
- Default to `"unknown"` when provider cannot be inferred.
**Verify:** `grep -n "gen_ai.vendor" src/pathly_orchestrator/otel_export.py`

---

## Phase 10: log-agent-done.md — remove inline pricing table   ← Conversation: 3

**File:** `src/pathly_data/core/skills/utilities/log-agent-done.md` — MODIFY
**Done when:** The file contains no per-token rate values (no `15.00`, `75.00`, `3.00`, `0.80` etc.); it instructs agents to pass `cost_usd` from provider output only.
**Delivers stories:** S3.3
**Depends on:** Phase 9
**Enables:** Conv 4
**Details:**
- Find the pricing table section in the skill doc (AC or implementation notes referencing Claude model rates).
- Remove it and replace with: "Pass `cost_usd` from the provider's output payload. Do not compute cost in the skill. The server resolves cost via the pricing registry."
- Remove any reference to 80/20 token split formulas.
- Keep all other sections (endpoint URL, field list, fallback strategy) intact.
**Verify:** `grep -n "15.00\|75.00\|3.00\|0.80\|0\.80\|80/20" src/pathly_data/core/skills/utilities/log-agent-done.md` → 0 matches

---

## Phase 11: costUtils.ts — server-fetched rates   ← Conversation: 4

**File:** `studio/src/renderer/src/components/DBExplorer/costUtils.ts` — MODIFY
**Done when:** The file contains no hardcoded per-token rates; it exports a `fetchPricingTable()` function and a `computeCost(model, tokensIn, tokensOut, pricingTable)` that uses the fetched table; cost cells show `"—"` when table is unavailable.
**Delivers stories:** S4.1
**Depends on:** Phase 10 (Conv 3 complete — GET /telemetry/pricing endpoint live)
**Enables:** (end of feature)
**Details:**
- Remove the hardcoded `PRICING` / rates object.
- Add `fetchPricingTable(): Promise<PricingTable | null>` — calls `GET http://127.0.0.1:8765/telemetry/pricing`, returns parsed JSON or `null` on error.
- Update `computeCost(model, tokensIn, tokensOut, table)` to accept the fetched table; return `{ cost: null, source: "unpriced" }` when table is null or model not found.
- Expose `cost_source` in the return object so DBExplorer components can render a badge.
- In DBExplorer parent component (identify by tracing imports from costUtils.ts): fetch pricing on mount, pass table down to cost display cells.
- If server unreachable: display `—` in cost column and `unpriced` badge; do not show `$0.00`.
**Verify:** `cd studio && npx tsc --noEmit 2>&1 | grep -c "error TS"` → 0 errors

---

## Prerequisites

- Python package installs cleanly: `pip install -e .`
- Studio compiles: `cd studio && npx tsc --noEmit`
- Existing `tests/` pass baseline (document any pre-existing failures in Phase 0)
- FSM HTTP server can be started: `pathly-fsm-http &`

## Key Decisions

- **PricingRegistry prefix match (longest wins):** Handles model suffixes like `-4-6` without enumerating every version.
- **cost_source = "provider_reported" only when cost_usd > 0 from caller:** Avoids marking zero-cost explicit passes as authoritative.
- **Remove EVENTS.jsonl patching, not just guard it:** Eliminates split-brain; DB is the only persistent cost store.
- **No 80/20 split anywhere:** If provider doesn't give token breakdown, record null not fabricated integers — bad data is worse than missing data.
- **Frontend fetches at mount, not build time:** Pricing can change without a Studio rebuild.
