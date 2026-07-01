# Architecture Proposal — pathly-observability

## Problem statement

Today, EVENTS.jsonl records only `AGENT_DONE` events — a single data point per conversation.
There is no visibility into which internal phase (analyze, scout, implement, review, test) was
active at any point, how long each phase took, or how many sub-agents were spawned within a phase.
Rigor levels exist conceptually but are not enforced or recorded anywhere.

---

## Design decisions

### Decision 1: New endpoint, not extending /record_activity

**Option A:** Add a `phase` field to the existing `/record_activity` endpoint.
**Option B (chosen):** Create a separate `/record_phase` endpoint.

**Rationale for B:** `/record_activity` is tied to `AGENT_DONE` semantics. Adding a `phase`
field would conflate phase events with agent completion events, making EVENTS.jsonl harder to
parse. A dedicated endpoint has a clear single responsibility and a distinct event schema.
Backwards compatibility with existing callers of `/record_activity` is preserved automatically.

### Decision 2: JSONL append, no database

Phase events are appended to the same `EVENTS.jsonl` file that already exists per feature.
No new storage format, no SQLite, no structured log service.

**Rationale:** The existing EVENTS.jsonl pattern is already used across the framework. Adding
phase events to the same file keeps all feature history in one place. The file is small enough
that full-scan reads are acceptable. If analytics become a requirement, a separate query layer
can be added without changing the write path.

### Decision 3: Best-effort logging in skills

Phase log calls in skill files use curl with `|| true` (or equivalent). If the HTTP server
is not running, the call is silently dropped. Skill execution is never blocked by logging.

**Rationale:** Phase logging is observability infrastructure, not correctness infrastructure.
Making it optional under degraded conditions prevents it from becoming a reliability hazard.
The trade-off is that EVENTS.jsonl may have gaps — this is acceptable.

### Decision 4: YAML-driven exempt prefixes, hardcoded defaults preserved

`_is_exempt()` reads `scope_gate.exempt_prefixes` from the active flow YAML when present.
The existing hardcoded defaults (`pathly/plans/` and `.tsbuildinfo`) are always active.

**Rationale:** Removing the hardcoded defaults would break existing deployments that rely on
them without a flow YAML. Extending via YAML allows new adapter paths to be added without
Python source edits. The YAML is already loaded at FSM init time, so there is no new I/O cost.

### Decision 5: rigor_contract tables embedded in agent files, not a shared file

Each agent file contains its own role-specific rigor table rather than importing from a
shared document.

**Rationale:** Agent files are deployed individually via pathly-setup. A shared rigor document
would need to be deployed alongside every agent file, adding adapter complexity. Role-specific
tables are more useful to agents because they describe concrete actions for that role, not
generic levels.

### Decision 6: stage_brief placement is early in the file

`## Stage brief` is placed near the top of each agent file (after the opening description,
before the first major section).

**Rationale:** Agent files are passed as context to Claude Code sessions. The first content
the model reads sets the frame for the entire session. A brief at the top means every agent
session opens with a clear statement of what the stage produces and how to know it is done.

---

## Data flow

```
Skill file (build.md)
  └─ calls log-phase utility or inline curl
       └─ POST /record_phase  →  http_server.py
            └─ validates fields
            └─ builds event dict (omits None values)
            └─ appends JSON line to pathly/plans/<feature>/EVENTS.jsonl
```

---

## What this does NOT change

- The `AGENT_DONE` event schema is unchanged. `/record_activity` is unchanged.
- `recover_state()` silent failure on JSONDecodeError is noted in scout findings but is out
  of scope. It is a separate reliability issue.
- `route_feedback()` returning `None` for unrecognized files is out of scope.
- Studio / Electron frontend is not changed.
- antigravity and copilot adapters are not touched (neither has a `_meta/` directory yet).

---

## Future considerations (not in scope)

- Phase duration analytics: compute elapsed time between PHASE_START and PHASE_DONE timestamps
- Scout budget enforcement: reject PHASE_DONE scout events where scouts_count exceeds rigor limit
- Telemetry dashboard in Studio showing phase timeline per feature
- Locking or write queuing for concurrent /record_phase calls (EC-06)
