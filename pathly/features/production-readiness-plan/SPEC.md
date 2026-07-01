# Pathly — Production-Readiness Assessment & Hardening Plan

**Feature:** `production-readiness-plan`
**Author:** architect (Claude Opus 4.8, via doc-audit dogfood session)
**Date:** 2026-07-01 · **Baseline version:** 2.18.1
**Status:** SPEC / proposal — not yet scheduled

> Companion to [docs/PRODUCTION_READINESS.md](../../../docs/PRODUCTION_READINESS.md) (which tracks the
> *adapter-install* release gates). This spec is broader: it assesses the **whole system** and lays out
> the work to take Pathly from "usable-with-significant-gaps" to a trustworthy, production-grade,
> board-driven control plane.

---

## 1. Thesis

Pathly's **core idea is right and somewhat ahead of the field**: a durable, DB-backed **board as the
substrate** — goals decompose into a task-DAG, agents post artifacts/decisions/discoveries back, and
that context is re-injected into every headless agent's prompt. It's a *blackboard architecture for LLM
agents*, layered cleanly over a **passive FSM** (decides the next step) and a **supervisor** (executes),
with a **fragment/skill split** (skill = *what*, fragments = *how it connects to Pathly*) and
**adapter-agnostic** delegation across Claude/Codex/Copilot/Antigravity.

The risk is **not the concept — it is consolidation.** Too many half-built subsystems are layered on a
core loop that is not yet reliably dogfooded, and the docs/memory have been running ahead of the code.
This plan freezes the frontier, hardens one loop end-to-end, pays down the storage/duplication debt,
adds CI gates that keep docs and structure honest, and lets the board/DAG model become the center.

---

## 2. What is strong (keep and lean into)

- **Board-as-substrate** (`comms_messages` + `comms_artifacts`, `/comms/*`). Externalizing state out of
  the context window into a queryable store is the winning bet. *No agent is blind to what came before.*
- **Passive FSM + separate supervisor loop.** Deterministic, testable, recoverable from the event log.
- **Skills = *what*, fragments = *how*.** Dependency-injection for prompts; one skill runs interactive
  or headless; connection-to-Pathly is centralized and un-editable.
- **Adapter-agnostic `agent_hint` + `preferred_adapter`.** Not betting on one vendor — a real
  differentiator vs. single-CLI orchestrators.
- **SOLID discipline is real** (layer rules, one-domain-per-blueprint) and mostly enforced — the
  codebase is navigable, which is rare at this size.

**Corollary:** the goal → task-DAG → executor model is the promising center. The fixed
`STORM→…→DONE` pipeline is the older, more rigid layer that the board should progressively supersede.

---

## 3. Core problem — expansion is outrunning consolidation

Evidence gathered during the 2026-07-01 doc audit:

- A storage flatten shipped (`db6a78ac`, features → flat `pathly/features/<name>/`) but a **core CLI
  path silently broke**: `cli/_discovery.py` still globbed the nested `features/*/plans/STATE.json`, so
  `pathly-status`/`ff`/`back`/`log` found **none** of the current features. Nobody noticed → the
  headless/CLI loop is **not** the daily driver. (Fixed in this session; symptomatic of the pattern.)
- `pathly/plans/` is declared "fully retired," yet it remains **hardcoded in ~6 subsystems**
  (`eventlog.py`, `runner/hydrate_helpers.py`, `http_server/feedback.py`, `blueprints/core/health.py`,
  `otel_export.py`, `pathly_hooks/stop_telemetry.py`) plus the `create-feature` skill.
- **Docs/memory drifted ahead of code** (this whole audit): version `2.16.x`→`2.18.1`, blueprint tree
  described as flat files when it is subpackages, `goal_run.py` documented as the dispatcher when it is a
  23-line shim, fragment list 7 vs 15 on disk, three non-existent skill dirs listed.
- **Duplication:** the dash-safety guard is mirrored in **three** places
  (`adapters.py::_dash_safe_prompt`, `skills/compose.py::_strip_leading_frontmatter`,
  `cliEngine.ts::dashSafePrompt`) that must be kept in sync by hand.
- **400-line rule regressed** after the 2.18.1 "enforce" commit: `supervisor/terminal.py` (462),
  `supervisor/goal_executor.py` (462), `fsm/engine_actions.py` (408).
- **Unwired agent:** `evaluator` exists in `core/agents/research/` but has **no `_meta/*.yaml` in any of
  the 4 adapters** — it cannot be installed (violates the core→adapter sync rule).

---

## 4. Gap analysis

| # | Gap | Evidence | Severity |
|---|---|---|---|
| G1 | End-to-end headless loop not dogfooded | `_discovery.py` regression unnoticed | **High** |
| G2 | Storage migration incomplete | `pathly/plans/` in 6+ subsystems + create-feature skill | **High** |
| G3 | Docs/memory drift ahead of code | this audit (9 files corrected) | Medium |
| G4 | Duplicated prompt-safety logic (3 mirrors) | `adapters.py`, `compose.py`, `cliEngine.ts` | Medium |
| G5 | Surface sprawl (differ / code-intel / parallel-fleet before core trusted) | readiness cut-list | **High** |
| G6 | Fixed FSM pipeline vs board/DAG tension | two overlapping execution models | Medium |
| G7 | 400-line rule not gated; regressions land | 3 files > 400 post-"enforce" | Low |
| G8 | `evaluator` agent unwired | no adapter `_meta/evaluator.yaml` | Medium |
| G9 | Positioning: installer-first vs board-first framing | docs admit historical drift | Medium |
| G10 | Test coverage thin at FSM↔driver + storage boundary | `next_state` bug, flatten bug both shipped | **High** |

---

## 5. Solution — phased hardening plan

### Phase 0 — Freeze & triage *(1–2 days)*
- **Freeze the feature frontier.** No new subsystems until the core loop is trusted.
- Adopt the readiness cut-list: **cut** differ + LSP; **defer** code-intel and parallel-fleet behind a
  capability flag (already largely the case) until Phase 4.
- Write the **golden-path definition** (§6) everyone agrees to.

### Phase 1 — Make ONE loop bulletproof *(the keystone)*
- Pick the canonical loop: **Studio Start → goal decompose → `single` executor drains DAG → DONE**,
  fully headless, on a real feature.
- Add an **end-to-end smoke test** that drives the *real* FSM through ≥1 real transition per stage
  (per the `next_state` lesson: mocks on both sides of the boundary hide contract breaks).
- **Dogfood daily:** run Pathly on Pathly's own backlog (this spec's tasks are the first candidates).
- Exit gate: 5 consecutive green end-to-end runs with no manual intervention.

### Phase 2 — Consolidate storage *(pay down G2)*
- **One resolver to rule them all:** route every `pathly/plans|features` reference through
  `storage_paths.py` / `_resolve_storage_path`. Delete the hardcoded `pathly/plans/` bases in
  `eventlog.py`, `hydrate_helpers.py`, `feedback.py`, `health.py`, `otel_export.py`, `stop_telemetry.py`.
- Fix `create-feature` skill's workspace path (`/plans/` → flat) to match the flatten.
- Add a **layout invariant test**: create a feature the canonical way, assert every subsystem
  (discovery, eventlog, feedback, telemetry, hydration) resolves the *same* directory.

### Phase 3 — De-duplicate & gate *(pay down G3, G4, G7)*
- **Unify dash-safety:** single source of truth. Options: (a) server always returns dash-safe prompts so
  the TS mirror becomes a thin assert; (b) a shared contract test that feeds identical inputs to all
  three and asserts identical output. Ship the contract test regardless.
- **CI gates** (fail the build, not just advise):
  - 400-line limit check over `src/pathly_orchestrator/**` and `studio/src/**`.
  - Extend `check_version_sync.py` to also assert the version string in README/CLAUDE.md/SECURITY.
  - A **doc-structure test**: assert the blueprint/​supervisor/​fragment/​skill lists in the CLAUDE.md
    files match the filesystem (catch drift automatically — this audit should never need repeating).

### Phase 4 — Board/DAG becomes the center *(resolve G6; re-admit deferred work)*
- Make goal → DAG → executor the primary path; treat the fixed `team.flow` pipeline as one executor
  strategy, not the spine.
- Re-admit code-intel / parallel-fleet **only behind the golden-path gate**, each with its own smoke test.
- Wire `evaluator` (`_meta/evaluator.yaml` in all 4 adapters) so board auto-evaluation actually installs.

### Phase 5 — Observability & trust
- **Structured, versioned events** (add `schema_version` per the standing RISK_ASSESSMENT item) so
  `pathly-events`/telemetry never silently mis-read.
- **Run replay:** reconstruct any run from the event log + board (the FSM is already deterministic —
  expose it as a debugging tool).
- Make hook/telemetry failures **observable** (they are currently silent by design).

### Phase 6 — Positioning
- Lead every surface with the **headless-board** story (done in narrative docs; carry it to the site/
  README hero + a 60-second "why the board" demo). Crisp one-liner beats feature lists vs. Agent HQ.

---

## 6. Production-readiness definition of done (gates)

A build is "production-grade" when **all** hold:

1. **Golden path:** Studio Start → decompose → executor → DONE runs headless, unattended, on a fresh
   machine, 5× green.
2. **Storage:** one resolver; zero hardcoded `pathly/plans/` bases; layout-invariant test green.
3. **No silent drift:** CI gates for line-limit, version sync (incl. prose docs), and doc-structure match.
4. **No duplication traps:** dash-safety contract test green; single source of truth.
5. **Every shipped agent installs** (adapter `_meta` parity test, incl. `evaluator`).
6. **Every run is replayable** from events + board.
7. **`pytest -q` green on 3.11–3.13; Studio typecheck + Vitest green.** (already gated)
8. **Frontier discipline:** deferred subsystems are flag-gated and each has a smoke test before re-admit.

---

## 7. Prioritized backlog (seed the DAG)

**P0 — trust the core**
- T1. End-to-end golden-path smoke test (real FSM, all stages). *(G1, G10)*
- T2. Single storage resolver; delete 6 hardcoded `pathly/plans/` bases + fix create-feature. *(G2)*
- T3. Layout-invariant test across all subsystems. *(G2, G10)*

**P1 — stop the drift**
- T4. CI: 400-line gate; extend version-sync to prose docs. *(G7, G3)*
- T5. Doc-structure test (CLAUDE.md lists vs filesystem). *(G3)*
- T6. Dash-safety contract test (3 mirrors → 1 asserted behavior). *(G4)*
- T7. Wire `evaluator` `_meta` in all 4 adapters + adapter-parity test. *(G8)*

**P2 — center the board, re-admit deferred**
- T8. Make goal→DAG the primary path; pipeline = one executor strategy. *(G6)*
- T9. `schema_version` on events + replay tool. *(G5, observability)*
- T10. Re-admit code-intel / parallel-fleet behind the golden-path gate. *(G5)*
- T11. Positioning pass: README hero + "why the board" demo. *(G9)*

---

## 8. Sequencing notes & risks

- **Do P0 before anything else.** Every deferred subsystem re-admitted before the core is trusted just
  widens the untested surface (the exact pattern that produced G1/G2).
- **The flatten and `next_state` bugs share a root cause:** changes crossed a boundary with tests/mocks
  on both sides. The layout-invariant (T3) and end-to-end (T1) tests target that class directly.
- **Don't over-rotate on the pipeline retirement (T8).** It is load-bearing today; migrate behind the
  DAG path incrementally, not in a big bang.
- **Keep the multi-adapter promise cheap:** unify prompt composition (dash-safety, fragments) so adding
  an adapter stays thin.
