# ARCHITECTURE_PROPOSAL.md — studio-backend

## Problem

The current Pathly database design creates one SQLite file per feature:

```
pathly/plans/auth-service/pathly.db
pathly/plans/payment-api/pathly.db
pathly/plans/user-profile/pathly.db
```

This was sufficient for the CLI workflow where each feature runs in isolation.

Studio requires cross-feature queries:
- "Show me all features in this project" — needs to scan N databases
- "Which features had the most agent invocations this week?" — needs a JOIN across features
- "Show me all skill overrides across all runs" — needs to aggregate data

With per-feature DBs, the server would need to discover, open, and fan-out queries
across an unbounded number of SQLite connections. This creates connection management
complexity, makes aggregation expensive, and is difficult to keep consistent under
concurrent writes.

---

## Solution

Centralize to one DB at `~/.pathly/pathly.db`, with `project_root` as an isolation column.

```
~/.pathly/pathly.db
  ├── fsm_events        (project_root, feature, ...)
  ├── fsm_state         (project_root, feature, ...)
  ├── runner_state      (project_root, feature, ...)
  ├── flow_definitions  (project_root nullable, name, ...)
  ├── agent_invocations (project_root, feature, ...)
  ├── skill_definitions (project_root nullable, ...)
  └── ...
```

Cross-feature aggregation becomes a single SQL query. Per-feature isolation is
achieved via WHERE clauses. The server holds one connection (or one pool), never
more than one WAL.

---

## Layer Architecture

```
pathly_data/ (source of truth for skill/agent/flow definitions)
     |
     |  _seed_if_empty() — reads YAML/MD files, INSERTs with project_root=NULL
     v
db.py (raw SQL helpers — all queries, no business logic)
     |  get_db()         — open/create ~/.pathly/pathly.db, run migrations
     |  append_event()   — INSERT into fsm_events
     |  read_events()    — SELECT from fsm_events
     |  upsert_*()       — catalog management
     |  ...18 helpers total
     v
services/ (business logic — shaped queries, no HTTP concerns)
     |  flow_service.py     — flow CRUD, shape for API
     |  event_service.py    — event query + count
     |  agent_service.py    — invocations + agent catalog
     |  span_service.py     — OTEL span query
     |  artifact_service.py — stage artifact query
     |  skill_catalog.py    — skill resolution (local-first)
     v
http_server.py (routing — parse request, call service, jsonify)
     |  @app.route('/api/flows')
     |  @app.route('/api/skills')
     |  @app.route('/api/features/<feature>/events')
     |  ...11 new routes
     v
Studio frontend (HTTP client — fetch, display)
```

---

## Key Decisions

### Decision 1: One DB at `~/.pathly/pathly.db`

Studio needs cross-project, cross-feature queries in a single list view.
A per-feature DB would require scanning and opening one SQLite file per feature
per project. The centralized DB eliminates this — all features from all projects
live in the same file, queryable with a single connection.

The trade-off: data from different projects shares one file. `project_root` as a
column provides isolation. There is no per-project data confidentiality requirement
in this use case (all projects are local, owned by the same user).

### Decision 2: `project_root` as a column, not a separate DB per project

Splitting by project (one DB per project root) would reduce fan-out from N features
to M projects, but would still require multi-DB management. The column approach
means one connection, one WAL, one migration path. SQLite handles the throughput
easily for the expected load (one developer, one machine).

### Decision 3: Services as thin query wrappers

Each service module calls `get_db()` directly and returns shaped Python structures
(dicts and lists). No Flask imports anywhere in services/. This makes services
testable with plain pytest — no Flask test client, no HTTP overhead. HTTP routes
become a thin translation layer: parse request args → call service → jsonify.

This separation also makes it easier to reuse service logic outside HTTP contexts
(e.g., a future CLI reporting tool could import event_service directly).

### Decision 4: No Flask blueprints

`http_server.py` already uses module-level `@app.route` decorators without a
factory or blueprints. Introducing blueprints would require refactoring all
existing routes (SSE endpoints, runner endpoints, FSM endpoints) and is out of
scope. New `/api/*` routes follow the existing pattern to minimize diff surface
and avoid breaking changes.

---

## What this does NOT change

- The pipeline runtime path is unchanged. FSM, supervisor, eventlog still work the
  same way — only their DB calls are updated (Conv 2).
- The SSE live-stream endpoint (`/events/runner`) is not modified.
- The existing `/next_action`, `/runner/start`, `/runner/stop` routes are not modified.
- OTEL export (`otel_export.py`) behavior is unchanged — only the DB open path differs.
- The Studio frontend is not part of this feature. These routes are backend-only.
