# FLOW_DIAGRAM.md — fsm-transition-actions

_Text-based diagrams. No external tools required._

---

## 1. Three-conversation delivery sequence

```
  fsm-configurable (ALL DONE) ──────────────────────────────┐
  agent-architecture-refactor (ALL DONE) ───────────────────┘
                                                             │
                                                             v
  ┌─────────────────────────────────────────────────────────────────────┐
  │  CONVERSATION 1 — Extend flow YAMLs                                 │
  │                                                                     │
  │  Stories: S1.1, S1.2                                                │
  │                                                                     │
  │  Files touched:                                                     │
  │    src/pathly_data/core/flows/team.flow.yaml    [ADD block]         │
  │    src/pathly_data/core/flows/debug.flow.yaml   [ADD key]           │
  │    src/pathly_data/core/flows/explore.flow.yaml [ADD key]           │
  │                                                                     │
  │  Codebase state after: YAML keys present, not yet read.             │
  │  Orchestrator still has hardcoded side-effect logic — no regression. │
  └────────────────────────────┬────────────────────────────────────────┘
                               │  (flow YAMLs carry transition_actions)
                               v
  ┌─────────────────────────────────────────────────────────────────────┐
  │  CONVERSATION 2 — Generalize orchestrator.md                        │
  │                                                                     │
  │  Stories: S2.1                                                      │
  │                                                                     │
  │  Files touched:                                                     │
  │    src/pathly_data/core/agents/orchestrator.md                      │
  │      INSERT: transition_actions executor (after EVENTS.jsonl write) │
  │      REMOVE: autoFlow commits block (lines 125-135)                 │
  │      REMOVE: artifact archiving block (lines 142-156)               │
  │                                                                     │
  │  Codebase state after: fully wired end-to-end. All three flows      │
  │  drive their side effects from YAML. Orchestrator is a pure FSM.    │
  └────────────────────────────┬────────────────────────────────────────┘
                               │
               ┌───────────────┴────────────────────────────┐
               │                                            │
               │  BLOCKED until fsm-configurable Phase 5c   │
               │  delivers:                                  │
               │    - validate_flow_cli in state.py          │
               │    - _REQUIRED_FLOW_KEYS in state.py        │
               │                                            │
               └───────────────┬────────────────────────────┘
                               │
                               v
  ┌─────────────────────────────────────────────────────────────────────┐
  │  CONVERSATION 3 — Extend state.py validation  [BLOCKED]             │
  │                                                                     │
  │  Stories: S3.1                                                      │
  │                                                                     │
  │  Files touched:                                                     │
  │    src/pathly_orchestrator/state.py                                 │
  │      ADD: transition_actions to known optional keys                 │
  │      ADD: action name validation (vocabulary check)                 │
  │      ADD: FROM->TO key validation (must exist in transitions list)  │
  │      ADD: expose transition_actions dict for orchestrator runtime   │
  │                                                                     │
  │  Codebase state after: typos in action names and transition keys    │
  │  are caught at validate time, not silently at runtime.              │
  └─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Files each conversation touches

```
File                                              Conv 1   Conv 2   Conv 3
─────────────────────────────────────────────────────────────────────────
src/pathly_data/core/flows/team.flow.yaml           W        -        -
src/pathly_data/core/flows/debug.flow.yaml          W        -        -
src/pathly_data/core/flows/explore.flow.yaml        W        -        -
src/pathly_data/core/agents/orchestrator.md         -        W        -
src/pathly_orchestrator/state.py                    -        -        W
─────────────────────────────────────────────────────────────────────────
W = written/edited    - = not touched
```

---

## 3. Data flow: YAML declaration → executor → side effects

```
  flow YAML (team.flow.yaml)
  ┌──────────────────────────────────────────────────────┐
  │ transition_actions:                                  │
  │   "BUILDING->REVIEWING":                             │
  │     - type: git_commit                               │
  │       message: "feat: complete building stage"       │
  │   "->DONE":                                          │
  │     - type: archive_artifacts                        │
  └──────────────────┬───────────────────────────────────┘
                     │  orchestrator reads at startup
                     v
  orchestrator.md — FSM loop (one iteration)
  ┌──────────────────────────────────────────────────────┐
  │  1. Read current state from STATE.json               │
  │  2. Look up agent in agent_map → spawn sub-agent     │
  │  3. Sub-agent returns outcome                        │
  │  4. Evaluate transition_rules → determine NEW_STATE  │
  │  5. Write NEW_STATE to STATE.json                    │
  │  6. Append event to EVENTS.jsonl                     │
  │  7. [NEW] Execute transition_actions ──────────────┐ │
  │     a. construct key "PREV_STATE->NEW_STATE"       │ │
  │     b. exact key lookup in transition_actions      │ │
  │     c. if no exact match: wildcard "->NEW_STATE"   │ │
  │     d. if feedback file present: skip git_commit   │ │
  │        and update_progress; allow archive_artifacts│ │
  │     e. execute matched actions in YAML order       │ │
  └───────────────────────────────────────┬────────────┘ │
                                          │              │
                     ┌────────────────────┘              │
                     v                                   │
  ┌──────────────────────────────────────────────────────┘
  │  Action dispatch
  │
  │  git_commit ────────────────► git add -A
  │                                git commit -m <message>
  │
  │  update_progress ──────────► PROGRESS.md
  │    mark: conv_done              mark current conv row DONE
  │    mark: all_phases_done        mark all phases in conv DONE
  │    (conv number from STATE.json)
  │
  │  archive_artifacts ────────► pipeline-walkthrough/<topic>/artifacts/
  │                                dual-write all feedback files
  │                                naming: FILENAME_conv<N>_attempt<M>.md
  └──────────────────────────────────────────────────────
```

---

## 4. Conv 3 dependency: fsm-configurable Phase 5c gate

```
  fsm-configurable feature
  └── Phase 5c (must be DONE)
        │
        │  delivers
        ▼
  src/pathly_orchestrator/state.py
    ├── validate_flow_cli          ← Conv 3 insertion point
    └── _REQUIRED_FLOW_KEYS        ← Conv 3 insertion point

        │
        │  enables
        ▼
  fsm-transition-actions Conversation 3
    └── state.py gains:
          - transition_actions in known optional keys
          - action vocabulary check (git_commit | update_progress | archive_artifacts)
          - FROM->TO key cross-reference against transitions list
          - expose transition_actions dict

        │
        │  enables
        ▼
  pathly-validate-flow CLI
    pathly-validate-flow --flow team.flow.yaml
    ├── PASS: clean flow (transition_actions valid)
    ├── WARN: transition_actions absent (optional — no error)
    └── ERROR: unknown action type / invalid transition key
```

---

## 5. Failure modes at a glance

```
  Failure point                   Conv where caught    Behavior
  ──────────────────────────────────────────────────────────────────────
  Unknown action type             Conv 2 (executor)    halt + report
                                  Conv 3 (validator)   error at load time
  Missing message on git_commit   Conv 2 (executor)    halt + report
                                  Conv 3 (validator)   error at load time
  FROM->TO not in transitions     Conv 3 (validator)   error at load time
                                  Conv 2 (executor)    dead key, no-op
  transition_actions absent       Conv 2 (executor)    no-op (empty map)
                                  Conv 3 (validator)   warn only
  transition_actions: {}          Conv 2 (executor)    no-op
                                  Conv 3 (validator)   no warning
  Exact + wildcard both present   Conv 2 (executor)    exact wins; wildcard skipped
  git_commit + feedback file      Conv 2 (executor)    skip git_commit + update_progress
  Mid-sequence action failure     Conv 2 (executor)    halt + report; no rollback
  Conv 3 started before Phase 5c  operator gate        detection: grep state.py
  ──────────────────────────────────────────────────────────────────────
```
