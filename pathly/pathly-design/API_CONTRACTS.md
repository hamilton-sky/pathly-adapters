# Pathly — API Contracts

All endpoints on `http://127.0.0.1:8765`.
All responses are JSON. All requests with a body use `Content-Type: application/json`.
`project_root` is always the absolute path to the selected project folder.

---

## Features

### `GET /api/features?project_root=<path>`
Returns all features for the given project, with summary stats.

**Response:**
```json
[
  {
    "project_root": "C:/my-project",
    "feature": "login-flow",
    "state": "REVIEWING",
    "convs_done": 2,
    "convs_total": 3,
    "event_count": 23,
    "agent_done_count": 4,
    "total_tokens": 142300,
    "total_cost_usd": 1.92,
    "last_event_ts": "2026-06-07T11:14:02Z"
  }
]
```

If `project_root` is omitted → returns all features across all projects (global dashboard).

---

### `POST /features/create`
Create a new feature.

**Request:**
```json
{
  "project_root": "C:/my-project",
  "feature": "login-flow",
  "flow": "team"
}
```

**Response:**
```json
{ "ok": true, "feature": "login-flow", "state": "STORM" }
```

---

### `GET /api/features/<feature>/events?project_root=<path>&limit=100&offset=0&type=AGENT_DONE`
Paginated event log for a feature. `type` is optional filter.

**Response:**
```json
{
  "total": 35,
  "events": [
    {
      "seq": 35,
      "feature": "login-flow",
      "type": "AGENT_DONE",
      "ts": "2026-06-07T10:08:07Z",
      "payload": {
        "agent": "reviewer",
        "result": "PASS",
        "total_tokens": 33012,
        "cost_usd": 0.74,
        "wall_seconds": 49.8,
        "tool_uses": 5,
        "summary": "Approved with note: coalesce NULL ts before ordering."
      }
    }
  ]
}
```

---

### `GET /api/features/<feature>/invocations?project_root=<path>&stage=BUILD`
Agent invocations for a feature. `stage` is optional filter.

**Response:**
```json
[
  {
    "id": 12,
    "feature": "login-flow",
    "run_id": "run_abc123",
    "stage": "BUILD",
    "conv_id": "bld-01",
    "agent_role": "builder",
    "model": "claude-sonnet-4-6",
    "input_tokens": 41200,
    "output_tokens": 7010,
    "tool_uses": 14,
    "cost_usd": 0.39,
    "wall_seconds": 86.4,
    "result": "PASS",
    "summary": "Implemented auth module. All files written.",
    "trace_id": "9f3a2b1c4d5e6f70",
    "span_id": "a1b2c3d4",
    "started_at": "2026-06-07T09:49:00Z",
    "finished_at": "2026-06-07T10:10:26Z"
  }
]
```

---

### `GET /api/features/<feature>/metrics?project_root=<path>`
Aggregated cost and token data for charts.

**Response:**
```json
{
  "total_cost_usd": 3.64,
  "total_tokens": 290749,
  "by_stage": [
    { "stage": "BUILD",  "cost_usd": 1.14, "tokens": 141215, "count": 3 },
    { "stage": "REVIEW", "cost_usd": 2.03, "tokens": 90554,  "count": 3 },
    { "stage": "TEST",   "cost_usd": 0.47, "tokens": 58970,  "count": 2 }
  ],
  "by_run": [
    { "run_id": "run_abc123", "cost_usd": 3.64, "started_at": "2026-06-07T09:02:11Z" }
  ],
  "cost_over_time": [
    { "ts": "2026-06-07T09:49:28Z", "cumulative_cost": 0.39 },
    { "ts": "2026-06-07T10:08:07Z", "cumulative_cost": 1.13 }
  ]
}
```

---

### `GET /api/features/<feature>/artifacts?project_root=<path>&type=REVIEW_FAILURES`
Stage artifacts mirrored from .md files. `type` is optional filter.

**Response:**
```json
[
  {
    "id": 5,
    "stage": "REVIEW",
    "artifact_type": "REVIEW_FAILURES",
    "content": "# Review Failures\n\n## Missing error handling...",
    "file_path": "C:/my-project/pathly/plans/login-flow/feedback/REVIEW_FAILURES.md",
    "created_at": "2026-06-07T10:08:07Z"
  }
]
```

---

## Runner control

### `POST /runner/start`
**Request:**
```json
{ "project_root": "C:/my-project", "feature": "login-flow" }
```
**Response:**
```json
{ "ok": true, "run_id": "run_abc123" }
```

### `POST /runner/pause`
**Request:** `{ "project_root": "...", "feature": "..." }`
**Response:** `{ "ok": true }`

### `POST /runner/resume`
**Request:** `{ "project_root": "...", "feature": "..." }`
**Response:** `{ "ok": true }`

### `POST /runner/abort`
**Request:** `{ "project_root": "...", "feature": "..." }`
**Response:** `{ "ok": true }`

---

## Flows (global — no project_root needed)

### `GET /api/flows`
**Response:**
```json
[
  { "id": "team",     "name": "Team",     "rigor": "standard", "description": "Full pipeline", "version": 1 },
  { "id": "standard", "name": "Standard", "rigor": "standard", "description": "Build + review + test", "version": 1 },
  { "id": "nano",     "name": "Nano",     "rigor": "nano",     "description": "Single conversation, no review", "version": 1 }
]
```

### `GET /api/flows/<id>`
Returns flow with full nodes and edges.

**Response:**
```json
{
  "id": "team",
  "name": "Team",
  "rigor": "standard",
  "description": "Full pipeline with review and test loops",
  "version": 1,
  "nodes": [
    { "id": 1, "name": "BUILD",  "agent_role": "builder",  "skill_name": "pathly-build.md",   "adapter": "claude", "pos_x": 100, "pos_y": 200 },
    { "id": 2, "name": "REVIEW", "agent_role": "reviewer", "skill_name": "pathly-review.md",  "adapter": "claude", "pos_x": 300, "pos_y": 200 },
    { "id": 3, "name": "TEST",   "agent_role": "tester",   "skill_name": "pathly-test.md",    "adapter": "claude", "pos_x": 500, "pos_y": 200 },
    { "id": 4, "name": "RETRO",  "agent_role": "planner",  "skill_name": "pathly-retro.md",   "adapter": "claude", "pos_x": 700, "pos_y": 200 }
  ],
  "edges": [
    { "id": 1, "from_node": "BUILD",  "to_node": "REVIEW", "condition": "PASS",  "label": "PASS" },
    { "id": 2, "from_node": "BUILD",  "to_node": "BUILD",  "condition": "FAIL",  "label": "retry" },
    { "id": 3, "from_node": "REVIEW", "to_node": "TEST",   "condition": "PASS",  "label": "PASS" },
    { "id": 4, "from_node": "REVIEW", "to_node": "BUILD",  "condition": "FAIL",  "label": "rework" },
    { "id": 5, "from_node": "TEST",   "to_node": "RETRO",  "condition": "PASS",  "label": "PASS" },
    { "id": 6, "from_node": "TEST",   "to_node": "BUILD",  "condition": "FAIL",  "label": "rework" },
    { "id": 7, "from_node": "RETRO",  "to_node": null,     "condition": null,    "label": "DONE" }
  ]
}
```

### `POST /api/flows`
Save (create or update) a flow. Replaces all nodes and edges for that flow_id.

**Request:**
```json
{
  "id": "team",
  "name": "Team",
  "description": "Full pipeline",
  "rigor": "standard",
  "nodes": [ ... ],
  "edges": [ ... ]
}
```
**Response:** `{ "ok": true, "version": 2 }`

---

## Skills

### `GET /api/skills?project_root=<path>`
Returns global skills + local overrides merged. Local skills have `scope: "local"`.

**Response:**
```json
[
  {
    "id": "pathly-build",
    "file_name": "pathly-build.md",
    "display_name": "Build",
    "category": "build",
    "description": "Standard build skill",
    "compatible_stages": ["BUILD"],
    "project_root": null,
    "scope": "global",
    "is_custom": false,
    "version": 1
  },
  {
    "id": "my-review",
    "file_name": "my-review.md",
    "display_name": "My Review",
    "category": "review",
    "description": "Project-specific review rules",
    "compatible_stages": ["REVIEW"],
    "project_root": "C:/my-project",
    "scope": "local",
    "is_custom": true,
    "version": 1
  }
]
```

### `GET /api/skills/<id>?project_root=<path>`
Returns full skill including `content` (markdown).

### `POST /api/skills`
Create or update a skill.

**Request:**
```json
{
  "id": "my-review",
  "file_name": "my-review.md",
  "display_name": "My Review",
  "category": "review",
  "content": "# My Review\n\n## Role\n...",
  "description": "Project-specific review rules",
  "compatible_stages": ["REVIEW"],
  "project_root": "C:/my-project"
}
```
**Response:** `{ "ok": true, "version": 1 }`

---

## Agents

### `GET /api/agents?project_root=<path>`
Returns global agents + local overrides merged.

**Response:**
```json
[
  {
    "role": "builder",
    "display_name": "Builder",
    "model": "claude-sonnet-4-6",
    "description": "Implements features",
    "capabilities": ["write_code", "edit_files", "run_tests"],
    "project_root": null,
    "scope": "global",
    "is_custom": false
  }
]
```

### `POST /api/agents`
Create or update an agent definition.

**Request:**
```json
{
  "role": "builder",
  "display_name": "Builder",
  "model": "claude-opus-4-8",
  "instructions": "...",
  "project_root": "C:/my-project"
}
```
**Response:** `{ "ok": true }`

---

## Skill override (runtime swap)

### `POST /api/skill-override`
Set a skill override for a specific stage in the current run.

**Request:**
```json
{
  "project_root": "C:/my-project",
  "feature": "login-flow",
  "run_id": "run_abc123",
  "stage": "REVIEW",
  "skill_name": "pathly-review-strict.md"
}
```
**Response:** `{ "ok": true, "override_id": 7 }`

---

## Traces

### `GET /api/traces?project_root=<path>&feature=login-flow`
List of trace summaries.

**Response:**
```json
[
  {
    "trace_id": "9f3a2b1c4d5e6f70",
    "feature": "login-flow",
    "span_count": 4,
    "start_time_ns": 1749290940000000000,
    "end_time_ns":   1749291027000000000,
    "duration_ms": 87000,
    "status_code": "OK"
  }
]
```

### `GET /api/traces/<trace_id>`
All spans for a trace (for Gantt timeline).

**Response:**
```json
[
  {
    "trace_id": "9f3a2b1c4d5e6f70",
    "span_id": "a1b2c3d4",
    "parent_span_id": null,
    "name": "invoke_agent builder",
    "start_time_ns": 1749290940000000000,
    "end_time_ns":   1749291027000000000,
    "status_code": "OK",
    "attributes": {
      "gen_ai.agent.name": "builder",
      "gen_ai.usage.input_tokens": 41200,
      "gen_ai.usage.output_tokens": 7010,
      "gen_ai.request.model": "claude-sonnet-4-6",
      "pathly.cost_usd": 0.39,
      "pathly.result": "PASS"
    }
  }
]
```

---

## SSE stream

### `GET /events/runner?project_root=<path>&feature=login-flow`
Persistent SSE connection. Receives events as they happen.

**Event format:** `data: <json>\n\n`

**Event types:**
```json
{ "type": "RUN_STARTED",    "topic": "login-flow", "run_id": "run_abc123" }
{ "type": "TERMINAL_SPAWN", "topic": "login-flow", "run_id": "...", "tab_id": "tab_1", "argv": ["claude", "-p", "..."], "adapter": "claude", "label": "BUILD bld-01" }
{ "type": "STATUS",         "topic": "login-flow", "stage": "BUILD", "adapter": "claude", "cost_usd": 0.12, "status": "running" }
{ "type": "AGENT_DONE",     "topic": "login-flow", "stage": "BUILD", "result": "PASS", "cost_usd": 0.39, "summary": "Implemented auth module." }
{ "type": "RUN_COMPLETE",   "topic": "login-flow", "run_id": "...", "status": "done" }
{ "type": "RUNNER_WARNING", "topic": "login-flow", "message": "Cost approaching limit: $0.90 / $1.00" }
```

---

## Project

### `POST /project/open`
**Request:** `{ "project_root": "C:/my-project" }`
**Response:** `{ "ok": true, "project_root": "C:/my-project", "features": [...] }`

### `GET /health`
**Response:** `{ "ok": true, "db": "~/.pathly/pathly.db" }`

### `GET /status?project_root=<path>&feature=<name>`
**Response:**
```json
{
  "fsm": { "current": "REVIEWING", "convs_done": 2, "convs_total": 3 },
  "runner": { "status": "running", "cost_usd_so_far": 1.13, "current_adapter": "claude" }
}
```
