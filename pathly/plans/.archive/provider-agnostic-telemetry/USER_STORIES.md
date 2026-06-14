---
name: User Stories
---
# Provider-Agnostic Telemetry — User Stories

## Context

Pathly telemetry is currently Claude-centric: pricing is hardcoded for Claude models only, cost is silently set to `0.0` for all other providers, the frontend (`costUtils.ts`) maintains its own duplicate rate table (which has drifted from the Python backend — Opus 4 is 5.00/25.00 in TS but 15.00/75.00 in Python), and no field distinguishes provider-reported cost from estimated or unpriced events.

This feature introduces a provider-agnostic telemetry layer: a `PricingRegistry` that covers Claude, Codex (OpenAI), Google (Gemini), and Antigravity; a `cost_source` field to mark confidence; DB schema extensions for provider and cache tokens; OTel span enrichment; and Studio UI alignment with the backend pricing table.

---

## Stories

### Story S1.1: Provider pricing registry
**As a** Pathly operator, **I want** a single `PricingRegistry` keyed by provider + model family so that **all** cost computation in the system draws from one authoritative source.

**Acceptance Criteria:**
- [ ] `src/pathly_orchestrator/http_server/telemetry_registry.py` exists with a `PricingRegistry` class.
- [ ] Registry contains entries for at least: `claude` (opus-4, sonnet-4, haiku-4), `codex` (gpt-4o), `google` (gemini-2.5-pro, gemini-2.5-flash), `antigravity` (gemini-2.5-pro).
- [ ] `pricing.py` delegates `compute_cost_usd` to the registry instead of using its own dict.
- [ ] Looking up an unknown model returns `(0.0, "unpriced")` — not an exception.
- [ ] Looking up a known model returns `(cost_float, "estimated")`.

**Edge Cases:**
- Unknown provider + unknown model → `(0.0, "unpriced")`, no exception.
- Model string with version suffix (e.g. `claude-sonnet-4-6`) → matched by prefix to correct family.

**Delivered by:** Phase 1–2 → Conversation 1

---

### Story S1.2: GET /telemetry/pricing endpoint
**As** Studio (or any consumer), **I want** a `GET /telemetry/pricing` endpoint that returns the current pricing table as JSON so that the frontend never needs hardcoded rates.

**Acceptance Criteria:**
- [ ] `GET /telemetry/pricing` returns HTTP 200 with JSON body `{"providers": { "claude": {...}, "codex": {...}, ... }}`.
- [ ] Response includes input and output price per million tokens for every registered model family.
- [ ] The endpoint is served by `blueprints/telemetry.py`.

**Edge Cases:**
- Server not running → Studio falls back to `null` cost display (no crash).

**Delivered by:** Phase 3 → Conversation 1

---

### Story S1.3: cost_source field on every telemetry event
**As a** reporting user, **I want** every telemetry event to carry a `cost_source` field (`provider_reported` | `estimated` | `unpriced`) so I can tell whether a cost figure is accurate or a best guess.

**Acceptance Criteria:**
- [ ] `record_activity` endpoint returns `cost_source` in its response body.
- [ ] When caller provides `cost_usd > 0` explicitly, `cost_source = "provider_reported"`.
- [ ] When cost is computed from the pricing registry, `cost_source = "estimated"`.
- [ ] When model is unrecognised and no explicit cost provided, `cost_source = "unpriced"`.
- [ ] The 80/20 token split fallback is removed from `telemetry.py`.

**Edge Cases:**
- Caller passes `cost_usd = 0.0` explicitly → treated as `"unpriced"` (not `"provider_reported"`).

**Delivered by:** Phase 3 → Conversation 1

---

### Story S2.1: DB schema — provider + cost confidence columns
**As a** DB consumer, **I want** `agent_invocations` and `run_history` to carry `cost_source`, `provider`, `cache_read_tokens`, and `cache_write_tokens` columns so queries can filter by cost confidence and provider, and cache costs can be tracked accurately.

**Acceptance Criteria:**
- [ ] Migration adds `cost_source TEXT DEFAULT 'unpriced'` to `agent_invocations`.
- [ ] Migration adds `cache_read_tokens INTEGER DEFAULT 0` and `cache_write_tokens INTEGER DEFAULT 0` to `agent_invocations`.
- [ ] Migration adds `provider TEXT` to `agent_invocations`.
- [ ] Migration adds `cost_source TEXT DEFAULT 'unpriced'` and `provider TEXT` to `run_history`.
- [ ] Migration is additive (no existing rows deleted or altered).
- [ ] DB opens cleanly after migration on a fresh SQLite file.

**Edge Cases:**
- Existing DB with no `cost_source` column → migration applies via `ALTER TABLE ... ADD COLUMN` safely.

**Delivered by:** Phase 4 → Conversation 2

---

### Story S2.2: AGENT_DONE / BILLING_UPDATE event schema extension
**As a** supervisor reading EVENTS.jsonl or the DB, **I want** `AGENT_DONE` and `BILLING_UPDATE` events to optionally carry `cost_source`, `cache_read_tokens`, and `cache_write_tokens` fields so nothing is lost when the stop hook or log-agent-done writes them.

**Acceptance Criteria:**
- [ ] `src/pathly_orchestrator/events.py` documents `cost_source`, `cache_read_tokens`, `cache_write_tokens` as optional fields on `AGENT_DONE` and `BILLING_UPDATE`.
- [ ] `eventlog.py` passes these fields through when present (no silent drop).
- [ ] Existing events without these fields still parse correctly (backward-compatible).

**Edge Cases:**
- Event written without `cost_source` → reads back as `"unpriced"` default.

**Delivered by:** Phase 5–6 → Conversation 2

---

### Story S2.3: Activity log provider + cost_source fields
**As a** CLI reporter, **I want** each `~/.pathly/activity.jsonl` entry to carry explicit `provider` and `cost_source` fields so the report can break down usage and cost confidence by provider.

**Acceptance Criteria:**
- [ ] `storage.py` `append_activity` accepts and writes `provider` and `cost_source`.
- [ ] Both fields are present in every new entry written after this change.
- [ ] Existing entries without these fields still parse (backward-compatible read).

**Delivered by:** Phase 7 → Conversation 2

---

### Story S3.1: Stop hook writes DB-only (single source of truth)
**As a** data integrity owner, **I want** the stop hook to write cost updates exclusively to the DB via `BILLING_UPDATE`, removing the EVENTS.jsonl patching path, so there is exactly one source of truth for cost data.

**Acceptance Criteria:**
- [ ] `stop_telemetry.py` no longer patches EVENTS.jsonl directly.
- [ ] All cost writes go through `POST /telemetry/billing_update` or the `eventlog.append_event` DB path.
- [ ] The stop hook includes `cost_source` when writing.

**Edge Cases:**
- HTTP server unavailable → falls back to `eventlog.append_event` (DB), never to raw JSONL patch.

**Delivered by:** Phase 8 → Conversation 3

---

### Story S3.2: OTel spans carry gen_ai.vendor
**As an** observability consumer, **I want** each OTel span to carry a `gen_ai.vendor` attribute (`claude`, `codex`, `google`, `antigravity`) so I can aggregate costs by provider in Grafana or Honeycomb without parsing model name strings.

**Acceptance Criteria:**
- [ ] `otel_export.py` includes `gen_ai.vendor` in the span attribute list.
- [ ] Value is the canonical provider slug (matches `PricingRegistry` provider keys).
- [ ] Spans for unknown providers carry `gen_ai.vendor = "unknown"` rather than omitting the field.

**Delivered by:** Phase 9 → Conversation 3

---

### Story S3.3: log-agent-done skill no longer embeds pricing table
**As a** skill maintainer, **I want** the inline Claude pricing table removed from `log-agent-done.md` so pricing is never stale in skill docs and agents don't use doc-embedded rates instead of the registry.

**Acceptance Criteria:**
- [ ] `src/pathly_data/core/skills/utilities/log-agent-done.md` contains no hardcoded per-token price values.
- [ ] The skill doc references server-side cost resolution and instructs agents to pass `cost_usd` from provider output only.
- [ ] The 80/20 token split formula is removed from the skill doc.

**Delivered by:** Phase 10 → Conversation 3

---

### Story S4.1: Studio costUtils fetches rates from server
**As a** Studio user, **I want** the DBExplorer cost display to fetch rates from `GET /telemetry/pricing` instead of using hardcoded values so cost numbers in the UI match the backend computation and cannot drift.

**Acceptance Criteria:**
- [ ] `costUtils.ts` contains no hardcoded per-token rate values.
- [ ] On DBExplorer load, pricing data is fetched from `GET /telemetry/pricing` (via IPC or direct HTTP).
- [ ] If fetch fails or server is unreachable, cost cells display `null` / "—" rather than a silently wrong number.
- [ ] `cost_source` value is surfaced in the UI where cost is displayed (e.g. tooltip or badge: "estimated" / "provider reported" / "unpriced").

**Edge Cases:**
- Server cold start — DBExplorer opened before server ready → shows "—" cost, refreshes on reconnect.
- Model not in pricing table → displays "unpriced" badge, not `$0.00`.

**Delivered by:** Phase 11 → Conversation 4
