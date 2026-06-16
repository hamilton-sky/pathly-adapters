# Phase 2 — UI/UX impact spec (Goals · Task-DAG · Executors on the board)

**Branch:** `feat/comms-board-dag-serial`
**Model:** [../GOALS-DAG-EXECUTORS.md](../GOALS-DAG-EXECUTORS.md) · **0b wiring:** [PHASE-0b-planner-dag-wiring.md](PHASE-0b-planner-dag-wiring.md)
**Status:** spec (not built). Produced by the 4-lens panel (architect · planner · PO · designer), 2026-06-17.

> **What this answers:** how the Board→Goals→Task-DAG→executors model changes the *current*
> Studio Command Center — what components we need, **how a user ties an executor to a goal/task**,
> and **how a user controls the system**. 0b/Phase-1 are backend; **this is the frontend phase.**

---

## 0. Where the UI work sits (and what must precede it)

```
0a schema ✅  →  0b planner emits DAG (backend+skill)  →  1 dispatcher (backend)  →  2 UI (this doc)  →  3 parallel
                 │ writes goal_id/executor/depends_on    │ routes a Run to its         │ renders + controls
                 │ NOTHING renders it yet                │ executor (single/loop/team) │ goals/DAG/executors
```

**Hard gate:** after 0b the columns are *written* but nothing *reads* them into the UI.
`GET /comms` already uses `SELECT *`, so the Python read API needs **no change** — the only
read-side gap is the **TypeScript `Message` interface** (it has none of these fields). The **Run**
action additionally needs the **Phase-1 dispatcher endpoint**. So Phase 2 splits cleanly:

- **P2 read-only (needs only 0b-1):** render goals/tasks/DAG/status. Ships independently of Phase 1.
- **P2 control (needs Phase 1):** the Run button → dispatcher. Disabled until Phase 1 lands.

---

## 1. Verified component map (the real canvas)

| Real file (verified) | Role today |
|---|---|
| `HQ/CommsPanel/CommsMsgCard.tsx` | renders a board message (Avatar + `MessageTypeBadge` + actions; body via `CardBody`) |
| `HQ/CommsPanel/CardBody.tsx` | switches on `m.type`: artifact / question / warning / **default→markdown**. `goal`/`task` hit the default branch today — **safe, no crash** |
| `CommandCenter/types.ts` | `Message` has **no** `goalId/executor/taskStatus/dependsOn`. `MessageType` has `'task'` but **not** `'goal'` |
| `store/commsStore.ts` | already has `boardRunState`, `runSingleAgent()`, `stopBoard()` |
| `HQ/CommsPanel/SingleAgentButton/` | already ships Engine dropdown (Claude/Codex), agent/skill/system-prompt, Headless/Interactive, progress cadence, Stop — **the goal header reuses this exact pattern** |
| backend: `/comms/tasks/{claim,complete,fail}` + `get_ready_tasks` + `/events/comms` SSE | task lifecycle + live events **already exist** — the dispatcher only adds *routing*, not state transitions |

---

## 2. What we tie: executor → goal / task

- **`executor` is a GOAL-level property** — stored on the `type='goal'` message (planner seeds it as
  `single`; user-overridable). **The goal header owns the executor choice.** This is the single place
  a user "ties an executor to a goal."
- **Run on the GOAL** runs the goal's whole DAG via its executor: `loop` = one agent chews ready-task-
  at-a-time; `team` = the trimmed BUILD→REVIEW→TEST→RETRO flow on the goal.
- **Run on a TASK** is the ad-hoc `single` path — nothing stored — reusing today's `runSingleAgent`
  aimed at one task. Shown **only when the goal's executor is `single`**; for `loop`/`team` the
  goal-level Run owns execution.

---

## 3. Screens (ASCII, grounded in the real components)

### Screen 1 — Board with goals as groupings (in `CommsMsgList`)
Goals become collapsible group headers; their tasks nest beneath in `depends_on` topological order.
All other message types stay in the flat thread, unchanged.

```
┌─ Feature Board: comms-board ─────────────────────────────────┐
│  [search……]                                                  │
│                                                              │
│  ▼ GOAL  "wire planner DAG"   [single|loop|team]  [▶ Run][⏹] │  ← GoalGroupHeader (NEW)
│        2/4 done · 1 ready                                    │
│     ├─ ✓ T1  accept goal_id/executor          done          │  ← TaskCard (NEW)
│     ├─ ⟳ T2  planner Step 6                    in_progress   │
│     ├─ ○ T3  propagate adapters   pending · waiting on T2    │
│     └─ ✕ T4  two-flow split       blocked · dep T2 failed    │
│                                                              │
│  [nudge / decision / status / artifact cards — unchanged]    │
│                                                              │
│  ▶ GOAL  "fix flaky tests"    [single|loop|team]  [▶ Run][⏹] │
│        0/2 · idle                                            │
│                                                              │
│  [footer: Reads row + SingleAgentButton + CommsInput — kept] │
└──────────────────────────────────────────────────────────────┘
 ✓ done   ⟳ in_progress   ○ pending   ✕ failed/blocked
```

### Screen 2 — GoalGroupHeader (zoom). NEW: `HQ/CommsPanel/GoalGroup/GoalGroupHeader.tsx`
Reuses SingleAgentButton's Engine select + `boardRunState`/stop pattern.

```
┌──────────────────────────────────────────────────────────┐
│ [◉ loop]  Goal · planner · 3m ago                        │
│ "wire planner DAG"                                       │
│                                                          │
│ Executor [ single ▾ ]    Engine [ Claude ▾ ]            │  executor = segmented (single|loop|team),
│                                                          │  defaults to message.executor
│ [▶ Run goal]  [⏹]      4 tasks · 2 done · 1 ready        │
└──────────────────────────────────────────────────────────┘
```
- Local state: `selectedExecutor` (default `message.executor`), `selectedEngine` (default `claude`).
- Changing the executor PATCHes the goal message's `executor` column (new `/comms/goal/executor`
  route — the P1/P2 boundary). **This is the one place a user ties an executor to a goal.**
- Run disabled while `goalRunState[goalId]==='running'`. Run calls the **Phase-1 dispatcher**
  (does not exist until Phase 1 → button is read-only/disabled until then).

### Screen 3 — TaskCard (zoom). NEW: `HQ/CommsPanel/GoalGroup/TaskCard.tsx`

```
┌──────────────────────────────────────────────────────────┐
│ [● ready]  Task · planner                                │
│ "Phase 2: planner Step 6 — emit task graph"             │
│ Artifact: IMPLEMENTATION_PLAN.md  [open]                │
│ Depends on: T1 ✓                                        │
│ [▶ Run task]   (shown only when goal executor = single) │
└──────────────────────────────────────────────────────────┘
```
- Status dot via the codebase's `data-*` variant pattern: `<span data-status={m.taskStatus} />`
  (studio CLAUDE.md: "3+ states → `data-*`").
- `depends_on` badges: green = dep done, red = dep failed/blocked, gray = dep pending.
- Artifact "open" reuses the existing `artifactPath → editor` plumbing on `CommsMsgCard`.

### Screen 4 — Observing a live run (the board *is* the observer — no new panel)
GoalGroupHeader flips to a progress view; task dots update live via the **existing** `/events/comms`
SSE (`task_unblocked`/`task_failed`/`task_blocked` already broadcast by `/comms/tasks/complete` + `/fail`).

```
┌──────────────────────────────────────────────────────────┐
│ [⚡ running]  Goal · loop · claude            [⏹ Stop]   │
│ <progress value=2 max=4>  2 / 4 tasks done              │
│ ├─ ✓ T1 done   ├─ ⟳ T2 in_progress ◄ agent here         │
│ ├─ ○ T3 pending  └─ ○ T4 pending                         │
└──────────────────────────────────────────────────────────┘
```
- **Headless loop:** SSE-driven status dots. **Interactive:** the existing terminal tab opens
  (today's SingleAgentButton interactive path); header shows a terminal-tab icon instead of the bar.
- **Intervene (unhappy path):** reuse existing warning-resolve actions; add only **Pause goal**
  (stops the dispatcher loop) and **Re-run task** (resets failed/blocked → pending). No control panel.

---

## 4. Component change map

| File | Change | What |
|---|---|---|
| `CommandCenter/types.ts` `MessageType` | MODIFY | add `'goal'` (`'task'` already present) |
| `CommandCenter/types.ts` `Message` | MODIFY | add `goalId?`, `executor?:'single'\|'loop'\|'team'`, `taskStatus?:'pending'\|'in_progress'\|'done'\|'blocked'\|'failed'`, `dependsOn?:string[]` |
| `commsApi.ts` mapper | MODIFY | map the new (already `SELECT *`-returned) columns onto `Message` |
| `HQ/CommsPanel/CommsMsgList` | MODIFY | group `type='task'` under parent `type='goal'` (`goalId`); flat for the rest |
| `HQ/CommsPanel/CardBody.tsx` | MINOR | defensive `goal`/`task` branches (handled by GoalGroup; prevents double-render) |
| `HQ/CommsPanel/GoalGroup/GoalGroupHeader.tsx` | **NEW** | executor segmented + Engine select + Run/Stop + rollup chip |
| `HQ/CommsPanel/GoalGroup/TaskCard.tsx` | **NEW** | status dot + `depends_on` badges + artifact link + per-task Run (single only) |
| `HQ/CommsPanel/GoalGroup/GoalGroup.tsx` | **NEW** | header + topo-ordered TaskCard list |
| `store/commsStore.ts` | MODIFY | `goalRunState: Record<goalId,…>`; `runGoal(goalId,executor,engine,boardKey)`; `stopGoal(goalId)` — mirror `boardRunState`/`runSingleAgent`/`stopBoard` |
| `MessageTypeBadge.tsx` | MODIFY | render `'goal'` (accent) + `'task'` (muted) |
| `SingleAgentButton.tsx` | **NO CHANGE** | continues to serve ad-hoc single-task runs |

**Accessibility:** status dots never colour-only (pair `aria-label="Task status: ready"`); GoalGroupHeader
`role="region"` + label; progress via `<progress>` (no inline style); every button `type="button"`;
executor/Run controls ≥44px.

---

## 5. Backend contract Phase 2 needs (mostly already present)

- **Read:** `goal_id/executor/depends_on/task_status` already surface via `SELECT *` — only the **TS mapper** needs them.
- **Goal grouping:** optional — the UI can group client-side from the existing `GET /comms` response
  (goal + task rows arrive in one scope). A `GET /comms/goals` convenience route is a nicety, not a blocker.
- **Dispatch endpoint (the true Phase-1 gate):** read `goal.executor` → route `single`/`loop`/`team` →
  reuse the existing `claim`/`complete`/`fail` task routes. The Run button is read-only-disabled until this lands.
- **Live:** `/events/comms` SSE already emits `task_unblocked`/`task_failed`/`task_blocked` — the DAG repaints without polling.

---

## 6. Full-arc task breakdown (0b → P1 → P2), dependency-ordered

```
0b-1  write path: comms.py route (extract+guard+pass goal_id/executor) + post_message (params+INSERT). Land atomically.
0b-2  tests: new tests/test_comms_goal_executor.py — round-trip + non-string→400 + no-fields→200+NULL (back-compat).   [dep 0b-1]
0b-3  plan.md Step 6: goal-first POST (guarded) → per-phase task POST (goal_id/depends_on/conv, NO executor).         [dep 0b-1]
        tail: pathly-setup claude --apply --repair && python -m build (mandatory)
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
P1-A  dispatcher: read goal.executor → route single/loop/team; ADD goal_id filter to the ready-task fetch.            [dep 0b-1]
P1-B  serial one-at-a-time gate.                                                                                       [dep P1-A]
P1-C  (carry-fix) goal-aware idempotency + partial-seed reseed in plan.md guard.                                      [dep 0b-3]
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
P2-A  types.ts + commsApi mapper (the already-returned columns).                                                      [dep 0b-1]
P2-B  read-only render: GoalGroup/Header/TaskCard, grouping, status dots, depends_on badges, live SSE.                [dep P2-A]
P2-C  executor selector + Engine on goal header; PATCH /comms/goal/executor.                                          [dep P2-B]
P2-D  Run Goal + Run task → commsStore.runGoal/stopGoal → P1 dispatcher.                                   [dep P1-A AND P2-C]
```

**Parallelism:** after **0b-1**, `P1-A` and `P2-A/P2-B` proceed **concurrently** (read-only UI needs no dispatcher).
Only `P2-D` joins the two tracks. Phase 3 flips `k>1` by lane (across-goal first).

---

## 7. Open questions (decide before/at build)

1. **executor placement — CONFIRM goal-only** (the one blocking decision; the candidate prompt + spec line 62
   contradicted the locked design — now corrected). Tasks carry no `executor`.
2. **Goal text** — is `"Goal: <feature>"` enough for 0b, or synthesize a one-line statement from USER_STORIES?
   (0b can ship the trivial form; richer text is a cheap later refinement.)
3. **`conv` on tasks** — include the phase's conversation int, or omit (NULL)? Both back-compat-safe.
4. **`planner.md` reinforcement line** — include the "you MUST run Step 6" imperative now, or rely on Step 6's own text?
5. **Multi-goal frontier** — accept that `get_ready_tasks` is board+scope only (safe for one-goal-per-scope);
   the `goal_id` filter is a **Phase-1 dispatcher** concern.
6. **Two-flow split precondition** (follow-on, not 0b) — verify the FSM starts a trimmed `team` run at the first
   listed state and nothing hard-codes `STORMING` in `fsm_ops.py` `_load_flow`/`recover_state`.

---

## Appendix — revised Phase-0b implementation prompt (use this, not the original)

> Corrections vs. the original: (1) `executor` removed from the task JSON — **goal-only**; (2) emit the *exact*
> canonical JSON incl. `conv` (int); (3) scope-honest headline + explicit NON-GOALS; (4) negative-path + back-compat
> test required; (5) explicit goal-first idempotency; (6) propagation covers `plan.md` **and** `planner.md`.

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
