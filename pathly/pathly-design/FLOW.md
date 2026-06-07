# Pathly — Full Flow: Backend ↔ Frontend

## 0. Architecture

```
ONE DATABASE:  ~/.pathly/pathly.db
  ├── Global config:   flow_definitions, flow_nodes, flow_edges,
  │                    skill_definitions (NULL project_root),
  │                    agent_definitions (NULL project_root)
  │
  └── Runtime data:    fsm_events, fsm_state, runner_state,
                       agent_invocations, otel_spans,
                       skill_overrides, stage_artifacts
                       (all have project_root + feature columns)

PROJECT FOLDER:  <user-selected-folder>/         ← workspace only, no DB
  pathly/
    plans/
      <feature>/
        USER_STORIES.md        ← agent reads/writes
        REVIEW_FAILURES.md     ← reviewer writes, builder reads
        TEST_FAILURES.md       ← tester writes, builder reads
```

**One DB connection. All queries filter by `project_root`.**
The folder is just a directory. Selecting it sets `project_root` in memory — nothing else.

---

## 1. App Startup

```
User opens Pathly Electron app
        │
        ├── Electron main process starts
        ├── Spawns Python HTTP server on :8765
        ├── Server opens ~/.pathly/pathly.db  (created if not exists)
        ├── Seeds DB with built-in flows, skills, agent roles (if empty)
        └── Studio (React) loads in Electron window
                │
                ├── GET :8765/health              → server ready
                ├── GET :8765/api/flows            → load flows into canvas
                ├── GET :8765/api/skills           → load skills into picker
                └── GET :8765/api/agents           → load agent roles into selector
```

---

## 2. User Selects a Project Folder

```
User is on the Pathly home screen
User clicks "Open Project" → selects C:/my-project/
        │
Studio  POST :8765/project/open
        body: { project_root: "C:/my-project" }
        │
http_server.py
        ├── creates  C:/my-project/pathly/plans/  (if not exists)
        │   (just a directory — no DB file)
        └── returns { project_root, features: [] }
                │
                Studio sets project_root = "C:/my-project" in Zustand store
                GET :8765/api/features?project_root=C:/my-project
                → queries fsm_state WHERE project_root='C:/my-project'
                → returns existing features (empty on first open)
```

No DB creation. No schema migration. Just a directory check.

---

## 3. User Creates a Feature

```
User clicks "New Feature" → types name "login-flow"
        │
Studio  POST :8765/features/create
        body: { project_root: "C:/my-project", feature: "login-flow", flow: "team" }
        │
http_server.py
        ├── creates  C:/my-project/pathly/plans/login-flow/  (artifact folder)
        ├── INSERT INTO fsm_state VALUES ('C:/my-project', 'login-flow', 'STORM', ...)
        ├── INSERT INTO runner_state VALUES ('C:/my-project', 'login-flow', 'idle', ...)
        └── Studio shows "login-flow" in feature list
```

---

## 4. Pipeline Run — Full Flow

```
Studio  POST :8765/runner/start
        body: { project_root: "C:/my-project", feature: "login-flow" }
        │
supervisor.py starts loop:
        │
        ├── POST :8765/next_action
        │     body: { project_root, feature }
        │         │
        │         FSM reads:
        │         ├── fsm_state WHERE (project_root, feature)   → current='BUILD'
        │         ├── flow_nodes WHERE flow_id='team', name='BUILD'
        │         │     → agent='builder', skill='pathly-build.md', adapter='claude'
        │         ├── skill_definitions WHERE file_name='pathly-build.md'
        │         │     AND (project_root='C:/my-project' OR project_root IS NULL)
        │         │     ORDER BY project_root IS NULL  ← local first
        │         └── skill_overrides WHERE (project_root, feature, run_id, stage='BUILD')
        │
        │         Returns: { agent: "builder", instructions: "..full prompt..", adapter: "claude" }
        │
        ├── Emits SSE  TERMINAL_SPAWN
        │         { tab_id, run_id, argv: ["claude","-p","..prompt.."], adapter: "claude" }
        │
        │   ┌────────────────────────────────────────────────┐
        │   │  Electron terminal.ts receives TERMINAL_SPAWN  │
        │   │  Opens PTY tab with node-pty                   │
        │   │  Spawns: claude -p "..prompt.."                │
        │   │  POST :8765/runner/terminal/started            │
        │   └────────────────────────────────────────────────┘
        │
        │   ┌────────────────────────────────────────────────┐
        │   │  Agent runs                                    │
        │   │  Reads .md files from project folder           │
        │   │  Does work                                     │
        │   │  Mid-phase: curl POST :8765/log → ~/.pathly/pathly.db  │
        │   │  Mid-phase: curl GET :8765/next_instructions   │
        │   │  Writes REVIEW_FAILURES.md etc.                │
        │   └────────────────────────────────────────────────┘
        │
        │   PTY exits → Electron POSTs /runner/terminal/result
        │         { run_id, project_root, feature, exit_code, wall_seconds }
        │
        └── http_server handles /runner/terminal/result:
                ├── reads EVENTS.jsonl → AGENT_DONE.summary
                ├── INSERT INTO fsm_events      (project_root, feature, ...)
                ├── UPDATE fsm_state            (project_root, feature, current=...)
                ├── UPDATE runner_state         (project_root, feature, cost=...)
                ├── INSERT INTO agent_invocations (project_root, feature, ...)  [NEW]
                ├── read REVIEW_FAILURES.md → INSERT INTO stage_artifacts       [NEW]
                ├── calls otel_export → INSERT INTO otel_spans                  [NEW]
                └── emits SSE: STATUS + AGENT_DONE → Studio updates
```

---

## 5. SSE Stream (real-time Studio updates)

```
Studio subscribes:  GET :8765/events/runner?project_root=C:/my-project&feature=login-flow
        │
Events received:
  RUN_STARTED       → show running badge
  TERMINAL_SPAWN    → open PTY tab
  TERMINAL_STARTED  → tab confirmed active
  STATUS            → update stage, cost, adapter
  AGENT_DONE        → update stage log, token counts
  RUN_COMPLETE      → show done/error state
  RUNNER_WARNING    → toast notification
```

---

## 6. DB API — How Studio reads data

```
Studio component          HTTP call                              project_root?
─────────────────────────────────────────────────────────────────────────────
DB Explorer cards    GET /api/features?project_root=            required
Feature modal        GET /api/features/<f>/events?project_root= required
                     GET /api/features/<f>/artifacts?...        required
                     GET /api/features/<f>/invocations?...      required

Monitoring Charts    GET /api/features/<f>/metrics?project_root= required
Global dashboard     GET /api/features  (no project_root)        optional → all projects

OTel Traces          GET /api/traces?project_root=&feature=      required
Span timeline        GET /api/traces/<trace_id>                  not needed (trace_id is global)

Skill picker         GET /api/skills?project_root=               returns merged global+local
Skill override       POST /api/skill-override                    required

Canvas               GET /api/flows                              not needed (flows are global)
                     POST /api/flows                             not needed
```

---

## 7. Skill Resolution — Local Override

```
FSM builds prompt for REVIEW stage:
        │
skill_catalog.resolve_skill('pathly-review.md', project_root='C:/my-project')
        │
        SELECT * FROM skill_definitions
        WHERE file_name = 'pathly-review.md'
          AND (project_root = 'C:/my-project' OR project_root IS NULL)
        ORDER BY project_root IS NULL   -- local (0) before global (1)
        LIMIT 1
        │
        ├── project has local 'pathly-review.md' → use it  [LOCAL OVERRIDE]
        └── no local → use global built-in                  [GLOBAL]
```

---

## 8. Skill Override Flow (Runtime Swap)

```
Pipeline running → about to start REVIEW stage
        │
Studio user picks "pathly-review-strict.md" in skill picker
Studio  POST :8765/api/skill-override
              { project_root, feature, run_id, stage: "REVIEW",
                skill_name: "pathly-review-strict.md" }
Server  INSERT INTO skill_overrides { status: 'pending' }
        │
Supervisor on next /next_action call:
        SELECT * FROM skill_overrides
        WHERE project_root=? AND feature=? AND run_id=? AND stage='REVIEW'
          AND status='pending'
        → found → inject pathly-review-strict.md into prompt
        → UPDATE skill_overrides SET status='applied'
```

---

## 9. Canvas Save → FSM Uses It

```
User edits flow in canvas → changes REVIEW agent to reviewer-strict
Studio  POST :8765/api/flows
              { id: "team", nodes: [...updated...], edges: [...] }
        │
FlowService.save() → UPSERT flow_definitions, flow_nodes, flow_edges
        │
Next run: FSM reads flow_nodes WHERE flow_id='team'
          → REVIEW node now has skill_name='pathly-review-strict.md'
          All future runs automatically use the updated flow
```

---

## 10. Summary: Who owns what

| Layer | Responsibility | Technology |
|---|---|---|
| **Studio (React)** | UI, canvas, monitoring, DB explorer | TypeScript, React, Zustand |
| **Electron shell** | Window, PTY terminals, filesystem, IPC | Electron, node-pty |
| **http_server.py** | All routes, SSE stream | Python, Flask |
| **supervisor.py** | Pipeline loop, PTY spawn, result handling | Python |
| **fsm_ops.py** | FSM state transitions | Python |
| **skill_catalog.py** | Local→global skill resolution | Python |
| **services/*.py** | Business logic, data shaping | Python |
| **db.py** | Raw SQL, always opens `~/.pathly/pathly.db` | Python, sqlite3 |
| **otel_export.py** | OTLP span export — remote + local | Python |
| **SQLite** | `~/.pathly/pathly.db` — everything | SQLite |

---

## 11. Adapter compatibility

Every agent (Claude, Codex, Copilot, Antigravity) communicates via:
1. **Read files** — agent reads `.md` files from the project workspace folder
2. **Write files** — agent writes output `.md` files to the workspace folder
3. **HTTP curl** — agent calls `curl POST :8765/...` for mid-phase logging

No MCP. No adapter-specific protocol.

```
Claude CLI     → bash curl :8765  ✅
Codex CLI      → bash curl :8765  ✅
Copilot Agent  → bash curl :8765  ✅
Antigravity    → bash curl :8765  ✅
```
