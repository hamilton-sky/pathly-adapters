---
name: Edge Cases
---
# Multi-Adapter Runner — Edge Cases

## Category 1: Caps & control

### EC-1.1: Cost cap reached mid-run
- **Trigger**: `cost_usd_so_far ≥ max_cost_usd` at a boundary.
- **Expected**: loop does NOT invoke the next agent; `status=error`, `kind=cap_exceeded`; `RUNNER_ERROR` SSE; terminal state mirrored.
- **Handled in**: Phase 6 / Conv 2.

### EC-1.2: Iteration cap reached
- **Trigger**: `iterations ≥ max_iterations` at a boundary.
- **Expected**: same as EC-1.1 (`cap_exceeded`). The iteration cap is the universal guardrail even when cost is unknown.
- **Handled in**: Phase 6 / Conv 2.

### EC-1.3: Abort during an in-flight subprocess
- **Trigger**: `/runner/abort` while an agent subprocess is running.
- **Expected**: subprocess killed within ~2s; `status=aborted`; this is the only operation that interrupts mid-subprocess.
- **Handled in**: Phase 6 / Conv 2.

### EC-1.4: start requires caps / double-start
- **Trigger**: `/runner/start` without `max_iterations`/`max_cost_usd`, or for a topic already running.
- **Expected**: 400 (missing caps) / 409 (already active) — never an unbounded run, never two loops per topic.
- **Handled in**: Phase 8 / Conv 3.

## Category 2: Sessions & adapters

### EC-2.1: Non-resumable adapter
- **Trigger**: next stage routes to copilot (`resume: null`).
- **Expected**: `supports_resume=false` → fresh launch; `SESSION{action:"opened", degraded:true}`.
- **Handled in**: Phase 7 / Conv 2; Phase 2 / Conv 1 (resolve_command).

### EC-2.2: Same adapter, consecutive stages
- **Trigger**: two stages both route to claude.
- **Expected**: continue the open session (resume flag + captured `session_id`); `SESSION{action:"continued"}`.
- **Handled in**: Phase 7 / Conv 2.

### EC-2.3: Unknown adapter in resolve_command
- **Trigger**: a topic rerouted to an adapter name not in `adapters.yaml`.
- **Expected**: `resolve_command` raises a clear error; `/runner/reroute` rejects an unknown adapter before it reaches the loop.
- **Handled in**: Phase 2 / Conv 1; Phase 8 / Conv 3.

## Category 3: Cost parsing

### EC-3.1: codex emits no parseable cost
- **Trigger**: `codex exec` output lacks a cost field.
- **Expected**: `cost_usd_so_far` does not advance for codex stages; the iteration cap still bounds the run; no crash. Documented as a v1 limitation.
- **Handled in**: Phase 6 / Conv 2 (`parse:` per adapter; safe default 0.0).

## Category 4: Crash / restart

### EC-4.1: Server restart with a run "in flight"
- **Trigger**: server restarts while a `RUNNER_STATE.json` says `running`.
- **Expected**: on startup the mirror is rewritten to `error` (the loop thread is gone); `GET /runner/status` reports `error`, not a false `running`.
- **Handled in**: Phase 5 / Conv 2.

### EC-4.2: Subprocess timeout
- **Trigger**: an agent subprocess exceeds the timeout.
- **Expected**: killed (existing behavior); surfaced as a `RUNNER_ERROR{kind:"subprocess"}`; loop stops cleanly.
- **Handled in**: Phase 6 / Conv 2.

## Category 5: SSE

### EC-5.1: Client disconnect
- **Trigger**: HQ closes the `/events/runner` EventSource.
- **Expected**: the per-client queue is deregistered (existing `/events/menu` pattern); the loop is unaffected.
- **Handled in**: Phase 9 / Conv 3.

## Known Limitations (out of scope)
- Cross-adapter cost normalization — cost cap is accurate only for adapters that report cost.
- Auto-launching interactive/GUI CLIs — headless invocation only; the interactive PTY path is the `hq-panel` feature.
- Multi-run-per-topic — one active run per topic by design (409 otherwise).
