---
name: Happy Flow
---
# fsm-sqlite — Happy Flow

## Overview

A developer runs a full Pathly pipeline (PLAN → BUILD → REVIEW → DONE) for a new feature.
The FSM orchestrator, supervisor, and Studio SSE stream all operate through the new SQLite
layer. No `.json` or `.jsonl` files are written; `pathly.db` is the single source of truth
for all control-plane state.

## Step-by-Step Happy Flow

### Step 1: Feature plan created
- **User does**: runs `/pathly plan my-feature`
- **System does**: creates `pathly/plans/my-feature/` with markdown plan files on disk
- **State after**: no `pathly.db` yet (only plan docs exist); orchestrator not yet started

### Step 2: Runner starts
- **User does**: clicks Start in Studio for `my-feature`
- **System does**: `supervisor.py` calls `db.get_db(feature_dir)` → creates `pathly.db` with WAL; calls `db.write_runner_state()` with `{status: 'running', current_state: 'PLANNING', ...}`
- **State after**: `pathly/plans/my-feature/pathly.db` exists; `runner_state` table has one row

### Step 3: FSM transitions to BUILD
- **System does**: FSM engine calls `eventlog.write_state()` → `db.write_state()` upserts `fsm_state` row with `{current: 'BUILDING', convs_total: 3, ...}`; calls `eventlog.append_event()` → `db.append_event()` inserts `{type: 'STATE_TRANSITION', to: 'BUILDING', seq: 1}`
- **State after**: `fsm_state` row updated; `fsm_events` has 1 row with seq=1

### Step 4: Builder agent runs
- **System does**: supervisor spawns PTY with builder prompt; builder agent writes plan docs via Write tool; FSM server receives AGENT_DONE from SSE watcher; `eventlog.append_event()` → inserts `{type: 'AGENT_DONE', agent: 'builder', conversation: 1, summary: '...', cost_usd: 0.42, seq: 2}`
- **State after**: `fsm_events` has 2 rows; `fsm_state.convs_done = 1`

### Step 5: Studio SSE stream delivers events
- **User does**: Studio is open, watching the `/events` SSE stream
- **System does**: `http_server._tail_events()` polls `SELECT payload FROM fsm_events WHERE feature=? AND seq > :last_seq`; yields each event with `id: {seq}`; Studio renders AGENT_DONE card
- **State after**: Studio shows build progress with live event feed; no file-seek involved

### Step 6: Runner state updated in real time
- **System does**: after AGENT_DONE detected, `supervisor._write_mirror()` calls `db.write_runner_state()` with `{cost_usd_so_far: 0.42, iterations: 1}`; Studio `/status` endpoint reads from SQLite — no partial-JSON risk
- **State after**: Studio shows updated cost and progress bar

### Step 7: Pipeline completes
- **System does**: FSM transitions to DONE; final `STATE_TRANSITION` event appended; `fsm_state.current = 'DONE'`; `runner_state.status = 'done'`; Studio SSE receives the terminal event
- **State after**: `pathly.db` contains the complete history: all events, final state, and runner summary

### Step 8: Server restart (crash recovery)
- **System does**: on next server start, `supervisor.recover_stale_mirrors()` calls `db.mark_stale_runners()` → finds any `status='running'` rows → sets to `'error'`; no corrupt JSON file to parse
- **State after**: stale run correctly marked; Studio shows error badge without data loss

## End State

The feature's `pathly.db` contains the full pipeline history: all FSM state transitions,
all AGENT_DONE records with cost and token data, and the final runner state. Developers
can query it directly with any SQLite viewer. Legacy `.json` and `.jsonl` files were
never written for this run.

## Success Indicators
- [ ] `pathly.db` created on first run; no `.json` or `.jsonl` files written by Python layer
- [ ] Studio SSE stream delivers events by seq number; reconnect resumes without gaps
- [ ] Server restart marks stale runner correctly without reading a partial JSON file
- [ ] `pytest tests/ -q` passes; no regressions in existing test suite
