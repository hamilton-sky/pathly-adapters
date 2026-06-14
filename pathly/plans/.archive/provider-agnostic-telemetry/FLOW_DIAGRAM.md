---
name: Flow Diagram
---
# Provider-Agnostic Telemetry — Flow Diagram

## Happy Path: cost resolution during record_activity

```
Caller (log-agent-done / stop hook)
        │  POST /record_activity
        │  { agent, model, provider?, cost_usd?, tokens_in, tokens_out, ... }
        ▼
blueprints/telemetry.py
        │
        ├─ cost_usd > 0 from caller? ──────────────────► cost_source = "provider_reported"
        │                                                  skip registry lookup
        │
        └─ cost_usd missing or == 0?
                │
                ▼
        PricingRegistry.compute(provider, model, tokens_in, tokens_out)
                │
                ├─ model prefix matched? ──────────────► cost_source = "estimated"
                │                                         cost_usd = computed
                │
                └─ no match? ─────────────────────────► cost_source = "unpriced"
                                                          cost_usd = 0.0

        │  response: { ..., cost_usd, cost_source }
        ▼
DB: agent_invocations
        │  provider, cost_source, cache_read_tokens, cache_write_tokens
        │
        ├──► activity.jsonl  (provider, cost_source appended)
        └──► otel_spans      (gen_ai.vendor attribute)
```

## Stop Hook Flow (after this feature)

```
Claude Code / adapter session ends
        │
        ▼
stop_telemetry.py
        │
        ├─ HTTP server up? ──────────────────────────► POST /telemetry/billing_update
        │                                               { ..., cost_source }
        │
        └─ HTTP server down? ────────────────────────► eventlog.append_event(DB)
                                                        { ..., cost_source }
        ✗  EVENTS.jsonl patch removed entirely
```

## Studio Frontend Flow (after this feature)

```
DBExplorer mounts
        │
        ▼
fetchPricingTable()
        │
        ├─ server responds? ─────────────────────────► store PricingTable in state
        │
        └─ server unreachable? ──────────────────────► table = null
                                                        cost cells render "—"

computeCost(model, tokensIn, tokensOut, table)
        │
        ├─ table null? ──────────────────────────────► { cost: null, source: null }
        ├─ model found in table? ────────────────────► { cost: float, source: "estimated" }
        └─ model not found? ─────────────────────────► { cost: null, source: "unpriced" }

DBExplorer cost cell renders:
        ├─ cost_source = "provider_reported" → "$X.XX  [✓ reported]"
        ├─ cost_source = "estimated"         → "$X.XX  [~ estimated]"
        ├─ cost_source = "unpriced" / null   → "—  [unpriced]"
        └─ table null (server down)          → "—"
```

## Component Legend

| Symbol / Name | Meaning in this feature |
|---|---|
| `PricingRegistry` | Single source of truth for provider/model pricing rates |
| `telemetry.py` | Cost resolver + API gateway; enforces cost_source policy |
| `cost_source` | Confidence field that flows through every store |
| `fetchPricingTable()` | Frontend bridge to live backend rates |
| `gen_ai.vendor` | OTel provider dimension for external observability |
| `eventlog.append_event` | DB-backed fallback for all cost writes (replaces JSONL patch) |
