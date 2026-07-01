---
name: User Stories
---
# Multi-Adapter Runner — User Stories

## Context

Pathly's `pathly-run` (runner.py) autonomously drives a flow by spawning `claude -p` per stage. It hardcodes claude, blocks on `input()` at decision points (unusable from a UI), and has no pause/abort/cost controls. This feature makes the runner multi-adapter, controllable, and observable — the backend a UI command center (`hq-panel`) can drive. It depends on `multi-adapter-routing` providing `preferred_adapter`.

---

## Stories

### Story S1: One adapter→command contract for both execution paths
**As a** Pathly maintainer, **I want** a single declarative adapter→command map that both the headless runner and the Studio UI read, **so that** the two paths can never disagree about how to launch an adapter.

**Acceptance Criteria:**
- [ ] `src/pathly_data/core/adapters.yaml` defines, per adapter (claude/codex/copilot): `terminal_kind`, `headless` argv template, `autonomy_flag`, `resume` mode, and `parse`.
- [ ] `resolve_command(adapter, prompt, model, session=None)` returns `{argv, terminal_kind, supports_resume}` derived from `adapters.yaml`.
- [ ] `runner.py`'s `invoke_agent` builds its subprocess command via `resolve_command` — and the claude path produces the same command it does today (no behavior change for claude).
- [ ] `scripts/gen_adapters_ts.py` generates `studio/src/renderer/src/lib/adapters.gen.ts` from `adapters.yaml`.
- [ ] A test regenerates the TS mirror in memory and fails if the committed `adapters.gen.ts` is stale (anti-drift guarantee).
- [ ] An adapter whose `headless` is `null` (e.g. copilot) yields `supports_resume = false` and is never launched headless without error — it reports the limitation. (failure-case criterion)

**Edge Cases:** unknown adapter name passed to `resolve_command` → raises a clear error. `session` provided but adapter has `resume: null` → fresh command, `supports_resume=false`.

**Delivered by:** Phase 1 → Conversation 1

---

### Story S2: Controllable autonomous supervisor
**As a** Pathly user, **I want** the runner to expose a controllable loop with pause/abort/caps that routes each stage to its `preferred_adapter`, **so that** I can run a pipeline autonomously across adapters without it running away.

**Acceptance Criteria:**
- [ ] A `RunnerState` (keyed by topic, in an in-memory registry under a lock) tracks: status, current_state, current_adapter, open_session, iterations, max_iterations, cost_usd_so_far, max_cost_usd, autonomy, pause/abort flags, pending_menu.
- [ ] The run loop routes each stage to its `preferred_adapter` (from `/next_action`) via `resolve_command`.
- [ ] Pause and the cost/iteration caps are evaluated **only at stage boundaries** (between agent invocations).
- [ ] Abort is a **hard kill**: an in-flight subprocess is killed within ~2s and status becomes `aborted` (the one operation allowed to interrupt mid-subprocess). (failure-case criterion)
- [ ] When `cost_usd_so_far ≥ max_cost_usd` OR `iterations ≥ max_iterations`, the loop does NOT invoke another agent; it sets `status=error`, `kind=cap_exceeded`, and writes terminal state. (failure-case criterion)
- [ ] A decision point is resolved without blocking `input()`: the loop sets `status=awaiting_decision` + `pending_menu`, and resumes when a decision is supplied, feeding it to `complete_stage` (the choice goes to the FSM, not a CLI).
- [ ] Session continuity: if the next stage's adapter == the open session's adapter and the adapter supports resume → continue (resume flag); else → fresh session. A non-resumable adapter is flagged `degraded`.
- [ ] `RUNNER_STATE.json` in `pathly/plans/<topic>/` is a write-through mirror; on server startup any mirror left `running` is rewritten to `error`.
- [ ] An adapter with `autonomy[adapter]=false` is invoked WITHOUT its `autonomy_flag`. (failure-case criterion)

**Edge Cases:** `MAX_FEEDBACK_ROUNDS` behavior preserved from current runner. Subprocess timeout still kills and surfaces an error.

**Delivered by:** Phase 2 → Conversation 2

---

### Story S3: Control API + live SSE stream
**As a** UI (the `hq-panel` feature), **I want** HTTP control endpoints and a live SSE stream, **so that** a user can start/steer a run and watch stage/menu/cost updates in real time.

**Acceptance Criteria:**
- [ ] These POST endpoints exist on the FSM server (port 8765): `/runner/start`, `/runner/pause`, `/runner/resume`, `/runner/advance`, `/runner/decision`, `/runner/reroute`, `/runner/retry`, `/runner/abort`; plus `GET /runner/status?topic=`.
- [ ] `/runner/start` requires `max_iterations` and `max_cost_usd` (no unbounded runs) and returns 409 if a run for that topic is already active. (failure-case criterion)
- [ ] `/runner/decision` validates `decision ∈ options` and feeds it to the supervisor (→ `complete_stage`).
- [ ] `/runner/reroute` overrides `preferred_adapter` for the next stage only.
- [ ] `GET /events/runner?topic=` is an SSE stream emitting the event types in FEATURE_INDEX.md (STAGE_CHANGE, DECISION_MENU, RUNNER_STATUS, COST_UPDATE, SESSION, RUNNER_ERROR), reusing the existing `_broadcast_sse` machinery.
- [ ] Control endpoints are thin: they mutate `RunnerState` under the lock and return immediately (the loop runs on its own daemon thread; no blocking on a request thread).
- [ ] Existing endpoints (`/next_action`, `/complete_stage`, `/events/menu`, `/events/stream`) are unchanged.

**Edge Cases:** control call for an unknown/finished topic → clear 404/409, never a 500. SSE client disconnect → queue deregistered (existing pattern).

**Delivered by:** Phase 3 → Conversation 3

---

## Out of scope (future work)
- Studio HQ UI — the sibling `hq-panel` feature.
- Auto-launch of GUI/interactive CLIs — the runner uses headless invocation; the interactive PTY path is HQ's concern.
- Cross-adapter cost normalization — see EDGE_CASES (codex may not report cost; iteration cap is the universal guardrail).
