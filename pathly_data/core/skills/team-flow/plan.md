# team-flow/plan

Stages 1 + 2 — Storm and Plan. Invoked by the `team-flow` orchestrator when FSM state is
PLANNING, or by `team-flow/discover` with arg `storm` to run Stage 1 first.

Parse `$ARGUMENTS`: `FEATURE`, `rigor` (lite|standard|strict), `autoFlow`, optional `storm` flag.

## FSM operations

**Transition state to X:** Write `plans/<feature>/STATE.json` `{"current": "X"}`.
Append `{"type": "STATE_TRANSITION", "to": "X"}` to `plans/<feature>/EVENTS.jsonl`.

**Log human response:** Append `{"type": "HUMAN_RESPONSE", "value": "<value>"}` to EVENTS.jsonl.

## Subagents

| Action | Spawn |
|---|---|
| Technical storm | `architect` |
| Create plan files | `planner` |

---

## Stage 1 — Storm
*(only runs if `storm` flag is present in args or FSM state is STORMING)*

**Spawn** `architect`:
```
Route to storm for the feature: [feature name]
Explore the idea technically — layers, dependencies, design decisions.
When the user is satisfied, they will type /stop plan to write STORM_SEED.md.
Remind them of this at the start.
```

If not autoFlow — pause:
```
[Stage 1 — Storm complete]
STORM_SEED.md written (or skipped).
Ready to plan? Reply 'yes' to continue, or 'no' to stop here.
```
- Proceed signal ('yes', 'go', 'continue', 'done', numeric): log human response with reply value. Advance.
- Stop signal ('no', 'stop'): log human response "stop". Write STATE.json with current state. Halt.
- Unrecognised: re-prompt without logging.

If autoFlow: log human response "auto-advance".

Transition state → PLANNING. Fall through to Stage 2.

---

## Stage 2 — Plan

**Spawn** `planner`:
```
Route to plan [feature name] [rigor].
If plans/[feature]/STORM_SEED.md exists, consume it as pre-filled answers.
If plans/[feature]/PO_NOTES.md exists, read it first for requirements context.
Ensure every story references which phase/conversation delivers it.
Ensure every phase references which stories it fulfills.
After creating the selected rigor's plan files, list them as a summary.
```

After planner completes — run the **rigor escalator** (below).

If not autoFlow — pause:
```
[Stage 2 — Plan complete]
plans/[feature]/ created with the selected rigor's required files.
Review USER_STORIES.md and CONVERSATION_PROMPTS.md.
Reply 'go' to start implementation, or 'stop' to pause here.
```
- Proceed: log human response with reply value. Advance.
- Stop: log human response "stop". Write STATE.json with current state. Halt.

If autoFlow: log human response "auto-advance".

Transition state → BUILDING.
Route back to `team-flow [FEATURE] [rigor] [autoFlow]`.

---

## Rigor escalator

Runs after planning completes, before routing back to the orchestrator.

The pipeline **always starts with the 4 core lite files** — no exceptions:
```
USER_STORIES.md
IMPLEMENTATION_PLAN.md
PROGRESS.md
CONVERSATION_PROMPTS.md
```

Check these signals after planning. Each additional file has one trigger:

| Extra file | Trigger signal | How to detect |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | Cross-layer dependency | Architect or planner mentions > 1 layer, or STORM_SEED.md references multiple layers |
| `EDGE_CASES.md` | High-risk keyword in risk context | See keyword rule below |
| `HAPPY_FLOW.md` | > 3 conversations planned | CONVERSATION_PROMPTS.md has more than 3 conversation blocks |
| `FLOW_DIAGRAM.md` | Long discovery path | STORM_SEED.md or explore output references > 3 files, or architect drew a multi-component diagram |

**EDGE_CASES.md keyword rule:** Scan USER_STORIES.md and STORM_SEED.md for:
`auth`, `payment`, `migration`, `security`, `schema`, `breaking change`

Signal fires only if the keyword appears in a risk context:
- Same sentence/bullet as: `fail`, `invalid`, `expire`, `breach`, `error`, `corrupt`, `race`, `concurrent`, `collision`, `rollback`, `sensitive`, `lost`, `overwrite`, `unauthorized`
- OR in a section heading about failure modes / edge cases / error handling
- OR appears more than once across the document

Does NOT fire for pure UI/label mentions (e.g. "auth button label", "payment icon color").

### Offer (interactive mode)

If any signal fires, write `plans/<feature>/feedback/HUMAN_QUESTIONS.md`:
```
[RIGOR ESCALATOR] — recommended additions for <feature>

The 4 core plan files are ready. Based on what was found during planning,
these additional files are recommended:

  ✦ ARCHITECTURE_PROPOSAL.md   → cross-layer dependencies detected
  ✦ EDGE_CASES.md              → keyword "payment" found in USER_STORIES.md
  ─ HAPPY_FLOW.md              → no signal (2 conversations planned)
  ─ FLOW_DIAGRAM.md            → no signal (discovery path was short)

Add to plan:
  [1] All recommended
  [2] ARCHITECTURE_PROPOSAL.md only
  [3] EDGE_CASES.md only
  [4] None — keep 4 core files only

Reply with 1, 2, 3, or 4:
```
Wait for reply. Spawn `planner` to generate only the selected file(s). Delete HUMAN_QUESTIONS.md.

If **no signals fire**: skip the offer entirely.

### Fast / auto mode

Skip the question. Apply all recommended files automatically.
Print: `[RIGOR AUTO] Adding: <file1>, <file2> — signals detected during planning.`

### Rules

- The 4 core files are never removed, never conditional, never skipped.
- Extra files are additive only — never replace core files.
- Do not add a file when its signal did not fire, even if the user asks for "standard".
  (If the user wants all 8 files explicitly, route to `flow <feature> standard`.)
