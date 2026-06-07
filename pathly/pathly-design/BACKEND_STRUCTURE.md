# Pathly — Backend File System Structure

## One Database, One Workspace

```
~/.pathly/pathly.db          ← ONLY database (all structured data)
  │
  │  Global config (no project_root):
  │    flow_definitions, flow_nodes, flow_edges
  │    skill_definitions (project_root=NULL)
  │    agent_definitions (project_root=NULL)
  │
  │  Runtime data (project_root identifies which project):
  │    fsm_events, fsm_state, runner_state
  │    agent_invocations, otel_spans
  │    skill_overrides, stage_artifacts
  │
  │  Local overrides (project_root=<folder>):
  │    skill_definitions (project_root=path)  ← project-specific skill
  │    agent_definitions (project_root=path)  ← project-specific agent config

<project-folder>/                ← workspace only (no DB here)
  pathly/
    plans/
      <feature>/
        USER_STORIES.md          ← agents read/write these files
        IMPLEMENTATION_PLAN.md
        CONVERSATION_PROMPTS.md
        REVIEW_FAILURES.md
        TEST_FAILURES.md
```

**Rule:** all structured data → `~/.pathly/pathly.db`
**Rule:** files agents read/write → `<project>/pathly/plans/<feature>/`
**Rule:** `project_root` TEXT column separates projects within the DB

---

## Root layout

```
pathly-adapters/
├── src/
│   └── pathly_orchestrator/        ← Python package (the backend)
├── studio/                         ← Electron app (the frontend)
├── pathly/
│   └── plans/
│       └── <feature>/
│           ├── USER_STORIES.md
│           ├── IMPLEMENTATION_PLAN.md
│           ├── CONVERSATION_PROMPTS.md
│           └── feedback/
│               ├── REVIEW_FAILURES.md
│               └── TEST_FAILURES.md
└── tests/
```

---

## Backend package: `src/pathly_orchestrator/`

```
src/pathly_orchestrator/
│
│── __init__.py
│
│── db.py                       ← DB connection + all raw SQL helpers
│                                  get_db() → sqlite3.Connection to ~/.pathly/pathly.db
│                                  NO feature_dir arg — always the same file
│                                  Tables 1-3: existing helpers (project_root added)
│                                  Tables 4-12: new helpers              [NEW]
│
│── http_server.py              ← Flask HTTP server on :8765
│                                  All routes (existing + new /api/* routes)
│                                  project_root passed in request body or query param
│
│── supervisor.py               ← Pipeline runner
│                                  Polls /next_action → spawns PTY terminal
│                                  Reads PTY exit → calls /runner/terminal/result
│                                  Mirrors artifact files → stage_artifacts table [NEW]
│                                  Writes agent_invocations on AGENT_DONE          [NEW]
│
│── otel_export.py              ← OpenTelemetry span exporter
│                                  Builds OTLP payload from AGENT_DONE event
│                                  POST to external collector (if configured)
│                                  Also writes to otel_spans table locally         [NEW]
│
│── eventlog.py                 ← Event log abstraction
│                                  Writes to fsm_events table (+ EVENTS.jsonl legacy)
│                                  read_state(project_root, feature)
│                                  append_event(project_root, feature, ...)
│
│── fsm_ops.py                  ← FSM transition logic
│                                  next_action(project_root, feature)
│                                  complete_stage(project_root, feature)
│                                  build_prompt() for each agent
│                                  Checks skill_overrides before building prompt   [NEW]
│
│── compose.py                  ← Block/fragment composition
│                                  Injects skill content into prompts
│
│── skill_catalog.py            ← Skill index
│                                  resolve_skill(file_name, project_root)
│                                  Queries project_root first → falls back to NULL [NEW]
│
│── skill_parser.py             ← Markdown → cells parser
│                                  Used by skill notebook editor
│
│── services/                   ← Service layer (business logic)     [NEW DIRECTORY]
│   │
│   ├── __init__.py
│   │
│   ├── flow_service.py         ← FlowService
│   │                              get_all() → all flows
│   │                              get(flow_id) → flow + nodes + edges
│   │                              save(payload) → upsert
│   │
│   ├── event_service.py        ← EventService
│   │                              list(project_root, feature, limit, type) → events
│   │
│   ├── agent_service.py        ← AgentService
│   │                              list(project_root, feature, stage) → invocations
│   │                              metrics(project_root, feature) → aggregates
│   │                              write(project_root, feature, inv) → store
│   │
│   ├── span_service.py         ← SpanService
│   │                              list_traces(project_root, feature) → trace summaries
│   │                              get_trace(trace_id) → all spans
│   │                              write(project_root, feature, span) → store
│   │
│   └── artifact_service.py     ← ArtifactService
│                                  list(project_root, feature, run_id, type)
│                                  write_skill_override(project_root, feature, ...)
│                                  get_pending_override(project_root, feature, stage)
│
└── hooks/
    └── stop_telemetry.py       ← Stop hook: appends token usage after each session
```

---

## HTTP API Routes (all on :8765)

### Existing routes (keep unchanged)

```
POST /next_action                ← FSM: what should the next agent do?
POST /complete_stage             ← FSM: mark current stage complete
POST /record_activity            ← FSM: record agent activity + fire OTel span

POST /runner/start               ← Start a pipeline run
POST /runner/pause               ← Pause running pipeline
POST /runner/resume              ← Resume paused pipeline
POST /runner/advance             ← Skip past current block
POST /runner/retry               ← Retry blocked stage
POST /runner/abort               ← Abort run
POST /runner/terminal/result     ← PTY exit callback
POST /runner/terminal/started    ← PTY started confirmation
GET  /events/runner              ← SSE stream of live runner events

GET  /skills/catalog             ← List available skills
POST /skills/parse               ← Parse skill markdown → cells
POST /skills/preview             ← Live preview rendering
PUT  /skills/export              ← Save edited skill to disk

GET  /status                     ← Current FSM state + runner status
GET  /metrics                    ← Aggregated cost + token stats
GET  /health                     ← Server health check
POST /shutdown                   ← Graceful shutdown
```

### New DB API routes [NEW]

All new routes accept `project_root` as a query param or in the request body.

```
── Features (runtime data for one project) ──
GET  /api/features?project_root=             ← all features + stats for this project
GET  /api/features/<feature>/events          ← paginated event log
GET  /api/features/<feature>/invocations     ← agent invocations list
GET  /api/features/<feature>/metrics         ← cost/token aggregates for charts
GET  /api/features/<feature>/artifacts       ← stage artifacts

── Flows (global config — no project_root needed) ──
GET  /api/flows                              ← all flow definitions
GET  /api/flows/<id>                         ← one flow with nodes + edges
POST /api/flows                              ← create or update a flow

── Skills (global + local) ──
GET  /api/skills?project_root=               ← merged list (local overrides marked)
POST /api/skills                             ← create/update skill
DELETE /api/skills/<id>?project_root=        ← delete skill

── Agents (global + local) ──
GET  /api/agents?project_root=               ← merged list (local overrides marked)
POST /api/agents                             ← create/update agent definition

── Traces ──
GET  /api/traces?project_root=&feature=      ← trace list
GET  /api/traces/<trace_id>                  ← all spans for a trace

── Runtime control ──
POST /api/skill-override                     ← set runtime skill swap
```

---

## Data flow through the backend

```
Agent (any adapter)
    │
    │  PTY exits → Electron POSTs /runner/terminal/result
    ▼
http_server.py  (Flask route handler)
    │
    ├── calls fsm_ops.py           → advances FSM
    ├── calls eventlog.append_event → writes fsm_events (project_root, feature)
    ├── calls db.write_state        → writes fsm_state  (project_root, feature)
    ├── calls db.write_invocation   → writes agent_invocations               [NEW]
    ├── calls otel_export.py        → POST to collector + write otel_spans   [NEW]
    ├── reads artifact .md files    → writes stage_artifacts                 [NEW]
    └── emits SSE event             → Studio receives update
```

---

## Service layer responsibility split

```
db.py           raw SQL only — no business logic
                get_db() → always ~/.pathly/pathly.db
                all helpers take (project_root, feature) args

services/*.py   business logic — calls db.py, returns shaped data
                resolve_skill() handles local→global fallback

http_server.py  routing only — calls services, returns JSON
                extracts project_root from request, passes through
```

---

## Key files that agents interact with (files, not DB)

These `.md` files live in the project workspace folder.
Agents are subprocesses that read and write the filesystem.
After each stage the supervisor mirrors them into `stage_artifacts` in the DB.
These files are safe to commit to git — they are plain text.

```
<project>/pathly/plans/<feature>/
    USER_STORIES.md          ← planner writes → reviewer/tester reads
    IMPLEMENTATION_PLAN.md   ← architect writes → builder reads
    CONVERSATION_PROMPTS.md  ← planner writes → builder reads
    feedback/
        REVIEW_FAILURES.md   ← reviewer writes → builder reads next conv
        TEST_FAILURES.md     ← tester writes → builder reads next conv
```
