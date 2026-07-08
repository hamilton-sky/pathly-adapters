# prd-import

Terminal emitter for importing a PRD or BMAD PRD into the board-native hierarchy:
project -> features -> goals -> task DAGs. `bmad-import` is an alias; both routes
resolve here.

This skill does **not** create legacy conversation plan files. It posts feature
and goal cards to the Comms Board and scaffolds starting feature specs. Task DAGs
are created later by decomposing each goal with the normal goal-level planner.

## Step 0 - Parse arguments

`$ARGUMENTS` is:

```text
<path/to/PRD.md> [project_scope_or_root]
```

- `PRD_PATH` is the first token.
- `PROJECT` is the remaining text, if present.
- If `PROJECT` is omitted, derive a readable project key from the PRD title.

Do not use the old `<feature-name> <path/to/PRD.md>` contract. A PRD maps to a
project/import scope; epics map to features, and stories map to goals.

If `PRD_PATH` is missing, stop and report:

```text
Route: prd-import <path/to/PRD.md> [project_scope_or_root]
Example: prd-import docs/payments-prd.md C:/Users/Yafit/my-app
```

Check that `PRD_PATH` exists. If not, stop and report the missing file.

## Step 1 - Read and classify the PRD

Read the full PRD file.

Classify it as BMAD-structured when it has clear epic/story structure, for example:

- `## Epic ...`, `### Epic ...`, or numbered `Epic N` sections;
- story sections under epics;
- explicit epic/story IDs;
- explicit dependency fields such as `Depends on`, `Dependencies`, `After`, or
  `Blocked by`.

Otherwise treat it as a generic PRD.

Extract:

- project title and overview;
- epics with title, scope, acceptance boundary, and dependency names;
- stories under each epic with title, scope, acceptance boundary, and dependency names;
- global constraints, out-of-scope notes, risks, and tech constraints.

## Step 2 - Read project context

Read project guidance and board context before proposing cards:

1. Project guidance files and rule files, if present.
2. Existing project-board features:
   ```bash
   curl -s "http://127.0.0.1:8765/comms?board=project&scope=$PROJECT&type=feature"
   ```
3. Existing artifacts on the project board:
   ```bash
   curl -s "http://127.0.0.1:8765/comms/artifacts?board=project&scope=$PROJECT"
   ```
4. Board context:
   ```bash
   curl -s -X POST http://127.0.0.1:8765/comms/agent-context \
     -H "Content-Type: application/json" \
     -d '{"scope": "$PROJECT"}'
   ```

Skip missing files or unreachable optional context sources, but do not skip the
PRD itself.

## Step 3 - Map PRD content to hierarchy

### BMAD PRD

- PRD title / explicit project scope -> `PROJECT`
- Epics -> project-board `type=feature` cards
- Stories -> feature-board `type=goal` cards
- Epic dependencies -> feature-card `depends_on`
- Story dependencies -> goal-card `depends_on`

### Generic PRD

Propose 2-5 project-board features from the PRD. Use natural product slices, not
implementation phases. Each feature must be independently reviewable and should
later decompose into 2-5 goals.

## Step 4 - Dependency rules

Dependencies are preserved at every hierarchy level, but only task dependencies
are executable scheduler DAG edges today.

- Feature dependencies are planning/review ordering metadata between sibling
  `type=feature` cards on the project board.
- Goal dependencies are planning/review ordering metadata between sibling
  `type=goal` cards on one feature board.
- Task dependencies remain the executable DAG under one goal.

`depends_on` must always store returned board `message_id` values, never slugs,
titles, filenames, or human labels.

Post upstream cards first. Record each POST response's `"message_id"` and resolve
later dependency names to those ids.

## Step 5 - Seed project-board feature cards

### 5a. Idempotency guard

Before posting features:

```bash
curl -s "http://127.0.0.1:8765/comms?board=project&scope=$PROJECT&type=feature"
```

If the project already has 2 or more `type=feature` cards, do not duplicate the
feature set. Reuse existing feature ids when wiring downstream story goals.

### 5b. Scaffold each feature

For each emitted feature, create `pathly/features/<feature-slug>/` if absent and
write a starting `SPEC.md` with:

- title and problem statement;
- scope and out-of-scope;
- PRD source path;
- relevant epic/story source references;
- acceptance boundary;
- known constraints and risks.

### 5c. Materialize each feature board/root goal

Ensure the feature has its own feature board/root goal, matching
`planning/project-decompose` behavior. If a `type=goal` already exists at
`scope=<feature-slug>`, reuse it. Otherwise post:

```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "<feature-slug>",
    "from": "planner",
    "type": "goal",
    "board": "feature",
    "scope": "<feature-slug>",
    "executor": "single",
    "text": "Goal: <feature title>"
  }'
```

### 5d. Post each feature card

Post features in dependency order:

```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "$PROJECT",
    "from": "planner",
    "type": "feature",
    "board": "project",
    "scope": "$PROJECT",
    "slug": "<feature-slug>",
    "text": "<feature-slug>: <title>\n\nScope: <scope paragraph>\n\nDone when:\n- <boundary 1>\n- <boundary 2>",
    "depends_on": ["<message_id_of_feature_dependency>"],
    "context_refs": [
      {"artifact": "<artifact_path>", "anchor": ""}
    ]
  }'
```

Use `[]` or omit `depends_on` when there is no dependency. Record every returned
`message_id`.

## Step 6 - Seed feature-board goal cards

This step applies to BMAD stories. For generic PRDs, stop after feature cards
unless the PRD has clear story-level structure.

### 6a. Idempotency guard

For each feature:

```bash
curl -s "http://127.0.0.1:8765/comms?feature=$FEATURE&scope=$FEATURE&type=goal"
```

If the feature already has 2 or more `type=goal` cards, do not duplicate that
goal set.

### 6b. Post story goals

Post goals in dependency order:

```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "$FEATURE",
    "from": "planner",
    "type": "goal",
    "board": "feature",
    "scope": "$FEATURE",
    "slug": "<goal-slug>",
    "executor": "team",
    "text": "<goal-slug>: <title>\n\nScope: <scope paragraph>\n\nDone when:\n- <boundary 1>\n- <boundary 2>",
    "depends_on": ["<message_id_of_goal_dependency>"],
    "context_refs": [
      {"artifact": "pathly/features/<feature-slug>/SPEC.md", "anchor": ""}
    ]
  }'
```

Use `[]` or omit `depends_on` when there is no dependency. Record every returned
`message_id`.

## Step 7 - Skip-if-down fallback

If the comms server is unreachable:

- still scaffold local `pathly/features/<feature-slug>/SPEC.md` files where possible;
- write `pathly/project/PRD_IMPORT_PLAN.md` with the same feature/goal/dependency
  plan that would have been posted;
- record in the completion report that board seeding did not complete.

Do not retry in a loop. Do not claim success for board seeding when the board was
unreachable.

## Step 8 - Completion report

Supply to the `completion-report` fragment:

- `agent: planner`
- `result: DONE` when board seeding succeeded, otherwise `BLOCKED`
- `conversation: 0`
- `summary: "prd-import seeded N features and M goals for $PROJECT from $PRD_PATH"`
- `outcome: success` or `failed`

The `completion-report` fragment writes AGENT_DONE as your final action.
Nothing may run after it.
