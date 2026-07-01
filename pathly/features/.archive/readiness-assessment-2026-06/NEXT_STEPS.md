# Pathly — How to Proceed (verified-today plan)

> **Date:** 2026-06-28 (same day as, and a few hours after, [ASSESSMENT.md](ASSESSMENT.md))
> **Status:** companion to ASSESSMENT.md — re-sequences its roadmap against the **current**
> code, because its keystone bug (P0-1) was fixed between the assessment and this doc.
> **Method:** every status below was re-verified against master today — the FSM fix commit,
> a full `pytest` run (6 failed / 865 passed / 5 skipped), and a code audit of
> skills/agents/templates/adapters. Claims carry `file:line`. Trust this doc's status over the
> assessment's where they differ.

---

## 0. Bottom line — the keystone is gone; the job is now "make master green and demo one real run"

The assessment's entire verdict rested on **P0-1** (`next_state` contract → "the single defining
feature is broken"). **P0-1 is fixed** (commit `4fcf01d2`: `complete_stage` now emits a top-level
`next_state`; `fsm_ops.py:1033-1040`). So the scariest claim in the assessment is no longer true.

What replaces it is smaller and mechanical: **master is still red, but for snapshot/regression
reasons, not an architecture break.** Fix those, land the latent storage-path bug, make the 2
dead adapters honest, connect the flow builder, and demo one full run — that is the whole
"usable app" milestone. Everything else (fragments-P1, code-intel, parallelism) is deferrable
and gates nothing.

> **The one move that matters this week:** get master green, then demo one STORM→DONE run on
> claude+codex with Studio open. Stop planning new tracks until that runs.

---

## 1. Verified-today delta vs ASSESSMENT.md

| Assessment said | Verified today | Action |
|---|---|---|
| **P0-1** `next_state` broken — defining feature dead | ✅ **FIXED** (`fsm_ops.py:1033-1040`, commit `4fcf01d2`) | Commit the test (below); add supervisor-loop case |
| **P0-2** master red, 4 stale snapshots | 🔴 **STILL RED — 6 failures** (4 snapshots **+ 1 new summary regression + 1 dag-parallel**) | §2.1 |
| **P0-3** storage-path unbuilt | 🔴 **STILL TRUE** — `db_api.py:71` + **36** skill bodies hardcode `pathly/plans/` | §2.2 |
| **P1-1** 2/4 adapters headless | 🔴 **STILL TRUE** — `adapters.yaml:15,22` `headless: null` | §2.3 |
| **P1-2** runner inert without Studio | 🟠 **STILL TRUE** — `supervisor/terminal.py:262-266`; `runner/invoke.py` unused | Tier B |
| **P1-3** flow builder decoupled | 🟠 **STILL TRUE** — `FlowControlBar.tsx:41`, no Run in `FlowEditor` Toolbar, 5 hardcoded flows | §2.4 |
| **P1-4** no-op controls | 🟠 **STILL TRUE** — `FeatureCard.tsx:73-85` local-only; `commandCenterStore.ts:10` hardcoded `INITIAL_FEATURE` | §2.4 |
| **P2-1** `validate_composition` not at boot | 🟠 **STILL TRUE** — defined `compose.py:271`, no boot caller | §2.4 |
| **P2-4** SOLID drift | 🟠 **WORSE** — `comms.py`=1110 (was 937), `fsm_ops.py`=1040 (was 924); 17 files >400; `db/queries/comms.py` imports `runner.embeddings` | Tier B |

**New, not in the assessment:** `tests/test_comms_artifact_summary_writeback.py::
test_summary_writeback_persists_selection_when_given` **fails** — a regression in the P0 summary
feature the assessment praised as "banked." Triage before anything else (§2.1).

---

## 2. Tier A — the "usable app" milestone (do these, in order)

### 2.1 Get master GREEN  ← start here

The current 6 failures, with the right disposition for each:

- [ ] **Triage the new summary-writeback regression** —
  `test_comms_artifact_summary_writeback::test_summary_writeback_persists_selection_when_given`.
  This is in shipped P0 code, so it's either a real regression or a flaky write-order test.
  Decide which **before** touching snapshots — it may share a cause with the snapshot churn.
- [ ] **Regenerate the 4 golden snapshots** — `team/review`, `team/test`, `development/review`,
  `development/test` (`tests/snapshots/*.claude.md`). ⚠️ **Not mechanical:** the diff blesses the
  new "description AND summary" wording in `fragments/comms-post.md:49-51` that **no human has
  reviewed**. Eyeball the rendered diff and confirm intent, then regenerate.
- [ ] **Dispose of `test_dag_scheduler::test_diamond_dag_parallelism`** — it asserts true B/C
  parallelism that the serial-only executors don't deliver (P1-5, deferred). Mark it `xfail`
  with a reason pointing at the parallel-fleet plan, OR delete until parallelism is built. Don't
  leave a permanently-red test as "expected."
- [ ] **Commit `tests/test_runner_fsm_integration.py`** (currently untracked) and **extend it to
  the supervisor loop** (`supervisor/orchestrator.py:75,525`) — today it only drives the runner
  loop (`run_flow`). The fix is at the `fsm_ops` level so both benefit, but only one is guarded.

**Exit:** `PYTHONPATH=src python -m pytest tests/ -q` is green (or green + documented xfails).

### 2.2 Land storage-path-alignment (P0-3) — before any new-path team run

`db_api.py:71` and **36** skill bodies still glob the legacy `pathly/plans/*/`. Harmless **only**
because no `pathly/<topic>/`-root feature exists yet; the first full-team run on a new-path plan
silently splits artifacts across two roots. Replace the hardcoded literals with the FSM-resolved
storage-path / dual-scan / DB query already half-wired. **Land before exercising the new-path flow.**

### 2.3 Make the 2 dead adapters honest (P1-1)

`copilot` + `antigravity` are `headless: null` (`adapters.yaml:15,22`). Python `resolve_command`
**raises** (run dies opaque); Studio `cliEngine.ts` **silently falls back to the claude argv** —
the two builders disagree. Minimum bar for "usable": **validate `adapter_map` at run-start and
reject unsupported adapters up-front with a clear message in BOTH builders.** (Real templates or
ACP adoption is Tier B.) Don't let a user silently run the wrong CLI.

### 2.4 The usability batch (small, high first-impression value)

- [ ] **Connect the flow builder to the runner (P1-3):** add a flow-list endpoint + a **Run**
  action in `FlowEditor`/`FlowControlBar` that runs the *currently selected* flow, not the
  hardcoded `'team'` (`FlowControlBar.tsx:41`); ensure wizard-created flows land in a runnable
  DB-seed location. A headline surface is currently disconnected from execution.
- [ ] **Wire or remove the no-op controls (P1-4):** `FeatureCard` Unblock/Skip/Pause only mutate
  local Zustand (`FeatureCard.tsx:73-85` → `commsStore.setFeatureStatus`) — wire to `/runner/*`
  or remove. Drop the hardcoded `INITIAL_FEATURE='send-to-agent-diff'` (`commandCenterStore.ts:10`)
  so a fresh project opens to a valid board. These make a working app *look* broken.
- [ ] **Call `validate_composition` at FSM boot (P2-1):** one line in the server boot path so a bad
  manifest edit fails fast instead of at first compose.

### 2.5 Demo the milestone

Run **one full STORM→DONE pipeline on claude+codex with Studio open**, end to end. When that works
and is recorded, the app is "usable." That demo is the definition of done for Tier A.

---

## 3. Tier B — production hardening (after the demo, by demand)

- **Server-side spawn fallback (P1-2):** give the supervisor a `runner/invoke.py` path so a goal/DAG
  drains without the desktop app. Unlocks CI / unattended — today it's desktop-only.
- **Adopt ACP** instead of hand-built per-adapter argv — kills P1-1 permanently and is the
  assessment's strategic call.
- **Real DAG parallelism (P1-5):** dependency edges in decompose + wire `LaneIsolation`. Only when
  parallel demand is real; this re-enables the `xfail`'d test.
- **Telemetry:** inject `PATHLY_PROJECT_ROOT` (installer/Studio) + dedup `BILLING_UPDATE` vs
  self-reported `AGENT_DONE` cost (P2-2); add the first `stop_telemetry.py` test.
- **Windows:** use `killPtyTree()` on `before-quit` so engine children aren't orphaned (P2-3).
- **CI hygiene (P2-4):** lint the 400-line + no-upward-import rules; split `comms.py`/`fsm_ops.py`;
  add unit tests for the scheduler/argv builders; add a **Windows CI lane**.

---

## 4. Architecture status — skills / agents / templates / fragments

Audited today against the unified-cli-composition design. Verdict: **designed and ~half-built; the
gaps are exactly where the design says they are (no surprise drift).**

| Layer | State | Notes |
|---|---|---|
| **Agents** | ✅ clean | No premature `gitnexus_*`/code-intel sections in scout/explorer/quick. Good discipline. |
| **Templates** | ✅ complete | `summary/{gist,topic-map,detailed}.md`, plan set, pipeline-walkthrough all present. |
| **Fragments** | ⚠️ P0 only | `client-file-output`+`artifact-transform` exist; **`board-start-context`+`task-dag-post` do NOT** → the **goal-backed profile (half the orchestration model) is unbuilt.** |
| **Skills** | ⚠️ 25/45 converted | Pure transforms (summarize/analyze/split) are agnostic. Stage skills still carry FSM-stage orchestration (+ `development/build` has `/comms/tasks` I/O) in-body — **a known P3+ track per DESIGN.md, not new debt.** `team/architect`+`team/research` are the small P1e cleanup. |
| **Decomposer** | ⚠️ partial | `development/decompose.md` not built (P1b), but `_decompose_planner`'s prompt is **already plan-type-agnostic** — half the ORCHESTRATION_MODEL goal is met. |
| **Adapters** | ✅ in sync | claude/codex/copilot/antigravity `_meta/` match for sampled skills+agents. |

**Implication:** the standalone-transform half of the new architecture ships; the goal-backed/
`profiles:` half is paper. Per the assessment that half is **invisible internal cleanup — defer it.**
Do not let fragments-P1 block the demo.

---

## 5. Do NOT do now (reaffirming the assessment's cut-list)

- **CUT:** `differ`, `lsp-integration`, `gitnexus-integration (A)`, `md-diagram-conversion`,
  `studio-sidebar-redesign`, `codebase-architecture` (empty/errored stubs or commodity rebuilds).
- **DEFER:** code-intel `code-context-injection (B)` + `code-intel-proxy (C)` — build **only** B+C,
  **only** if a real code-navigation pain point appears; better to **consume** GitNexus/Serena as a
  fragment than build it. `parallel-fleet-1/2` + `comms-board P3` (parallelism designed 3×, 0% built)
  — consolidate and defer.
- **DEFER:** unified-cli-composition **P1+** (goal-backed profile, `blocks:`→`profiles:` rename,
  decompose skill, drain-dag conversion). Invisible; gates nothing user-facing.

> The assessment's §7 "design-without-build" pattern is the real lesson: stop forking new designs,
> finish the single lane, prove it runs.

---

## 6. Definition of done for "usable app"

1. `pytest` green (or green + documented xfails).
2. storage-path-alignment landed.
3. Unsupported adapters rejected with a clear message (not silently mis-run).
4. A built/selected flow runs from the UI; no-op controls wired or gone.
5. **One full STORM→DONE run on claude+codex with Studio open, recorded.**

When #5 is on tape, ship the MVP and move to Tier B by demand.
