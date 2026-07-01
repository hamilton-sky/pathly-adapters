# HAPPY_FLOW.md — studio-backend

## Narrative: First-time Studio user

A developer installs Pathly and opens Studio for the first time.

---

### Step 1 — Studio starts, DB initializes

Studio launches and calls `GET /api/flows` to populate the flow selector.

The HTTP server calls `_svc.get_flows()`, which calls `get_db()`.

`get_db()` sees that `~/.pathly/` does not exist. It creates the directory,
creates `~/.pathly/pathly.db`, runs `_run_migrations()` (12 tables + schema_version),
then runs `_seed_if_empty()`.

Seed completes: 5 flows (explore, test, team, debug, quick-fix), all agent definitions,
and all skill definitions are now in the DB with `project_root = NULL`.

`GET /api/flows` returns a JSON array with 5 entries. The flow selector populates.

---

### Step 2 — Developer opens a project

Developer clicks "Open Project" and selects `/home/dev/my-app`.

Studio sends:
```
POST /project/open
{"project_root": "/home/dev/my-app"}
```

The server scans `/home/dev/my-app/pathly/plans/` for subdirectories.
It finds two existing features: `auth-service` and `payment-api`.

Response: `{"features": ["auth-service", "payment-api"]}`

Studio populates the feature list sidebar.

---

### Step 3 — Developer selects a feature

Developer clicks `auth-service`. Studio sends:
```
GET /api/features/auth-service/events?project_root=/home/dev/my-app
```

`event_service.get_events("/home/dev/my-app", "auth-service")` queries `fsm_events`
filtered by `project_root` and `feature`. Returns `{total: 42, events: [...]}`.

Studio renders the event timeline.

---

### Step 4 — Developer starts a pipeline run

Developer clicks the Start button on the `auth-service` feature.

Studio calls `POST /runner/start` (existing endpoint, unchanged).

`supervisor.py` picks up the run, calls `get_db()`, and begins writing events:
```python
append_event(conn, "/home/dev/my-app", "auth-service", {"event_type": "FSM_START", ...})
```

The live event stream (`GET /events/runner`, SSE, unchanged) pushes updates to Studio.

---

### Step 5 — Agent runs, invocation recorded

The FSM advances to the BUILD stage. An agent PTY is spawned.
When the agent completes, `supervisor.py` calls:
```python
write_agent_invocation(conn, "/home/dev/my-app", "auth-service", {
    "run_id": "run-abc123",
    "stage": "BUILD",
    "agent_role": "builder",
    "started_at": "...",
    "finished_at": "...",
    "tokens_in": 1200,
    "tokens_out": 3400,
    "cost_usd": 0.014,
    "summary": "Implemented AuthService with JWT support",
})
```

---

### Step 6 — Developer inspects the run after it completes

Developer opens the DB Explorer tab. Studio sends:
```
GET /api/features/auth-service/events?project_root=/home/dev/my-app
GET /api/features/auth-service/invocations?project_root=/home/dev/my-app
GET /api/features/auth-service/metrics?project_root=/home/dev/my-app
```

Responses populate the event list, invocation table, and metrics panel.

Metrics example: `{"event_count": 47, "invocation_count": 3, "span_count": 0}`

---

### Step 7 — Developer applies a skill override for the next run

Developer decides to use a custom build skill for this feature.

Studio sends:
```
POST /api/skill-override
{
  "project_root": "/home/dev/my-app",
  "feature": "auth-service",
  "run_id": "run-def456",
  "stage": "BUILD",
  "skill_name": "pathly-build-strict"
}
```

The override is written to `skill_overrides`. On the next run, the FSM calls
`read_skill_override(conn, "/home/dev/my-app", "auth-service", "BUILD")` before
selecting the skill, and receives `pathly-build-strict`.

---

### Summary

Every interaction in the happy flow uses the centralized `~/.pathly/pathly.db`.
No per-feature SQLite files are created or read. The developer never sees
the DB — they interact only through Studio's UI, which speaks HTTP to the server.
