# Pathly Skills Overview

19 canonical skills. Each lives in `core/skills/`. Adapters translate them to
host-native surfaces. This document is the authoritative reference.

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
  plans/, PROGRESS.md, git status
      │
      ▼
  Classify intent:
  ┌─────────────────────────────────────┐
  │ tiny_change → team-flow nano        │
  │ new_feature → team-flow <rigor>     │
  │ brainstorm  → storm <topic>         │
  │ resume      → team-flow build       │
  │ test        → team-flow test        │
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
  Scan plans/ (skip .archive/)
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
  plans/<feature>/consults/
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
  Scan plans/ for IN PROGRESS
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
  │ storm-done   → plan / team-flow    │
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

Creates the plan files that `build` and `team-flow` consume.

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

## 12. team-flow — Full Feature Pipeline

Thin orchestrator. Reads `plans/<feature>/STATE.json`, routes to the correct
sub-skill for the current FSM state, then re-reads state and routes again until DONE.
Each sub-skill lives in `core/skills/team-flow/` and handles exactly one stage.

```
team-flow <feature> [rigor] [flags]      ← orchestrator (team-flow.md)
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
                    │ IDLE/STORMING  → team-flow/discover│
                    │ PLANNING       → team-flow/plan   │
                    │ BUILDING       → team-flow/build  │
                    │ REVIEWING      → team-flow/review │
                    │ TESTING        → team-flow/test   │
                    │ RETRO          → team-flow/retro  │
                    │ BLOCKED_ON_HUMAN → wait for user  │
                    │ DONE           → stop             │
                    └───────────────────────────────────┘

Sub-skill responsibilities:

  team-flow/discover  Stage 0 — 5-path discovery menu
                      (quick storm / skip / PRD / explore / full PO+storm)
                      → writes STATE.json → PLANNING, routes back

  team-flow/plan      Stage 1+2 — architect storm + planner
                      rigor escalator offers extra files if signals fire
                      → writes STATE.json → BUILDING, routes back

  team-flow/build     Stage 3a — analyze → scout → implement (one conv)
                      feedback routing: IMPL_QUESTIONS → planner
                                        DESIGN_QUESTIONS → architect
                      → writes STATE.json → REVIEWING, routes back

  team-flow/review    Stage 3b — pre-scout + reviewer (per rigor)
                      feedback routing: ARCH_FEEDBACK → architect → rebuild
                                        REVIEW_FAILURES → builder (max 2)
                                        zero-diff stall → HUMAN_QUESTIONS
                      → writes STATE.json → BUILDING or TESTING, routes back

  team-flow/test      Stage 4 — scout + tester, TEST_FAILURES → builder (max 2)
                      → writes STATE.json → RETRO, routes back

  team-flow/retro     Stage 5 — quick → RETRO.md + LESSONS_CANDIDATE.md
                      → writes STATE.json → DONE, routes back

State is stored in two files per feature (filesystem-native, no Python required):
  plans/<feature>/STATE.json    — current FSM state snapshot
  plans/<feature>/EVENTS.jsonl  — append-only event log
```

---

## 13. debug — Bug Investigation Pipeline

Traces symptom → root cause → fix → verified resolution.

```
debug <symptom>
      │
      ▼
  INVESTIGATING
  Create debugs/<symptom>/
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
  Spawn scout (READ-ONLY)
      │
      ▼
  Write TRACE.md (file:line findings)
  Append ## Findings to EXPLORE.md
      │
      ▼
  Spawn quick → Write CONCLUSIONS.md:
  answer | evidence | recommendation
  BUILD / SKIP / INVESTIGATE MORE
      │
      ▼
  Show conclusions. Offer:
  ┌──────────────────────────────┐
  │ 1. Graduate → team-flow      │
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

Moves a completed feature out of `plans/` after all gates pass.

```
archive <feature>
      │
      ▼
  Validate (all must pass):
  ┌──────────────────────────────┐
  │ ✓ plans/<feature>/ exists   │
  │ ✓ RETRO.md exists           │
  │ ✓ All conversations DONE    │
  │ ✓ No open feedback files    │
  └──────────────────────────────┘
  (any fails → stop + explain)
      │
      ▼
  mv plans/<feature>/
     → plans/.archive/<feature>/
      │
      ▼
  "Archived. Recoverable: git checkout"
  "plans/ is clean."
```

---

## 19. verify-state — Pipeline Health Check

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

## Skill Map — Who Does What

```
  INPUT                SKILL          OUTPUT
  ─────────────────────────────────────────────────────
  idea / intent   ──►  storm     ──►  STORM_SEED.md
  STORM_SEED.md   ──►  plan      ──►  plans/<feature>/
  any PRD file    ──►  prd-import──►  plans/<feature>/
  plans/<feature> ──►  build     ──►  code + PROGRESS.md
  plans/<feature> ──►  team-flow ──►  full pipeline
  git diff        ──►  review    ──►  violations report
  PROGRESS.md     ──►  retro     ──►  RETRO.md
  RETRO.md files  ──►  lessons   ──►  LESSONS.md
  LESSONS.md      ──►  plan      ──►  (injected silently)
  RETRO.md + done ──►  archive   ──►  plans/.archive/
  question        ──►  explore   ──►  CONCLUSIONS.md
  bug symptom     ──►  debug     ──►  fix + FIX.md
  any feature     ──►  verify-   ──►  health report
                       state
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
`plans/<feature>/feedback/`. A file present = issue open. Deleted = resolved.

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

_Generated 2026-05-11 — update this file after any core/skills/ change._
