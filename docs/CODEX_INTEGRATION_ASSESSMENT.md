# Codex Integration Assessment

_Assessment of [PATHLY_IMPROVEMENT_RECOMMENDATIONS.md](PATHLY_IMPROVEMENT_RECOMMENDATIONS.md) from the perspective of Pathly + Codex integration._

## Bottom Line

The recommendations help Codex use Pathly better, but they do not yet define a full
integration contract between the two systems.

What the plan does well:

- Improves the information Pathly gives to the next agent turn.
- Reduces cold-start behavior by surfacing prior state, consults, and feedback.
- Makes the Pathly workflow more consistent and less dependent on agent memory.

What is still missing for a real Codex integration:

- A defined data contract for what Codex sends to Pathly and what Pathly returns.
- A lifecycle model for Codex sessions, retries, and state handoff.
- A clear tool/auth boundary for how Codex should invoke Pathly actions safely.
- Explicit success/failure semantics for when Codex should continue, pause, or escalate.

## What The Plan Covers

The strongest integration-related items are:

- `1.1 Agent Context Bridging`
- `1.3 meet.md Consultation Auto-Injection`
- `1.4 Feedback TTL and Stale-Feedback Warning`
- `1.5 Cross-Stage Lesson Injection`
- `1.7 Director Correction Path`

These all make Pathly more usable from Codex because they reduce missing context and
make the next step more deterministic.

## What Is Missing

### 1. Codex-to-Pathly contract

The plan does not specify:

- the exact request payload Codex should send
- the exact response payload Pathly should return
- which fields are required versus optional
- how versioning should work when the contract changes

Without that, integration remains implicit rather than interoperable.

### 2. Session continuity rules

The plan improves stage context, but it does not fully define:

- how Codex should resume after interruption
- how to restore an abandoned session
- how to reconcile local state versus live FSM state
- when a session becomes stale enough to require revalidation

### 3. Tooling boundary

The plan assumes the FSM can expose better state, but it does not define:

- which actions are pure reads
- which actions mutate the workflow
- which actions Codex may automate directly
- which actions require human confirmation

That boundary matters if Codex is expected to drive Pathly autonomously.

### 4. Error and retry semantics

The recommendations identify several missing warnings and fallback cases, but they do
not yet define a unified policy for:

- retry limits
- blocked-state escalation
- malformed state recovery
- unrecognized feedback routing

Codex integration will be much easier if those are normalized into one response model.

## Practical Assessment

If the goal is “make Pathly more helpful to Codex,” this plan is directionally good.
If the goal is “define the integration surface between Pathly and Codex,” it is only
partial.

My assessment:

- Good for workflow quality: yes.
- Good for reducing context loss: yes.
- Sufficient as a full integration spec: no.

## Recommended Next Layer

Add a follow-up document that defines:

1. A `CodexSession` payload schema.
2. A `PathlyActionResponse` schema.
3. State transition and retry rules.
4. Human escalation rules.
5. Versioning and compatibility policy.

That would turn the current improvement plan into an actual integration contract.

## Draft Integration Spec

This is a minimal starting contract that would make the Pathly/Codex boundary explicit.

### 1. `CodexSession`

Suggested fields:

- `session_id`: stable identifier for the Codex-driven interaction
- `feature`: Pathly feature name or plan name
- `state`: current FSM state
- `conv`: current conversation number
- `retry_count`: number of retries in the current stage
- `open_feedback`: list of unresolved feedback files
- `recent_events`: last few FSM events
- `recent_consult`: latest consult content if available
- `plan_path`: relative path to the active plan folder
- `schema_version`: contract version for compatibility

Example:

```json
{
  "schema_version": "1.0",
  "session_id": "codex-2026-05-31-001",
  "feature": "chat-mini-terminal",
  "state": "REVIEWING",
  "conv": 3,
  "retry_count": 1,
  "open_feedback": ["HUMAN_QUESTIONS.md"],
  "recent_events": [
    "BUILDING started",
    "VERIFY.md passed",
    "REVIEW requested"
  ],
  "recent_consult": "Use the shared xterm instance and avoid duplicate terminal state.",
  "plan_path": "pathly/plans/chat-mini-terminal"
}
```

### 2. `PathlyActionResponse`

Suggested fields:

- `decision`: `continue`, `block`, `escalate`, or `complete`
- `next_state`: FSM state to enter next
- `instructions`: what Codex should do next
- `stage_brief`: compact summary of current state
- `warnings`: list of surfaced risks or stale artifacts
- `required_files`: files Codex must read or update
- `schema_version`: response contract version

Example:

```json
{
  "schema_version": "1.0",
  "decision": "continue",
  "next_state": "BUILDING",
  "instructions": "Read the stage brief, apply the consult, then update only the planned files.",
  "stage_brief": {
    "state": "REVIEWING",
    "retry_count": 1,
    "open_feedback": ["HUMAN_QUESTIONS.md"],
    "feedback_age_hours": 6
  },
  "warnings": [
    "HUMAN_QUESTIONS.md has been open for 6h"
  ],
  "required_files": [
    "docs/IMPLEMENTATION_PLAN.md",
    "docs/VERIFY.md"
  ]
}
```

### 3. Transition Rules

The contract should define clear behavior for each response type:

- `continue`: Codex may proceed with the next stage.
- `block`: Codex must stop and surface the blocking issue.
- `escalate`: Codex should hand off to a human or a higher-trust path.
- `complete`: The plan is finished and can be closed out.

### 4. Versioning

The schema should be versioned from day one:

- bump `schema_version` only on breaking changes
- allow backward-compatible additions without breaking old clients
- reject or warn on unknown major versions

### 5. Why This Matters

This is the missing layer between “Pathly gives better context” and “Codex can reliably
operate Pathly as a workflow engine.”

Without it, the integration remains a set of useful improvements.
With it, the system becomes an explicit contract.
