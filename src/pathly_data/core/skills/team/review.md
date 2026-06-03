# team/review

Stage 3b — Review. Invoked by the `team` orchestrator when FSM state is REVIEWING.
Runs reviewer for the current conversation, handles feedback loops, then advances.

Parse `$ARGUMENTS`: `FEATURE`, `rigor`, `autoFlow`. Conv N is the most recent BUILDING conversation
(last row in PROGRESS.md that is not yet DONE).

> Shared protocols — **Scout choreography**, **Feedback protocol**, **Completion report**,
> **Sub-agent spawning rules**, and **Live progress logging** — are composed in below from
> fragments. This body covers only the REVIEWING-stage specifics.

## Role

**Stage orchestrator: Reviewing**
You coordinate subagents, handle feedback routing, and log every phase boundary.
Logging is mandatory — each `log-phase` call is part of the pipeline contract.

> After each phase completes, log `log-phase PHASE_DONE <phase>` before starting the next.
> If `pathly-fsm-call` is unavailable, skip silently — never block execution.

## FSM operations

All events are appended to `pathly/plans/<feature>/EVENTS.jsonl` as JSON lines.
Every appended event must include `"ts": "<iso-timestamp>"` using the current ISO-8601 UTC time.
State snapshots are written to `pathly/plans/<feature>/STATE.json`.

- **Log file created:** Append `{"type": "FILE_CREATED", "file": "<filename>", "ts": "<iso-timestamp>"}`.
- **Log file deleted:** Append `{"type": "FILE_DELETED", "file": "<filename>", "ts": "<iso-timestamp>"}`.
- **Log retry:** Append `{"type": "RETRY", "key": "conv-N:FILE.md", "ts": "<iso-timestamp>"}`.
- **Check retry count:** Count RETRY events in EVENTS.jsonl where `key = "conv-N:FILE.md"`.
- **Log human response:** Append `{"type": "HUMAN_RESPONSE", "value": "<value>", "ts": "<iso-timestamp>"}`.
- **Never** append `STATE_TRANSITION` events — the FSM writes all state transitions after your AGENT_DONE.

## Subagents (REVIEWING stage)

| Action | Spawn |
|---|---|
| Phase 1 — Analyze changes | `reviewer` (phase: analyze) |
| Phase 2 — Scout context | `scout` or `quick` with `ROLE: reviewer` |
| Phase 3 — Review | `reviewer` (phase: review) |
| Fix architectural violations | `architect` |
| Fix implementation violations | `builder` |

## Rigor gate

- `lite`: reviewer runs once after the **final** builder conversation, unless any of these apply:
  feedback files exist, risky files were touched, or user preference requires per-conversation review.
  If this is not the final conversation and none of those conditions apply → skip directly to Advance.
- `standard` or `strict`: reviewer runs after **every** builder conversation.

log-phase PHASE_START review

## Phase 0 — Record review start time

Run: `python -c "import time; print(int(time.time()))"` and note the printed integer as `REVIEW_START`.

## Phase 1 — Analyze

log-phase PHASE_START analyze

**Spawn** `reviewer` with `phase: analyze` (see Scout choreography for the NEEDS_CONTEXT contract):
```
phase: analyze
Conv N of [feature] — scan the diff to identify what context you need before reviewing.
Run: git diff HEAD~1 HEAD
Read pathly/plans/[feature]/ARCHITECTURE_PROPOSAL.md if it exists.
List what you need — output NEEDS_CONTEXT block only.

Always include at minimum:
  - type: scout | scope: CLAUDE.md, .claude/rules/, pathly/plans/[feature]/ARCHITECTURE_PROPOSAL.md | question: what architectural rules and coding conventions apply to the changed files?

Output `none` if the default rules scout above is sufficient.
```
If the block is `none`, use only the default rules scout in Phase 2.

log-phase PHASE_DONE analyze

## Phase 2 — Scout

log-phase PHASE_START scout

Run the Scout choreography with `ROLE: reviewer`. Compress all findings into a short summary for Phase 3.

log-phase PHASE_DONE scout

## Phase 3 — Review

log-phase PHASE_START review

**Spawn** `reviewer` with `phase: review` and scout findings injected:
```
phase: review
Review the changes from conversation N of [feature].
Run: git diff HEAD~1 HEAD (or git diff --staged if not yet committed).

## Applicable Rules and Context (from pre-review scout)
[compressed findings]

Check against these rules and pathly/plans/[feature]/ARCHITECTURE_PROPOSAL.md.
If architectural violations found: write pathly/plans/[feature]/feedback/ARCH_FEEDBACK.md
If implementation violations found: write pathly/plans/[feature]/feedback/REVIEW_FAILURES.md
Use the shared feedback protocol formats.
If all clear: report PASS.
```

log-phase PHASE_DONE review

## Feedback routing after reviewer

Apply the Feedback protocol retry-count guard before routing each file (escalate to
HUMAN_QUESTIONS.md when the retry limit is exceeded).

### If `ARCH_FEEDBACK.md` exists

After the retry guard, **spawn** `architect`:
```
Read pathly/plans/[feature]/feedback/ARCH_FEEDBACK.md.
Redesign the affected architecture in pathly/plans/[feature]/ARCHITECTURE_PROPOSAL.md,
or pathly/plans/[feature]/IMPLEMENTATION_PLAN.md for lite plans without ARCHITECTURE_PROPOSAL.md.
If phases need to change, update IMPLEMENTATION_PLAN.md.
Delete pathly/plans/[feature]/feedback/ARCH_FEEDBACK.md when resolved.
Report: what changed in the design.
```
After architect resolves: log file deleted for ARCH_FEEDBACK.md.
Return. Orchestrator determines next state from transition_rules.

### If `REVIEW_FAILURES.md` exists (no ARCH_FEEDBACK.md)

After the retry guard, **spawn** `builder`:
```
Read pathly/plans/[feature]/feedback/REVIEW_FAILURES.md.
Fix each violation listed. Do not change anything outside the listed violations.
Delete pathly/plans/[feature]/feedback/REVIEW_FAILURES.md when all fixed.
```

**Guard — zero-diff stall check** (before re-spawning reviewer):
```bash
git diff HEAD -- . ":(exclude)pathly/plans/"
```
- If command fails: skip check, print `[FSM WARNING] git diff failed — skipping zero-diff check`.
- If output is **empty** (no code changed):
  Write `pathly/plans/[feature]/feedback/HUMAN_QUESTIONS.md`:
  ```
  [STALL] Conversation N — builder and reviewer in zero-diff loop.
  Builder claimed to fix REVIEW_FAILURES.md but no code changed.
  Human decision required: accept as-is, override the rule, or rewrite the conversation scope.
  ```
  Append `{"type": "NO_DIFF_DETECTED", "ts": "<iso-timestamp>"}` to EVENTS.jsonl.
  Stop: "Zero-diff loop detected for Conv N. Escalated to HUMAN_QUESTIONS.md."
- If output is **non-empty**: re-run from Phase 1 — Analyze above.

### If no feedback files — PASS

log-phase PHASE_DONE review

Run the Completion report with `agent: reviewer`, `result: PASS`, using `REVIEW_START` from Phase 0.

## Advance

If not autoFlow — pause:
```
[Stage 3 — Conversation N complete + reviewed]
Reviewer: PASS. Commit your changes now.
Reply 'continue' for the next conversation, or 'stop' to pause here.
```
- Proceed signal: log human response with reply value. Advance.
- Stop signal: log human response "stop". Halt.
- Unrecognised: re-prompt without logging.

If autoFlow: log human response "auto-advance".

Mark Conv N as DONE in `pathly/plans/[feature]/PROGRESS.md`.

**Write-or-delete transition artifacts:**
- If REVIEW_FAILURES.md was written this run: it already exists — keep it.
  If reviewer passed cleanly (no REVIEW_FAILURES.md written): delete `<storage_path>/feedback/REVIEW_FAILURES.md` if it exists.

Return. Orchestrator determines next state from transition_rules.
