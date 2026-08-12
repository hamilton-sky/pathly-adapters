# SPEC — Spawn Policy (unified model + logging control)

**Status:** design · P0 (DB foundation) landing · **Scope:** feature
**Depends on:** unified-control-plane (the single spawn chokepoint) · **Date:** 2026-08-09

> One Settings control plane for **every** agent spawn: choose (1) **which model per agent/role**
> and (2) **where logs go + how much** — DB-backed, read by **both** the renderer gate and the
> Python resolver, applied at the **single spawn chokepoint**. Purpose: uniform control of the
> build + **cost + monitoring**.

## 0. The invariant (most important)

The **cost/monitor spine is ALWAYS ON** — never user-disableable. That is the control plane
itself: `run_history` + `agent_invocations` + gate liveness + `completion-report`. Only
**agent-narration** sinks (board posts, verbosity) are configurable. A user must never be able to
switch off the monitoring/cost the whole feature exists to give them.

## 1. The Settings UX — TWO sections (not three)

Roles and "places" are the **same axis** (every place — split/analyze/board — *is* a role), so
they merge into one grouped list. Don't build two override lists that overlap.

1. **Models** — a **global default** (company + model) + an optional **grouped override list**:
   - *Pipeline*: architect · planner · builder · reviewer · tester · scout · designer · director · evaluator
   - *Editor / one-shot*: split · analyze · diagram · comment · summarize
   - Each row → pick company + model. Dropdowns are **data-driven from `db/pricing.py::PRICING`**
     (models per provider), **plus a free-text "custom model"** escape hatch per provider (model drift).
2. **Logging** — board on/off + verbosity (quiet/normal/verbose). **Monitor + Cost shown locked/always-on.**

## 2. Resolution — layered, ONE resolver

`per-run override → per-role (DB) → global default (DB) → engine default (drop --model)`.
Roles ≡ the existing telemetry/agent identities. Both consumers — renderer (`cliEngine`/gate) and
Python (`resolve_command` caller) — read the **same** DB config, so nothing re-fragments.

## 3. Audit — current wiring (code-intel verified 2026-08-09)

| Concern | Where it lives today | Action |
|---|---|---|
| **Model → argv** | `supervisor/terminal.py::_run_stage_via_terminal(model=…)` (405/461) → `adapters.py::resolve_command(adapter, model)` → `{model}`. Model today ≈ `""` (engine default). | **Inject the resolved model at the caller** of `_run_stage_via_terminal`. |
| **Config store** | `db/queries/app_settings.py` (`get/set_setting` + typed helpers; precedent `get_default_progress` @ key `board:default_progress`). | **Extend here (P0).** |
| **Model registry** | `db/pricing.py::PRICING` (models per provider + $/token). | **Drives the dropdowns.** |
| **Company memory (partial)** | renderer `editorCli.ts` `CLI_KEY_*` (localStorage, per-place *adapter*, renderer-only — never seen by Python). | **Subsume into the DB config.** |
| **Logging fragments** | `core/skills/fragments/{comms-post,progress-logging,completion-report}.md` attached via `composition.yaml` → `skills/compose.py::compose_skill`. Verbosity precedent: `board:default_progress` + `/comms/default-progress`. | **`comms-post`/`progress` composition reads the logging config; `completion-report` stays always-on.** |
| **`runModel` bypass** | `renderer/services/aiRouter.ts::runModel` (model-mode summaries) skips the gate. | **Route through the gate** or it ignores the policy + escapes cost. |

## 4. Phased plan

- **P0 — DB config foundation (this):** model-policy + logging-config helpers in
  `db/queries/app_settings.py` + a `resolve_agent_model` resolver + tests. The keystone
  ("controlled by the DB backend"). Pure-additive, no behavior change until P1 wires it.
- **P1 — HTTP + resolver wiring:** GET/PUT routes (mirror `/comms/default-progress`) +
  inject `resolve_agent_model(...)` at the model-decision point before `_run_stage_via_terminal`.
- **P2 — Settings UI:** Models section (grouped, PRICING-driven, custom escape hatch) + Logging
  section, writing to the DB.
- **P3 — logging composition + runModel:** board-narration fragments honor the logging config;
  route `runModel` through the gate.

**Test-as-you-go; the invariant (§0) is a hard rule for every phase.**
