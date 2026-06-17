---

---
# plan

This is the canonical, tool-agnostic Pathly behavior for the plan workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

## Skill Contract

**Consumes (optional):** `pathly/plans/STORM_SEED.md` - pre-filled answers for the interview
**Produces:** `pathly/plans/$FEATURE/` - FEATURE_INDEX.md + 4 files in lite, FEATURE_INDEX.md + 8 files in standard/strict
**Consumed by:** `build` skill reads `pathly/plans/$FEATURE/FEATURE_INDEX.md` first, then `CONVERSATION_PROMPTS.md` and `PROGRESS.md`

## Step 0: Parse Arguments

Parse `$ARGUMENTS`:
- First token that is not `lite`, `standard`, or `strict` = `FEATURE`
- `lite` -> `rigor = lite`
- `standard` -> `rigor = standard`
- `strict` -> `rigor = strict`
- Default: `rigor = standard`

Use `FEATURE` for the folder name, not the full `$ARGUMENTS` string.

If `pathly/plans/$FEATURE/` already exists, treat this as a rigor change or plan completion task:
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

Check if `pathly/plans/STORM_SEED.md` exists.

If it exists: read it, pre-fill interview answers, confirm with user, then delete the seed file.

If it does not exist: interview the user. Ask what it does, which layers it touches, dependencies, and complexity (Small/Medium/Large). Skip only if the user already gave a detailed description.

If `rigor = strict`, do not skip risk questions. Explicitly ask about security, data loss, migrations, compliance, production impact, and rollback expectations unless the user already answered them.

## Step 3: Gather Codebase Context

Capture start time: `python3 -c "import time; print(int(time.time()))"` → `PLAN_START`

**Phase 1 — Analyze:**
log-phase PHASE_START analyze

Spawn `planner` with `phase: analyze`. Pass the feature name and rigor level.
Parse the returned `## NEEDS_CONTEXT` block.

log-phase PHASE_DONE analyze

**Phase 2 — Scout:**
log-phase PHASE_START scout

If `NEEDS_CONTEXT` is not `none`: call `scout-path` with the block, `ROLE: planner`, `FEATURE: [feature name]`. Use the returned summary as Scout Findings.
If `NEEDS_CONTEXT` is `none`: findings = none. Skip scout-path.

log-phase PHASE_DONE scout (include scouts_count = number of entries passed to scout-path, or 0 if skipped)

**Phase 3 — Plan:**
log-phase PHASE_START plan

Spawn `planner` with `phase: plan`. Inject:
```
## Scout Findings
[compressed summary from Phase 2, or "none" if skipped]
```
Plus all existing context: rigor level, `STORM_SEED` contents if it existed, `PO_NOTES` contents if it exists.

log-phase PHASE_DONE plan

Run the Completion report with `agent: planner`, `result: DONE`, `conversation: 0`, using `PLAN_START` from the start of this step. Set `summary` to: `"planner created <N> files for <FEATURE> (<rigor> rigor)"` where N is the count of files written in Step 4.

## Template Path Resolution

Before reading any template file, resolve `TEMPLATE_BASE` using this fallback chain — stop at the first path that successfully returns content:

1. `{{TEMPLATES_DIR}}/plan/` — the adapter-installed path (Claude: `~/.claude/plugins/pathly/templates/plan/`, Codex: `~/.codex/plugins/pathly/templates/plan/`, Copilot: `~/.vscode/extensions/pathly/templates/plan/`)
2. Replace `~` in path 1 with `$HOME` — Linux / macOS env var (Codex, Copilot, Claude in worktrees on Mac)
3. Replace `~` in path 1 with `$USERPROFILE` — Windows env var (Copilot, Claude in worktrees on Windows)
4. `.claude/templates/plan/` — project-local copy; works for any agent in any worktree if templates are committed to the repo

If none of the four paths resolve, proceed without the template and use only the inline descriptions in this skill.

All template reads below use `$TEMPLATE_BASE/<FILE>.template.md`.

## Step 4: Create The Plans Folder

Create `pathly/plans/$FEATURE/` if it does not exist. If it exists, add or update only the files/sections needed for the selected rigor.

### Rigor File Sets

**All rigor levels produce `FEATURE_INDEX.md` as the first file.** Write it before any other plan file.

Lite produces 5 required files:
- `FEATURE_INDEX.md` ← always first
- `USER_STORIES.md`
- `IMPLEMENTATION_PLAN.md`
- `PROGRESS.md`
- `CONVERSATION_PROMPTS.md`

Lite merges happy path, edge cases, architecture notes, and flow notes into the relevant sections of those four files. Keep the plan small: target 1-2 conversations and only include detail the builder needs.

Standard produces 9 files:
- `FEATURE_INDEX.md` ← always first
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

Conversation cap rule: max 4 conversations per folder. If more are needed, split into `pathly/plans/$FEATURE-part-1/` and `pathly/plans/$FEATURE-part-2/`.

### 4a. FEATURE_INDEX.md ← write this first

Read `{{TEMPLATES_DIR}}/plan/FEATURE_INDEX.template.md` for the exact file structure.

Fill in:
- **Plan files table** — list every plan file this feature will produce, with written-by/read-by/purpose.
- **Codebase touchpoints table** — list every source file this feature will create or modify, which conversation touches it, and what changes. One row per file. These are the paths the builder must verify before editing.
- **Conversation map** — one row per conversation matching PROGRESS.md exactly.
- **Optional plan files** — mark yes/no for each of the 4 optional files.

Write this file before writing any other plan file. All codebase paths must be accurate — the builder will glob-verify each one.

### 4b. USER_STORIES.md

Read `{{TEMPLATES_DIR}}/plan/USER_STORIES.template.md` for the exact file structure.

In lite, include only the stories and acceptance criteria needed for the small change.

### 4c. IMPLEMENTATION_PLAN.md

Read `{{TEMPLATES_DIR}}/plan/IMPLEMENTATION_PLAN.template.md` for the exact file structure.

Each phase header must carry a `Conversation: N` tag matching the PROGRESS.md row it belongs to:
```
## Phase 2 — Fix path prefixes   ← Conversation: 1
```
This enforces 1:1 alignment between plan phases and PROGRESS.md rows. The builder navigates by conversation number; the tag is the bridge.

In lite, add short sections for happy path, edge cases, and architecture notes directly in this file instead of creating separate files.

In strict, add risk, rollback, approval, and verification mapping sections.

### 4d. PROGRESS.md

Read `{{TEMPLATES_DIR}}/plan/PROGRESS.template.md` for the exact file structure.

### 4e. CONVERSATION_PROMPTS.md (legacy — superseded by board-DAG task text)

> **Legacy.** In the board-DAG model the **task `text` posted in Step 6 is the builder
> prompt** (self-contained, per task). `CONVERSATION_PROMPTS.md` is retained only for the
> older `build` skill path that still reads it; the board-native executors
> (`single`/`loop`) never open it. When the build path is reworked to consume board tasks,
> this file goes away. Generate it for back-compat, but the per-task Step-6 text is
> authoritative.

Verbatim prompts for each builder conversation. Max 4 conversations per folder.
Read `{{TEMPLATES_DIR}}/plan/CONVERSATION_PROMPTS.template.md` for the exact file structure.

Each prompt must be self-contained. Start every prompt with:
```
Read pathly/plans/$FEATURE/FEATURE_INDEX.md first to orient yourself and verify codebase paths.
```
Do not re-list all codebase files in the prompt — they live in FEATURE_INDEX.md.

### 4f. HAPPY_FLOW.md

Skip in `lite`; merge the happy path into `USER_STORIES.md` or `IMPLEMENTATION_PLAN.md`.

For standard and strict, read `{{TEMPLATES_DIR}}/plan/HAPPY_FLOW.template.md` for the exact file structure.

### 4g. EDGE_CASES.md

Skip in `lite`; merge only relevant edge cases into `USER_STORIES.md` and `CONVERSATION_PROMPTS.md`.

For standard and strict, read `{{TEMPLATES_DIR}}/plan/EDGE_CASES.template.md` for the exact file structure.

### 4h. ARCHITECTURE_PROPOSAL.md

Skip in `lite`; put short architecture notes directly in `IMPLEMENTATION_PLAN.md`.

For standard and strict, read `{{TEMPLATES_DIR}}/plan/ARCHITECTURE_PROPOSAL.template.md` for the exact file structure.

### 4i. FLOW_DIAGRAM.md

Skip in `lite` unless the flow is unclear without a diagram.

For standard and strict, read `{{TEMPLATES_DIR}}/plan/FLOW_DIAGRAM.template.md` for the exact file structure.
Use ASCII only. Show only layers touched. Include happy path and fallback. Label arrows with action name or config key. Max about 70 chars wide.

**Mermaid option:** If the feature introduces a new inter-agent calling convention, sub-skill, or orchestration pattern — at any rigor level — also offer `{{TEMPLATES_DIR}}/plan/MERMAID_DIAGRAM.template.md` as the diagram format. Mermaid renders richer in tools that support it; ASCII is the fallback for plain-text hosts. Let the user choose, or default to Mermaid when the host is known to render it.

## Task Decomposition Rules

When turning stories into implementation work, each phase and conversation must
show both its purpose and its dependency relationship to the larger feature.

For each phase in `IMPLEMENTATION_PLAN.md`, include:

- File: exact path of the file this phase creates or modifies (required at all rigor levels).
- Done when: one observable sentence — what is true when this phase is complete (required at all rigor levels).
- Purpose: why this phase exists in the user-facing feature.
- Depends on: earlier phase/conversation, existing code path, or external setup.
- Enables: what later phase or acceptance criterion this unlocks.
- Verify: a runnable command or manual check (standard/strict only; omit in lite).
- Rollback: how to undo if this phase goes wrong (strict only).

`File` and `Done when` are mandatory at every rigor level. They let the builder jump directly to the right file and know exactly when to stop — eliminating orientation tool calls on every run.

Keep decomposition small enough for builder reliability:

- Lite: 1-2 conversations, 1 phase per file touched — one File + Done when per phase.
- Standard/strict: up to 4 conversations, 3-6 phases per conversation, each with File + Done when + Verify.
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

- `FEATURE_INDEX.md` exists in `pathly/plans/$FEATURE/` for all rigor levels.
- If `rigor = lite`, all 5 required files exist in `pathly/plans/$FEATURE/`.
- If `rigor = standard` or `strict`, all 9 files exist in `pathly/plans/$FEATURE/`.
- `CONVERSATION_PROMPTS.md` has no more than 4 conversations.
- Conversation prompts reference correct phase numbers.
- `PROGRESS.md` conversation table matches `CONVERSATION_PROMPTS.md`.
- Phase numbers are consistent across all created files.
- Every phase in `IMPLEMENTATION_PLAN.md` has a `File:` field and a `Done when:` field — all rigor levels.
- Verify commands use correct project commands (standard/strict only).
- If `rigor = strict`, every acceptance criterion has an explicit verification mapping and rollback note.

## Step 6: Post Tasks to Comms Board

After all plan files are verified, seed the comms board DAG so the builder can poll
`GET /comms/tasks?ready=true` and Studio can visualize task progress. The DAG hangs off
a **goal message** (`type=goal`): you post the goal first, then stamp every phase task
with `goal_id` pointing at it.

**Idempotency guard — skip if this DAG already exists.** Check for BOTH an existing goal
and existing tasks for this feature's scope:
```
curl -s "http://127.0.0.1:8765/comms/tasks?feature=$FEATURE"
curl -s "http://127.0.0.1:8765/comms?feature=$FEATURE&scope=$FEATURE&type=goal"
```
If **either** response contains any messages, skip this entire step — the DAG is already
seeded (e.g. from a previous planning run).

**Post the goal first.** One `type=goal` message; capture its returned `message_id` as
`$GOAL_ID`. `executor` is set on the **goal only** (`single` = one agent runs the whole
goal; the `{single,loop,team}` choice is consumed later by the dispatcher, not here):

```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "$FEATURE",
    "from": "planner",
    "type": "goal",
    "text": "Goal: $FEATURE",
    "board": "feature",
    "scope": "$FEATURE",
    "executor": "single"
  }'
```
Record the response `"message_id"` as `$GOAL_ID`.

**Post each phase in order** (Phase 1 first). Track the `message_id` returned by each call
so later phases can reference their dependencies.

**The task `text` IS the builder prompt** — in the board-DAG model each task is the unit of
work (replacing the per-conversation prompts of the legacy `CONVERSATION_PROMPTS.md`). An
executor agent runs a task seeing ONLY its `text` plus the file at `artifact_path` — so the
text must be **self-contained**: what to build, which files, and when it's done. Do not rely
on the agent reading a separate conversation-prompts file.

For each phase in `IMPLEMENTATION_PLAN.md`:
1. Extract the phase number `N`, title, the `Purpose:` (what to build), the `File:` field,
   and the `Done when:` field (all required on every phase per Task Decomposition Rules).
2. Read the `Depends on:` field — note which phase numbers it depends on (e.g. `Phase 1, Phase 2`).
   Use `[]` when the phase says `Depends on: nothing`.
3. Resolve dependencies: replace each named phase number with the `message_id` you recorded
   when that phase was posted (your local map: `phase_N → message_id`).
4. **Compose the self-contained task `text`** (a single JSON string; use `\n` for line breaks),
   following this shape — keep it tight, no line numbers or exact test counts (Team-Safe rules):
   ```
   Phase N: <title>

   <Purpose — 1–2 sentences on what to build and why>

   Files: <the phase's File: value>
   Done when: <the phase's Done when: value>

   Read pathly/plans/$FEATURE/FEATURE_INDEX.md first to orient and verify paths. Do NOT touch
   files outside this phase's scope. If verification fails and the fix needs out-of-scope
   changes, stop and report; if fundamentally broken, git checkout the affected files and retry.
   ```
5. POST the task with `goal_id:"$GOAL_ID"` and that composed `text`. Emit this EXACT shape.
   `executor` is **NOT** on the task (it lives on the goal). `conv` is the conversation number
   from the plan and MUST be a JSON **integer** — omit the key entirely rather than send a
   string (the route 400s on a string `conv`):

```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "$FEATURE",
    "from": "planner",
    "type": "task",
    "text": "Phase N: <title>\n\n<purpose>\n\nFiles: <file>\nDone when: <done-when>\n\nRead pathly/plans/$FEATURE/FEATURE_INDEX.md first…",
    "board": "feature",
    "scope": "$FEATURE",
    "stage": "BUILDING",
    "conv": <int>,
    "depends_on": ["<phase_K_message_id>"],
    "goal_id": "$GOAL_ID",
    "artifact_path": "pathly/plans/$FEATURE/IMPLEMENTATION_PLAN.md",
    "artifact_type": "plan_artifact"
  }'
```

6. Record the `"message_id"` from the response as `phase_N_id` in your local map.

If the comms server is unreachable (connection refused or non-200 response), skip this step
silently — plan files are the authoritative source of truth and the DAG is advisory.

## Step 7: Report

```text
## Plans folder created: pathly/plans/$FEATURE/

Rigor: [lite / standard / strict]

Files:
- FEATURE_INDEX.md - entry point: all plan files + codebase touchpoints
- USER_STORIES.md - N stories with acceptance criteria
- IMPLEMENTATION_PLAN.md - N phases across N conversations (each tagged Conversation: N)
- PROGRESS.md - tracking table, all TODO
- CONVERSATION_PROMPTS.md - N builder prompts ready to use
- HAPPY_FLOW.md - ideal journey [standard/strict only]
- EDGE_CASES.md - edge cases [standard/strict only]
- ARCHITECTURE_PROPOSAL.md - design decisions [standard/strict only]
- FLOW_DIAGRAM.md - ASCII flow diagram [standard/strict only]

Seed consumed: [yes / no]
Next route: `continue $FEATURE`
```
