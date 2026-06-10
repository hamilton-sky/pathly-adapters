
## send-to-agent-diff (2026-06-10)

- **Diff reconstruct() needs unit tests early**: Section rebuild from diff hunks is stateful logic that silently produces empty sections when rejection handling is wrong. Write parametric unit tests in Conv 2, not after the test stage.
- **IPC wiring checklist**: observer setup, cleanup guard, and race condition guard should be a standard checklist for CommentsPanel-style terminal-driven flows.
- **Timing contract in DESIGN**: Event vs. polling for watch-disappear must be spec'd in DESIGN phase, not discovered by tester.
- **ARIA linting pre-commit**: role=dialog / role=tab violations consistently appear in review. Add linter rule or pre-commit hook.
- **CSS data-* attribute pattern**: Non-negotiable for 3+ mutually exclusive states — enforce at PR time, not in review.
- **FSM dual-state sync**: When manually editing STATE.json, always use eventlog.write_state() to sync the SQLite DB — direct file writes bypass on_state_counter reads.
