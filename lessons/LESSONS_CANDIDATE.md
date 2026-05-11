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
