---
name: Edge Cases
---
# Provider-Agnostic Telemetry — Edge Cases

## Category 1: Unknown / unregistered models

### EC-1.1: Model not in registry, no provider-reported cost
- **Trigger:** A new Claude model suffix (e.g. `claude-sonnet-4-9`) is released before the registry is updated; or a fine-tuned model with a custom name is used.
- **Current behavior:** `compute_cost_usd` returns `0.0` silently; stored as zero — looks like free usage.
- **Expected behavior:** `cost_source = "unpriced"`; `cost_usd = 0.0`; Studio shows `—` badge "unpriced" instead of `$0.00`.
- **Handled in:** Phase 1 (registry miss returns `(0.0, "unpriced")`), Phase 3 (telemetry.py propagates it), Phase 11 (Studio renders badge).

### EC-1.2: Model string is empty or None
- **Trigger:** Adapter fails to inject model name into the stop hook payload.
- **Expected behavior:** `_ADAPTER_PREFIXES` inference returns `"unknown"` provider; registry returns `(0.0, "unpriced")`.
- **Handled in:** Phase 1 — `compute("unknown", "", ...)` must return `(0.0, "unpriced")` without raising.

### EC-1.3: Model version suffix causes no match
- **Trigger:** Model is `"claude-sonnet-4-6"` but registry key is `"claude-sonnet-4"`.
- **Expected behavior:** Longest-prefix match finds `"claude-sonnet-4"` → returns `"estimated"` cost.
- **Handled in:** Phase 1 — registry prefix match algorithm (longest key that is a prefix of the model string wins).

---

## Category 2: Provider-reported cost edge cases

### EC-2.1: Caller passes `cost_usd = 0.0` explicitly
- **Trigger:** Provider reports zero cost (free tier, error path, or test environment).
- **Expected behavior:** `cost_source = "unpriced"` — not `"provider_reported"`. Zero is indistinguishable from "not provided."
- **Handled in:** Phase 3 — condition is `cost_usd > 0.0` for `"provider_reported"`.

### EC-2.2: Caller passes `cost_usd` but omits `tokens_in` / `tokens_out`
- **Trigger:** Provider reports total cost but not token breakdown (some APIs).
- **Expected behavior:** `cost_usd` stored as-is with `cost_source = "provider_reported"`; `tokens_in = 0`, `tokens_out = 0` stored (not estimated via 80/20).
- **Handled in:** Phase 3 — 80/20 split is deleted entirely; partial token data stored as-is.

---

## Category 3: DB migration on existing data

### EC-3.1: Old DB without new columns
- **Trigger:** User upgrades pathly-adapters on a machine with an existing SQLite file.
- **Expected behavior:** Migration `ALTER TABLE ... ADD COLUMN` runs; existing rows get `DEFAULT` values; no data lost.
- **Handled in:** Phase 4 — use `PRAGMA table_info` guard to skip if column exists.

### EC-3.2: Migration run twice (re-run or crash-restart)
- **Trigger:** Server crashes mid-migration and restarts.
- **Expected behavior:** `IF NOT EXISTS` / `PRAGMA table_info` guard prevents duplicate-column error.
- **Handled in:** Phase 4.

---

## Category 4: Stop hook / dual-write removal

### EC-4.1: HTTP server unreachable when stop hook fires
- **Trigger:** FSM HTTP server not running when Claude Code session ends.
- **Current behavior:** Falls back to EVENTS.jsonl patching.
- **Expected behavior (after this feature):** Falls back to `eventlog.append_event` (DB write) — no JSONL patching.
- **Handled in:** Phase 8 — fallback chain is HTTP → DB, never JSONL.

### EC-4.2: Feature directory missing when stop hook fires
- **Trigger:** Run was ephemeral or plan folder was deleted.
- **Expected behavior:** Stop hook logs a warning and exits cleanly — no crash.
- **Handled in:** Phase 8 — existing guard logic for missing feature dir must remain.

---

## Category 5: Studio frontend

### EC-5.1: Studio opens before FSM server starts
- **Trigger:** User opens DBExplorer immediately after launching Studio.
- **Expected behavior:** `fetchPricingTable()` returns `null`; all cost cells show `—`; no JS error.
- **Handled in:** Phase 11 — `fetchPricingTable` catches all errors, returns null.

### EC-5.2: DB row has `cost_source = NULL` (pre-migration data)
- **Trigger:** Rows written before this feature was deployed.
- **Expected behavior:** Studio treats `null` as `"unpriced"` for display purposes.
- **Handled in:** Phase 11 — display logic defaults to "unpriced" badge when `cost_source` is null or absent.

---

## Known Limitations

- Pricing table is static code — requires a code change when vendors update rates. A manual override file (mentioned in plan Open Questions) is explicitly out of scope for this plan.
- Cache token pricing (cache_write = 3.75× input, cache_read = 0.10× input for Claude) is stored but not factored into cost computation in this plan — cost remains tokens_in × rate + tokens_out × rate. Cache cost refinement is a follow-up.
- `run_history.provider` field is TEXT (not a foreign key) — no referential integrity enforced in this plan.
