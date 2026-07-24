# Unified Control Plane — SPEC

**Status:** design (P-1 backend-correctness fixes landing) · **Date:** 2026-07-24
· **Owner:** hamilton · **Scope:** feature

> One "Pipelines" control plane — like an Azure DevOps pipeline — that centralizes
> **all spawning**, **all logs/observability**, and **all board posting**, and lets a
> human select a goal / board / task / flow, spawn it, watch every log + board post
> live, and drive the runner controls, from a single surface.

This SPEC is the anchor for consolidating Pathly's scattered run controls. It is a
**consolidation, not a rewrite**: the hard substrate (one PTY spawn chokepoint, one
billing chokepoint, one run-identity map) already exists.

---

## 0. Why this feature exists — the four pillars, and where they fray

Pathly's core concept has four pillars:

1. **Control of flows** — single agents *and* flows-of-single-agents, driven by an FSM
   whose state lives in SQLite, controlled from the Electron app; spawning **headless**
   CLI agents (claude, codex, antigravity, …).
2. **Board context via fragments** — every prompt an agent receives is assembled through
   the un-editable fragment layer (board CRUD, context retrieval, progress logging,
   completion) + skills/prompts.
3. **Artifacts** — markdown today; images / pdf / text / video next phase.
4. **Context depth** — the human controls global / project / feature reach.

A four-agent audit (2026-07-24) found the **foundation is aligned and correct**, but the
divergences cluster around **one seam: the run loop is renderer-coupled and the run
lifecycle is split in two.** That same seam is what makes the *controls* feel scattered
and what makes "headless" only half-true. Fixing it fixes both. (Full findings: Appendix A.)

---

## 1. Root cause — what actually diverges

**Already unified (KEEP, do not touch):**

- One PTY spawn chokepoint — `supervisor/terminal.py::_run_stage_via_terminal` (`terminal.py:401`).
- One host gate — `studio/src/main/ipc/terminal.ts` dual-cap gate → `pty.spawn` → `spawn:state`.
- One billing chokepoint — `POST /runner/terminal/result` (`api_lifecycle.py:235`).
- One identity map — `run_history` (`{run_id, project_root, feature=slug, board_scope, …}`) +
  `agent_invocations` (cost/tokens, `run_id`-keyed).

**What diverges:**

1. **Two parallel lifecycle systems** (the root of the fragmentation):

   | Run kind | Lifecycle owner | Keyed by | Stop route |
   |---|---|---|---|
   | FSM `flow` / `team` / consultation | `_registry` RunnerState | **topic** | `/runner/abort` |
   | board `single` / `loop` / `task` / decompose | `board_lock` | **board+scope** | `/comms/run/stop`, `/comms/goals/stop`, `/comms/tasks/stop` |

   `/comms/goals/stop` (`goals.py:179`) already holds the resolver we need (try `board_lock`,
   fall back to `_registry`) — written inline and duplicated across three stop routes.
   Because of this split, **board runs have no pause/resume/advance/reroute at all** — only
   the single FSM `topic` run does (`FlowControlBar`).

2. **Six entry facades over the one chokepoint** — `start_run`, `start_board_run`,
   `start_goal_run`, `start_goal_decompose`, `runner_start`, `/comms/tasks/run`.

3. **Four SSE channels + one IPC, none keyed by `run_id`** — `/events/spawn` (firehose),
   `/events/runner?topic`, `/events/comms?scope`, `/events/stream?topic+root`, `spawn:state`.
   To watch one run you mentally join four differently-keyed streams. `run_id` — the one
   identity a run *is* — keys none of them.

4. **Run I/O is ephemeral.** The composed prompt is built and sent but never persisted
   per-run; stdout is parsed for cost then **discarded** (PTY tail buffer); the mid-phase
   board context injected into the prompt is not stored; `comms_messages` has **no `run_id`**.
   So "show me everything about run X" is literally unanswerable today.

5. **Start on the board, observe in a different panel** — `CommsPanel` buttons start runs;
   `Monitor` + `CliMonitorBar` observe them, with three different stores.

---

## 2. The Complete Run Record — the core data model

> This is the product-owner refinement that sharpens Agent 1's P0. A run is not just a
> status + a cost — it is a **durable, replayable transcript** keyed by `run_id`.

Every run, per stage, captures **all the relevant info in one record**:

| Field | Today | Target |
|---|---|---|
| Composed **prompt sent** (fragment-assembled `agent_text` + any `stage_override`) | built, not persisted | persisted per stage |
| **Mid-phase board context injected** (`retrieve_board_context` / `board_context_for`) | injected, not stored | persisted per stage |
| **stdin** fed to the CLI | transient | persisted |
| **stdout** received | parsed for cost, then discarded | persisted (durable log sink) |
| Structured **result** — cost, tokens, outcome, session_id | in `agent_invocations` (`run_id`-keyed) | keep |
| **Board posts** made during the run | in `comms_messages`, **not** `run_id`-keyed | += `run_id` column |
| **Artifacts** produced | `comms_artifacts` (board_scope + window) | joined by run window |

**Storage:**
- `run_history` — identity + lifecycle (**exists**).
- `agent_invocations` — cost/tokens (**exists**, `run_id`-keyed).
- `comms_messages` — **add `run_id` column** so board posts correlate to a run.
- **NEW durable run-log store** (`db/queries/run_log.py` + a `run_log` table): per-stage
  `{run_id, stage, prompt_sent, board_context_injected, stdin, stdout, ts}`. Written at the
  spawn chokepoint (`_run_stage_via_terminal` already has the composed prompt + board block
  in hand) and completed from the `/runner/terminal/result` stdout tail — **before** it is
  discarded.

This record is what the unified pane renders and — critically — what lets the pane
**rehydrate from the DB on a renderer reload** instead of orphaning (see §5, risk 5).

---

## 3. The four seams (each REUSES an existing chokepoint)

1. **`supervisor/dispatch.py`** — a `RunSpec` dataclass + `dispatch_run()` router over the
   existing `start_*` functions (a front door, not a reimplementation), plus
   `resolve_run(run_id)` / `control_run(run_id, action)` generalizing the `/comms/goals/stop`
   resolver by `run_id`. Layer-safe: imports only sibling supervisor modules.
2. **Read-model** — `db/queries/run_history.py::list_runs / get_run_detail` (JOIN cost +
   the run-log store) + a supervisor `overlay_live_status` that upgrades a persisted
   `running` row to the live status and attaches a per-kind `capabilities` set.
3. **Unified feed** — `sse.py::_broadcast_run_event` as a **4th sink** called from the three
   existing broadcast helpers (~3 lines, the proven `_SPAWN_EVENT_TYPES` mirror pattern) →
   `GET /events/runs` (`run_id`-filterable).
4. **Single board-posting path** — `blueprints/control/_lifecycle.make_board_posters`
   replacing the three duplicated poster closures in `runs.py` / `goals.py` / `tasks.py`, and
   **stamping `run_id`** into every board post.

New blueprint domain `http_server/blueprints/control/`:
`runs_read.py` (`GET /runs`, `GET /runs/<id>`), `runs_control.py` (`POST /runs`,
`POST /runs/<id>/<action>`), `run_streams.py` (`GET /events/runs`), `_lifecycle.py`.

Studio `components/Pipelines/` pane: RunList → RunDetail (Stages · Logs · Board · Artifacts ·
Cost) with inline `RunControls`, reusing `deriveFlowSteps` / `FlowStepper` / `RunCostBadge`.
`NewRunButton` subsumes the four board launchers; `RunControls` is **capability-gated**
(a loop/single run shows only Abort; a flow run shows the full six).

---

## 4. Phased plan

### P-1 — Backend correctness (precursor; landing now)
- **Fix #4 (done):** `parse_result` surfaces `is_error` / `subtype` / `api_error_status` so the
  failure guards (`scheduler._outcome_is_failure`, `/comms/tasks/run`) become reachable.
- **Fix #5 (done):** `orchestrator._loop` surfaces a stage's self-reported failure as a
  non-fatal `RUNNER_WARNING` (advancement unchanged — downstream REVIEW/TEST is the gate).
  *Open product decision:* whether to **halt** on self-reported failure for no-review rigors
  (nano/lite) instead of warn — flagged, not yet implemented.
- **CI gates (todo):** enforce layer-import direction (clean today → strict); enforce the
  400-line limit with a **grandfather allowlist** (18 current offenders, mirroring
  `mirror_reads_allowlist.txt`) so it blocks *new* violations only.

### P0 — Run record + read-model + read-only pane (pure-additive, zero behavior change)
- Add the `run_log` store + `comms_messages.run_id` column; write the composed prompt +
  injected board context at the spawn chokepoint and the stdout at result time.
- Add `run_history.list_runs / get_run_detail`, `dispatch.overlay_live_status`,
  `blueprints/control/runs_read.py`, Studio `runsStore` / `runsApi` / read-only `Pipelines` pane.
- **AC:** the pane lists every run kind with correct status + cost at parity with today's
  Monitor RECENT; a selected run shows its full transcript (prompt, injected context, stdout,
  board posts, artifacts, cost); the pane rehydrates from `GET /runs` on renderer reload.

### P1 — Unified event feed
- `sse.py::_broadcast_run_event` + `GET /events/runs`; `make_board_posters` stamps `run_id`;
  RunLogs + RunBoardPosts render live from one subscription.

### P2 — Unified dispatch facade + launcher
- `supervisor/dispatch.py` (`RunSpec` + `dispatch_run`), `POST /runs`, `NewRunButton`.
  Old board buttons still work.

### P3 — Unified control + surface merge + server-side loop
- `resolve_run` / `control_run`, `board_lock.find_by_run`, `POST /runs/<id>/<action>`,
  capability-gated `RunControls`; merge `Monitor`/`CliMonitorBar` into projections of
  `runsStore`; **move the run loop fully server-side** so a renderer reload no longer orphans
  a run (durability — the real #1 reliability gap).

### Parallel tracks (independent)
- **Pillar 4:** wire the project/global context-depth toggles (today cosmetic —
  `CommsPanel.tsx:205`, server hardcodes `comms_context.py:353`).
- **Pillar 3:** artifact type-model P0 — stop hardcoding `type="md"`
  (`artifact_reconcile.py:60,83`; `comms_artifacts.py:248`); return a clean error, not
  mojibake, for a non-md hydrate (`hydrate_helpers.py:111`).

---

## 5. KEEP / UNIFY / BUILD & risks

**KEEP:** `_run_stage_via_terminal`; the `terminal.ts` gate + `spawn:state`;
`/runner/terminal/result` + `invocation_projection`; `run_history`; `TerminalSpawnListener`;
`deriveFlowSteps` / `FlowStepper`; the five `start_*` functions.

**UNIFY:** 6 facades → `dispatch_run`; 4 stop routes → `control_run`; 4 SSE channels →
`/events/runs`; 3 board-poster closures → `make_board_posters`.

**BUILD:** `supervisor/dispatch.py`; `db/queries/run_log.py` + `run_history.list_runs/get_run_detail`;
`blueprints/control/`; `sse._broadcast_run_event`; `board_lock.find_by_run`; Studio `Pipelines/` pane.

**Top risks:** (1) the two-lock resolver correctness — mitigate by generalizing the existing
goals/stop logic keyed by `run_id`; (2) control granularity is *semantic* — capability-gate,
do not fake pause/advance for board runs; (3) board posts lack `run_id` until P1 threads it;
(4) `/events/runs` firehose scale — server-side `?run_id=` filter; (5) **reload resilience
becomes a strength** — DB-backed read-model rehydrates the pane where today's pure-SSE
`runnerStore` orphans; enforce "DB on mount, SSE overlay" as an invariant; (6) file-size
discipline — the read/control/stream split is along the 400-line + SRP seams.

---

## Appendix A — Alignment findings (four-agent audit, 2026-07-24)

**Pillar 1 (flows/FSM/headless):** FSM genuinely DB-authoritative; human-target correctly
escalates instead of stalling. Leaks: `interactive` defaults `True` at every base layer
(`api.py:23`, `api_lifecycle.py:121`, `runnerStore.ts:119`) — only newer call sites override;
legacy `runner/cli.py` still calls `input()`; the renderer is the sole spawn trigger with no
replay (reload orphans in-flight runs).

**Pillar 2 (fragments):** system sound, a few leaks — `development/design.md:12` and
`build.md:183` bake their own `curl record_phase` + `pathly-fsm-call complete-stage`;
`planning/storm.md` is 100% unconverted (absent from `composition.yaml`); `stage_override`
(`fsm_compose.py:352`) replaces the whole body verbatim with nothing enforcing
`comms-post`/`completion-report` survive.

**Pillar 3 (artifacts):** deliberately MD-only, clean generic schema underneath —
`type="md"` hardcoded (`artifact_reconcile.py:60,83`; `comms_artifacts.py:248`); `hydrate.py`
is `.md`-only; a PDF/PNG returns mojibake (`hydrate_helpers.py:111`); UI pdf/image icons are
cosmetic-only.

**Pillar 4 (context depth):** real end-to-end **only for feature scope**; project/global
toggles flip local React state with no API call (`CommsPanel.tsx:205`), server hardcodes their
depth (`comms_context.py:353`).

**Correctness bugs (backend audit; core chain otherwise correct, 105/105 tests pass):**
- Bug #4 — `parse_result` dropped `is_error`/`api_error_status`, making failure guards
  unreachable (`output.py:333` vs `scheduler.py:40`, `tasks.py:281`). **Fixed in P-1.**
- Bug #5 — `_loop` ignored the relayed `outcome` (`orchestrator.py:300`). **Surfaced in P-1.**

**Governance:** CI enforces neither the 400-line limit nor layer direction; 18 files exceed
400 lines (`terminal.py` 810). Half-built stale-run recovery is unwired
(`recover_stale_mirrors` / `mark_stale_runners` have no call site; `runner_state` is
write-only) — relevant scaffolding for the P3 server-side loop.
