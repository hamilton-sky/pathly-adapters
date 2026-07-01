# FLOW_DIAGRAM.md — studio-backend

## Main Runtime Path: Pipeline Run to API Query

```
Developer (Studio UI)
        |
        | POST /runner/start
        |   {topic, flow, project_root}
        v
http_server.py
        |
        v
supervisor.py: start_run(topic, flow, project_root)
        |
        | get_db()  -->  ~/.pathly/pathly.db
        |
        | write_runner_state(conn, project_root, feature, {status: "running"})
        |
        v
FSM loop: /next_action (internal call)
        |
        | read_state(conn, project_root, feature)
        |   --> {current_state: "PLAN", ...}
        |
        | read_skill_override(conn, project_root, feature, stage)  [optional]
        |   --> "pathly-build-strict"  or  None
        |
        v
PTY agent spawned (e.g., builder for BUILD stage)
        |
        | [agent runs, writes AGENT_DONE to EVENTS.jsonl]
        |
        v
supervisor.py: PTY exits, reads EVENTS.jsonl
        |
        | append_event(conn, project_root, feature, AGENT_DONE event)
        |
        | write_agent_invocation(conn, project_root, feature, {
        |     run_id, stage, agent_role,
        |     tokens_in, tokens_out, cost_usd, summary
        | })
        |
        | write_state(conn, project_root, feature, {current_state: "BUILD"})
        |
        v
/events/runner (SSE stream)  -->  Studio live event stream
        |
        [run completes or loops to next stage]
        |
        v
Developer opens DB Explorer tab in Studio
        |
        | GET /api/features/auth-service/events
        |   ?project_root=/home/dev/my-app&since_seq=0
        |
        v
http_server.py: api_feature_events()
        |
        v
event_service.get_events("/home/dev/my-app", "auth-service")
        |
        | get_db()  -->  ~/.pathly/pathly.db
        | read_events(conn, "/home/dev/my-app", "auth-service")
        |
        v
{total: 47, events: [...]}  -->  Studio DB Explorer view
```

---

## Error and Recovery Path: Stale Runner Cleanup

```
Server starts (or restarts after crash)
        |
        v
http_server.py: startup hook
        |
        | get_db()  -->  ~/.pathly/pathly.db
        |
        v
mark_stale_runners(conn)
        |
        | UPDATE runner_state
        |   SET runner_json = json_set(runner_json, '$.status', 'stale')
        | WHERE updated_at < datetime('now', '-30 minutes')
        |   AND json_extract(runner_json, '$.status') = 'running'
        |
        | Returns count of rows updated (logged)
        v
DB is consistent — no phantom "running" runners
        |
        v
Normal request handling resumes
```

---

## Seed Path: First DB Initialization

```
get_db() called for the first time
        |
        | Path.home() / '.pathly' / 'pathly.db'
        |   directory created if missing
        |
        v
_run_migrations(conn)
        |
        | CREATE TABLE IF NOT EXISTS schema_version ...
        | CREATE TABLE IF NOT EXISTS fsm_events ...
        | ... (12 tables total) ...
        | INSERT OR IGNORE INTO schema_version VALUES (1, ...)
        |
        v
_seed_if_empty(conn)
        |
        | SELECT COUNT(*) FROM flow_definitions
        |   --> 0  (first time)
        |
        | Read src/pathly_data/core/flows/*.flow.yaml
        |   --> upsert_flow_definition(conn, None, "explore", ...)
        |   --> upsert_flow_definition(conn, None, "test", ...)
        |   --> upsert_flow_definition(conn, None, "team", ...)
        |   --> upsert_flow_definition(conn, None, "debug", ...)
        |   --> upsert_flow_definition(conn, None, "quick-fix", ...)
        |
        | Read src/pathly_data/core/agents/**/*.md
        |   + adapters/claude/_meta/<agent>.yaml
        |   --> upsert_agent_definition(conn, None, "builder", ...)
        |   --> upsert_agent_definition(conn, None, "architect", ...)
        |   --> ... (13+ agents)
        |
        | Read src/pathly_data/core/skills/**/*.md
        |   + adapters/claude/_meta/<skill>_skill.yaml
        |   --> upsert_skill_definition(conn, None, "pathly-build", ...)
        |   --> upsert_skill_definition(conn, None, "pathly-plan", ...)
        |   --> ...
        |
        v
DB ready — flows, agents, skills populated with project_root = NULL
        |
        v
get_db() returns conn
```

---

## Skill Override Resolution Path

```
FSM selecting skill for BUILD stage
        |
        | read_skill_override(conn, project_root, feature, "BUILD")
        |
        +--[override found]--> use "pathly-build-strict"
        |
        +--[no override]-----> skill_catalog.resolve_skill("pathly-build", project_root)
                                        |
                                        | SELECT * FROM skill_definitions
                                        | WHERE skill='pathly-build'
                                        |   AND (project_root=? OR project_root IS NULL)
                                        | ORDER BY project_root IS NULL
                                        | LIMIT 1
                                        |
                                        +--[project row exists]--> project-local skill content
                                        |
                                        +--[only global row]-----> global skill content
```
