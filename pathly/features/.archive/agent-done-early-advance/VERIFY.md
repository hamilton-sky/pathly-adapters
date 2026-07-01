RESULT: PASS
Verified: conversation 1 complete — TYPE_STAGE_RECONCILIATION_FAILURE constant added to events.py, FeatureFlags.early_advance property added to feature_flags.py, tail_agent_done() generator added to runner.py with threading/Generator imports, test_tail_agent_done_yields_and_stops added to test_runner.py; all 396 tests pass.

RESULT: PASS
Verified: conversation 2 complete — _agent_done_events/_agent_done_stop_events module dicts, _agent_done_watcher(), _reconciliation_window(), fast-path branch in _run_stage_via_terminal(), /runner/terminal/result handler guard confirmed, 3 new supervisor tests; all 399 tests pass.

RESULT: PASS (billing-update fix)
Verified: TYPE_BILLING_UPDATE constant added to events.py; _patch_last_agent_done in runner.py now appends BILLING_UPDATE after in-place patch; mergeBillingUpdate() added to Monitor/utils.ts; useMonitorSession.ts SSE handler routes BILLING_UPDATE to mergeBillingUpdate instead of appending — Studio EventLog now shows corrected cost/tool values after PTY exit; tsc --noEmit clean, 399 tests pass.

RESULT: PASS
Verified: conversation 5 complete — build_pipeline_history_block() added to runner.py (collects AGENT_DONE events oldest-first, max_items cap, returns markdown or ""); build_prompt() in fsm_ops.py imports and appends history after context block; 3 new tests: test_pipeline_history_block_format, test_pipeline_history_empty_when_no_events, test_build_prompt_includes_pipeline_history; 404 tests pass.

RESULT: PASS
Verified: conversation 4 complete — TYPE_STAGE_INTERACTIVE_DONE added to events.py; FeatureFlags.interactive property (PATHLY_RUNNER_INTERACTIVE); resolve_argv guards --print/--output-format=json via interactive param; supervisor startup guard (interactive without early_advance raises RuntimeError + RUNNER_WARNING); fast-path branch in _run_stage_via_terminal emits TERMINAL_KILL SSE, writes STAGE_INTERACTIVE_DONE, calls _cleanup_run_id (skips reconciliation window) in interactive mode; 2 new tests pass; 401 tests pass.

RESULT: PASS
Verified: conversation 3 complete — TERMINAL_AGENT_DONE SSE broadcast added to supervisor.py fast-path (before reconciliation thread start); RunnerStatus union extended with 'finalizing'; StageStatusStrip dotClass handles finalizing→dotFinalizing; stage text shows "${stage} — finalizing…" when status===finalizing; .dotFinalizing CSS class (amber pulsing); useHQ.tsx routes TERMINAL_AGENT_DONE to setRunnerState({status:'finalizing'}); 399 tests pass, tsc --noEmit clean.
