# mcp-fsm-driver — Flow Diagrams

---

## 1. System overview — inputs, modules, and state machine

```
╔══════════════════════════════════════════════════════════════════╗
║                        PATHLY MCP FSM                           ║
╚══════════════════════════════════════════════════════════════════╝

  INPUT: team.flow.yaml (defines states, transitions, agents, actions)
  ┌─────────────────────────────────────────────────────────────┐
  │  states: [PLANNING, BUILDING, REVIEWING, TESTING, DONE]     │
  │  agent_map: { PLANNING: planner, BUILDING: builder, ... }   │
  │  transition_rules: { PLANNING: { on_artifact: IMPL_PLAN,    │
  │                                  default: BUILDING } }       │
  │  transition_actions: { BUILDING->REVIEWING: [git_commit] }  │
  │  feedback_routing: [HUMAN_QUESTIONS, REVIEW_FAILURES, ...]  │
  │  limits:                                                     │
  │    needs_context_per_stage: 3                                │
  │    feedback_rounds_per_stage: 2                              │
  └─────────────────────────────────────────────────────────────┘
                              │
                              │ loaded once via importlib.resources
                              ▼
╔══════════════════════════════════════════════════════════════════╗
║             pathly_orchestrator.mcp_server (Python)             ║
║                                                                  ║
║   ┌──────────────────────┐   ┌──────────────────────────────┐  ║
║   │    next_action()     │   │      complete_stage()        │  ║
║   │  flow, topic,        │   │  flow, topic,                │  ║
║   │  project_root        │   │  project_root                │  ║
║   └──────────┬───────────┘   └──────────────┬───────────────┘  ║
║              │                              │                   ║
║              └──────────┬───────────────────┘                   ║
║                         │ both call fsm.py functions            ║
║   ┌─────────────────────▼──────────────────────────────────┐   ║
║   │                    fsm.py (pure Python)                 │   ║
║   │                                                         │   ║
║   │  recover_state()  ──── reads STATE.json + EVENTS.jsonl  │   ║
║   │                        resolves limits from YAML        │   ║
║   │  route_feedback() ──── reads feedback/*.md              │   ║
║   │  evaluate_transition_rules() ── checks on_artifact      │   ║
║   │  run_transition_actions() ─── git commit, archive, etc  │   ║
║   │  write_state()    ──── writes STATE.json (atomic)       │   ║
║   │  append_event()   ──── appends to EVENTS.jsonl          │   ║
║   └─────────────────────────────────────────────────────────┘   ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## 2. State machine loop — one full pipeline pass

```
  LLM skill calls next_action()
          │
          ▼
  ┌───────────────────────────────────┐
  │  feedback/*.md present?           │
  │                                   │
  │  YES → return {blocked: true,     │──── human? → surface to user, halt
  │          target_agent, instruct}  │──── agent?  → LLM resolves, retry
  │                                   │
  │  NO  → recover_state()            │
  │        → current state: PLANNING  │
  │        → agent: planner           │
  │        → limits: {3, 2}           │
  │        → instructions: (agent.md  │
  │                        + context) │
  └───────────────────────────────────┘
          │
          │ return {current_state, agent, instructions, limits}
          ▼
  LLM acts as PLANNER
  writes IMPLEMENTATION_PLAN.md
          │
          ▼
  LLM skill calls complete_stage()
          │
          ▼
  ┌───────────────────────────────────┐
  │  feedback/*.md present?  → BLOCK  │
  │                                   │
  │  evaluate_transition_rules()      │
  │    IMPL_PLAN.md exists? → YES     │
  │    next_state = BUILDING          │
  │                                   │
  │  write_state(BUILDING)            │
  │  append_event(STATE_TRANSITION)   │
  │  run_transition_actions()         │
  │    "PLANNING->BUILDING" key?      │
  │    → no match → no-op             │
  └───────────────────────────────────┘
          │
          │ return {next_state: BUILDING, agent: builder, instructions, limits}
          ▼
  LLM acts as BUILDER
  writes code
          │
          ▼
  LLM skill calls complete_stage()  ──► REVIEWING ──► TESTING ──► DONE
                                         (reviewer)    (tester)
          │
          ▼ (when next_state == DONE)
  return {done: true}
```

---

## 3. Full skill loop — with scouts and NEEDS_CONTEXT

```
╔══════════════════════════════════════════════════════════════════╗
║                    FULL SKILL LOOP (team.md)                    ║
╚══════════════════════════════════════════════════════════════════╝

  skill calls next_action()
       │
       │  returns: { agent: "builder", instructions, limits }
       │
       ▼
  ╔════════════════════════════════════════════════════════════╗
  ║   LLM acting as BUILDER                                   ║
  ║                                                            ║
  ║   reads IMPLEMENTATION_PLAN.md                            ║
  ║   tries to act...                                         ║
  ║   "I don't know enough about src/foo/bar.py"              ║
  ║          │                                                 ║
  ║          │ outputs: NEEDS_CONTEXT                         ║
  ╚══════════╪═════════════════════════════════════════════════╝
             │
             │  skill detects NEEDS_CONTEXT
             │  needs_context_count += 1
             │  count < limits.needs_context_per_stage? → continue
             ▼
  ╔════════════════════════════════════════════════════════════╗
  ║   skill calls scout-path                                  ║
  ║                                                            ║
  ║   scout-path spawns agents in parallel:                   ║
  ║     Scout A ──► trace call path in foo/bar.py             ║
  ║     Scout B ──► find all callers of affected function     ║
  ║     Scout C ──► read related test files                   ║
  ║          │                                                 ║
  ║          ▼                                                 ║
  ║   scout-path returns: summary (TRACE.md / CONCLUSIONS.md) ║
  ╚══════════╪═════════════════════════════════════════════════╝
             │
             │  skill feeds summary back to builder
             ▼
  ╔════════════════════════════════════════════════════════════╗
  ║   LLM acting as BUILDER (resumed with context)            ║
  ║                                                            ║
  ║   now has enough info → edits files                       ║
  ║   may emit NEEDS_CONTEXT again → loop repeats             ║
  ║   eventually: done editing                                 ║
  ╚══════════╪═════════════════════════════════════════════════╝
             │
             │  builder finished, skill calls complete_stage()
             ▼
  FSM: BUILDING → REVIEWING  (Python decides, checks artifacts)
```

---

## 4. NEEDS_CONTEXT loop with limit enforcement

```
  next_action() → { instructions, limits: { needs_context_per_stage: N } }
       │
       ▼
  execute agent   [needs_context_count = 0,  feedback_round_count = 0]
       │
       ├─ NEEDS_CONTEXT emitted?
       │    needs_context_count += 1
       │    count >= limits.needs_context_per_stage?
       │      YES → warn user, halt
       │            "Agent requested context N times without completing stage"
       │      NO  → call scout-path → feed summary → resume agent
       │              └──────────────────────────────────┘ (loop)
       │
       ├─ complete_stage() → { blocked: true }?
       │    feedback_round_count += 1
       │    count >= limits.feedback_rounds_per_stage?
       │      YES → write HUMAN_QUESTIONS.md, surface to user
       │      NO  → skill resolves feedback, deletes file,
       │             calls complete_stage() again
       │              └──────────────────────────────────┘ (loop)
       │
       └─ complete_stage() → { next_state } → advance to next state
```

---

## 5. Two-layer separation — what Python owns vs what the LLM owns

```
  FSM layer  (Python, deterministic — python never calls LLM)
  ┌──────────────────────────────────────────────────────────────┐
  │                                                              │
  │  PLANNING → BUILDING → REVIEWING → TESTING → DONE           │
  │                                                              │
  │  decides: which state comes next (evaluate_transition_rules) │
  │  decides: which agent runs next (agent_map lookup)           │
  │  decides: is there open feedback? (route_feedback)           │
  │  executes: git commit, archive, progress update              │
  │  enforces: limits from YAML                                  │
  │                                                              │
  └──────────────────────────────────────────────────────────────┘

  Execution layer  (LLM, inside each state — FSM never sees this)
  ┌──────────────────────────────────────────────────────────────┐
  │                                                              │
  │  PLANNING:   [Scout] [Scout] → synthesize → write plan       │
  │  BUILDING:   [Scout] → find files → edit code                │
  │  REVIEWING:  [Scout] → read diffs → write REVIEW_FAILURES    │
  │  TESTING:    run tests → write TEST_FAILURES if any          │
  │                                                              │
  │  scouts, NEEDS_CONTEXT cycles, and feedback resolution       │
  │  are all invisible to the FSM                                │
  │                                                              │
  └──────────────────────────────────────────────────────────────┘
```

---

## 6. Filesystem state layout

```
  pathly/plans/<topic>/
  ├── STATE.json          ← current FSM state (written atomically by write_state)
  ├── EVENTS.jsonl        ← append-only audit log of all transitions
  ├── PROGRESS.md         ← human-readable progress tracker
  ├── IMPLEMENTATION_PLAN.md   ← artifact that triggers PLANNING→BUILDING
  └── feedback/
      ├── HUMAN_QUESTIONS.md   → blocks pipeline, surfaces to user (user deletes)
      ├── ARCH_FEEDBACK.md     → routes to architect agent
      ├── REVIEW_FAILURES.md   → routes to builder to fix
      └── TEST_FAILURES.md     → routes to builder to fix

  pathly/pipeline-walkthrough/<topic>/artifacts/
  └── REVIEW_FAILURES_conv1_attempt1.md   ← archived by run_transition_actions
```

---

## 7. build_prompt routing — which helper is called when

```
  MCP server needs to produce instructions string
          │
          ├─ normal response (not blocked)?
          │    state_name known → build_prompt(flow, state_name, storage_path)
          │    → looks up agent_map[state_name] → loads agent.md
          │
          ├─ blocked, target_agent == "human"?
          │    → return feedback file contents verbatim
          │       build_prompt NOT called
          │
          └─ blocked, target_agent == <agent_name>?
               → build_prompt_for_agent(flow, agent_name, storage_path)
                  → loads agent.md directly (no agent_map lookup)

  NEVER pass feedback["target_agent"] to build_prompt()
  — agent names are not keys in agent_map → KeyError
```

---

## 8. Three-level transition routing — evaluation order

```
  evaluate_transition_rules(flow, current_state, storage_path)
          │
          ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  LEVEL 1 — on_artifact  (pure Python, Path.exists)         │
  │                                                             │
  │  for each entry in transition_rules[state]["on_artifact"]:  │
  │    if storage_path / entry["file"] exists:                  │
  │      return entry["next"]   ◄── STOP, cheapest check first  │
  └───────────────────────────────┬─────────────────────────────┘
                                  │ no match
                                  ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  LEVEL 2 — on_content  (pure Python, regex/contains)       │
  │                                                             │
  │  for each entry in transition_rules[state]["on_content"]:   │
  │    read file (skip if missing)                              │
  │    if entry["contains"] in contents:                        │
  │      return entry["next"]   ◄── STOP                        │
  │    if entry["regex"] matches:                               │
  │      return entry["next"]   ◄── STOP                        │
  └───────────────────────────────┬─────────────────────────────┘
                                  │ no match
                                  ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  LEVEL 3 — decide  (constrained LLM classifier)            │
  │                                                             │
  │  fsm.py returns sentinel dict — does NOT call LLM:         │
  │    {"decide": True, "context_file": "REVIEW_FAILURES.md",  │
  │     "question": "...", "options": {...}, "default": "..."}  │
  │                                                             │
  │  mcp_server.py calls resolve_decide():                     │
  │    read context_file                                        │
  │    call claude-haiku (max_tokens=10, temperature=0):        │
  │      "Choose one: option_a, option_b, option_c"            │
  │      reply = strip(response)                                │
  │    reply in options?                                        │
  │      YES → return options[reply]  ◄── mapped next state     │
  │      NO  → return decide["default"]                         │
  │    append DECIDE_ROUTING event either way                   │
  └───────────────────────────────┬─────────────────────────────┘
                                  │ no decide block / LLM failed
                                  ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  FALLBACK — default                                         │
  │    transition_rules[state]["default"]                       │
  │    or transitions[state][0]                                 │
  │    or raise ValueError                                      │
  └─────────────────────────────────────────────────────────────┘
```

---

## 9. Decision tree — non-linear pipeline example

```
  With three-level routing the FSM becomes a DAG, not a line:

                        PLANNING
                           │
                        BUILDING
                           │
                        REVIEWING
                        /   │   \
                       /    │    \
              L2 match /    │     \ L3 decide
     contains "CRITICAL"    │      \
                /       default     architecture
               /            │            \
      SECURITY_REVIEW    BUILDING     ARCH_REVIEW
               \            │            /
                \           │           /
                 └──────────┼──────────┘
                            │
                         TESTING
                            │
                           DONE

  Python owns every branch decision.
  LLM (haiku) only participates in the L3 "decide" branch —
  choosing between 2–3 predefined options, never inventing paths.
```

╔══════════════════════════════════════════════════════════════════════╗
║  LAYER 1 — ORCHESTRATION SPEC  (authored by human or wizard)        ║
║                                                                      ║
║   future: wizard/form UI                                            ║
║   ┌──────────────────────────────────────────────┐                  ║
║   │  "I want a pipeline that:                    │                  ║
║   │   - plans → builds → reviews → tests         │                  ║
║   │   - uses planner/builder/reviewer agents     │                  ║
║   │   - commits on each transition               │                  ║
║   │   - max 3 scout calls per stage"             │                  ║
║   └──────────────────┬───────────────────────────┘                  ║
║                      │ generates                                     ║
║                      ▼                                               ║
║             team.flow.yaml                                           ║
║   ┌──────────────────────────────────────────────┐                  ║
║   │  states, agent_map, transition_rules,        │                  ║
║   │  transition_actions, feedback_routing,       │                  ║
║   │  limits                                      │                  ║
║   └──────────────────────────────────────────────┘                  ║
╚══════════════════════════════════════════════════════════════════════╝
                              │
                              │ loaded at runtime via importlib.resources
                              ▼
╔══════════════════════════════════════════════════════════════════════╗
║  LAYER 2 — PYTHON FSM MCP SERVER  (deterministic, no LLM)           ║
║                                                                      ║
║   pathly_orchestrator.mcp_server                                     ║
║                                                                      ║
║   holds:  core/agents/*.md     ← agent contracts (planner, builder) ║
║           core/skills/*.md     ← skill loop definitions             ║
║           core/flows/*.yaml    ← all flow specs (team/debug/explore)║
║                                                                      ║
║   exposes two MCP tools:                                             ║
║   ┌─────────────────────────┐  ┌─────────────────────────────────┐  ║
║   │  next_action()          │  │  complete_stage()               │  ║
║   │  → which agent + why    │  │  → advance state + next agent   │  ║
║   │  → what instructions    │  │  → run git/archive actions      │  ║
║   │  → what limits apply    │  │  → enforce limits               │  ║
║   └─────────────────────────┘  └─────────────────────────────────┘  ║
║                                                                      ║
║   Python decides: routing, transitions, feedback priority, limits    ║
║   Python never calls LLM                                             ║
╚══════════════════════════════════════════════════════════════════════╝
                              │
                              │ MCP tool calls (host-native syntax)
                              ▼
╔══════════════════════════════════════════════════════════════════════╗
║  LAYER 3 — LLM EXECUTION  (Claude / Codex / Copilot)                ║
║                                                                      ║
║   receives:  agent contract + context from Layer 2                   ║
║   does:      actual work — plans, writes code, reviews, tests        ║
║   uses:      scouts when it needs codebase context                   ║
║   signals:   complete_stage() when done with a stage                 ║
║                                                                      ║
║   ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  ║
║   │ Claude Code  │  │    Codex     │  │  Copilot / other         │  ║
║   │ (claude.md   │  │ (codex.yaml  │  │  (adapter per host)      │  ║
║   │  adapter)    │  │  adapter)    │  │                          │  ║
║   └──────────────┘  └──────────────┘  └──────────────────────────┘  ║
║                                                                      ║
║   LLM never decides: which state, which agent, when to commit        ║
║   LLM only decides: HOW to do the work it was given                  ║
╚══════════════════════════════════════════════════════════════════════╝