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
POST /runner/resume-parked           ← resume a run parked on a headless human checkpoint (fresh run_id, same FSM state)
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
    board_scope.py         # ONE resolution of which tiers a run may see, serving BOTH directions: the context pushed into the prompt (board_context_for) and the tiers the board-search fragment lets an agent pull (<search_tiers>) — an agent told it may search a tier its own context channel isn't reading would be reaching AROUND the board-scope setting; search_tiers_value() renders board+scope pairs (feature->slug, project->normalized root, global->"global") since a mismatched pair returns [] rather than an error
    comms_context.py       # assembles board context (governance + referenced + semantic, relevance-gated); tags each kept row _tier from the search loop (authoritative, not row["board"]) so the render can budget per tier; _matched_chunk surfaced as "matched topic: …" via comms_formatters.py
    context_budget.py      # per-tier char budget MATH (pure — no DB on the render path): allocate_budget() splits the configured char_budget by weight (feature .5/project .3/global .2) NORMALISED over the enabled tiers (a feature-only run still gets the whole budget), select_within_budget() charges each line to its own tier then pools the unspent remainder; replaces a single shared budget that let the feature tier (rendered first) starve project/global outright
    context_settings.py    # the two numbers that size every board block, as app_settings keys read at CALL time (same contract as code_context.backend): board_context.char_budget (default 4000, bounds [200,40000]) + board_context.k_{feature,project,global} (defaults 5/3/2, bounds [0,25]). They are a PAIR — k binds first in the intended case, so raising the budget alone is half a change. Garbage/out-of-range FALLS BACK to the default rather than clamping, so the rendered block always matches a documented number; k=0 legally mutes one tier's semantic pull while its governance still injects. Needs NO new route: GET /db/settings + PUT /db/settings/<key> already take arbitrary keys. Replaces bare literals (2000, and 3/2/1 inline in enabled_boards) that had no recorded justification — unlike the cosine cutoffs beside them, which carry a live-board calibration
    context_record.py      # render_stats() + record_board_context() — appends ONE `BOARD_CONTEXT` fsm_event per prompt build carrying the volume actually rendered vs dropped (rendered_entries/chars, per-tier chars, omitted_entries/chars) PLUS the budget+k in force, so the next move on those numbers is made from data. Inert to telemetry: append_event projects only AGENT_DONE/BILLING_UPDATE. Wrapped + never-raising (a telemetry write must never break prompt assembly) and create_dir=False so it can't plant an empty decoy dir that later wins _resolve_storage_path's existence probe. Opt-in via storage_path, which keeps the /comms/agent-context preview write-free
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

**Layer rules — CI-enforced (`import-linter`, `[tool.importlinter]` in `pyproject.toml`).**
"Architecture bugs, not style issues" now has a gate: `lint.yml`'s consistency job runs
`lint-imports`, which fails the build on ANY new violation of the direction below (not just
`.py` files reachable from a route handler — the whole `pathly_orchestrator.*` import graph).
- `db/` — no imports from runner, supervisor, or http_server
- `runner/` — may import db; no imports from supervisor or http_server
- `supervisor/` — may import db and runner; no imports from http_server
- `http_server/` — may import all; supervisor/db imports inside route handlers (lazy — this is
  about avoiding a slow/circular import at module load, not something the layers contract
  itself needs to know: `http_server` importing DOWN into `supervisor`/`db` is the ALLOWED
  direction regardless of laziness)
- Each package's `__init__.py` re-exports all symbols for backward compatibility

**Three pre-existing violations are frozen as `ignore_imports` in the contract**, same spirit
as `scripts/file_size_baseline.txt` — documented debt, not something to add to. All three route
through a shared top-level hub module OUTSIDE the four layers, not one layer package importing
another directly: `db.migrations -> board_mirror -> board_mirror_hydrate -> runner.embeddings`;
`runner/__init__.py -> fsm_http_client -> fsm_ops -> fsm_ops_complete -> supervisor.artifact_reconcile`;
and `eventlog -> http_server.sse`, which alone accounts for two reported violations
(`supervisor.{goal_executor,terminal,terminal_reconcile} -> eventlog -> http_server.sse` and
`runner.{context_record,events,history,provenance} -> eventlog -> http_server.sse`) since
`eventlog.append_event` broadcasts SSE toasts on write. Fixing these is real, separate work.

**Modules split under the 400-line ratchet (2026-08-18) — import paths unchanged.** Each keeps its
original name as the entry point and re-exports every symbol its callers and the test-suite already
import, so no call site moved:

| Entry point | Now delegates to |
|---|---|
| `fsm_compose.py` (298) — keeps `build_prompt` / `build_prompt_for_agent` / `_load_agent_text` | `fsm_compose_tables` (lookup tables) · `fsm_compose_vars` (`_inject_prompt_vars` + its inputs) · `fsm_compose_paths` (`resolve_stage_out_path`, `resolve_board_scope`) · `fsm_compose_stage` (section drops, stage overrides, adapter choice) · `fsm_compose_hints` (`_agent_hint`) |
| `skills/compose.py` (197) — keeps the resolver | `compose_base` (constants + `_strip_leading_frontmatter`) · `compose_resources` (manifest/skill/fragment I/O) · `compose_caps` · `compose_segments` · `compose_validate` |
| `supervisor/terminal.py` (390) — keeps the spawn | `terminal_argv` · `terminal_identity` · `terminal_reconcile` · `terminal_billing` · `terminal_phase` |
| `fsm/engine_actions.py` (204) — keeps `run_transition_actions` | `fsm/gates/` — one module per gate type (`artifact` · `tasks` · `scope` · `command`) behind the `run_gates` dispatcher in `gates/__init__.py`; `_helpers` owns `append_event` / `_write_gate_feedback` / `gate_failed` / `project_root_of` |

Two constraints govern what may leave these files, and both are load-bearing:
`fsm_compose._load_agent_text` and `supervisor.terminal._reconciliation_window` are **monkeypatched
in those namespaces by tests**, so the functions that call them must stay in the same module and
call them as bare names. `fsm_compose.py` also still loads `fsm_compose_responses` at the BOTTOM of
the file — that ordering is what keeps its back-reference from becoming a cycle.

## Transition gates (`fsm/gates/`)

A gate answers one question: may the FSM leave `prev_state` for `next_state`? `run_gates`
(`fsm/gates/__init__.py`) dispatches through a `_CHECKS` registry — **a new gate type is a new
module, never another `elif`**. Each check returns `None` to allow the transition or a
`{"gate_failed", "feedback_file"}` dict to block it; the first failure wins and
`fsm_ops_complete` turns it into a blocked response routed by `feedback_routing`.

| Gate | Module | Proves | Config |
|---|---|---|---|
| `require_artifact` | `artifact.py` | an agent wrote a file | `artifact` |
| `verify_gate` | `artifact.py` | an agent wrote `pass_marker` on line 1 | `artifact`, `pass_marker` |
| `require_tasks_done` | `tasks.py` | the board DAG has no unfinished task (goal-scoped when `goal_id` is set, else feature-scoped) | — |
| `scope_gate` | `scope.py` | the builder stayed inside its declared footprint (git diff ∪ untracked vs. `scope_file`) | `scope_file` |
| `command_gate` | `command.py` | **the project's own verify command exits 0** | `command_key` (+ optional `command`, `timeout`) |

**The first four read state that agents produced; only `command_gate` executes something.** That
distinction is the point of it: `verify_gate` is satisfied by an agent writing `RESULT: PASS`, so
the FSM's pass/fail signal was, end to end, an agent's opinion of its own work. `command_gate`
re-derives the answer from a process exit code and routes the real stdout/stderr back as feedback.

**Command resolution** (highest precedence first): `gate["command"]` literal → app-setting
`verify.<command_key>` → **skip**. Configure a project with
`PUT /db/settings/verify.test {"value": "python -m pytest -q"}` (also `verify.build`, `verify.lint`,
and `verify.timeout_seconds`; default timeout 600s).

**Fail-open on absent config, fail-closed on everything else.** No configured command → `GATE_SKIPPED`
(`no_command_configured`), so adding the gate to a shared flow never breaks a project that has not
configured one. But a command that runs and fails, times out, cannot be parsed, or cannot be executed
all **block** — a verify command that silently does nothing is worse than no gate at all.

The command is split with `shlex.split` and run **without a shell**, so `&&`, `|` and `>` are not
operators — put those in a script and call the script. A value starting with `[` is parsed as a JSON
argv array instead, for exact control on any platform — **required on Windows for batch shims**
(`npm`/`yarn`/`tsc` are `.cmd` files and do not resolve by bare name without a shell: use
`["npm.cmd", "test"]`). It runs with cwd = the repo root (via
`gates/_helpers.project_root_of`, which delegates to `eventlog._project_root_of` so a nested
`goals/<slug>` run resolves the same root the event log keys off) and `PATHLY_VERIFY_GATE=1` in the
environment. Failure output is clipped head+tail (3000/5000 chars) — compilers put the first error at
the top, test runners put the summary at the bottom, so tailing alone loses half the signal.

Events: `GATE_PASSED` (command, `exit_code`, `duration_ms`) on success — the objective evidence on
the run's record — and `GATE_FAILED` (with `reason`, `command`, `exit_code`) on failure.

Wired in `core/flows/team.flow.yaml` and `team-build.flow.yaml`: `BUILDING->REVIEWING` runs
`verify.build` → `BUILD_FAILURES.md`, `TESTING->RETRO` runs `verify.test` → `TEST_FAILURES.md`.
Both route to the builder.

## Human checkpoints — parked, not failed

When `complete_stage` blocks with `target_agent == "human"`, the supervisor stops the loop
without treating it as a failure. `orchestrator_stage.py::_park` (not `_fail`) sets
`RunnerState.status = "parked"` — a status distinct from `"error"`/`"aborted"` and included
alongside them in `VALID_STATUSES` (`supervisor/state.py`) and in `_set_status`'s
run-history-finalizing set (`supervisor/registry.py`), since resuming starts a fresh run_id
rather than reviving this one.

**Why this is safe to resume, not just "not an error":** parking never touches the FSM's own
state — `fsm_state` still sits exactly where the checkpoint left it, waiting on whatever
feedback file `target_agent == "human"` named. `_post_human_escalation` posts an answerable
`type="escalation"` board message naming that file and `POST /runner/resume-parked`. A human
(or an agent proxying for one) edits the file to resolve it; `POST /runner/resume-parked
{"topic": ...}` → `supervisor.resume_parked_run` reads the parked `RunnerState`'s
flow/project_root/model/goal_id and calls `start_run` again under a NEW run_id — `start_run`
only refuses a topic whose status is running/paused/awaiting_decision, so a parked topic is
free to restart. The fresh `/next_action` call re-evaluates the SAME feedback file's CURRENT
content, so the human's edit takes effect immediately — no separate "replay" step exists or
is needed. Cost/iteration counters restart at zero under the same caps; they are not carried
over from the parked attempt.

**`on_done` consumers still see it as non-success.** `api.py`'s `_run_and_finalize` sets
`result["error"]` for `status in {"error", "aborted", "parked"}` — every existing `on_done`
(e.g. `goals.py`'s `_on_done`) branches on `res.get("error")` to avoid reporting a non-clean
stop as `"finished"`; a parked run without this would have been silently reported as success.
`result["status"]` still reads `"parked"` for a caller that wants to distinguish resumable
from dead — `goals.py`'s board-message wording does not yet make that distinction (falls
into the generic "goal run failed" text), a known cosmetic gap, not a correctness one.

## Goal cost cap (`supervisor/cost_cap.py`)

The FSM loop (`orchestrator.py`) refuses to spawn a new stage once `cost_usd_so_far >=
max_cost_usd` — but that check lives entirely inside `orchestrator.py`; the DAG/loop
executor's `scheduler.py` frontier loop has no equivalent, so a goal's task-DAG could run
to any cost. `cost_cap.py` closes this WITHOUT touching `scheduler.py` (frozen at its
400-line ratchet ceiling): `CostCapTracker.wrap(spawn_fn)` returns a spawn function with
the same signature that accumulates each task's real `cost_usd` as it becomes known, and
`goal_executor.py::_run_loop` folds `tracker.exceeded()` into the SAME `abort_check` hook
`scheduler_loop` already polls at the top of its frontier loop before scheduling anything
new — no new extension point, no scheduler changes.

Same limitation as the FSM loop's own cap, for the same reason: a headless
`claude -p --output-format json` spawn reports cost in one JSON envelope at process exit,
not a stream, so there is no way to know a task's cost before it finishes. This stops the
DAG from scheduling FURTHER tasks once the aggregate is blown; it cannot preempt one
already in flight.

Configure per project with `PUT /db/settings/goal.max_cost_usd {"value": "5.0"}` —
absent/invalid/non-positive means **no cap**, the same fail-open contract as
`command_gate`. On breach, `tracker.report(res)` sets `res["error"]` /
`res["cost_cap_exceeded"]` on the loop's result — the same shape `goal_verify`'s
`verify_clean_drain` already uses, so every `on_done` consumer (which branches on
`res.get("error")`) reports it as a non-clean stop rather than silent success.

## Headless spawn host (`pty_host/`)

The supervisor never spawns a CLI itself. `supervisor/terminal.py` emits `TERMINAL_SPAWN` on the
topic-independent `/events/spawn` SSE channel and blocks on `TerminalRun.wait_started(30)`, then
`wait_pty_result(1800)`. Whoever answers is the **spawn host**. There are now two, and the
supervisor cannot tell them apart:

| Host | Process | Answers with | Used for |
|---|---|---|---|
| Studio | Electron main (`studio/src/main/ipc/terminal.ts`), node-pty | a visible PTY tab | desktop, human watching |
| `pathly-pty-host` | this package, plain pipes | a headless subprocess | server-side drain, CI, no desktop |

```bash
pathly-fsm-http &        # the FSM server
pathly-pty-host          # the spawn host — one at a time; two would double-spawn every run
```

Both implement the same three-event / two-callback contract: consume `TERMINAL_SPAWN`,
`TERMINAL_KILL`, `TERMINAL_SIGNAL(term)`; answer `POST /runner/terminal/started` (releases the 30s
wait) and `POST /runner/terminal/result` (the authoritative, run-keyed billing gate). Because the
result POST carries the same `adapter` + raw `stdout_tail`, headless runs get the SAME telemetry
path as Studio runs — `parse_result` on the server, `BILLING_UPDATE`, invocation projection.

Module map: `host.py` (SSE loop + dispatch + concurrency) · `process.py` (one child: capture, kill)
· `client.py` (the two callbacks) · `sse.py` (urllib SSE reader) · `cli.py` (`pathly-pty-host`).

Four behaviors are load-bearing rather than incidental:

- **Pipes, not a pseudo-terminal.** Every adapter's headless mode (`claude -p`, `codex exec`) is
  non-interactive, so no TTY is needed. **stdin is `/dev/null`** — `codex` headless otherwise stalls
  waiting on terminal input (the hazard `terminal.ts` handles by piping `$null` on Windows).
- **The child gets its own process group** (POSIX `start_new_session`, Windows `taskkill /T`), so a
  kill reaches the CLI's own children. Killing only the direct child is what leaves orphaned CLI
  processes behind after an abort.
- **`stop()` shuts the SSE socket down, it does not `close()` the response.** `close()` needs the
  BufferedReader lock that the blocked `readline()` already holds, so it only returns at the
  server's next 25s keepalive — a 25s hang on every Ctrl-C. `socket.shutdown()` makes the in-flight
  `recv()` return immediately (`sse.close_stream`).
- **An interactive stage is refused, not attempted.** Headless has no terminal and no human, so the
  host reports `exit_code 1` with a nameable reason instead of letting the supervisor wait out its
  30-minute result timeout on a stage that can never finish there.

The child env carries `PATHLY_GATE_BILLED=1` (so the interactive stop hook skips the run rather than
double-billing it via its "most recently active feature" guess) and `PATHLY_PROJECT_ROOT`, matching
what Studio exports.

## Retry ladder — what varies by ATTEMPT, not just who owns it

`escalation_routing` (`fsm/engine_transitions.py::_resolve_feedback_target`) already changes
the ROLE by round — rounds 1-2 the file's owner, round 3 an upstream specialist, round 4+
human (`_ESCALATE_AT_ATTEMPT = 3`; a flow's tiers come from `["planner", "architect"]`-style
lists or explicit `{at, to}` dicts, normalized by `_normalize_tiers`). What escalating the
ROLE never did is escalate the STRATEGY: every attempt on a given role got the identical
prompt — no signal it was a repeat, no guaranteed view of what actually failed (only
Fix-mode roles — po/planner/architect/designer — are told to go read the feedback file), no
visibility into what an earlier attempt on this stage reported.

`route_feedback` now returns `retry_count` alongside `target_agent` (the SAME count
`_resolve_feedback_target` used to pick the role — one number, two effects, always in sync).
`fsm_compose.build_prompt_for_agent(..., retry_count=...)` appends a retry-ladder block from
round 2 on (`retry_count > 0`): the attempt number, the feedback file's CURRENT content read
fresh at call time (capped, so a pathological feedback file can't blow up the prompt), and
`build_pipeline_history_block` — the SAME recent-`AGENT_DONE`-summaries helper `build_prompt`'s
normal stage-advance path already uses, so no second history mechanism exists. **Round 1
(`retry_count == 0`, the default) is byte-identical to before this** — every existing caller
that never threads the new parameter, and every golden snapshot, is unaffected.

## FSM/DAG convergence — Phase 0 hygiene fixes

Four small, independent fixes surfaced while researching converging the FSM engine and the
DAG/goal engine into one execution model (design at `pathly/features/` — see the root
`CLAUDE.md`'s Comms board section for the DAG side). None of these change the convergence
design itself; they clear real bugs/inconsistencies found along the way, same discipline as
the earlier goal-cost-cap / provenance / retry-ladder additions above.

1. **`team/build`'s board poll is now goal-scoped.** The FSM gates around BUILDING
   (`on_board_count`, `require_tasks_done`) already read `RunnerState.goal_id`, but the skill's
   own `GET /comms/tasks?ready=true` query had no `goal_id` param — a goal-executor run could
   claim a ready task belonging to a DIFFERENT goal on the same feature board.
   `fsm_compose.build_prompt` now substitutes a real `<goal_id>` prompt var (mirroring
   `<feature>`/`<board>`/…, not left to the agent to infer) into any composed FSM-stage prompt;
   `team/build.md`'s curl line sends it as `&goal_id=<goal_id>` (empty string when the run isn't
   goal-scoped, which `/comms/tasks` already treats as "no filter").
2. **`test.flow.yaml` no longer self-loops on `TEST_FAILURES.md`.** It routed
   `TESTING->TESTING` instead of `TESTING->BUILDING` like both `team.flow.yaml` and
   `team-build.flow.yaml` (and its own `feedback_routing: TEST_FAILURES: builder`). A same-state
   "transition" skips `eventlog.write_state`'s legality check entirely (`old_current ==
   new_current`), so this never crashed — it just re-ran `team/test` against unfixed code
   forever instead of ever handing the failure to the builder.
3. **`feature-consultation.flow.yaml` / `project-consultation.flow.yaml` now carry the same
   `adapter_map` as `consultation.flow.yaml`** (PO discussion + design on `codex`, everything
   else `claude`). Both files' own header comments describe them as "consultation.flow.yaml
   lifted one altitude up" (same PO→architect→researcher→designer→planner shape); the
   `adapter_map` was dropped when they were copied and is now reconciled.
4. **`fsm/state.py`'s `STATES`/`VALID_STATES`/`TRANSITIONS`** (sourced from
   `pathly_data/schemas/state.schema.json`) were flagged during research as apparent dead code —
   the vocabulary (`IDLE`, `DISCOVERING`, `REVIEW_BLOCKED`, …) matches none of the 9 shipped
   flows, and every real caller (`fsm_ops.py`, `fsm_ops_complete.py`) always passes its own
   `flow_config`. Closer investigation found this was the wrong call: `eventlog.write_state`/
   `append_event`'s `flow is None` branch is a genuine, still-enforced fallback legality check
   for a caller that omits a flow, and `tests/fsm_flows/test_orchestrator.py` deliberately
   exercises it (`test_write_state_rejects_illegal_transition` and siblings). Deleting it would
   have broken that safety net and those tests for no benefit — left in place, with a comment
   clarifying it is a generic fallback vocabulary, not any live flow's state machine.

## FSM/DAG convergence — Phase 1: per-task retry/escalation (`supervisor/task_retry.py`)

The `loop` executor's `scheduler.py` frontier loop had NO retry at all: any task failure — a
worker exception, or an outcome reporting failure (`_outcome_is_failure`) — called `fail_task()`
immediately and permanently, cascading `blocked` to every transitive dependent. The `attempts`
column (`comms_messages.attempts`, already incremented by `claim_task` on every claim) was
written but never read anywhere — a dead signal. Contrast the `team`/`team-build` FSM path,
which already gets real per-task verification for free: `team-build.flow.yaml`'s
`BUILDING->REVIEWING` `command_gate` runs once per task (BUILDING spawns one `team/build` agent
per ready task, per the per-task loop docs above) — that path needed no new gate, just the
Phase 0 goal-scoping fix. The gap was specifically the `loop` executor's flat, gate-less DAG.

**What Phase 1 does NOT do, and why:** the original plan sketch called for a per-task
*completion gate* reusing `fsm.gates.command.check_command_gate`, keyed by a `task_kind`/`stage`
column. Investigation found `assigned_to_stage` (the column that would key it) is declared in
the schema but written nowhere — populating it is a task-creation change (planner/decomposer),
out of scope for an additive pass. Worse, running `verify.build`/`verify.test` after EVERY task
directly contradicts `goal_verify.py`'s own documented rationale for checking once at goal-drain
("not per task, which would run the whole suite N times for one goal"). So Phase 1 is scoped to
what the codebase actually has a real gap in — retry — not a redundant per-task command_gate.

**`resolve_task_failure`** is the one decision point `scheduler.py`'s completion handler calls
on a failed task, and owns the FULL side-effect set for whichever branch it picks (so
`scheduler.py` only needs the returned `(decision, blocked_ids)`):
- **Retry** (`current_attempt < goal.task_max_attempts`, default 3): `retry_task` reverts the
  task to `pending` — the frontier's next poll re-schedules it — and stamps the failure reason
  into the existing `fail_reason` column (no new column: `get_ready_tasks`' `SELECT *` already
  returns it, so the NEXT attempt's `task` dict carries it for free).
- **Escalate** (attempt `>= goal.task_max_attempts`): the original behavior, delayed until
  retries are exhausted — `fail_task`'s cascade-to-blocked, plus a board `escalation` message
  (mirrors `goal_verify.post_gate_failure_escalation`) so a human/agent sees it instead of a
  silent DB-only cascade.

**`build_retry_context`** appends a retry-ladder block to a retried task's prompt from the
second attempt on — mirrors `fsm_compose._retry_ladder_block`'s "what varies by ATTEMPT, not
just who owns it": the attempt number and the previous failure's reason, so a retry doesn't
repeat the identical blind prompt. A first attempt (`attempts == 0`) is unaffected — byte-
identical to before this feature.

**`detect_deadlocks`** is `scheduler.py`'s former loop-only postscript (any task still `pending`
after a normal drain has an unsatisfiable dependency — a cycle, or a `depends_on` that will
never complete; `get_ready_tasks` silently excludes it, so without this a drain returns a
clean-looking result while work sits stuck forever), extracted so any drain path with DB access
can reuse it — universal deadlock detection. Only `scheduler_loop` calls it today; wiring the
`single` executor's agent-driven `drain-dag` loop to it would need a new HTTP endpoint (an
agent can't call Python directly) and is flagged, not attempted, in this pass.

Configure per project with `PUT /db/settings/goal.task_max_attempts {"value": "5"}` — unlike
`command_gate`/`goal.max_cost_usd`'s fail-open-to-off contract, an absent/invalid/non-positive
setting here falls back to the **default (3)**, not "no retry": an unconfigured project should
still get the safety net.

This shipped as an EXTRACTION-plus-ADDITION, not pure addition: `scheduler.py` was already at
its 400-line ratchet ceiling (433), so the failure branch's full logic (including the old
unconditional `fail_task` call and the deadlock postscript) moved into `task_retry.py` — net
result, `scheduler.py` is now SHORTER (415 lines) despite gaining retry capability, and no flow
YAML, Studio surface, or existing test needed to change.

**Follow-up bug caught before it shipped to production: retried attempts shared one `run_id`.**
The first version of this change kept `task_run_id = f"sched-{task_id}"` unchanged — fine when a
task_id spawned at most once, but retry means the SAME task_id can spawn multiple times. `run_id`
is the identity the whole billing chain keys off (`TERMINAL_SPAWN`, the PTY result callback,
`_reconciliation_window`'s async patch, `agent_invocations.run_id`), and
`invocation_projection.on_event_appended` matches a `BILLING_UPDATE` to the MOST RECENT
`AGENT_DONE` sharing its `run_id` — so a late-arriving reconciliation for attempt N (early-advance
mode: the agent self-reports done while the real PTY billing is still in flight on a background
thread) could fold its real cost onto attempt N+1's row instead of its own once attempt N+1 had
already written its own `AGENT_DONE` under the identical run_id. Fixed by making `run_id` unique
per attempt: `f"sched-{task_id}#{attempt}"` (`#` is a safe separator — task ids are uuid4: hex and
hyphens only). Every place that previously parsed a bare task_id back out of a `sched-` run_id
(`test_dag_scheduler.py`, `test_golden_path.py`, `test_comms_goals_run.py`) now also strips the
`#<attempt>` suffix; production code was already unaffected since it only ever checked the
`sched-` PREFIX (`run_history_read._classify_kind`/`_is_parent`), never parsed the remainder.

## FSM/DAG convergence — more Phase-0-style fixes found while researching Phase 2 readiness

Three more small, independent bugs, found the same way as the original Phase 0 batch (research
agents scanning the DAG/board, telemetry, and FSM/flow-YAML layers for the same CLASS of defect —
a sibling divergence or a dropped parameter — before considering Phase 2's bigger compiler work):

- **`POST /comms/goals/run`'s `stage_overrides` validated against a hardcoded `"team-build"`**
  instead of the flow actually being run (`flow_override`, which the route already accepts and
  threads to `start_goal_run`). `_validate_stage_overrides` drops any override key not in the
  named flow's declared `states` — so a goal run with `flow: "debug"` and a `FIXING` override had
  it silently dropped, since `FIXING` isn't one of `team-build.flow.yaml`'s states. Fixed by
  validating against `flow_override or "team-build"` (the same default `start_goal_run`/
  `goal_executor._TEAM_FLOW` already use).
- **A parked goal run (`RunnerState.status == "parked"`, a headless human checkpoint) was reported
  to the board as `"goal run failed"`** — the exact cosmetic gap this repo's own docs already named
  (see "Human checkpoints — parked, not failed" above: *"`goals.py`'s board-message wording does
  not yet make that distinction"*). `comms_goals_run`'s `_on_done` now special-cases
  `res.get("status") == "parked"` before the generic error fallback, posting "goal run paused —
  awaiting human input" on the existing non-error `stopped` phase (Studio's `phase` union has no
  dedicated `parked` value, so adding one would require a frontend change too — out of scope for
  this pass; `stopped` already clears the timer pill without the `failed` toast).
- **`test.flow.yaml` had no `escalation_routing` at all**, unlike `team.flow.yaml`/
  `team-build.flow.yaml` which share its exact `team/review`+`team/test` skills and carry an
  identical 3-tier table (`REVIEW_FAILURES`/`SCOPE_VIOLATION` → planner, `TEST_FAILURES` → po, both
  escalating to human past round 4). An empty `escalation_routing` makes
  `_resolve_feedback_target` unconditionally return the base agent — so a persistently failing
  review/test loop in `test.flow.yaml` routed back to `builder` forever, with no round-3 hand-off
  and no round-4 human escalation. Fixed by copying the same table from `team.flow.yaml`.

**Flagged, not fixed — needs a human call, not a unilateral one:** `DESIGN_QUESTIONS.md` routes to
`architect` in `team.flow.yaml`/`test.flow.yaml` but to `designer` in `team-build.flow.yaml` and
all three consultation flows. `team/build.md`'s own inline body text ("If `DESIGN_QUESTIONS.md`
exists… Spawn `architect`") resolves it before the FSM-level table is ever consulted for
`team`/`team-build` in the common case, so this is latent rather than live — but
`tests/fsm_flows/test_two_flows.py` explicitly pins `"designer"` for `team-build.flow.yaml` as a
deliberate, tested value, and no comment anywhere explains the split. Reversing a tested,
deliberate-looking decision on a guess is a bigger call than the fixes above — left alone pending
someone who knows the original intent.

## FSM/DAG convergence — Phase 2: a lightweight direct executor (`supervisor/compiled_flow.py`)

The plan's original Phase 2 sketch was a compiler that reads a flow YAML and emits an
equivalent DAG task-chain, drained by Phase 1's generalized `scheduler.py`. Research into
building it surfaced a landmine specific to the flows chosen as the safest first target
(`quick-fix`, `debug`): their skills (`fix/build.md`, `debug/build.md`, `debug/verify.md`)
contain literal "call `pathly-fsm-call complete-stage`" instructions in their bodies,
neutralized ONLY by the "you're headless, ignore the FSM-operations instructions above"
runner-contract block `fsm_compose.build_prompt` injects into every FSM-composed prompt.
`scheduler.py`'s existing DAG-task prompt path (`compose_skill("development/execute-task",
...)`, what real loop-executor goals use) does **not** inject that override — reusing it
verbatim for these flows would leave an agent trying to call an FSM endpoint that means
nothing for a DAG-driven run, a real correctness bug rather than a style issue.

**Resolution: `run_compiled_flow` walks a flow's states directly in Python** — no `fsm_state`
DB row, no `STATE.json`, no `/next_action`/`/complete_stage` HTTP round-trip; this run's
position in the flow lives only in a local variable for the call's lifetime. It reuses the
SAME pure, flow_config+filesystem-only helpers `fsm_ops_complete.complete_stage` already
orchestrates — `route_feedback`, `evaluate_transition_rules`, `run_gates`,
`run_transition_actions` — and the SAME prompt-building path (`fsm_compose.build_prompt`/
`build_prompt_for_agent`), so the runner-contract override is never skipped. This does NOT
gain Phase 1's DAG-native retry/escalation/deadlock machinery (`task_retry.py` is untouched;
`scheduler.py` is untouched) — it has its own much simpler in-process feedback-round loop
instead, capped at the same `MAX_FEEDBACK_ROUNDS` `orchestrator_stage.py` uses.

**Opt-in per flow, off by default.** `resolve_compiled_flows()` reads the
`flow.compiled_executors` app-setting (comma-separated flow names) — same fail-open-to-off
contract as `command_gate`/`cost_cap`/`task_retry`'s own settings. The dispatch seam lives in
`api.py::start_run`, swapping which function `_run_and_finalize` closes over
(`run_compiled_flow` vs. `orchestrator._loop`) based on `is_compiled_flow(flow)` — every flow
not in the setting is byte-identical to before this existed. **Nothing is enabled by default**:
this ships as real, tested code with zero effect on any existing run until an operator
explicitly opts a flow in. Only `quick-fix` and `debug` have been verified against it (no
`gates`, no `adapter_map`, no `transition_rules` at all — every transition is the flow's own
listed default, so `evaluate_transition_rules` never returns a `decide` block for either).
Adding another flow to the setting is unverified and should not be done without re-checking
its shape against the limitations below first.

**Known, deliberate limitations vs. the FSM path (documented in the module, not silently
absorbed):**
- **No park/resume.** A human-checkpoint feedback file fails the run (`error_kind
  "human_checkpoint"`, with a board escalation posted) instead of parking it — a parked run
  has nowhere to resume FROM here (no persisted current-state), so faking "parked" would
  silently restart the whole flow from `states[0]` on resume, worse than an honest failure.
  Fine for quick-fix/debug (human checkpoints are their rare/edge-case path per their own
  `feedback_routing` comments); a flow leaning on human checkpoints routinely should not be
  added to `flow.compiled_executors`.
- **No session continuity** — every stage spawns a fresh session, unlike `_loop`'s
  same-adapter session reuse. A real, small cost increase; not implemented for this slice.
- **A pre-existing `fsm_state`/`STATE.json` row for the topic refuses the run outright**
  (`error_kind "existing_fsm_state"`) rather than silently ignoring prior FSM-driven progress
  on the same topic.
- **A `decide` transition rule fails loudly** (`error_kind "decide_unsupported"`) rather than
  being silently mishandled — neither validated flow uses one.

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

## `pathly-run` — the OTHER execution path (`runner/cli.py`, `runner/invoke.py`)

`pathly-run <topic> --flow team --model … --project-root …` is a second, self-contained way
to drive a flow, separate from the supervisor entirely. It calls `next_action`/`complete_stage`
directly in a loop (`run_flow`/`resolve_stage` in `runner/cli.py`) and spawns each agent itself
via `invoke_agent` (`runner/invoke.py`, a plain `subprocess.Popen`) — no `RunnerState`, no board,
no goal DAG, no `TERMINAL_SPAWN`/`/runner/terminal/result`, none of the spawn-scheduler's
dual-cap concurrency. It is also genuinely interactive, not headless: a human checkpoint or a
`decide` response calls `input()` and blocks the terminal — this is a personal, desktop-less CLI
for driving one flow by hand, not a background/CI runner.

Bypassing `/runner/terminal/result` means bypassing the ONE chokepoint that bills every other
spawn (`CLAUDE.md`'s "spawn gate" telemetry docs, root file) — `pathly-run` had **no cost source
at all** until this fix: `invoke_agent`'s `Popen` call set no `env`, so the child inherited the
parent shell's environment unchanged, and the interactive stop hook (the ONLY fallback billing
path a non-gate-billed claude session has) could not find `PATHLY_PROJECT_ROOT` to know which
feature to bill. Fixed by exporting it explicitly, matching what Studio already does for every
interactive tab (`terminal.ts`) — `env={**os.environ, "PATHLY_PROJECT_ROOT": project_root}`. A
`pathly-run` session now bills the same way any other interactive claude session does.

**What this does NOT fix, and why it's left alone:** `pathly-run` remains a genuinely separate
execution path from the supervisor — two ways to drive a flow that can drift independently, and
`pathly-run` runs are invisible to the board/DAG/Monitor. Collapsing it onto the supervisor +
`pty_host` (so `pathly-run` becomes a thin wrapper around `supervisor.start_run` with an embedded
spawn host, or is retired in favor of `pathly-fsm-http` + `pathly-pty-host` directly) is real,
valuable follow-up work — but it means rewriting a public, interactive CLI entry point's control
flow, and doing it safely needs its own scoped review, not a same-pass bolt-on next to five other
changes. Flagged here rather than attempted blind.

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

## Per-stage git provenance — MEASURED, not self-reported (`runner/provenance.py`)

`AGENT_DONE.summary` is written by the agent itself (the `completion-report` fragment runs
agent-authored Python) — a self-report, same category `command_gate` closed a hole for on the
correctness side. `runner/provenance.py` answers a different question with a SERVER-measured
answer: at the moment `POST /runner/terminal/result` fires (the one per-spawn chokepoint every
adapter's result passes through — see the billing docs above), what does `git` say actually
changed in `project_root`? `record_stage_provenance` runs `git rev-parse HEAD` + `git diff --stat
HEAD` + `git status --porcelain` there and appends a `STAGE_PROVENANCE` event
(`{run_id, stage, head_sha, diff_stat, files_changed}`) — nothing the agent writes or omits can
affect it.

Two things make this correct rather than superficially similar to `scope_gate`'s git usage:

- **Untracked files are included.** `git diff HEAD` alone only covers tracked paths — a brand new
  file (the most common thing a builder does) never appears in it. `files_changed`/`diff_stat`
  fold in `git status --porcelain`'s `??` lines too.
- **The whole `pathly/` tree is exempt**, wider than `scope_gate`'s `pathly/features/`/
  `pathly/plans/` prefix check. `pathly/` is entirely Pathly's own storage substrate (features/,
  project/, board-artifacts/, lessons/, the legacy plans/ — never builder code), and on a brand
  new project's very first feature git collapses an entirely-untracked tree to its SHALLOWEST
  boundary (`?? pathly/`, not the deeper `?? pathly/features/<f>/`) — a narrower prefix check
  would miss exactly the run it exists to exempt.

Deliberately **cumulative, not per-stage-isolated**: with `pathly.auto_commit` off by default,
changes routinely accumulate across several stages before a human commits, so "the full
working-tree diff from the last commit, as of right now" is the honest unit — isolating one
stage's exact incremental delta would need a per-stage baseline snapshot (`scope_gate`'s
`build_baseline` captures one, but for a narrower purpose — stale scope-drift detection, not
general provenance). Best-effort throughout: `capture_stage_provenance` returns `None` (never
raises) outside a git repo or on any git failure, and `record_stage_provenance` never blocks or
fails the result callback that calls it.

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
