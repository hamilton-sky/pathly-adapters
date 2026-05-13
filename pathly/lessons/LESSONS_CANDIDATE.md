# Lessons Candidate

Patterns extracted from retros. Promote to LESSONS.md via `/lessons`.

---

## [docs-sync] Builder acts on plan-baked facts instead of re-verifying live paths

### Pattern
Builder agents edit files based on paths provided in the conversation prompt without first confirming those paths exist and are current in the live repo, causing incorrect edits and multiple review cycles.

### Rule
MUST include an explicit "verify before edit" step in every conversation prompt that touches paths, module names, or entry points — instructing the builder to glob/read the live repo and correct any discrepancy before making changes.

### Injection
- Add to `CONVERSATION_PROMPTS.md` preamble: "Before making any edits, verify the following paths exist in the live repo: `[list paths]`. Correct any discrepancy between the plan's stated paths and reality before proceeding."
- Add to `IMPLEMENTATION_PLAN.md` phase header: "Criticality: low/medium/high — high means extra verification step required."

### Source
Feature: docs-sync | Stage: implementation | Date: 2026-05-11

---

## [docs-sync] No feature-folder index causes agent orientation overhead

### Pattern
Agents spend multiple tool calls globbing and reading plan files to orient themselves because there is no single entry point that lists all files in the feature folder and their roles.

### Rule
MUST create a `FEATURE_INDEX.md` in every feature folder at planning time, listing every plan file with a one-line description of its role and which agent reads it.

### Injection
- Add to planner output: create `plans/<feature>/FEATURE_INDEX.md` as the first file, before USER_STORIES.md.
- Template entry: `| File | Written by | Read by | Purpose |` — one row per plan file.

### Source
Feature: docs-sync | Stage: planning | Date: 2026-05-11

---

## [docs-sync] Implementation plan phases not aligned to PROGRESS.md rows

### Pattern
The implementation plan lists fixes as prose phases but PROGRESS.md tracks at the conversation level, leaving no task-level bridge. The planner fills PROGRESS.md manually, creating drift between the plan and actual tracked work.

### Rule
MUST map each IMPLEMENTATION_PLAN phase to exactly one PROGRESS.md conversation row — one phase = one conversation = one builder prompt.

### Injection
- Add to `IMPLEMENTATION_PLAN.md` template: each phase header must carry a `Conversation: N` tag that matches the corresponding row in PROGRESS.md.
- Add to planner instructions: "After writing IMPLEMENTATION_PLAN.md, verify that every phase maps to exactly one row in PROGRESS.md before writing CONVERSATION_PROMPTS.md."

### Source
Feature: docs-sync | Stage: planning | Date: 2026-05-11

---

## [parallel-scout-standard] Multi-file conversations are too large for reliable builder execution

### Pattern
Conversations that touch 3–4 files of the same type (skills, agents) accumulate too much scope, making it harder to verify and easier to introduce inconsistencies across files.

### Rule
MUST scope each conversation to at most one file per category — one skill file or one agent file per conversation, not a batch. Each phase must carry an explicit file path and done-condition at all rigor levels (lite included).

### Injection
- Add to `CONVERSATION_PROMPTS.md` splitting rule: "If a conversation touches more than one file of the same type (skill, agent, config), split into separate conversations — one per file."
- Add to each phase in `IMPLEMENTATION_PLAN.md`: `**File:** <exact path>` and `**Done when:** <observable condition>` — required at all rigor levels.

### Source
Feature: parallel-scout-standard | Stage: implementation | Date: 2026-05-11

---

## [parallel-scout-standard] Pre-loading file paths and done-conditions eliminates agent orientation overhead

### Pattern
Agents without explicit file paths and done-conditions in their task spend 4–6 tool calls on orientation (reading FEATURE_INDEX, globbing for files, re-reading the plan to understand "done") before any real work starts. This compounds across retries and continuation sessions.

### Rule
MUST include an explicit `File:` path and `Done when:` condition in every phase of every plan, at all rigor levels — not just standard/strict. The planning cost is paid once; the orientation savings are paid on every builder run.

### Injection
- Add to every phase in `IMPLEMENTATION_PLAN.md`: `**File:** <exact path to file being created/modified>` and `**Done when:** <one observable sentence — what is true when this phase is complete>`.
- Depth scales by rigor: lite = path + done-condition; standard = + verify command; strict = + verify command + rollback note.

### Source
Feature: parallel-scout-standard | Stage: retro discussion | Date: 2026-05-11

---

## [parallel-scout-standard] Flow diagram template not offered for orchestration features

### Pattern
Features that introduce new calling conventions or orchestration patterns (like scout-flow) benefit from a visual flow diagram during planning, but the plan skill only offers ASCII diagrams and does not prompt for one when the feature is orchestration-heavy.

### Rule
MUST offer the flow diagram template when a feature introduces a new inter-agent calling convention, sub-skill, or orchestration pattern.

### Injection
- Add to `plan.md` Step 2 (Understand The Feature): "If the feature introduces a new calling convention, sub-skill, or orchestration pattern, include a `FLOW_DIAGRAM.md` regardless of rigor level."

### Source
Feature: parallel-scout-standard | Stage: planning | Date: 2026-05-11

---

## [agent-architecture-refactor] Narrow verify scope misses files not named in the conversation prompt

### Pattern
Conv 1 listed 8 explicit skill files and scoped its verify command to only those files. team/plan.md also had scout-path references but was not in the prompt's file list — the verify command passed, but the tester caught 4 residual references at test time, requiring an extra fix cycle.

### Rule
MUST write the done-condition verify command to cover the entire affected directory, not just the files the conversation explicitly lists. For "replace X across all skills" features, grep the full `src/pathly_data/core/skills/` tree — a miss in the file list is still caught.

### Injection
- Add to Conv 1 verify in `CONVERSATION_PROMPTS.md`: "grep -rn 'scout-path' src/pathly_data/core/skills/ — expected: no output" (full tree, not per-file)
- Add to plan phase template: "Verify scope: if the feature eliminates a pattern globally, the done-condition must grep the entire affected tree, not the explicit file list."

### Source
Feature: agent-architecture-refactor | Stage: test | Date: 2026-05-13

---

## [agent-architecture-refactor] YAML capability expansions need a cross-file audit verify step

### Pattern
After adding `can_spawn` to multiple YAML files across claude/ and codex/ adapters, there is no verify command that confirms all YAML files are consistent. A missed file would compile silently but cause a runtime capability mismatch between adapters.

### Rule
MUST include a single grep that covers all adapter YAML files for the changed field whenever a capability field (can_spawn, can_read, can_write) is added or modified across multiple adapter targets.

### Injection
- Add to any YAML-touching conversation: "Verify: grep -rn 'can_spawn' src/pathly_data/adapters/ — confirm all adapter variants are consistent, not just the ones the conversation touched."

### Source
Feature: agent-architecture-refactor | Stage: implementation | Date: 2026-05-13
