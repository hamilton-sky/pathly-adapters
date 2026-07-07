# FSM HTTP Server API Reference

The FSM HTTP server (`pathly-fsm-http`) exposes a REST API on `http://127.0.0.1:8765` by default.

All request bodies must be `application/json`. All responses are JSON unless otherwise noted.

Rate limit: 120 requests per 60-second window per IP. Loopback callers (`127.0.0.1`) are exempt
from rate limiting entirely.

## Authentication

Requests require the `X-Pathly-Secret` header (or a `token` query parameter). The secret is a
64-char hex token auto-generated on first run and stored at `~/.pathly/server_secret.txt`.
Studio reads and injects it automatically.

```bash
SECRET=$(cat ~/.pathly/server_secret.txt)
curl -X POST http://127.0.0.1:8765/next_action \
  -H "X-Pathly-Secret: $SECRET" \
  -H "Content-Type: application/json" \
  -d '...'
```

The secret's real job is blocking browser-origin CSRF, not gating local agents: it is only
enforced for **browser-origin requests** (any request carrying an `Origin` header) or
**non-loopback callers**. A local `curl`/CLI call from `127.0.0.1` with no `Origin` header — the
normal case for a Pathly agent calling its own FSM server — is let through without the header.
`GET /health` and `GET /events/*` are always exempt (SSE streams are additionally secured by
loopback-only binding).

Omitting the secret when it is required returns `401 Unauthorized` — body `{"error": "unauthorized"}`.

---

## GET /health

Returns server liveness status.

**Request:** no body, no query parameters.

**Response — 200**
```json
{
  "status": "ok",
  "server": "pathly-fsm-http"
}
```

**Example**
```bash
curl http://localhost:8765/health
```

---

## POST /next_action

Asks the FSM what the current agent should do next for a given feature. Returns the FSM's action descriptor without advancing state.

**Required fields**

| Field | Type | Description |
|---|---|---|
| `flow` | string | Flow name (e.g. `"team"`, `"debug"`, `"explore"`) |
| `topic` | string | Feature or topic name (matches the plans sub-directory) |
| `project_root` | string | Absolute path to the project root |

All three fields must be non-empty strings.

**Response — 200**

The response shape is determined by the FSM `next_action` implementation. It includes at minimum the action descriptor the FSM computed.

**Error responses**

| Status | Condition |
|---|---|
| `400` | Missing JSON body |
| `400` | One or more required fields absent — body: `{"error": "Missing fields: <names>"}` |
| `400` | A required field is not a non-empty string |
| `429` | Rate limit exceeded |
| `500` | Unexpected FSM error — body includes `"error"` and `"type"` keys |

**Example**
```bash
SECRET=$(cat ~/.pathly/server_secret.txt)
curl -s -X POST http://localhost:8765/next_action \
  -H "X-Pathly-Secret: $SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "flow": "team",
    "topic": "my-feature",
    "project_root": "/home/user/myproject"
  }'
```

---

## POST /complete_stage

Advances the FSM to the next stage for a feature. Optionally resolves a decision branch or deletes resolved feedback files.

**Required fields**

| Field | Type | Description |
|---|---|---|
| `flow` | string | Flow name (e.g. `"team"`, `"debug"`, `"explore"`) |
| `topic` | string | Feature or topic name |
| `project_root` | string | Absolute path to the project root |

**Optional fields**

| Field | Type | Description |
|---|---|---|
| `decision` | string | Decision key for decide-blocks in the flow YAML |
| `resolved_files` | array of strings | Paths to feedback files to delete as part of the transition |

**Response — 200**

The response shape is determined by the FSM `complete_stage` implementation. It reflects the new state after the transition.

**Error responses**

| Status | Condition |
|---|---|
| `400` | Missing JSON body |
| `400` | One or more required fields absent — body: `{"error": "Missing fields: <names>"}` |
| `400` | A required field is not a non-empty string |
| `429` | Rate limit exceeded |
| `500` | Unexpected FSM error — body includes `"error"` and `"type"` keys |

**Example**
```bash
SECRET=$(cat ~/.pathly/server_secret.txt)
curl -s -X POST http://localhost:8765/complete_stage \
  -H "X-Pathly-Secret: $SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "flow": "team",
    "topic": "my-feature",
    "project_root": "/home/user/myproject"
  }'
```

With an optional decision:
```bash
curl -s -X POST http://localhost:8765/complete_stage \
  -H "X-Pathly-Secret: $SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "flow": "team",
    "topic": "my-feature",
    "project_root": "/home/user/myproject",
    "decision": "approved"
  }'
```

---

## POST /record_activity

Appends an activity record to `~/.pathly/activity.jsonl`. Used by agents to report token usage and work summaries for telemetry.

**Required fields**

| Field | Type | Description |
|---|---|---|
| `agent` | string | Agent name (e.g. `"builder"`, `"reviewer"`) |
| `feature` | string | Feature or topic the agent worked on |
| `summary` | string | One-line description of what the agent did |

**Optional fields**

| Field | Type | Default | Description |
|---|---|---|---|
| `input_tokens` | number | `0` | Input tokens consumed (must be non-negative) |
| `output_tokens` | number | `0` | Output tokens produced (must be non-negative) |

**Response — 200**
```json
{
  "status": "recorded"
}
```

**Error responses**

| Status | Condition |
|---|---|
| `400` | Missing JSON body |
| `400` | One or more required fields absent — body: `{"error": "Missing fields: <names>"}` |
| `400` | A required string field is empty |
| `400` | `input_tokens` or `output_tokens` is negative or not a number |
| `429` | Rate limit exceeded |
| `500` | Unexpected error — body includes `"error"` and `"type"` keys |

**Example**
```bash
SECRET=$(cat ~/.pathly/server_secret.txt)
curl -s -X POST http://localhost:8765/record_activity \
  -H "X-Pathly-Secret: $SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "builder",
    "feature": "my-feature",
    "summary": "implemented login form validation",
    "input_tokens": 12400,
    "output_tokens": 3200
  }'
```

---

## Comms board — goals, decompose, and task-run endpoints

These endpoints back the Board -> Goals -> Task-DAG model (see the root `CLAUDE.md` "Comms
board" section). Full route inventory for the rest of `/comms/*` lives in
[src/pathly_orchestrator/CLAUDE.md](../src/pathly_orchestrator/CLAUDE.md#comms-board-endpoints-multi-agent-message-board).

## GET /comms/goals

Lists goals on a `(board, scope)`, each enriched with its task-DAG rollup — the read-model
partner to `POST /comms/goals/run|stop|decompose`. Saves callers from fetching goals and tasks
separately and joining them client-side.

**Query parameters**

| Parameter | Required | Description |
|---|---|---|
| `feature` | yes | Feature or topic name |
| `board` | no | `"feature"` (default), `"project"`, or `"global"` |
| `scope` | no | Defaults to `feature` |

**Response — 200**
```json
[
  {
    "id": "msg-abc123",
    "slug": "add-login-form",
    "text": "Add a login form to the app",
    "executor": "loop",
    "from_agent": "planner",
    "ts": "2026-07-01T12:00:00Z",
    "tasks": {
      "total": 5,
      "done": 2,
      "in_progress": 1,
      "pending": 2,
      "blocked": 0,
      "failed": 0,
      "ready": 1
    }
  }
]
```

**Error responses**

| Status | Condition |
|---|---|
| `400` | `feature` query parameter missing |
| `500` | Unexpected error — body includes `"error"` and `"type"` keys |

**Example**
```bash
SECRET=$(cat ~/.pathly/server_secret.txt)
curl -s "http://localhost:8765/comms/goals?feature=my-feature" \
  -H "X-Pathly-Secret: $SECRET"
```

---

## POST /comms/project/decompose

Decomposes a big spec dropped on the PROJECT board into 2-5 sibling FEATURE cards, each
scaffolded under `pathly/features/<slug>/`.

**Required fields**

| Field | Type | Description |
|---|---|---|
| `project_root` | string | Absolute path to the project root |

**Optional fields**

| Field | Type | Default | Description |
|---|---|---|---|
| `rigor` | string | `"light"` | `"light"` \| `"full"` -> single-agent board run (`planning/project-decompose`); `"consultation"` -> the `project-consultation` FSM flow |
| `project` | string | normalized `project_root` | Overrides the project-board scope key |
| `adapter` | string | `"claude"` | CLI engine to spawn |
| `model` | string | `"claude-sonnet-4-6"` | Model for the spawned agent |

**Response — 200**

Shape depends on `rigor`. `light`/`full` return the `start_board_run` result (`{ok, run_id, ...}`)
plus `rigor` and `project`. `consultation` returns `{"ok": true, "run_id": "...", "rigor":
"consultation", "project": "...", "status": "started"}`.

**Error responses**

| Status | Condition |
|---|---|
| `400` | Missing JSON body |
| `400` | `rigor` not one of `light`/`full`/`consultation` — body includes `"reason": "invalid_rigor"` |
| `409` | Board already busy (a run holds the lock) — body includes `"reason": "board_busy"` |
| `500` | Unexpected error — body includes `"error"` and `"type"` keys |

**Example**
```bash
SECRET=$(cat ~/.pathly/server_secret.txt)
curl -s -X POST http://localhost:8765/comms/project/decompose \
  -H "X-Pathly-Secret: $SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "project_root": "/home/user/myproject",
    "rigor": "light"
  }'
```

---

## POST /comms/features/decompose

Decomposes a feature into a task DAG or a full plan.

**Required fields**

| Field | Type | Description |
|---|---|---|
| `feature` | string | Feature name (board scope) |
| `project_root` | string | Absolute path to the project root |

**Optional fields**

| Field | Type | Default | Description |
|---|---|---|---|
| `rigor` | string | `"light"` | `"light"` -> `planning/feature-decompose`; `"full"` -> `planning/plan`; `"consultation"` -> the `feature-consultation` FSM flow |
| `adapter` | string | `"claude"` | CLI engine to spawn |
| `model` | string | `"claude-sonnet-4-6"` | Model for the spawned agent |

**Response — 200**

Same shape as `/comms/project/decompose`, with `feature` in place of `project`.

**Error responses**

| Status | Condition |
|---|---|
| `400` | Missing JSON body |
| `400` | `feature` empty |
| `400` | `rigor` not one of `light`/`full`/`consultation` — body includes `"reason": "invalid_rigor"` |
| `409` | Board already busy — body includes `"reason": "board_busy"` |
| `500` | Unexpected error — body includes `"error"` and `"type"` keys |

**Example**
```bash
SECRET=$(cat ~/.pathly/server_secret.txt)
curl -s -X POST http://localhost:8765/comms/features/decompose \
  -H "X-Pathly-Secret: $SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "my-feature",
    "project_root": "/home/user/myproject",
    "rigor": "light"
  }'
```

---

## POST /comms/tasks/run

Runs ONE task headlessly: claims it, spawns a builder on its self-contained prompt (the task's
`text`), and marks it complete on success. Ad-hoc per-task execution from the Goals & Tasks
view — independent of the goal executor's `single`/`loop`/`team` strategies.

**Required fields**

| Field | Type | Description |
|---|---|---|
| `message_id` | string | ID of the `type=task` message to run |

**Optional fields**

| Field | Type | Default | Description |
|---|---|---|---|
| `adapter` | string | `"claude"` | CLI engine to spawn |
| `model` | string | `"claude-sonnet-4-6"` if `adapter="claude"`, else engine default | Model for the spawned agent |
| `project_root` | string | `""` | Absolute path to the project root |
| `progress` | string | `""` | Progress-reporting style override |

**Response — 200**
```json
{
  "ok": true,
  "run_id": "run-abc123",
  "message_id": "msg-abc123"
}
```

**Error responses**

| Status | Condition |
|---|---|
| `400` | `message_id` missing/empty, or the message is not `type=task` (`"reason": "not_task"`) |
| `404` | No message found for `message_id` (`"reason": "not_found"`) |
| `409` | Task already done (`"reason": "already_done"`), already running (`"reason": "already_running"`), or the claim failed (`"reason": "busy"`) |
| `400` / `409` | Spawn refused — `"reason": "board_busy"` (409) or `"spawn_failed"` (400) |
| `500` | Unexpected error — body includes `"error"` and `"type"` keys |

**Example**
```bash
SECRET=$(cat ~/.pathly/server_secret.txt)
curl -s -X POST http://localhost:8765/comms/tasks/run \
  -H "X-Pathly-Secret: $SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "message_id": "msg-abc123",
    "project_root": "/home/user/myproject"
  }'
```

---

## POST /comms/tasks/stop

Stops a single-task run started via `POST /comms/tasks/run`: kills its board run (if any) and
reverts the task from `in_progress` back to `pending`.

**Required fields**

| Field | Type | Description |
|---|---|---|
| `message_id` | string | ID of the running task message |

**Response — 200**
```json
{
  "ok": true,
  "stopped": true
}
```

**Error responses**

| Status | Condition |
|---|---|
| `400` | `message_id` missing/empty |
| `404` | No message found for `message_id` (`"reason": "not_found"`) |
| `500` | Unexpected error — body includes `"error"` and `"type"` keys |

**Example**
```bash
SECRET=$(cat ~/.pathly/server_secret.txt)
curl -s -X POST http://localhost:8765/comms/tasks/stop \
  -H "X-Pathly-Secret: $SECRET" \
  -H "Content-Type: application/json" \
  -d '{"message_id": "msg-abc123"}'
```

---

## GET /comms/goals/refs-coverage

Reports per-goal `context_refs` coverage — the fraction of a goal's tasks that carry at least
one curated context ref. A low `coverage_pct` means many tasks will fall back to weaker
auto-derived/semantic context at dispatch time; this makes that gap visible to a human before
running the goal.

**Query parameters**

| Parameter | Required | Description |
|---|---|---|
| `goal_id` | yes | ID of the `type=goal` message |

**Response — 200**
```json
{
  "goal_id": "msg-abc123",
  "total": 5,
  "with_refs": 3,
  "without_refs": 2,
  "coverage_pct": 60.0
}
```

`coverage_pct` is `null` when the goal has no tasks yet.

**Error responses**

| Status | Condition |
|---|---|
| `400` | `goal_id` query parameter missing |
| `500` | Unexpected error — body includes `"error"` and `"type"` keys |

**Example**
```bash
SECRET=$(cat ~/.pathly/server_secret.txt)
curl -s "http://localhost:8765/comms/goals/refs-coverage?goal_id=msg-abc123" \
  -H "X-Pathly-Secret: $SECRET"
```

---

## POST /code/query

Code-intelligence proxy: an agent asks Pathly for code structure over HTTP, and Pathly proxies
the query to the shared `codebase-memory-mcp` backend. Never returns a 500 on a backend
miss — a missing/disabled backend or a malformed backend response degrades to a safe-null
envelope (`"result": null`) so the caller falls back to Grep instead of crashing. Results are
cached by `(op, target, content-hash)` so a repeated query for an unchanged file is served
without re-querying the backend. Access is gated by the caller's `role` (an excluded role, e.g.
`web-researcher`/`human`, or an op outside the role's tier gets a safe-null with a `"reason"`,
not an error).

**Required fields**

| Field | Type | Description |
|---|---|---|
| `op` | string | `"impact"` \| `"callers"` \| `"chain"` \| `"symbol"` \| `"context"` \| `"pattern"` |
| `target` | string | File path or symbol name to query |

**Optional fields**

| Field | Type | Default | Description |
|---|---|---|---|
| `role` | string | `""` | Calling agent's role — gates which ops are permitted |
| `scope` | string (or `feature`) | `""` | Feature/board scope, used for board logging |
| `project_root` | string | `""` | Absolute path to the project root |
| `budget` | number | `1500` | Soft character budget for the returned block |

**Response — 200**
```json
{
  "ok": true,
  "op": "callers",
  "target": "src/pathly_orchestrator/runner/invoke.py",
  "result": "...",
  "backend": "cli",
  "cached": false
}
```

`result` is `null` when the backend is off, disabled for the role, or has nothing for the query.
When denied by the role gate, the response also includes `"reason"` (`"disabled"` or
`"op-not-permitted"`) and echoes `"role"`.

**Error responses**

| Status | Condition |
|---|---|
| `400` | Missing/invalid JSON body |
| `400` | `op` or `target` missing/empty |
| `500` | Never returned — an internal error still responds `200` with `{"ok": true, "result": null, "backend": "none"}` |

**Example**
```bash
SECRET=$(cat ~/.pathly/server_secret.txt)
curl -s -X POST http://localhost:8765/code/query \
  -H "X-Pathly-Secret: $SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "op": "callers",
    "target": "src/pathly_orchestrator/runner/invoke.py",
    "role": "builder"
  }'
```

---

## GET /events/stream

Server-Sent Events (SSE) stream. Tails `<feature-home>/EVENTS.jsonl` under the given project root — the feature home resolves to `pathly/features/<topic>/` first, falling back to the legacy `pathly/plans/<topic>/` — and pushes new lines to connected clients in real time. Used by the Pathly Studio UI.

**Query parameters**

| Parameter | Required | Description |
|---|---|---|
| `topic` | yes | Feature or topic name |
| `project_root` | yes | Absolute path to the project root |

**Response — 200**

Content-Type: `text/event-stream`

The server sends one SSE message per EVENTS.jsonl line appended. Each message has the form:

```
data: <json-line>\n\n
```

On connect, the server immediately sends a connected notification:

```
data: {"type":"connected"}
```

While idle the server sends keepalive comments every ~25 seconds to prevent proxy timeouts:

```
: keepalive
```

**Response headers**

| Header | Value |
|---|---|
| `Cache-Control` | `no-cache` |
| `X-Accel-Buffering` | `no` |
| `Access-Control-Allow-Origin` | Value of `PATHLY_CORS_ORIGIN` env var, or `null` if unset |

**Error responses**

| Status | Condition |
|---|---|
| `400` | `topic` or `project_root` query parameter missing |
| `400` | `project_root` resolves outside its own path (path traversal guard) |
| `429` | Rate limit exceeded |
| `503` | SSE streaming disabled via feature flag |

**Example**
```bash
curl -N "http://localhost:8765/events/stream?topic=my-feature&project_root=/home/user/myproject"
```

Connecting from a browser (JavaScript):
```js
const source = new EventSource(
  'http://localhost:8765/events/stream?topic=my-feature&project_root=/home/user/myproject'
);
source.onmessage = (e) => console.log(JSON.parse(e.data));
```
