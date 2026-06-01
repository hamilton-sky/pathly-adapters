---
name: Conversation Guide
---
# Multi-Adapter Runner — Conversation Guide

Split into 3 conversations (strict order `1 → 2 → 3`). Each produces runnable, tested code.
After each conversation, **commit your changes** before starting the next.

**Upstream dependency:** `multi-adapter-routing` Conv 1 (preferred_adapter) must be shipped first.

---

## Conversation 1: Adapter→command contract (Phases 0-4)

**Stories delivered:** S1

**Prompt to paste:**
```
Read pathly/plans/multi-adapter-runner/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Multi-Adapter Runner Conversation 1 (Phases 0-4) from pathly/plans/multi-adapter-runner/IMPLEMENTATION_PLAN.md.

Before editing anything: glob/read the live repo to confirm every path. Read CLAUDE.md, src/pathly_orchestrator/CLAUDE.md, and src/pathly_data/CLAUDE.md (the core/-is-truth + adapter sync rule).

Scope:
- Phase 0 (pre-flight): run `python -m pytest tests/ -q` (baseline). Confirm `/next_action` returns `preferred_adapter` (grep fsm_ops.py) — if it does NOT, STOP and report (this feature depends on multi-adapter-routing Conv 1). Note the existing JSON cost/session_id parsing in runner.py invoke_agent.
- Phase 1: create src/pathly_data/core/adapters.yaml with claude/codex/copilot per the canonical shape in FEATURE_INDEX.md (terminal_kind, headless argv template, autonomy_flag, resume, parse). copilot has headless:null / resume:null.
- Phase 2: create src/pathly_orchestrator/adapters.py with resolve_command(adapter, prompt, model, session=None) -> {argv, terminal_kind, supports_resume}. Read adapters.yaml via importlib.resources (same pattern as runner._storage_path). Unknown adapter raises a clear error. supports_resume = resume is not None. Parameterize autonomy-flag inclusion.
- Phase 3: create scripts/gen_adapters_ts.py that writes studio/src/renderer/src/lib/adapters.gen.ts from adapters.yaml (verify the lib/ dir exists first). Add a test that regenerates in memory and FAILS if the committed adapters.gen.ts is stale.
- Phase 4: refactor runner.py invoke_agent to build its command via resolve_command. The claude path MUST stay behavior-identical (same argv it builds today). Keep the timeout/kill, JSON parse, and _patch_last_agent_done telemetry. Add an `adapter` param defaulting to "claude".

Architectural rules: adapters.yaml is the SINGLE source of truth; the TS file is generated, never hand-edited. Do not duplicate the command shape anywhere else.

Do NOT touch: http_server.py, supervisor.py (does not exist yet — do not create it this conversation), or anything under studio/ except the generated adapters.gen.ts.
Verify: `python -m pytest tests/ -q` and `python scripts/gen_adapters_ts.py`
After done, update pathly/plans/multi-adapter-runner/PROGRESS.md phases 0-4 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `adapters.yaml`, `resolve_command`, the TS generator + staleness test, and `invoke_agent` building commands from the map (claude unchanged).
**Files touched:** `src/pathly_data/core/adapters.yaml`, `src/pathly_orchestrator/adapters.py`, `scripts/gen_adapters_ts.py`, `studio/src/renderer/src/lib/adapters.gen.ts`, `src/pathly_orchestrator/runner.py`, `tests/`

---

## Conversation 2: Autonomous supervisor + RunnerState (Phases 5-7)

**Stories delivered:** S2

**Prompt to paste:**
```
Read pathly/plans/multi-adapter-runner/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Multi-Adapter Runner Conversation 2 (Phases 5-7) from pathly/plans/multi-adapter-runner/IMPLEMENTATION_PLAN.md. Conversation 1 (adapters.yaml + resolve_command + invoke_agent refactor) is complete.

Before editing anything: glob/read the live repo to confirm paths. Re-read runner.py (run_flow, resolve_stage, handle_decide, invoke_agent) — you will reuse this logic.

Scope:
- Phase 5: create src/pathly_orchestrator/supervisor.py with a RunnerState dataclass and an in-memory registry keyed by topic under a threading.Lock (fields per USER_STORIES S2). Add a RUNNER_STATE.json write-through mirror in pathly/plans/<topic>/. On module import / server startup, rewrite any mirror left status="running" to "error".
- Phase 6: add a per-topic daemon-thread run loop: next_action → resolve_command → invoke_agent → advance. Evaluate pause and the cost/iteration caps ONLY at stage boundaries. Abort is a hard kill (proc.kill within ~2s) and is the only thing allowed to interrupt mid-subprocess. Caps exceeded → status=error, kind=cap_exceeded, no further invocation. Accumulate cost_usd_so_far from the parsed cost.
- Phase 7: replace handle_decide's blocking input() with state-driven decision handling — set status=awaiting_decision + pending_menu, and resume when a decision is supplied, feeding it to complete_stage (the choice goes to the FSM, not a CLI). Implement session continuity: compare the next stage's adapter to open_session.adapter; continue (resume flag) if same and resumable, else fresh; mark degraded if the adapter is non-resumable. Capture session_id from claude JSON into open_session.

Architectural rules: the supervisor calls the FSM via the existing fsm_http_client; the FSM never imports the supervisor. Reuse runner.invoke_agent — do not duplicate command construction.

Do NOT touch: http_server.py (the HTTP control surface is Conversation 3), adapters.yaml/adapters.py, or anything under studio/.
Verify: `python -m pytest tests/ -q` (drive the supervisor with a fake/stub FSM client in tests).
After done, update pathly/plans/multi-adapter-runner/PROGRESS.md phases 5-7 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** A threaded, controllable supervisor with caps, hard abort, FSM-fed decisions, and session continuity — unit-tested against a fake FSM client.
**Files touched:** `src/pathly_orchestrator/supervisor.py`, `src/pathly_orchestrator/runner.py`, `tests/`

---

## Conversation 3: Control API + /events/runner SSE (Phases 8-10)

**Stories delivered:** S3

**Prompt to paste:**
```
Read pathly/plans/multi-adapter-runner/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Multi-Adapter Runner Conversation 3 (Phases 8-10) from pathly/plans/multi-adapter-runner/IMPLEMENTATION_PLAN.md. Conversations 1-2 are complete (the supervisor exists in supervisor.py).

Before editing anything: glob/read the live repo. Read http_server.py fully — especially the existing route decorators, the CORS/OPTIONS pattern on /chat, and the SSE machinery (_broadcast_sse, the /events/menu handler with its per-client queue.Queue + lock-guarded registry + keepalive).

Scope:
- Phase 8: add POST endpoints /runner/start, /runner/pause, /runner/resume, /runner/advance, /runner/decision, /runner/reroute, /runner/retry, /runner/abort and GET /runner/status?topic=. Wire each to the supervisor registry. They must be thin — mutate RunnerState and return immediately (never block a request thread; the loop runs on its own daemon thread). /runner/start requires max_iterations and max_cost_usd and returns 409 if a run for that topic is already active. /runner/decision validates decision ∈ options. /runner/reroute overrides the next-stage adapter only.
- Phase 9: add GET /events/runner?topic= as an SSE endpoint, cloning the /events/menu pattern. Add a _broadcast_runner(topic, payload) twin of _broadcast_sse. The supervisor calls it to emit STAGE_CHANGE / DECISION_MENU / RUNNER_STATUS / COST_UPDATE / SESSION / RUNNER_ERROR (exact fields in FEATURE_INDEX.md). Do NOT modify /events/menu or /events/stream.
- Phase 10: add tests covering start (caps required + 409 on double-start), decision validation, reroute, abort, and one SSE emission.

Architectural rules: control endpoints depend on the supervisor; the FSM/supervisor never import HTTP code beyond the broadcast hook. Keep existing endpoints unchanged.

Do NOT touch: adapters.yaml/adapters.py, supervisor core logic (only add the _broadcast_runner hook calls if needed), or anything under studio/.
Verify: `python -m pytest tests/ -q`, then exercise the runner start endpoint with a JSON-capable client and confirm the runner events stream with a streaming-capable client.
After done, update pathly/plans/multi-adapter-runner/PROGRESS.md phases 8-10 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** A full `/runner/*` control API + `/events/runner` SSE stream on port 8765, tested — the backend a UI can drive.
**Files touched:** `src/pathly_orchestrator/http_server.py`, `tests/`

---

## After Conversation 3 — hard CI gate
Before the `hq-panel` Studio feature begins: confirm the full Python path is drivable by curl — start a run, observe SSE events, supply a decision, abort. This gate matches the agreed sequence (backend before Studio, gated by CI).
