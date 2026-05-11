# plan

This is the canonical, tool-agnostic Pathly behavior for the plan workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

## Skill Contract

**Consumes (optional):** `plans/STORM_SEED.md` - pre-filled answers for the interview
**Produces:** `plans/$FEATURE/` - 4 files in lite, 8 files in standard/strict
**Consumed by:** `build` skill reads `plans/$FEATURE/CONVERSATION_PROMPTS.md` and `PROGRESS.md`

## Step 0: Parse Arguments

Parse `$ARGUMENTS`:
- First token that is not `lite`, `standard`, or `strict` = `FEATURE`
- `lite` -> `rigor = lite`
- `standard` -> `rigor = standard`
- `strict` -> `rigor = strict`
- Default: `rigor = standard`

Use `FEATURE` for the folder name, not the full `$ARGUMENTS` string.

If `plans/$FEATURE/` already exists, treat this as a rigor change or plan completion task:
- `lite -> standard`: keep existing files and add missing standard files.
- `standard -> strict`: keep existing files and add strict risk, rollback, approval, and verification mapping.
- `strict -> standard` or `standard -> lite`: do not delete files; report that downgrades change future gates only.
- Never overwrite existing plan content without asking the user.

## Step 1: Apply Active Lessons

If `LESSONS.md` exists in the project root, read it now.
Apply the `Injection` field of each lesson when generating the relevant plan file.
Do not restate lesson reasoning - just apply the injection silently.
If two lessons conflict, prefer the one with more sources listed.

## Step 2: Understand The Feature

Check if `plans/STORM_SEED.md` exists.

If it exists: read it, pre-fill interview answers, confirm with user, then delete the seed file.

If it does not exist: interview the user. Ask what it does, which layers it touches, dependencies, and complexity (Small/Medium/Large). Skip only if the user already gave a detailed description.

If `rigor = strict`, do not skip risk questions. Explicitly ask about security, data loss, migrations, compliance, production impact, and rollback expectations unless the user already answered them.

## Planner Consultation Policy

The planner owns the final plan files. It may consult other roles, but those
consultations are optional inputs, not mandatory stages.

Consult `po` before writing `USER_STORIES.md` only when product intent is
unclear:

- The target user or buyer is ambiguous.
- MVP scope is too broad or mixes multiple user problems.
- Acceptance criteria describe implementation instead of observable outcomes.
- Success criteria, out-of-scope items, or product edge cases are missing.
- A PRD exists but has gaps or conflicting requirements.

Before writing user stories, spawn `quick` with `ROLE: po`:
```
ROLE: po
Single factual lookup: who are the existing users of [feature area]? What similar features already exist in this codebase that set scope expectations?
Read at most 2 files. Return 3–5 bullet facts relevant to product scope only.
```
Inject findings into PO consultation context.

If PO consultation is needed, request or read `plans/$FEATURE/PO_NOTES.md`, then
turn those notes into user stories and acceptance criteria. Do not keep PO in
the default lite path when the user already gave enough product context.

Consult `architect` only when technical risk is material:

- Cross-layer dependency direction is unclear.
- Data migrations, auth, payments, security, compliance, or rollback are in scope.
- The feature changes shared abstractions or public contracts.
- The planner cannot produce implementation phases without design decisions.

When architect consultation is triggered, first spawn `scout` with `ROLE: architect`:
```
ROLE: architect
What cross-layer dependencies, existing design decisions, and architectural constraints apply to [feature]?
Scope: ARCHITECTURE_PROPOSAL.md files, layer boundary files, files the feature will touch.
Return: existing constraints that must be respected, patterns to follow, open design questions.
```
Inject findings as `## Architecture Context` into the architect spawn prompt.

Do not add a generic "consult everyone" stage. Use targeted consultation so
Pathly stays low-latency and low-token by default.
## Step 3: Research The Codebase

1. Read project guidance and linked rule files for layer structure, dependency direction, naming conventions, and test commands.
2. Find similar existing components and use them as reference patterns.
3. Identify files to create or modify.
4. Check test directory conventions if tests are in scope.

## Step 4: Create The Plans Folder

Create `plans/$FEATURE/` if it does not exist. If it exists, add or update only the files/sections needed for the selected rigor.

### Rigor File Sets

Lite produces 4 required files:
- `USER_STORIES.md`
- `IMPLEMENTATION_PLAN.md`
- `PROGRESS.md`
- `CONVERSATION_PROMPTS.md`

Lite merges happy path, edge cases, architecture notes, and flow notes into the relevant sections of those four files. Keep the plan small: target 1-2 conversations and only include detail the builder needs.

Standard produces 8 files:
- `USER_STORIES.md`
- `IMPLEMENTATION_PLAN.md`
- `PROGRESS.md`
- `CONVERSATION_PROMPTS.md`
- `HAPPY_FLOW.md`
- `EDGE_CASES.md`
- `ARCHITECTURE_PROPOSAL.md`
- `FLOW_DIAGRAM.md`

Standard is the current default.

Strict produces the same 8 files plus stronger audit expectations:
- Add explicit risk, rollback, verification, and approval notes to `IMPLEMENTATION_PLAN.md`.
- Ensure every acceptance criterion maps to a verification step.
- Keep all assumptions and unresolved questions visible.
- Do not mark ambiguous requirements as implementation-ready.

Conversation cap rule: max 4 conversations per folder. If more are needed, split into `plans/$FEATURE-part-1/` and `plans/$FEATURE-part-2/`.

### 4a. USER_STORIES.md

Read `core/templates/plan/USER_STORIES.template.md` for the exact file structure.

In lite, include only the stories and acceptance criteria needed for the small change.

### 4b. IMPLEMENTATION_PLAN.md

Read `core/templates/plan/IMPLEMENTATION_PLAN.template.md` for the exact file structure.

In lite, add short sections for happy path, edge cases, and architecture notes directly in this file instead of creating separate files.

In strict, add risk, rollback, approval, and verification mapping sections.

### 4c. PROGRESS.md

Read `core/templates/plan/PROGRESS.template.md` for the exact file structure.

### 4d. CONVERSATION_PROMPTS.md

This is the key file: verbatim prompts for each builder conversation. Max 4 conversations per folder.
Read `core/templates/plan/CONVERSATION_PROMPTS.template.md` for the exact file structure.

Each prompt must be self-contained and runnable without reading every plan file.

### 4e. HAPPY_FLOW.md

Skip in `lite`; merge the happy path into `USER_STORIES.md` or `IMPLEMENTATION_PLAN.md`.

For standard and strict, read `core/templates/plan/HAPPY_FLOW.template.md` for the exact file structure.

### 4f. EDGE_CASES.md

Skip in `lite`; merge only relevant edge cases into `USER_STORIES.md` and `CONVERSATION_PROMPTS.md`.

For standard and strict, read `core/templates/plan/EDGE_CASES.template.md` for the exact file structure.

### 4g. ARCHITECTURE_PROPOSAL.md

Skip in `lite`; put short architecture notes directly in `IMPLEMENTATION_PLAN.md`.

For standard and strict, read `core/templates/plan/ARCHITECTURE_PROPOSAL.template.md` for the exact file structure.

### 4h. FLOW_DIAGRAM.md

Skip in `lite` unless the flow is unclear without a diagram.

For standard and strict, read `core/templates/plan/FLOW_DIAGRAM.template.md` for the exact file structure.
Use ASCII only. Show only layers touched. Include happy path and fallback. Label arrows with action name or config key. Max about 70 chars wide.

## Task Decomposition Rules

When turning stories into implementation work, each phase and conversation must
show both its purpose and its dependency relationship to the larger feature.

For each phase in `IMPLEMENTATION_PLAN.md`, include:

- Purpose: why this phase exists in the user-facing feature.
- Depends on: earlier phase/conversation, existing code path, or external setup.
- Enables: what later phase or acceptance criterion this unlocks.
- Verification: the smallest useful command or manual check for that phase.

Keep decomposition small enough for builder reliability:

- Lite: 1-2 conversations, 1-3 phases per conversation.
- Standard/strict: up to 4 conversations, 3-6 phases per conversation.
- If dependency chains exceed 4 conversations, split the feature into follow-up
  plan folders instead of creating a giant plan.
## Conversation Splitting Rules

1. Each conversation must leave the codebase runnable and end with a verify command.
2. Hard cap: 4 conversations per folder.
3. Natural order: foundation first, then workflow/integration, then additional stories.
4. Every prompt must say `Do NOT touch [X] yet`.
5. Later prompts reference completed earlier conversations.
6. Target 3-6 phases per conversation in standard/strict; target 1-3 phases in lite.
7. Each prompt is self-contained.

## Team-Safe Prompt Rules

1. Never reference specific line numbers.
2. Never reference exact test counts.
3. Include relevant architectural boundary reminders in prompts that touch integration or data layers.
4. Include a recovery instruction: `If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.`

## Step 5: Verify Structure

- If `rigor = lite`, all 4 required files exist in `plans/$FEATURE/`.
- If `rigor = standard` or `strict`, all 8 files exist in `plans/$FEATURE/`.
- `CONVERSATION_PROMPTS.md` has no more than 4 conversations.
- Conversation prompts reference correct phase numbers.
- `PROGRESS.md` conversation table matches `CONVERSATION_PROMPTS.md`.
- Phase numbers are consistent across all created files.
- Verify commands use correct project commands.
- If `rigor = strict`, every acceptance criterion has an explicit verification mapping and rollback note.

## Step 6: Report

```text
## Plans folder created: plans/$FEATURE/

Rigor: [lite / standard / strict]

Files:
- USER_STORIES.md - N stories with acceptance criteria
- IMPLEMENTATION_PLAN.md - N phases across N conversations
- PROGRESS.md - tracking table, all TODO
- CONVERSATION_PROMPTS.md - N builder prompts ready to use
- HAPPY_FLOW.md - ideal journey [standard/strict only]
- EDGE_CASES.md - edge cases [standard/strict only]
- ARCHITECTURE_PROPOSAL.md - design decisions [standard/strict only]
- FLOW_DIAGRAM.md - ASCII flow diagram [standard/strict only]

Seed consumed: [yes / no]
Next route: `continue $FEATURE`
```
