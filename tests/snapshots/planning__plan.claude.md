# plan

This is the canonical, tool-agnostic Pathly behavior for the plan workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

## Skill Contract

**Consumes (optional):** `pathly/features/STORM_SEED.md` - pre-filled answers for the interview
**Produces:** `$PLAN_DIR/` - FEATURE_INDEX.md + 4 files in lite, FEATURE_INDEX.md + 8 files in standard/strict (Step 0.5 resolves `PLAN_DIR`: the feature folder in feature mode, the **goal folder** in goal-decompose mode)
**Consumed by:** the board task DAG seeded in Step 6 (authoritative for board-native executors); the legacy `build` skill path reads `$PLAN_DIR/FEATURE_INDEX.md` first, then `CONVERSATION_PROMPTS.md` and `PROGRESS.md`

## Step 0: Parse Arguments

Parse `$ARGUMENTS`:
- First token that is not `lite`, `standard`, or `strict` = `FEATURE`
- `lite` -> `rigor = lite`
- `standard` -> `rigor = standard`
- `strict` -> `rigor = strict`
- Default: `rigor = standard`

Use `FEATURE` for the folder name, not the full `$ARGUMENTS` string.

## Step 0.5: Resolve PLAN_DIR — where every plan file goes

Storage path provided by the launch context (substituted at compose time):

```
<feature_path>
```

- **Flow / decompose mode:** if the line above shows a real path, set `PLAN_DIR` to it
  exactly. For a goal decompose (e.g. the consultation flow's terminal planner stage) this
  is the **goal folder** — `pathly/features/<name>/goals/<goal-slug>` — NOT the feature
  root. The plan and its task DAG belong to the goal; knowledge artifacts live on the
  feature board ("two owners, two homes"). Writing plan files to the feature root in this
  mode silently clobbers sibling goals' plans — never do it.
- **Interactive mode:** if the line above still literally reads `<feature_path>` (angle
  brackets — nothing was substituted), there is no flow context. Set
  `PLAN_DIR = pathly/features/$FEATURE`.

All Step 4 file writes, Step 5 checks, and Step 6 `artifact_path` values use `$PLAN_DIR/`.

If `$PLAN_DIR/FEATURE_INDEX.md` already exists, treat this as a rigor change or plan completion task:
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

Check if `pathly/features/STORM_SEED.md` exists.

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

> **Do NOT write the completion report (`AGENT_DONE`) here.** It MUST be your **final action**,
> written only AFTER the task DAG is seeded in Step 6 — see **Step 8**. Emitting `AGENT_DONE` at the
> end of this phase lets the runner's early-advance end the stage before Steps 4–6 run, so the
> goal+task DAG never gets seeded (the consultation flow's terminal planner stage relies on Step 6).
> That is also why the summary's `N` references "files written in Step 4" — it is only knowable later.

## Template Path Resolution

Before reading any template file, resolve `TEMPLATE_BASE` using this fallback chain — stop at the first path that successfully returns content:

1. `{{TEMPLATES_DIR}}/plan/` — the adapter-installed path (Claude: `~/.claude/plugins/pathly/templates/plan/`, Codex: `~/.codex/plugins/pathly/templates/plan/`, Copilot: `~/.vscode/extensions/pathly/templates/plan/`)
2. Replace `~` in path 1 with `$HOME` — Linux / macOS env var (Codex, Copilot, Claude in worktrees on Mac)
3. Replace `~` in path 1 with `$USERPROFILE` — Windows env var (Copilot, Claude in worktrees on Windows)
4. `.claude/templates/plan/` — project-local copy; works for any agent in any worktree if templates are committed to the repo

If none of the four paths resolve, proceed without the template and use only the inline descriptions in this skill.

All template reads below use `$TEMPLATE_BASE/<FILE>.template.md`.

## Step 4: Create The Plans Folder

Create `$PLAN_DIR/` (from Step 0.5) if it does not exist. If it exists, add or update only the files/sections needed for the selected rigor.

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

Conversation cap rule: max 4 conversations per folder. If more are needed, split into `pathly/features/$FEATURE-part-1/` and `pathly/features/$FEATURE-part-2/`.

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

Each prompt must be self-contained. Start every prompt with (write the resolved `$PLAN_DIR` value, not the variable):
```
Read $PLAN_DIR/FEATURE_INDEX.md first to orient yourself and verify codebase paths.
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

**Collision guard (decompose mode):** if `$PLAN_DIR/ARCHITECTURE_PROPOSAL.md` already exists
(a consultation's architect stage wrote it), do NOT overwrite it — it is the authoritative
proposal. Keep it, and only append a `## Phase Mapping` section at the end if the phase-anchor
mapping is missing.

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

- `FEATURE_INDEX.md` exists in `$PLAN_DIR/` for all rigor levels.
- If `rigor = lite`, all 5 required files exist in `$PLAN_DIR/`.
- If `rigor = standard` or `strict`, all 9 files exist in `$PLAN_DIR/`.
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

**Advisory artifact heading convention (anchor-addressable phases).** When writing
`EDGE_CASES.md`, `HAPPY_FLOW.md`, and `ARCHITECTURE_PROPOSAL.md`, you MUST use `## Phase N`
headings that match the `## Phase N` headings in `IMPLEMENTATION_PLAN.md` (e.g.
`## Phase 3 — Fix path prefixes`). This makes each phase's advisory content anchor-addressable
(slug `phase-N`) so the retrieval system can deterministically link a phase task to its
edge-case, happy-flow, and architecture sections. The heading text must contain `Phase <N>`
(e.g. `## Phase 2 — Add migration`). For `ARCHITECTURE_PROPOSAL.md`, use phase-aligned
`## Phase N` headings where the proposal maps to specific phases; a single-phase or
phase-agnostic proposal may use descriptive headings instead.

**Idempotency guard — skip only if THIS goal already has a task DAG.** After you resolve
`$GOAL_ID` (the "Find OR create the goal" block just below), check for tasks **scoped to that goal**:
```
curl -s "http://127.0.0.1:8765/comms/tasks?goal_id=$GOAL_ID"
```
Skip the task-posting only if **this goal** already has tasks. Do NOT skip just because some
*other* goal on the feature has tasks — a feature-wide check is what previously made a fresh
decompose of a new goal silently seed nothing.

**Find OR create the goal.** This run may be a *decompose of a goal that already exists* (the
goal card you were launched from — its `goal_id` may be named in your prompt) OR a fresh plan.
Look the goal up first:
```
curl -s "http://127.0.0.1:8765/comms?feature=$FEATURE&scope=$FEATURE&type=goal"
```
- **If a `type=goal` message exists** (or your prompt names a `goal_id`): use its `id` as
  `$GOAL_ID`. Do **NOT** post a duplicate goal — you are only adding its task children.
- **If none exists:** post one and capture its `message_id` as `$GOAL_ID`. `executor` is set on
  the **goal only** (`single` = one agent runs the whole goal; the `{single,loop,team}` choice is
  consumed later by the dispatcher, not here):

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
Record the `$GOAL_ID` (the existing goal's `id`, or the new `"message_id"`).

**Post advisory files as artifacts (standard/strict only).** Before posting phase tasks,
post each advisory file that exists as a `type='artifact'` message so the context-retrieval
system can index and hydrate them. Skip silently if the file does not exist (lite plans omit
them). Capture each returned `message_id` for reference (the retrieval system looks up the
artifact row by `(scope, path)`, so the id is advisory — you do not need to pass it into
task posts). Keep these posts under the same idempotency guard and fail-silent-on-connection-
refused branch as the rest of Step 6.

```bash
# Post EDGE_CASES.md if it exists
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "$FEATURE",
    "from": "planner",
    "type": "artifact",
    "text": "Advisory artifact: edge cases for $FEATURE",
    "board": "feature",
    "scope": "$FEATURE",
    "artifact_path": "$PLAN_DIR/EDGE_CASES.md",
    "artifact_type": "plan_artifact"
  }'

# Post HAPPY_FLOW.md if it exists
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "$FEATURE",
    "from": "planner",
    "type": "artifact",
    "text": "Advisory artifact: happy flow for $FEATURE",
    "board": "feature",
    "scope": "$FEATURE",
    "artifact_path": "$PLAN_DIR/HAPPY_FLOW.md",
    "artifact_type": "plan_artifact"
  }'

# Post ARCHITECTURE_PROPOSAL.md if it exists
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "$FEATURE",
    "from": "planner",
    "type": "artifact",
    "text": "Advisory artifact: architecture proposal for $FEATURE",
    "board": "feature",
    "scope": "$FEATURE",
    "artifact_path": "$PLAN_DIR/ARCHITECTURE_PROPOSAL.md",
    "artifact_type": "plan_artifact"
  }'
```

**Post each task via the Comms Board fragment (task-dag-post).** The composed fragment
(included in this skill when `goal_id` is set) owns the full POST mechanics: idempotency
guard, task JSON shape, `depends_on` resolution, skip-if-down. For each phase in
`IMPLEMENTATION_PLAN.md`:

1. Extract: phase number N, title, Purpose, File, Done-when, Depends-on
2. Compose the self-contained task `text` (same shape as before — Phase N: title, purpose,
   files, done-when, FEATURE_INDEX read note)
3. Derive `context_refs` from phase N (EDGE_CASES, HAPPY_FLOW, ARCHITECTURE_PROPOSAL anchors
   if those files exist) and `depends_on` from the depends-on phase map
4. Post each task via the fragment mechanics

The `context_refs` and `depends_on` derivation rules are unchanged:
- `context_refs`: `[{"artifact": "EDGE_CASES.md", "anchor": "phase-N"}, ...]`
- `depends_on`: resolve phase numbers to `message_id`s from prior posts
- `conv`: the integer phase number (omit if not applicable)
- `executor` is NOT on the task — it lives on the goal

## Step 7: Report

```text
## Plans folder created: $PLAN_DIR/

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

## Step 8: Completion report (FINAL action — only after the DAG is seeded)

This is the **last thing you do**, AFTER Step 6 has seeded the task DAG. Writing `AGENT_DONE`
earlier lets the runner's early-advance terminate the stage before the DAG exists — that is the
exact bug this ordering fixes, so do not move it back.

Run the Completion report with `agent: planner`, `result: DONE`, `conversation: 0`, using
`PLAN_START` from Step 3. Set `summary` to:
`"planner created <N> files for <FEATURE> (<rigor> rigor) and seeded <T> tasks under goal <GOAL_ID>"`
where `N` is the count of files written in Step 4 and `T` is the number of phase tasks you posted
in Step 6 (use `0` and note the reason if Step 6 was skipped or the server was unreachable).

## Live progress logging

Each `log-phase PHASE_START <phase>` or `log-phase PHASE_DONE <phase>` marker is a mandatory
pipeline event. When you encounter one (or an inline `Run:` bash block replacing it), execute it immediately:

Run:
```bash
# On PHASE_START:
pathly-fsm-call record-phase \
  --feature "<feature>" \
  --agent "<agent>" \
  --phase "<phase>" \
  --event-type PHASE_START \
  --project-root "<project_root>"

# On PHASE_DONE:
pathly-fsm-call record-phase \
  --feature "<feature>" \
  --agent "<agent>" \
  --phase "<phase>" \
  --event-type PHASE_DONE \
  --project-root "<project_root>"
```

- `<feature>` — the feature slug (folder name under `pathly/features/`)
- `<agent>` — the current agent role (`builder`, `reviewer`, `tester`, `designer`, etc.)
- `<phase>` — one of `analyze`, `scout`, `implement`, `review`, `test`, `plan`, `design`, `storm`

**Server availability — start-if-needed (same contract as log-agent-done):**

If `pathly-fsm-call` fails or the server is not reachable:
1. Start the server in the background: `pathly-fsm-http`
2. Wait 2 seconds, then retry the `record-phase` call once.
3. If the retry also fails: skip silently and continue — phase logging must never block execution.

This makes phase logging reliable on any adapter (Codex, Copilot, CLI) where the
FSM server is not automatically managed by the host environment.

## Code intelligence (ask Pathly's code graph before Grep)

When you need to understand code **structure** — where a symbol is defined, who calls it, or the
blast radius of a change — ask Pathly's code-knowledge graph first. It is precise and fast, and each
query is logged to the board as shared context for other agents.

```bash
curl -s -X POST http://127.0.0.1:8765/code/query -H "Content-Type: application/json" -d '{
  "op": "symbol",
  "target": "<file path OR symbol name>",
  "role": "<your-role>",
  "scope": "<feature>" }'
```

- `op` — `symbol` (definition + signature) · `callers` (who calls it) · `impact` (what a change to
  it touches) · `chain` (call path between two symbols) · `context` (surrounding structure) ·
  `pattern` (find a code pattern). Your `role` gates which ops you may use.
- The response is `{ "ok": true, "result": <block-or-null>, "backend": "<name>" }`.
- **If `result` is `null`** (the backend is off, or it found nothing), **fall back to Grep/Read** and
  continue — never block on it. This is an accelerator, not a gate.

Use it **before** editing an unfamiliar symbol (check `callers` / `impact` so you don't break a
caller) and whenever a task names a symbol you haven't located yet (`symbol`). Prefer one targeted
query over a broad Grep sweep.

## Registering your output artifact

After you finish your stage work, register your primary output artifact. This runs **after**
you write your output file and **before** your completion report — so `AGENT_DONE` stays your
final act. This step never advances the pipeline: no `/complete_stage`, no `next-action`, no
FSM transition. The supervisor advances the flow once your artifact exists.

**1. Write your output file.** Write your stage's primary artifact to exactly `<out_path>`
(the runner injected this path — do not choose your own). This is the file the gate checks.

**2. Append one line to the artifact ledger.** Append a single JSON line to
`<feature_path>/ARTIFACTS.jsonl` (create the file if absent, append-only — never rewrite it):
```bash
python3 -c '
import json, os, sys, time
rec = {"role": "<agent>", "path": "<out_path>", "type": "md",
       "title": "<short title>", "summary": "<one-line gloss>", "ts": time.time()}
p = "<feature_path>/ARTIFACTS.jsonl"
with open(p, "a", encoding="utf-8") as f:
    f.write(json.dumps(rec) + "\n")
'
```

**3. Advisory board POST (skip-if-down).** Mirror the artifact to the board so other agents
see it without opening the file. If the server is unreachable (connection refused / non-200),
skip silently — `ARTIFACTS.jsonl` and the file are the source of truth.
```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{"feature": "<feature>", "from": "<agent>", "type": "artifact", "board": "feature",
       "scope": "<feature>", "text": "<1-2 sentence description>",
       "artifact_path": "<out_path>", "artifact_type": "md"}'
```

---

## Completion report (AGENT_DONE) — your FINAL action

`AGENT_DONE` is the authoritative signal the supervisor reads to end this stage, and the runner's
early-advance acts on it the instant it appears in the central DB — it does **not** wait for your
process to exit. So this is the **last thing you do**, with NOTHING after it:

- Write it ONLY after every output file is written **and** every board write is done — including
  deliverable board state (a seeded task DAG: `type=goal` / `type=task`) and any advisory
  `artifact` / `status` / `decision` posts. Anything that writes to the board comes BEFORE this.
- If the task above lists later steps (e.g. "Post Tasks to Comms Board"), this runs **after all of
  them** — never mid-workflow. A completion report emitted early lets early-advance silently cut off
  the remaining steps, so the DAG you were supposed to seed never gets posted.
- The skill supplies only the *content* (role, result, conversation, summary, the `*_START` time);
  this fragment owns *when* (last) and *how* (below).

## Set `outcome` — success or failed (REQUIRED)

The AGENT_DONE carries an explicit `outcome` the supervisor's loop executor reads to decide
whether your task **succeeded** or **failed**. A clean process exit is **not** taken as success on
its own — you must say so. Judge honestly:

- `outcome: 'success'` — you completed the task and its acceptance/goal is met. Leave `error` empty (`''`).
- `outcome: 'failed'` — you could **not** complete it: a blocking dependency, an unmet requirement,
  a build/test you could not get to pass, or a hard limit you hit. Put the one-sentence reason in
  `error`. Still write the report — a reported failure lets the DAG block dependents loudly instead
  of draining a broken branch as "done".

When genuinely unsure between the two, prefer `failed` with an `error`: a false success hides broken
work (the costlier mistake), while a false failure only re-surfaces the task.

Write the AGENT_DONE event to the **central DB** via eventlog. This is **mandatory** — the
supervisor reads it as the authoritative result.

## Compute wall seconds

1. Compute wall_seconds: `python3 -c "import time; print(int(time.time()) - BUILD_START)"`

## Sum subagent tokens

2. Sum `total_tokens` and `tool_uses` across **ALL** subagents spawned during this stage (analyze, scouts, implement/review, and every fix/retry iteration). Parse each subagent's `<usage>` block (look for `subagent_tokens:` and `tool_uses:` lines in the tool result) and add to running totals. `duration_ms = 0` if absent.

## Estimate cost

3. Compute `cost_usd` from `total_tokens` and `model` using an 80/20 input/output token split:

   | Model prefix | Input $/MTok | Output $/MTok |
   |---|---|---|
   | `claude-opus-4` | 15.00 | 75.00 |
   | `claude-sonnet-4` | 3.00 | 15.00 |
   | `claude-haiku-4` | 0.80 | 4.00 |
   | other / unknown | — | set `cost_usd = 0.0` |

   Formula:
   ```
   in_est  = total_tokens * 0.8
   out_est = total_tokens * 0.2
   cost_usd = round((in_est / 1_000_000 * input_rate) + (out_est / 1_000_000 * output_rate), 6)
   ```

## Write the AGENT_DONE event

4. Write the event — **do not invoke a skill**, run this command:

```bash
python3 -c "
import json, datetime, pathlib
ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
event = {
  'type': 'AGENT_DONE',
  'agent': 'AGENT_ROLE',
  'model': 'MODEL_ID',
  'conversation': CONV_N,
  'result': 'DONE',
  'outcome': 'OUTCOME',
  'error': 'ERROR_REASON',
  'summary': 'SUMMARY_SENTENCE',
  'total_tokens': TOTAL_TOKENS,
  'tool_uses': TOOL_USES,
  'wall_seconds': WALL_SECONDS,
  'cost_usd': COST_USD,
  'ts': ts,
  'schema_version': 1,
}

_written = False

# Primary path: POST to HTTP endpoint
try:
    import urllib.request, urllib.error
    body = json.dumps({
        'type': event['type'],
        'feature': '<feature>',
        'project_root': str(pathlib.Path.cwd()),
        'payload': event,
    }).encode('utf-8')
    req = urllib.request.Request(
        'http://127.0.0.1:8765/runner/event',
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=3) as resp:
        if resp.status == 200:
            print('AGENT_DONE written via HTTP /runner/event')
            _written = True
except Exception:
    pass  # server unreachable — fall through to local fallback

# Fallback: write via eventlog (DB-primary, EVENTS.jsonl secondary)
if not _written:
    try:
        from pathly_orchestrator.eventlog import append_event as _ae
        _ae('<feature_path>', event)
        print('AGENT_DONE written to DB (fallback)')
    except Exception as _exc:
        path = pathlib.Path('<feature_path>/EVENTS.jsonl')
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'a', encoding='utf-8') as _f:
            _f.write(json.dumps(event) + chr(10))
        print(f'AGENT_DONE written to EVENTS.jsonl (last resort: {_exc})')

# Always dual-write to EVENTS.jsonl as backup
path = pathlib.Path('<feature_path>/EVENTS.jsonl')
path.parent.mkdir(parents=True, exist_ok=True)
with open(path, 'a', encoding='utf-8') as _f:
    _f.write(json.dumps(event) + chr(10))
"
```

## Post to activity log

5. POST to the activity log — non-blocking; skip silently if server is unavailable:

```bash
pathly-fsm-call record-activity \
  --agent "AGENT_ROLE" \
  --feature "<feature>" \
  --summary "SUMMARY_SENTENCE" \
  --conversation CONV_N \
  --model "MODEL_ID" \
  --total-tokens TOTAL_TOKENS \
  --tool-uses TOOL_USES \
  --wall-seconds WALL_SECONDS \
  --cost-usd COST_USD
```

## Placeholder reference

Replace the UPPER_CASE placeholders with actual values:
- `AGENT_ROLE` — e.g. `builder`, `reviewer`, `tester`, `planner`
- `MODEL_ID` — model used in this stage (e.g. `claude-sonnet-4-6`)
- `CONV_N` — integer conversation number (0 for non-build stages like plan/review/test)
- `OUTCOME` — `success` or `failed` (see "Set `outcome`" above) — the supervisor's authoritative pass/fail signal
- `ERROR_REASON` — one-sentence failure reason when `OUTCOME` is `failed`; empty string `''` when `success`
- `SUMMARY_SENTENCE` — one sentence: what was done and the outcome
- `TOTAL_TOKENS`, `TOOL_USES`, `WALL_SECONDS` — from `<usage>` block or wall_seconds computation
- `COST_USD` — computed in step 3

## Return to orchestrator

`<feature>` and `<feature_path>` are pre-substituted by the runner — use the values as written.

Return. The orchestrator determines the next state from `transition_rules`.
