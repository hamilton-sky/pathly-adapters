# Phase 0b — Planner → task DAG (wiring spec)

**Branch:** `feat/comms-board-dag-serial`
**Master design:** [../GOALS-DAG-EXECUTORS.md](../GOALS-DAG-EXECUTORS.md) · **Phase 0:** [PHASE-0-goals-schema.md](PHASE-0-goals-schema.md)
**Status:** ready to build. Grounded by the `phase0-recon` workflow (all paths verified against source).

> Goal of 0b: make decomposition emit a **machine-readable task DAG** onto the comms
> board (so the serial runner / builder can consume it), instead of prose-only plans.

---

## Keystone insight

The planner skill **already describes** posting tasks to the board — `plan.md` **Step 6
"Post Tasks to Comms Board" (lines ~266–306)** — but (a) the JSON it emits is missing
`goal_id`/`executor`/`artifact_path`, and (b) `/comms/post` **silently drops** `goal_id`
and `executor` today. So 0b = teach the write path to accept those fields, then upgrade
the planner's Step 6 contract. **No schema migration needed** (columns already exist).

---

## Step 1 — accept `goal_id` + `executor` on the write path (code, isolated, do first)

**File A — `src/pathly_orchestrator/http_server/blueprints/comms.py`** (`comms_post` route):
1. After `depends_on = data.get("depends_on")`, add:
   ```python
   goal_id = data.get("goal_id")
   executor = data.get("executor")
   ```
2. After the `depends_on` validation block, add type guards:
   ```python
   if goal_id is not None and not isinstance(goal_id, str):
       return jsonify({"error": "Field 'goal_id' must be a string or null"}), 400
   if executor is not None and not isinstance(executor, str):
       return jsonify({"error": "Field 'executor' must be a string or null"}), 400
   ```
3. Pass `goal_id=goal_id, executor=executor` into the `_post_message(...)` call.
4. Update the route docstring's "Optional:" line to include `goal_id, executor`.

**File B — `src/pathly_orchestrator/db/queries/comms.py`** (`post_message`):
1. Add params after `artifact_type`: `goal_id: str | None = None, executor: str | None = None`.
2. Extend the INSERT column list + placeholders with `goal_id, executor`.
3. Append `goal_id, executor` to the values tuple.

**Verify in isolation:** a single `POST /comms/post` with `goal_id`/`executor`, then
`GET /comms` (or read the row) confirms they persist. Add a focused test mirroring
`tests/test_comms_*`.

## Step 2 — upgrade the planner's Step 6 JSON (skill)

**File — `src/pathly_data/core/skills/planning/plan.md`**, Step 6 (lines ~290–300).
Per-phase POST, in phase order, recording each returned `message_id` into a local
`phase_N → message_id` map for `depends_on`:

```json
{
  "feature": "$FEATURE", "from": "planner", "type": "task",
  "text": "Phase N: <title> — <one-line description>",
  "board": "feature", "scope": "$FEATURE", "stage": "BUILDING",
  "conv": <int>,
  "depends_on": ["<phase_K_message_id>"],
  "goal_id": "$GOAL_ID",
  "artifact_path": "pathly/plans/$FEATURE/IMPLEMENTATION_PLAN.md",
  "artifact_type": "plan_artifact"
}
```
> **CORRECTION (2026-06-17):** `executor` is **NOT** on the task. Per
> [GOALS-DAG-EXECUTORS.md](../GOALS-DAG-EXECUTORS.md) §3, `executor` is stored on the
> **goal message only** (`single` is an ad-hoc action on a task and isn't stored). An
> earlier draft of this block carried `"executor":"single"` on the task — that was a typo;
> do not propagate it. The DB column exists on the row and is harmlessly NULL for tasks.
> (Also: `conv` is optional but, if present, MUST be a JSON **integer** literal — the route
> 400s on a string.)
Keep the existing **idempotency guard** (`GET /comms/tasks?feature=$FEATURE` → skip if
tasks exist) and **fail-silent on connection refused** (plan files are authoritative).

**Optional reinforcement:** add one imperative line to `core/agents/planning/planner.md`:
*"Before returning, you MUST execute plan.md Step 6 to seed the comms-board task DAG."*

**Propagation (mandatory — core skill edit):** after editing `plan.md`:
```
pathly-setup claude --apply --repair
python -m build
```
(The `comms.py` Python changes do NOT go through adapters.)

## Decision (LOCKED 2026-06-16) — `goal_id` = a real `type='goal'` message id

Use a **real goal message**, matching the schema design (NOT the `$FEATURE` shortcut).
The planner MUST:
1. Post one goal message **first**:
   `{feature:"$FEATURE", from:"planner", type:"goal", text:"Goal: <feature>", board:"feature", scope:"$FEATURE", executor:"single"}`
   → capture the returned `message_id` as `$GOAL_ID`.
2. Stamp every phase task with `goal_id:"$GOAL_ID"`.

Why: preserves the goal-message linkage for future `WHERE goal_id = <goal id>` joins and
per-goal grouping on the board. (The `$FEATURE` opaque-key shortcut was rejected.)

## Verified facts / gotchas (don't relearn these)

- **`get_ready_tasks` does NOT filter by `goal_id`** — only board+scope+type+task_status.
  So in 0b `goal_id` is grouping metadata, not a frontier filter. Fine for one goal per
  scope; multiple goals sharing a scope would need a follow-up filter change.
- A `comms_artifacts` side-row is created **only for `type=="artifact"`**, not `type=="task"`.
  For tasks, `artifact_path`/`artifact_type` are plain columns — which is what we want.
- `task_status` is auto-set to `"pending"` on insert when `type=="task"` (the frontier picks it up).
- `conv` must be an **int** or the post is rejected.

## Follow-on (the two-flow split — separate from 0b's keystone)

The consultation flow (PO→architect→design→planner) and trimming `team` to
BUILD→REVIEW→TEST→RETRO are **flow-seed YAML** work in `src/pathly_data/core/flows/`
(`_refresh_flows()` re-seeds on server restart; no SQL, no adapter build). Full verified
YAML for both is in the `phase0-recon` workflow output. Flag to confirm first: that the
FSM starts a `team` run at the **first listed state** (would become `BUILDING`) and nothing
hard-codes `STORMING` — check `fsm_ops.py:_load_flow` / `recover_state`.

## Build order
1. Step 1 (accept goal_id/executor) — verify with a POST + read-back.
2. Step 2 (plan.md Step 6 + propagation) — `goal_id` = real goal-message id (LOCKED, see above).
3. Then the two-flow split (consultation + trimmed team).

---

## ▶ Ready-to-run build prompt (corrected — hand this to the new session)

Reviewed by a 4-lens panel (architect/planner/PO/designer) and corrected vs. the original draft:
(1) `executor` removed from the task JSON — **goal-only**; (2) emit the *exact* canonical JSON incl.
`conv` (int); (3) scope-honest headline + explicit NON-GOALS; (4) negative-path + back-compat test
required; (5) explicit goal-first idempotency; (6) propagation covers `plan.md` **and** `planner.md`.
(The executor-semantics refinement in [GOALS-DAG-EXECUTORS.md](../GOALS-DAG-EXECUTORS.md) §3 does **not**
change this prompt — 0b only *persists* the `executor` string; single/loop/team behavior applies at the
Phase-1 dispatcher.)

```
You're on feat/comms-board-dag-serial. Build Phase 0b — the keystone that makes the planner emit a
machine-readable task DAG onto the comms board (the data substrate the P1 dispatcher and P2 UI will
later drive). Read PHASE-0b-planner-dag-wiring.md and GOALS-DAG-EXECUTORS.md first.

OUT OF SCOPE: no Run button, no executor selector, no goal/task rendering, no dispatcher — frontend is
Phase 2. The two-flow split (consultation + trimmed-team YAML in core/flows/) is a SEPARATE follow-on.
No schema migration (columns exist from 0a). No templates.

STEP 1 — write path (code, verify in isolation, do FIRST). Land both files atomically.
  File A — http_server/blueprints/comms.py (comms_post route, ~line 140): after the depends_on read,
    add goal_id = data.get("goal_id") and executor = data.get("executor"); after the depends_on
    validation, add type-guards returning 400 if present and not a string (comment: executor is any
    string — the {single,loop,team} enum is enforced downstream by the Phase-1 dispatcher); pass
    goal_id=…, executor=… into _post_message(...); add them to the docstring "Optional:" line.
  File B — db/queries/comms.py (post_message, ~line 18): add keyword params after artifact_type:
    goal_id: str | None = None, executor: str | None = None; add the two INSERT columns + placeholders
    + values. (None-defaults keep back-compat.)
  Verify: POST a type='task' with goal_id+executor AND a type='goal' with executor → GET both back →
    confirm persist. Then ADD tests/test_comms_goal_executor.py (mirror test_comms_dag.py): (1) round-trip
    non-null; (2) goal_id non-string → 400; (3) task with NO goal_id/executor → 200 + NULL columns
    (back-compat). Run: python -m pytest tests/test_comms_*.py -q.

STEP 2 — planner → DAG (skill). File: core/skills/planning/plan.md, Step 6 (~lines 266-306).
  BEFORE the phase loop, insert a goal-first block: extend the idempotency guard to skip if a type='goal'
    OR any type='task' already exists for this scope; else POST one goal {from:"planner", type:"goal",
    text:"Goal: <feature>", board:"feature", scope:"$FEATURE", executor:"single"} and capture its
    message_id as $GOAL_ID.
  Then per phase, in order, POST type='task' with the EXACT canonical JSON (record each returned
    message_id into a phase_N→id map for depends_on): keys feature, from, type, text, board, scope,
    stage:"BUILDING", conv (int — optional, never a string), depends_on, goal_id:"$GOAL_ID",
    artifact_path, artifact_type:"plan_artifact". executor is NOT on the task.
  Keep the fail-silent-on-connection-refused branch. Optional: add to core/agents/planning/planner.md:
    "Before returning, you MUST execute plan.md Step 6 to seed the comms-board task DAG."
  Propagate (mandatory, covers plan.md AND planner.md): pathly-setup claude --apply --repair ; python -m build.

DONE-STATE (manual check): GET /comms/tasks?feature=$FEATURE → one type='goal' + N type='task', all
  goal_id == the goal's message_id, depends_on edges acyclic (roots []), executor on the goal only.

KNOWN FOLLOW-UPS (flag, NOT 0b): get_ready_tasks is board+scope only (the P1 dispatcher must add a
  goal_id filter); the idempotency guard is goal-blind (partial-seed can't self-heal); executor is
  stored but unread until the P1 dispatcher. Next phase after 0b = the P1 dispatcher.
```
