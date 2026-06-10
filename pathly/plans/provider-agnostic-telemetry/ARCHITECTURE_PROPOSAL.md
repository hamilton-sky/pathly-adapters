---
name: Architecture Proposal
---
# Provider-Agnostic Telemetry — Architecture Proposal

## Problem Statement

Pathly's cost tracking is built on Claude-centric assumptions scattered across five independent locations: `pricing.py`, `telemetry.py`, `stop_telemetry.py`, `costUtils.ts`, and `log-agent-done.md`. Any new provider requires edits in all five. The frontend rate table has drifted from the backend (Opus 4: 5.00/25.00 in TS vs 15.00/75.00 in Python). No mechanism signals whether a `cost_usd` value is accurate or a fallback zero.

## Proposed Solution

Consolidate cost logic into a single `PricingRegistry` class. Enrich the telemetry event schema with a `cost_source` field. Remove all secondary pricing tables. Make the frontend consume the backend's live table via an HTTP endpoint.

## Layer Breakdown

```
Caller (log-agent-done skill / stop hook)
     │  passes: cost_usd (provider-reported), provider, model, tokens_in/out
     ▼
telemetry.py blueprint   — GET /telemetry/pricing  ←  Studio (costUtils.ts)
     │  resolves: (cost_usd, cost_source) via PricingRegistry
     ▼
PricingRegistry (telemetry_registry.py)
     │  compute(provider, model, in, out) → (float, "provider_reported"|"estimated"|"unpriced")
     │  all_providers() → JSON for GET endpoint
     ▼
DB layer (migrations.py)
     │  agent_invocations: cost_source, provider, cache_read_tokens, cache_write_tokens
     │  run_history: cost_source, provider
     ▼
Event schema (events.py + eventlog.py)
     │  AGENT_DONE / BILLING_UPDATE: cost_source, cache_read_tokens, cache_write_tokens (optional)
     ▼
Storage + OTel
     │  activity.jsonl: provider, cost_source
     └  otel spans: gen_ai.vendor
```

## Key Design Decisions

### Decision 1: PricingRegistry as a class, not a module-level dict
- **Options:** (A) Module-level dict in pricing.py (current), (B) Singleton class in new file, (C) Config YAML loaded at startup.
- **Chosen:** B — singleton class in `telemetry_registry.py`.
- **Rationale:** Allows `all_providers()` method for the API endpoint without exposing internals. Testable in isolation. Avoids YAML parsing dependency for a static table. Config YAML (option C) is reserved for a follow-up if dynamic pricing overrides are added.

### Decision 2: Longest-prefix match for model families
- **Options:** (A) Exact model ID match, (B) Prefix match, (C) Regex per provider.
- **Chosen:** B — longest matching prefix.
- **Rationale:** Handles model version suffixes (`claude-sonnet-4-6` matches `claude-sonnet-4`) without enumerating every released version. Regex adds complexity with no advantage for the current model naming conventions.

### Decision 3: cost_source = "unpriced" when cost_usd == 0.0 even if explicitly passed
- **Options:** (A) Trust caller — mark as "provider_reported" if caller passed the field, (B) Only mark "provider_reported" if value > 0.
- **Chosen:** B.
- **Rationale:** Zero is ambiguous — it can mean "provider reported free" or "caller didn't know." Treating zero as "unpriced" is safer for reporting. The rare legitimate zero-cost case (free tier) is acceptable as "unpriced" since it has no impact on cost aggregation.

### Decision 4: Remove EVENTS.jsonl patching entirely, not conditionally
- **Options:** (A) Keep JSONL patching as a last-resort fallback, (B) Remove it completely.
- **Chosen:** B.
- **Rationale:** The fallback chain is HTTP → DB (via `eventlog.append_event`). JSONL patching is a dangerous write that modifies an existing line mid-file — if it races with a reader or crashes, the file is corrupt. DB writes via eventlog are transactional. "Two sources of truth" is the root problem; removing one path eliminates it.

### Decision 5: Frontend fetches pricing at mount, not at build time
- **Options:** (A) Bundle rates at build time via a codegen script, (B) Fetch on mount, (C) Fetch on each cost computation.
- **Chosen:** B — fetch once on DBExplorer mount, cache in component state.
- **Rationale:** Rates change with server updates, not code changes. Build-time bundling (A) would require a rebuild on every rate change. Per-computation fetch (C) is wasteful. A single mount fetch is a good balance — stale only if server is updated mid-session, which is acceptable.

## Key Components

| Component | File | Description |
|---|---|---|
| `PricingRegistry` | `telemetry_registry.py` | Central pricing table + cost resolver |
| `GET /telemetry/pricing` | `blueprints/telemetry.py` | Serves live pricing table to all consumers |
| `cost_source` field | `events.py`, `migrations.py`, `storage.py` | Confidence signal propagated to all stores |
| `gen_ai.vendor` | `otel_export.py` | OTel span provider dimension |
| `fetchPricingTable()` | `costUtils.ts` | Frontend pricing fetch + null-safe cost compute |

## Interface Design

```python
# telemetry_registry.py
class PricingRegistry:
    def compute(self, provider: str, model: str, tokens_in: int, tokens_out: int
               ) -> tuple[float, str]:  # (cost_usd, cost_source)
        ...

    def all_providers(self) -> dict:
        # {"claude": {"claude-opus-4": {"input": 15.0, "output": 75.0}, ...}, ...}
        ...
```

```typescript
// costUtils.ts
type CostResult = { cost: number | null; source: "provider_reported" | "estimated" | "unpriced" | null }
function fetchPricingTable(): Promise<PricingTable | null>
function computeCost(model: string, tokensIn: number, tokensOut: number, table: PricingTable | null): CostResult
```

## Risks

- **Registry rates drift from vendor pricing:** Mitigated by keeping rates in one file and documenting a manual override path as a follow-up.
- **EVENTS.jsonl removal breaks something that reads patched entries:** Mitigated by audit — grep for all readers of EVENTS.jsonl before Phase 8. The DB is the authoritative store; JSONL is append-only for the FSM state machine.
- **Frontend fetch latency on slow systems:** Mitigated — `fetchPricingTable` is fire-and-forget at mount; cost cells render `—` until it resolves.
- **cache_read_tokens / cache_write_tokens not factored into cost:** Documented limitation; stored for future use. Does not affect correctness of current cost_usd values.
