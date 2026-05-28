# Pathly Skills Overview

29 user-facing skills plus 2 internal transition-action skills. Each lives in
`core/skills/`. Adapters translate them to host-native surfaces. This document
is the authoritative reference.

---

## The Machine — Lifecycle Control

Pathly is a state machine. These six skills are the control signals:

```
┌─────────────────────────────────────────────────────┐
│                   PATHLY MACHINE                    │
│                                                     │
│  /pathly start                                      │
│       │                                             │
│       ▼                                             │
│    [IDLE] ──────── /pathly go <intent> ──────►     │
│                         │                           │
│                    [ROUTING]                        │
│                         │                           │
│              ┌──────────┘                           │
│              ▼                                      │
│          [RUNNING] ◄─────────────────────┐          │
│              │                           │          │
│              ├── /pathly pause ──► [PAUSED]         │
│              │                       │              │
│              │                    /pathly meet      │
│              │                       │              │
│              │                  [CONSULTING]        │
│              │                       │              │
│              │                    /pathly go        │
│              │                       │              │
│              └───────────────────────┘              │
│              │                                      │
│         /pathly end                                 │
│              │                                      │
│           [DONE]                                    │
└─────────────────────────────────────────────────────┘
```

**Why meet fits here:** After pausing, the user can consult a role (architect,
tester, reviewer, etc.) without touching code or plan files. The consult note
is written, then the user resumes with `/pathly go`. This gives full control
without breaking pipeline state.

---

## 1. pathly — Dispatcher

The canonical router. All entry points go through here.

```
/pathly [subcommand] [args]
         │
         ▼
  ┌──────────────────────────────────┐
  │  subcommand → behavior           │
  │                                  │
  │  (empty)        → help           │
  │  start / s      → start          │
  │  go / g /       → go             │
  │  continue/resume                 │
  │  end / done /   → end            │
  │  finish / wrap                   │
  │  pause / stop   → pause          │
  │  help / h / ?   → help           │
  │  meet           → meet           │
  │  anything else  → go (as intent) │
  └──────────────────────────────────┘
         │
         ▼
  Print: "Pathly route: <subcommand>"
  Execute behavior inline
```

---

## 2. start — Welcome Gate

Entry point for new sessions.

```
/pathly start
      │
      ▼
  ┌──────────────────────────────┐
  │  Welcome menu:               │
  │  1. storm    — shape an idea │
  │  2. plan     — define feature│
  │  3. go       — continue work │
  │  4. prd-import — import PRD  │
  │  or: free text → go (intent) │
  └──────────────────────────────┘
      │
  ┌───┴──────┬────────┬──────────┐
  ▼          ▼        ▼          ▼
storm      plan      go      prd-import
<topic>  <feature>          <f> <path>
```

---

## 3. go — Director / Intent Router

Reads project state, classifies intent, chooses the lightest safe workflow.

```
/pathly go [intent]
      │
      ▼ (ask if empty)
  Read project state
  pathly/plans/, PROGRESS.md, git status
      │
      ▼
  Classify intent:
  ┌─────────────────────────────────────┐
  │ tiny_change → team nano        │
  │ new_feature → team <rigor>     │
  │ brainstorm  → storm <topic>         │
  │ resume      → team build       │
  │ test        → team test        │
  │ fix/review  → review / nano         │
  │ retro       → retro <feature>       │
  │ unclear     → ask one question      │
  └─────────────────────────────────────┘
      │
      ▼
  Choose rigor:
  nano     → ≤2 files, obvious path
  lite     → low risk, 1–3 convs
  standard → multi-layer, > 3 convs
  strict   → auth / payment / data
      │
      ▼
  Print decision → Invoke route
```

---

## 4. pause — Save State

Cleanly suspends the active session without losing state.

```
/pathly pause
      │
      ▼
  Scan pathly/plans/ (skip .archive/)
      │
  ┌───┴──────────────────┐
  ▼                      ▼
IN PROGRESS found     nothing found
      │                   │
      ▼                   ▼
Write PAUSED          "Nothing in
to PROGRESS.md         progress."
      │
      ▼
  "Session paused.
   Resume:  /pathly go
   Consult: /pathly meet"
```

---

## 5. meet — Mid-Flow Consultation

Ask one named role a bounded question without touching code or pipeline state.

```
/pathly meet [feature]
      │
      ▼
  Read feature state
  (PROGRESS.md, feedback/, STATE.json)
      │
      ▼
  Infer state:
  planning | building | feedback-open
  testing | done
      │
      ▼
  Show state-aware role menu:
  ┌──────────────────────────────────┐
  │ building → planner, architect,   │
  │   reviewer, tester, scout        │
  │ feedback-open → reviewer,        │
  │   architect, planner, scout      │
  │ (builder + director never listed)│
  └──────────────────────────────────┘
      │
      ▼
  "What is your one question?"
      │
      ▼
  Run role READ-ONLY:
  no code edits · no plan edits
  no feedback file changes
      │
      ▼
  Write consult note:
  pathly/plans/<feature>/consults/
  YYYYMMDD-HHMMSS-<role>.md
      │
      ▼
  ┌──────────────────────────────────┐
  │ 1. Return to build               │
  │ 2. Promote to planner update     │
  │ 3. Promote to architect update   │
  │ 4. Ask another question          │
  └──────────────────────────────────┘
      │
  (if promotion chosen)
      ▼
  planner/architect reads note
  updates only affected plan files
  does not change source code
```

---

## 6. end — Session Close

Wraps up the session; offers retro.

```
/pathly end
      │
      ▼
  Scan pathly/plans/ for IN PROGRESS
      │
  ┌───┴──────────────────────┐
  ▼                          ▼
found IN PROGRESS        nothing found
      │                       │
      ▼                       ▼
  Show summary:          "Nothing in
  Feature + conv count    progress. Done."
      │
      ▼
  "Write retro? (y/n)"
      │
  ┌───┴───────┐
  ▼           ▼
 yes          no
  │           │
retro      "Done.
<feature>  Commit?"
```

---

## 7. help — State-Aware Menu

Detects where you are in the pipeline and shows the right next actions.

```
/pathly help [feature]
      │
      ▼
  Detect state:
  ┌────────────────────────────────────┐
  │ no-feature   → start / storm /     │
  │                prd-import          │
  │ storm-done   → plan / team    │
  │ plan-done    → continue / review / │
  │                meet                │
  │ feedback-open→ resume / show       │
  │ build-done   → end / test / retro  │
  │ retro-done   → archive / lessons   │
  └────────────────────────────────────┘
      │
  "See all" → full command reference
  "--doctor" → run diagnostics mode
                (verify-state + stuck checks)
```

---

## 8. prd-import — PRD → Plan Files

Handles any PRD format: generic, AI-generated, or BMAD-structured.
`bmad-import` is an alias — both resolve here.

```
prd-import <feature> <path> [rigor]
      │
      ▼
  Parse args + validate
  (file exists, no plan conflict)
      │
      ▼
  Read PRD — extract:
  stories · ACs · edge cases
  constraints · out-of-scope
      │
      ▼
  Read project conventions
  (CLAUDE.md, rules/, similar code)
      │
      ▼
  Plan conversation split:
  LOW  (≤4 ACs)  → 2 convs
  MED  (5–8 ACs) → 3 convs
  HIGH (9+ ACs)  → 4 convs / split
      │
      ▼
  Translate ACs → verify commands
  Map edge cases → convs
      │
      ▼
  Generate files:
  lite     → 4 files
  standard → 8 files
  strict   → 8 + risk/rollback
      │
      ▼
  Verify output → Report
  "Next: continue <feature>"
```

---

## 9. storm — Brainstorm Mode

Persistent interactive thinking space. No files, no code, no plans.
Only exits on explicit stop trigger.

```
storm [topic]
      │
      ▼
  If codebase topic:
  spawn quick (ROLE: architect)
  → Known Context block
      │
      ▼
  ╔══════════════════════════╗
  ║   ⚡  STORM MODE ON  ⚡  ║
  ╚══════════════════════════╝
      │
      ▼
  ┌──────────────────────────────┐
  │  Brainstorm loop (persistent)│
  │                              │
  │  user message                │
  │       │                      │
  │       ▼                      │
  │  one idea + ASCII diagram    │
  │  + one follow-up question    │
  │       │                      │
  │  (repeat until stop signal)  │
  └──────────────────────────────┘
      │
  Exit triggers:
  "stop"       → 3-bullet summary
  "stop plan"  → write STORM_SEED.md
                 ⚡ STORM MODE OFF
```

---

## 10. plan — Plan File Generator

Creates the plan files that `build` and `team` consume.

```
plan <feature> [rigor]
      │
      ▼
  Read LESSONS.md
  (silently apply injections)
      │
      ▼
  STORM_SEED.md exists?
  yes → pre-fill answers
  no  → interview user
        (stories, layers, complexity)
      │
      ▼
  Optional targeted consults:
  ┌──────────────┬───────────────┐
  │ po           │ architect     │
  │ (scope       │ (cross-layer, │
  │  unclear)    │  risk present)│
  └──────┬───────┴──────┬────────┘
         └──────┬────────┘
                ▼
  Research codebase
  (patterns, rules, layer structure)
                │
                ▼
  Generate files:
  lite     → 4 files
  standard → 8 files
  strict   → 8 + audit notes
                │
                ▼
  Verify structure → Report
  "Next: continue <feature>"
```

---

## 11. build — Conversation Executor

Implements one conversation from the plan, verifies it, updates PROGRESS.md.

```
build <plan> [auto]
      │
      ▼
  Choose mode: auto / manual
      │
      ▼
  Pre-flight: git status clean?
  (not clean → stop, ask)
      │
      ▼
  Read PROGRESS.md → first TODO conv
  Read CONVERSATION_PROMPTS.md
      │
      ▼
  Two-phase builder:
  ┌──────────────────────────────┐
  │ Phase 1: analyze             │
  │   → NEEDS_CONTEXT block      │
  │   → none? skip Phase 2       │
  │                              │
  │ Phase 2: scout (if needed)   │
  │   → quick or scout per entry │
  │   → compress findings        │
  │                              │
  │ Phase 3: implement           │
  │   → builder with context     │
  └──────────────────────────────┘
      │
      ▼
  Run verify command
  (fail → fix, max 2 retries)
      │
      ▼
  Update PROGRESS.md → DONE
      │
  ┌───┴───────────────┐
  ▼                   ▼
auto                manual
  │                   │
auto-commit        "Remember
guide to next       to commit"
```

---

## 12. team — Full Feature Pipeline

Thin orchestrator. Reads `pathly/plans/<feature>/STATE.json`, routes to the correct
sub-skill for the current FSM state, then re-reads state and routes again until DONE.
Each sub-skill lives in `core/skills/team/` and handles exactly one stage.

```
team <feature> [rigor] [flags]      ← orchestrator (team.md)
      │
      ▼
  Parse args → recover STATE.json/EVENTS.jsonl
      │
  ┌───┴─────────────────────┐
  ▼ nano mode               ▼ normal (routes to sub-skills)
builder → reviewer          │
(≤2 files, inline)          │
                    ┌───────▼──────────────────────────┐
                    │ FSM state → sub-skill             │
                    │                                   │
                    │ IDLE/STORMING  → team/discover│
                    │ PLANNING       → team/plan   │
                    │ BUILDING       → team/build  │
                    │ REVIEWING      → team/review │
                    │ TESTING        → team/test   │
                    │ RETRO          → team/retro  │
                    │ BLOCKED_ON_HUMAN → wait for user  │
                    │ DONE           → stop             │
                    └───────────────────────────────────┘

Sub-skill responsibilities:

  team/discover  Stage 0 — 5-path discovery menu
                      (quick storm / skip / PRD / explore / full PO+storm)
                      → writes STATE.json → PLANNING, routes back

  team/plan      Stage 1+2 — architect storm + planner
                      rigor escalator offers extra files if signals fire
                      → writes STATE.json → BUILDING, routes back

  team/build     Stage 3a — analyze → scout → implement (one conv)
                      feedback routing: IMPL_QUESTIONS → planner
                                        DESIGN_QUESTIONS → architect
                      → writes STATE.json → REVIEWING, routes back

  team/review    Stage 3b — pre-scout + reviewer (per rigor)
                      feedback routing: ARCH_FEEDBACK → architect → rebuild
                                        REVIEW_FAILURES → builder (max 2)
                                        zero-diff stall → HUMAN_QUESTIONS
                      → writes STATE.json → BUILDING or TESTING, routes back

  team/test      Stage 4 — tester(analyze) → scout-flow → tester(test),
                      TEST_FAILURES → builder (max 2)
                      → writes STATE.json → RETRO, routes back

  team/retro     Stage 5 — quick → RETRO.md + LESSONS_CANDIDATE.md
                      → writes STATE.json → DONE, routes back

State is stored in two files per feature (filesystem-native, no Python required):
  pathly/plans/<feature>/STATE.json    — current FSM state snapshot
  pathly/plans/<feature>/EVENTS.jsonl  — append-only event log
```

---

## 13. debug — Bug Investigation Pipeline

Traces symptom → root cause → fix → verified resolution.

```
debug <symptom>
      │
      ▼
  INVESTIGATING
  Create pathly/debugs/<symptom>/
  Write SYMPTOM.md
      │
      ▼
  REPRODUCING
  scout → REPRO.md
      │
      ▼
  Tester pre-fix:
  [CONFIRMED]      → continue
  [NOT REPRODUCED] → stop (ask for more info)
  [PARTIAL]        → continue with caveat
      │
      ▼
  scout again → ROOT_CAUSE.md
      │
      ▼
  FIXING
  builder → FIX.md + commit
      │
      ▼
  VERIFYING
  Tester post-fix:
  [FIXED]      → continue to reviewer
  [NOT FIXED]  → retry builder (max 2)
  [REGRESSION] → write HUMAN_QUESTIONS.md, stop
      │
      ▼
  DONE
  reviewer: security + contracts only
  (no style, no unrelated issues)
      │
      ▼
  Print summary:
  root cause · fix · test status
```

---

## 14. explore — Codebase Investigation

Answers a question about the codebase. No code changes. No plan files.
Orchestrates the explorer agent through analyze → scout-flow → explore → conclude phases.

```
explore <topic>
      │
      ▼
  Frame the question
  Write EXPLORE.md:
  question | scope | success criterion
      │
  [User confirms framing]
      │
      ▼
  Phase 1: explorer(analyze)
  → NEEDS_CONTEXT block
  → none? skip Phase 2
      │
      ▼
  Phase 2: scout-flow (if NEEDS_CONTEXT)
  ROLE: explorer
  → compressed Scout Findings
      │
      ▼
  Phase 3: explorer(explore) + Scout Findings
  → writes TRACE.md
  (human question? → HUMAN_QUESTIONS.md, wait, retry)
      │
      ▼
  Phase 4: explorer(conclude)
  → writes CONCLUSIONS.md:
    answer | evidence | recommendation
    BUILD / SKIP / INVESTIGATE MORE
      │
      ▼
  Show conclusions. Offer:
  ┌──────────────────────────────┐
  │ 1. Graduate → team      │
  │ 2. Explore follow-up         │
  │ 3. Keep as reference         │
  │ 4. Archive                   │
  └──────────────────────────────┘
```

---

## 15. review — Code Reviewer

Checks staged or committed changes against architectural rules. Reports only.

```
review [staged | last | <file>]
      │
      ▼
  Get diff from git
      │
      ▼
  Spawn scout (ROLE: reviewer)
  → Applicable rules for changed files
    (ARCHITECTURE_PROPOSAL.md, rules/)
      │
      ▼
  Check each file:
  ┌──────────────────────────────┐
  │ Dependency direction         │
  │ Layer responsibility         │
  │ Naming conventions           │
  │ Scope (within conv boundary) │
  └──────────────────────────────┘
      │
      ▼
  PASS → "no violations"
  [ARCH] file:line → what + should be
  [IMPL] file:line → what + fix needed
  (never auto-fix — report only)
```

---

## 16. retro — Retrospective

Three focused questions → RETRO.md → lessons extracted.

```
retro <feature>
      │
      ▼
  Read PROGRESS.md +
  CONVERSATION_PROMPTS.md
      │
      ▼
  Ask 3 questions (one at a time):
  Q1: Conv sizing (too big/small)?
  Q2: Unexpected surprises?
  Q3: What was missing from plan?
      │
      ▼
  Compute cost summary
  from EVENTS.jsonl (if exists)
      │
      ▼
  Write RETRO.md:
  cost table | plan quality
  what worked | improvements
  seed for next storm
      │
      ▼
  Extract 1–3 lessons
  Append to LESSONS_CANDIDATE.md
      │
      ▼
  "Promote with: lessons"
```

---

## 17. lessons — Lesson Promoter

Finds repeating patterns across retros and writes them to active memory.

```
lessons
      │
      ▼
  Read:
  LESSONS_CANDIDATE.md
  + up to 6 recent RETRO.md files
      │
  (if neither found → "run retro first")
      │
      ▼
  Find patterns in 2+ features
  (same failure type, same stage)
      │
      ▼
  Write LESSONS.md:
  ┌──────────────────────────────┐
  │ max 12 lessons               │
  │ ordered by evidence count    │
  │ each lesson:                 │
  │   pattern → rule → injection │
  │   sources (feature list)     │
  └──────────────────────────────┘
      │
      ▼
  "Planner reads this on next plan"
```

---

## 18. archive — Feature Archiver

Moves a completed feature out of `pathly/plans/` after all gates pass.

```
archive <feature>
      │
      ▼
  Validate (all must pass):
  ┌──────────────────────────────┐
  │ ✓ pathly/plans/<feature>/ exists   │
  │ ✓ RETRO.md exists           │
  │ ✓ All conversations DONE    │
  │ ✓ No open feedback files    │
  └──────────────────────────────┘
  (any fails → stop + explain)
      │
      ▼
  mv pathly/plans/<feature>/
     → pathly/plans/.archive/<feature>/
      │
      ▼
  "Archived. Recoverable: git checkout"
  "pathly/plans/ is clean."
```

---

## 19. test — Acceptance Test Runner

Verifies acceptance criteria for a completed feature. Standalone alternative to
`team <feature> test` — usable without running the full pipeline.
Orchestrates tester through analyze → scout-flow → test phases, then fix loop.

```
test <feature>
      │
      ▼
  Pre-flight:
  all PROGRESS conversations DONE?
  USER_STORIES.md exists?
  (no → stop, explain)
      │
      ▼
  Phase 1: tester(analyze)
  → NEEDS_CONTEXT block
      │
      ▼
  Phase 2: scout-flow (if NEEDS_CONTEXT)
  ROLE: tester
  → Test Context
      │
      ▼
  Phase 3: tester(test) + Test Context
  → PASS / FAIL / NOT COVERED per criterion
      │
  ┌───┴──────────────────┐
  ▼                      ▼
TEST_FAILURES.md?     all pass
  │                      │
  ▼                      ▼
builder fixes         Report +
re-run tester         offer retro
(max 2 cycles)
```

---

## 20. verify-state — Pipeline Health Check

Read-only. Detects stale files, drift, and FSM inconsistencies. Never auto-fixes.

```
verify-state [feature | all]
      │
      ▼
  For each feature:
      │
      ▼
  Check A: Feedback files
  ┌──────────────────────────────┐
  │ orphan? (event not in log)   │
  │ TTL expired?                 │
  │ stale? (no commits since)    │
  └──────────────────────────────┘
      │
  Check B: PROGRESS drift
  (DONE convs with no git diff)
      │
  Check C: Dead references
  (plan mentions files not on disk)
      │
  Check D: FSM consistency
  (STATE.json vs EVENTS.jsonl
   vs open feedback files)
      │
      ▼
  Report:
  ✓  All clear
  ⚠  [ORPHAN FEEDBACK]
  ⚠  [EXPIRED FEEDBACK]
  ⚠  [STALE FEEDBACK]
  ⚠  [PROGRESS DRIFT]
  ⚠  [DEAD REFERENCE]
  ⚠  [STATE DRIFT]
  ⚠  [CORRUPT STATE / EVENTS]

  (report only — never auto-fix)
```

---

## 21. po — Product Owner Consultation

Opens a structured Product Owner discussion for a feature. Use it to clarify
requirements, validate scope, or resolve ambiguity before planning or mid-flow.

```
po [feature]
      │
      ▼
  Detect feature context
  (from args or active pathly/plans/)
      │
      ▼
  Spawn po agent:
  ┌──────────────────────────────────┐
  │ Reads: USER_STORIES.md, plans    │
  │ Asks clarifying questions        │
  │ Validates scope, ACs, criteria   │
  │ No code or plan edits            │
  └──────────────────────────────────┘
      │
      ▼
  Write PO_NOTES.md:
  pathly/plans/<feature>/PO_NOTES.md
      │
      ▼
  "Next: /pathly plan <feature>"
```

---

## 22. scout-path — Targeted Code-Path Scout

**Called by other skills, not by users directly.**

Receives a `NEEDS_CONTEXT` block from a calling skill (plan, build, review, etc.),
spawns scout agents in parallel, and returns a compressed summary of findings.

```
scout-path is invoked by:
  plan / build / review / debug / explore / test
      │
      ▼
  Receives NEEDS_CONTEXT block + ROLE + FEATURE
      │
      ▼
  Spawn scout agents in parallel
  (one per NEEDS_CONTEXT entry)
      │
      ▼
  Compress findings → Scout Findings block
      │
      ▼
  Return to calling skill
```

---

## 23. fix — Open Feedback Resolver

Resolves open feedback files for an active feature. Auto-detects the feature
from `STATE.json` or accepts an explicit topic argument.

```
fix [feature]
      │
      ▼
  Resolve TOPIC (arg or auto-detect from pathly/plans/)
      │
      ▼
  Read feedback/ for open files
  (priority: HUMAN_QUESTIONS > ARCH_FEEDBACK > DESIGN_QUESTIONS
             > IMPL_QUESTIONS > REVIEW_FAILURES > TEST_FAILURES)
      │
      ▼
  Spawn appropriate agent to resolve highest-priority file
      │
      ▼
  Re-check feedback/ → repeat until clear or blocked
```

---

## 24. ff — Fast-Forward FSM State

Advances the FSM to the next state without running the current stage agent.
Thin wrapper around the `pathly-ff` CLI command.

```
/pathly ff [feature]
      │
      ▼
  pathly-ff $ARGUMENTS
      │
      ▼
  Print output as returned
  (command not found → "Run pathly-setup first")
```

---

## 25. back — Roll Back FSM State

Rolls back the FSM one state with user confirmation. Does not undo git commits.
Thin wrapper around the `pathly-back` CLI command.

```
/pathly back [feature]
      │
      ▼
  pathly-back $ARGUMENTS
      │
      ▼
  Print output as returned
  (command not found → "Run pathly-setup first")
```

---

## 26. status — Cross-Feature Dashboard

Shows all active Pathly flows and their current FSM state.
Thin wrapper around the `pathly-status` CLI command.

```
/pathly status
      │
      ▼
  pathly-status $ARGUMENTS
      │
      ▼
  Print output as returned
  (command not found → "Run pathly-setup first")
```

---

## 27. log — FSM Event Timeline

Shows a readable timeline of FSM events for the active or named feature.
Thin wrapper around the `pathly-log` CLI command.

```
/pathly log [feature]
      │
      ▼
  pathly-log $ARGUMENTS
      │
      ▼
  Print output as returned
  (command not found → "Run pathly-setup first")
```

---

## 28. design — Visual Spec Generator

Generates a `DESIGN.md` artifact that `build` uses as its visual spec.
Runs **after plan, before build**. Detects the active feature and tech stack
automatically, then invokes the designer agent to produce layout, component,
and style decisions.

```
design [feature]
      │
      ▼
  Detect active feature + tech stack
  (package.json → react/next/vue/svelte/astro)
      │
      ▼
  Spawn designer agent:
  → generates DESIGN.md:
    layout | components | colors
    typography | interactions
      │
      ▼
  Write pathly/plans/<feature>/DESIGN.md
  "Next: /pathly build <feature>"
```

---

## 29. log-agent-done — Agent Telemetry Recorder

Writes an `AGENT_DONE` event to `EVENTS.jsonl` and POSTs telemetry to the FSM
HTTP backend. Called automatically by agents at the end of each completed stage.
Can be invoked directly for manual telemetry reporting.

```
log-agent-done $ARGUMENTS   (JSON object)
      │
      ▼
  Parse required: agent, feature, conversation, result
      │
      ▼
  Compute cost_usd:
  ┌───────────────────────────────────────┐
  │ Priority 1: caller-provided cost_usd  │
  │ Priority 2: Claude pricing table      │
  │   (input+output tokens × rate/MTok)   │
  │ Priority 3: non-Claude → cost_usd=0   │
  │   (print advisory, continue)          │
  └───────────────────────────────────────┘
      │
      ▼
  Append AGENT_DONE to EVENTS.jsonl:
  pathly/plans/<feature>/EVENTS.jsonl
      │
      ▼
  POST to http://127.0.0.1:8765/record_activity
  (server unavailable → skip telemetry, do not fail)
```

Supported models: Claude (cost computed), OpenAI, Gemini, and others (pass
`cost_usd` directly; cost computation skipped for non-Claude models).

---

## Transition-Action Skills (internal, orchestrator-only)

These two skills are not user-facing. The orchestrator spawns them automatically
as `transition_actions` in flow YAMLs when specific state transitions occur.

### commit

Commits staged changes to git. Guards against committing when feedback files are open.

```
Inputs: message, storage_path, topic
  │
  ▼
Check feedback/ for open files
  (if any exist → suppress commit)
  │
  ▼
git add -A && git commit -m "<message>"
  │
  ▼
Append ACTION_DONE event to EVENTS.jsonl
```

Invoked by the orchestrator on: `BUILDING->REVIEWING` (team flow)

### archive-artifacts

Copies active feedback files to `pathly/pipeline-walkthrough/<topic>/artifacts/`
for record-keeping before they are deleted by the resolving agent.

```
Inputs: storage_path, topic, conv
  │
  ▼
Collect *.md files from feedback/
  │
  ▼
Determine attempt number (M)
  │
  ▼
Copy to: pipeline-walkthrough/<topic>/artifacts/
  <FILENAME>_conv<conv>_attempt<M>.md
  │
  ▼
Append ACTION_DONE event to EVENTS.jsonl
```

Invoked by the orchestrator on: `RETRO->DONE` (team), `VERIFYING->DONE` (debug), `CONCLUDING->DONE` (explore)

---

## Skill Map — Who Does What

```
  INPUT                SKILL          OUTPUT
  ─────────────────────────────────────────────────────
  idea / intent   ──►  storm     ──►  STORM_SEED.md
  STORM_SEED.md   ──►  plan      ──►  pathly/plans/<feature>/
  any PRD file    ──►  prd-import──►  pathly/plans/<feature>/
  pathly/plans/<feature> ──►  build     ──►  code + PROGRESS.md
  pathly/plans/<feature> ──►  team ──►  full pipeline
  git diff        ──►  review    ──►  violations report
  PROGRESS.md     ──►  retro     ──►  RETRO.md
  RETRO.md files  ──►  lessons   ──►  LESSONS.md
  LESSONS.md      ──►  plan      ──►  (injected silently)
  RETRO.md + done ──►  archive   ──►  pathly/plans/.archive/
  question        ──►  explore   ──►  CONCLUSIONS.md
  pathly/plans/<feature> ──►  test      ──►  test report + TEST_FAILURES.md
  bug symptom     ──►  debug     ──►  fix + FIX.md
  any feature     ──►  verify-   ──►  health report
                       state
  feature work    ──►  po        ──►  PO_NOTES.md
  (by other skills)──► scout-    ──►  Scout Findings block
                       path
  open feedback   ──►  fix       ──►  resolved feedback files
  (CLI wrapper)   ──►  ff        ──►  FSM advanced one state
  (CLI wrapper)   ──►  back      ──►  FSM rolled back one state
  (CLI wrapper)   ──►  status    ──►  all-feature dashboard
  (CLI wrapper)   ──►  log       ──►  event timeline
  plan done       ──►  design    ──►  DESIGN.md visual spec
  ─────────────────────────────────────────────────────
  TRANSITION ACTIONS (spawned by orchestrator, not users)
  BUILDING→REVIEWING──► commit   ──►  git commit
  RETRO→DONE       ──►  archive- ──►  pipeline-walkthrough/
                        artifacts     artifacts/
  ─────────────────────────────────────────────────────
  MACHINE CONTROLS (no output files, change only state)
  /pathly start   ──►  start     ──►  welcome menu
  /pathly go      ──►  go        ──►  routes to skill
  /pathly pause   ──►  pause     ──►  PAUSED in PROGRESS
  /pathly meet    ──►  meet      ──►  consult note
  /pathly end     ──►  end       ──►  → retro or close
  /pathly help    ──►  help      ──►  state-aware menu
  /pathly         ──►  pathly    ──►  dispatches above
```

---

## Feedback File Protocol

All pipeline communication between agents happens through files in
`pathly/plans/<feature>/feedback/`. A file present = issue open. Deleted = resolved.

```
Priority order (highest to lowest):
  HUMAN_QUESTIONS.md   any agent   → user  (BLOCKS pipeline)
  ARCH_FEEDBACK.md     reviewer    → architect (BLOCKING)
  DESIGN_QUESTIONS.md  builder     → architect
  IMPL_QUESTIONS.md    builder     → planner
  REVIEW_FAILURES.md   reviewer    → builder
  TEST_FAILURES.md     tester      → builder
```

---

_Generated 2026-05-28 — update this file after any core/skills/ change._
