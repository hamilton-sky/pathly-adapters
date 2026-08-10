# Unified Control Plane — DRAIN HANDOFF (implement the task-DAG)

**Purpose:** let a FRESH Claude Code session implement the 6-task DAG that was decomposed onto the
`unified-control-plane` board. Read this top-to-bottom, then implement **T1 → T6** in dependency
order, committing + pushing each, and marking each task done on the board.

**Starter prompt (paste into the new session):**
> Read `pathly/features/unified-control-plane/DRAIN_HANDOFF.md` top-to-bottom, then drain the DAG:
> implement T1–T6 in dependency order (T1/T3/T5 first, then T2/T4/T6). Commit + push each task to
> `feat/unified-control-plane`, mark each task done on the board, and use `/code/query` for
> impact/caller analysis before touching shared code. Use `./.venv/bin/python` for tests.

---

## Context

- Repo: `pathly-adapters`. Branch: **`feat/unified-control-plane`** (NEVER push to master; commit +
  push each task to this branch). Python: **`./.venv/bin/python`** (system python has no pytest).
- Feature: **unified-control-plane** — one "Pipelines" plane to *see + control every run* from one
  surface. Full design: [SPEC.md](SPEC.md). This DAG completes the goal's **P1 (live feed)**,
  **P2 (launcher)**, and **P3 (run_id control)**; the P3 **server-side loop** is intentionally OUT
  (a separate architectural effort — see the board `decision`).
- **Already shipped this arc (patterns to mirror — read these first):**
  - `POST /runs/<run_id>/stop` — `src/pathly_orchestrator/http_server/blueprints/control/runs_control.py`
    (the run_id→stop resolver: registry scan → `abort_run(topic)`, or `board_lock.find_by_holder` →
    board stop). **T1 and T5 extend this exact file.**
  - Read-model — `src/pathly_orchestrator/db/queries/run_history_read.py` (`list_runs`,
    `get_run_detail`, `_classify_kind`, `_is_parent`).
  - `RunDetailPage` — `studio/src/renderer/src/components/RunDetailPage/RunDetailPage.tsx` (the
    ■ Stop button + `.stop` CSS; `useRunDetail` polls `GET /runs/<id>` every 8s). **T2/T4 extend here.**

## The DAG (3 independent chains — board goal `0dd1d2bd-7e9d-4d39-945f-3d49b42aaf10`)

```
P3 control    T1 backend  ──▶  T2 frontend
P1 live feed  T3 backend  ──▶  T4 frontend
P2 launcher   T5 backend  ──▶  T6 frontend
```
Ready frontier = **T1, T3, T5** (no deps). Do those first (in any order), then T2/T4/T6.

Board task IDs (this machine's DB; mark them done as you finish — see "Board tracking"):
| Task | id | depends_on |
|---|---|---|
| T1 P3 control · backend  | `75203a83-ff39-4521-9e0e-92fb46dd3379` | — |
| T2 P3 control · frontend | `59c5d13b-04bd-4f97-823e-2f6553cae3ea` | T1 |
| T3 P1 feed · backend     | `4249a51f-637a-4427-b4bc-8b9050cd6dae` | — |
| T4 P1 feed · frontend    | `5f560607-96d2-4207-b4a9-601bfc86a000` | T3 |
| T5 P2 launcher · backend | `ac9ff84d-1b44-4f70-b8e1-a0461dbbf3a0` | — |
| T6 P2 launcher · frontend| `a5280187-de24-4c53-9762-595f3820cc3d` | T5 |

---

## Task specs (portable — the board is per-machine, this doc is the source of truth)

### T1 — P3 control · backend  *(extends `runs_control.py`)*
Add `POST /runs/<run_id>/<action>` for `action ∈ pause|resume|advance|reroute|retry|abort`, mirroring
the existing `/runs/<run_id>/stop` resolver in the same file:
- Resolve run_id → a registry `RunnerState` (FSM flow/team/consultation) and call the matching
  **topic-keyed** supervisor fn. **Reuse the exact functions the existing `/runner/*` control routes
  call** — see `blueprints/runner/api_control.py` (`/runner/pause|resume|advance|reroute|retry|abort`)
  → `supervisor/api.py` (`pause_run`, `resume_run`, `abort_run`, `reroute_run`, …). Don't reinvent;
  route by run_id → topic, then delegate.
- A board-lock run (single/loop, via `board_lock.find_by_holder`) supports **only `abort`** (the
  board-stop path already in the file); flow-only actions return `{"ok": false, "reason":
  "unsupported_for_kind"}`, 200.
- `reroute` needs a target — accept `{stage?, adapter?}` in the POST body and pass through.
- Keep `runs_control.py` **< 400 lines** (extract a helper module if needed).
- **Acceptance:** add cases to `tests/http_api/test_runs_control.py` (mirror the stop tests: a flow
  run pauses via the registry; a board run rejects flow-only actions; unknown run → not_active).
  `PYTHONPATH=src ./.venv/bin/python -m pytest tests/http_api/test_runs_control.py -q` green.

### T2 — P3 control · frontend  *(extends `RunDetailPage.tsx`)*
Add capability-gated **RunControls** to the RunDetail header: pause/resume/advance/reroute/retry/abort
buttons. Gate by run kind — a `flow` run shows the full set; `single`/`loop` show only **Stop**
(already present). Add `apiRunAction(runId, action, body?)` in `store/commsApi.ts` → `POST
/runs/<id>/<action>`. Mirror the existing ■ Stop button markup + `.stop` CSS variant; extract a
`RunControls/` subcomponent if the header grows past the file's size budget.
- **Acceptance:** `studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` + `(cd studio
  && node_modules/.bin/vitest run)` green.

### T3 — P1 live feed · backend  *(new `run_streams.py` + `sse.py`)*
- In `src/pathly_orchestrator/http_server/sse.py` add `_broadcast_run_event(run_id, payload)` as a
  **4th sink**, called from the existing `_broadcast_runner` / `_broadcast_comms` helpers (mirror the
  `_SPAWN_EVENT_TYPES` fan-out already in that file — ~3 lines each). Buffer/filter by `run_id`.
- Add `GET /events/runs?run_id=` in a **new** `blueprints/control/run_streams.py`, registered in
  `blueprints/control/__init__.py` (`all_blueprints`). **Mirror the existing runner SSE stream** —
  `blueprints/runner/streams.py` (the `/events/runner` generator + `_inc("pathly_sse_clients_active")`
  bookkeeping). Keep new files < 400 lines.
- **Acceptance:** `pytest tests/http_api -q` green + a smoke test that a posted run event reaches a
  `/events/runs?run_id=` subscriber.

### T4 — P1 live feed · frontend  *(extends `useRunDetail.ts`)*
Make RunDetail's **Logs + Board** tabs update live from `GET /events/runs?run_id=` (EventSource)
instead of the 8s poll in `RunDetailPage/hooks/useRunDetail.ts`. Keep the poll as a fallback if the
stream drops/errors (mirror the app's other SSE-with-poll-fallback hooks).
- **Acceptance:** renderer `tsc` + `vitest run` green.

### T5 — P2 launcher · backend  *(extends `runs_control.py`)*
Add `POST /runs` (create). Body = a thin **RunSpec** `{kind, board, scope, flow?, goal_id?, adapter?,
model?}`. Validate, then **dispatch to the matching EXISTING facade** — `supervisor.api.start_run`
(flow), `supervisor.board_run.start_board_run` (single/evaluator), `supervisor.goal_executor.
start_goal_run` (goal). **Route only — do NOT reimplement the runners.** Return `{ok, run_id}`.
- **Acceptance:** `pytest tests/http_api/test_runs_control.py -q` green (a create routes to the right
  facade; a bad kind → 400).

### T6 — P2 launcher · frontend  *(extends `Monitor/RunList/`)*
Add a **"New run"** button to the Pipeline Runs view (`studio/src/renderer/src/components/Monitor/
RunList/`) opening a small form (kind + board/scope + flow) → `apiCreateRun` (new, in `commsApi.ts`)
→ `POST /runs`. On success, refresh the run list.
- **Acceptance:** renderer `tsc` + `vitest run` green.

---

## Board tracking (best-effort, this machine)

As you finish each task, mark it done so the board reflects progress:
```bash
curl -s -X POST http://127.0.0.1:8765/comms/tasks/complete -H 'Content-Type: application/json' \
  -d '{"message_id":"<task id from the table>"}'
```
If the FSM server isn't running, skip it — the git commits are the authoritative record. (The board
is per-machine; this doc + the commits are the portable state.)

## Alternative: headless loop-executor drain
Instead of implementing directly, you *can* run the loop executor (spawns headless builder agents),
but it needs **Studio connected** to spawn PTYs (`GET /health` must show `sse_client`s > 0 —
the supervisor has NO headless PTY fallback). If so:
`POST /comms/goals/run {"goal_id":"0dd1d2bd-7e9d-4d39-945f-3d49b42aaf10","executor":"loop","project_root":"<repo>"}`.
Recommended: implement directly (this session IS a capable builder) — it's reliable and doesn't
depend on the Studio PTY-spawn path.

## Constraints (hard rules)
- **Code-intel first** for shared code: query `POST /code/query` (`op=impact|callers`, `target=<file
  path>`, `scope=(interactive)`) before editing — the backend is installed + `auto`. Verify against
  live code (advisory).
- **SOLID / 400-line limit** per file; **layer direction** `db → runner → supervisor → http_server`
  (supervisor/db imports **lazy inside** Flask route functions). New endpoints → the correct domain
  file; new control routes → `blueprints/control/`.
- **Test-as-you-go**; rerun `./.venv/bin/python scripts/gen_test_index.py` after adding a test.
- **Doc-sync in the same commit**: root `CLAUDE.md` (control endpoints), `src/pathly_orchestrator/
  CLAUDE.md` (blueprint map / run-identity), `studio/CLAUDE.md` (RunDetail / Pipeline).
- **Commit policy**: one commit per task, `feat/unified-control-plane` only, message ends with
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Verify each task's acceptance before
  committing.

## Verify (per task)
```bash
studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json    # renderer (T2/T4/T6)
studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.node.json   # main
(cd studio && node_modules/.bin/vitest run)                          # renderer tests
PYTHONPATH=src ./.venv/bin/python -m pytest tests/http_api -q        # backend (T1/T3/T5)
```
