# Flow Diagram — pathly-observability

## Phase event flow — single build conversation

```
build.md skill execution
│
├─ [Step 1] Phase 0 pre-flight
│
├─ [Step 2] PHASE_START analyze
│   └─ POST /record_phase {event_type: PHASE_START, phase: analyze}
│        └─ http_server validates → appends to EVENTS.jsonl
│
├─ [Step 3] Read files, understand scope
│
├─ [Step 4] PHASE_DONE analyze
│   └─ POST /record_phase {event_type: PHASE_DONE, phase: analyze}
│
├─ [Step 5] PHASE_START scout
│   └─ POST /record_phase {event_type: PHASE_START, phase: scout}
│
├─ [Step 6] Spawn scout sub-agents (0–4 depending on rigor)
│
├─ [Step 7] PHASE_DONE scout  [scouts_count=N]
│   └─ POST /record_phase {event_type: PHASE_DONE, phase: scout, scouts_count: N}
│
├─ [Step 8] PHASE_START implement
│   └─ POST /record_phase {event_type: PHASE_START, phase: implement}
│
├─ [Step 9] Write code, edit files
│
├─ [Step 10] Run verify command
│
├─ [Step 11] PHASE_DONE implement  [total_tokens, tool_uses]
│   └─ POST /record_phase {event_type: PHASE_DONE, phase: implement, total_tokens: N, tool_uses: N}
│
└─ [Step 12] log-agent-done (existing AGENT_DONE event — unchanged)
    └─ POST /record_activity {...}
         └─ appends AGENT_DONE to EVENTS.jsonl
```

---

## /record_phase endpoint internals

```
POST /record_phase
│
├─ Parse JSON body
│
├─ Validate required fields (feature, agent, phase, event_type)
│   └─ missing → HTTP 400 {"error": "missing required field: <field>"}
│
├─ Validate event_type in {PHASE_START, PHASE_DONE}
│   └─ invalid → HTTP 400 {"error": "invalid event_type: <value>"}
│
├─ Validate phase in allowed enum
│   └─ invalid → HTTP 400 {"error": "invalid phase: <value>"}
│
├─ Check pathly/plans/<feature>/ directory exists
│   └─ missing → HTTP 400 {"error": "feature directory not found: ..."}
│
├─ Build event dict:
│   {schema_version: 1, type: <event_type>, phase: <phase>, agent: <agent>,
│    feature: <feature>, ts: <utcnow ISO-8601>}
│   + optional fields if present: conv, total_tokens, tool_uses, scouts_count, summary
│   (omit fields with None values)
│
├─ Append JSON line to pathly/plans/<feature>/EVENTS.jsonl
│   (create file if not exists, append-only)
│
└─ Return HTTP 200 {"status": "recorded"}
```

---

## _is_exempt() logic (updated)

```
_is_exempt(path, flow_yaml)
│
├─ hardcoded_prefixes = ["pathly/plans/", ".tsbuildinfo"]
│
├─ yaml_prefixes = flow_yaml.get("scope_gate", {}).get("exempt_prefixes", [])
│
├─ all_prefixes = hardcoded_prefixes + yaml_prefixes
│
└─ return any(path.startswith(p) or path.endswith(p) for p in all_prefixes)
```

---

## EVENTS.jsonl timeline — full feature lifecycle

```
pathly/plans/my-feature/EVENTS.jsonl
─────────────────────────────────────
{"type":"PHASE_START","phase":"plan","agent":"planner","conv":1,...}
{"type":"PHASE_DONE","phase":"plan","agent":"planner","conv":1,...}
{"type":"AGENT_DONE","agent":"planner","conv":1,...}          ← existing, unchanged

{"type":"PHASE_START","phase":"analyze","agent":"builder","conv":2,...}
{"type":"PHASE_DONE","phase":"analyze","agent":"builder","conv":2,...}
{"type":"PHASE_START","phase":"scout","agent":"builder","conv":2,...}
{"type":"PHASE_DONE","phase":"scout","agent":"builder","conv":2,"scouts_count":2,...}
{"type":"PHASE_START","phase":"implement","agent":"builder","conv":2,...}
{"type":"PHASE_DONE","phase":"implement","agent":"builder","conv":2,"total_tokens":8200,...}
{"type":"AGENT_DONE","agent":"builder","conv":2,...}          ← existing, unchanged

{"type":"PHASE_START","phase":"analyze","agent":"reviewer","conv":3,...}
{"type":"PHASE_DONE","phase":"analyze","agent":"reviewer","conv":3,...}
{"type":"PHASE_START","phase":"review","agent":"reviewer","conv":3,...}
{"type":"PHASE_DONE","phase":"review","agent":"reviewer","conv":3,...}
{"type":"AGENT_DONE","agent":"reviewer","conv":3,...}         ← existing, unchanged
─────────────────────────────────────
```

---

## Adapter propagation flow

```
Conv 4 completion
│
├─ All 6 agent files edited (rigor_contract + stage_brief added)
│
├─ pathly-setup claude --apply
│   └─ reads src/pathly_data/core/agents/ + src/pathly_data/claude/_meta/
│   └─ writes to ~/.claude/agents/ (or equivalent install path)
│   └─ exit 0
│
└─ pathly-setup codex --apply
    └─ reads src/pathly_data/core/agents/ + src/pathly_data/codex/_meta/
    └─ writes to ~/.codex/ + ~/.agents/ (or equivalent install path)
    └─ exit 0
```
