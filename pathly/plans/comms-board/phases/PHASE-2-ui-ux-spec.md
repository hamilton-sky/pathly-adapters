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

> **Location truth (2026-06-17):** the board content (search · message list · compose) lives in
> `HQ/CommsPanel/CommsPanel.tsx` but is **rendered by the Command Center** — `CommandCenter/BoardSection/
> BoardSection.tsx` does `<CommsPanel scope=… />`. The `HQ/` folder name is a leftover; there is no separate
> live "HQ" view. **Planned cleanup (own step, a rename refactor like SkillNotebook→MarkdownNotebook):
> relocate `HQ/CommsPanel/` → `CommandCenter/Board/`.** All NEW goal/task/view components in this spec land
> in that board module (paths below say `Board/…`; until the relocation they physically sit in `HQ/CommsPanel/`).

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

`executor` is a **GOAL-level** property — stored on the `type='goal'` message (planner seeds it as
`single`; user-overridable) for **all three** modes. **The goal header owns the executor choice** — this
is the single place a user "ties an executor to a goal." **Run on the GOAL** runs its whole DAG via its
executor (see [GOALS-DAG-EXECUTORS.md](../GOALS-DAG-EXECUTORS.md) §3 for the refined semantics):

| Executor | Owns the frontier | What runs |
|---|---|---|
| **single** | the **agent** (self-loop) | ONE agent runs the whole goal in one context; after each task it calls the board HTTP for the next ready task and continues until the DAG drains |
| **loop** | the **supervisor** | a **fresh** agent per ready task (or batch); supervisor respawns the next — new context each task (the P2 frontier loop; `k>1` fan-out at P3) |
| **team** | the **FSM flow** | trimmed builder → reviewer → tester on the goal |

The per-task **Run** button (run one task with one ad-hoc agent) is a **separate affordance** — it is NOT
the `single` executor and isn't stored. Show it on a TaskCard regardless of the goal's executor (it's an
escape hatch to nudge a single ready task by hand).

---

## 3. Screens (ASCII, grounded in the real components)

### Screen 0 — board becomes a 3-VIEW surface (the view switcher)
The board no longer mixes goals/tasks into the message thread. A **full-width search** keeps its row;
**underneath it** a new **view-switcher** row toggles the board's content between **Messages · Goals & Tasks
· Artifacts**. (Chosen layout: full-width search + a dedicated toggle row — degrades better than a 50/50
split at the ≤200px panel widths the Command Center allows. Segmented control sits LEFT in the standard
Studio toolbar grammar; the RIGHT slot is an action area, empty now, for per-view actions like "+ New goal".)

```
┌─ PROJECT BOARD : pathly-adapters ───────────────────── [x] ┐  BoardSection header (unchanged)
│  🔍 Search this board…………………………………………………………… │  SearchBar — FULL width
│  ┌─────────────────────────────────────────────────────┐  │
│  │ [≡ Messages] [◧ Goals & Tasks] [▣ Artifacts]    (+…) │  │  BoardViewToggle (NEW) — segmented LEFT,
│  └─────────────────────────────────────────────────────┘  │  action slot RIGHT
│   …content of the selected view (Screen 1 / thread / artifacts)… │
│  Reads:[✓Project][✓Global]   [⚙Agent]   [compose…][DECISION▾][➤] │  foot — unchanged
└────────────────────────────────────────────────────────────┘
```
- **Messages** = today's `CommsMsgList`, but goals/tasks are FILTERED OUT (they live in their own view).
- **Goals & Tasks** = Screen 1 below (goal groups + DAG + executor + Run). **All goal/executor controls live here.**
- **Artifacts** = `type='artifact'` messages as a filtered card list (reuses the existing artifact card).
- View state is local to `CommsPanel` (`boardView: 'messages'|'goals'|'artifacts'`, default `'messages'`).

### Screen 1 — the "Goals & Tasks" view (goal groupings + task DAG)
Goals are collapsible group headers; their tasks nest beneath in `depends_on` topological order. This is a
view, NOT the message thread — only goals + tasks render here.

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

> Paths shown as `Board/…` = the relocated board module (today `HQ/CommsPanel/…` until the rename lands).

| File | Change | What |
|---|---|---|
| `CommandCenter/types.ts` `MessageType` | MODIFY | add `'goal'` (`'task'` already present) |
| `CommandCenter/types.ts` `Message` | MODIFY | add `goalId?`, `executor?:'single'\|'loop'\|'team'`, `taskStatus?:'pending'\|'in_progress'\|'done'\|'blocked'\|'failed'`, `dependsOn?:string[]` |
| `commsApi.ts` mapper | MODIFY | map the new (already `SELECT *`-returned) columns onto `Message` |
| `Board/CommsPanel.tsx` | MODIFY | add `boardView` state (`messages\|goals\|artifacts`, default `messages`); render the `BoardViewToggle` under the full-width `SearchBar`; switch content on `boardView` |
| `Board/BoardViewToggle/BoardViewToggle.tsx` | **NEW** | segmented Messages/Goals&Tasks/Artifacts (LEFT) + a right action slot; `data-*` variant pattern |
| `Board/CommsMsgList` | MODIFY | **Messages view: filter OUT `type='goal'`/`'task'`** (they render only in the Goals view) |
| `Board/GoalsView/GoalsView.tsx` | **NEW** | the Goals&Tasks view: list `GoalGroup`s for the scope (group tasks under goals by `goalId`) |
| `Board/GoalsView/GoalGroup.tsx` | **NEW** | header + topo-ordered TaskCard list |
| `Board/GoalsView/GoalGroupHeader.tsx` | **NEW** | executor segmented + Engine select + Run/Stop + rollup chip |
| `Board/GoalsView/TaskCard.tsx` | **NEW** | status dot + `depends_on` badges + artifact link + per-task ad-hoc Run |
| `Board/ArtifactsView/ArtifactsView.tsx` | **NEW** | filtered `type='artifact'` card list (reuse existing artifact card) |
| `store/commsStore.ts` | MODIFY | `goalRunState: Record<goalId,…>`; `runGoal(goalId,executor,engine,boardKey)`; `stopGoal(goalId)` — mirror `boardRunState`/`runSingleAgent`/`stopBoard` |
| `MessageTypeBadge.tsx` | MODIFY | render `'goal'` (accent) + `'task'` (muted) |
| `CommandCenter/FeatureCard/FeatureCard.tsx` | **REDESIGN** | strip the team-flow run controls (Play/Pause/Status). Becomes a nav item: name + **goal count** + `[open ▸]`. Execution moved to the board's Goals&Tasks view, per-goal. (Keep Archive + Set-main.) |
| `Board/SingleAgentButton.tsx` | **NO CHANGE** | the board-footer ad-hoc agent run stays |

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
P2-0  (cleanup, independent) relocate HQ/CommsPanel → CommandCenter/Board (rename refactor). Do early or anytime.
P2-A  types.ts + commsApi mapper (the already-returned columns).                                                      [dep 0b-1]
P2-T  BoardViewToggle + CommsPanel boardView state; Messages view filters out goal/task; Artifacts view.             [indep]
P2-B  read-only Goals&Tasks view: GoalsView/GoalGroup/Header/TaskCard, status dots, depends_on badges, live SSE.   [dep P2-A,P2-T]
P2-S  FeatureCard redesign — strip run controls; name + goal count + open.                                            [dep P2-A]
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
