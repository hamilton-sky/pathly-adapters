---
name: Feature Index
---
# Provider-Agnostic Telemetry — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point for feature context |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria — the contract |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design — the what and how |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts — one section per conversation |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status — the checkpoint |

### Optional plan files (present if signals fired)

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Cross-layer design decisions — PricingRegistry, cost_source, OTel extension |
| `EDGE_CASES.md` | yes | Failure modes: unknown models, zero-cost, provider field missing |
| `HAPPY_FLOW.md` | yes | Golden-path narrative for cost resolution |
| `FLOW_DIAGRAM.md` | yes | ASCII cost-resolution and data-flow diagram |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `src/pathly_orchestrator/http_server/telemetry_registry.py` | Conv 1 | CREATE: PricingRegistry class + multi-provider table + GET /telemetry/pricing |
| `src/pathly_orchestrator/http_server/pricing.py` | Conv 1 | MODIFY: delegate compute_cost_usd to PricingRegistry |
| `src/pathly_orchestrator/http_server/blueprints/telemetry.py` | Conv 1 | MODIFY: add cost_source to output, accept provider param, remove 80/20 split |
| `src/pathly_orchestrator/db/migrations.py` | Conv 2 | MODIFY: add cost_source, provider, cache_read_tokens, cache_write_tokens columns |
| `src/pathly_orchestrator/events.py` | Conv 2 | MODIFY: add cost_source + cache token optional fields to AGENT_DONE / BILLING_UPDATE |
| `src/pathly_orchestrator/eventlog.py` | Conv 2 | MODIFY: pass new fields when reading/writing events |
| `src/pathly_telemetry/storage.py` | Conv 2 | MODIFY: add provider + cost_source to activity.jsonl entries |
| `src/pathly_hooks/stop_telemetry.py` | Conv 3 | MODIFY: remove EVENTS.jsonl patching, use DB-only BILLING_UPDATE |
| `src/pathly_orchestrator/otel_export.py` | Conv 3 | MODIFY: add gen_ai.vendor span attribute |
| `src/pathly_data/core/skills/utilities/log-agent-done.md` | Conv 3 | MODIFY: remove inline pricing table, document server-side resolution |
| `studio/src/renderer/src/components/DBExplorer/costUtils.ts` | Conv 4 | MODIFY: remove hardcoded rates, fetch from GET /telemetry/pricing |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Pricing Registry + cost resolver | S1.1, S1.2, S1.3 | TODO | `telemetry_registry.py`, `pricing.py`, `telemetry.py` |
| 2 | DB schema + storage layer | S2.1, S2.2, S2.3 | TODO | `migrations.py`, `events.py`, `eventlog.py`, `storage.py` |
| 3 | Hooks + OTel + skill doc | S3.1, S3.2, S3.3 | TODO | `stop_telemetry.py`, `otel_export.py`, `log-agent-done.md` |
| 4 | Studio frontend | S4.1 | TODO | `costUtils.ts` |

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/provider-agnostic-telemetry/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
