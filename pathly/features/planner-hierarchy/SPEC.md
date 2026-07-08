# SPEC - Planner Hierarchy: recursive Project -> Features -> Goals -> Tasks

> **Thesis:** Pathly has one decomposition pattern: a board-level parent item is
> split into sibling child items, those children are posted back to the board with
> dependency wiring, and executors drain the resulting work. This feature lifts
> the existing goal -> task-DAG model up two levels so one project spec can flow
> through project -> features -> goals -> tasks, with the board at each level as
> the shared-awareness substrate.

This feature is a multi-goal feature. The current implementation dogfoods the
model partially: G1 and G2 are implemented as board-native decomposers, while G3
remains the open import-modernization goal.

**Status as of 2026-07-08**

| Goal | Status | Notes |
|---|---|---|
| G0 - Reliability foundation | Mostly shipped | Loud no-DAG/no-child gates, code-query role fix, and invocation telemetry reconciliation are in place. |
| G1 - Feature -> goals | Shipped, one routing caveat | Skill, flow, route, UI, gate, and tests exist. The `full` tier must keep using the `feature-decompose` terminal emitter, not `planning/plan`, because the gate counts `type=goal` messages. |
| G2 - Project -> features | Shipped | Skill, consultation flow, route, UI, gate, tests, and feature scaffolding exist. G2 now has the same `light|full|consultation` ladder as G1. |
| G3 - PRD/BMAD import -> goal-DAG | Not built | `planning/prd-import` still emits the old conversation/phases model and `CONVERSATION_PROMPTS.md`. |

---

## The Recursion

```text
PROJECT board   <- drop a big spec, PRD, BMAD PRD, or free text
   |
   | project-decompose: split into FEATURES + scaffold each feature SPEC.md
   v
FEATURE board   <- each feature's starting spec
   |
   | feature-decompose: split into GOALS
   | consultation tier: team artifacts first, then sibling goal cards
   v
GOAL card
   |
   | goal planner: split into TASKS, the DAG
   v
TASKS -> executors drain through single, loop, or team strategy
```

The invariant is the same at every level:

- read the parent input and the current board context;
- propose 2-5 sibling children;
- post child cards with `type`, `scope`, `slug`, `depends_on`, and `context_refs`;
- stop for human review before auto-cascading to the next level;
- fail loudly when the expected child cards were not seeded.

Only the terminal emit type changes by altitude:

| Parent | Terminal skill | Child cards |
|---|---|---|
| Project/spec | `planning/project-decompose` | `type=feature` on the project board |
| Feature | `planning/feature-decompose` | `type=goal` on the feature board |
| Goal | `planning/plan` or `planning/dag-sketch` | `type=task` DAG items |

---

## Dependency Model

Dependencies are part of the hierarchy at every level, not only inside task DAGs.
The same `depends_on` field is used for sibling ordering across features, goals,
and tasks.

| Parent level | Child type | Dependency example | Enforced today |
|---|---|---|---|
| Project | `type=feature` | `dashboard` depends on `auth-service` | Planning metadata; consumed by planners/UI/humans |
| Feature | `type=goal` | `frontend` depends on `backend-api` | Planning metadata; consumed by planners/UI/humans |
| Goal | `type=task` | `wire-submit` depends on `build-form` | Executor DAG scheduling |

Rules:

- `depends_on` always stores returned board `message_id` values, never slugs,
  titles, filenames, or human labels.
- Dependency edges only connect siblings on the same board scope:
  - feature -> feature on the project board;
  - goal -> goal on one feature board;
  - task -> task under one `goal_id`.
- Upstream children are posted first so their `message_id`s are available for
  downstream `depends_on` arrays.
- Importers may read dependency names from BMAD/PRD text, but they must resolve
  those names to posted `message_id`s before writing `depends_on`.
- Feature and goal dependencies are currently ordering/context constraints, not
  automatic multi-feature scheduling. Task dependencies are executable DAG
  constraints today.

---

## Current State

| Level | Status | Notes |
|---|---|---|
| Goal -> Tasks | Exists | `planning/plan` and `planning/dag-sketch` emit task DAGs. The bottom level now has loud failure behavior when no DAG is seeded. |
| Feature -> Goals | Exists | `planning/feature-decompose`, `feature-consultation.flow.yaml`, `/comms/features/decompose`, UI config, `NO_GOALS_SEEDED`, and tests are present. |
| Project -> Features | Exists | `planning/project-decompose`, `project-consultation.flow.yaml`, `/comms/project/decompose`, UI config, `NO_FEATURES_SEEDED`, feature-board scaffolding, and tests are present. |
| BMAD / PRD import | Legacy | `planning/prd-import` parses PRDs into the old conversation model. It must be modernized to seed feature and goal cards directly. |

---

## Goals

### G0 - Reliability Foundation

The upper levels are only useful if the bottom level cannot silently succeed
without a usable DAG.

Delivered or expected foundation:

- loud failure when a decompose seeds no task DAG: `NO_DAG_SEEDED`;
- code-query actually fires in loop agents through the role-gate fix;
- coherent per-agent cost/token telemetry through invocation reconciliation;
- child-count gates at each altitude:
  - goal -> tasks requires a task DAG;
  - feature -> goals requires at least 2 `type=goal` cards or `NO_GOALS_SEEDED`;
  - project -> features requires at least 2 `type=feature` cards or `NO_FEATURES_SEEDED`.

### G1 - Feature Planner: Feature -> Goals

A decomposer reads a feature's `SPEC.md`, feature-board context, and any
feature-level artifacts, then posts 2-5 sibling goal cards. Typical goals are
`backend-api`, `frontend-dashboard`, `db-schema`, or `migration-path`. Each goal
has a scope statement, acceptance boundary, optional `depends_on`, and
`context_refs` pointing at shared feature artifacts.

The rigor ladder is:

| Tier | What runs | Produces |
|---|---|---|
| `light` | `planning/feature-decompose` directly | bare sibling goal cards from the feature spec |
| `full` | `planning/feature-decompose` with deeper planning expectations | goals with scope, acceptance boundaries, and dependency wiring |
| `consultation` | PO -> architect -> researcher -> designer -> `planning/feature-decompose` | feature-level artifacts first, then sibling goal cards that inherit those artifacts |

Important contract: `full` must still terminate through `planning/feature-decompose`.
It must not dispatch to `planning/plan`, because `planning/plan` emits `type=task`
DAG items for an individual goal, while the G1 gate requires `type=goal` siblings.

After emitting goals, the flow stops for human review. It does not automatically
decompose each goal into tasks.

### G2 - Project Planner: Project Spec -> Features

A decomposer reads a project-level spec on the project board or
`pathly/project/SPEC.md`, then posts 2-5 feature cards on the project board. Each
feature card is paired with a materialized feature workspace:
`pathly/features/<slug>/SPEC.md`, plus the feature's own board/root goal so it can
be decomposed into goals later.

G2 now mirrors G1's rigor ladder:

| Tier | What runs | Produces |
|---|---|---|
| `light` | `planning/project-decompose` directly | sibling feature cards and starting feature specs |
| `full` | `planning/project-decompose` with deeper planning expectations | features with scope, acceptance boundaries, starting specs, and dependencies |
| `consultation` | PO -> architect -> researcher -> designer -> `planning/project-decompose` | project-level artifacts first, then feature cards that inherit those artifacts |

After emitting features, the flow stops for human review. It does not
automatically decompose each feature into goals.

### G3 - Modernize PRD/BMAD Import

Rework `planning/prd-import` so imports feed the goal-DAG hierarchy instead of
the old conversation model.

Required behavior:

- detect BMAD structure, especially epics/stories sections, versus a generic PRD;
- parse arguments as `<path/to/PRD.md> [project_scope_or_root]`, not the legacy
  `<feature-name> <path/to/PRD.md>` contract;
- map PRD title to the project identity, using an explicit project scope/root
  when provided and otherwise deriving a readable project key from the title;
- map BMAD epics to project-board `type=feature` cards via `POST /comms/post`;
- map BMAD stories to feature-board `type=goal` cards via `POST /comms/post`;
- scaffold `pathly/features/<slug>/SPEC.md` for every emitted feature, reusing the
  `planning/project-decompose` materialization mechanics;
- materialize each emitted feature's own board/root goal so the feature can be
  opened and decomposed independently;
- wire feature `depends_on` when the PRD specifies epic dependencies, using
  posted feature `message_id` values rather than slugs;
- wire goal `depends_on` when BMAD story dependencies are explicit, using posted
  goal `message_id` values;
- preserve the hierarchy-wide dependency contract: features may depend on
  sibling features, goals may depend on sibling goals, and later task DAGs may
  depend on sibling tasks under the goal;
- for generic PRDs, still emit 2-5 project-board `type=feature` cards;
- remove the legacy `CONVERSATION_PROMPTS.md`, phase split, and old conversation
  output entirely.

Canonical posting rules:

- **Idempotency first.** Before posting feature children, query existing project
  features:
  ```bash
  curl -s "http://127.0.0.1:8765/comms?board=project&scope=$PROJECT&type=feature"
  ```
  If the project already has 2 or more `type=feature` cards, do not duplicate
  the feature set.
- **Feature POST shape.** For every epic/generic feature, post to the project
  board with this contract:
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
      "text": "<feature-slug>: <title>\n\nScope: <scope>\n\nDone when:\n- <boundary>",
      "depends_on": ["<message_id_of_feature_dependency>"],
      "context_refs": [...]
    }'
  ```
  Record every returned `message_id`; downstream feature dependencies point to
  those ids.
- **Feature-board setup.** For each feature, scaffold
  `pathly/features/<feature-slug>/SPEC.md` and ensure the feature board/root goal
  exists, matching `planning/project-decompose` behavior.
- **Goal idempotency.** Before posting story goals for a feature, query existing
  goals:
  ```bash
  curl -s "http://127.0.0.1:8765/comms?feature=$FEATURE&scope=$FEATURE&type=goal"
  ```
  If the feature already has 2 or more `type=goal` cards, do not duplicate that
  goal set.
- **Goal POST shape.** For every BMAD story, post to the feature board with this
  contract:
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
      "text": "<goal-slug>: <title>\n\nScope: <scope>\n\nDone when:\n- <boundary>",
      "depends_on": ["<message_id_of_goal_dependency>"],
      "context_refs": [...]
    }'
  ```
  Record every returned `message_id`; downstream goal dependencies point to those
  ids.
- **Task DAG snippet applicability.** The existing task-DAG posting contract is
  useful for its mechanics: idempotency guard, exact `/comms/post` payload,
  dependency wiring by returned `message_id`, no retry loop when the server is
  down, and completion-report disclosure. Do not copy the task payload into G3:
  G3 emits `type=feature` and `type=goal`, not `type=task`, and `goal_id` belongs
  only to task children under an existing goal.
- **Skip-if-down.** If the comms server is unreachable, scaffold local
  `SPEC.md` files where possible and record in the completion report that board
  seeding did not complete. Do not retry in a loop.

Composition requirement:

```yaml
planning/prd-import:
  no_defaults: true
  fragments:
    - code-query
    - comms-post
    - completion-report
```

Done means a BMAD PRD import posts feature cards on the project board and goal
cards on each feature board, and creates no `CONVERSATION_PROMPTS.md` or phases
files. This can be implemented before any higher-level decompose route changes
because it posts directly to `/comms/post`.

---

## Design Constraints

- **Storage stays nested and readable.** Feature workspaces live at
  `pathly/features/<feature>/`; sibling goals live under that feature's board and
  may materialize under `pathly/features/<feature>/goals/<goal>/` as needed. Do
  not flatten goals into the project root.
- **Board is the awareness substrate at every level.** Decompose prompts must
  read sibling cards and relevant artifacts from the current board scope.
- **Reuse the same decomposition primitive.** New levels are terminal emitters
  plus thin routes/flows/gates, not new flow engines.
- **Produce once, inherit many.** Consultation artifacts produced at project or
  feature level are passed down through `context_refs` instead of being
  re-derived independently by every child.
- **Human checkpoint between levels.** Project -> features and feature -> goals
  stop after seeding children. The next altitude runs only after review.

---

## Tests Expected for G3

Add `tests/test_prd_import_new.py` mirroring the patterns in
`tests/test_project_decompose.py` and `tests/test_feature_decompose.py`.

Required cases:

1. `composition.yaml` registers `planning/prd-import` with `no_defaults: true`,
   `code-query`, `comms-post`, and `completion-report`.
2. The composed `planning/prd-import` prompt contains the project-board
   `type=feature` POST contract and feature-board `type=goal` POST contract.
3. The composed prompt no longer contains legacy plan-file generation for
   `CONVERSATION_PROMPTS.md`, `PROGRESS.md` phases, or 4/8-file PRD plan output.
4. The prompt requires idempotency checks before posting project features and
   feature goals.
5. The prompt requires `depends_on` to use returned `message_id` values.
6. The prompt distinguishes dependency levels: epic dependencies become
   feature-card `depends_on`; story dependencies become goal-card `depends_on`;
   task dependencies remain the goal-level DAG contract.
7. The prompt requires feature `SPEC.md` scaffolding for emitted features.
8. A BMAD PRD fixture maps epics to features and stories to goals. If the import
   remains prompt-only, assert the contract text deterministically; if parser
   helpers are added, unit-test those helpers directly.
9. A generic non-BMAD PRD fixture still maps to 2-5 project-board feature cards.

Verification command:

```powershell
$env:PYTHONPATH = "src"; python -m pytest tests/test_prd_import_new.py -q
```

---

## Sequencing

Original sequencing was bottom-up:

```text
G0 -> G1 -> G2 -> G3
```

Current practical sequencing is:

```text
G3 next
```

G1 and G2 are already shipped enough for G3 to target their board-native model.
The remaining caution is to preserve the child-type gates: import must post
`type=feature` on the project board and `type=goal` on feature boards, never
legacy conversation phases.

---

## Non-Goals

- Parallel cross-feature execution. That belongs to the separate P3/worktree
  fan-in track.
- Replacing every executor strategy. The classic team/FSM pipeline can remain
  as one executor strategy while board/DAG becomes the primary planning model.
