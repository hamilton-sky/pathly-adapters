# Scout 2 — Hook Reliability (classify_feedback, inject_feedback_ttl)

Objective: Analyze hook implementations for correctness and failure modes.

Files in scope:
- src/pathly_hooks/ — all .sh files, env handling, exit codes
- src/install_cli/ — hook registration and setup logic

Task:
1. Locate classify_feedback and inject_feedback_ttl hook definitions
2. Trace execution flow: when are they called, with what inputs, expected outputs
3. Identify potential failure modes: env var missing, file not found, permission denied
4. Check error handling: graceful degradation vs. hard failures
5. List concrete improvements with file:line pointers

Output: Hook analysis with 2-5 actionable improvements.
