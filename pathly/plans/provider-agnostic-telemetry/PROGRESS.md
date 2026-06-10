---
name: Progress
---
# Provider-Agnostic Telemetry — Progress

## Status: CONV 3 DONE

## Story Status

| Story | Title | Delivered by | Status |
|---|---|---|---|
| S1.1 | Provider pricing registry | Conv 1 | DONE |
| S1.2 | GET /telemetry/pricing endpoint | Conv 1 | DONE |
| S1.3 | cost_source field on every event | Conv 1 | DONE |
| S2.1 | DB schema — provider + cost confidence columns | Conv 2 | DONE |
| S2.2 | AGENT_DONE / BILLING_UPDATE schema extension | Conv 2 | DONE |
| S2.3 | Activity log provider + cost_source fields | Conv 2 | DONE |
| S3.1 | Stop hook writes DB-only | Conv 3 | TODO |
| S3.2 | OTel spans carry gen_ai.vendor | Conv 3 | TODO |
| S3.3 | log-agent-done skill removes inline pricing table | Conv 3 | TODO |
| S4.1 | Studio costUtils fetches rates from server | Conv 4 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|---|---|---|---|---|
| 1 | Ph0–Ph3 | S1.1, S1.2, S1.3 | DONE | `curl -s http://127.0.0.1:8765/telemetry/pricing \| python -m json.tool` |
| 2 | Ph4–Ph7 | S2.1, S2.2, S2.3 | DONE | `python -m pytest tests/ -q` |
| 3 | Ph8–Ph10 | S3.1, S3.2, S3.3 | DONE | `grep -rn "EVENTS.jsonl" src/pathly_hooks/stop_telemetry.py` (→ 0) |
| 4 | Ph11 | S4.1 | TODO | `cd studio && npx tsc --noEmit` |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|---|---|---|---|---|---|
| 1 | Ph0 Pre-flight | `src/pathly_orchestrator/http_server/pricing.py` | Baseline test run + verify existing compute_cost_usd | Tests pass or failures documented | DONE |
| 1 | Ph1 PricingRegistry | `src/pathly_orchestrator/http_server/telemetry_registry.py` | CREATE: multi-provider registry class | compute("claude","claude-sonnet-4-6",800,200) returns (>0,"estimated") | DONE |
| 1 | Ph2 pricing.py delegate | `src/pathly_orchestrator/http_server/pricing.py` | Delegate to PricingRegistry | compute_cost_usd still works, uses registry | DONE |
| 1 | Ph3 telemetry.py | `src/pathly_orchestrator/http_server/blueprints/telemetry.py` | cost_source + GET endpoint + remove 80/20 | /telemetry/pricing returns 200; response has cost_source | DONE |
| 2 | Ph4 DB migration | `src/pathly_orchestrator/db/migrations.py` | Add cost_source, provider, cache token columns | Fresh DB has new columns | DONE |
| 2 | Ph5 event schema | `src/pathly_orchestrator/events.py` | Add optional fields to AGENT_DONE / BILLING_UPDATE | Schema has cost_source, cache tokens | DONE |
| 2 | Ph6 eventlog | `src/pathly_orchestrator/eventlog.py` | Pass new fields through read/write | Round-trip preserves cost_source | DONE |
| 2 | Ph7 storage | `src/pathly_telemetry/storage.py` | Add provider + cost_source to activity.jsonl | append_activity writes both fields | DONE |
| 3 | Ph8 stop hook | `src/pathly_hooks/stop_telemetry.py` | Remove JSONL patching, DB-only writes | grep EVENTS.jsonl → 0 matches | TODO |
| 3 | Ph9 OTel vendor | `src/pathly_orchestrator/otel_export.py` | Add gen_ai.vendor span attribute | grep gen_ai.vendor → match found | TODO |
| 3 | Ph10 skill doc | `src/pathly_data/core/skills/utilities/log-agent-done.md` | Remove inline pricing table | grep 15.00 → 0 matches | TODO |
| 4 | Ph11 costUtils.ts | `studio/src/renderer/src/components/DBExplorer/costUtils.ts` | Replace hardcoded rates with server fetch | tsc --noEmit → 0 TS errors | TODO |

## Prerequisites

- `pip install -e .` succeeds
- `cd studio && npx tsc --noEmit` passes
- `pathly-fsm-http` starts without error

## Blocked By

- Nothing
