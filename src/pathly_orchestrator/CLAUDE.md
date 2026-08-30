# pathly_orchestrator - FSM Layer

Python package that implements the Pathly finite-state machine. Runs as both an MCP server (registered in `.claude/settings.json` as `pathly-fsm`) and an HTTP server on port **8765**.

## State machine

Features advance through: `PLANNING -> DESIGNING -> BUILDING -> REVIEWING -> TESTING -> RETRO -> DONE` (the literal state identifiers in `core/flows/team.flow.yaml`; the `-ING` suffix matters — `current_state` is e.g. `"BUILDING"`, not `"BUILD"`). PLANNING is `states[0]` — the seed a new feature starts at. (STORMING was dropped as the team seed — it was headless ceremony for spec-driven work; genuine brainstorming lives in the interactive `/pathly storm` on-ramp and the consultation flows. STORMING still exists as a state in `test.flow.yaml` and maps to `/pathly storm`.)

Each transition is driven by events written to the central SQLite DB (`~/.pathly/pathly.db`).

**State & flow storage — the DB is authoritative:**
- **FSM state** lives in the `fsm_state` table (source of truth). `STATE.json` directly in the feature dir (`pathly/features/<feature>/`; legacy `pathly/plans/<feature>/`, still resolved) is a **DB→disk EXPORT** written after every transition (`eventlog.write_state` writes the DB first, then the file atomically). `next_action`/`complete_stage` read the DB and only fall back to `STATE.json` when the DB has no row. The only remaining direct readers are allow-listed DB-first fallbacks (scope gate `build_baseline`, FSM recovery, feedback-routing retry counts) and the human CLI (`pathly-back`/`-log`/discovery globs) — Studio reads `/db/features` instead (state-one-authority; enforced by `scripts/check_no_mirror_reads.py`).

**Disk-file classification (state-one-authority):** *the SQLite DB is the single runtime authority; every per-feature disk file is a SEED (read once into the DB) or an EXPORT (written DB→disk) — never round-tripped for a runtime decision.*

| File | Class | Direction | DB authority |
|---|---|---|---|
| `STATE.json` | EXPORT (git-trackable) | DB→disk, atomic, every transition | `fsm_state` |
| `BOARD.json` | EXPORT (gitignored) | DB→disk, debounced (`board_mirror.py`) | `comms_*` |
| `EVENTS.jsonl` | EXPORT (gitignored; rewritten from the DB on every server start) | DB→disk, debounced (`event_mirror.py`) | `fsm_events` |
| `ARTIFACTS.jsonl` | **DROPPED** — artifact metadata lives in `BOARD.json`; reconcile attaches the stage's declared `<out_path>` directly | — | `comms_artifacts` |
| `*.flow.yaml` | SEED | disk→DB on server start (`_refresh_flows`) | `flow_nodes`/`flow_yaml` |
| `abilities/*.md`, `prompts/*.md` | SEED (file *is* authority) | disk→compose | n/a |
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
POST /runner/terminal/result         ← PTY exit callback: { run_id, topic, exit_code, stdout_tail, wall_seconds, user_initiated } — enriched with AGENT_DONE.summary from central DB; stdout used for session_id + cost_usd (+ persisted verbatim to run_log — unified-control-plane P0 Complete Run Record display sink)
POST /runner/terminal/started        ← PTY started confirmation: { run_id, topic, tab_id }
GET  /events/runner?topic=<topic>    ← SSE stream of runner events for Studio
POST /shutdown                       ← graceful server shutdown (health blueprint; used by Electron on restart)
```

**`stage_overrides` — transient per-run, per-stage prompt override (flow-gate-preview).**
`POST /runner/start` accepts an optional `stage_overrides: {<STATE>: <prompt_text>}` body field
— the flow analogue of `board_run.start_board_run(prompt_override=…)`, sourced from Studio's
`FlowGatePreview` gate (a stage's Sections trim, "use once"). `blueprints/runner/_runner_bp.py`'s
`_validate_stage_overrides` sanitizes it (dict[str,str], keys coerced to the flow's own declared
states when the flow loads — else fail-open, per-value/total size capped at 64 KB/256 KB, blanks
dropped; malformed input degrades to `{}`, never a 400) before `runner_start` passes it to
`supervisor.start_run(stage_overrides=…)`, which stores it on `RunnerState.stage_overrides` —
**in-memory, per-run only, never persisted** (contrast: the PERSISTENT
`stage_configs.{ability_ids,excluded_sections}` selection edited in the flow-phase-inspector /
`ConfigurePhaseModal`, which `stage_overrides` never touches or shows up in). `_loop` forwards the
map to `/next_action` only when non-empty; `fsm_ops.next_action` picks the entry keyed by the
CURRENT state and passes it to `fsm_compose.build_prompt(..., stage_override=…)`, which — when set
— uses it **verbatim** in place of the composed `agent_text` for that state only (skipping compose
AND `_apply_stage_selection`, so a gate override is never double-trimmed), while
`_inject_prompt_vars` and the context/history/board/code tail still apply exactly as for a
composed stage.

The channel has four callers, all reusing the SAME `RunnerState.stage_overrides` → `build_prompt`
plumbing above (no second channel): `POST /runner/start` (board Run→Flow, any flow); `POST
/comms/goals/run` (goal-executor `team`, flow `team-build` — `blueprints/comms/goals.py` validates
against `"team-build"` and threads it through `goal_executor.start_goal_run` → `_run_team` →
`start_run(stage_overrides=…)`; single/loop executors ignore it, they use `prompt_override`
instead); and the three consultation decomposers — `POST /comms/goals/decompose` (flow
`consultation`, only when `mode=='consultation'`; planner/plan ignore it),
`POST /comms/features/decompose` (flow `feature-consultation`), `POST /comms/project/decompose`
(flow `project-consultation`) — each validating with the SAME `_validate_stage_overrides` helper
before threading through `goal_decomposer.start_goal_decompose` → `_decompose_consultation` (goal
case) or directly (feature/project case) into their own `start_run(stage_overrides=…)` call. A
consultation override needs no "seed THIS goal" directive baked in — the supervisor appends
`_decompose_directive` after `build_prompt` regardless of whether a stage composed or was
overridden.

### Comms board endpoints (multi-agent message board)

The comms blueprint package (`blueprints/comms/`) backs the Studio comms board — agents and
humans post messages, ask/answer questions, decompose DAG tasks, and supersede stale notes.

```
POST /comms/post            ← post a message (embedding computed for hybrid search)
GET  /comms                 ← list board messages (scoped)
POST /comms/search          ← hybrid (semantic + keyword) search; semantic arm floored at SEMANTIC_DISTANCE_CEILING, keyword hits bypass; no match → [] (never padded with recent messages). Reached by AGENTS too via the `board-search` fragment (own board only) — the self-authored second query the pushed context can't make; Studio's search box is the other caller
POST /comms/promote         ← copy a decision/constraint UP a tier (feature→project→global). COPY not move: the source board is the audit record of HOW the decision was reached. Stamps promoted_from/original_scope on the copy + promoted_to on the source (the three columns migrations.py reserved and nothing read). Idempotent, keyed off the COPY's promoted_from so one message can promote to two tiers. Own permission set `_PROMOTE_WRITERS` = {director, evaluator, human, **retro**} — NOT _GLOBAL_WRITERS, else the RETRO stage (the one headless role whose job IS capturing lessons) could never promote. decision/constraint only
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
POST /comms/hydrate         ← board disk-mirror: import a project's on-disk BOARD.json mirrors into the DB (fresh-clone; DB-authoritative, no-ops non-empty boards)
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

**`GET /events/runs?run_id=<run_id>`** (unified-control-plane T3, `control/run_streams.py`) — a
unified per-run feed: any event above, or a `/events/comms` `COMMS_UPDATE`, whose payload carries
a `run_id` is ALSO mirrored onto this run-scoped channel by `sse._broadcast_run_event`, teed from
`_broadcast_runner`/`_broadcast_comms` (mirrors the `_SPAWN_EVENT_TYPES` tee pattern above, but
keyed by run_id presence in the payload instead of event type). Lets a single subscription watch
ONE run end-to-end regardless of which topic/board/scope it lives under.

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
    pricing.py             # PRICING table, PricingRegistry, estimate_cost()/infer_provider(),
                           # estimate_cost_for() (accepts a model OR an adapter slug — falls back
                           # to the adapter's default model family so a renderer one-shot with no
                           # explicit --model, e.g. codex, can still be priced; used by
                           # project_agent_done for the /db/invocation path) — the layer-safe
                           # pricing SSOT (db/ imports nothing internal, so the projector below
                           # can price a row without importing upward into http_server/). http_server/telemetry_registry.py re-exports these
                           # symbols for back-compat; http_server/pricing.py (a separate file:
                           # MODEL_PRICING/compute_cost_usd) is unrelated and still imports FROM
                           # telemetry_registry, unchanged.
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
                           #   _price_if_needed() (chokepoint, applied on every projected row) calls
                           #   db/pricing.estimate_cost() when cost_usd==0 AND tokens>0 (e.g. codex,
                           #   which reports tokens but no dollar cost) — idempotent, never re-prices
                           #   an already-priced row; a token-less agy/gemini row is marked
                           #   cost_source='unavailable' instead of a misleading $0. run_id is now
                           #   stamped on the projected row (AGENT_DONE.run_id, or a later
                           #   BILLING_UPDATE.run_id via COALESCE) — backs GET /db/runs/<run_id>/cost.
                           #   `category` (flow|single|loop) is the run TYPE, read from the
                           #   AGENT_DONE payload (completion-report's <run_category>, or Fix A's
                           #   synthetic) and guarded to the valid set — backs the Monitor RECENT
                           #   bucketing (scope_tier is the board tier, not the run type).
      comms.py             # re-export shim — splits into comms_messages, comms_artifacts, comms_tasks, comms_embeddings, comms_counts, comms_goals_read (import from domain modules for new code)
      comms_messages.py    # board message CRUD; goal_id/executor columns back the Goals->Task-DAG model
      comms_artifacts.py   # artifact metadata CRUD (attach, list, section index, update_summary)
      comms_tasks.py       # task DAG operations (get_ready, complete, claim, fail, reclaim, goal_refs_coverage)
      comms_embeddings.py  # embedding storage + hybrid/semantic search; search_by_embedding() merges parent+child vectors, deduplicates by message_id, returns _matched_chunk for subtopic surfacing; store_chunk_embeddings() writes to comms_chunk_embeddings; SEMANTIC_DISTANCE_CEILING (0.72) + opt-in max_distance= floor scored hits for /comms/search (BM25 hits bypass; comms_context.py keeps its own per-tier gates); _fts_query() quotes each token so raw FTS5 operators (code:query, a OR b, unbalanced ") match literally instead of reparsing; search_by_hybrid() tags each row _match_source (keyword|semantic) for client grouping
      comms_counts.py      # count_goals_for_feature / count_features_for_project — gate the consultation flows' seed thresholds
      comms_goals_read.py  # get_goals_with_rollup() — backs GET /comms/goals
      comms_summary.py     # per-artifact AI-summary selection/style/note setters+getters (unified-ai-routing)
      skill_composition.py # per-project skill-composition overrides (composition editor)
      prompt_library.py    # prompt_library table CRUD — now the LEGACY kind='ability' store only; global/project merge, name-upsert, idempotent seed. kind='preset' (system-prompts) moved to FILES → skills/prompt_files.py (mirrors abilities), with a one-time lazy DB→files migration
  runner/                  # CLI runner, agent invocation, argv, output parsing
    argv.py                # resolve_argv, resolve_interactive_argv, _storage_path
    output.py              # parse_result, _extract_json_payload; extract_tokens + the per-adapter
                           # _TOKEN_STRATEGIES registry (Strategy A — token counting; cost is
                           # Strategy B in db/pricing.py)
    events.py              # read_last_agent_done, _patch_last_agent_done, tail_agent_done
    history.py             # build_pipeline_history_block
    invoke.py              # invoke_agent(abort_callback=None, proc_callback=None)
    embeddings.py          # embed()/warm() — local embedding model; embed() has a bounded LRU (check inside _model_lock) so the per-board search fan-out re-embedding one query N+2 times computes the vector once; model load RETRIES transient failures (was a permanent silent latch that disabled semantic search process-wide) and embedder_status() reports {loaded,unavailable,load_attempts} to /health; chunk_summary() splits a summary into child chunks (per-bullet for topic-map, per-### for detailed, none for gist); embed_artifact_async() stores one PARENT vector (whole message text + summary) in comms_embeddings + CHILD vectors per chunk in comms_chunk_embeddings
    comms_context.py       # assembles board context (governance + referenced + semantic, relevance-gated); tags each kept row _tier from the search loop (authoritative, not row["board"]) so the render can budget per tier; _matched_chunk surfaced as "matched topic: …" via comms_formatters.py
    context_budget.py      # per-tier char budget for the Context channel — allocate_budget() splits CONTEXT_CHAR_BUDGET (2000) by weight (feature .5/project .3/global .2) NORMALISED over the enabled tiers (feature-only run still gets the full 2000), select_within_budget() charges each line to its own tier then pools the unspent remainder; replaces a single shared budget that let the feature tier (rendered first) starve project/global outright
    sections.py            # parse_sections/slugify_heading/structure_key — markdown section index (anchors)
    hydrate.py             # hydrate_section/ensure_indexed — /section payload + staleness; index_artifact_async (eager, section-index only)
    code_context.py        # CodeContextProvider protocol + get_provider()/build_block() (backend=auto[default]|off|cli|lsp|both) — codebase-intelligence context injection
    code_context_cli.py    # CliProvider — shells out to codebase-memory-mcp graph for code_context.py
    code_context_lsp.py    # LspProvider — bridges a long-lived Serena MCP session (LSP, always-fresh); async warm-up, never-raise
    cli.py                 # run_flow, main, resolve_stage, handle_blocked, handle_decide
  supervisor/              # Visible runner: PTY spawning, SSE broadcast, registry
    state.py               # RunnerState, OpenSession dataclasses
    registry.py            # _registry, _lock, get_state, recover_stale_mirrors
    terminal.py            # _run_stage_via_terminal — THE SPAWN. Re-exports the names below,
                           #   because supervisor/__init__ and the tests import them from here
                           #   (and _reconciliation_window is monkeypatched in THIS namespace,
                           #   so it must be called as a bare name, never via its own module).
    terminal_argv.py       # _resolve_spawn_argv — the seam a NEW ADAPTER touches
    terminal_identity.py   # _record_spawn_identity/_record_spawn_prompt/_settle_spawn_identity, _run_board_scope
    terminal_reconcile.py  # _agent_done_watcher, _reconciliation_window, _synthesize_agent_done_if_missing
    terminal_billing.py    # _emit_executor_telemetry, _reconcile_billing_now (were spawn-local closures)
    terminal_phase.py      # _write_supervisor_phase_summary
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
    artifact_reconcile.py  # after a stage/goal run: attach the stage's declared <out_path>
                           #   (resolved from the FSM's own manifest via fsm_compose.resolve_stage_out_path,
                           #   passed as out_path — state-one-authority: NO ARTIFACTS.jsonl ledger) AND
                           #   <storage>/feedback/*.md (HUMAN_QUESTIONS/REVIEW/TEST_FAILURES)
                           #   to the board (idempotent). A headless human checkpoint also posts
                           #   a type='escalation' board message (orchestrator_stage.py) so it's
                           #   answerable instead of failing silently.
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
      flows/               # defs.py (flow CRUD); stage_configs.py (per-stage overrides: agent/adapter/skill + layer-3 ability_ids + excluded_sections — the flow-phase-inspector SELECTION, applied FRESH at spawn by fsm_compose.build_prompt, never stored as trimmed text)
      catalog/             # items.py (file-tree catalog)
      skills/              # editor.py re-export shim; editor_render.py (/skills/catalog|parse|preview|compose [returns segments+tokens; accepts ability_ids]|summary-format/<style>); editor_io.py (/skills/save|export); prompt_library.py (/skills/prompts — system-prompts are file-backed via skills/prompt_files.py, kind='ability' stays legacy DB); abilities.py (/skills/abilities — layer-3 ability FILES, see skills/abilities.py)
      comms/               # board + goals/DAG, split by domain: messages*.py, tasks.py, artifacts*.py, runs.py, goals.py, goals_read.py (GET /comms/goals rollup), settings.py, context.py, features.py (/comms/features/decompose), project.py (/comms/project/decompose) (+ _helpers.py); see "Comms board endpoints" above
      ops/                 # telemetry*.py (/record_activity, /record_phase*, /telemetry/*); menu.py (/menu, /metrics); db_api*.py (/db/* read API); chat.py (/chat); export.py
      code/                # query.py (POST /code/query — codebase-intelligence)
      control/             # runs_read.py (GET /runs, /runs/<run_id> — unified run read API; P0);
                           # runs_control.py (POST /runs — the unified launcher: a thin RunSpec
                           # {kind, board, scope, flow?, goal_id?, adapter?, model?} validated
                           # then routed to the matching EXISTING facade — kind=flow →
                           # supervisor.api.start_run, kind=single|evaluator →
                           # supervisor.board_run.start_board_run, kind=goal →
                           # supervisor.goal_executor.start_goal_run; route only, never
                           # reimplements a runner; POST /runs/<run_id>/stop AND
                           # POST /runs/<run_id>/<action> for action in
                           # pause|resume|advance|reroute|retry|abort — run_id-addressed control:
                           # resolves run_id → abort_run/pause_run/resume_run/reroute_run/start_run
                           # (FSM registry) or board-lock stop (board/goal; board-lock runs support
                           # ONLY abort, else {ok:false,reason:unsupported_for_kind}), else
                           # {ok:false,reason:not_active}; board_lock.find_by_holder reverse-lookup;
                           # _helpers.py holds the shared resolution/abort/retry + create-run bodies);
                           # run_streams.py (GET /events/runs?run_id=<run_id> — unified per-run SSE
                           # feed, T3: mirrors the /events/runner shape incl. the
                           # pathly_sse_clients_active gauge bookkeeping; fed by
                           # sse._broadcast_run_event, teed from _broadcast_runner/_broadcast_comms
                           # whenever a payload carries a run_id)
```

**Layer rules:**
- `db/` — no imports from runner, supervisor, or http_server
- `runner/` — may import db; no imports from supervisor or http_server
- `supervisor/` — may import db and runner; no imports from http_server
- `http_server/` — may import all; supervisor/db imports inside route handlers (lazy)
- Each package's `__init__.py` re-exports all symbols for backward compatibility

**Modules split under the 400-line ratchet (2026-08-18) — import paths unchanged.** Each keeps its
original name as the entry point and re-exports every symbol its callers and the test-suite already
import, so no call site moved:

| Entry point | Now delegates to |
|---|---|
| `fsm_compose.py` (298) — keeps `build_prompt` / `build_prompt_for_agent` / `_load_agent_text` | `fsm_compose_tables` (lookup tables) · `fsm_compose_vars` (`_inject_prompt_vars` + its inputs) · `fsm_compose_paths` (`resolve_stage_out_path`, `resolve_board_scope`) · `fsm_compose_stage` (section drops, stage overrides, adapter choice) · `fsm_compose_hints` (`_agent_hint`) |
| `skills/compose.py` (197) — keeps the resolver | `compose_base` (constants + `_strip_leading_frontmatter`) · `compose_resources` (manifest/skill/fragment I/O) · `compose_caps` · `compose_segments` · `compose_validate` |
| `supervisor/terminal.py` (390) — keeps the spawn | `terminal_argv` · `terminal_identity` · `terminal_reconcile` · `terminal_billing` · `terminal_phase` |

Two constraints govern what may leave these files, and both are load-bearing:
`fsm_compose._load_agent_text` and `supervisor.terminal._reconciliation_window` are **monkeypatched
in those namespaces by tests**, so the functions that call them must stay in the same module and
call them as bare names. `fsm_compose.py` also still loads `fsm_compose_responses` at the BOTTOM of
the file — that ordering is what keeps its back-reference from becoming a cycle.

## Visible runner (supervisor/)

`supervisor/` drives the pipeline by polling `/next_action` and calling `/complete_stage`. Every agent invocation goes through a visible terminal — there is no headless fallback.

**Stage flow:**
1. `supervisor/orchestrator.py` calls `/next_action` → gets `agent_hint.instructions` (full prompt)
2. `supervisor/terminal.py` builds `argv` (via `terminal_argv._resolve_spawn_argv`) and emits `TERMINAL_SPAWN` SSE with `{ tab_id, run_id, argv, cwd, label, adapter }`
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
| `skills/compose_base.py` (used by `compose_skill` / `compose_skill_with_block`) | `_strip_leading_frontmatter(text)` | composed/skill path |

`_dash_safe_prompt` (in `adapters.py`): strips a leading YAML-frontmatter block (`---…---`)
and then any remaining leading horizontal-rule lines, so the sanitized prompt is guaranteed
not to start with `-` regardless of source.

## Result split — stdout vs central DB

When a PTY stage exits, the supervisor merges two sources:

| Source | Used for |
|---|---|
| `--output-format=json` stdout | `session_id` (session continuity) + `cost_usd` (API-accurate billing) |
| Central DB `AGENT_DONE.summary` | Semantic result text — what the agent did, outcome, key files |

The `summary` field is written by the agent via the `log-agent-done` skill to the central DB during its run.
It is never subject to the PTY's 500-chunk rolling output buffer.
If `summary` is absent (e.g. legacy agent), stdout `result` is used as a fallback.

The runner→FSM result dict `_run_stage_via_terminal` returns also relays the agent's self-reported `outcome` (`success`/`failed`) + `error` from `AGENT_DONE`, so the loop executor's `_outcome_is_failure` (`supervisor/scheduler.py`) fails a task that exited cleanly but reported failure (silent-failure guard #2); a `_pty_return()` helper merges the CLI `exit_code` into the same returned dict for that check.

## Run identity — ISSUED at spawn (run-identity)

Telemetry identity is **issued where truth is known — at spawn — never derived from storage
location downstream.** Every run carries three identity facts as first-class columns, so no
consumer has to guess which identity a `feature` key holds:

| Fact | Meaning | Lives in |
|---|---|---|
| `run_id` (**primary**) | one id per spawn — per-stage `topic-N-ts` for FSM stages, `sched-<task_id>` per loop task, uuid per board run | `agent_invocations.run_id`, `run_history.run_id`, event payloads |
| run slug (`<fsm_feature>`) | the storage-dir basename — the canonical event-log key (`fsm_state`, `STATE_TRANSITION`, `eventlog.append_event`, billing reconciliation, early-advance watcher) | the `feature` column everywhere (incl. `run_history` new rows) |
| `board_scope` (`<feature>`) | the parent feature/project board the run belongs to | `fsm_events.board_scope`, `agent_invocations.board_scope`, `run_history.board_scope` |

For a **plain feature run** slug == board scope; for goal/debug/nested runs they differ — and
both now land as columns instead of being re-derived. The pieces:

- **One derivation** — `fsm_compose.resolve_board_scope` (plain feature → the slug; `project` →
  normalized `project_root`; goal → the goal's parent board scope). `build_prompt` uses it for
  the `<feature>` substitution and the supervisor uses the SAME helper for stamping
  (`terminal._run_board_scope`), so prompt and telemetry can never drift. Board/loop executors
  issue `RunnerState.board_scope` directly at spawn.
- **Agent side** — `completion-report` / `utilities/log-agent-done` write
  `board_scope: <feature>` into the `AGENT_DONE` body; the event's feature key stays
  `<fsm_feature>` (goal cost keys by the slug, so the goal panel never shows `$0`).
- **Server guarantee** — `_synthesize_agent_done_if_missing` and the BILLING_UPDATE
  (`_patch_last_agent_done`) stamp `run_id` + `board_scope` when the agent omitted them.
  COALESCE-style everywhere: an agent-provided value is never overwritten; `append_event`
  extracts the column (an unsubstituted `<placeholder>` lands as NULL, never junk).
- **`run_history` is the identity map** — `_record_spawn_identity` writes
  `{run_id, project_root, feature=slug, board_scope}` at the spawn chokepoint
  (`_run_stage_via_terminal`) and `_settle_spawn_identity` closes the row (done/error);
  the registry finish-upsert and `/runner/start` insert also key by the slug. Legacy
  full-path rows are never rewritten — read helpers match them via a basename shim.
- **FSM-flow PARENT row carries the FLOW NAME as `adapter`** (spawn-tracking) — the
  bare-uuid parent run's `adapter` column is the flow name (`team`/`team-build`/`consultation`/…),
  NOT the last stage's CLI adapter, because the read-model (`run_history_read._classify_kind`)
  keys a bare-uuid run's kind off that column: a flow name in `FLOW_NAMES` → `flow` (cost summed
  over the stage time-window), a real adapter → `single` with $0 (no invocation carries the parent
  uuid). `supervisor/registry._record_run_history` (shared by `_set_status`'s terminal write AND
  `start_run`'s **early `running` row**) writes `state.flow` there — fixing (1) completed flows
  reclassifying to `single`/$0, and (2) `team`/consultation/feature/project runs (which call
  `start_run` directly, bypassing `/runner/start`) being invisible in `GET /runs` until they
  finished. The goal **`loop`** executor is the same shape: `_run_loop` writes its own PARENT row
  (`adapter="goal-loop"` via `state.flow`) — the read-model classifies a `goal-loop` bare-uuid as
  a **loop parent** (`_is_parent`) that windows its per-task `sched-*` rows (folded out of
  `list_runs`, folded INTO its RunDetail as stages), so a loop shows as ONE run with real cost
  instead of N task rows + a 404-ing parent uuid. A legacy parent-less loop still lists its tasks.
  Renderer-driven one-shots (editor AI actions, ai-router artifact/HQ summaries) never
  cross the supervisor, so their ONLY Python seam — `POST /db/invocation`
  (`blueprints/ops/db_api_invocation.py`) — writes their own `done` `run_history` row (+
  `run_log` stdout), best-effort, so they surface in `GET /runs` alongside supervisor runs
  instead of living only in `agent_invocations`/`/db/recent`.
- **Consumers pivot** — `/db/rollup`'s feature block and `/db/features/<f>/{agents,runs}`
  match `feature=? OR board_scope=?`, so a goal run's cost is visible under BOTH its slug and
  its parent feature. The Monitor's RECENT bucketing already pivots on the stamped
  `category` column and needs nothing further. Legacy rows (NULL `board_scope` / NULL
  `run_id`) keep the exact old feature-key behavior — a fallback, not a guess.
- (Residual: `PHASE_SUMMARY`/OTel spans still key by the full `state.topic` path — a non-cost
  display nuance, explicitly out of run-identity's gate.)
