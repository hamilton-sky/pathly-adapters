# team/review

Stage 3b — Review. Invoked by the `team` orchestrator when FSM state is REVIEWING.
Runs reviewer for the current conversation, handles feedback loops, then advances.

Parse `$ARGUMENTS`: `FEATURE`, `rigor`, `autoFlow`. Conv N is the most recent BUILDING work item —
the board task that was just built and claimed for review.

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

Events are logged to the central DB via `pathly_orchestrator.eventlog.append_event`.
Every event must include `"ts": "<iso-timestamp>"` using the current ISO-8601 UTC time.
State snapshots are written to `<feature_path>/STATE.json` by the FSM server (the skill never writes STATE.json directly).

- **Log event:** `python3 -c "from pathly_orchestrator.eventlog import append_event; append_event('<feature_path>', {'type': 'FILE_CREATED', 'file': '<filename>', 'ts': '<iso-timestamp>'})"`
- **Log retry:** Same pattern with `{'type': 'RETRY', 'key': 'conv-N:FILE.md', 'ts': '<iso-timestamp>'}`.
- **Check retry count:** `python3 -c "from pathly_orchestrator.db import get_db; c=get_db(); print(c.execute(\"SELECT COUNT(*) FROM fsm_events WHERE feature=? AND event_type='RETRY' AND json_extract(payload,'$.key')=?\",('<feature>','conv-N:FILE.md')).fetchone()[0])"`
- **Log human response:** Same pattern with `{'type': 'HUMAN_RESPONSE', 'value': '<value>', 'ts': '<iso-timestamp>'}`.
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
Read <feature_path>/ARCHITECTURE_PROPOSAL.md if it exists.
List what you need — output NEEDS_CONTEXT block only.

Always include at minimum:
  - type: scout | scope: CLAUDE.md, .claude/rules/, <feature_path>/ARCHITECTURE_PROPOSAL.md | question: what architectural rules and coding conventions apply to the changed files?

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

If the task being reviewed has `context_refs`, for each `{artifact, anchor}` call:
  GET /comms/artifacts/section?scope=$SCOPE&artifact=<artifact>&anchor=<anchor>
and read the returned `text` field (the full advisory spec — edge cases / happy flow
for the phase the builder implemented). The `summary` is a pointer, not the spec —
read `text`. These are the same refs the builder hydrated; review against the same spec.

Check against these rules and <feature_path>/ARCHITECTURE_PROPOSAL.md. Classify each
violation by ROOT CAUSE and write it into the matching file (see Feedback protocol —
Root-cause classification for the full tag ⇄ file ⇄ role table):
- Requirement/scope gap: <feature_path>/feedback/REQUIREMENT_GAP.md
- Plan/phasing/task-DAG problem: <feature_path>/feedback/PLAN_FEEDBACK.md
- Architectural violation: <feature_path>/feedback/ARCH_FEEDBACK.md
- UI/UX/design-system violation: <feature_path>/feedback/DESIGN_FEEDBACK.md
- Implementation defect (default): <feature_path>/feedback/REVIEW_FAILURES.md
Use the shared feedback protocol formats. One review with violations from two root causes
writes TWO files, not one file with two tags.
If all clear: report PASS.
```

log-phase PHASE_DONE review

## Feedback routing after reviewer

Apply the Feedback protocol retry-count guard before routing each file (escalate to
HUMAN_QUESTIONS.md when the retry limit is exceeded). Route the HIGHEST-PRIORITY open
file first (see Feedback protocol — priority order): `REQUIREMENT_GAP.md` >
`PLAN_FEEDBACK.md` > `ARCH_FEEDBACK.md` > `DESIGN_FEEDBACK.md` > `REVIEW_FAILURES.md`.

### If `REQUIREMENT_GAP.md` exists

After the retry guard, **spawn** `po`:
```
Read <feature_path>/feedback/REQUIREMENT_GAP.md.
Correct <feature_path>/USER_STORIES.md so the acceptance criteria/scope match the failure.
If the correction implies code changes, append a short [IMPL] section to
<feature_path>/feedback/REVIEW_FAILURES.md naming the change.
Delete <feature_path>/feedback/REQUIREMENT_GAP.md when resolved.
Report: what changed in the requirement.
```
After po resolves: log file deleted for REQUIREMENT_GAP.md.
Return. Orchestrator determines next state from transition_rules.

### If `PLAN_FEEDBACK.md` exists (no `REQUIREMENT_GAP.md`)

After the retry guard, **spawn** `planner`:
```
Read <feature_path>/feedback/PLAN_FEEDBACK.md.
Correct the phasing/task DAG in <feature_path>/IMPLEMENTATION_PLAN.md.
If the correction implies code changes, append a short [IMPL] section to
<feature_path>/feedback/REVIEW_FAILURES.md naming the change.
Delete <feature_path>/feedback/PLAN_FEEDBACK.md when resolved.
Report: what changed in the plan.
```
After planner resolves: log file deleted for PLAN_FEEDBACK.md.
Return. Orchestrator determines next state from transition_rules.

### If `ARCH_FEEDBACK.md` exists (no `REQUIREMENT_GAP.md`/`PLAN_FEEDBACK.md`)

After the retry guard, **spawn** `architect`:
```
Read <feature_path>/feedback/ARCH_FEEDBACK.md.
Redesign the affected architecture in <feature_path>/ARCHITECTURE_PROPOSAL.md,
or <feature_path>/IMPLEMENTATION_PLAN.md for lite plans without ARCHITECTURE_PROPOSAL.md.
If phases need to change, update IMPLEMENTATION_PLAN.md.
Delete <feature_path>/feedback/ARCH_FEEDBACK.md when resolved.
Report: what changed in the design.
```
After architect resolves: log file deleted for ARCH_FEEDBACK.md.
Return. Orchestrator determines next state from transition_rules.

### If `DESIGN_FEEDBACK.md` exists (no higher-priority file above)

After the retry guard, **spawn** `designer`:
```
Read <feature_path>/feedback/DESIGN_FEEDBACK.md.
Correct the UI/UX design system in <feature_path>/DESIGN.md.
If the correction implies code changes, append a short [IMPL] section to
<feature_path>/feedback/REVIEW_FAILURES.md naming the change.
Delete <feature_path>/feedback/DESIGN_FEEDBACK.md when resolved.
Report: what changed in the design system.
```
After designer resolves: log file deleted for DESIGN_FEEDBACK.md.
Return. Orchestrator determines next state from transition_rules.

### If `REVIEW_FAILURES.md` exists (no root-cause file above)

After the retry guard, **spawn** `builder`:
```
Read <feature_path>/feedback/REVIEW_FAILURES.md.
Fix each violation listed. Do not change anything outside the listed violations.
Delete <feature_path>/feedback/REVIEW_FAILURES.md when all fixed.
```

**Guard — zero-diff stall check** (before re-spawning reviewer):
```bash
git diff HEAD -- . ":(exclude)pathly/features/"
```
- If command fails: skip check, print `[FSM WARNING] git diff failed — skipping zero-diff check`.
- If output is **empty** (no code changed):
  Write `<feature_path>/feedback/HUMAN_QUESTIONS.md`:
  ```
  [STALL] Conversation N — builder and reviewer in zero-diff loop.
  Builder claimed to fix REVIEW_FAILURES.md but no code changed.
  Human decision required: accept as-is, override the rule, or rewrite the conversation scope.
  ```
  Log `{"type": "NO_DIFF_DETECTED", "ts": "<iso-timestamp>"}` via `python3 -c "from pathly_orchestrator.eventlog import append_event; append_event('<feature_path>', {'type':'NO_DIFF_DETECTED','ts':'<iso-timestamp>'})"`.
  Stop: "Zero-diff loop detected for Conv N. Escalated to HUMAN_QUESTIONS.md."
- If output is **non-empty**: re-run from Phase 1 — Analyze above.

### If no feedback files — PASS

**Write `<feature_path>/REVIEW.md`** with this exact content (first line must be exact):
```
RESULT: PASS
Reviewed: conversation N — <one-sentence summary of what was reviewed and the verdict>
```
The first line **must** be `RESULT: PASS` verbatim (case-sensitive, no leading whitespace). This is the
review-pass artifact the `REVIEWING → TESTING` gate (`verify_gate`) checks — without it the flow cannot
advance to testing. (Mirror of the builder's `VERIFY.md`.)

Then run the Completion report with `agent: reviewer`, `result: PASS`, using `REVIEW_START` from Phase 0.

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

The board task's status is already managed (completed in BUILDING, re-opened on review failure) —
there is no per-conversation progress file to mark.

**Write-or-delete transition artifacts:**
- If reviewer PASSED (no REVIEW_FAILURES.md written this run): `REVIEW.md` (RESULT: PASS) was written above — keep it,
  and delete `<storage_path>/feedback/REVIEW_FAILURES.md` if it exists.
- If reviewer FAILED (REVIEW_FAILURES.md written this run): keep it, and **delete any stale `<feature_path>/REVIEW.md`**
  from a previous pass — a failing review must never leave a passing artifact that would wave the flow through the gate.

Return. Orchestrator determines next state from transition_rules.
