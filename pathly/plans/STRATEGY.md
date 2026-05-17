# Pathly — Dual-Engine Strategy

> Read this before working on any plan that touches routing, orchestration,
> or the flow YAML. It explains the architectural goal that all plans serve.

---

## The goal

Pathly runs two routing engines **side by side on the same codebase**:

| Engine | How routing works | Who decides next state |
|---|---|---|
| **LLM-driven** | `orchestrator.md` reads flow YAML as a prompt | The LLM |
| **Python FSM** | `pathly-mcp-server` reads flow YAML as code | Python (deterministic) |

The user picks which engine to use **at start time** — not at install time, not
at deploy time. Both engines are always installed. Both read the same flow YAMLs,
the same agents, the same skills, the same templates.

---

## Why both, not one

The comparison is the point. Same prompts, same flows, different routing engine.
Any difference in output is caused by the engine alone — not by different prompts
or different flows. This gives a measurable, scientific comparison between:

- AI-driven orchestration (flexible, non-deterministic, context-rich)
- Code-driven orchestration (deterministic, auditable, zero hallucination risk)

Neither is "the winner" until the comparison runs. Both ship.

---

## How the user picks

At the start of every flow (`/pathly team`, `/pathly debug`, `/pathly explore`):

```
Routing engine:
[1] Python FSM  — deterministic, MCP-driven
[2] LLM driven  — orchestrator reads YAML
```

The choice is stored in `STATE.json`:

```json
{ "current": "STORMING", "flow": "team", "engine": "python-mcp" }
```

Every subsequent command (`go`, `pause`, `fix`, `ff`) reads `engine` from
`STATE.json` and routes accordingly. The user is never asked again for that topic.

---

## What is shared (never duplicated)

```
src/pathly_data/core/
├── agents/        ← identical for both engines
├── skills/        ← identical for both engines
├── templates/     ← identical for both engines
└── flows/         ← identical YAML, read by both engines
```

The flow YAML format is the contract between the two engines. Both must be
able to read the same YAML without modification.

---

## What differs per engine

```
LLM-driven:
  src/pathly_data/core/agents/orchestrator.md
    ← reads flow YAML as a prompt
    ← decides routing at each step
    ← writes STATE.json, EVENTS.jsonl

Python FSM:
  src/pathly_orchestrator/mcp_server.py
    ← reads flow YAML as Python data
    ← executes routing deterministically
    ← writes STATE.json, EVENTS.jsonl (same format)
```

Both engines write `STATE.json` and `EVENTS.jsonl` in the **same format** so
that pathly-studio can read from either without knowing which engine produced it.

---

## What pathly-studio sees

pathly-studio auto-detects which engine is active for the current topic:

```
ping MCP server (500ms timeout)
  → alive:   read state via MCP tool call    (Python FSM active)
  → timeout: watch STATE.json + EVENTS.jsonl (LLM-driven active)
```

The monitor panel shows identical UI regardless of engine. The connection status
badge tells the user which source is active: `● MCP live` or `○ File watch`.

---

## Implementation order

```
1. LLM-driven        already complete — do not touch
2. mcp-fsm-driver    adds Python FSM alongside LLM engine
3. pathly-commands-v2  new commands work with both engines
4. pathly-studio       UI connects to both engines
```

The LLM-driven engine is frozen. `mcp-fsm-driver` is purely additive.

---

## What "additive" means for mcp-fsm-driver

- `orchestrator.md` is NOT modified
- Flow YAMLs are NOT modified
- Agents and skills are NOT modified
- The MCP server is a new Python module that reads existing flow YAMLs
- The `go`/`start`/`team` skills get one new branch: `if engine == "python-mcp"`

Nothing existing breaks. Switching back to LLM-driven for any topic requires
only changing `engine` in `STATE.json`.
