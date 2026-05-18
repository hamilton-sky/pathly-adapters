# CONTEXTUAL_MENU_UX.md — mcp-fsm-driver

_Design reference for the state-aware menu displayed by team / debug / explore
skills before every agent execution. Three scenarios with full ASCII renders._

---

## Design rationale

The current orchestrator is silent — it routes internally and the user has no
visibility into what state the machine is in or what is happening next. The menu
fixes this. Every time the skill calls `next_action` or `complete_stage`, it
surfaces the result as a human-readable panel before executing, giving the user
a chance to redirect, pause, or inspect.

**Principles:**
- Show pipeline progress as a single line so users can see where they are at a
  glance without reading STATE.json.
- Surface blocking information (feedback files, decide questions) prominently —
  never hide why the machine is stopped.
- Options are always numbered 1–4 and contextual — they change based on state,
  not a fixed menu everywhere.
- Consistent visual structure: fixed-width divider, same header format, same
  indentation. Matches the `start.md` box-drawing style already in the codebase.

---

## Scenario 1 — Team flow, BUILDING state (happy path, manual mode)

**Trigger:** User runs `/pathly team checkout-feature`.  
`next_action` returns: `{current_state: "BUILDING", agent: "builder", conv: 2}`.  
No feedback blocking. No decide question.

```
─────────────────────────────────────────────────────────
  Pathly  ·  team  ·  checkout-feature
  State : BUILDING      Conv : 2      Mode : manual
  Agent : builder
─────────────────────────────────────────────────────────
  Pipeline:
    STORMING ✓  PLANNING ✓  [ BUILDING ]  reviewing  testing  retro
─────────────────────────────────────────────────────────
  Builder will implement IMPLEMENTATION_PLAN.md.
  After this stage the reviewer runs automatically.
  Commit is triggered on BUILDING → REVIEWING transition.
─────────────────────────────────────────────────────────
  Options:
    [1] Proceed   — run builder now
    [2] Pause     — save state and stop
    [3] Status    — print STATE.json + last 10 events
    [4] Switch    — jump to /debug or /explore instead
─────────────────────────────────────────────────────────
  Reply [1–4] or press Enter to proceed:
```

**Implementation notes:**
- Pipeline line is built from `flow["states"]` in order. Current state is
  bracketed `[ ]`. Completed states get `✓` (read from STATE.json history or
  EVENTS.jsonl `STATE_TRANSITION` entries). Future states are lowercase.
- Guidance line is looked up from a static table in the skill file keyed by
  state name. The commit note is included only when `transition_actions` has an
  entry for `BUILDING->REVIEWING` (read from flow YAML).
- Default action on Enter = `[1] Proceed`. Skill never auto-proceeds without
  showing this panel first.

---

## Scenario 2 — Debug flow, FIXING state, blocked by REVIEW_FAILURES

**Trigger:** User runs `/pathly debug null-ptr-crash`.  
`next_action` returns: `{blocked: true, target_agent: "builder",
file: "REVIEW_FAILURES.md"}`.  
The reviewer left failures — builder must resolve before VERIFYING.

```
─────────────────────────────────────────────────────────
  Pathly  ·  debug  ·  null-ptr-crash
  State : FIXING        Conv : 3      Mode : auto-flow
  Agent : builder  [ BLOCKED — open feedback ]
─────────────────────────────────────────────────────────
  Pipeline:
    INVESTIGATING ✓  REPRODUCING ✓  ROOT_CAUSE_FOUND ✓
    [ FIXING ]  verifying  done
─────────────────────────────────────────────────────────
  ! Open feedback file: REVIEW_FAILURES.md
    Reviewer found issues that must be addressed
    before the pipeline can advance to VERIFYING.
─────────────────────────────────────────────────────────
  Options:
    [1] Resolve   — run builder on REVIEW_FAILURES.md now
    [2] View      — print REVIEW_FAILURES.md contents here
    [3] Escalate  — write HUMAN_QUESTIONS.md and halt for
                    you to decide (builder will not run)
    [4] Pause     — save state and stop session
─────────────────────────────────────────────────────────
  Reply [1–4]:
```

**Implementation notes:**
- When `blocked=true` the agent label gets `[ BLOCKED — open feedback ]`.
  The option set changes: `[1]` becomes Resolve (not Proceed), `[2]` becomes
  View so the user can inspect before deciding, `[3]` becomes Escalate.
- Escalate writes `HUMAN_QUESTIONS.md` with a standard escalation note:
  `"Builder has seen REVIEW_FAILURES <N> times. Manual decision required."`.
  After writing, the skill halts and prints the file contents.
- After [1] Resolve: builder runs, skill deletes `REVIEW_FAILURES.md` from
  `feedback/`, then calls `complete_stage` again. One file at a time.
- `[4] Pause` is always available regardless of blocked state — the user can
  always stop cleanly.

---

## Scenario 3 — Team flow, REVIEWING state, Level 3 decide (two-call protocol)

**Trigger:** User runs `/pathly team checkout-feature` after BUILDING completed.  
`complete_stage` evaluates transition rules. L1 and L2 do not match.  
L3 fires — returns `{decide: true, question: "...", context: "...", options: {...}}`.

**Panel A — FSM surfaces the decide question to the LLM:**

```
─────────────────────────────────────────────────────────
  Pathly  ·  team  ·  checkout-feature
  State : REVIEWING     Conv : 3      Mode : manual
  Agent : reviewer  [ ROUTING DECISION NEEDED ]
─────────────────────────────────────────────────────────
  Pipeline:
    STORMING ✓  PLANNING ✓  BUILDING ✓  [ REVIEWING ]  testing  retro
─────────────────────────────────────────────────────────
  ! The FSM cannot determine the next stage automatically.
    A constrained routing decision is required.

  Question:
    "What type of fix does this review require?"

  Context (REVIEW_FAILURES.md):
  ┌──────────────────────────────────────────────────┐
  │ AUTH-001: Token expiry not handled in middleware.│
  │ Severity: HIGH. Affects all authenticated        │
  │ endpoints. Recommend architectural change to     │
  │ the session layer, not a targeted patch.         │
  └──────────────────────────────────────────────────┘

  Options — reply with exactly one key:
    refactor      → loop back to BUILDING for targeted fix
    architecture  → escalate to ARCH_REVIEW stage
    minor         → treat as minor, advance to TESTING
─────────────────────────────────────────────────────────
  Your choice [refactor / architecture / minor]:
```

**Panel B — After user / LLM replies "architecture":**

The skill calls `complete_stage(..., decision="architecture")`.  
`complete_stage` maps `"architecture"` → `"ARCH_REVIEW"`, writes STATE.json,
appends `DECIDE_ROUTING` event, returns next agent.

```
─────────────────────────────────────────────────────────
  Pathly  ·  team  ·  checkout-feature
  Decision recorded: architecture → ARCH_REVIEW
─────────────────────────────────────────────────────────
  Pipeline:
    STORMING ✓  PLANNING ✓  BUILDING ✓  REVIEWING ✓
    [ ARCH_REVIEW ]  building  testing  retro
─────────────────────────────────────────────────────────
  Architect will review the session layer design.
  Builder resumes after architect feedback is resolved.
─────────────────────────────────────────────────────────
  Options:
    [1] Proceed   — run architect now
    [2] Pause     — save state and stop
    [3] Status    — print STATE.json + last 10 events
    [4] Switch    — jump to /debug or /explore instead
─────────────────────────────────────────────────────────
  Reply [1–4] or press Enter to proceed:
```

**Implementation notes:**
- Panel A is rendered when `complete_stage` returns `{decide: true, ...}`.
  The skill prints the panel, waits for a single-word reply, then calls
  `complete_stage` again with `decision=<reply>`.
- The context box (inner border `┌─┐`) is shown when `context` is non-null.
  If `context` is null (file missing), omit the box and add a note:
  `"Context file not found — choose based on option labels alone."`.
- Panel B renders the updated pipeline immediately so the user can see the
  decision took effect before the agent runs.
- Invalid reply (not a key in `options`): skill prompts once more, then falls
  back to calling `complete_stage(..., decision=null)` which uses `default`.

---

## Recommendation: where each panel is rendered

| Skill / command | When to show the panel |
|---|---|
| `team`, `debug`, `explore` | After every `next_action` call, before running agent |
| `go` | After recovering state, before routing to the correct skill |
| `pause` | After writing PAUSED status — show as the final output (no options, just state) |
| `end` | Before running retro — show current state and conv count as confirmation |
| `verify-state` | Show full state table (all stages + DONE/TODO) not the action menu |

The panel is **not** shown inside sub-agents (builder, reviewer, planner etc.) —
only at the skill level, before the skill spawns or routes to an agent.

---

## Static guidance table (implemented in each skill file)

| Flow | State | Guidance line |
|---|---|---|
| team | STORMING | Architect discovers scope and risks. No implementation yet. |
| team | PLANNING | Planner drafts IMPLEMENTATION_PLAN.md. Builder waits for it. |
| team | BUILDING | Builder implements the plan. Reviewer runs automatically after. |
| team | REVIEWING | Reviewer checks builder output. REVIEW_FAILURES.md blocks advance. |
| team | TESTING | Tester validates. TEST_FAILURES.md loops back to builder. |
| team | RETRO | Final retrospective. Topic closes when complete. |
| team | DONE | Topic complete. Artifacts archived. |
| debug | INVESTIGATING | Scout traces the symptom. SYMPTOM.md must exist first. |
| debug | REPRODUCING | Tester confirms a repro case. REPRO.md written here. |
| debug | ROOT_CAUSE_FOUND | Builder writes ROOT_CAUSE.md — no code changes yet. |
| debug | FIXING | Builder implements the fix. Commit on FIXING→VERIFYING. |
| debug | VERIFYING | Reviewer confirms fix is correct and tests pass. |
| debug | DONE | Bug closed. Artifacts archived. |
| explore | FRAMING | Explorer scopes the question. EXPLORE.md confirmed before tracing. |
| explore | ANALYZING | Explorer maps the relevant layers and dependencies. |
| explore | TRACING | Scouts read code. Direct reads forbidden — scouts only. |
| explore | CONCLUDING | Explorer writes CONCLUSIONS.md with recommendation. |
| explore | DONE | Exploration closed. |
