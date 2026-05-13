# agent-architecture-refactor — Conversation Prompts

---

## Pre-flight (run before Conv 1)

```
grep -rl "scout-path" src/pathly_data/core/skills/
```

Expected files: `build.md`, `review.md`, `test.md`, `explore.md`, `team/build.md`, `team/test.md`, `scout-path.md`, and possibly `team/discover.md`. If a file is missing, check FEATURE_INDEX.md paths before proceeding.

---

## Conversation 1 — Scout-pattern migration

**Stories:** S1.1, S1.2

```
Read plans/agent-architecture-refactor/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement agent-architecture-refactor Conversation 1 (Phases 1–6) from plans/agent-architecture-refactor/IMPLEMENTATION_PLAN.md.

Before editing anything: read each file listed below and confirm it exists at the stated path.

Codebase files this conversation touches:
- src/pathly_data/core/skills/build.md — replace Call `scout-path` with Spawn scout agent (~line 54)
- src/pathly_data/core/skills/review.md — replace call `scout-path` with Spawn scout agent (~line 24)
- src/pathly_data/core/skills/test.md — replace call scout-path with Spawn scout agent (~line 66)
- src/pathly_data/core/skills/explore.md — two lines: ~83 and ~166
- src/pathly_data/core/skills/scout-path.md — add standalone-only note
- src/pathly_data/core/skills/team/build.md — replace Call `scout-path` with Spawn scout agent (~line 77)
- src/pathly_data/core/skills/team/test.md — replace Call scout-path with Spawn scout agent (~line 65)
- src/pathly_data/core/skills/team/discover.md — subagents table doc update

Reference pattern (read but do not modify):
- src/pathly_data/core/skills/team/review.md — already correct; replicate this spawn pattern

Phase by phase:

Phase 1: In build.md and review.md, replace the Call `scout-path` instruction with a Spawn **scout** agent inline delegation block matching team/review.md Phase 2.

Phase 2: In test.md, replace `call **scout-path**` with a Spawn **scout** agent inline delegation block.

Phase 3: In team/build.md and team/test.md, replace Call `scout-path` with a Spawn **scout** agent inline delegation block.

Phase 4: In explore.md, apply exactly two changes:
  - Replace `call **scout-path**` (~line 83) with Spawn **scout** agent
  - Replace `Explorer + scout-path only` (~line 166) with `Explorer + scout agent only`

Phase 5: In scout-path.md, add a note after the opening callout:
  > Note: scout-path is for standalone invocation only. Pipeline stages spawn the scout agent directly — they do not call scout-path.

Phase 6: In team/discover.md, update the subagents table entry referencing scout-path to describe the direct spawn pattern.

Rules:
- Do NOT modify team/review.md.
- Do NOT modify any agent .md files or YAML files.
- Do NOT touch any files outside the 8 listed above.

Verify:
  grep -rn "scout-path" src/pathly_data/core/skills/build.md src/pathly_data/core/skills/review.md src/pathly_data/core/skills/test.md src/pathly_data/core/skills/explore.md src/pathly_data/core/skills/team/build.md src/pathly_data/core/skills/team/test.md
Expected: no output.
  git diff --stat — confirm only the 8 listed files are modified.

After verification: update plans/agent-architecture-refactor/PROGRESS.md Phases 1–6 and Conv 1 to DONE.

Recovery: if a file is corrupted, run `git checkout -- <file>` and retry that phase only.
```

---

## Conversation 2 — Worker agent contracts + YAML

**Stories:** S2.1, S2.2, S2.3, S2.4, S2.5

```
Read plans/agent-architecture-refactor/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement agent-architecture-refactor Conversation 2 (Phases 7–13) from plans/agent-architecture-refactor/IMPLEMENTATION_PLAN.md.

Before editing anything: read each file listed below in full.

Codebase files this conversation touches:
- src/pathly_data/core/agents/tester.md — add scout spawn section
- src/pathly_data/core/agents/builder.md — upgrade delegation pattern (add way of thinking + constraints)
- src/pathly_data/core/agents/planner.md — add scout spawn section, remove no-scout rule
- src/pathly_data/adapters/claude/_meta/tester.yaml — can_spawn update
- src/pathly_data/adapters/codex/_meta/tester.yaml — can_spawn update
- src/pathly_data/adapters/claude/_meta/planner.yaml — can_spawn update
- src/pathly_data/adapters/codex/_meta/planner.yaml — can_spawn update

Reference files (read but do not modify):
- src/pathly_data/core/agents/reviewer.md — reference for full delegation pattern structure
- src/pathly_data/core/agents/architect.md — reference for full delegation pattern structure

Phase 7: In tester.md, add a subagent delegation section after the existing `## Phase: analyze` block.
  Match the section title and structure of reviewer.md exactly.
  Include: type: scout (multi-file test infrastructure investigation), type: quick (single-file lookups).
  Include `way of thinking`: look for test patterns, coverage gaps, fixture paths, and untested acceptance criteria paths.
  Include `constraints`: read only, do not fix code, stay within stated scope.

Phase 8: In builder.md, find the existing scout delegation block.
  Add `way of thinking`: look for existing patterns to follow, utility functions, interface shapes, import paths, and naming conventions — what a builder needs to implement correctly without inventing new patterns.
  Add `constraints`: read only, do not suggest fixes or refactors, stay within stated scope.
  Do not alter any other content in builder.md.

Phase 9: In planner.md:
  Remove the line: "Planner does not spawn scouts — codebase investigation is builder's domain."
  Add a scout delegation section consistent with reviewer.md structure.
  Include: type: scout (cross-file architecture investigation — understand current state, existing patterns, integration boundaries, delivered scope), type: quick (single-file lookups).
  Include `way of thinking`: understand current architecture and what already exists to plan integration accurately. Do not make HOW decisions — that belongs to architect and builder.
  Include `constraints`: read only, do not suggest implementation approaches, scope to existing state only.

Phase 10: In src/pathly_data/adapters/claude/_meta/tester.yaml, change:
  can_spawn: [builder]  →  can_spawn: [quick, scout, builder]
  Change only that line.

Phase 11: In src/pathly_data/adapters/codex/_meta/tester.yaml, apply the identical change as Phase 10.

Phase 12: In src/pathly_data/adapters/claude/_meta/planner.yaml, change:
  can_spawn: [quick, web-researcher]  →  can_spawn: [quick, scout, web-researcher]
  Change only that line.

Phase 13: In src/pathly_data/adapters/codex/_meta/planner.yaml, apply the identical change as Phase 12.

Rules:
- Do NOT modify po.md — PO scout exclusion is intentional.
- Do NOT modify reviewer.md or architect.md — they are already correct references.
- Do NOT modify explorer.md — that is Conv 3 scope.
- Do NOT change any YAML field other than can_spawn.

Verify:
  grep "can_spawn" src/pathly_data/adapters/claude/_meta/tester.yaml   → can_spawn: [quick, scout, builder]
  grep "can_spawn" src/pathly_data/adapters/codex/_meta/tester.yaml    → can_spawn: [quick, scout, builder]
  grep "can_spawn" src/pathly_data/adapters/claude/_meta/planner.yaml  → can_spawn: [quick, scout, web-researcher]
  grep "can_spawn" src/pathly_data/adapters/codex/_meta/planner.yaml   → can_spawn: [quick, scout, web-researcher]
  git diff --stat — confirm only the 7 listed files are modified.

After verification: update plans/agent-architecture-refactor/PROGRESS.md Phases 7–13 and Conv 2 to DONE.

Recovery: if a YAML file is malformed, run `git checkout -- <file>` and retry that phase only.
```

---

## Conversation 3 — Explorer agent parity

**Stories:** S3.1, S3.2

```
Read plans/agent-architecture-refactor/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement agent-architecture-refactor Conversation 3 (Phases 14–16) from plans/agent-architecture-refactor/IMPLEMENTATION_PLAN.md.

Before editing anything: read explorer.md in full and read both explorer.yaml files.

Codebase files this conversation touches:
- src/pathly_data/core/agents/explorer.md — add scout spawn section, remove no-spawn rule
- src/pathly_data/adapters/claude/_meta/explorer.yaml — add can_spawn field
- src/pathly_data/adapters/codex/_meta/explorer.yaml — add can_spawn field

Reference files (read but do not modify):
- src/pathly_data/core/agents/reviewer.md — reference for delegation pattern structure

Phase 14: In explorer.md:
  Remove the line: "Do NOT spawn additional agents."
  Add a scout delegation section (before "## Hard constraints") consistent with reviewer.md structure.
  Include: type: scout (trace code paths, find structural patterns, map dependencies relevant to the exploration question), type: quick (single-file lookups).
  Include `way of thinking`: look for code paths, structural dependencies, and patterns that directly answer the exploration question. Report facts — do not recommend changes.
  Include `constraints`: scouts are terminal and read-only. Explorer remains read-only on production code — scouts may not write any files.
  Do not alter any other content in explorer.md.

Phase 15: In src/pathly_data/adapters/claude/_meta/explorer.yaml, add:
  can_spawn: [scout, quick]
  Add this as a new line after the existing fields. Do not change any other field.

Phase 16: In src/pathly_data/adapters/codex/_meta/explorer.yaml, apply the identical change as Phase 15.

Rules:
- Do NOT modify any other agent contracts or YAML files.
- Scouts spawned by explorer remain terminal — do not add web-researcher to explorer's spawn list.

Verify:
  grep "can_spawn" src/pathly_data/adapters/claude/_meta/explorer.yaml  → can_spawn: [scout, quick]
  grep "can_spawn" src/pathly_data/adapters/codex/_meta/explorer.yaml   → can_spawn: [scout, quick]
  grep "Do NOT spawn" src/pathly_data/core/agents/explorer.md           → no output
  git diff --stat — confirm only the 3 listed files are modified.

After verification: update plans/agent-architecture-refactor/PROGRESS.md Phases 14–16 and Conv 3 to DONE.

Recovery: if explorer.md is inconsistent after editing, run `git checkout -- src/pathly_data/core/agents/explorer.md` and retry Phase 14.
```

---

## Conversation 4 — Orchestrator conversion

**Stories:** S4.1, S4.2

```
Read plans/agent-architecture-refactor/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement agent-architecture-refactor Conversation 4 (Phases 17–18) from plans/agent-architecture-refactor/IMPLEMENTATION_PLAN.md.

Before editing anything: read both orchestrator.md and team.md in full.

**Merge rule for Phase 17:** orchestrator.md may already contain partial versions of the sections you are adding (git commit logic, PROGRESS.md updates, a routing table). If a section already exists, update or merge it — do NOT append a duplicate section. The done-when criteria check for content presence, not for new additions, so a merge is always acceptable. If you are unsure whether two sections describe the same concept, flag the ambiguity in PROGRESS.md before editing.

Codebase files this conversation touches:
- src/pathly_data/core/agents/orchestrator.md — add four FSM sections from team.md
- src/pathly_data/core/skills/team.md — convert to thin launcher

Phase 17: Add four sections to orchestrator.md, placed before "## What you must NOT do":

  1. Git commit section — sourced from team.md "Orchestrator responsibilities between stages":
     After BUILDING → REVIEWING (autoFlow): git add -A + git commit feat message.
     After REVIEWING → TESTING (reviewer passed): update PROGRESS.md + git commit chore message.

  2. PROGRESS.md update logic — mark conv row DONE, mark all Phase Detail rows DONE,
     set overall Status COMPLETE when all convs done.

  3. Team pipeline routing table:
     | FSM state | Sub-skill |
     | IDLE / PO_DISCUSSING / EXPLORING / STORMING | team/discover |
     | PLANNING | team/plan |
     | BUILDING | team/build |
     | REVIEWING | team/review |
     | TESTING | team/test |
     | RETRO | team/retro |
     | BLOCKED_ON_HUMAN | print + wait + restore prior state + re-route |
     | DONE | print complete and stop |

  4. Artifact archiving dual-write rule — sourced from team.md "Artifact archiving" section:
     copy every feedback file written to plans/<feature>/feedback/ also to
     pipeline-walkthrough/<feature>/artifacts/ with the naming convention.

Phase 18: Convert team.md to thin launcher:

  KEEP unchanged:
  - ## Argument parsing
  - ## Feature detection
  - ## Mode selection
  - ## Nano mode (all five steps)

  REMOVE (these sections move to orchestrator.md):
  - ## FSM operations (filesystem-native)
  - ## State recovery
  - ## Entry stage override
  - ## Routing (the routing table)
  - ## Orchestrator responsibilities between stages
  - ## Artifact archiving — dual-write rule

  ADD between ## Mode selection and ## Nano mode:
  A section titled "## Spawn orchestrator" with:
    After mode selection is complete (autoFlow is set), spawn the **orchestrator** agent with:
    - FEATURE: [parsed feature name]
    - rigor: [parsed rigor]
    - autoFlow: [true/false]
    - entryStage: [parsed entryStage, default: discovery]
    The orchestrator handles all FSM state recovery, routing, git commits, PROGRESS.md updates,
    and artifact archiving. Do not perform these actions in team.md.

  The spawn section must appear before nano mode so that nano mode remains a bypass
  (nano tasks never reach the spawn instruction).

Rules:
- Nano mode must stay inline in team.md — do not move it to orchestrator.md.
- Do NOT modify any skill, YAML, or other agent files.

Verify:
  grep -n "FSM operations\|State recovery\|routing table" src/pathly_data/core/skills/team.md
  → no output

  grep -n "orchestrator" src/pathly_data/core/skills/team.md
  → at least one line in the spawn section

  grep -n "dual-write\|routing table\|PROGRESS.md" src/pathly_data/core/agents/orchestrator.md
  → lines present

  grep -n "nano mode\|Nano mode" src/pathly_data/core/skills/team.md
  → must return matches (confirms nano mode survived section removal)

  git diff --stat — confirm only the 2 listed files are modified.

After verification: update plans/agent-architecture-refactor/PROGRESS.md Phases 17–18, Conv 4 to DONE, and overall Status to COMPLETE.

Recovery: Phase 17 and Phase 18 can be retried independently — run `git checkout -- <file>` on the affected file and retry that phase only.
```
