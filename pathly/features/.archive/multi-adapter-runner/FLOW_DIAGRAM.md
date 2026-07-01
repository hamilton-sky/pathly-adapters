---
name: Flow Diagram
---
# Multi-Adapter Runner — Flow Diagram

## Supervisor loop (per topic, daemon thread)

```
/runner/start (caps required)
        │  register RunnerState, spawn thread
        ▼
┌──► BOUNDARY ──────────────────────────────────────────┐
│      │ abort_requested?  ──yes─► kill subproc, ABORTED │
│      │ pause_requested?  ──yes─► wait (PAUSED) ◄──resume│
│      │ caps exceeded?    ──yes─► ERROR(cap_exceeded)    │
│      ▼ no                                               │
│   next_action() ──► preferred_adapter                   │
│      │                                                  │
│   resolve_command(adapter,prompt,model,session)         │
│      │ {argv, terminal_kind, supports_resume}           │
│      ▼                                                  │
│   invoke_agent(argv)  (headless; abort may kill)        │
│      │  parse cost/session_id → cost_so_far, open_session│
│      ▼                                                  │
│   complete_stage() ──► next_state | decide | blocked    │
│      ├─ decide ─► AWAITING_DECISION (pending_menu) ◄─┐  │
│      │              /runner/decision → complete_stage─┘  │
│      ├─ blocked ─► feedback rounds (MAX_FEEDBACK_ROUNDS) │
│      └─ next_state ─► advance; iteration++              │
└────────────────────────────────────────────────────────┘
        │ DONE
        ▼  status=done; thread exits
```

## Adapter→command resolution (the shared contract)

```
core/adapters.yaml ──runtime read──► resolve_command()
        │                                 │
        │ build-time (scripts/gen)        ├─ adapter known? ──no─► raise
        ▼                                 ├─ substitute {prompt}/{model}
studio/.../adapters.gen.ts                ├─ session + resume? ─► splice resume flag
   (hq-panel reads; staleness             └─ autonomy[adapter]? ─► include autonomy_flag
    test guards drift)                     → {argv, terminal_kind, supports_resume}
```

## Session continuity decision

```
next stage adapter vs open_session.adapter
        ├─ same  AND supports_resume ─► continue (resume flag)  SESSION{continued}
        ├─ different ────────────────► fresh session           SESSION{opened}
        └─ same BUT not resumable ───► fresh + degraded         SESSION{opened,degraded}
```

## Control + SSE surface

```
HQ (hq-panel) ──HTTP POST──► /runner/{start,pause,resume,advance,
   │                          decision,reroute,retry,abort}
   │                              │ mutate RunnerState (thin, returns now)
   │                              ▼
   │                         supervisor daemon loop
   │                              │ _broadcast_runner(topic, payload)
   └──SSE◄── /events/runner ◄─────┘
        STAGE_CHANGE / DECISION_MENU / RUNNER_STATUS /
        COST_UPDATE / SESSION / RUNNER_ERROR
```

## Component Legend

| Symbol | Meaning |
|--------|---------|
| RunnerState | Per-topic control state (status, caps, open_session, pending_menu) |
| resolve_command | Pure fn: adapter+prompt → argv/terminal_kind/supports_resume |
| invoke_agent | Headless executor (subprocess); abort may kill it |
| _broadcast_runner | SSE fan-out twin of the existing _broadcast_sse |
| BOUNDARY | Between-stage checkpoint where pause/abort/caps are evaluated |
