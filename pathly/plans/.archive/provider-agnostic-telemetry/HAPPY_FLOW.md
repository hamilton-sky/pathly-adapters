---
name: Happy Flow
---
# Provider-Agnostic Telemetry — Happy Flow

## Overview

A Pathly pipeline stage runs with a Google Gemini model via the `antigravity` adapter. The agent completes its work, the provider reports `cost_usd` directly, and Pathly stores it with `cost_source = "provider_reported"`. The Studio DBExplorer shows the exact cost with a "provider reported" badge — no estimates, no zeros, no stale hardcoded rates.

---

## Step-by-Step Happy Flow

### Step 1: Agent completes a stage

- **User does:** Starts a pipeline run in Studio using the `antigravity` adapter (Gemini 2.5 Pro).
- **System does:** Agent finishes, `log-agent-done` skill fires — passes `cost_usd` from Antigravity's output payload, `provider = "antigravity"`, `model = "gemini-2.5-pro"`.
- **State after:** `POST /record_activity` request arrives at the FSM HTTP server.

### Step 2: Cost resolver runs

- **System does:** `telemetry.py` sees `cost_usd > 0` from the caller → sets `cost_source = "provider_reported"`. Skips the registry lookup. No 80/20 split.
- **State after:** `cost_usd` and `cost_source = "provider_reported"` are in the response body.

### Step 3: DB write

- **System does:** `agent_invocations` row is inserted with `provider = "antigravity"`, `cost_source = "provider_reported"`, `cache_read_tokens = 0`, `cache_write_tokens = 0`.
- **State after:** DB has an accurate, provider-confirmed cost record.

### Step 4: Activity log write

- **System does:** `storage.py` appends to `~/.pathly/activity.jsonl` with `provider = "antigravity"` and `cost_source = "provider_reported"`.
- **State after:** CLI report can break down usage by provider.

### Step 5: Stop hook fires

- **System does:** `stop_telemetry.py` fires. It calls `POST /telemetry/billing_update` (DB-only — no JSONL patching). Includes `cost_source`.
- **State after:** DB is the single source of truth; no divergence.

### Step 6: Studio DBExplorer opens

- **User does:** Opens DBExplorer in Studio.
- **System does:** `costUtils.ts` calls `GET /telemetry/pricing` on mount — receives the live registry table. Renders cost from the `cost_usd` DB value, shows `cost_source` badge: **"provider reported"**.
- **State after:** User sees accurate cost, correctly attributed, with confidence indicator.

### Step 7: OTel export

- **System does:** If OTel is configured, span is exported with `gen_ai.vendor = "antigravity"` — Grafana/Honeycomb can group costs by provider without parsing model strings.
- **State after:** Observability consumers have a clean provider dimension.

---

## End State

- Every cost figure in the DB, activity log, Studio UI, and OTel is consistent.
- Zero `$0.00` entries that actually mean "cost unknown."
- `cost_source` distinguishes real costs from estimates everywhere.
- Frontend never falls out of sync with backend pricing.

## Success Indicators

- [ ] `GET /telemetry/pricing` returns entries for all 4 providers.
- [ ] `record_activity` response includes `cost_source` on every call.
- [ ] `agent_invocations.cost_source` is never NULL in a fresh run.
- [ ] `stop_telemetry.py` produces no EVENTS.jsonl writes.
- [ ] Studio cost column shows `—` when server is unreachable, not `$0.00`.
- [ ] `grep -rn "15\.00\|75\.00" studio/src` returns 0 results after Conv 4.
