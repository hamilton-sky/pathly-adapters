---
name: Implementation Plan
---
# Multi-Adapter Runner — Implementation Plan

## Overview

Make `pathly-run` multi-adapter, controllable, and observable. Introduce `core/adapters.yaml` (the one adapter→command contract), a threaded supervisor with `RunnerState` (pause/abort/caps, FSM-fed decisions, session continuity), and a `/runner/*` control API + `/events/runner` SSE stream. The FSM stays passive; the supervisor calls it.

## Layer Architecture

```
core/adapters.yaml ──(runtime read)──► adapters.py: resolve_command()
        │                                      │ {argv, terminal_kind, supports_resume}
        │ (build-time gen)                     ▼
        ▼                              runner.invoke_agent (headless executor)
studio/.../adapters.gen.ts                     │
   (consumed by hq-panel)                       ▼
                                       supervisor.py: RunnerState + loop thread
                                               │ calls FSM (next_action/complete_stage)
                                               ▼
                                       http_server: /runner/* + /events/runner SSE
                                               │
                                               ▼  (consumed by hq-panel)
```

**Dependency direction:** HQ → control API → supervisor → FSM (one-way). FSM imports nothing from the runner/adapter layer. `adapters.yaml` is the only shared contract (TS side is generated, never authored).

---

## Phases

### Phase 0: Pre-flight   ← Conversation: 1
**File:** none (verification only)
**Done when:** baseline green and dependency confirmed.
**Details:**
- `python -m pytest tests/ -q` passes (record pre-existing failures as baseline).
- Confirm `multi-adapter-routing` Conv 1 is present: `/next_action` returns `preferred_adapter` (grep `fsm_ops.py`). If absent, STOP — this feature depends on it.
- Confirm `invoke_agent` in `runner.py` currently builds `["claude","-p",...]`, and note the JSON cost/`session_id` parsing already there.
**Verify:** `python -m pytest tests/ -q`

### Phase 1: adapters.yaml — the command contract   ← Conversation: 1
**File:** `src/pathly_data/core/adapters.yaml` (NEW)
**Done when:** the file defines claude/codex/copilot with `terminal_kind`, `headless`, `autonomy_flag`, `resume`, `parse` per the FEATURE_INDEX canonical shape.
**Delivers stories:** S1
**Depends on:** Phase 0
**Details:** copilot has `headless: null`/`resume: null` (no headless mode). Placeholders `{prompt}`, `{model}`, `{session_id}` are substituted by `resolve_command`.
**Verify:** `python -c "import yaml,importlib.resources as r; yaml.safe_load(r.files('pathly_data').joinpath('core/adapters.yaml').read_text())"`

### Phase 2: resolve_command()   ← Conversation: 1
**File:** `src/pathly_orchestrator/adapters.py` (NEW)
**Done when:** `resolve_command(adapter, prompt, model, session=None)` returns `{argv, terminal_kind, supports_resume}`; unknown adapter raises a clear error; `autonomy` flag inclusion is parameterized.
**Delivers stories:** S1
**Depends on:** Phase 1
**Details:** read `adapters.yaml` via `importlib.resources.files("pathly_data")` (same pattern as `runner._storage_path`). Substitute placeholders. `supports_resume = resume is not None`. When `session` given and resume supported, splice the resume flag/arg into argv.
**Verify:** `python -m pytest tests/ -q`

### Phase 3: TS generator + staleness test   ← Conversation: 1
**File:** `scripts/gen_adapters_ts.py` (NEW) → emits `studio/src/renderer/src/lib/adapters.gen.ts` (NEW); test in `tests/`
**Done when:** running the generator writes the TS mirror, and a test fails if the committed mirror is stale.
**Delivers stories:** S1
**Depends on:** Phase 1
**Details:** the generator reads `adapters.yaml` and writes a typed TS object (`terminal_kind`, `supports_resume`, color-chip hint). The test regenerates in memory and asserts equality with the committed file. Verify the `studio/src/renderer/src/lib/` location exists before writing there.
**Verify:** `python scripts/gen_adapters_ts.py && python -m pytest tests/ -q`

### Phase 4: invoke_agent uses resolve_command   ← Conversation: 1
**File:** `src/pathly_orchestrator/runner.py` (MODIFY)
**Done when:** `invoke_agent` builds its command via `resolve_command`, and the claude path is behavior-identical to today.
**Delivers stories:** S1
**Depends on:** Phase 2
**Details:** replace the hardcoded `cmd = ["claude","-p",...]` with `resolve_command(...)["argv"]`. Keep the existing timeout/kill, JSON parse, and `_patch_last_agent_done` telemetry. Add an `adapter` param (default `"claude"` so the existing CLI path is unchanged).
**Verify:** `python -m pytest tests/ -q` (existing runner tests still pass)

### Phase 5: RunnerState + registry + mirror   ← Conversation: 2
**File:** `src/pathly_orchestrator/supervisor.py` (NEW)
**Done when:** a `RunnerState` dataclass + in-memory registry (keyed by topic, under a `threading.Lock`) exist, with a `RUNNER_STATE.json` write-through mirror; startup rewrites a stale `running` mirror to `error`.
**Delivers stories:** S2
**Depends on:** Phase 4
**Details:** fields per USER_STORIES S2. In-memory is authority; JSON is durable shadow in `pathly/plans/<topic>/`.
**Verify:** `python -m pytest tests/ -q`

### Phase 6: Threaded run loop + boundary caps + abort   ← Conversation: 2
**File:** `src/pathly_orchestrator/supervisor.py` (MODIFY)
**Done when:** a per-topic daemon thread runs next_action→resolve_command→invoke_agent→advance; pause and cost/iteration caps are checked at the boundary; abort hard-kills within ~2s.
**Delivers stories:** S2
**Depends on:** Phase 5
**Details:** reuse `invoke_agent` and the feedback/`resolve_stage` logic from runner.py. Pause/caps = graceful at boundary; abort = immediate `proc.kill()`. Caps exceeded → `status=error, kind=cap_exceeded`, no further invocation. Accumulate `cost_usd_so_far` from parsed cost.
**Verify:** `python -m pytest tests/ -q` (supervisor driven by a fake FSM client)

### Phase 7: FSM-fed decisions + session continuity   ← Conversation: 2
**File:** `src/pathly_orchestrator/supervisor.py` (MODIFY); `src/pathly_orchestrator/runner.py` (MODIFY)
**Done when:** decision points set `awaiting_decision`+`pending_menu` and resume via a supplied decision → `complete_stage`; session continue-vs-new is decided by comparing next adapter to `open_session`.
**Delivers stories:** S2
**Depends on:** Phase 6
**Details:** replace `handle_decide`'s blocking `input()` with state-driven waiting (the supervisor exposes a way to supply the decision). Capture `session_id` from claude JSON into `open_session`. Non-resumable adapter → fresh + `degraded`.
**Verify:** `python -m pytest tests/ -q`

### Phase 8: /runner/* control endpoints   ← Conversation: 3
**File:** `src/pathly_orchestrator/http_server.py` (MODIFY)
**Done when:** the 8 POST endpoints + `GET /runner/status` exist, are thin (mutate state, return immediately), and enforce start-requires-caps + 409-if-active.
**Delivers stories:** S3
**Depends on:** Phase 7
**Details:** wire each endpoint to the supervisor registry. `/runner/decision` validates `decision ∈ options`. `/runner/reroute` overrides next-stage adapter. Follow the existing route-decorator + CORS pattern.
**Verify:** `python -m pytest tests/ -q` + manual `curl -X POST .../runner/start ...`

### Phase 9: /events/runner SSE   ← Conversation: 3
**File:** `src/pathly_orchestrator/http_server.py` (MODIFY)
**Done when:** `GET /events/runner?topic=` streams the FEATURE_INDEX event types via a `_broadcast_runner` twin of `_broadcast_sse`.
**Delivers stories:** S3
**Depends on:** Phase 8
**Details:** clone the `/events/menu` handler (per-client `queue.Queue`, lock-guarded registry, keepalive). The supervisor calls `_broadcast_runner(topic, payload)` at each state change / cost update / decision / session event. Do not alter `/events/menu` or `/events/stream`.
**Verify:** `python -m pytest tests/ -q` + manual SSE check with `curl -N .../events/runner?topic=...`

### Phase 10: Endpoint + SSE tests   ← Conversation: 3
**File:** `tests/`
**Done when:** tests cover start (caps required, 409 on double-start), decision validation, reroute, abort, and an SSE event emission, all passing.
**Delivers stories:** S3
**Depends on:** Phase 9
**Verify:** `python -m pytest tests/ -q`

---

## Prerequisites
- `multi-adapter-routing` Conv 1 shipped (`preferred_adapter` in `/next_action`).
- FSM server importable/runnable; `tests/` green at baseline.

## Key Decisions
- **One `core/adapters.yaml`, TS mirror generated.** The only shared contract; generation + a staleness test make TS/Python drift structurally impossible.
- **Control API on the existing 8765 server, supervisor on a per-topic daemon thread.** Avoids a second service and self-HTTP; thin endpoints never block a request thread.
- **Pause = graceful at boundary; abort = immediate kill.** Cost control wants clean state on pause but instant stop on abort.
- **Caps are required start params and first-class state.** No unbounded autonomous runs.
- **Decisions feed the FSM, not a CLI.** Replaces the blocking `input()`; keeps the FSM authoritative.
- **In-memory RunnerState is authority; RUNNER_STATE.json is a durable mirror.** Matches the existing STATE.json/EVENTS.jsonl split.

## Risks
- **codex may not emit parseable cost JSON** → `cost_usd_so_far` could be codex-blind. Mitigation: the iteration cap is the universal guardrail; `parse:` per adapter handles known formats; see EDGE_CASES.
- **`--dangerously-skip-permissions` blast radius** across adapters → per-adapter `autonomy` flag + always-reachable abort + required caps.
