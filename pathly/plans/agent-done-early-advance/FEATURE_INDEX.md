# FEATURE_INDEX.md — agent-done-early-advance

## What this feature does

When an agent writes an `AGENT_DONE` event to `EVENTS.jsonl` mid-run, the supervisor
advances the FSM immediately — without waiting for the PTY process to exit. The PTY
path remains alive so billing data (cost_usd, session_id) can arrive via the normal
`/runner/terminal/result` POST after the early advance. If billing data never arrives
within a 30-second reconciliation window, a `STAGE_RECONCILIATION_FAILURE` event is
written and the orchestrator falls back to EVENTS.jsonl cost data.

## Plan files

| File | Purpose |
|---|---|
| FEATURE_INDEX.md | This file — map of all plan artifacts and touchpoints |
| USER_STORIES.md | Six acceptance-criteria-driven stories |
| IMPLEMENTATION_PLAN.md | Phases with File + Done when + Verify per phase |
| PROGRESS.md | Conversation tracking table |
| CONVERSATION_PROMPTS.md | Builder prompts (3 conversations) |
| HAPPY_FLOW.md | Nominal path narrative |
| EDGE_CASES.md | Non-nominal scenarios |
| ARCHITECTURE_PROPOSAL.md | ADR-001 Option C summary |
| FLOW_DIAGRAM.md | ASCII dual-path diagram |

## Codebase touchpoints

| File | Change type | What changes |
|---|---|---|
| `src/pathly_orchestrator/events.py` | Add constant | `TYPE_STAGE_RECONCILIATION_FAILURE` string constant + schema comment |
| `src/pathly_orchestrator/runner.py` | Add function | `tail_agent_done()` polling generator |
| `src/pathly_orchestrator/feature_flags.py` | Add property | `early_advance` boolean flag |
| `src/pathly_orchestrator/supervisor.py` | Core logic | `_agent_done_events` dict, watcher thread, fast-path branch, reconciliation window, billing-only update |
| `tests/test_supervisor.py` | Add tests | Three new test cases covering fast path, timeout, no-regression |
| `studio/src/main/ipc/terminal.ts` | Optional SSE | `TERMINAL_AGENT_DONE` SSE emission when watcher fires (cosmetic, no PTY logic change) |

## Conversation map

| Conversation | Scope | Stories delivered |
|---|---|---|
| Conv 1 | `events.py` constant + `runner.py` tail generator + `feature_flags.py` property | S-1, S-2 |
| Conv 2 | `supervisor.py` watcher + reconciliation window + billing-only update + tests | S-3, S-4, S-5, S-6 |
| Conv 3 (optional) | `terminal.ts` SSE pill | cosmetic only, no story gate |
