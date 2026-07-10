# pathly_orchestrator - FSM Layer

Python package that implements the Pathly finite-state machine. Runs as both an MCP server (registered in `.claude/settings.json` as `pathly-fsm`) and an HTTP server on port **8765**.

## State machine

Features advance through: `STORMING -> PLANNING -> DESIGNING -> BUILDING -> REVIEWING -> TESTING -> RETRO -> DONE` (the literal state identifiers in `core/flows/team.flow.yaml`; the `-ING` suffix matters — `current_state` is e.g. `"BUILDING"`, not `"BUILD"`).

Each transition is driven by events written to the central SQLite DB (`~/.pathly/pathly.db`).

**State & flow storage — the DB is authoritative:**
- **FSM state** lives in the `fsm_state` table (source of truth). `STATE.json` directly in the feature dir (`pathly/features/<feature>/`; legacy `pathly/plans/<feature>/`, still resolved) is a **synchronized mirror** written after every transition (`eventlog.write_state` writes the DB first, then the file atomically). `next_action`/`complete_stage` read the DB and only fall back to `STATE.json` when the DB has no row. The file is still read *directly* by the scope gate (`build_baseline`), Studio feature-discovery, and the CLI — a mirror, not redundant; removing it would need a migration, not a delete.
- **Flows** load **DB-first at runtime** (`_load_flow`): `flow_nodes`/`flow_edges` → `flow_yaml` blob → packaged `.flow.yaml`. The `core/flows/*.flow.yaml` files are the **version-controlled seed**, re-synced into the DB on every server start (`_refresh_flows`). The filesystem read is a seed + resilience fallback (DB-unavailable / `project_root=None` CLI), not live config.

## HTTP endpoints

Use the packaged `pathly-fsm-call` helper as the canonical transport. It
encodes JSON safely on Windows and Unix shells and auto-starts the server if
needed.

```bash
pathly-fsm-call next-action \
  --flow "team" \
  --topic "<feature>" \
  --project-root "C:/Users/Yafit/pathly-adapters"

pathly-fsm-call complete-stage \
  --flow "team" \
  --topic "<feature>" \
  --project-root "C:/Users/Yafit/pathly-adapters"
```

If you need to debug the raw HTTP server, use a real JSON-capable client rather
than shell-escaped `curl` strings on PowerShell.

### Runner endpoints (Studio ↔ supervisor)

```
POST /runner/start                   ← Studio FlowControlBar: start a new pipeline run
POST /runner/pause                   ← pause running pipeline
POST /runner/resume                  ← resume paused pipeline
POST /runner/advance                 ← skip past current block
POST /runner/decision                ← supply a continue/block/escalate decision to a waiting run
POST /runner/agent-answer            ← answer an agent's mid-run human question
POST /runner/reroute                 ← reroute the run to a different stage/adapter
POST /runner/retry                   ← retry blocked stage
POST /runner/abort                   ← abort run completely
POST /runner/event                   ← inject an arbitrary runner event
GET  /runner/status                  ← current runner state snapshot
POST /runner/terminal/result         ← PTY exit callback: { run_id, topic, exit_code, stdout_tail, wall_seconds, user_initiated } — enriched with AGENT_DONE.summary from central DB; stdout used only for session_id + cost_usd
POST /runner/terminal/started        ← PTY started confirmation: { run_id, topic, tab_id }
GET  /events/runner?topic=<topic>    ← SSE stream of runner events for Studio
POST /shutdown                       ← graceful server shutdown (health blueprint; used by Electron on restart)
```

### Comms board endpoints (multi-agent message board)

The comms blueprint package (`blueprints/comms/`) backs the Studio comms board — agents and
humans post messages, ask/answer questions, decompose DAG tasks, and supersede stale notes.

```
POST /comms/post            ← post a message (embedding computed for hybrid search)
GET  /comms                 ← list board messages (scoped)
POST /comms/search          ← hybrid (semantic + keyword) search; semantic arm floored at SEMANTIC_DISTANCE_CEILING, keyword hits bypass; no match → [] (never padded with recent messages)
POST /comms/acknowledge     ← mark a message acknowledged
POST /comms/answer          ← answer a posted question
GET  /comms/tasks           ← list DAG tasks
POST /comms/tasks/complete  ← mark a task complete
POST /comms/tasks/run       ← run ONE task headlessly: claim it, spawn a builder on its prompt, complete on success
POST /comms/tasks/stop      ← stop a single-task run: kill its board run and revert the task to pending
POST /comms/attach          ← attach an artifact to a message
GET  /comms/artifacts       ← list artifacts linked to a message (comms_artifacts table)
GET  /comms/trash           ← list trashed messages
POST /comms/restore         ← restore a trashed message
POST /comms/supersede       ← mark a message superseded_by another
GET  /comms/scope           ← read the active board scope
POST /comms/scope           ← set the active board scope
GET  /comms/permissions     ← role-based write permissions
POST /comms/delete          ← soft-delete a message
POST /comms/edit            ← edit a message's text (e.g. goal rename)
POST /comms/tasks/claim     ← claim a ready task (pending → in_progress)
POST /comms/tasks/fail      ← mark a task failed (cascade-blocks dependents)
GET  /comms/artifacts/<id>/section ← hydrate a named section of a .md artifact (+ path form); context-retrieval HYDRATE tier
POST /comms/run             ← single-agent / evaluator board run
POST /comms/run/stop        ← stop a board run
POST /comms/agent-context   ← board context block for prompt injection
GET  /comms/goals           ← list goals + per-goal task-DAG rollup (read-model; symmetric partner to the goals write routes)
POST /comms/goals/run       ← dispatch a goal's task-DAG to its executor (single|loop|team)
POST /comms/goals/stop      ← stop a running goal (releases lock / aborts FSM run)
POST /comms/goals/decompose ← decompose a goal into a task-DAG (planner|consultation)
GET  /comms/goals/refs-coverage ← per-goal context_refs coverage stats
POST /comms/features/decompose ← decompose a feature board into a goal task-DAG (feature-consultation flow)
POST /comms/project/decompose  ← decompose a project spec into a feature set + scaffold pathly/features/<slug>/ (project-consultation flow)
POST /comms/consolidate     ← memory consolidation: near-dup dedup; mode=full adds the reflection pass
GET  /events/comms          ← SSE stream of comms board updates (streams blueprint)
```

### SSE events (GET /events/runner)

| Event type | Payload fields | Purpose |
|---|---|---|
| `RUN_STARTED` | `topic`, `run_id` | pipeline run began |
| `TERMINAL_SPAWN` | `tab_id`, `run_id`, `label`, `cwd`, `argv[]`, `adapter` | Studio should open a new terminal tab and spawn the PTY |
| `SESSION` | `kind` (new/continue), `session_id` | adapter session continuity signal |
| `RUNNER_WARNING` | `message` | non-fatal warning to surface as a toast |
| `RUNNER_STATUS` | `status`, `topic` | status change + periodic state sync (`running`/`paused`/`done`/`aborted`/`error`) — `supervisor/registry.py` `_set_status` |

> Pipeline completion is **not** a distinct SSE event — it is a `RUNNER_STATUS` carrying a terminal `status` (`done`/`aborted`/`error`). PTY-started confirmation is the `POST /runner/terminal/started` HTTP callback, not an SSE event.

## `/next_action` response contract

Every `/next_action` response includes the following top-level fields:

| Field | Values | Notes |
|---|---|---|
| `current_state` | FSM stage string | e.g. `"BUILDING"` |
| `agent` | role name string | e.g. `"builder"` |
| `decision` | `"continue"` / `"block"` / `"escalate"` | automation gate - see below |
| `agent_hint.role` | `"worker"` or `"explorer"` | host-neutral delegation signal |
| `agent_hint.instructions` | string | full prompt for the next agent |
| `codex_subagent` | legacy object | **frozen** - present for backward compat only; new adapters must read `agent_hint` |
| `preferred_adapter` | adapter name string | per-stage adapter from the flow's `adapter_map` (or a `stage_configs` override); the host spawns this CLI for the stage |

**`decision` field:**
- `continue` - adapter may automate the next step without human involvement
- `block` - an agent-resolvable feedback file is open; surface to the next Pathly agent via the standard feedback resolution flow
- `escalate` - human input is required (corrupt state, unknown feedback, or retry limit exceeded); do not automate

## FSM recovery

The `orchestrator` agent (haiku) can reconstruct state from the central DB event log if `STATE.json` is lost or corrupt. It is deterministic — same event log always produces the same state.

## Package structure

Each monolithic file has been decomposed into a sub-package:

```
pathly_orchestrator/
  db/                      # SQLite connection, migrations, per-entity query helpers
    connection.py          # get_db(), _get_write_lock(), connection cache
                           # DB concurrency: one process-wide threading.RLock (_global_write_lock,
                           # reentrant) is returned by _get_write_lock(conn). Every writer wraps
                           # its execute+commit in `with _get_write_lock(conn):`. WAL mode +
                           # busy_timeout=5000 handle cross-process contention; the RLock handles
                           # cross-thread contention within the server process.
    migrations.py          # _run_migrations(), CREATE TABLE SQL
    queries/
      fsm_events.py        # append_event, read_events, read_last_agent_done
      fsm_state.py         # write_state, read_state
      runner_state.py      # write_runner_state, read_runner_state, mark_stale_runners
      flow_defs.py / skill_defs.py / agent_defs.py / invocations.py / overrides.py / feedback_items.py
      otel_spans.py / run_history.py / stage_configs.py / catalog_items.py / trends.py / app_settings.py
      invocation_projection.py # agent_invocations = projection of the AGENT_DONE event stream:
                           #   one row per AGENT_DONE (keyed by fsm_events.seq = source_seq), the
                           #   superseding BILLING_UPDATE folded in (billing wins, never summed).
                           #   backfill_invocations_from_events() (idempotent startup rebuild) +
                           #   on_event_appended() (live hook fired from fsm_events.append_event).
                           #   Editor/chat rows (/db/invocation, source_seq NULL) are left untouched.
      comms.py             # re-export shim — splits into comms_messages, comms_artifacts, comms_tasks, comms_embeddings, comms_counts, comms_goals_read (import from domain modules for new code)
      comms_messages.py    # board message CRUD; goal_id/executor columns back the Goals->Task-DAG model
      comms_artifacts.py   # artifact metadata CRUD (attach, list, section index, update_summary)
      comms_tasks.py       # task DAG operations (get_ready, complete, claim, fail, reclaim, goal_refs_coverage)
      comms_embeddings.py  # embedding storage + hybrid/semantic search; search_by_embedding() merges parent+child vectors, deduplicates by message_id, returns _matched_chunk for subtopic surfacing; store_chunk_embeddings() writes to comms_chunk_embeddings; SEMANTIC_DISTANCE_CEILING (0.72) + opt-in max_distance= floor scored hits for /comms/search (BM25 hits bypass; comms_context.py keeps its own per-tier gates); _fts_query() quotes each token so raw FTS5 operators (code:query, a OR b, unbalanced ") match literally instead of reparsing; search_by_hybrid() tags each row _match_source (keyword|semantic) for client grouping
      comms_counts.py      # count_goals_for_feature / count_features_for_project — gate the consultation flows' seed thresholds
      comms_goals_read.py  # get_goals_with_rollup() — backs GET /comms/goals
      comms_summary.py     # per-artifact AI-summary selection/style/note setters+getters (unified-ai-routing)
      skill_composition.py # per-project skill-composition overrides (composition editor)
  runner/                  # CLI runner, agent invocation, argv, output parsing
    argv.py                # resolve_argv, resolve_interactive_argv, _storage_path
    output.py              # parse_result, _extract_json_payload
    events.py              # read_last_agent_done, _patch_last_agent_done, tail_agent_done
    history.py             # build_pipeline_history_block
    invoke.py              # invoke_agent(abort_callback=None, proc_callback=None)
    embeddings.py          # embed()/warm() — local embedding model; embed() has a bounded LRU (check inside _model_lock) so the per-board search fan-out re-embedding one query N+2 times computes the vector once; model load RETRIES transient failures (was a permanent silent latch that disabled semantic search process-wide) and embedder_status() reports {loaded,unavailable,load_attempts} to /health; chunk_summary() splits a summary into child chunks (per-bullet for topic-map, per-### for detailed, none for gist); embed_artifact_async() stores one PARENT vector (whole message text + summary) in comms_embeddings + CHILD vectors per chunk in comms_chunk_embeddings
    comms_context.py       # assembles board context (governance + referenced + semantic, relevance-gated); _matched_chunk surfaced as "matched topic: …" via comms_formatters.py
    sections.py            # parse_sections/slugify_heading/structure_key — markdown section index (anchors)
    hydrate.py             # hydrate_section/ensure_indexed — /section payload + staleness; index_artifact_async (eager, section-index only)
    code_context.py        # CodeContextProvider protocol + get_provider()/build_block() — codebase-intelligence context injection
    code_context_cli.py    # CliProvider — shells out to codebase-memory-mcp for code_context.py
    cli.py                 # run_flow, main, resolve_stage, handle_blocked, handle_decide
  supervisor/              # Visible runner: PTY spawning, SSE broadcast, registry
    state.py               # RunnerState, OpenSession dataclasses
    registry.py            # _registry, _lock, get_state, recover_stale_mirrors
    terminal.py            # _run_stage_via_terminal, _agent_done_watcher, _reconciliation_window
    interactions.py        # _await_agent_question
    orchestrator.py        # _loop, _resolve_stage_supervised
    api.py                 # start_run, pause_run, resume_run, abort_run, supply_decision, reroute_run
    goal_run.py            # thin re-export shim (start_goal_run / start_goal_decompose) → the two modules below
    goal_executor.py       # Board→Goals→Task-DAG executor dispatcher:
                           #   start_goal_run(goal_id, executor_override=…) reads the goal's
                           #   `executor` field and routes to one of three strategies:
                           #   single → one agent drains the whole DAG (start_board_run + drain-dag skill)
                           #   loop   → supervisor owns the frontier via scheduler_loop + _run_loop
                           #   team   → runs an FSM flow (default 'team-build') via start_run
    goal_decomposer.py     # start_goal_decompose() bridges an analyzed goal into a DAG
                           #   (mode='planner' or mode='consultation')
    scheduler.py           # DAG frontier loop (scheduler_loop): event-driven, blocks on completion_q;
                           #   at most one worker per lane; goal_id= scopes the frontier to one goal's tasks
    isolation.py           # lane / serial isolation strategies for the frontier loop
    file_claims.py         # per-file claim tracking so parallel tasks don't collide on writes
    artifact_reconcile.py  # reconcile board artifacts after a stage / goal run
    slug.py                # scope / slug helpers for goal + board addressing
    orchestrator_stage.py  # single-stage resolution helpers split out of orchestrator.py
    board_run.py           # start_board_run: board-lock + skill compose + async spawn helper
    board_lock.py          # Per-board/scope advisory lock (acquire/release/holder)
  http_server/             # Flask HTTP server: FSM endpoints + SSE + runner routes
    app.py                 # Flask app factory, blueprint registration, main()
    middleware.py          # _log_request, _log_response, rate limiting, metrics
    sse.py                 # SSE globals (_clients, _runner_clients, _menu_clients) + broadcast helpers
    pricing.py             # MODEL_PRICING, compute_cost_usd()
    feedback.py            # _feedback_watcher, _process_feedback_file
    blueprints/            # registered in app.py via the all_blueprints list
      core/                # health.py (GET /health,/status; POST /shutdown); fsm.py (POST /next_action,/complete_stage)
      runner/              # api.py + api_lifecycle.py + api_control.py — 13 /runner/* routes; streams.py (GET /events/menu|runner|spawn|history|stream|comms)
      flows/               # defs.py (flow CRUD); stage_configs.py (per-stage agent/model overrides)
      catalog/             # items.py (file-tree catalog)
      skills/              # editor.py re-export shim; editor_render.py (/skills/catalog|parse|preview|compose|summary-format/<style>); editor_io.py (/skills/save|export)
      comms/               # board + goals/DAG, split by domain: messages*.py, tasks.py, artifacts*.py, runs.py, goals.py, goals_read.py (GET /comms/goals rollup), settings.py, context.py, features.py (/comms/features/decompose), project.py (/comms/project/decompose) (+ _helpers.py); see "Comms board endpoints" above
      ops/                 # telemetry*.py (/record_activity, /record_phase*, /telemetry/*); menu.py (/menu, /metrics); db_api*.py (/db/* read API); chat.py (/chat); export.py
      code/                # query.py (POST /code/query — codebase-intelligence)
```

**Layer rules:**
- `db/` — no imports from runner, supervisor, or http_server
- `runner/` — may import db; no imports from supervisor or http_server
- `supervisor/` — may import db and runner; no imports from http_server
- `http_server/` — may import all; supervisor/db imports inside route handlers (lazy)
- Each package's `__init__.py` re-exports all symbols for backward compatibility

## Visible runner (supervisor/)

`supervisor/` drives the pipeline by polling `/next_action` and calling `/complete_stage`. Every agent invocation goes through a visible terminal — there is no headless fallback.

**Stage flow:**
1. `supervisor/orchestrator.py` calls `/next_action` → gets `agent_hint.instructions` (full prompt)
2. `supervisor/terminal.py` builds `argv` and emits `TERMINAL_SPAWN` SSE with `{ tab_id, run_id, argv, cwd, label, adapter }`
3. Studio opens a PTY tab (`node-pty`) and spawns the process via the `argv`
4. Studio POSTs `/runner/terminal/started` when PTY is up
5. PTY exits → `terminal.ts` POSTs `/runner/terminal/result` with exit code and stdout tail
6. Supervisor receives the result, calls `/complete_stage`, advances to next stage

Same-adapter consecutive stages share a `session_id`. Cross-adapter transitions start a new session.

On Windows, the argv is passed to PowerShell via `-EncodedCommand` (base64 UTF-16LE) to handle arbitrary prompt content safely.

## CLI shortcuts

```bash
pathly-ff      # fast-forward current feature state one step
pathly-back    # roll back current feature state one step
pathly-status  # show all active features and their current FSM state
```

## Prompt dash-safety

Headless prompts are sanitized before being passed to the CLI to ensure they never
start with `-` — which would be parsed as an unknown option (root cause: `claude -p
'---...'` errors with "unknown option '---'").

Two sanitization sites:

| Site | Function | Trigger |
|---|---|---|
| `adapters.py` `resolve_command` | `_dash_safe_prompt(prompt)` | every headless argv build |
| `skills/compose.py` (in `compose_skill` / `compose_block`) | `_strip_leading_frontmatter(text)` | composed/skill path |

`_dash_safe_prompt` (in `adapters.py`): strips a leading YAML-frontmatter block (`---…---`)
and then any remaining leading horizontal-rule lines, so the sanitized prompt is guaranteed
not to start with `-` regardless of source.

## Result split — stdout vs EVENTS.jsonl

When a PTY stage exits, the supervisor merges two sources:

| Source | Used for |
|---|---|
| `--output-format=json` stdout | `session_id` (session continuity) + `cost_usd` (API-accurate billing) |
| Central DB `AGENT_DONE.summary` | Semantic result text — what the agent did, outcome, key files |

The `summary` field is written by the agent via the `log-agent-done` skill to the central DB during its run.
It is never subject to the PTY's 500-chunk rolling output buffer.
If `summary` is absent (e.g. legacy agent), stdout `result` is used as a fallback.

The runner→FSM result dict `_run_stage_via_terminal` returns also relays the agent's self-reported `outcome` (`success`/`failed`) + `error` from `AGENT_DONE`, so the loop executor's `_outcome_is_failure` (`supervisor/scheduler.py`) fails a task that exited cleanly but reported failure (silent-failure guard #2); a `_pty_return()` helper merges the CLI `exit_code` into the same returned dict for that check.

## Telemetry feature key — `<fsm_feature>` vs `<feature>` (goal runs)

Every `fsm_events` row is keyed by a `feature` string. There are **two** distinct identities in a
prompt, and telemetry must use the right one or the goal panel shows `$0`:

| Placeholder | Resolves to | Substituted in | Used for |
|---|---|---|---|
| `<feature>` | **board scope** — the parent feature/project the goal lives on (e.g. `planner-hierarchy`) | `fsm_compose._inject_prompt_vars` (= `board_scope`) | board writes (`/comms/*`), record-activity — so artifacts don't orphan onto a throwaway slug board |
| `<fsm_feature>` | **run slug** — the storage-dir basename (e.g. `g3-…`) | `fsm_compose._inject_prompt_vars` (= `storage_path.name`) | telemetry: the `AGENT_DONE` POST in the `completion-report` fragment |

The slug is the canonical event-log key: `fsm_state`, `STATE_TRANSITION`, every
`eventlog.append_event(<path>)` (keys by `feature_dir.name`, `eventlog.py`), the supervisor
billing reconciliation (`_patch_last_agent_done(events_path.parent, …)`), the early-advance
watcher (`terminal.py` keys by `feature_dir.name`), and the DB-explorer goal panel
(`/db/features/<feature>/{events,agents}`) all use it. For a **plain feature run** the board
scope and the slug are identical, so `<feature> == <fsm_feature>` and nothing changes. For a
**goal team run** they differ — so `completion-report` posts `AGENT_DONE` under `<fsm_feature>`
(not `<feature>`); otherwise the cost lands on the feature/board scope and the goal detail shows
`$0` / "No AGENT_DONE events yet". `team/retro` records its stage via `log-agent-done`, which is
also passed `<fsm_feature>` so the retro slice keys by the slug like every other stage.
(Residual: `PHASE_SUMMARY`/`run_history`/OTel spans still key by the full `state.topic` path — a
non-cost display nuance, not yet unified.)
