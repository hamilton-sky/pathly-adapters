# Provider-Agnostic Telemetry Plan

## Problem

Pathly telemetry is currently split across provider-specific assumptions:

- `log-agent-done` computes `cost_usd` only for `claude-*` models.
- Other providers can still emit token counts and duration, but cost often stays `0.0`.
- Stop hooks and orchestrator patches have different paths for filling telemetry.
- Different companies expose different payload shapes, so a single hardcoded parser is brittle.

This creates inconsistent reporting:

- tokens are often captured
- wall-clock time is often captured
- USD cost is sometimes missing or left as zero
- downstream reporting cannot reliably compare providers

## Goals

- Support Codex, Claude, Google/Gemini, Copilot, Antigravity, and future providers through one telemetry path.
- Preserve provider-specific pricing data without hardcoding vendor logic into every caller.
- Prefer provider-reported `cost_usd` when available.
- Keep unknown models safe by recording tokens/time even when cost cannot be computed.
- Make it obvious when cost was estimated versus provider-reported.

## Non-Goals

- Perfect billing parity with every vendor dashboard.
- Reverse-engineering hidden pricing when a provider does not expose it.
- Reworking all adapter plans at once.

## Issues To Fix

1. Cost is computed with Claude-only assumptions.
2. Telemetry producers use different field names for usage data.
3. No shared registry exists for provider/model pricing.
4. Unknown providers fall back to `cost_usd = 0.0`, which hides real usage cost.
5. Existing reports do not distinguish provider-reported cost from estimated cost.

## Solution

Introduce a provider-agnostic telemetry layer with provider-specific pricing adapters.

Core behavior:

- Normalize every telemetry event into a shared schema.
- Capture `provider`, `model`, `tokens_in`, `tokens_out`, `total_tokens`, `duration_ms`, `wall_seconds`, `tool_uses`, and `cost_usd`.
- If the provider returns `cost_usd`, store it directly.
- If cost is missing, compute it from a pricing registry keyed by provider and model family.
- If no pricing entry exists, keep cost as `0.0` and mark the event as unpriced.

## Architecture Proposal

### Layer 1: Event normalization

Create a small normalization module that accepts raw provider payloads and emits a canonical telemetry object:

- `provider`
- `model`
- `usage`
- `cost_usd`
- `cost_source`
- `tokens_in`
- `tokens_out`
- `total_tokens`
- `duration_ms`
- `wall_seconds`
- `tool_uses`

This layer should hide provider-specific field names such as:

- `input_tokens` vs `inputTokens`
- `output_tokens` vs `outputTokens`
- `total_cost_usd` vs `cost_usd`
- vendor-specific usage wrappers

### Layer 2: Pricing registry

Add a shared pricing registry that maps:

- provider name
- model family or exact model
- token price per input/output million tokens

Example structure:

```python
PRICING = {
    "claude": {
        "claude-sonnet-4": {"input": 3.0, "output": 15.0},
        "claude-haiku-4": {"input": 0.8, "output": 4.0},
    },
    "google": {
        "gemini-2.5-pro": {"input": X, "output": Y},
        "gemini-2.5-flash": {"input": X, "output": Y},
    },
    "codex": {
        "gpt-4o": {"input": X, "output": Y},
    },
    "antigravity": {
        "gemini-2.5-pro": {"input": X, "output": Y},
    },
}
```

The registry should live in one place and be used by:

- `log-agent-done`
- stop hooks
- any reporting code that needs estimates

### Layer 3: Cost resolution policy

Resolve cost in this order:

1. Use provider-reported `cost_usd` if present.
2. Else look up a pricing entry by provider + model.
3. Else try a provider-family fallback if exact model is unknown.
4. Else record `cost_usd = 0.0` and `cost_source = "unpriced"`.

### Layer 4: Reporting

Update downstream reports to display:

- actual cost
- estimated cost
- unpriced events

This prevents zero-cost records from being mistaken for free usage.

## Implementation Notes

- Keep provider adapters small and declarative.
- Do not embed vendor pricing logic in UI code.
- Do not make `claude-*` the default assumption for all telemetry.
- Keep the event schema backward-compatible so existing logs still parse.
- Add tests for provider-reported cost, estimated cost, and unpriced fallback.

## Open Questions

- Which providers expose authoritative cost in their API responses today?
- Which model names should be normalized across providers?
- Should costs be stored in raw event logs, derived at report time, or both?
- Do we want a manual override file for pricing changes?

## Recommended Next Step

Implement a shared telemetry utility, then migrate `log-agent-done`, the stop hook, and event reporting to use it.
