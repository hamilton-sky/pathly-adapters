# Pathly — How the App Controls the FSM and Runner

---

## The Core Idea

```
Studio UI  →  HTTP :8765  →  Python server  →  ~/.pathly/pathly.db
                                    ↑
                              reads DB to decide
                              what to do next
                              (filtered by project_root)
```

One database. One HTTP server. Studio never touches the DB directly.
Every action goes through `:8765`. Every state change is a DB write.

---

## How the App Controls the FSM

The FSM decides what stage the pipeline is in and what agent runs next.

### What controls FSM state

| Table | project_root? | What it stores | Who writes | Who reads |
|---|---|---|---|---|
| `fsm_state` | Yes | Current stage, retries, convs done/total | http_server after each PTY exit | FSM to decide next action |
| `fsm_events` | Yes | Append-only log of every event | http_server on every transition | FSM for recovery, Studio for event log |
| `flow_definitions` | No (global) | Which flows exist | Canvas (Studio) | FSM at run start |
| `flow_nodes` | No (global) | Stage → agent role + skill + adapter | Canvas (Studio) | FSM to build each prompt |
| `flow_edges` | No (global) | Transition conditions (PASS→next, FAIL→retry) | Canvas (Studio) | FSM to route after each result |
| `skill_overrides` | Yes | Runtime skill swap for a specific stage | Studio skill picker | FSM before building prompt |

### FSM decision cycle

```
Studio calls:  POST :8765/next_action  { project_root, feature }
                      │
              http_server reads from ~/.pathly/pathly.db:
              ├── fsm_state WHERE (project_root, feature)    → current stage?
              ├── flow_nodes WHERE flow_id=<runner.flow>     → which agent + skill?
              ├── flow_edges WHERE flow_id=<runner.flow>     → what transitions exist?
              └── skill_overrides WHERE (project_root, feature, run_id, stage)
                                                             → any runtime swap?
                      │
              Returns: { agent, instructions, skill, adapter, decision }
                      │
              Supervisor spawns the CLI with those instructions
```

### How Studio modifies FSM behavior

| Studio action | HTTP call | DB write | Effect |
|---|---|---|---|
| Edit flow in canvas | `POST /api/flows` | `flow_nodes`, `flow_edges` | All future runs use the updated flow |
| Swap skill before a stage | `POST /api/skill-override` | `skill_overrides` | This run uses the chosen skill for that stage |
| Pause pipeline | `POST /runner/pause` | `runner_state.status = paused` | Supervisor stops before next stage |
| Resume pipeline | `POST /runner/resume` | `runner_state.status = running` | Supervisor continues |
| Abort run | `POST /runner/abort` | `runner_state.status = aborted` | Supervisor exits loop |

---

## How the App Controls the Runner

The runner (`supervisor.py`) drives the pipeline loop.
It is controlled through `runner_state` — filtered by `(project_root, feature)`.

### Runner state columns the supervisor checks

| Column | Values | What it does |
|---|---|---|
| `status` | `idle` `running` `paused` `done` `error` `aborted` | Checked before every stage — stops if not `running` |
| `flow` | `team` `standard` `nano` | Which flow to load from `flow_definitions` |
| `current_state` | `BUILD` `REVIEW` `TEST` | Updated by FSM after each transition |
| `current_adapter` | `claude` `codex` `copilot` | Which CLI to spawn — set per stage from `flow_nodes.adapter` |
| `cost_usd_so_far` | `0.0 → n` | Supervisor checks against `max_cost_usd` before each stage |
| `max_cost_usd` | user-set | If exceeded, supervisor sets `status=error` and exits |
| `max_iterations` | user-set | If exceeded, supervisor stops |

### Runner loop

```
supervisor.py:

  while True:
      SELECT * FROM runner_state WHERE project_root=? AND feature=?
      │
      if status == 'paused'  → sleep 2s, poll again
      if status == 'aborted' → break
      if cost_usd_so_far > max_cost_usd → set error, break
      │
      POST :8765/next_action { project_root, feature }
      → FSM returns { agent, instructions, skill, adapter }
      │
      emit SSE TERMINAL_SPAWN { argv, adapter, tab_id, run_id }
      Studio opens PTY tab, spawns CLI
      │
      wait for POST /runner/terminal/result callback
      │
      INSERT INTO agent_invocations (project_root, feature, ...)
      INSERT INTO otel_spans        (project_root, feature, ...)
      INSERT INTO stage_artifacts   (project_root, feature, ...)  ← mirrors .md files
      UPDATE fsm_state              (project_root, feature, current=<next>)
      emit SSE STATUS
```

---

## Local vs Global Skills and Agents

One DB handles both global and local overrides via `project_root`:

```
skill_definitions
  project_root = NULL          → global skill, available in every project
  project_root = 'C:/proj'     → local override, only for that project folder

agent_definitions
  project_root = NULL          → global role config (model, instructions)
  project_root = 'C:/proj'     → local override (different model for this project)
```

### Resolution — always local first

```sql
-- same query pattern for both skills and agents:
SELECT * FROM skill_definitions
WHERE file_name = 'pathly-review.md'
  AND (project_root = 'C:/my-project' OR project_root IS NULL)
ORDER BY project_root IS NULL   -- 0 (local, has a path) before 1 (global, NULL)
LIMIT 1
```

### Skill picker in Studio

```
User opens skill picker for REVIEW stage (project: C:/my-project)
         │
GET /api/skills?project_root=C:/my-project
         │
Server returns merged list:
  ● pathly-review-security.md  [LOCAL]            ← project_root='C:/my-project'
  ● pathly-review.md           [LOCAL OVERRIDE]   ← shadows the global one
  ● pathly-review.md           (hidden — shadowed by local)
  ● pathly-review-strict.md    [GLOBAL]
  ● pathly-review-lite.md      [GLOBAL]
```

---

## Summary: DB as the single control surface

```
~/.pathly/pathly.db

  ┌─────────────────────────────────────────────────┐
  │  GLOBAL (no project_root)                        │
  │  flow_definitions + nodes + edges  ← canvas      │
  │  skill_definitions (NULL)          ← built-in    │
  │  agent_definitions (NULL)          ← built-in    │
  └─────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────┐
  │  PER PROJECT (project_root = 'C:/my-project')    │
  │  runner_state      ← pause/resume/abort          │
  │  fsm_state         ← current stage               │
  │  fsm_events        ← append-only log             │
  │  skill_overrides   ← runtime skill swap          │
  │  skill_definitions ← local overrides             │
  │  agent_definitions ← local overrides             │
  │  agent_invocations ← charts + cost               │
  │  otel_spans        ← trace timeline              │
  │  stage_artifacts   ← mirrored .md content        │
  └─────────────────────────────────────────────────┘

C:/my-project/pathly/plans/<feature>/
  USER_STORIES.md          ← files only, agents read/write
  REVIEW_FAILURES.md
  TEST_FAILURES.md
```

Studio talks to `:8765`. Server talks to the DB.
The project folder is a workspace for `.md` files — not a data store.
