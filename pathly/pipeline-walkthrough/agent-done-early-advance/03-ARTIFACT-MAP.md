# 03-ARTIFACT-MAP.md — agent-done-early-advance

**Date:** 2026-06-04  
**Branch:** master

---

## Feedback Files (resolved)

| File | Type | Raised | Resolved | Notes |
|---|---|---|---|---|
| feedback/HUMAN_QUESTIONS.md | require_artifact gate | REVIEWING→TESTING | Same session | REVIEW.md was missing; created manually, resolved with --resolved-file flag |

No REVIEW_FAILURES or TEST_FAILURES files raised.

---

## Plan Artifacts Produced

| File | Purpose |
|---|---|
| pathly/plans/agent-done-early-advance/FEATURE_INDEX.md | Entry point, codebase touchpoints |
| pathly/plans/agent-done-early-advance/USER_STORIES.md | 8 stories with acceptance criteria |
| pathly/plans/agent-done-early-advance/IMPLEMENTATION_PLAN.md | 5 conversation phases |
| pathly/plans/agent-done-early-advance/PROGRESS.md | Conversation status (all DONE) |
| pathly/plans/agent-done-early-advance/CONVERSATION_PROMPTS.md | 5 builder prompts |
| pathly/plans/agent-done-early-advance/HAPPY_FLOW.md | Ideal journey |
| pathly/plans/agent-done-early-advance/EDGE_CASES.md | Edge cases |
| pathly/plans/agent-done-early-advance/ARCHITECTURE_PROPOSAL.md | Design decisions |
| pathly/plans/agent-done-early-advance/FLOW_DIAGRAM.md | ASCII flow diagram |
| pathly/plans/agent-done-early-advance/VERIFY.md | PASS entries for all 5 convs |
| pathly/plans/agent-done-early-advance/REVIEW.md | PASS entries for all 5 convs |
| pathly/plans/agent-done-early-advance/RETRO.md | Retrospective |

---

## Source Files Changed

### Python — Orchestrator

| File | Changes |
|---|---|
| src/pathly_orchestrator/events.py | +TYPE_STAGE_RECONCILIATION_FAILURE, +TYPE_BILLING_UPDATE, +TYPE_STAGE_INTERACTIVE_DONE |
| src/pathly_orchestrator/feature_flags.py | +early_advance property, +interactive property |
| src/pathly_orchestrator/runner.py | +tail_agent_done(), +build_pipeline_history_block(), resolve_argv interactive param |
| src/pathly_orchestrator/supervisor.py | +_agent_done_events/_agent_done_stop_events dicts, +_agent_done_watcher, +_reconciliation_window, +_cleanup_run_id, fast-path branch, TERMINAL_AGENT_DONE broadcast, interactive kill path |
| src/pathly_orchestrator/fsm_ops.py | build_prompt() appends pipeline history block |
| src/pathly_orchestrator/http_server.py | /runner/terminal/result handler guard for reconciliation window |

### Studio — TypeScript/React

| File | Changes |
|---|---|
| studio/src/renderer/src/store/runnerStore.ts | RunnerStatus union +finalizing |
| studio/src/renderer/src/components/HQ/useHQ.tsx | TERMINAL_AGENT_DONE → setRunnerState({status:'finalizing'}) |
| studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.tsx | dotFinalizing class + "— finalizing…" text |
| studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.module.css | .dotFinalizing amber pulsing animation |
| studio/src/renderer/src/components/Monitor/utils.ts | +mergeBillingUpdate() |
| studio/src/renderer/src/components/Monitor/hooks/useMonitorSession.ts | BILLING_UPDATE SSE → mergeBillingUpdate |

### Tests

| File | Changes |
|---|---|
| tests/test_runner.py | +test_tail_agent_done_yields_and_stops, +test_pipeline_history_block_format, +test_pipeline_history_empty_when_no_events |
| tests/test_supervisor.py | +test_early_advance_with_billing_reconciliation, +test_early_advance_billing_timeout, +test_slow_path_no_regression, +test_interactive_mode_kills_pty_on_agent_done, +test_interactive_mode_strips_headless_flags |
| tests/test_fsm_ops.py | +test_build_prompt_includes_pipeline_history |

**Final test count: 404 passed, 3 skipped, 0 failed**
