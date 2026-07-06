# feature-decompose

Terminal emitter for splitting a feature into sibling goal cards on the feature board.
This one skill covers every rigor tier: run standalone after a quick spec review (light)
or as the final stage of a consultation flow (consultation tier — PO→architect→researcher→designer
write feature-level artifacts first, then this skill emits the goals).

After emitting goals the flow **stops for human review** — goals are not auto-cascaded into
task DAGs. The human edits the goal set, then decomposes each goal individually.

## Step 0 — Parse arguments

`$FEATURE` is the feature slug (folder name under `pathly/features/`).

## Step 1 — Read feature context

Read the following (skip missing files silently):

1. **Feature spec** — try `pathly/features/$FEATURE/SPEC.md`, then `pathly/features/$FEATURE/FEATURE_INDEX.md`.
   This is the primary decomposition input.

2. **Existing goals on the board** — check for goals already seeded (idempotency):
   ```bash
   curl -s "http://127.0.0.1:8765/comms?feature=$FEATURE&scope=$FEATURE&type=goal"
   ```

3. **Feature-level artifacts** — produced by the consultation tier (absent in light tier):
   ```bash
   curl -s "http://127.0.0.1:8765/comms/artifacts?board=feature&scope=$FEATURE"
   ```
   Collect the `artifact_path` of each artifact — used in goal `context_refs` below.

4. **Board context** — open decisions, prior research, and discoveries (skip-if-down):
   ```bash
   curl -s -X POST http://127.0.0.1:8765/comms/agent-context \
     -H "Content-Type: application/json" \
     -d '{"scope": "$FEATURE"}'
   ```

## Step 2 — Idempotency guard

If the existing goals query in Step 1 returned **≥ 2** `type=goal` messages scoped to
`$FEATURE`, the goal set is already seeded. Skip Steps 3–4 and go directly to Step 5.

## Step 3 — Propose 2–5 sibling goals

Based on the feature spec, board context, and feature artifacts, propose **2–5 sibling goals**.
Each goal must have:

- **slug** — short, readable identifier (e.g. `backend-api`, `frontend-dashboard`, `db-schema`).
  Use kebab-case, max 3 words.
- **title** — one sentence: what this goal delivers when complete.
- **scope** — one short paragraph: what is in scope, what is explicitly out of scope.
- **acceptance boundary** — 2–4 observable bullets: conditions that mark this goal DONE.
- **depends_on** — which other sibling goals (by slug) this one depends on, if any.
  Wire only real dependencies (e.g. frontend depends on the backend API contract being stable).

Good decomposition rules:
- Goals are independently runnable — avoid tight coupling between sibling goals.
- Wire `depends_on` only when the downstream goal **cannot** start without the upstream output.
- 2–3 goals is better than 5 when in doubt — fewer goals = faster iteration.
- Each goal should map to one natural team pipeline run (plan → build → review → test).

## Step 4 — Post goal cards to the board

Post goals in dependency order (upstream goals first). For each goal:

```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "$FEATURE",
    "from": "planner",
    "type": "goal",
    "board": "feature",
    "scope": "$FEATURE",
    "slug": "<slug>",
    "executor": "team",
    "text": "<slug>: <title>\n\nScope: <scope paragraph>\n\nDone when:\n- <bullet 1>\n- <bullet 2>",
    "depends_on": ["<message_id of upstream sibling goal — omit field if none>"],
    "context_refs": [
      {"artifact": "<artifact_path from Step 1>", "anchor": ""}
    ]
  }'
```

Field rules:
- `slug` — the short identifier; must be unique within the feature.
- `executor` — always `"team"` (each goal runs the full team pipeline when decomposed).
- `depends_on` — array of `message_id` values from prior POSTs in this step.
  Use `[]` (empty array) or omit the field when there is no dependency.
- `context_refs` — list every feature-level artifact found in Step 1
  (e.g. `ARCHITECTURE_PROPOSAL.md`, `RESEARCH.md`, `DESIGN.md` at the feature root).
  In the light tier no consultation ran first, so set `context_refs: []`.
  In the consultation tier these artifacts ARE the produce-once cross-goal design — every goal
  inherits them so each downstream task DAG consumes the shared contract instead of re-deriving it.
- Record each returned `"message_id"` to use in later goals' `depends_on`.

**Fallback when server is unreachable:** Write goal proposals to
`pathly/features/$FEATURE/GOAL_PLAN.md` (one section per goal, same fields as above).
Continue to Step 5.

## Step 5 — Gate: require ≥ 2 goals seeded

Count `type=goal` messages on the board for `$FEATURE`:

```bash
curl -s "http://127.0.0.1:8765/comms?feature=$FEATURE&scope=$FEATURE&type=goal"
```

If the count is **< 2**:
- Write `pathly/features/$FEATURE/NO_GOALS_SEEDED.md`:
  ```
  NO_GOALS_SEEDED
  feature-decompose ran but fewer than 2 goals are on the board.
  Check: comms server reachable? Spec readable? Goal POST responses OK?
  ```
- Set `outcome: failed`, `error: "goal seeding produced fewer than 2 goals"`.
- Run the completion report (Step 6) and stop.

If the count is **≥ 2**: proceed to Step 6 with `outcome: success`.

## Step 6 — Completion report

Supply to the `completion-report` fragment:
- `agent: planner`
- `result: DONE`
- `conversation: 0`
- `summary: "feature-decompose seeded N goals for $FEATURE: [slug1, slug2, …]"` where N is the
  count of goals now on the board.
- `outcome: success` (or `failed` — see Step 5)

The `completion-report` fragment writes AGENT_DONE as your **final action**.
Nothing may run after it.
