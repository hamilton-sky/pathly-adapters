# Artifact Map — provider-agnostic-telemetry

**Date:** 2026-06-11

---

## Feedback Files Archived

| File | Conv | Retries | Outcome |
|---|---|---|---|
| REVIEW_FAILURES_conv2_attempt1.md | 1 | 2 | Fixed (DRY + shape + cost_source) |
| VERIFY_conv1_attempt1.md | 1 | — | Verification pass |
| TEST_FAILURES_conv1_attempt1.md | test | 1 | Fixed (S4.1 cost_source badge) |

---

## Source Files Changed

### Python — Backend

| File | Change |
|---|---|
| `src/pathly_orchestrator/http_server/telemetry_registry.py` | **CREATED**: PricingRegistry class, PRICING dict, _ADAPTER_PREFIXES, all_providers() |
| `src/pathly_orchestrator/http_server/pricing.py` | Delegates compute_cost_usd to PricingRegistry |
| `src/pathly_orchestrator/http_server/blueprints/telemetry.py` | GET /telemetry/pricing endpoint; cost_source in record_activity response; provider kwarg to append_activity |
| `src/pathly_orchestrator/db/migrations.py` | 6 additive ALTER TABLE columns: cost_source, provider, cache_read_tokens, cache_write_tokens on agent_invocations + run_history |
| `src/pathly_orchestrator/events.py` | Optional fields documented: cost_source, cache_read_tokens, cache_write_tokens on AGENT_DONE + BILLING_UPDATE; stale comment fixed |
| `src/pathly_orchestrator/eventlog.py` | Pass-through confirmed (no key filtering) |
| `src/pathly_telemetry/storage.py` | provider + cost_source params added to append_activity |
| `src/pathly_hooks/stop_telemetry.py` | EVENTS.jsonl patching removed; DB-only writes; cost_source included |
| `src/pathly_orchestrator/otel_export.py` | _infer_vendor() helper; gen_ai.vendor span attribute |

### Skill Docs

| File | Change |
|---|---|
| `src/pathly_data/core/skills/utilities/log-agent-done.md` | Inline pricing table removed; 80/20 split formula removed; server-side registry reference added |

### Studio — TypeScript Frontend

| File | Change |
|---|---|
| `studio/src/renderer/src/components/DBExplorer/costUtils.ts` | **REWRITTEN**: fetchPricingTable() + computeCost(model, tokensIn, tokensOut, table) replacing hardcoded RATES |
| `studio/src/renderer/src/components/DBExplorer/FeatureModal/FeatureModal.tsx` | fetchPricingTable on mount; pricingTable state + prop pass |
| `studio/src/renderer/src/components/DBExplorer/AgentsTab/AgentsTab.tsx` | pricingTable prop; costSource field in AgentRow; sourceBadge in COST td |
| `studio/src/renderer/src/components/DBExplorer/AgentsTab/AgentsTab.module.css` | .barCostNull, .tdCostNull, .sourceBadge with data-source variants |
| `studio/src/renderer/src/components/DBExplorer/InspectTab/InspectTab.tsx` | pricingTable prop; costSourceSummary in TypeStat; sourceBadge in cost display |
| `studio/src/renderer/src/components/DBExplorer/InspectTab/InspectTab.module.css` | .statCostNull, .sourceBadge with data-source variants |

---

## Plan Files

Located in `pathly/plans/provider-agnostic-telemetry/`:

| File | Purpose |
|---|---|
| USER_STORIES.md | 10 stories (S1.1–S4.1), 42 acceptance criteria |
| IMPLEMENTATION_PLAN.md | 11 phases, 4 conversations |
| ARCHITECTURE_PROPOSAL.md | Layer rules, decision record (5 decisions) |
| CONVERSATION_PROMPTS.md | Per-conversation builder prompts |
| PROGRESS.md | Story + conversation status tracking |
| EDGE_CASES.md | 5 edge case categories |
| REVIEW.md | FSM gate artifact — all 4 reviewer passes recorded |
| RETRO.md | Retrospective |
| VERIFY.md | Final verification result |
