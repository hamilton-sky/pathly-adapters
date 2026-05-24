# Enforcement Gates — Happy Flow

## Overview

A builder finishes implementation, runs verify, and calls `complete_stage`. The FSM checks
the gates declared in `team.flow.yaml`, finds all conditions met, and advances to `REVIEWING`
— identically whether the builder is Claude Code or Codex.

## Step-by-Step Happy Flow

### Step 1: Builder completes work and calls complete_stage

- **Builder does**: Runs `pytest`, writes `VERIFY.md` with `RESULT: PASS` on line 1, calls `POST /complete_stage`.
- **System does**: `complete_stage` calls `evaluate_transition_rules` → computes `next_state = REVIEWING`.
- **State after**: `next_state` resolved, gates not yet evaluated.

### Step 2: run_gates() evaluates BUILDING→REVIEWING gates

- **System does**: Reads `gates["BUILDING->REVIEWING"]` from `team.flow.yaml`. Runs `verify_gate` — finds `VERIFY.md`, reads line 1, confirms exactly `RESULT: PASS`. Runs `scope_gate` — reads declared files from `CONVERSATION_PROMPTS.md`, runs `git diff --name-only <conv_start_sha>`, confirms all diff paths are declared.
- **State after**: `run_gates()` returns `None` (all gates pass).

### Step 3: Transition actions run, state advances

- **System does**: Calls `run_transition_actions` → commits build artifacts. Writes `STATE.json` with `current = REVIEWING`. Appends `STATE_TRANSITION` event.
- **State after**: Pipeline is in `REVIEWING`. `VERIFY.md` is committed. No feedback files exist.

### Step 4: Reviewer picks up work normally

- **System does**: `next_action` routes to `team/review` agent with instructions.
- **State after**: Review proceeds as before gates were added.

## End State

The builder's work is gated at the handoff: unverified or out-of-scope builds cannot reach
`REVIEWING`. The reviewer receives work that has passed proof-of-verify and scope checks.

## Success Indicators

- [ ] `STATE.json` shows `current = REVIEWING` after `complete_stage`.
- [ ] `EVENTS.jsonl` has no `GATE_FAILED` events.
- [ ] `feedback/` directory is empty.
- [ ] Commit was made (transition action ran after gates passed).
