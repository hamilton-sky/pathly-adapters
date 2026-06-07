# USER_STORIES.md — fsm-db-migration

## Story Map

| Story | Title | Conv |
|---|---|---|
| S1.1 | fsm_ops reads state from DB | Conv 1 |
| S1.2 | fsm_ops writes state to DB | Conv 1 |
| S1.3 | STATE.json becomes optional export | Conv 1 |
| S2.1 | New POST /runner/event endpoint | Conv 2 |
| S2.2 | log-agent-done skill POSTs to server | Conv 2 |
| S2.3 | EVENTS.jsonl written as backup only | Conv 2 |
| S3.1 | supervisor reads AGENT_DONE from DB | Conv 3 |
| S3.2 | supervisor reads FSM state from DB | Conv 3 |
| S3.3 | No file reads after PTY exits | Conv 3 |

---

## S1.1 + S1.2 — fsm_ops reads/writes DB

**As a** pipeline operator,
**I want** `fsm_ops.py` to read and write FSM state via `db.read_state()` / `db.write_state()`,
**So that** STATE.json is no longer the source of truth for the state machine.

### Acceptance Criteria

- AC1.1: `get_current_state(project_root, feature)` reads from `fsm_state` table, not STATE.json.
- AC1.2: `transition_state(project_root, feature, new_state)` writes to `fsm_state` table.
- AC1.3: STATE.json is written as a side-effect export (human-readable backup), not primary store.
- AC1.4: If `fsm_state` table has no row, falls back to STATE.json for migration compatibility.
- AC1.5: `python -m pytest tests/ -q` passes at baseline count.

---

## S2.1 + S2.2 + S2.3 — AGENT_DONE via HTTP

**As a** pipeline agent,
**I want** AGENT_DONE events to be POSTed to the FSM server,
**So that** the DB receives events directly without file intermediaries.

### Acceptance Criteria

- AC2.1: `POST /runner/event` endpoint accepts `{type, feature, project_root, payload}` and writes to `fsm_events` table.
- AC2.2: `POST /runner/event` returns HTTP 200 `{ok: true}` on success.
- AC2.3: `pathly-log-agent-done` skill POSTs to `/runner/event` when server is reachable.
- AC2.4: `pathly-log-agent-done` falls back to EVENTS.jsonl file append when server is unreachable (offline/codex mode).
- AC2.5: EVENTS.jsonl is still written as a backup (dual-write) so existing tooling is not broken.

---

## S3.1 + S3.2 + S3.3 — supervisor reads DB only

**As a** supervisor process,
**I want** to read AGENT_DONE summary and FSM state from the DB after a PTY exits,
**So that** the file read after PTY exit is eliminated.

### Acceptance Criteria

- AC3.1: After PTY exits, supervisor queries `fsm_events` for the latest AGENT_DONE row instead of reading EVENTS.jsonl.
- AC3.2: supervisor reads current FSM state from `fsm_state` table, not STATE.json.
- AC3.3: No `open(EVENTS.jsonl)` or `open(STATE.json)` calls remain in supervisor's post-PTY path.
- AC3.4: `python -m pytest tests/ -q` passes at baseline count.
- AC3.5: A full pipeline run (start → one stage → terminal/result) writes and reads exclusively from DB.
