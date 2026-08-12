# PO Notes — Unified Control Plane

_Last updated: 2026-07-24 · Stage 1 (PO) of interactive consultation · branch `feat/unified-control-plane`_

Scope framing for the architect (stage 2). The SPEC already carries the design + P-1…P3
phasing from the four-agent audit — this does **not** re-derive it. It pins the **MVP
boundary, scope cuts, per-phase acceptance shape, riskiest assumptions, and the edge cases
the build must handle.**

## Verified starting state (checked against live code, not assumed)
- On branch `feat/unified-control-plane`. P-1 Fix #4 **landed** — `runner/output.py::parse_result`
  now surfaces `is_error`/`subtype`/`api_error_status`.
- Everything this feature BUILDS is greenfield: `db/queries/run_log.py`, `blueprints/control/`,
  and `run_history.list_runs`/`get_run_detail` do **not** exist yet (`run_history.py` today has
  only `upsert_run`/`read_run_history`/`latest_project_root_for_feature`).
- `comms_messages` DDL (`migrations.py:270`) has **no `run_id` column** — confirmed. Adding it
  is a nullable additive migration.
- The four "already unified" chokepoints are real: `sse.py` has `_broadcast_comms`/`_broadcast_runner`/`_broadcast_spawn`
  (the 3 sinks P1 mirrors into a 4th); `terminal.py::_run_stage_via_terminal` is a genuine
  chokepoint (callers:3, callees:16 — already heavy); `board_lock` keys by `(board, scope)`.

## Who Is This For
The **human supervisor** driving headless multi-agent runs from Studio. The job-to-be-done is
one sentence: **"show me everything about run X, and drive it, from one surface."** Today that is
literally unanswerable — run I/O is ephemeral, observability is split across 4 SSE channels + 3
stores, and board runs have no controls at all. Not an end-user feature; a control-plane /
operator feature. This is dogfooding — Pathly supervising Pathly.

## Definition of Success / MVP boundary
**MVP = P0 only: the durable Complete Run Record + a read-only Pipelines pane.** It is the
keystone — every later phase (live feed, launcher, control, reload-resilience) depends on the
durable per-run record existing first. It is pure-additive (zero behavior change) so it can ship
without risking the working substrate.

**Success test for the MVP:** a supervisor selects any finished run and sees its full transcript
(prompt sent, board context injected, stdout, board posts, artifacts, cost) reconstructed **from
the DB** — with status + cost at **parity with today's Monitor RECENT** (same numbers), and the
pane **repopulates after a renderer reload** instead of orphaning to a blank.

Ship order after MVP: **P1 (live feed)** next — a read-only pane that needs manual refresh is a
weak demo, and P1 is the low-risk 3-line mirror pattern. **P2 (launcher)** and **P3 (control +
surface merge + server-side loop)** are the unification payoff but carry the real risk; defer
until P0+P1 are proven.

## Scope Cuts — explicitly NOT in the MVP
- **P2 launcher** (`NewRunButton`, `dispatch_run`, `POST /runs`) — deferred.
- **P3 control** (`RunControls`, `control_run`/`resolve_run`, surface merge of Monitor/CliMonitorBar,
  **moving the run loop server-side**) — deferred. Note: the server-side loop is the *actual* #1
  reliability fix (reload orphans in-flight runs); MVP does **not** claim to fix it — see risks.
- **Pillar 3 artifact type-model** (stop hardcoding `type="md"`, non-md hydrate) — parallel track,
  out of the control-plane critical path. MVP only needs the pane to **not break** on a non-md
  artifact.
- **Pillar 4 context-depth toggles** — independent parallel track.
- **P-1 "halt vs warn on self-reported failure for nano/lite"** — orthogonal runner-semantics
  decision; leave flagged, decide separately (see open questions).
- **No rewrite of the substrate.** This is consolidation over the top. Any task that *modifies*
  `_run_stage_via_terminal`'s spawn/billing logic (vs *adding* a best-effort run-log write beside
  it) is out of scope.

## Acceptance Shape — per phase
**P0 (MVP):**
1. Pipelines pane lists **every run kind** (flow/team/consultation/single/loop/task/decompose) with
   status + cost **at parity with Monitor RECENT** (identical figures).
2. Selecting a run shows Stages · Logs · Board · Artifacts · Cost, all from the DB.
3. A run with **zero board posts** → empty Board tab (empty state), never error/spinner.
4. A **non-md artifact** → listed with its type + path; **no inline hydrate attempt, no mojibake**.
5. **Renderer reload** → pane repopulates from `GET /runs` (DB on mount), no orphan blank.
6. A **run-log write failure never fails the run** (best-effort invariant — telemetry never blocks).
7. **Zero behavior change**: Monitor / CommsPanel / FlowControlBar untouched; existing tests
   (105/105) still green.

**P1:** new board posts carry `run_id`; Logs + Board tabs update **live** via `GET /events/runs`
with no manual refresh; under two concurrent same-board-tier runs each post attributes to the
**correct** `run_id` (exact, not window-approximate).

**P2:** `NewRunButton` launches all run kinds via `POST /runs`; the old board buttons still work
byte-identically.

**P3:** capability-gated `RunControls` (loop/single → Abort only; flow → full six); a renderer
reload **no longer orphans an in-flight run** (it continues server-side); Monitor / CliMonitorBar
become projections of `runsStore` (no third store).

## Riskiest Assumptions (de-risk these before building)
1. **"P0 is zero behavior change."** The new run-log write sits at the hot spawn chokepoint
   (`_run_stage_via_terminal`, already 810 lines). It is only truly zero-impact if the write is
   **best-effort and cannot raise into the spawn path** (ideally deferred/async). This single
   constraint is what makes the "pure-additive" claim hold.
2. **"Durable stdout = complete transcript."** False. The stdout available at
   `/runner/terminal/result` is the **rolling ~500-chunk PTY tail** — the same buffer whose
   truncation forced the `parse_result` regex-recovery saga. The run-log persists the
   best-available tail, **not** a guaranteed-complete log, unless the capture point changes.
   Don't promise a complete stdout transcript.
3. **`comms_messages.run_id` is nullable and un-backfilled.** Legacy posts, human posts, and any
   `/comms/post` not routed through a poster closure legitimately have NULL `run_id`. The
   RunDetail Board join must be **run_id-when-present, time-window-fallback-when-NULL** — the
   window join is **approximate under concurrent same-board runs** (acceptable for read-only P0;
   must be exact once P1 threads the column).
4. **"6 facades → dispatch_run" wraps, not rewrites.** The 5 existing `start_*` functions must
   remain the callees. Risk only materializes in P2/P3 — out of MVP.

## Edge Cases the Build MUST Handle
- **Reload mid-run:** the pane rehydrates from the DB and shows a still-running run as `running`
  with its transcript-so-far; live updates resume via SSE overlay (P1). But the run's
  **continuation** is renderer-driven until P3 — so "reload resilience" in P0 means *the pane
  survives*, **not** *the run survives*. State this boundary in the AC precisely; do not
  over-promise.
- **Concurrent runs on one board:** same `(board, scope)` is serialized by `board_lock`, but two
  goals under one feature board (same tier, different scope) and an FSM-topic run vs a board run
  (separate lock systems) **can be live at once**. `run_id` disambiguates each record; the
  window-join board-post fallback can cross-attribute overlapping posts until P1 — flag it.
- **Run with zero board posts:** the run-log + `run_history` rows are keyed by `run_id` **at
  spawn**, independent of any board activity — so a silent run still gets a full record and a
  RECENT entry. (Mirrors the existing telemetry lesson: a run that emits no `AGENT_DONE` vanishes
  from billing; the record must not depend on the agent posting anything.)
- **Non-md artifact:** the pane **lists** it (name/type/path) and offers md-only inline preview;
  anything else gets "preview unavailable for <type>" or open-externally — **never** a raw
  hydrate that returns mojibake (`hydrate_helpers.py:111`).
- **Renderer-less / headless observation:** the record is DB-authoritative, so a run's transcript
  is fully reconstructable with **no renderer ever attached** — the pane is a viewer, not the
  source. This is the invariant that makes "headless" finally true.

## Open Questions (non-blocking — fallbacks stated, do not block on these)
1. **Run-log storage growth / stdout cap.** Persisting full per-stage stdout for every run grows
   unbounded. *Fallback assumption:* cap persisted stdout to a bounded size (e.g. head+tail with a
   truncation marker) and treat the run-log as a debug/display sink, not an authority — billing
   already lives in `agent_invocations`. Architect to confirm the cap + retention.
2. **Concurrent same-board board-post attribution (pre-P1).** *Fallback:* time-window join,
   accept approximate cross-attribution for read-only P0; make exact via the `run_id` column in P1.
3. **CI gates sequencing (P-1 todo).** The 400-line grandfather allowlist + layer-import gate are
   hygiene, not user-facing. *Fallback:* land them **with** the `blueprints/control/` split (that
   is when new files are added along the 400-line seams and most benefit from the guard), not as a
   gate on MVP delivery.
4. **P-1 halt-vs-warn for nano/lite self-reported failure.** Out of this feature's scope.
   *Fallback:* keep the current warn-and-advance behavior; decide separately.
