---

---
## Feedback protocol

All feedback files live in `<feature_path>/feedback/`. File exists = issue open.
Absent = resolved.

Priority order (highest first): `HUMAN_QUESTIONS.md` › `ARCH_FEEDBACK.md` › `DESIGN_QUESTIONS.md` ›
`ACCEPTANCE_QUESTION.md` › `IMPL_QUESTIONS.md` › `REFLECT_CRITIQUE.md` › `REVIEW_FAILURES.md` › `TEST_FAILURES.md`

When you write a feedback file, use the shared feedback protocol formats and then report blocked.
The orchestrator routes the highest-priority open file to the responsible agent, one at a time,
before advancing.

### Guard — feedback-open check

Before spawning the stage agent, scan `<feature_path>/feedback/`. If any file exists:
1. Identify the highest-priority file using the order above.
2. Log file created for that file.
3. Route to the responsible agent (see the stage's feedback routing section).
4. When resolved and the file is deleted: log file deleted. Re-scan.
5. Only proceed when no feedback files remain.

### Guard — retry-count check (3-tier escalation)

A **failure** file (`REVIEW_FAILURES.md`, `TEST_FAILURES.md`, `SCOPE_VIOLATION.md`) routes
**upstream** as the same loop keeps failing — repeated failure usually means the
plan / design / acceptance-criteria are wrong, not the local fix:

- **Rounds 1–2** → the file's owner (the **builder**). Log retry for `conv-N:FILE.md`, route the fix.
- **Round 3** → the **upstream specialist** named in the flow's `escalation_routing`
  (e.g. `REVIEW_FAILURES → planner`, `TEST_FAILURES → po`) — the plan/criteria are the suspect.
- **Round 4+** → the **human** (the FSM returns `decision: escalate`).

You don't choose the target — the FSM's `route_feedback` resolves it from the flow's
`feedback_routing` + `escalation_routing` and the file's retry count. **Your job:** write the
failure file and report blocked; the FSM routes it to the right role. (Log retry for
`conv-N:FILE.md` so the count advances. Check it via the central DB if you need to:
`python3 -c "from pathly_orchestrator.db import get_db; c=get_db(); print(c.execute(\"SELECT COUNT(*) FROM fsm_events WHERE feature=? AND event_type='RETRY' AND json_extract(payload,'$.key')=?\",('<feature>','conv-N:FILE.md')).fetchone()[0])"`)

**Clarification** requests are exempt from tiering and always go to their owner:
`IMPL_QUESTIONS.md → planner`, `DESIGN_QUESTIONS.md → designer/architect`,
`ACCEPTANCE_QUESTION.md → po` (the tester asks whether the acceptance criteria themselves are right).
