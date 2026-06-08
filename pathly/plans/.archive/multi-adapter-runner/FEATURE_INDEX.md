---
name: Feature Index
---
# Multi-Adapter Runner — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.

---

## What this feature does

Turns Pathly's autonomous runner into a **multi-adapter command center backend**. Three pieces:
1. A single declarative **`core/adapters.yaml`** mapping each adapter (claude/codex/copilot) to its CLI command shape, read by Python at runtime and exported to TS at build time (`adapters.gen.ts`) — so the headless and Studio paths can never drift.
2. An **autonomous supervisor**: a controllable, threaded run loop with `RunnerState` (pause/abort/cost+iteration caps, decision-via-FSM, session continuity).
3. A **control API + SSE**: `/runner/*` endpoints and an `/events/runner` stream so a UI (the `hq-panel` feature) can drive the loop and receive live menus.

The FSM stays passive — the supervisor sits above it and calls it. This is the Python backend half; the Studio UI is the sibling **`hq-panel`** feature.

## Dependencies

- **Requires `multi-adapter-routing` Conv 1 shipped** — that feature makes `/next_action` return `preferred_adapter`, which this runner consumes. If `preferred_adapter` is absent, the runner treats it as `""` (uses the default adapter / current behavior).
- **Blocks `hq-panel`** — the Studio feature consumes this feature's `/runner/*` endpoints, `/events/runner` SSE, and generated `adapters.gen.ts`.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status |

### Optional plan files

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Adapter-map keystone, control API, runner state, security |
| `EDGE_CASES.md` | yes | Caps, abort, session degradation, codex cost-blindness |
| `HAPPY_FLOW.md` | yes | Golden-path autonomous run |
| `FLOW_DIAGRAM.md` | yes | Supervisor loop + control + SSE diagram |

---

## Codebase touchpoints

**Verify each path exists before editing (glob it).**

| Codebase file | Conversation | What changes |
|---|---|---|
| `src/pathly_data/core/adapters.yaml` (NEW) | Conv 1 | Adapter→command map: per-adapter `terminal_kind`, `headless` argv template, `resume` mode, `autonomy_flag`, `parse` |
| `src/pathly_orchestrator/adapters.py` (NEW) | Conv 1 | `resolve_command(adapter, prompt, model, session)` → `{argv, terminal_kind, supports_resume}`; reads adapters.yaml via `importlib.resources` |
| `scripts/gen_adapters_ts.py` (NEW) | Conv 1 | Reads adapters.yaml, writes the TS mirror; a test asserts the committed mirror is up to date |
| `studio/src/renderer/src/lib/adapters.gen.ts` (NEW, generated) | Conv 1 | Generated TS adapter map consumed by `hq-panel` (verify the `lib/` location) |
| `src/pathly_orchestrator/runner.py` (MODIFY) | Conv 1, 2 | Conv 1: `invoke_agent` builds its command via `resolve_command` (claude behavior unchanged). Conv 2: supervisor reuses `invoke_agent`; `handle_decide`'s blocking `input()` is replaced by state-driven decision waiting |
| `src/pathly_orchestrator/supervisor.py` (NEW) | Conv 2 | `RunnerState` dataclass + in-memory registry (keyed by topic, under a lock) + threaded run loop; boundary pause/abort/caps; `RUNNER_STATE.json` write-through mirror; session continuity |
| `src/pathly_orchestrator/http_server.py` (MODIFY) | Conv 3 | 9 `/runner/*` endpoints + `/events/runner` SSE; `_broadcast_runner` twin of the existing `_broadcast_sse` |
| `tests/` | Conv 1, 2, 3 | resolve_command + gen-staleness (Conv 1); supervisor with a fake FSM client (Conv 2); control endpoints + SSE (Conv 3) |

---

## Canonical `adapters.yaml` shape (the keystone — single source of truth)

```yaml
claude:
  terminal_kind: claude
  headless: [claude, "-p", "{prompt}", "--model", "{model}", "--output-format", json]
  autonomy_flag: "--dangerously-skip-permissions"   # included only if autonomy[adapter] is true
  resume: { mode: flag, flag: "--resume", arg: "{session_id}" }
  parse: claude_json
codex:
  terminal_kind: codex
  headless: [codex, exec, "{prompt}", "--model", "{model}"]
  autonomy_flag: "--full-auto"
  resume: { mode: flag, flag: "--continue" }
  parse: codex_json          # may not report cost — see EDGE_CASES
copilot:
  terminal_kind: shell
  headless: null             # no headless mode → supports_resume = false
  autonomy_flag: null
  resume: null
  parse: null
```

Python reads this at runtime; `scripts/gen_adapters_ts.py` emits the TS mirror. The TS file is **generated, never hand-authored** — a staleness test is the anti-drift guarantee.

---

## `/events/runner` SSE event schema (exact fields)

```
{"type":"connected"}
{"type":"STAGE_CHANGE","topic":str,"state":str,"adapter":str,"iteration":int}
{"type":"DECISION_MENU","topic":str,"menu":{"question":str,"options":obj,"default":str}}
{"type":"RUNNER_STATUS","topic":str,"status":"running"|"paused"|"awaiting_decision"|"aborted"|"done"|"error"}
{"type":"COST_UPDATE","topic":str,"cost_usd":float,"iterations":int,"max_cost_usd":float}
{"type":"SESSION","topic":str,"adapter":str,"action":"continued"|"opened","degraded":bool}
{"type":"RUNNER_ERROR","topic":str,"message":str,"kind":"cap_exceeded"|"subprocess"}
```

---

## Conversation map

| Conv | Title | Stories | Status | Key files |
|---|---|---|---|---|
| 1 | Adapter→command contract | S1 | TODO | `core/adapters.yaml`, `adapters.py`, `scripts/gen_adapters_ts.py`, `runner.py`, `tests/` |
| 2 | Autonomous supervisor + RunnerState | S2 | TODO | `supervisor.py`, `runner.py`, `tests/` |
| 3 | Control API + /events/runner SSE | S3 | TODO | `http_server.py`, `tests/` |

**Dependency:** `1 → 2 → 3` (strict). After Conv 3 a **hard CI gate** must pass (full Python path drivable by curl) before `hq-panel` work begins.

---

## Feedback files (transient)

Live in `pathly/plans/multi-adapter-runner/feedback/`. A file existing = issue open: `REVIEW_FAILURES.md` (Reviewer→Builder), `TEST_FAILURES.md` (Tester→Builder), `IMPL_QUESTIONS.md` (Builder→Planner), `DESIGN_QUESTIONS.md` (Builder→Architect), `HUMAN_QUESTIONS.md` (Any→User).
