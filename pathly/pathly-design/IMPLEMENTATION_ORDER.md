# Pathly — Implementation Order

Build in this sequence. Each step unblocks the next.
Do not skip ahead — later steps depend on earlier ones working.

---

## Phase 1 — Backend foundation (unblocks everything)

### 1.1 — Rewrite `db.py`
- Change `get_db(feature_dir)` → `get_db()` (always `~/.pathly/pathly.db`)
- Replace `_SCHEMA_SQL` with full schema from `schema_all.sql` (all 12 tables)
- Add `schema_version` table + `_run_migrations()` function
- Update all helper signatures: add `project_root` param
- Add new helpers for tables 7-12
- **Done when:** `get_db()` returns a working connection, all 12 tables created, schema migration runs cleanly

### 1.2 — Seed data
- Add `_seed_if_empty(db)` to `db.py` startup
- Seeds: flows (team/standard/nano/plan-only), skills from `pathly_data/`, agents from `pathly_data/`
- Uses `INSERT OR IGNORE` — idempotent
- **Done when:** fresh DB has all built-in flows, skills, agents populated

### 1.3 — Update callers of `db.py`
- `fsm_ops.py`: `(feature_dir)` → `(project_root, feature)`
- `supervisor.py`: pass `project_root` from runner config
- `eventlog.py`: `(feature_dir)` → `(project_root, feature)`
- `otel_export.py`: add `project_root` to all writes
- **Done when:** existing pipeline runs without errors with new signatures

### 1.4 — Add `services/` directory
Create each service file (see BACKEND_STRUCTURE.md):
- `flow_service.py` — CRUD for flows/nodes/edges
- `event_service.py` — paginated event queries
- `agent_service.py` — invocations + metrics aggregation
- `span_service.py` — trace queries
- `artifact_service.py` — artifact reads + skill override writes
- `skill_catalog.py` — `resolve_skill(file_name, project_root)` with local-first SQL
- **Done when:** each service has working methods with unit tests

---

## Phase 2 — HTTP routes (unblocks frontend)

### 2.1 — Add `/api/features` routes
- `GET /api/features?project_root=`
- `GET /api/features/<feature>/events`
- `GET /api/features/<feature>/invocations`
- `GET /api/features/<feature>/metrics`
- `GET /api/features/<feature>/artifacts`
- **Done when:** curl returns correct JSON (test against seed data)

### 2.2 — Add `/api/flows` routes
- `GET /api/flows`
- `GET /api/flows/<id>`
- `POST /api/flows`
- **Done when:** canvas can load and save flows

### 2.3 — Add `/api/skills` and `/api/agents` routes
- `GET /api/skills?project_root=` — merged global + local
- `POST /api/skills`
- `GET /api/agents?project_root=`
- `POST /api/agents`
- **Done when:** notebook can load and save skills/agents

### 2.4 — Add `/api/traces` routes
- `GET /api/traces?project_root=&feature=`
- `GET /api/traces/<trace_id>`
- **Done when:** trace timeline can load spans

### 2.5 — Add `/api/skill-override` route
- `POST /api/skill-override`
- **Done when:** Studio can set a runtime skill swap

### 2.6 — Update runner routes to use `project_root`
- `POST /runner/start` — reads `project_root` from body
- `POST /runner/pause`, `/resume`, `/abort` — same
- `POST /runner/terminal/result` — writes to DB with `project_root`
- **Done when:** a full pipeline run completes and writes all data to single DB

### 2.7 — Add `POST /project/open`
- Creates `<project_root>/pathly/plans/` directory
- Returns existing features from DB
- **Done when:** Studio can open a project folder

---

## Phase 3 — Frontend (parallel tracks once Phase 2 done)

### 3.1 — Update `api.ts`
- Write typed fetch wrappers for all endpoints in API_CONTRACTS.md
- Include `project_root` in all calls
- **Done when:** all endpoints callable with TypeScript types

### 3.2 — Update Zustand store
- Add `projectRoot`, `features`, `view`, `notebookFile`, `activeFlowId`
- SSE connection in store (`useEffect` on `projectRoot`)
- **Done when:** store can hold all app state with correct types

### 3.3 — Update `StudioApp.tsx` shell
- Sidebar logic: render different sidebar per `view`
- Header: project picker calls `POST /project/open`
- **Done when:** switching views changes sidebar correctly

### 3.4 — Update `NotebookView.tsx` — universal editor
- Accept `NotebookFile` prop (skill | agent | artifact)
- Load content from API based on `file.kind`
- Skills/agents: editable cells → `POST /api/skills` or `POST /api/agents` on save
- Artifacts: read-only mode (no edit toolbar)
- Cell toggle: per-cell raw/preview button (already partially built)
- **Done when:** can edit a skill, save it, and reopen with changes preserved

### 3.5 — Update `NotebookSidebar.tsx`
- Three sections: Skills, Agents, Feature Files
- Click any item → `store.openNotebook(file)`
- Local files show `[LOCAL]` badge
- **Done when:** sidebar lists all files, clicking opens in notebook

### 3.6 — Build `CanvasView.tsx`
- ReactFlow canvas loading from `GET /api/flows/<id>`
- Custom node component: shows name, agent, skill, adapter
- Click node → `CanvasSidebar` shows properties
- Drag node → update `pos_x`, `pos_y` in local state
- Save button → `POST /api/flows`
- **Done when:** user can open a flow, edit a node's skill, save, and next run uses it

### 3.7 — Update `DBExplorerView.tsx`
- Load from `GET /api/features?project_root=`
- Feature modal: add **Artifacts** tab (rendered notebook, read-only)
- Feature modal: add **Traces** tab (Gantt span timeline)
- **Done when:** all 5 tabs work in feature modal

### 3.8 — Build `SettingsView.tsx`
- Adapter paths, cost limits, OTel endpoint
- Appearance (accent, density)
- Export/import flows as YAML, skills as .md
- **Done when:** settings persist via Electron `app.getPath('userData')`

---

## Phase 4 — Polish

### 4.1 — Mid-phase logging in skills
- Add curl log commands to each built-in skill
- `POST :8765/log` → writes to `fsm_events`
- `GET :8765/next_instructions?stage=BUILD` → reads `skill_overrides`
- **Done when:** Monitor shows live events during agent execution

### 4.2 — Skill override full loop
- Studio: pause button before stage → skill picker appears
- Select skill → `POST /api/skill-override`
- Resume → supervisor picks up override on next `/next_action`
- **Done when:** user can swap a skill mid-run and next stage uses it

### 4.3 — Multi-adapter routing
- Canvas: each node has `adapter` dropdown
- Supervisor reads `flow_nodes.adapter` per stage
- Spawns correct CLI (`claude`, `codex`, etc.)
- **Done when:** REVIEW stage can run on codex while BUILD runs on claude

---

## Dependency graph

```
1.1 db.py rewrite
  └── 1.2 seed data
        └── 1.3 update callers
              └── 1.4 services/
                    ├── 2.1 /api/features
                    ├── 2.2 /api/flows ──────── 3.6 Canvas
                    ├── 2.3 /api/skills ─────── 3.4 Notebook
                    ├── 2.4 /api/traces ─────── 3.7 DB Explorer (traces tab)
                    ├── 2.5 /api/skill-override  4.2 skill swap loop
                    ├── 2.6 runner routes ────── 4.1 mid-phase logging
                    └── 2.7 /project/open ─────  3.3 App shell
                                                  └── 3.1 api.ts
                                                        └── 3.2 store
                                                              ├── 3.3 shell
                                                              ├── 3.5 notebook sidebar
                                                              └── 3.8 settings
```

---

## What to test at each step

| Step | Test |
|---|---|
| 1.1 | `python -c "from pathly_orchestrator.db import get_db; db=get_db(); print(db.execute('SELECT name FROM sqlite_master').fetchall())"` |
| 1.2 | Check DB has rows in `flow_definitions`, `skill_definitions`, `agent_definitions` |
| 1.3 | Run an existing pipeline end to end — should complete without errors |
| 2.1 | `curl http://127.0.0.1:8765/api/features?project_root=C:/my-project` |
| 2.2 | `curl http://127.0.0.1:8765/api/flows` |
| 3.6 | Open canvas, move a node, save, restart server, reopen canvas — position preserved |
| 3.4 | Edit a skill cell, save, close notebook, reopen — edit preserved |
| 4.2 | Run pipeline to REVIEW, pause, swap skill, resume — check agent_invocations.skill_name |
