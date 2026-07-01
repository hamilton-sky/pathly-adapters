# FEATURE_INDEX.md — agent-done-early-advance

## What this feature does

**Core (Conv 1–2):** When an agent writes an `AGENT_DONE` event to `EVENTS.jsonl` mid-run, the supervisor
advances the FSM immediately — without waiting for the PTY process to exit. The PTY
path remains alive so billing data (cost_usd, session_id) can arrive via the normal
`/runner/terminal/result` POST after the early advance. If billing data never arrives
within a 30-second reconciliation window, a `STAGE_RECONCILIATION_FAILURE` event is
written and the orchestrator falls back to EVENTS.jsonl cost data.

**Interactive mode (Conv 4):** When `PATHLY_RUNNER_INTERACTIVE=1`, agents run in a visible
non-headless PTY (no `--print`/`--output-format=json`). On AGENT_DONE detection the supervisor
emits `TERMINAL_KILL` SSE — Studio closes the tab — instead of waiting for natural PTY exit
or starting a reconciliation window.

**Pipeline History (Conv 5):** Every stage prompt includes a `## Pipeline History` section
auto-generated from AGENT_DONE summaries in EVENTS.jsonl, giving each agent full context of
what previous agents accomplished without re-reading plan files.

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
| `src/pathly_orchestrator/events.py` | Add constant | `TYPE_STAGE_INTERACTIVE_DONE` string constant + schema comment |
| `src/pathly_orchestrator/feature_flags.py` | Add property | `interactive` boolean flag (`PATHLY_RUNNER_INTERACTIVE`) |
| `src/pathly_orchestrator/supervisor.py` | Extend fast-path | Strip headless flags when interactive; emit `TERMINAL_KILL` SSE + `STAGE_INTERACTIVE_DONE` event on AGENT_DONE |
| `src/pathly_orchestrator/runner.py` | Add function | `build_pipeline_history_block()` — generates `## Pipeline History` markdown from EVENTS.jsonl |
| `src/pathly_orchestrator/fsm_ops.py` | Extend `build_prompt()` | Append pipeline history block after composed skill text |

## Conversation map

| Conversation | Scope | Stories delivered |
|---|---|---|
| Conv 1 | `events.py` constant + `runner.py` tail generator + `feature_flags.py` property | S-1, S-2 |
| Conv 2 | `supervisor.py` watcher + reconciliation window + billing-only update + tests | S-3, S-4, S-5, S-6 |
| Conv 3 (optional) | `terminal.ts` SSE pill | cosmetic only, no story gate |
| Conv 4 | `events.py` constant + `feature_flags.py` interactive + `supervisor.py` interactive-mode branch | S-7 |
| Conv 5 | `runner.py` `build_pipeline_history_block` + `fsm_ops.py` injection | S-8 |
