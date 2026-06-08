---
name: Architecture Proposal
---
# Multi-Adapter Runner — Architecture Proposal

## Problem Statement

`pathly-run` autonomously drives a flow but hardcodes `claude -p`, blocks on `input()` at decisions (unusable from a UI), and has no pause/abort/cost controls. We need a multi-adapter, controllable, observable supervisor — without making the FSM spawn anything.

## Proposed Solution

Three layers, one shared contract:
1. **`core/adapters.yaml`** — the adapter→command map. Python reads it at runtime; a generator emits a TS mirror for the Studio side.
2. **`supervisor.py`** — a threaded, per-topic run loop with `RunnerState` (pause/abort/caps, FSM-fed decisions, session continuity).
3. **`/runner/*` + `/events/runner`** — thin control endpoints and an SSE stream on the existing 8765 server.

## Layer Breakdown

```
core/adapters.yaml ──runtime──► adapters.resolve_command()
        │ build-time gen                 │ {argv, terminal_kind, supports_resume}
        ▼                                ▼
studio/.../adapters.gen.ts        runner.invoke_agent (headless executor)
   (hq-panel consumes)                   │
                                         ▼
                              supervisor: RunnerState + daemon loop
                                         │ next_action / complete_stage (HTTP client)
                                         ▼
                              http_server: /runner/* + /events/runner
                                         │  (hq-panel consumes)
                                         ▼  FSM stays passive
```

## Key Design Decisions

### Decision 1: One `core/adapters.yaml`; the TS side is generated (the keystone)
- **Options:** duplicate command logic in TS + Python; a Python module; a YAML in `core/`.
- **Chosen:** YAML in `core/`, Python reads at runtime, `scripts/gen_adapters_ts.py` emits the TS mirror, a test asserts the mirror isn't stale.
- **Rationale:** command shape is adapter data, and `core/` is the data layer's single source of truth. Generating the TS side makes headless/Studio drift **structurally impossible** rather than a matter of discipline. This is the single most load-bearing decision — land it in Conv 1.
- **Anti-pattern avoided:** do NOT put command shape in `_meta/*.yaml` (those are per-adapter×agent and would force N copies). Command shape is per-adapter.

### Decision 2: Control API on 8765; supervisor on a per-topic daemon thread
- **Rationale:** the SSE registry, CORS, and FSM client already live in this process; a second service would need its own fan-out and a socket back to 8765. Flask is `threaded=True`, but a 600s blocking run can't sit on a request thread — so the loop runs on a dedicated daemon (same pattern as `_tail_events`), and control endpoints just mutate `RunnerState` and return.

### Decision 3: Pause = graceful at boundary; abort = immediate kill
- **Rationale:** pause and caps want clean state, so they're checked between agent invocations. But "stop spending money now" can't wait for a 600s agent — abort is the one operation that interrupts a subprocess (`proc.kill()`).

### Decision 4: Caps are required start params and first-class state
- **Rationale:** an autonomous, permission-skipping, multi-adapter loop must never be unbounded. `max_iterations` and `max_cost_usd` are required on `/runner/start` and enforced at every boundary.

### Decision 5: Decisions feed the FSM, not a CLI
- **Rationale:** replaces the blocking `input()`. The supervisor parks at `awaiting_decision`; the supplied choice goes to `complete_stage`, keeping the FSM the single authority over transitions.

### Decision 6: In-memory RunnerState is authority; RUNNER_STATE.json is a durable mirror
- **Rationale:** the loop is a live thread; its truth is in RAM. The JSON survives restarts (a stale `running` becomes `error`), mirroring the existing STATE.json/EVENTS.jsonl split.

## Key Components
- `adapters.yaml` — per-adapter `terminal_kind`, `headless`, `autonomy_flag`, `resume`, `parse`.
- `resolve_command()` — `(adapter, prompt, model, session) → {argv, terminal_kind, supports_resume}`.
- `RunnerState` + registry — per-topic control state.
- `_broadcast_runner()` — SSE twin of `_broadcast_sse`.

## Interface Design
- `/runner/start` `{flow, topic, project_root, rigor, model?, max_iterations, max_cost_usd, autonomy}` → `{status, run_id}`; pause/resume/advance/decision/reroute/retry/abort `{topic, ...}`; `GET /runner/status?topic=`.
- `/events/runner?topic=` SSE — event schema in FEATURE_INDEX.md.

## Risks
- **codex cost-blindness:** if `codex exec` doesn't emit parseable cost JSON, `cost_usd_so_far` is claude-accurate but codex-blind. *Mitigation:* the iteration cap is the universal guardrail; `parse:` is per-adapter; scope the cost cap to adapters that report cost in v1. (See EDGE_CASES EC-3.x.)
- **`--dangerously-skip-permissions` blast radius across adapters:** *Mitigation:* per-adapter `autonomy` flag, required caps, always-reachable abort.
- **Non-resumable adapters:** copilot has no headless/resume. *Mitigation:* `resume: null` → `supports_resume=false`, fresh launch, `degraded` flag surfaced to the UI.

## Future Work
- Auto-launch supervisor hosted by a local LLM (Ollama/node-llama-cpp) or Brightsky for narrow done/retry/escalate judgments with constrained output.
- Cross-adapter cost normalization.
