# team/plan

Stages 1 + 2 — Storm and Plan. Invoked by the `team` orchestrator when FSM state is
PLANNING, or by `team/discover` with arg `storm` to run Stage 1 first.

Parse `$ARGUMENTS`: `FEATURE`, `rigor` (lite|standard|strict), `autoFlow`, optional `storm` flag.

## Role

**Stage orchestrator: Planning & Storm**
You coordinate subagents, handle feedback routing, and log every phase boundary.
Logging is mandatory — each `log-phase` call is part of the pipeline contract.

> After each phase completes, log `log-phase PHASE_DONE <phase>` before starting the next.
> If `pathly-fsm-call` is unavailable, skip silently — never block execution.

## FSM operations

**Transition state to X:** Call `pathly-fsm-call complete-stage --flow <flow> --topic <topic> --project-root <project_root>`.
The FSM computes the next state from transition_rules — the skill no longer decides or writes STATE.json.
Log via: `python3 -c "from pathly_orchestrator.eventlog import append_event; append_event('<feature_path>', {'type':'STATE_TRANSITION','to':'X','ts':'<iso-timestamp>'})"`.

Every logged event must include `"ts": "<iso-timestamp>"` using the current ISO-8601 UTC time.

**Log human response:** `python3 -c "from pathly_orchestrator.eventlog import append_event; append_event('<feature_path>', {'type':'HUMAN_RESPONSE','value':'<value>','ts':'<iso-timestamp>'})"`.


## Subagents

| Action | Spawn |
|---|---|
| Storm Phase 1 — Analyze | `architect` (phase: analyze) |
| Storm Phase 2 — Research | scout agent — parallel per entry (architect lens) |
| Storm Phase 3 — Storm | `architect` (phase: storm) |
| PO Phase — Requirements | `po` |
| Plan Phase 1 — Analyze | `planner` (phase: analyze) |
| Plan Phase 2 — Scout | scout agent — parallel per entry (planner lens) |
| Plan Phase 3 — Plan | `planner` (phase: plan) |

---

## Stage 1 — Storm
*(only runs if `storm` flag is present in args or FSM state is STORMING)*

### Phase 1 — Analyze

log-phase PHASE_START storm-analyze

**Spawn** `architect` with `phase: analyze`:
```
phase: analyze
Feature: [feature name]
Read <feature_path>/PO_NOTES.md if it exists.
Read <feature_path>/STORM_SEED.md if it exists.
List what codebase research and external information you need before storming — output NEEDS_CONTEXT block only.

NEEDS_CONTEXT format (one entry per line):
  - type: scout | scope: <files or directories> | question: <specific question>
  - type: quick | question: <specific question>
  - type: web | query: <search query>

Output `none` if no upfront research is needed.
```
Parse the `## NEEDS_CONTEXT` block. If it says `none`, skip Phase 2.

log-phase PHASE_DONE storm-analyze

### Phase 2 — Research

log-phase PHASE_START storm-research

Spawn all NEEDS_CONTEXT entries in parallel (max 4 total) with `ROLE: architect`:
- `type: quick` → spawn `quick` with `ROLE: architect` + the question
- `type: scout` → spawn `scout` with `ROLE: architect` + scope + question
- `type: web` → spawn `web-researcher` with `ROLE: architect` + the query

Default: always parallel — scouts are read-only, scope overlap is not a problem.
Sequential only when entry B's question explicitly references entry A's answer
(e.g. "that class", "the above", "what you found").
Collect all findings. Synthesize into a single Research Findings block before Phase 3.

log-phase PHASE_DONE storm-research

### Phase 3 — Storm

log-phase PHASE_START storm

**Spawn** `architect` with `phase: storm` and research findings injected:
```
phase: storm
Route to storm for the feature: [feature name]
Explore the idea technically — layers, dependencies, design decisions.

## Research Findings
[compressed summary — or "none" if Phase 2 was skipped]

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
- Stop signal ('no', 'stop'): log human response "stop". Halt without advancing to next stage.
- Unrecognised: re-prompt without logging.

If autoFlow: log human response "auto-advance".

log-phase PHASE_DONE storm

Call `pathly-fsm-call complete-stage --flow team --topic <feature> --project-root <project_root>` to advance to PLANNING.
Fall through to Stage 2.

---

## Stage 2 — Plan

Record start time: run `python -c "import time; print(int(time.time()))"` and note as `PLAN_START`.

### PO Phase — Requirements

log-phase PHASE_START po

Before planner analysis, check whether `<feature_path>/PO_NOTES.md` exists.
If it exists, skip this phase entirely and proceed to Phase 1 — Analyze.

If `PO_NOTES.md` does not exist, check `<feature_path>/STORM_SEED.md`
richness:
- Rich STORM_SEED.md: spawn `po` in confirmation-pass mode.
- Thin or absent STORM_SEED.md: spawn `po` in full-interactive mode.

Wait for `PO_NOTES.md` to be written before continuing. If PO exits via
`stop` (discard) without writing `PO_NOTES.md`, halt and print an error to the
user: `PO Phase discarded without PO_NOTES.md; planning cannot continue.`
This is an unrecoverable state for the pipeline.

If autoFlow is active, PO Phase runs non-interactively. PO writes its best-guess
`PO_NOTES.md`, then the planner proceeds immediately.

log-phase PHASE_DONE po

### Phase 1 — Analyze

log-phase PHASE_START plan-analyze

**Spawn** `planner` with `phase: analyze`:
```
phase: analyze
Feature: [feature name], rigor: [rigor]
Read <feature_path>/STORM_SEED.md if it exists.
Read <feature_path>/PO_NOTES.md if it exists.
If pathly/explorations/[feature]/CONCLUSIONS.md exists, read it as prior exploration context — treat its findings as established facts and do not re-investigate what it already covers.
List what codebase context you need before writing the plan — output NEEDS_CONTEXT block only.

NEEDS_CONTEXT format (one entry per line):
  - type: scout | scope: <files or directories> | question: <specific question>
  - type: quick | question: <specific question>

Output `none` if no upfront research is needed.
```
Parse the `## NEEDS_CONTEXT` block. If it says `none`, skip Phase 2.

log-phase PHASE_DONE plan-analyze

### Phase 2 — Scout

log-phase PHASE_START plan-scout

Spawn all NEEDS_CONTEXT entries in parallel (max 4 total) with `ROLE: planner`:
- `type: quick` → spawn `quick` with `ROLE: planner` + the question
- `type: scout` → spawn `scout` with `ROLE: planner` + scope + question

Default: always parallel — scouts are read-only, scope overlap is not a problem.
Sequential only when entry B's question explicitly references entry A's answer.
Collect all findings. Synthesize into a single Scout Findings block before Phase 3.

log-phase PHASE_DONE plan-scout

### Phase 3 — Plan

log-phase PHASE_START plan

**Spawn** `planner` with `phase: plan` and scout findings injected:
```
phase: plan
Route to plan [feature name] [rigor].
If <feature_path>/STORM_SEED.md exists, consume it as pre-filled answers.
Read <feature_path>/PO_NOTES.md as the authoritative source of user stories.
If pathly/explorations/[feature]/CONCLUSIONS.md exists, treat it as prior exploration: do not re-investigate what it covers; use its Recommendation and Evidence sections to anchor scope and risk decisions.
Decompose — do not re-author stories.

## Scout Findings
[compressed summary — or "none" if Phase 2 was skipped]

Ensure every story references which phase/conversation delivers it.
Ensure every phase references which stories it fulfills.
After creating the selected rigor's plan files, list them as a summary.
```

After planner completes, parse the `<usage>` block from its response:
- `total_tokens`: the number after `total_tokens:` (0 if absent)
- `tool_uses`: the number after `tool_uses:` (0 if absent)
- `duration_ms`: the number after `duration_ms:` (0 if absent)

After planner completes — run the **rigor escalator** (below).

log-phase PHASE_DONE plan

If not autoFlow — pause:
```
[Stage 2 — Plan complete]
<feature_path>/ created with the selected rigor's required files.
Review USER_STORIES.md and IMPLEMENTATION_PLAN.md.
Reply 'go' to start implementation, or 'stop' to pause here.
```
- Proceed: log human response with reply value. Advance.
- Stop: log human response "stop". Halt without advancing to next stage.

If autoFlow: log human response "auto-advance".

Call `pathly-fsm-call complete-stage --flow team --topic <feature> --project-root <project_root>` to advance to BUILDING.

Run the Completion report with `agent: planner`, `result: DONE`, `conversation: 0`, using `PLAN_START` from Stage 2. Set `summary` to: `"planner created <N> files for <FEATURE> (<rigor> rigor)"` where N is the count of files written.

Route back to `team [FEATURE] [rigor] [autoFlow]`.

---

## Rigor escalator

Runs after planning completes, before routing back to the orchestrator.

The pipeline **always starts with the 3 core lite files** — no exceptions:
```
FEATURE_INDEX.md
USER_STORIES.md
IMPLEMENTATION_PLAN.md
```
`IMPLEMENTATION_PLAN.md` is the phase source: each phase becomes one board task in plan.md
Step 6, and the build loop drains that board DAG — there are no per-conversation plan files.

Check these signals after planning. Each additional file has one trigger:

| Extra file | Trigger signal | How to detect |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | Cross-layer dependency | Architect or planner mentions > 1 layer, or STORM_SEED.md references multiple layers |
| `EDGE_CASES.md` | High-risk keyword in risk context | See keyword rule below |
| `HAPPY_FLOW.md` | > 3 conversations planned | IMPLEMENTATION_PLAN.md has more than 3 phases |
| `FLOW_DIAGRAM.md` | Long discovery path | STORM_SEED.md or explore output references > 3 files, or architect drew a multi-component diagram |

**EDGE_CASES.md keyword rule:** Scan USER_STORIES.md and STORM_SEED.md for:
`auth`, `payment`, `migration`, `security`, `schema`, `breaking change`

Signal fires only if the keyword appears in a risk context:
- Same sentence/bullet as: `fail`, `invalid`, `expire`, `breach`, `error`, `corrupt`, `race`, `concurrent`, `collision`, `rollback`, `sensitive`, `lost`, `overwrite`, `unauthorized`
- OR in a section heading about failure modes / edge cases / error handling
- OR appears more than once across the document

Does NOT fire for pure UI/label mentions (e.g. "auth button label", "payment icon color").

### Offer (interactive mode)

If any signal fires, write `<feature_path>/feedback/HUMAN_QUESTIONS.md`:
```
[RIGOR ESCALATOR] — recommended additions for <feature>

The 3 core plan files are ready. Based on what was found during planning,
these additional files are recommended:

  ✦ ARCHITECTURE_PROPOSAL.md   → cross-layer dependencies detected
  ✦ EDGE_CASES.md              → keyword "payment" found in USER_STORIES.md
  ─ HAPPY_FLOW.md              → no signal (2 conversations planned)
  ─ FLOW_DIAGRAM.md            → no signal (discovery path was short)

Add to plan:
  [1] All recommended
  [2] ARCHITECTURE_PROPOSAL.md only
  [3] EDGE_CASES.md only
  [4] None — keep 3 core files only

Reply with 1, 2, 3, or 4:
```
Wait for reply. Spawn `planner` to generate only the selected file(s). Delete HUMAN_QUESTIONS.md.

If **no signals fire**: skip the offer entirely.

### Fast / auto mode

Skip the question. Apply all recommended files automatically.
Print: `[RIGOR AUTO] Adding: <file1>, <file2> — signals detected during planning.`

### Rules

- The 3 core files are never removed, never conditional, never skipped.
- Extra files are additive only — never replace core files.
- Do not add a file when its signal did not fire, even if the user asks for "standard".
  (If the user wants all 7 files explicitly, route to `flow <feature> standard`.)
