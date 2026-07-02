## Creating a feature board

Run this when you START a new feature. A board is not a separate object you allocate — a
feature's board exists as soon as its ROOT GOAL is posted at `board=feature, scope=<feature>`.
Posting that goal is the act that materializes the board and gives the feature a card in Studio.

Advisory + idempotent: if the FSM server is unreachable, skip silently (the feature's files
under `<feature_path>` are the source of truth); if the feature already has a goal, reuse it —
never post a duplicate.

### 1. Reuse or create the feature's root goal

Look the feature up first:
```bash
curl -s "http://127.0.0.1:8765/comms?feature=<feature>&scope=<feature>&type=goal"
```
- **A `type=goal` message already exists** → the board is already created; use its `id` as
  `$GOAL_ID` and stop (do not post a duplicate).
- **None exists** → post the root goal. This POST is what creates the board:
```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "<feature>",
    "from": "<agent>",
    "type": "goal",
    "text": "Goal: <one-line description of the feature>",
    "board": "feature",
    "scope": "<feature>",
    "executor": "single"
  }'
```
Record the returned `"message_id"` as `$GOAL_ID` — later task/artifact posts stamp it.

### 2. Workspace

The feature's workspace is `<feature_path>` (the flat feature home, e.g.
`pathly/features/<feature>/`). Write the feature's files directly there — never invent a
different location, and do not nest them under a `plans/` subdir. Create it if it does not exist.

### Creating several features in one run

Repeat step 1 per feature with a distinct `<feature>` name — each becomes its own board (scope)
and its own workspace. A feature name must be filesystem-safe and must NOT be a reserved
structural name: `features`, `project`, `plans`, `goals`, `debugs`, `explorations`, `fixes`,
`lessons`, `board-artifacts`, `pipeline-walkthrough`. Slugify anything that collides.
