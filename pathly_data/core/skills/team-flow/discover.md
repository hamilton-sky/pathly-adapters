# team-flow/discover

Stage 0 — Discovery Path. Invoked by the `team-flow` orchestrator when FSM state is
IDLE / PO_DISCUSSING / EXPLORING / STORMING.

Parse `$ARGUMENTS`: first non-keyword word = `FEATURE`, `lite|standard|strict` = `rigor`,
`fast` = `autoFlow = true`.

## FSM operations

**Transition state to X:** Write `plans/<feature>/STATE.json` `{"current": "X"}`.
Append `{"type": "STATE_TRANSITION", "to": "X"}` to `plans/<feature>/EVENTS.jsonl`.

**Log human response:** Append `{"type": "HUMAN_RESPONSE", "value": "<value>"}` to EVENTS.jsonl.

## Subagents used in this stage

| Action | Spawn |
|---|---|
| PO discussion | `po` |
| Codebase exploration | `scout` |
| Technical storm | `architect` |
| Planning (path 5 only) | `planner` |

## Discovery menu

Print exactly this and wait for user input:

```
═══════════════════════════════════════════
  [feature-name] — Choose discovery path
═══════════════════════════════════════════

  [1] Quick storm
      Architect explores the idea now (~10 min)
      Best for: rough idea that needs shaping,
                technical unknowns to surface

  [2] Skip discovery
      Go straight to planning
      Best for: you already know what to build,
                small or familiar feature

  [3] Import PRD
      You have a requirements file ready
      Best for: BMAD output, hand-written PRD,
                any structured requirements doc

  [4] Explore first
      Explorer maps the codebase, then you decide
      Best for: unfamiliar code, "where does this go?",
                checking if something already exists

  [5] Full discovery
      PO discussion → Architect storm → Planner
      Best for: new features, unclear requirements,
                high stakeholder alignment needed

Reply with 1, 2, 3, 4, or 5:
```

---

## Path 1 — Quick storm

Transition state → STORMING.
Route to `team-flow/plan [FEATURE] [rigor] [autoFlow] storm`.

---

## Path 2 — Skip discovery

Print: `Skipping discovery. Starting planning...`
Transition state → PLANNING.
Route to `team-flow/plan [FEATURE] [rigor] [autoFlow]`.

---

## Path 3 — Import PRD

Ask:
```
Path to your PRD file? (e.g. docs/feature-prd.md)
```
Wait for path. Route to `prd-import [FEATURE] [path] [rigor]`.

After import returns, print:
```
PRD imported. Plan files ready in plans/[feature]/

The PRD covers your requirements. How do you want to proceed?
  [A] Skip to build — PRD is sufficient, go straight to implementation
  [B] PO gap-review — PO advisor reads the PRD and asks only about gaps
  [C] Architect storm — go to technical design before building

Reply with A, B, or C:
```
Wait for reply.

**A** → Transition state → BUILDING.
Print: `Skipping discovery. Starting implementation from PRD plan.`
Route back to `team-flow [FEATURE] [rigor] [autoFlow]`.

**B** → Transition state → PO_DISCUSSING. **Spawn** `po`:
```
Run PO mode for the feature: [feature name]
A PRD has already been imported. Read plans/[feature]/USER_STORIES.md as the baseline.
Focus only on gaps: missing edge cases, unclear acceptance criteria, unstated constraints.
The user will type "stop notes" when satisfied to write plans/[feature]/PO_NOTES.md.
Remind them of this at the start.
```
After PO completes: transition state → BUILDING.
Route back to `team-flow [FEATURE] [rigor] [autoFlow]`.

**C** → Transition state → STORMING.
Print: `Plan files ready. Starting architect storm for technical design.`
Route to `team-flow/plan [FEATURE] [rigor] [autoFlow] storm`.

---

## Path 4 — Explore first

Transition state → EXPLORING. **Spawn** `scout`:
```
Explore the codebase for the feature: [feature name]
Map where this functionality would live — layers, existing files, dependencies, anything already present.
Output a short summary: relevant files found, likely touch points, open questions.
Do not plan or implement — explore only.
```

After scout completes, print:
```
[Explore complete] Scout mapped the codebase.

What next?
  [A] Plan — go to planning (planner uses scout findings as context)
  [B] Implement directly — nano mode, no plan (best if explore showed ≤ 2 files to touch)
  [C] Stop here — I'll review the explore output first

Reply with A, B, or C:
```

**A** → Store scout output as `exploreContext`. Transition state → PLANNING.
Route to `team-flow/plan [FEATURE] [rigor] [autoFlow]` (pass explore context in args or STATE.json).

**B** → Route back to `team-flow [FEATURE] nano`. (Orchestrator will run nano mode.)

**C** → Print: `Pipeline paused after explore. Resume with team-flow [feature] build when ready.`
Transition state → IDLE. Stop.

---

## Path 5 — Full discovery (PO → Storm → Plan)

**Phase 1 — PO Discussion:**
Transition state → PO_DISCUSSING.

**Spawn** `po`:
```
Run PO mode for the feature: [feature name]
Probe requirements interactively — problem, users, MVP scope, out-of-scope, constraints, edge cases.
The user will type "stop notes" when satisfied to write plans/[feature]/PO_NOTES.md.
Remind them of this at the start.
```
After PO completes: transition state → PO_PAUSED.

If not autoFlow — pause:
```
[Phase 1 — PO Discussion complete]
Requirements captured in plans/[feature]/PO_NOTES.md.
Ready for architect storm? Reply 'yes' to continue, or 'no' to stop here.
```
On 'no': log human response "stop". Write STATE.json with current state. Halt.
On 'yes': log human response with reply value. Advance.
If autoFlow: log human response "auto-advance".

**Phase 2 — Architect Storm:**
Transition state → STORMING.

**Spawn** `architect`:
```
Route to storm for the feature: [feature name]
Context from PO discussion is in plans/[feature]/PO_NOTES.md — read it first.
Explore the idea technically — layers, dependencies, design decisions.
When the user is satisfied, they will type /stop plan to write STORM_SEED.md.
Remind them of this at the start.
```

If not autoFlow — pause:
```
[Phase 2 — Architect Storm complete]
STORM_SEED.md written. Ready to plan? Reply 'yes' to continue, or 'no' to stop here.
```
On 'no': halt.

**Phase 3 — Hand off to plan:**
Transition state → PLANNING.
Route to `team-flow/plan [FEATURE] [rigor] [autoFlow]`.
