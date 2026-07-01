---
name: Happy Flow
---
# Multi-Adapter Runner — Happy Flow

## Overview

A user starts an autonomous run of a routed flow (BUILD→codex, REVIEW→claude) with a $5 / 20-iteration cap. The supervisor drives each stage on its routed adapter, streams progress, parks for one decision, and finishes — all without a blocking prompt.

## Step-by-Step Happy Flow

### Step 1: Start
- **User does**: `POST /runner/start {flow:"team", topic:"feat-x", max_iterations:20, max_cost_usd:5.0, autonomy:{claude:true,codex:true}}`.
- **System does**: registers `RunnerState` for `feat-x`, spawns the daemon loop, returns `{status:"running", run_id}`.
- **State after**: `/events/runner?topic=feat-x` begins emitting; status `running`.

### Step 2: Routed stage execution
- **System does**: `next_action` → `preferred_adapter="codex"` for BUILDING. `resolve_command("codex", prompt, model)` → argv. `invoke_agent` runs it headless. Emits `STAGE_CHANGE{state:BUILDING, adapter:codex}` and `COST_UPDATE`.
- **State after**: BUILDING runs on codex; cost accrues.

### Step 3: Boundary check
- **System does**: at the stage boundary, checks pause/abort/caps — all clear (under $5, under 20 iterations) — and advances.
- **State after**: iteration counter +1; `RUNNER_STATE.json` mirrored.

### Step 4: Decision point
- **System does**: `complete_stage` returns `decide` → status `awaiting_decision`, `pending_menu` set; emits `DECISION_MENU{question, options, default}`.
- **User does**: `POST /runner/decision {topic:"feat-x", decision:"proceed"}`.
- **System does**: validates `proceed ∈ options`, feeds it to `complete_stage`; loop resumes.

### Step 5: Adapter switch + session continuity
- **System does**: REVIEWING routes to `claude`. Open session was codex → different adapter → opens a fresh claude session; emits `SESSION{adapter:claude, action:"opened"}`.
- **State after**: review runs on claude.

### Step 6: Done
- **System does**: FSM reaches DONE; status `done`; final `COST_UPDATE`; loop thread exits.
- **State after**: `RUNNER_STATE.json` terminal; SSE stream closes cleanly.

## End State
A feature built on codex and reviewed on claude, driven autonomously within caps, with one human decision — no blocking prompt, full live observability.

## Success Indicators
- [ ] Each stage ran on its `preferred_adapter`.
- [ ] Caps were respected; the run never exceeded them.
- [ ] The decision round-tripped through the FSM (not a CLI).
- [ ] SSE emitted stage/cost/decision/session events throughout.
- [ ] An equivalent run with no `adapter_map` uses the default adapter and still completes (backward compatible).
