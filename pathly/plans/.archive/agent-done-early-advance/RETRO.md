# RETRO.md — agent-done-early-advance

## 1. What went well

- **Modular conversation design**: 5 focused conversations (foundation → watcher → SSE → interactive → history) with clear dependency ordering. All passed review on first attempt.
- **Consistent implementation patterns**: Builders followed established conventions (FeatureFlags property decorator, lazy imports in fsm_ops, SSE broadcast ordering) — reduced review friction.
- **Test discipline**: Each conversation added tests covering happy path + edge cases. Final count grew 396→404 with zero failures.
- **Billing-update fix interleaved smoothly**: `mergeBillingUpdate()` in Studio was a pure function, integrated cleanly with EventLog routing without blocking Conv 3+.
- **Studio integration minimal**: TERMINAL_AGENT_DONE SSE pill + dotFinalizing CSS were cosmetic changes with no breaking impacts on Monitor or HQ logic.

## 2. What was harder than expected

- **Reconciliation window complexity**: 30-second billing wait required careful thread orchestration (_agent_done_watcher vs _reconciliation_window race, PTY result handler guard). Analysis phase in Conv 2 took longest due to correctness concerns around cost/tool patch timing.
- **Interactive mode guard design**: Startup-time RuntimeError check (interactive=True without early_advance=True) required clarifying when to fail vs. warn.
- **Gate artifact require_artifact**: GATE_FAILED event before TESTING — REVIEW.md was missing, blocking transition. Required manual creation + resolved-file flag. Gate could be more lenient about artifact creation timing.

## 3. What we'd do differently

- **Pre-define reconciliation window SLA in USER_STORIES**: Specify the 30-second billing timeout upfront rather than discovering it during Conv 2 analysis.
- **Add event-type enum guard test to pipeline history**: `build_pipeline_history_block()` filtering should have an explicit test asserting non-AGENT_DONE types are dropped.
- **Defer cosmetic SSE pills to separate feature**: Conv 3 (TERMINAL_AGENT_DONE visual) could be a follow-up branch. Early advance core (Conv 1-2) stands alone.
- **Document interactive ↔ early_advance coupling in ARCHITECTURE_PROPOSAL.md**: Not in Conv 4 analysis. Helps adapters understand capability dependencies earlier.
