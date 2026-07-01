---

---
# team/discover

Stage 0 — Discovery Path. Invoked by the `team` orchestrator when FSM state is
IDLE / PO_DISCUSSING / EXPLORING / STORMING.

Parse `$ARGUMENTS`: first non-keyword word = `FEATURE`, `lite|standard|strict` = `rigor`,
`fast` = `autoFlow = true`.

## FSM operations

**Transition state to X:** Call `pathly-fsm-call complete-stage --flow team --topic <feature> --project-root <project_root>`.
The FSM computes the next state from transition_rules and persists it to the DB and STATE.json mirror.

Every logged event must include `"ts": "<iso-timestamp>"` using the current ISO-8601 UTC time.

**Log human response:** `python3 -c "from pathly_orchestrator.eventlog import append_event; append_event('<feature_path>', {'type':'HUMAN_RESPONSE','value':'<value>','ts':'<iso-timestamp>'})"`.


## Subagents used in this stage

| Action | Route / Spawn |
|---|---|
| PO discussion | `po` |
| Codebase exploration | `explore` skill (explorer + scout agent internally) |
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

Call `pathly-fsm-call complete-stage --flow team --topic [FEATURE] --project-root <project_root>`.
Route to `team/plan [FEATURE] [rigor] [autoFlow] storm`.

---

## Path 2 — Skip discovery

Print: `Skipping discovery. Starting planning...`
Call `pathly-fsm-call complete-stage --flow team --topic [FEATURE] --project-root <project_root>`.
Route to `team/plan [FEATURE] [rigor] [autoFlow]`.

---

## Path 3 — Import PRD

Ask:
```
Path to your PRD file? (e.g. docs/feature-prd.md)
```
Wait for path. Route to `prd-import [FEATURE] [path] [rigor]`.

After import returns, print:
```
PRD imported. Plan files ready in <feature_path>/

The PRD covers your requirements. How do you want to proceed?
  [A] Skip to build — PRD is sufficient, go straight to implementation
  [B] PO gap-review — PO advisor reads the PRD and asks only about gaps
  [C] Architect storm — go to technical design before building

Reply with A, B, or C:
```
Wait for reply.

**A** → Call `pathly-fsm-call complete-stage --flow team --topic [FEATURE] --project-root <project_root>`.
Print: `Skipping discovery. Starting implementation from PRD plan.`
Route back to `team [FEATURE] [rigor] [autoFlow]`.

**B** → Call `pathly-fsm-call complete-stage --flow team --topic [FEATURE] --project-root <project_root>`. **Spawn** `po`:
```
Run PO mode for the feature: [feature name]
A PRD has already been imported. Read <feature_path>/USER_STORIES.md as the baseline.
Focus only on gaps: missing edge cases, unclear acceptance criteria, unstated constraints.
The user will type "stop notes" when satisfied to write <feature_path>/PO_NOTES.md.
Remind them of this at the start.
```
After PO completes: call `pathly-fsm-call complete-stage --flow team --topic [FEATURE] --project-root <project_root>`.
Route back to `team [FEATURE] [rigor] [autoFlow]`.

**C** → Call `pathly-fsm-call complete-stage --flow team --topic [FEATURE] --project-root <project_root>`.
Print: `Plan files ready. Starting architect storm for technical design.`
Route to `team/plan [FEATURE] [rigor] [autoFlow] storm`.

---

## Path 4 — Explore first

Call `pathly-fsm-call complete-stage --flow team --topic [FEATURE] --project-root <project_root>`.

Route to `explore [FEATURE]`.

The explore skill frames the question, runs the explorer + scout agent pipeline, and
writes `pathly/explorations/[FEATURE]/CONCLUSIONS.md`.

After the explore skill returns control (user chose "Done" or "Graduate"), read
`pathly/explorations/[FEATURE]/CONCLUSIONS.md` and print:

```
[Explore complete] Findings in pathly/explorations/[FEATURE]/CONCLUSIONS.md.

What next?
  [A] Plan — go to planning (planner gets CONCLUSIONS.md as context)
  [B] Implement directly — nano mode, no plan (best if explore showed ≤ 2 files to touch)
  [C] Stop here — I'll review the explore output first

Reply with A, B, or C:
```

**A** → Call `pathly-fsm-call complete-stage --flow team --topic [FEATURE] --project-root <project_root>`.
Route to `team/plan [FEATURE] [rigor] [autoFlow]`.
(`team/plan` reads `pathly/explorations/[FEATURE]/CONCLUSIONS.md` automatically — no extra injection needed.)

**B** → Route back to `team [FEATURE] nano`. (Orchestrator will run nano mode.)

**C** → Print: `Pipeline paused after explore. Resume with team [feature] build when ready.`
Call `pathly-fsm-call complete-stage --flow team --topic [FEATURE] --project-root <project_root>`. Stop.

---

## Path 5 — Full discovery (PO → Storm → Plan)

**Phase 1 — PO Discussion:**
Call `pathly-fsm-call complete-stage --flow team --topic [FEATURE] --project-root <project_root>`.

**Spawn** `po`:
```
Run PO mode for the feature: [feature name]
Probe requirements interactively — problem, users, MVP scope, out-of-scope, constraints, edge cases.
The user will type "stop notes" when satisfied to write <feature_path>/PO_NOTES.md.
Remind them of this at the start.
```
After PO completes: call `pathly-fsm-call complete-stage --flow team --topic [FEATURE] --project-root <project_root>`.

If not autoFlow — pause:
```
[Phase 1 — PO Discussion complete]
Requirements captured in <feature_path>/PO_NOTES.md.
Ready for architect storm? Reply 'yes' to continue, or 'no' to stop here.
```
On 'no': log human response "stop". Halt.
On 'yes': log human response with reply value. Advance.
If autoFlow: log human response "auto-advance".

**Phase 2 — Architect Storm:**
Call `pathly-fsm-call complete-stage --flow team --topic [FEATURE] --project-root <project_root>`.
Route to `team/plan [FEATURE] [rigor] [autoFlow] storm`.
(plan.md Stage 1 runs the full analyze → research → storm cycle, reading PO_NOTES.md automatically.)

If not autoFlow — pause:
```
[Phase 2 — Architect Storm complete]
STORM_SEED.md written. Ready to plan? Reply 'yes' to continue, or 'no' to stop here.
```
On 'no': halt.

**Phase 3 — Hand off to plan:**
Call `pathly-fsm-call complete-stage --flow team --topic [FEATURE] --project-root <project_root>`.
Route to `team/plan [FEATURE] [rigor] [autoFlow]`.

---

## State recovery — resume in-progress feature

Before printing the discovery menu, call `pathly-fsm-call next-action --flow team --topic <feature> --project-root <project_root>` to recover the authoritative state from the FSM/DB. The FSM is the source of truth; STATE.json is a mirror written by the FSM.

If the recovered state is not IDLE or a discovery state, **bypass the discovery menu entirely** and route directly to the team skill for the true state:

| True state (from DB) | Route to |
|---|---|
| `PLANNING` | `team/plan [FEATURE] [rigor] [autoFlow]` |
| `DESIGNING` | `team/design [FEATURE] [rigor] [autoFlow]` |
| `BUILDING` | `team/build [FEATURE] [rigor] [autoFlow]` |
| `REVIEWING` | `team/review [FEATURE] [rigor] [autoFlow]` |
| `TESTING` | `team/test [FEATURE] [rigor] [autoFlow]` |
| `RETRO` | `team/retro [FEATURE] [rigor] [autoFlow]` |
| `DONE` | Print: `[feature] pipeline is already DONE.` and stop. |

> **Never route to `pathly-build`, `pathly-review`, or other interactive
> (non-team) skills during state recovery.** Those skills have different phase
> logging and lifecycle expectations. Always use the `team/*` variants.
