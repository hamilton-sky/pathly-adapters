## Feedback protocol

All feedback files live in `<feature_path>/feedback/`. File exists = issue open.
Absent = resolved.

Priority order (highest first): `HUMAN_QUESTIONS.md` › `ARCH_FEEDBACK.md` › `DESIGN_QUESTIONS.md` ›
`IMPL_QUESTIONS.md` › `REVIEW_FAILURES.md` › `TEST_FAILURES.md`

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

### Guard — retry-count check

Before routing any feedback file to its agent:
1. Check the retry count for `conv-N:FILE.md` in EVENTS.jsonl.
2. If > 2: write `HUMAN_QUESTIONS.md` with an escalation message, log file created for
   `HUMAN_QUESTIONS.md`. Stop and report the retry limit exceeded.
3. If ≤ 2: after routing the fix agent, log retry for `conv-N:FILE.md`.

Max 2 feedback cycles per conversation per feedback file. If exceeded, escalate to
`HUMAN_QUESTIONS.md`.

Exception: `IMPL_QUESTIONS.md` and `DESIGN_QUESTIONS.md` are clarification requests — exempt
from retry counting.
