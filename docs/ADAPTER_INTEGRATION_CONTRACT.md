# Pathly Adapter Integration Contract

_Assessment of [CODEX_INTEGRATION_ASSESSMENT.md](CODEX_INTEGRATION_ASSESSMENT.md)
plus recommended contract spec. Written 2026-05-31._

---

## Assessment of the Existing Document

### What it gets right

The core diagnosis is correct: `PATHLY_IMPROVEMENT_RECOMMENDATIONS.md` improves
workflow quality but does not define an integration contract. That is a real gap.

The four missing concerns it names are all genuine:

- No defined request/response schema
- No session continuity rules
- No tooling boundary (read vs. mutate vs. human-required)
- No unified error and retry semantics

The proposed `PathlyActionResponse` additions that are genuinely new and useful:

| Field | Why it is good |
|---|---|
| `decision` enum (`continue`, `block`, `escalate`, `complete`) | Cleaner than the current implicit `blocked: true` check |
| `warnings` array | Surfaces feedback TTL and stale-artifact signals |
| `stage_brief` | Reduces agent cold-start — aligns with recommendations 1.1 |
| `schema_version` | Missing today; needed for safe evolution |

### The fundamental error

The `CodexSession` request payload inverts the FSM's ownership model.

The draft proposes Codex sends state back to Pathly:

```json
{
  "session_id": "...",
  "state": "REVIEWING",
  "conv": 3,
  "retry_count": 1,
  "open_feedback": ["HUMAN_QUESTIONS.md"]
}
```

This is wrong for two reasons:

1. **The FSM already owns all of this.** `state`, `conv`, `retry_count`, and
   `open_feedback` are computed from `STATE.json` and `EVENTS.jsonl` by
   `recover_state()`. The FSM is the authority; Codex is a client.

2. **Two sources of truth produce divergence bugs.** If Codex tracks state locally
   and sends it back, the FSM must decide which copy wins. That decision is
   not defined, and the bugs will be silent.

The `session_continuity` concern the document raises is already solved.
`recover_state()` rebuilds FSM state deterministically from `EVENTS.jsonl`.
An interrupted Codex session calls `/next_action` again and gets exactly where
it left off. No session tracking by the caller is needed.

### The correct request shape (already right today)

```json
{ "flow": "team", "topic": "my-feature", "project_root": "/path/to/project" }
```

That is all any adapter — Claude, Codex, Copilot — needs to send. The FSM
reconstructs everything else from disk.

---

## Recommended Integration Contract

### Principle

The integration model is **ask → act → report**:

```
1. Adapter  →  POST /next_action          ask: what should I do?
2. Adapter     executes work natively      act: in its own environment
3. Adapter  →  POST /complete_stage        report: I am done
```

The FSM owns state. Adapters own execution. Neither leaks into the other.

---

### `/next_action` — recommended response shape

Extends the current response with four new fields. All existing fields are
preserved for backwards compatibility.

```json
{
  "schema_version": "1",
  "decision":       "continue",
  "current_state":  "BUILDING",
  "conv":           2,
  "role":           "builder",
  "agent":          "team/build",
  "agent_hint": {
    "role":         "builder",
    "skill_path":   "team/build",
    "instructions": "..."
  },
  "stage_brief": {
    "state":              "BUILDING",
    "conv":               2,
    "retry_count":        0,
    "open_feedback":      [],
    "feedback_age_hours": null,
    "recent_events":      ["BUILDING started", "VERIFY.md passed"],
    "recent_consult":     null,
    "plan_path":          "pathly/plans/my-feature"
  },
  "warnings":      [],
  "storage_path":  "pathly/plans/my-feature",
  "limits":        { "max_files": 8, "max_tool_uses": 120 },
  "menu":          { ... }
}
```

**New fields:**

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Bumped only on breaking changes. Start at `"1"`. |
| `decision` | enum | See decision semantics below. |
| `role` | string | Abstract role from `role_map` — adapter-agnostic. |
| `agent_hint` | object | Replaces `codex_subagent`. See adapter agnosticism doc. |
| `stage_brief` | object | Structured context for agent cold-start reduction. |
| `warnings` | array | Surfaced risks: stale feedback, corrupt state, etc. |

**Deprecated fields (keep for one release, then remove):**

| Field | Replaced by |
|---|---|
| `codex_subagent` | `agent_hint` |

---

### `decision` semantics

Every response from `/next_action` and `/complete_stage` carries a `decision`
field. Adapters must respect it.

| Value | Meaning | Adapter action |
|---|---|---|
| `continue` | FSM is ready; proceed to next stage | Invoke agent, then call `/complete_stage` |
| `block` | A feedback file or human question is open | Surface to user; do not call `/complete_stage` |
| `escalate` | Unrecognized feedback or corrupt state | Halt and surface to user immediately |
| `complete` | Feature reached DONE state | Close out; no further FSM calls needed |

Current implicit logic (`if blocked: true`) maps to `block`. The `escalate`
case is new — it covers `fsm.py` recommendation 2.5 (unrecognized feedback
routing) and 2.6 (corrupt STATE.json recovery).

---

### Tooling boundary

Which actions are safe for automated adapter execution vs. which require human
confirmation:

| Action | Safety | Notes |
|---|---|---|
| `GET /health` | Read-only | Always safe |
| `POST /next_action` | Writes once per conversation | Stamps `conv_start_sha` in `STATE.json` on first call per conversation; subsequent calls within the same conversation are idempotent |
| `POST /complete_stage` | Mutates FSM state | Safe to automate in `continue` decision |
| `POST /complete_stage` with `decision: escalate` | Blocked | Adapter must not call; surface to human |
| Any action on `block` decision | Blocked | Adapter must not call `/complete_stage`; surface to human |

Rule: **adapters may automate `continue`; they must surface `block` and `escalate`.**

---

### Error and retry semantics

Normalized policy for all adapters:

| Scenario | FSM response | Adapter action |
|---|---|---|
| Feedback file present | `decision: block`, `file` field set | Surface file path to user |
| Unrecognized feedback file | `decision: escalate`, `warnings` includes filename | Halt, show warning |
| `STATE.json` corrupt | `decision: escalate`, `warnings: ["state_recovered_from_corrupt"]` | Halt, show warning |
| Gate failed | `decision: block`, gate name in `warnings` | Surface gate failure; do not advance |
| Stage retry limit reached | `decision: escalate` | Halt, prompt for human review |
| Network error calling FSM | No response | Adapter retries up to 3× with exponential backoff, then surfaces error |

---

### Session continuity

No session object is needed. The FSM recovers state deterministically from
`EVENTS.jsonl`. An adapter that was interrupted simply calls `/next_action`
again with the same `{ flow, topic, project_root }` and resumes exactly where
it left off.

If an adapter wants to verify it is resuming a consistent session (e.g. after
a crash), it can compare the `current_state` and `conv` fields in the response
against its last known values. A mismatch means another agent advanced the
pipeline in the interim — the adapter should re-read the stage brief before
continuing.

---

### Versioning policy

- `schema_version` is a string integer (`"1"`, `"2"`, …).
- Additive changes (new optional fields) do not bump the version.
- Breaking changes (removed fields, changed semantics) bump the version.
- Adapters should warn on an unknown `schema_version` but not hard-fail.
- The FSM returns the version it was built against; adapters should log mismatches.

---

## End-to-End Flows

### Shared FSM core (identical for all three adapters)

```
User triggers skill
        │
        ▼
POST /next_action
{ flow: "team", topic: "my-feature", project_root: "/path" }
        │
        ▼
FSM reads STATE.json + EVENTS.jsonl
        │
        ▼
Returns:
{
  schema_version: "1",
  decision:       "continue",
  current_state:  "BUILDING",
  conv:           2,
  role:           "builder",          ← abstract, adapter reads this
  agent_hint: {
    role:         "builder",
    skill_path:   "team/build",       ← Claude-specific, ignored by others
    instructions: "You are a builder. Conv 2 goal: ..."
  },
  stage_brief: {
    retry_count:   0,
    open_feedback: [],
    recent_events: ["PLANNING done", "DESIGNING done"]
  },
  warnings: []
}
```

---

### Claude Code path

```
/pathly build
     │
     ▼
POST /next_action  ──────────────────────────────────────────┐
     │                                                        │
     ▼                                                        │
decision = "continue"                                         │
reads agent_hint.skill_path = "team/build"                    │
     │                                                        │
     ▼                                                        │
Agent(subagent_type="team/build",                             │
      prompt=agent_hint.instructions)                         │
     │                                                        │
     │  [builder agent runs, writes VERIFY.md]               │
     ▼                                                        │
POST /complete_stage                                          │
     │                                                        │
     ▼                                                        │
FSM runs scope_gate + verify_gate                             │
decision = "continue"  →  state advances to REVIEWING         │
     │                                                        │
     └── returns next action ◄────────────────────────────────┘
```

---

### Codex path

```
pathly build       (Codex skill — calls HTTP directly)
     │
     ▼
POST /next_action
     │
     ▼
decision = "continue"
reads agent_hint.role = "builder"          ← no skill_path needed
reads agent_hint.instructions = "..."
     │
     ▼
codex.run(
  agent = "builder",                       ← Codex's own agent registry
  system_prompt = agent_hint.instructions  ← same prompt, native dispatch
)
     │
     │  [Codex builder agent runs natively]
     ▼
POST /complete_stage
     │
     ▼
same FSM logic, same gate checks
decision = "continue"  →  REVIEWING
```

---

### Copilot path

```
@pathly build      (Copilot chat command)
     │
     ▼
POST /next_action
     │
     ▼
decision = "continue"
reads agent_hint.role = "builder"
reads agent_hint.instructions = "..."
     │
     ▼
copilot.agent(
  role    = "builder",
  context = agent_hint.instructions
)
     │
     │  [Copilot agent runs in VS Code context]
     ▼
POST /complete_stage
     │
     ▼
FSM advances → REVIEWING
```

---

### Block path (same for all three adapters)

```
POST /next_action
     │
     ▼
{
  decision: "block",
  current_state: "BUILDING",
  stage_brief: {
    open_feedback:      ["REVIEW_FAILURES.md"],
    feedback_age_hours: 2
  },
  warnings: ["REVIEW_FAILURES.md open for 2h"]
}
     │
     ▼
adapter does NOT call /complete_stage
adapter surfaces to user:
  "Pipeline blocked — REVIEW_FAILURES.md needs resolution"
     │
     ▼
user resolves file
     │
     ▼
/pathly fix  →  POST /complete_stage
               { resolved_files: ["REVIEW_FAILURES.md"] }
     │
     ▼
decision = "continue"  →  resumes normally
```

---

### Before vs. after

**Before:** Claude Code skill inspects `codex_subagent.mode`, makes assumptions
about the runtime, dispatches `Agent()` with Claude-specific logic. Codex and
Copilot adapters receive `agent: "team/build"` — a string only Claude understands
— and have no protocol to follow.

**After:** Every adapter gets `role: "builder"` and `decision: "continue"`. The
FSM contract is identical for all three. Each adapter's only adapter-specific line
is how it invokes its native agent for that role. The FSM does not know or care
which environment executed the work.

The FSM is a traffic light. Adapters are drivers. The light speaks the same
language to all of them.

---

## Relationship to Other Docs

| Document | Role |
|---|---|
| [PATHLY_IMPROVEMENT_RECOMMENDATIONS.md](PATHLY_IMPROVEMENT_RECOMMENDATIONS.md) | Workflow quality improvements — independent of adapter contract |
| [MULTI_ADAPTER_AGNOSTICISM.md](MULTI_ADAPTER_AGNOSTICISM.md) | Gap analysis + code-level changes needed in `fsm_ops.py` and flow YAMLs |
| This document | The contract itself — what adapters receive and must respect |

The Phase 1 changes in `MULTI_ADAPTER_AGNOSTICISM.md` (add `role`, rename
`codex_subagent` → `agent_hint`) are the implementation of sections 2 and 3
of this contract. They are the right starting point.

---

## Codebase Reality Check

Verified against `src/pathly_orchestrator/fsm_ops.py` and
`src/pathly_data/core/flows/*.flow.yaml` on 2026-05-31.

### What is already done (no work needed)

- **All 5 flow YAMLs already have `role_map`** (`team`, `test`, `quick-fix`,
  `debug`, `explore`). The implementation order below does not need to add it.

- **`adapters/codex/SKILL_EXECUTION.md` already defines the HTTP call contract.**
  It documents `pathly-fsm-call next-action`, `complete-stage`, and
  `record-activity`. The gap for Codex is renaming `codex_subagent` → `agent_hint`,
  not building the invocation layer from scratch.

- **`feedback_routing` uses abstract role names in all flows.** No changes needed.

### What the response shapes actually look like today

`next_action` (happy path, `fsm_ops.py` lines 270–279):
```json
{
  "current_state": "BUILDING",
  "conv": 2,
  "agent": "team/build",
  "instructions": "...",
  "codex_subagent": { "pathly_agent": "...", "codex_role": "worker", "mode": "...", "instructions": "..." },
  "storage_path": "pathly/plans/my-feature",
  "limits": {},
  "menu": {}
}
```

`complete_stage` (happy path, `fsm_ops.py` lines 437–444) — **different shape**:
```json
{
  "next_state": "REVIEWING",
  "agent": "team/review",
  "instructions": "...",
  "codex_subagent": { ... },
  "limits": {},
  "menu": {}
}
```

Note: `complete_stage` returns `next_state` (not `current_state`), and omits
`conv` and `storage_path`. The recommended response shape must account for this
difference — both endpoints need to be aligned when the new fields are added.

### `codex_subagent` call sites — actual count

5 call sites in `fsm_ops.py` (not 3):
- line 260 — feedback branch in `next_action`
- line 275 — happy path in `next_action`
- line 321 — feedback branch in `complete_stage`
- line 391 — gate failure in `complete_stage`
- line 441 — happy path in `complete_stage`

1 reference in `adapters/codex/SKILL_EXECUTION.md` (reads `codex_subagent.codex_role`
and `codex_subagent.instructions`). This file must be updated when the key is renamed.

Zero skill `.md` files in `core/skills/` reference `codex_subagent`.

---

## Implementation Order

1. **`fsm_ops.py`** — add `schema_version`, `decision`, `role`, `agent_hint`,
   `stage_brief`, `warnings` to both `next_action` and `complete_stage` responses.
   Align `complete_stage` shape to include `current_state`, `conv`, `storage_path`.
   Rename `_codex_subagent_hint` → `_agent_hint`, update all 5 call sites.
   Deprecate `codex_subagent` key. (~60 lines)

2. **`adapters/codex/SKILL_EXECUTION.md`** — update 1 reference: replace
   `codex_subagent.codex_role` / `codex_subagent.instructions` with
   `agent_hint.role` / `agent_hint.instructions`.

3. **Adapter `_meta/` files** — add `invocation` blocks to codex and copilot
   skill YAMLs so the install layer knows to use `agent_hint.role` rather than
   `agent_hint.skill_path`.

4. **Claude Code skills** — no `.md` files in `core/skills/` need updating.
   The `SKILL_EXECUTION.md` change in step 2 covers the Codex surface.
## Line-By-Line Critique

### 1. Response shape consistency

The document is mostly consistent, but `next_action` and `complete_stage` still
show slightly different payload shapes in the "Codebase Reality Check" section.
The contract should either:

- explicitly document that difference as intentional, or
- normalize both endpoints to the same top-level shape.

Right now the text says the contract is unified, but the examples still show
asymmetry.

### 2. `decision` semantics on `complete_stage`

The document says every response from `/next_action` and `/complete_stage`
carries a `decision` field. That is good in principle, but it needs one extra rule:

- If `complete_stage` returns `block` or `escalate`, what exactly should the adapter
  do after the stage has already been reported?

That case is possible if the FSM re-evaluates gates during completion. The doc
should say whether `complete_stage` can ever be called speculatively or only after
the agent work is already done.

### 3. `warnings` lacks a strict schema

`warnings` is useful, but the doc leaves its shape too loose.

Questions the contract should answer:

- Are warnings plain strings only?
- Can they carry codes, severity, or file paths?
- Should adapters parse them or just display them?

Without a stricter format, adapters will likely treat warnings inconsistently.

### 4. `stage_brief` may grow into an unbounded blob

`stage_brief` is the right place for cold-start context, but it is also a dumping
ground risk.

The contract should bound it more explicitly:

- max number of `recent_events`
- max length of `recent_consult`
- whether `open_feedback` is truncated

Without limits, this field can become large enough to hurt prompt quality.

### 5. `schema_version` policy is incomplete

The versioning policy is reasonable, but it needs one more rule:

- What should an adapter do on a higher major version it does not understand?

The doc says warn, but if the version is incompatible, a warning may not be enough.
For a breaking change, the adapter should probably fail closed and surface the issue.

### 6. Tooling boundary is correct but incomplete

The safety table is useful, but it omits one important case:

- What happens if `/next_action` is called repeatedly before `/complete_stage`?

The doc implies idempotence inside a conversation, but it should say whether repeated
calls are safe, and whether they re-read the same stage or re-evaluate the current
state.

### 7. `block` vs. `escalate` needs a sharper edge

This is the most important behavioral distinction in the document.

`block` means:

- the pipeline is paused
- a human or file resolution is required

`escalate` means:

- something is structurally wrong
- the adapter should stop and surface the problem immediately

That is good, but the document should define what kinds of issues belong in each
bucket. For example:

- stale feedback probably belongs in `block`
- corrupt state belongs in `escalate`
- unknown feedback file probably belongs in `escalate`

That mapping should be explicit so adapters do not improvise.

### 8. Session continuity is stated correctly

This section is one of the strongest parts of the contract.

The only caveat is that it assumes filesystem state is authoritative and available.
That is fine for local Pathly, but if the architecture ever moves to remote state or
multi-host orchestration, the contract will need a new persistence model.

### 9. The Codex path example is still conceptual

The Codex example is helpful, but `codex.run(...)` is not yet a concrete API
commitment. The document should avoid implying that this exact call exists unless it
is backed by a real adapter implementation.

As written, it is fine as pseudocode, but it should be labeled more clearly as such.

### 10. The codebase reality check is the most trustworthy section

This section is doing important work because it separates design intent from actual
repo state.

The main thing to keep watching is drift:

- if the FSM response shape changes again, the contract will need to be updated
- if `SKILL_EXECUTION.md` changes, the Codex surface should be rechecked
- if adapter `_meta/` files start carrying real invocation logic, the rollout order may
  need to change

### Overall critique

The document is solid and practical, but it is still slightly ahead of the
implementation in a few places.

Best parts:

- clear ownership split
- explicit decision model
- provider-agnostic role abstraction
- good backward-compatibility thinking

Main risks:

- `stage_brief` becomes too open-ended
- `warnings` stays underspecified
- `decision` semantics are not fully pinned down for edge cases
- the Codex example could be mistaken for a real API rather than an example

Net: this is a good contract draft, but it needs tighter edge-case rules before it
can be treated as a stable external interface.
