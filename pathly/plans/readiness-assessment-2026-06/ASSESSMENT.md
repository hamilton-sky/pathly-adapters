# Pathly — Readiness Assessment, Issues & Solutions

> **Date:** 2026-06-28
> **Scope:** Full assessment of Pathly after the fragments work and the B-core→C→A (code-intel) track — readiness, competitive landscape, and what is needed vs. cuttable for a "full usable app."
> **Method:** 32-agent multi-agent workflow — 11 codebase-reality readers (verified against source, not docs), 8 plan-inventory readers, 9 competitive web-research agents, and 4 adversarial synthesis agents (readiness verdict + cut-list + positioning + a critic that re-checked the verdict against raw findings). Every maturity claim below is backed by `file:line` evidence the agents cited or empirically reproduced.

---

## 0. Bottom line

**Readiness: `usable-with-significant-gaps` — not yet a full usable app.**

The architecture is real, substantial, and well-tested. But **the single defining feature — the automated multi-stage headless run — is broken on master today**: every Studio Start run and every `pathly-run` terminates with `status=error` after exactly **one** stage transition, due to an FSM/driver contract mismatch that is hidden behind mocked tests. Fix that one bug + ~6 small usability fixes and the single-lane claude/codex flow crosses into MVP-ready.

**Neither fragments-P1 nor the entire B-core→C→A code-intel track is on the critical path to "usable."** Fragments P0 (the user-visible win) is already banked; P1+ is invisible internal cleanup. Code-intel is 100% design-stage, degrades to Grep/Read, and competes with a free commodity field — it should be *consumed*, not built.

---

## 1. Readiness scorecard

### ✅ What genuinely works end-to-end today (verified, not doc-trusted)

| Subsystem | Status | Evidence |
|---|---|---|
| Adapter install / `pathly-setup` | **shipped** | `pip install` + `pathly-setup <host> --apply` verified live for all 4 hosts (exit 0); manifest ownership + SHA-256 integrity + repair + uninstall; PyPI release via `v*` tag (`publish.yml`). |
| comms-board core (goals → task-DAG → executors) | **mostly-built** | `db/queries/comms.py:588-779` (get_ready_tasks/claim/complete/fail-cascade/reclaim); `supervisor/goal_run.py:36-142` (single/loop/team dispatch); ~55-70 tests pass. **This is the product's spine.** |
| Studio Command Center UI | **mostly-built** | Renderer typechecks clean; create feature → post → create goal → decompose → run all hit real routes; SSE-live board (`commsStore.ts:453-557`, `commsApi.ts:547-724`). |
| PTY spawn round-trip (single) | **mostly-built** | TERMINAL_SPAWN → node-pty → `/runner/terminal/result`; dual-cap scheduler + Windows `.ps1`/codex-`$null` hardening (`terminal.ts:206-242, 290-448`). |
| Fragment / skill composition (live FSM path) | **mostly-built** | `build_prompt → compose_skill` on the real `next_action`/`complete_stage` path (`fsm_ops.py:182-220, 798, 1019`); `/skills/compose` live; shipped manifest passes its own validator. |
| A single FSM transition | **works** | Empirically ran real `fsm_ops.complete_stage` on a seeded PLANNING feature → advanced PLANNING→DESIGNING and persisted. |
| Runner-mode billing/telemetry | **mostly-built** | Self-contained: supervisor reconciliation + `invoke.py` patch cost from `--output-format=json` stdout, independent of the Stop hook. |
| Unified markdown editor + byte-stable save | **shipped** | `notebook-edit-actions` Phase 0/1 + `editor-unify`; `tests/test_skill_round_trip.py`. |

### 🔴 What is broken or half-delivered

See **§2 Issues & Solutions** — every gap is enumerated there with evidence and a fix.

---

## 2. Issues & Solutions

Severity legend: **P0** = blocks the core promise / master is red · **P1** = should-fix before calling it usable · **P2** = honesty/consistency/UX polish.

### P0-1 🔴 FSM ↔ driver `next_state` contract mismatch — multi-stage runs die after stage 1

- **What:** `fsm_ops.complete_stage`'s success envelope emits `current_state` and **never a top-level `next_state` key** (it's only a local var). But all four driver call-sites gate "continue to next stage" on `result.get("next_state")`. On a normal advance the key is absent → both loops fall through to the "Unexpected result" → `status=error` branch and **terminate after exactly one transition**.
- **Evidence:**
  - `src/pathly_orchestrator/fsm_ops.py:450-470` (`_response_envelope` emits `current_state`, no `next_state`); `:928, :944, :1016` (`next_state` exists only as a local variable).
  - `supervisor/orchestrator.py:75` and `:525` → `:528-532` (Unexpected → `status=error`).
  - `runner/cli.py:74` (`resolve_stage`) and `:188-197` (`run_flow` prints "Unexpected result", returns 1).
  - **Masked by mocks:** `tests/test_supervisor.py:46-47` and `tests/test_runner.py:37-43` mock `complete_stage` to return `{'next_state': to}` (a fictional contract), while `tests/test_fsm_ops.py:363, 380` assert the **real** contract (`'next_state' not in result`). The real FSM is never driven through either real loop in any test.
  - Empirically reproduced: real `complete_stage` advance envelope has keys `[..., current_state, ...]` with **no** `next_state`.
- **Impact:** The product's defining capability (automated multi-stage headless pipeline) does not function. Affects Studio Start, `pathly-run`, **and** the interactive `run_flow`/`resolve_stage` CLI wrappers (only a raw `complete_stage` call advances).
- **Solution:**
  1. Either make `fsm_ops.complete_stage` also emit a top-level `next_state` on a successful advance, **OR** change all four driver call-sites to treat a clean envelope (`current_state` present; no `done`/`blocked`/`decide`) as a successful advance. (Prefer the latter — it keeps the FSM contract honest and centralizes the "advance" semantics.)
  2. Mind the branch ordering at each of the 4 sites (`_resolve_stage_supervised` returns the raw envelope at `orchestrator.py:209`; the decision/feedback return paths must stay consistent).
  3. **Add an integration test that drives the REAL FSM through the REAL supervisor loop and the REAL runner loop across ≥2 transitions, with no mocking of `complete_stage`.** This is the missing regression guard that let the bug ship green.
- **Effort:** Small but not a one-liner — 4 call-sites across 2 files + 1 integration test.

### P0-2 🔴 Master is RED — 4 stale golden-snapshot failures block CI

- **What:** `comms-post.md` fragment was updated (commit `a6bb49f4`, "agents provide description AND summary") but the golden snapshots were never regenerated. `pytest tests/` = **4 failed / 864 passed**.
- **Evidence:** `tests/test_compose.py` failures for `team/review`, `team/test`, `development/review`, `development/test`; `tests/snapshots/team__review.claude.md` dated 2026-06-24 vs `fragments/comms-post.md` dated 2026-06-28.
- **Impact:** Red master blocks CI-gated merges (including the P0-1 fix) and erodes the only safety net.
- **Solution:** Regenerate the 4 snapshots. **But not purely mechanical:** the review/test composed prompts changed *semantically* (new description-AND-summary wording) and no human reviewed the new output — eyeball the new fragment wording and confirm it's intended **before** blessing the snapshots.

### P0-3 🟠 Latent: `storage-path-alignment` unbuilt — first new-path team run splits artifacts

- **What:** ~14 skills and `db_api.py:75` still hardcode the legacy `pathly/plans/*/` glob, while the new `pathly/<topic>/` root is only half-wired (FSM resolver + Studio dual-scan + single-agent board_run done).
- **Impact:** Harmless **only** because zero new-path features exist today. The first full-team run on a `+New-feature` plan under the new root would silently split artifacts across two roots.
- **Solution:** Replace the remaining hardcoded `pathly/plans/*/` literals + single-path discovery globs with the FSM-resolved storage-path / dual-scan / DB query. Land it before exercising the new-path team flow.

### P1-1 🟠 Only 2 of 4 adapters work headless; the two argv builders disagree

- **What:** `copilot` and `antigravity` have `headless: null`. Python `resolve_command` **raises** `ValueError` (uncaught → run dies with generic `status=error`); Studio `cliEngine.ts` **silently falls back to the claude argv shape**. The two paths disagree.
- **Evidence:** `core/adapters.yaml:13-26`; `adapters.py:56-61`; `orchestrator.py:381-404` (only wrapped in `except RuntimeError`) → `:534` (outer `except Exception`); `cliEngine.ts:75-80`.
- **Impact:** The "adapter-agnostic, route any stage to any CLI" promise is half-delivered; selecting copilot/antigravity either kills the run opaquely or silently runs the wrong CLI.
- **Solution:** Either (a) implement real headless templates for the two, **or** (b) validate `adapter_map` at run-start and **reject unsupported adapters up-front with a clear message** in *both* builders. Strategic option: **adopt the Agent Client Protocol (ACP)** instead of hand-built per-adapter argv (see §6).

### P1-2 🟠 Runner is inert without the Electron Studio app

- **What:** The supervisor delegates **all** process spawning to node-pty via SSE and blocks on `wait_started(timeout=30)`. With no Studio spawn-listener connected, every stage times out (`terminal_spawn_timeout`). There is no server-side/CI headless spawn path (`runner/invoke.py` exists but the supervisor path doesn't use it).
- **Evidence:** `supervisor/terminal.py:262-266`; `runner/invoke.py:111-147` (unused by supervisor).
- **Impact:** "Headless" means *no human in the per-step loop*, **not** *runs standalone*. No CI/server-only path to drain a DAG.
- **Solution:** Give the supervisor a server-side spawn fallback (reuse `runner/invoke.py`) so a goal/DAG can be drained without the desktop app — required for any CI/unattended story. (Lower priority if the desktop-only model is acceptable for v1, but it caps the product's reach.)

### P1-3 🟠 Flow builder is decoupled from execution

- **What:** A visually built/edited flow cannot be selected to run from any UI surface. `FlowControlBar` Start **hardcodes the team flow**; the only flow picker lists 5 hardcoded built-ins; `FlowEditor` toolbar has Save/Add-state/Auto-layout/Publish but **no Run button**.
- **Evidence:** `FlowControlBar.tsx:41`; `SingleAgentButton/flowCatalog.ts:4, 37`; `FlowEditor/VisualView/parts/Toolbar.tsx:34-71`; `FlowWizard.tsx:256` (writes to user flows dir, not a DB-seed location re-synced on server start).
- **Impact:** The visual flow builder — a headline surface — is disconnected from the runner.
- **Solution:** Add a flow-list endpoint + a Run action in `FlowEditor`/`FlowControlBar` that runs the *currently selected* flow (not the hardcoded team flow); ensure wizard-created flows are synced to a runnable DB location.

### P1-4 🟠 Misleading / no-op UI controls

- **What:** `FeatureCard` Unblock/Skip/Pause only mutate local Zustand state (no FSM/runner API call); Unblock locally flips warnings to "resolved" without server persistence. Separately, a hardcoded `INITIAL_FEATURE='send-to-agent-diff'` is persisted into layout, so a fresh/other project opens an empty/wrong board section until manually re-picked.
- **Evidence:** `FeatureCard.tsx:71-85`; `commsStore.ts:264-282` (`setFeatureStatus` local-only); `commandCenterStore.ts:10-21` (hardcoded INITIAL_FEATURE), `:189-197` (migration only resets on version<3).
- **Impact:** Makes a working app *look* broken — first-impression usability killers.
- **Solution:** Wire Unblock/Skip/Pause to `/runner/*` (or remove them); drop/repair the persisted hardcoded `INITIAL_FEATURE` so a fresh project opens to a valid board.

### P1-5 🟠 Auto-decompose produces a flat, edgeless DAG; executors are serial-only

- **What:** `_decompose_planner` posts flat `type=task` messages and never sets `depends_on`, so every auto-decomposed task is immediately "ready." Shipped executors run `SerialIsolation` (max_concurrency=1). `LaneIsolation` (true parallel) is unit-tested but wired into no production executor; `WorktreeIsolation` is a `NotImplementedError('P3')` stub. One test (`test_dag_scheduler.py::test_diamond_dag_parallelism`) already fails on the unshipped parallel path.
- **Evidence:** `supervisor/goal_run.py:463-530`; `supervisor/isolation.py:69-86, 89-106`.
- **Impact:** The headline appeal of a *parallel* task-DAG is unavailable; "DAG" is effectively a flat serial list.
- **Solution (deferred — not a usability gate):** Real dependency edges in decompose + wire `LaneIsolation` when parallelism is genuinely needed. **Defer to the parallel-fleet plans** (see cut-list) — serial already self-drives a goal end-to-end.

### P2-1 🟠 `validate_composition` never called at startup

- **What:** Defined, exported, and tested but never invoked at FSM server boot — a bad manifest edit (via skill editor / DB override) surfaces only at first compose, not at boot.
- **Evidence:** grep finds callers only in `compose.py` (def) + `skills/__init__.py` (export); not in `http_server/app.py` or any boot path.
- **Solution:** Call `validate_composition` on FSM server startup so a bad manifest fails fast.

### P2-2 🟠 Interactive `/pathly` cost telemetry silently no-ops; possible double-count

- **What:** The Stop hook hard-exits when `PATHLY_PROJECT_ROOT` is unset, and neither the installer nor Studio ever sets it. Plus a possible double-count: if an interactive agent self-reports cost into `AGENT_DONE` while the hook also appends `BILLING_UPDATE`, `db_api` SUMs both with no dedup.
- **Evidence:** `stop_telemetry.py:129-131`; `orchestrate.py:32-108` (no env injection); `index.ts:109-113`, `terminal.ts:455-461` (`env: process.env` only); `db_api.py:131-135, 199-214` (SUM over both event types).
- **Solution:** Have the installer/Studio inject `PATHLY_PROJECT_ROOT`; add a dedup/idempotency guard so an already-priced `AGENT_DONE` isn't summed with a `BILLING_UPDATE`. Add a functional test for `stop_telemetry.py` (currently zero coverage).

### P2-3 🟠 Windows: orphaned engine processes after app quit

- **What:** `killAllPtys()` on `before-quit` uses `p.kill()` not `killPtyTree()`; on Windows `p.kill()` ends only the `powershell.exe` host, orphaning the child claude/codex engine.
- **Evidence:** `terminal.ts:259` (vs the correct `killPtyTree` taskkill `/T /F` at `:248-256`).
- **Solution:** Use `killPtyTree()` in the quit-all path.

### P2-4 🟠 Code-health / SOLID drift

- **What:** The repo's own 400-line limit and no-upward-import rule have no automated enforcement. 12 of 143 Python files exceed 400 lines (`comms.py`=937, `fsm_ops.py`=924). One layer violation: `db/queries/comms.py:318` imports `runner.embeddings`. Studio frontend tests thin (6 vitest files / 483 TS files). No Windows CI for the unit/integration matrix; `terminal.ts` + `cliEngine.ts` have no unit tests.
- **Solution:** Add a CI lint that enforces the file-size + layer rules; split the two oversized files; add unit tests for the scheduler/argv builders; add a Windows CI lane.

---

## 3. Your mental model — corrected

Your words: *"a user can spawn cli agents in single or flows on the board with one goal or task; single/loop/flows with one goal or task."* — **Structurally correct.** It maps exactly onto the implemented model: `goal_run.py` reads `goal.executor` and dispatches `single` / `loop` / `team(=flow/FSM)`, and Studio's `GoalRunButton`/`GoalDecomposeButton`/`SingleAgentButton` dispatch them.

Four corrections about **today**:

| You picture | Reality |
|---|---|
| Flow/team on a goal → runs to completion | Dispatchable, **cannot complete** (P0-1). Single-agent + single FSM step work. |
| "Headless" = standalone / server / CI | = *no human in per-step loop*, **not** standalone. Requires Studio as the PTY host (P1-2). |
| Task-DAG = parallel | Flat + **serial** today; parallel is unbuilt P3 (P1-5). |
| Adapter-agnostic = any CLI | Only **claude + codex** headless (P1-1). |

---

## 4. What you gain from fragments + B-core→C→A (and why it isn't "usable")

- **Fragments:** P0 is **already banked** — `/skills/compose` live, client seam wired, fixed a real summary-corruption bug. P1+ (goal-backed profile, `blocks:`→`profiles:` rename, Decompose/drain-dag conversion) is **pure internal DRY** — invisible to users, gates nothing. *Defer; do not let it block "usable."*
- **B-core → C → A (code-intel):** **100% design-stage, zero code.** No `runner/code_context.py`, no `/code/query` route, no `_mcp/*.json`; the external **gitnexus binary isn't even procured**. Two of these plans have `RUNNER_STATE=error` (crashed at PLANNING). It degrades to Grep/Read — *proof the app works without it* — and competes with a free commodity field (GitNexus ~43k★, CodeGraph ~47k★, Serena).
  - **Verdict:** **Defer the whole A/B/C fork.** If a real code-navigation pain point ever appears, build exactly **one** surface — **code-intel-proxy (C) on top of code-context-injection (B)** — and **cut gitnexus (A) and lsp-integration**. Better: **consume** a best-in-class graph as a fragment instead of building your own.

> **Net:** Finishing fragments-P1 and the code-intel track does **not** get you to a usable app. The keystone is **P0-1** + the §2 P0/P1 fixes.

---

## 5. Plan inventory & cut-list

| Plan / cluster | Status | Necessity | Recommendation |
|---|---|---|---|
| **comms-board core** | shipped/in-progress | **must-have** | Done — it IS the control plane. Only P0-1 unblocks its execution. |
| **notebook-edit-actions** P0/P1 | done | **must-have** | Byte-stable editing of md contracts. Keep. |
| **editor-unify** | done | should-have | Done. |
| **storage-path-alignment** | designed-not-built | **must-have (latent)** | Land before first new-path team run (P0-3). |
| **unified-cli-composition** P0 | done | should-have | Banked. Wire `validate_composition` at boot (P2-1). |
| **unified-cli-composition** P1+ | designed-not-built | nice-to-have | **Defer** — invisible internal cleanup. |
| **change-explorer** Phase 0-1 | designed-not-built | should-have | **Build Phase 0-1 only** (in-Studio git diff). Cut the per-hunk staging engine. |
| **notebook-edit-actions** Phase 2 (Cmd+K) | designed-not-built | should-have | High-value, reuses draft-diff pipeline. Not gating. |
| **chat-stop-proxy**, **ai-action-config** | done | should-have | Done — just sync stale PROGRESS.md. |
| **board-context-pull** | in-progress (landed) | should-have | Finish last-mile Studio surfaces. |
| **brightsky-agent-upgrade** | done | nice-to-have | **Close as shipped** (docs stale). |
| **differ** | stub-empty | defer-or-cut | **CUT** — see §5.1. |
| **lsp-integration** | designed-not-built | defer-or-cut | **CUT** — clearest cut; downstream of unbuilt gitnexus; most fragile. |
| **code-context-injection (B)** / **code-intel-proxy (C)** | designed-not-built | should-/nice-have | **Defer**; if ever, build B+C only. |
| **gitnexus-integration (A)** | designed-not-built | nice-to-have | **Cut** — consume a graph as a fragment instead. |
| **codebase-architecture** | stub-empty (errored) | defer-or-cut | **CUT** — empty errored stub, no idea to evaluate. |
| **parallel-fleet-part-1 / part-2** | designed-not-built (0%) | defer-or-cut | **Defer** — ~17 docs, 0% built. Cut the Fleet Dashboard first. |
| **comms-board P3 (parallel)** | designed-not-built | nice-to-have | **Defer + consolidate** into parallel-fleet (duplicate framing). |
| **md-diagram-conversion** | designed-not-built | defer-or-cut | **CUT** — decoration for an LLM-contract author. |
| **editor-notebook-enhancements** | designed-not-built | nice-to-have | **Cut to backlog** — load-bearing item already shipped via notebook P1. |
| **studio-sidebar-redesign** | designed-not-built (PROGRESS falsely "done") | nice-to-have | **CUT** — cosmetic; the one useful slice already exists. |
| **chat-automate-toggle** (AI-draft panel) | designed-not-built | nice-to-have | **Defer** — overlaps board planner/architect agents. |
| **board-storm-consultation** | designed-not-built | nice-to-have | **Defer** — overlaps PO/consultation decomposer. |
| **rtk-token-killer-eval** | designed-not-built | defer-or-cut | **CLOSE** — its own verdict is "do not build." |

### 5.1 The `differ` verdict — CUT

The entire `differ` plan is **one 1,556-byte `artifacts/BOARD_EVAL.md`** — no BRIEF/DESIGN/STATE/code. Its own text says it's a *design question*, not a ticket, and explicitly proposes reusing the **same `DraftDiffViewer` seam** that `change-explorer` is already built on. Pathly already does semantic change assessment via the reviewer/tester pipelines (`REVIEW_FAILURES.md`/`TEST_FAILURES.md`) and ships inline accept/reject via `DraftDiffViewer`. **Zero distinct capability is missing.** → Delete `pathly/plans/differ/`; if `change-explorer` Phase 0-1 proves its worth, address board-artifact diffing as its Phase 3.

---

## 6. Competition & positioning

**You researched the wrong competitors.** CrewAI/MetaGPT/ChatDev/AutoGen are a **different category** — they orchestrate *internal LLM personas via API calls*, not real external coding CLIs against a live repo.

**Your real competition** is the CLI-agent-orchestrator space (crowded, converging fast, 30+ entrants in 2025-26):

- **Vibe Kanban (BloopAI, ~27k★)** — closest open-source analog (board over 10+ CLIs, worktree-per-task). Interactive, no FSM/roles/fragments. **Sunsetting (Bloop shut down early 2026)** → an opening for you.
- **GitHub Agent HQ / Mission Control** — **biggest threat.** Identical "command center for many heterogeneous agents" pitch, shipped *by default to every Copilot seat*, already in preview with audit/permissions/Plan-Mode/AGENTS.md. If it adds opinionated pipelines + local exec, it commoditizes you overnight.
- **Bernstein, Composio Agent Orchestrator, Devin Desktop, Conductor (Series A), Emdash (YC W26), Warp Oz, Google Antigravity 2.0 Agent Manager** — each owns 1-3 of your pillars. Bernstein already has 44 adapters + passive scheduler + DAG + `--headless`.
- **Claude Code Agent Teams** — native shared-task-list/mailbox/lead/hooks *inside the CLI you depend on*. One headless/board mode away from erasing your edge for Claude-only users.

**Positioning verdict:** Your **5-pillar bundle** (FSM-SDLC + role contracts + fragment composition + comms-board substrate + headless-primary) is **currently unique as a combination** — but *"occupied on paper, vacant in practice,"* because the bundle doesn't yet execute (P0-1, 2/4 adapters, no CI path, no parallelism). Defensibility is **weak-to-moderate and convergence-vulnerable** — an execution/integration moat, not a structural one.

**Strategy:**
1. **Don't lead with "orchestrate many CLIs from a board"** — that's table-stakes now; you're outgunned on funding/distribution.
2. **Lead with the 3 legs incumbents won't combine:** (a) enforced opinionated methodology (roles + rigor + FSM gates), (b) **vendor-neutral, local-first, zero-egress, Windows-first** (Conductor=Mac, Agent HQ/Antigravity=cloud — a real seam), (c) **board-as-shared-semantic-context substrate**.
3. **Adopt the Agent Client Protocol (ACP)** instead of hand-built adapters.
4. **Consume** GitNexus/CodeGraph/Serena as fragments — don't rebuild code-intel.
5. **Who it's for:** solo/small team that *already pays for Claude Code + Codex*, wants a rigorous inspectable *local* process, on *Windows*. **Not** for citizen-builders, GitHub/IDE-native teams, or anyone needing it unattended *right now*.

---

## 7. The pattern worth naming — design-without-build

- **Parallelism is designed 3×** (comms-board P3 + parallel-fleet-1 + parallel-fleet-2 ≈ 17 docs, 0% built).
- **Code-intel is over-forked** (3 surfaces + 2 external binaries + ~6 docs, 0% built).
- At least 4 plans had automated runs that **crashed at PLANNING and produced nothing**.
- **The roadmap can't be trusted by its own status fields** — several "BUILDING/TODO" plans are actually done; `studio-sidebar-redesign` claims "Conv1 DONE" but the code never landed. Verify against code before allocating.

> Highest-leverage move: **stop planning, fix P0-1, and make the single-lane claude/codex flow actually run end-to-end.** Then everything else is real.

---

## 8. Recommended roadmap (in order)

1. **Fix P0-1** (`next_state` contract) + add the real-FSM-through-real-loop integration test.
2. **Fix P0-2** (regenerate the 4 snapshots; eyeball the new review/test prompt wording).
3. **Land P0-3** (`storage-path-alignment`) before any new-path team run.
4. **P1 batch:** honest adapters (P1-1) + wire `validate_composition` at boot (P2-1) + fix no-op `FeatureCard` controls + `INITIAL_FEATURE` (P1-4).
5. **Connect the flow builder to the runner** (P1-3), then demo one full STORM→DONE run on claude+codex with Studio open. **← that's your "usable app" milestone.**
6. (Then, by demand) server-side spawn path (P1-2) → real DAG parallelism (P1-5) → ACP + consumed code-intel fragment.

---

## Appendix — assessment method

32-agent workflow (2.65M tokens, ~49 min): 11 codebase-reality readers (verified against source; several reproduced findings by running code), 8 plan-inventory readers, 9 competitive web-research agents, 3 synthesis agents (readiness / cut-list / positioning), 1 adversarial critic. The critic independently re-verified the central `next_state` thesis at every cited line and reproduced red master — and judged the overall verdict **well-calibrated** (neither over-optimistic nor over-pessimistic), with two nuances folded in above: the fix spans 4 call-sites + a real integration test (not literally "10 lines"), and the interactive CLI wrappers (`run_flow`/`resolve_stage`) are broken by the same bug (only a raw `complete_stage` call advances).
