# FSM HTTP Server API Reference

The FSM HTTP server (`pathly-fsm-http`) exposes a REST API on `http://127.0.0.1:8765` by default.

All request bodies must be `application/json`. All responses are JSON unless otherwise noted.

Rate limit: 120 requests per 60-second window per IP. Exceeding it returns `429`.

## Authentication

All `POST` routes require the `X-Pathly-Secret` header. The secret is a 64-char hex token
auto-generated on first run and stored at `~/.pathly/server_secret.txt`. Studio reads and
injects it automatically.

```bash
SECRET=$(cat ~/.pathly/server_secret.txt)
curl -X POST http://127.0.0.1:8765/next_action \
  -H "X-Pathly-Secret: $SECRET" \
  -H "Content-Type: application/json" \
  -d '...'
```

`GET /events/*` endpoints are exempt — the browser `EventSource` API cannot send custom headers,
so SSE streams are secured by loopback-only binding (`127.0.0.1`).

Omitting `X-Pathly-Secret` on a POST returns `401 Unauthorized`.

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

## GET /events/stream

Server-Sent Events (SSE) stream. Tails `pathly/plans/<topic>/EVENTS.jsonl` under the given project root and pushes new lines to connected clients in real time. Used by the Pathly Studio UI.

**Query parameters**

| Parameter | Required | Description |
|---|---|---|
| `topic` | yes | Feature or topic name (must match a plans sub-directory) |
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
