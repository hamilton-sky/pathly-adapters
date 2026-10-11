# Implementation Plan — Chief Agent

Each ticket maps to one board task. Design: [SPEC.md](SPEC.md); acceptance:
[USER_STORIES.md](USER_STORIES.md).

**Prerequisite:** role-read-policy RRP-1, RRP-2, RRP-3
([plan](../role-read-policy/IMPLEMENTATION_PLAN.md)). The chief's identity, its read wall and
the provenance gate on promotion all come from there. Build order: role-read-policy's
feature-flow plan (RRP-1..3) reaches DONE → this plan (`tasks/01..13`) on the same branch →
role-read-policy RRP-2b, RRP-4..8 later.

Layering and size rules as in role-read-policy: new endpoints get a **new blueprint domain**
(`blueprints/chief/`), new tables get a **new migration module**, and near-limit files
(`runner/comms_context.py`, `blueprints/comms/messages_write.py`, `studio/src/main/ipc/terminal.ts`,
`db/migrations.py`) only gain a call site.

## Ticket map

```
CHF-1 contract + fragments ─► CHF-2 thread/inbox + turn ─► CHF-3 inbox events ─► CHF-5 Studio chat
                                         │                         │
                                         └─► CHF-4 standing directives (needs RRP-3)
CHF-6 episodic tier (needs RRP-1, RRP-3) ─► CHF-7 scheduled promote ─► CHF-8 limits + session rebuild
```

---

## CHF-1 — Role contract + fragments (P1) · P0 · Low

New files
- `src/pathly_data/core/agents/support/chief.md` — role contract (absorbs `director.md` routing:
  rigor + executor choice). Model: opus/sonnet decided in review.
- `src/pathly_data/core/skills/fragments/chief-tools.md` — allowed calls as `curl` with
  `X-Pathly-Run-Token`: `POST /comms/goals/decompose|run|stop`, `GET /comms/goals`,
  `GET /runner/status`, `GET /runs`, `POST /runs/<id>/<action>`, `POST /runner/agent-answer`,
  `POST /comms/post`, `POST /comms/search`.
- `chief-rules.md` — never edit files or run stages; never answer/approve for the human without a
  quote; confirm before stop / `strict`.
- `chief-status.md` — summarize from rollups + run summaries, cite ids.
- Adapter `_meta/*.yaml` entries so `pathly-setup … --apply` and `python -m build` include it.

Changed files
- `runner/read_policy.py` — `chief` built-in row (if RRP-1 did not already add it).

Tests: composed chief prompt contains the tool list and rules (fragment snapshot); adapter build
check passes.

---

## CHF-2 — Chief thread, inbox and one turn (P2) · P0 · Med · needs CHF-1, RRP-2

New files
- `db/queries/chief.py` + `db/migrations_chief.py` — tables `chief_thread(id, project_root, role
  [human|chief], text, ts, run_id)`, `chief_inbox(id, project_root, kind, ref_id, ts,
  consumed_at)`, `chief_session(project_root PK, session_id, updated_at)`. Migration hooked from
  `migrations_incremental` (one line).
- `http_server/blueprints/chief/__init__.py`, `messages.py` — `POST /chief/message`,
  `GET /chief/thread` (+ SSE event `CHIEF_REPLY` via the existing broadcaster). Register in
  `http_server/app.py` like the other domains.
- `supervisor/chief_turn.py` — compose the chief prompt (fragments + board context + inbox
  batch), mint a run token with role `chief`, spawn through the existing spawn host with
  `--resume <chief_session>`, write the reply to `chief_thread` on terminal result. Stamp
  `run_category=chief`.

Changed files
- Billing projection guard — add `chief` to the valid `category` set.
- `src/pathly_orchestrator/CLAUDE.md` blueprint domain map — add `chief/`.

Tests: one human message → one spawn (fake spawn host) → reply in thread; billing row
`category=chief`; second message reuses the session id.

---

## CHF-3 — Inbox events + relay answers (P3) · P0 · Med · needs CHF-2

New files
- `supervisor/chief_inbox.py` — subscribers for run done, interaction asked
  (`supervisor/interactions.py`), escalation posted, goal blocked; debounce window (setting
  `chief.debounce_ms`), one turn per batch.

Changed files
- `supervisor/interactions.py` — one call to enqueue the question for the chief.
- `blueprints/runner/api_control.py` `/runner/agent-answer` — accept the chief token only when the
  request carries the quoted human message id from `chief_thread` (else `403`).

Tests: US-3 cases; debounce (10 events → 1 turn); unquoted chief answer refused.

---

## CHF-4 — Standing directives (P3b) · P0 · Med · needs RRP-3, CHF-2

New files
- `db/migrations_chief.py` — add `binding INTEGER DEFAULT 0` to `comms_messages` (`to_agent`
  already exists).
- `db/queries/comms_directives.py` — `get_binding_decisions(conn, boards, scopes, role)`: binding,
  not superseded, not deleted, `to_agent IN (role, '*')`, any `status`.
- `supervisor/directive_check.py` — after a stage's terminal result: binding decisions newer than
  the run's spawn and targeting its role → mark result `stale_directive`, re-queue the stage.

Changed files
- `runner/comms_context.py` — governance block also takes `get_binding_decisions` (call site
  only; dedupe by id with pending decisions).
- `blueprints/comms/messages_write.py` — reject `binding=1` unless caller identity is
  `chief` run token or UI token (call into `_read_gate`/`run_identity`, not inline logic).
- `blueprints/comms/_helpers.py` `_PROJECT_WRITERS` + `db/queries/app_settings.py`
  `_DEFAULT_WRITE_PERMISSIONS` — add `chief` (kept in sync, per the comment there).
- Orchestrator / loop executor — honor `stale_directive` (re-queue, not advance).

Tests: US-4 cases (targeting, acknowledge does not hide, supersede retires, builder binding
refused, stale-directive re-queue).

---

## CHF-5 — Studio chat drives the chief (P4) · P0 · Low · needs CHF-2, CHF-3

Changed files
- `studio/src/renderer/src/components/HQ/` (`useHQ.tsx`, `MessageList`, `ChatInput`) — talk to
  `/chief/message` + `/chief/thread`, render `CHIEF_REPLY` SSE; links from cited board ids.
- `chat_agent.py` / `POST /chat` — delegate to the chief when `chief.enabled`; keep the regex path
  as fallback when off.
- `README.md`, `docs/WHAT_IS_PATHLY.md`, `studio/CLAUDE.md` — the chief as the front door.

Tests: renderer test for thread render + send; `npm run typecheck`; end-to-end with a fake spawn
host: a chat message creates a goal on the board.

---

## CHF-6 — Episodic memory tier (P5) · P1 · Med · needs RRP-1, RRP-3

New files
- `db/migrations_memory.py` + `db/queries/memory_episodes.py` — `memory_episodes(id, feature,
  goal_id, run_id, role, outcome, summary, ts, author_role, author_run_id, author_source)` + vec
  index (same sqlite-vec setup as comms).
- `runner/memory_episodic.py` — `record_episode(run)` at run end (from `AGENT_DONE.summary` +
  outcome), embedded via `runner/embeddings.py`; `retrieve_episodes(role, feature, k, policy)`
  with `policy_predicate` ANDed before `k`.
- `runner/comms_context_memory.py` — renders an "Earlier runs" section; `comms_context.py` gains
  one call site.

Tests: US-5 (next run sees last summary; reviewer does not see the builder's); the RRP-6
invariant test enumerates this query too.

---

## CHF-7 — Scheduled consolidate + promote (P6) · P1 · Med · needs CHF-6

New files
- `supervisor/memory_schedule.py` — at RETRO/DONE: run the existing consolidate
  (`/comms/consolidate` logic) and promote (`/comms/promote` logic) in-process.

Changed files
- Promotion path (`db/queries/comms_promote.py` or its gate) — to `global` only with
  `author_source ∈ {token, system}` **and** an evaluator/human approval record; else leave a
  pending promotion for the human.

Tests: US-6 cases; a `legacy` row is never auto-promoted to global.

---

## CHF-8 — Limits, refusals, session rebuild (P7) · P1 · Low · needs CHF-2

Changed files
- `supervisor/chief_turn.py` — `chief.max_turns_per_hour` (setting), provider-refusal → thread
  message "paused until …"; on missing/failed `--resume`, start a fresh session and rebuild
  context from board + memory only.

Tests: US-7 cases (cap enforced; refusal surfaced; lost session → correct status answer).

---

## Cross-cutting DoD (every ticket)
- `python -m pytest tests/ -q` (full suite), `python3 scripts/check_file_size.py`,
  `python3 scripts/check_no_mirror_reads.py`, `python scripts/gen_test_index.py --check`
- Studio tickets: `npm run typecheck` + `tsc -p tsconfig.node.json`
- Fragment/agent tickets: `python -m build`, `pathly-setup claude --apply --repair` dry check
- Living docs in the same commit (root `CLAUDE.md` "Documentation sync").
