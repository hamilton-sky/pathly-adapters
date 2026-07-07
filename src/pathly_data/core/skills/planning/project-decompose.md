# project-decompose

Terminal emitter for splitting a big project spec into sibling FEATURE cards on the project board.
This one skill covers every rigor tier: run standalone after a quick spec review (light) or as the
final stage of a consultation flow (consultation tier — PO→architect→researcher→designer write
project-level artifacts first, then this skill emits the features).

Unlike `feature-decompose` (which posts goal cards *in place* on the feature board), each feature
this skill emits ALSO gets a filesystem home: `pathly/features/<slug>/` with a starting `SPEC.md`,
plus its own feature board (root goal) so a human can immediately open it and decompose it into
goals. That materialization is the one thing this level adds — everything else mirrors
`feature-decompose` exactly, one altitude up.

After emitting features the flow **stops for human review** — features are not auto-cascaded into
goals. The human edits the feature set, then decomposes each feature individually (feature→goals).

## Step 0 — Parse arguments

`$PROJECT` is the project-board scope key — the **normalized project root path** (e.g.
`C:/Users/Yafit/pathly-adapters`; backslashes → `/`, no trailing slash). This is the exact scope
Studio and Pathly's prompt-injection both use for the project board, so posting feature cards at
this scope is what makes them visible in the UI **and** injectable as siblings into the next
feature's decompose prompt. The big spec has been dropped on the project board (a `type=spec` or
free-text message) or lives at `pathly/project/SPEC.md`.

## Step 1 — Read project context

Read the following (skip missing sources silently):

1. **Big spec** — the decomposition input. Try, in order:
   - the project board's spec message —
     `curl -s "http://127.0.0.1:8765/comms?board=project&scope=$PROJECT"` (take the largest
     `type=spec` / free-text message);
   - `pathly/project/SPEC.md`, then `pathly/project/PROJECT_INDEX.md`.

2. **Existing features on the board** — check for features already seeded (idempotency):
   ```bash
   curl -s "http://127.0.0.1:8765/comms?board=project&scope=$PROJECT&type=feature"
   ```

3. **Project-level artifacts** — produced by the consultation tier (absent in light tier):
   ```bash
   curl -s "http://127.0.0.1:8765/comms/artifacts?board=project&scope=$PROJECT"
   ```
   Collect each `artifact_path` — used in feature `context_refs` below.

4. **Board context** — open decisions, prior research, and discoveries (skip-if-down):
   ```bash
   curl -s -X POST http://127.0.0.1:8765/comms/agent-context \
     -H "Content-Type: application/json" \
     -d '{"scope": "$PROJECT"}'
   ```

## Step 2 — Idempotency guard

If the existing-features query in Step 1 returned **≥ 2** `type=feature` messages on the project
board scoped to `$PROJECT`, the feature set is already seeded. Skip Steps 3–4 and go directly to
Step 5.

## Step 3 — Propose 2–5 sibling features

Based on the big spec, board context, and project artifacts, propose **2–5 sibling features**.

**Sibling awareness.** The `## Communication Board` block injected into your prompt already carries
the OTHER `type=feature` cards on this project board (via `retrieve_board_context`, keyed by the
same normalized project-root scope) plus any project-level artifacts referenced by `context_refs`.
Read them first: do **not** re-propose a feature a sibling already covers, and wire `depends_on`
against the sibling slugs that are already on the board.

Each feature must have:

- **slug** — short, readable, filesystem-safe kebab-case (max 3 words), e.g. `invoice-export`,
  `auth-service`, `admin-dashboard`. It must NOT be a reserved structural name (`features`,
  `project`, `plans`, `goals`, `debugs`, `explorations`, `fixes`, `lessons`, `board-artifacts`,
  `pipeline-walkthrough`) — slugify or suffix anything that collides.
- **title** — one sentence: what this feature delivers when complete.
- **scope** — one short paragraph: what is in scope, what is explicitly out of scope.
- **starting spec** — 3–8 sentences seeding the feature's own SPEC.md: the problem, the deliverable,
  and any known constraints. This becomes `pathly/features/<slug>/SPEC.md`.
- **acceptance boundary** — 2–4 observable bullets: conditions that mark this feature DONE.
- **depends_on** — which other sibling features (by slug) this one depends on, if any. Wire only
  real dependencies (e.g. `admin-dashboard` depends on `auth-service`'s API being stable).

Good decomposition rules (same as feature→goals, one level up):
- Features are independently shippable — avoid tight coupling between siblings.
- Wire `depends_on` only when the downstream feature **cannot** start without the upstream output.
- 2–3 features is better than 5 when in doubt — fewer features = faster iteration.
- Each feature should map to one natural feature→goals decomposition (backend / frontend / db / …).

## Step 4 — Materialize + post each feature

Process features in dependency order (upstream features first). For each feature:

**4a. Scaffold the feature workspace.** Create `pathly/features/<slug>/` if it is absent and write
the Step-3 starting spec to `pathly/features/<slug>/SPEC.md`. Feature files live FLAT under this
dir — never nest them under a `plans/` subdir.

**4b. Materialize the feature's own board** (reuse `create-feature` mechanics) — post its root goal
so the feature gets a Studio card and a board ready for feature→goals. Idempotent: if a `type=goal`
already exists at `scope=<slug>`, reuse it and do not post a duplicate.
```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "<slug>",
    "from": "planner",
    "type": "goal",
    "board": "feature",
    "scope": "<slug>",
    "executor": "single",
    "text": "Goal: <feature title>"
  }'
```

**4c. Post the feature card on the PROJECT board** — the sibling card, aware of the others:
```bash
curl -s -X POST http://127.0.0.1:8765/comms/post \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "$PROJECT",
    "from": "planner",
    "type": "feature",
    "board": "project",
    "scope": "$PROJECT",
    "slug": "<slug>",
    "text": "<slug>: <title>\n\nScope: <scope paragraph>\n\nDone when:\n- <bullet 1>\n- <bullet 2>",
    "depends_on": ["<message_id of upstream sibling feature — omit field if none>"],
    "context_refs": [
      {"artifact": "<artifact_path from Step 1>", "anchor": ""}
    ]
  }'
```

Field rules:
- `slug` — the short identifier; must be unique within the project.
- `depends_on` — array of `message_id` values from prior feature POSTs in this step (the 4c posts).
  Use `[]` (empty array) or omit the field when there is no dependency.
- `context_refs` — list every project-level artifact found in Step 1 (e.g. `ARCHITECTURE_PROPOSAL.md`,
  `RESEARCH.md`, `DESIGN.md` at `pathly/project/`). In the light tier no consultation ran first, so
  set `context_refs: []`. In the consultation tier these artifacts ARE the produce-once cross-feature
  design — every feature inherits them so each downstream feature→goals decompose consumes the shared
  contract instead of re-deriving it.
- Record each 4c response's `message_id` to use in later features' `depends_on`.

**Fallback when the server is unreachable:** Write feature proposals to
`pathly/project/FEATURE_PLAN.md` (one section per feature, same fields as above) and STILL scaffold
each `pathly/features/<slug>/SPEC.md` locally. Continue to Step 5.

## Step 5 — Gate: require ≥ 2 features seeded

Count `type=feature` messages on the project board for `$PROJECT`:

```bash
curl -s "http://127.0.0.1:8765/comms?board=project&scope=$PROJECT&type=feature"
```

If the count is **< 2**:
- Write `pathly/project/NO_FEATURES_SEEDED.md`:
  ```
  NO_FEATURES_SEEDED
  project-decompose ran but fewer than 2 features are on the project board.
  Check: comms server reachable? Spec readable? Feature POST responses OK?
  ```
- Set `outcome: failed`, `error: "feature seeding produced fewer than 2 features"`.
- Run the completion report (Step 6) and stop.

If the count is **≥ 2**: proceed to Step 6 with `outcome: success`.

## Step 6 — Completion report

Supply to the `completion-report` fragment:
- `agent: planner`
- `result: DONE`
- `conversation: 0`
- `summary: "project-decompose seeded N features for $PROJECT: [slug1, slug2, …]"` where N is the
  count of features now on the project board.
- `outcome: success` (or `failed` — see Step 5)

The `completion-report` fragment writes AGENT_DONE as your **final action**.
Nothing may run after it.
