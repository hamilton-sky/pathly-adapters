# team-flow/review

Stage 3b — Review. Invoked by the `team-flow` orchestrator when FSM state is REVIEWING.
Runs reviewer for the current conversation, handles feedback loops, then advances.

Parse `$ARGUMENTS`: `FEATURE`, `rigor`, `autoFlow`. Conv N is the most recent BUILDING conversation
(last row in PROGRESS.md that is not yet DONE).

## FSM operations

All events are appended to `plans/<feature>/EVENTS.jsonl` as JSON lines.
State snapshots are written to `plans/<feature>/STATE.json`.

- **Transition state to X:** Write STATE.json `{"current": "X"}`. Append `{"type": "STATE_TRANSITION", "to": "X"}`.
- **Log file created:** Append `{"type": "FILE_CREATED", "file": "<filename>"}`.
- **Log file deleted:** Append `{"type": "FILE_DELETED", "file": "<filename>"}`.
- **Log retry:** Append `{"type": "RETRY", "key": "conv-N:FILE.md"}`.
- **Check retry count:** Count RETRY events in EVENTS.jsonl where `key = "conv-N:FILE.md"`.
- **Log human response:** Append `{"type": "HUMAN_RESPONSE", "value": "<value>"}`.

## Subagents

| Action | Spawn |
|---|---|
| Gather applicable rules | `scout` with `ROLE: reviewer` |
| Review changes | `reviewer` |
| Fix architectural violations | `architect` |
| Fix implementation violations | `builder` |

## Rigor gate

- `lite`: reviewer runs once after the **final** builder conversation, unless any of these apply:
  feedback files exist, risky files were touched, or user preference requires per-conversation review.
  If this is not the final conversation and none of those conditions apply → skip directly to Advance.
- `standard` or `strict`: reviewer runs after **every** builder conversation.

---

## Pre-review scout

**Spawn** `scout` with `ROLE: reviewer`:
```
ROLE: reviewer
What architectural rules, layer contracts, and coding conventions apply to the files changed
in conversation N of [feature]?
Check: project guidance files (CLAUDE.md, .claude/rules/), plans/[feature]/ARCHITECTURE_PROPOSAL.md
if it exists.
Return only the rules relevant to the specific files touched — not a general summary.
```

## Reviewer spawn

**Spawn** `reviewer` with scout findings injected:
```
Review the changes from conversation N of [feature].
Run: git diff HEAD~1 HEAD (or git diff --staged if not yet committed).

## Applicable Rules (from pre-review scout)
[scout findings]

Check against these rules and plans/[feature]/ARCHITECTURE_PROPOSAL.md.
If architectural violations found: write plans/[feature]/feedback/ARCH_FEEDBACK.md
If implementation violations found: write plans/[feature]/feedback/REVIEW_FAILURES.md
Use the shared feedback protocol formats.
If all clear: report PASS.
```

---

## Feedback routing after reviewer

### If `ARCH_FEEDBACK.md` exists

Check retry count for `conv-N:ARCH_FEEDBACK.md`:
- If > 2: write HUMAN_QUESTIONS.md with escalation. Log file created for HUMAN_QUESTIONS.md.
  Stop: "Feedback loop exceeded for Conv N. Manual intervention required."
- Else: log retry for `conv-N:ARCH_FEEDBACK.md`.

**Spawn** `architect`:
```
Read plans/[feature]/feedback/ARCH_FEEDBACK.md.
Redesign the affected architecture in plans/[feature]/ARCHITECTURE_PROPOSAL.md,
or plans/[feature]/IMPLEMENTATION_PLAN.md for lite plans without ARCHITECTURE_PROPOSAL.md.
If phases need to change, update IMPLEMENTATION_PLAN.md.
Delete plans/[feature]/feedback/ARCH_FEEDBACK.md when resolved.
Report: what changed in the design.
```
After architect resolves: log file deleted for ARCH_FEEDBACK.md.
Transition state → BUILDING.
Route back to `team-flow [FEATURE] [rigor] [autoFlow]`. (Orchestrator re-runs build for Conv N.)

### If `REVIEW_FAILURES.md` exists (no ARCH_FEEDBACK.md)

Check retry count for `conv-N:REVIEW_FAILURES.md`:
- If > 2: write HUMAN_QUESTIONS.md with escalation. Log file created for HUMAN_QUESTIONS.md. Stop.
- Else: log retry for `conv-N:REVIEW_FAILURES.md`.

**Spawn** `builder`:
```
Read plans/[feature]/feedback/REVIEW_FAILURES.md.
Fix each violation listed. Do not change anything outside the listed violations.
Delete plans/[feature]/feedback/REVIEW_FAILURES.md when all fixed.
```

**Guard — zero-diff stall check** (before re-spawning reviewer):
```bash
git diff HEAD -- . ":(exclude)plans/"
```
- If command fails: skip check, print `[FSM WARNING] git diff failed — skipping zero-diff check`.
- If output is **empty** (no code changed):
  Write `plans/[feature]/feedback/HUMAN_QUESTIONS.md`:
  ```
  [STALL] Conversation N — builder and reviewer in zero-diff loop.
  Builder claimed to fix REVIEW_FAILURES.md but no code changed.
  Human decision required: accept as-is, override the rule, or rewrite the conversation scope.
  ```
  Append `{"type": "NO_DIFF_DETECTED"}` to EVENTS.jsonl.
  Stop: "Zero-diff loop detected for Conv N. Escalated to HUMAN_QUESTIONS.md."
- If output is **non-empty**: re-run reviewer spawn above (go back to pre-review scout).

### If no feedback files — PASS

Append `{"type": "AGENT_DONE", "agent": "reviewer"}` to EVENTS.jsonl.

---

## Advance

If not autoFlow — pause:
```
[Stage 3 — Conversation N complete + reviewed]
Reviewer: PASS. Commit your changes now.
Reply 'continue' for the next conversation, or 'stop' to pause here.
```
- Proceed signal: log human response with reply value. Advance.
- Stop signal: log human response "stop". Write STATE.json with current state. Halt.
- Unrecognised: re-prompt without logging.

If autoFlow: log human response "auto-advance".

Mark Conv N as DONE in `plans/[feature]/PROGRESS.md`.

**Check if all conversations are now DONE:**
- If more TODO conversations remain: transition state → BUILDING.
  Route back to `team-flow [FEATURE] [rigor] [autoFlow]`. (Orchestrator routes to build for next conv.)
- If all DONE: append `{"type": "IMPLEMENT_COMPLETE"}` to EVENTS.jsonl.
  Transition state → TESTING.
  Route back to `team-flow [FEATURE] [rigor] [autoFlow]`. (Orchestrator routes to test.)
