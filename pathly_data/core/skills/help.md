# help

This is the canonical, tool-agnostic Pathly behavior for the help workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Adapter Surface

This core prompt names Pathly workflows and menu actions. Adapters translate
those actions into their native surface. Do not satisfy a menu action by running
an adapter-specific command unless the user explicitly asked for that fallback.

## Doctor mode (`doctor`)

If `$ARGUMENTS` contains `--doctor` (e.g. `doctor` or `help my-feature --doctor`),
run the diagnostic flow below instead of the normal menu. Extract the feature name from
`$ARGUMENTS` if one is provided alongside `--doctor`; otherwise scan `plans/` for the most
recently modified feature folder.

### Doctor Step 1 — Run verify-state internally

Perform every check from the `verify-state` skill (Checks A through D) for the target feature.
Collect all flagged issues.

### Doctor Step 2 — Check additional stuck-state indicators

Beyond what verify-state checks, also look for:

- **STATE.json says BUILDING but no conversations are in_progress in PROGRESS.md** →
  FSM stuck: builder may have exited mid-run.
- **Feedback file has expired TTL** (from frontmatter `created_at + ttl_hours`) →
  stale orphan from a previous run.
- **Feedback file event ID not in EVENTS.jsonl** → orphan from a different session.
- **REVIEW_FAILURES.md exists but git diff shows no changes since it was written** →
  builder loop (zero-diff stall).

### Doctor Step 3 — Report in plain language

Print a diagnostic summary in this format:

```
╔══════════════════════════════════════════╗
  doctor — <feature>
╚══════════════════════════════════════════╝

✓  Everything looks healthy.
```

Or, if issues found:

```
╔══════════════════════════════════════════╗
  doctor — <feature>
  N issue(s) found
╚══════════════════════════════════════════╝

Issue 1: REVIEW_FAILURES.md is a leftover from a previous run
  Why: its event ID (2026-04-28T10:00:00Z) does not appear in the current EVENTS.jsonl.
  Suggestion: delete plans/<feature>/feedback/REVIEW_FAILURES.md

Issue 2: STATE.json says BUILDING but no conversation is active
  Why: PROGRESS.md shows all conversations as either DONE or TODO — none are in_progress.
  Suggestion: route to `team-flow <feature> build` to return the pipeline to a stable state.

────────────────────────────────────────────
Run suggestion 1? [yes / no / show all suggestions]
```

### Doctor Step 4 — Offer action

If there are suggestions, ask: `Run suggestion 1? [yes / no / show all suggestions]`

- **yes** → execute the first suggestion (delete orphan file, or run the recommended route)
- **no** → print the full list of suggestions and stop
- **show all suggestions** → print the full list and ask "Which suggestion to run? [1/2/…/none]"

**Rules for doctor mode:**
- Never auto-fix without explicit user confirmation.
- If a suggestion is "delete a file", show the file path clearly before confirming.
- If a suggestion is "run a route", show the exact route before running.
- One action at a time — do not batch multiple fixes without explicit approval.

---

## Step 1: Detect state

Check in this order:

1. If `$ARGUMENTS` is provided, use it as `FEATURE`.
   Otherwise scan `plans/` for the most recently modified feature folder.

2. Read `plans/$FEATURE/PROGRESS.md` if it exists.

3. Check `plans/$FEATURE/feedback/` for open files.

4. Infer current rigor:
   - **lite** — required 4 files exist, but one or more standard files are missing:
     `HAPPY_FLOW.md`, `EDGE_CASES.md`, `ARCHITECTURE_PROPOSAL.md`, `FLOW_DIAGRAM.md`
   - **standard** — all 8 plan files exist, but strict audit files or strict markers are missing
   - **strict** — all 8 plan files exist and `STATE.json` + `EVENTS.jsonl` exist, or the plan explicitly says `Rigor: strict`
   - **unknown** — no plan folder exists yet

5. Print the inferred rigor in every feature-specific menu banner:
   `Rigor: lite|standard|strict|unknown`

6. Classify into one of these states:
   - **no-feature** — no plans/ folder or no feature found
   - **storm-done** — `plans/STORM_SEED.md` exists, no plans folder yet
   - **plan-done** — plans folder exists, at least one conversation TODO, no open feedback
   - **feedback-open** — plans folder exists, feedback file(s) present
   - **build-done** — all conversations DONE, no RETRO.md yet
   - **retro-done** — RETRO.md exists

---

## Step 2: Print interactive menu

Print the banner, then the numbered options for the detected state. Wait for user input.

### State: no-feature

```
═══════════════════════════════════════════
  Pathly
  No active feature found
═══════════════════════════════════════════

  What do you want to do?

  [1] Start a new feature                     -> /pathly start
  [2] Brainstorm/refine an unclear idea       -> storm
  [3] Start a new feature with a PRD/BMAD file
  [4] See all commands

Reply with 1, 2, 3, or 4:
```

On '1': route to director via `/pathly start` (director asks for intent)
On '2': ask "What idea do you want to refine?" -> route to `storm <answer>`
On '3': ask "Feature name?" then "PRD or BMAD file path?" -> route to `team-flow <name>` and user selects PRD/BMAD at the path selector
On '4': print full command reference (Step 3)

---

### State: storm-done

```
═══════════════════════════════════════════
  Storm complete — STORM_SEED.md ready
═══════════════════════════════════════════

  What do you want to do?

  [1] Plan the feature now      -> plan <feature>
  [2] Run full pipeline         -> team-flow <feature>
  [3] See all commands

Reply with 1, 2, or 3:
```

On '1': route to `plan <feature>`
On '2': route to `team-flow <feature>`
On '3': print full command reference

---

### State: plan-done

Read PROGRESS.md: X conversations done, Y remaining.

```
═══════════════════════════════════════════
  <feature> — Plan ready
  Conv: X done · Y remaining
  Rigor: lite|standard|strict
═══════════════════════════════════════════

  What do you want to do?

  [1] Continue building         → /pathly continue
  [2] Run full pipeline         → build + review + test + retro
  [3] Run full pipeline (fast)  → no pause points
  [4] Review current code       -> review
  [5] Meet a role               -> /pathly meet
  [6] Change rigor              ? see options
  [7] See all commands          -> /pathly help
Reply with 1–7:
```

On '1': route to orchestrator via `/pathly continue` (reads STATE.json for active feature)
On '2': route to `team-flow <feature> build`  (with pauses)
On '3': route to `team-flow <feature> build fast`
On '4': route to `review`
On '5': route to meet skill via `/pathly meet` (reads STATE.json for active feature)
On '6': print the "CHANGING RIGOR" section from Step 3
On '7': print full command reference

---

### State: feedback-open

List which feedback files exist and who must act.

```
═══════════════════════════════════════════
  <feature> — Open feedback requires action
  Rigor: lite|standard|strict
═══════════════════════════════════════════

  Open files:
    REVIEW_FAILURES.md → builder must fix
    [other files if present]

  What do you want to do?

  [1] Resume pipeline (routes to correct agent automatically)  → /pathly continue
  [2] See the feedback file contents
  [3] See all commands

Reply with 1, 2, or 3:
```

On '1': route to orchestrator via `/pathly continue` (reads STATE.json, routes to correct agent)
On '2': read and print the feedback file(s)
On '3': print full command reference

---

### State: build-done

```
═══════════════════════════════════════════
  <feature> — All conversations complete
  Rigor: lite|standard|strict
═══════════════════════════════════════════

  What do you want to do?

  [1] Close feature (tests + retro)  → /pathly end
  [2] Continue building              → /pathly continue
  [3] Run tests only                 → tester verifies all ACs
  [4] Write retro only               -> retro <feature>
  [5] See all commands

Reply with 1–5:
```

On '1': route to orchestrator via `/pathly end` (confirms, runs tests if needed, then retro)
On '2': route to orchestrator via `/pathly continue` (reads STATE.json for active feature)
On '3': route to `team-flow <feature> test`
On '4': route to `retro <feature>`
On '5': print full command reference

---

### State: retro-done

```
═══════════════════════════════════════════
  <feature> — DONE ✓
  RETRO.md written
  Rigor: lite|standard|strict
═══════════════════════════════════════════

  What do you want to do?

  [1] Archive this feature      → moves to plans/.archive/
  [2] Promote lessons           -> lessons (update active memory)
  [3] Start next feature        -> /pathly start
  [4] Read the retro            → show RETRO.md
  [5] See all commands

Reply with 1–5:
```

On '1': route to `archive <feature>`
On '2': route to `lessons`
On '3': route to director via `/pathly start` (director asks for new feature intent)
On '4': read and print RETRO.md
On '5': print full command reference

---

## Step 3: Full command reference (shown on request only)

```
───────────────────────────────────────────
  ENTRY POINTS
───────────────────────────────────────────

  pathly                                prompts "What do you want?" -> routes
  pathly <what you want>                skip prompt, routes immediately
  help [feature]                        detect state -> show this menu
  doctor [feature]                      diagnose stuck FSM, orphan files, stale feedback
  meet [feature]                        consult one relevant role, write a read-only consult note

───────────────────────────────────────────
  MAIN COMMAND
───────────────────────────────────────────

  flow <feature>                       full pipeline, standard rigor by default
  flow <feature> lite                  small change, 4-file plan, lighter gates
  flow <feature> standard              current full 8-file pipeline
  flow <feature> strict                mandatory approvals + audit-grade gates
  flow <feature> build                 skip to build stage
  flow <feature> test                  skip to test stage
  flow <feature> plan                  skip discovery, start planning
  flow <feature> fast                  no pause points
  flow <feature> build fast            resume build, no pauses

───────────────────────────────────────────
  INDIVIDUAL STAGES
───────────────────────────────────────────

  storm                                     architect explores idea -> STORM_SEED.md
  plan <feature> [rigor]                    planner creates 4 or 8 plan files
  continue <feature>                        builder implements next TODO conversation
  review                                    reviewer audits staged changes
  retro <feature>                           quick summarizes; retro skill writes RETRO.md + extracts lessons
  lessons                                   promote candidate lessons -> LESSONS.md
  archive <feature>                         move completed feature to plans/.archive/
  prd-import <feature> <file> [rigor]        translate any PRD file -> plan files
  bmad-import <feature> <file> [rigor]       translate BMAD PRD -> plan files
  verify-state [feature]                    check stale feedback, PROGRESS drift, dead references

───────────────────────────────────────────
  CHANGING RIGOR
───────────────────────────────────────────

  help [feature] should show the inferred current rigor.

  Upgrade lite → standard:
    plan <feature> standard
    Adds missing standard files. Keeps existing plan content.

  Upgrade standard → strict:
    plan <feature> strict
    Adds strict risk, rollback, approval, and verification mapping.

  Downgrade strict → standard:
    flow <feature> standard
    Uses standard gates from now on. Do not delete audit files.

  Downgrade standard → lite:
    flow <feature> lite
    Uses lighter gates from now on. Keep extra plan files as references.

  Never delete plan files just to downgrade. Rigor controls future gates.

───────────────────────────────────────────
  FEEDBACK FILES  (plans/<feature>/feedback/)
───────────────────────────────────────────

  ARCH_FEEDBACK.md     reviewer → architect   (BLOCKING)
  REVIEW_FAILURES.md   reviewer → builder
  IMPL_QUESTIONS.md    builder [REQ]  → planner
  DESIGN_QUESTIONS.md  builder [ARCH] → architect
  TEST_FAILURES.md     tester   → builder
  HUMAN_QUESTIONS.md   any agent → user (BLOCKED_ON_HUMAN)

  File present = issue open. Deleted = resolved.

───────────────────────────────────────────
  DOCS
───────────────────────────────────────────

  docs/ARCHITECTURE_AGENTS.md   full pipeline + agent map
  docs/ORCHESTRATOR_FSM.md      deterministic workflow state machine
  docs/FEEDBACK_PROTOCOL.md     feedback file formats
  docs/CONCEPTS.md              philosophy
  docs/README.md or the adapter-specific documentation

═══════════════════════════════════════════
```
