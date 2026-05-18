# FLOW_DIAGRAM.md — mcp-fsm-driver

_Text-based diagrams. No external tools required._

---

## 1. Four-conversation delivery sequence

```
  fsm-transition-actions (ALL DONE) ──────────────────────────────────┐
  fsm-configurable (ALL DONE) ─────────────────────────────────────────┤
                                                                        │
                                                                        v
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  CONVERSATION 1 — Python FSM core + MCP server + entry point             │
  │                                                                          │
  │  Stories: S1.1, S1.2, S1.3                                               │
  │                                                                          │
  │  Files created/edited:                                                   │
  │    src/pathly_orchestrator/fsm.py          [CREATE]                      │
  │    src/pathly_orchestrator/mcp_server.py   [CREATE]                      │
  │    pyproject.toml                          [EDIT — add pathly-fsm]       │
  │                                                                          │
  │  Codebase state after: MCP server exists and starts. Not registered      │
  │  in any host config. No behavior change to existing installs.            │
  └────────────────────────────┬─────────────────────────────────────────────┘
                               │
                               v
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  CONVERSATION 2 — mcp_config.py registration                             │
  │                                                                          │
  │  Stories: S2.1                                                           │
  │                                                                          │
  │  Files edited:                                                           │
  │    src/install_cli/mcp_config.py  [EDIT — add pathly-fsm for Claude +   │
  │                                    Codex alongside pathly-telemetry]     │
  │                                                                          │
  │  Codebase state after: pathly-setup --apply registers pathly-fsm         │
  │  in both host configs. Users must re-run setup to pick it up.            │
  └────────────────────────────┬─────────────────────────────────────────────┘
                               │
                               v
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  CONVERSATION 3 — Skill files + orchestrator agent update                │
  │                                                                          │
  │  Stories: S3.1, S3.2                                                     │
  │                                                                          │
  │  Files edited:                                                           │
  │    src/pathly_data/core/skills/team.md         [EDIT]                    │
  │    src/pathly_data/core/skills/debug.md        [EDIT]                    │
  │    src/pathly_data/core/skills/explore.md      [EDIT]                    │
  │    adapters/claude/_meta/team_skill.yaml       [EDIT] (+ debug, explore) │
  │    adapters/codex/_meta/team_skill.yaml        [EDIT] (+ debug, explore) │
  │    src/pathly_data/core/agents/orchestrator.md [EDIT — legacy note]      │
  │    adapters/claude/_meta/orchestrator.yaml     [EDIT — legacy note]      │
  │                                                                          │
  │  Codebase state after: full integration wired. LLM agents call MCP       │
  │  tools; Python drives all FSM routing. Orchestrator agent kept as        │
  │  fallback, not primary runtime.                                          │
  └────────────────────────────┬─────────────────────────────────────────────┘
                               │
                               v
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  CONVERSATION 4 — Tests                                                  │
  │                                                                          │
  │  Stories: S4.1                                                           │
  │                                                                          │
  │  Files created:                                                          │
  │    tests/test_fsm.py         [CREATE]                                    │
  │    tests/test_mcp_server.py  [CREATE]                                    │
  │                                                                          │
  │  Codebase state after: FSM core and MCP tools covered by automated       │
  │  tests. pytest -q passes with zero failures.                             │
  └──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Files each conversation touches

```
File                                                  Conv 1  Conv 2  Conv 3  Conv 4
──────────────────────────────────────────────────────────────────────────────────
src/pathly_orchestrator/fsm.py                          C       -       -       -
src/pathly_orchestrator/mcp_server.py                   C       -       -       -
pyproject.toml                                          W       -       -       -
src/install_cli/mcp_config.py                           -       W       -       -
src/pathly_data/core/skills/team.md                     -       -       W       -
src/pathly_data/core/skills/debug.md                    -       -       W       -
src/pathly_data/core/skills/explore.md                  -       -       W       -
src/pathly_data/adapters/claude/_meta/team_skill.yaml   -       -       W       -
src/pathly_data/adapters/claude/_meta/debug_skill.yaml  -       -       W       -
src/pathly_data/adapters/claude/_meta/explore_skill.yaml-       -       W       -
src/pathly_data/adapters/codex/_meta/team_skill.yaml    -       -       W       -
src/pathly_data/adapters/codex/_meta/debug_skill.yaml   -       -       W       -
src/pathly_data/adapters/codex/_meta/explore_skill.yaml -       -       W       -
src/pathly_data/core/agents/orchestrator.md             -       -       W       -
src/pathly_data/adapters/claude/_meta/orchestrator.yaml -       -       W       -
tests/test_fsm.py                                       -       -       -       C
tests/test_mcp_server.py                                -       -       -       C
──────────────────────────────────────────────────────────────────────────────────
C = created    W = written/edited    - = not touched
```

---

## 3. Runtime flow: LLM + MCP server interaction

```
  User: /pathly team checkout-feature
                │
                ▼
  team skill (adapter-specific)
                │
                ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  LLM calls: next_action(flow="team", topic="checkout-feature")  │
  └────────────────────────┬────────────────────────────────────────┘
                           │
                           ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  Python MCP server (pathly_orchestrator.mcp_server)             │
  │                                                                 │
  │  1. load_flow("team") via importlib.resources                   │
  │  2. recover_state(storage_path, flow)                           │
  │     └── reads STATE.json + EVENTS.jsonl                         │
  │  3. route_feedback(flow, storage_path)                          │
  │     └── reads feedback/ dir → None (no open files)             │
  │  4. returns {agent: "planner", instructions: "..."}             │
  └────────────────────────┬────────────────────────────────────────┘
                           │
                           ▼
  LLM acts as planner → writes IMPLEMENTATION_PLAN.md
                           │
                           ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  LLM calls: complete_stage(flow="team", topic="checkout-feature")│
  └────────────────────────┬────────────────────────────────────────┘
                           │
                           ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  Python MCP server                                              │
  │                                                                 │
  │  1. route_feedback → None                                       │
  │  2. evaluate_transition_rules("PLANNING", storage_path)         │
  │     └── IMPLEMENTATION_PLAN.md exists? yes → "BUILDING"        │
  │  3. write_state(storage_path, "BUILDING")                       │
  │  4. append_event(EVENTS.jsonl, STATE_TRANSITION)                │
  │  5. run_transition_actions("PLANNING", "BUILDING", ...)         │
  │     └── no actions for this transition → no-op                 │
  │  6. returns {next_state: "BUILDING", agent: "builder", ...}    │
  └────────────────────────┬────────────────────────────────────────┘
                           │
                           ▼
  LLM acts as builder → writes code
                           │
                           ▼
  LLM calls: complete_stage(...)
                           │
  Python: evaluate → "REVIEWING"; run transition_actions (git_commit)
                           │
  returns {next_state: "REVIEWING", agent: "reviewer", ...}
                           │
                           ▼
  ... continues through REVIEWING → TESTING → RETRO → DONE
                           │
  complete_stage at RETRO → "DONE"
    run_transition_actions: archive-artifacts
    returns {done: true}
                           │
  LLM: pipeline complete.
```

---

## 4. Feedback blocking flow

```
  LLM (builder) writes REVIEW_FAILURES.md in feedback/
                │
                ▼
  LLM calls: complete_stage(flow="team", topic=...)
                │
                ▼
  Python MCP server:
    route_feedback(flow, storage_path)
    └── REVIEW_FAILURES.md found
        feedback_routing["REVIEW_FAILURES"] = "builder"
    returns {blocked: true, target_agent: "builder",
             instructions: "<reviewer feedback content>"}
                │
                ▼
  LLM acts as builder, resolves the feedback, deletes REVIEW_FAILURES.md
                │
                ▼
  LLM calls: complete_stage(...) again
                │
                ▼
  Python: route_feedback → None → proceed with transition
```

---

## 5. Cross-host MCP registration

```
  pathly-setup --apply
         │
         ├── mcp_config.install_mcp_config("claude")
         │     ├── adds "pathly-telemetry" to ~/.claude/settings.json  (existing)
         │     └── adds "pathly-fsm"        to ~/.claude/settings.json  (new)
         │
         └── mcp_config.install_mcp_config("codex")
               ├── adds [mcp_servers.pathly-telemetry] to ~/.codex/config.toml  (existing)
               └── adds [mcp_servers.pathly-fsm]        to ~/.codex/config.toml  (new)

  Both hosts connect to the same Python server:
    command: python
    args:    ["-m", "pathly_orchestrator.mcp_server"]
```
