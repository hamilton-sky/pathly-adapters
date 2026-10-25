# pathly_orchestrator - FSM Layer

Python package that implements the Pathly finite-state machine. Runs as both an MCP server (registered in `.claude/settings.json` as `pathly-fsm`) and an HTTP server on port **8765**.

**Another port: `PATHLY_FSM_HTTP_PORT`.** The server binds to it (`config.Settings.from_env`), and
the callers follow it through `config.fsm_port()` (the lenient read: unset or invalid means 8765):
`fsm_http_client.DEFAULT_PORT` (the supervisor's own `/next_action` + `/complete_stage` calls and
`pathly-fsm-call`), `RunnerState.fsm_port` (exported to workers by `isolation.py`) and
`pathly-pty-host --port`. Skills and fragments keep their literal `http://127.0.0.1:8765` URLs;
`config.localize_fsm_urls` rewrites them to the configured port where a prompt is handed to a CLI
(`_run_stage_via_terminal`, next to the `<run_id>` substitution, and `adapters.resolve_command`
for `pathly-run`). On the default port it is a no-op, so default prompts and the golden snapshots
are byte-identical. Interactive `/pathly` skills installed under `~/.claude/skills` are not
rewritten and still call 8765.

## Architecture at a glance — control and data flow

Five views of the SAME system, verified against the code rather than reconstructed from the
prose below. The narrative sections that follow carry the detail and the phase-by-phase history
of how it got here; these are the map.

### 1. Control — one engine, one authority

```
 ENTRY POINTS                          all converge on the same engine
 ------------                          -------------------------------
 Studio "Start"  - POST /runner/start --+
 POST /runs (kind=flow) ----------------+
 /comms/goals/run  -+                   |
   executor=team ---+- _run_team -------+
   executor=loop ---+  (flow=goal-loop) |
 /comms/{goals,features,project}/decompose -+   (mode=consultation only;
                                            |    mode=planner/plan is a board run)
                                        v
                              supervisor.api.start_run()
                              - RunnerState -> _registry[topic]
                              - run_history PARENT row (adapter = FLOW NAME)
                                        |
                                        v
                        +------- orchestrator._loop --------+
                        |  (THE engine - one per run)       |
                        +----------------+------------------+
                                         |
    +------------------------------------v---------------------------------+
    |  1. abort? pause? caps?  (iterations, max_cost_usd)                   |
    |  2. POST /next_action  ->  {current_state, agent_hint.instructions,   |
    |                             preferred_adapter, decision}              |
    |  3. resolve_session()  ->  reuse iff same adapter; reviewer: fresh    |
    |  4. fan_out.run_stage(...)          <- THE one stage call site        |
    |  5. POST /complete_stage  -> run_gates() -> next_state | blocked      |
    +------------------------------------+---------------------------------+
                                         |  next_state
                                         v
                          eventlog.write_state()   <- legality-checked
                          fsm_state (DB)  ->  STATE.json (export)
                                         |
                                         +--> loop, until DONE / parked / abort
```

`executor: single` is the one goal path that does **not** enter here — it is agent-driven
(`start_board_run` + the `development/drain-dag` skill), and `pathly-run` is a separate CLI
path entirely (see its own section below).

### 2. Inside a stage — single spawn vs fan-out

```
                        fan_out.run_stage(state, flow_config, STATE, ...)
                                         |
                    parallel_config(flow_config, STATE)
                                         |
          +------------------------------+------------------------------+
          | None (no parallel_states entry)      | entry present         |
          |  -- every state of 9 flows --        |  -- goal-loop/DRAINING|
          v                                      v   (the ONLY opt-in) --+
   _run_stage_via_terminal(...)          fan_out._drain(...)
   ONE agent, stage's own prompt          |
          |                               +- scope = _frontier_scope(state)
          |                               |    the run's BOARD scope, NOT state.topic
          |                               |    (a goal run's topic is its own slug)
          |                               |
          |                               +- isolation <- YAML
          |                               |    lane -> AuditedLaneIsolation
          |                               |    serial -> Serial ; worktree -> Serial+warn
          |                               v
          |                        drain.drain_frontier()   <- ONE scheduler_loop
          |                        - owns CostCapTracker       call site in the repo
          |                        - wraps spawn_fn EXACTLY once
          |                        - ORs tracker.exceeded() into abort_check
          |                               |
          |                               v
          |                        scheduler_loop()  -- frontier poll --+
          |                          |                                  |
          |                          |  max_concurrency(ready_lanes)    |
          |                          |    +- re-AUDITS every round      |
          |                          |       undeclared files -> 1      |
          |                          |       cross-lane overlap -> 1    |
          |                          |       audit raised     -> 1      |
          |                          |                                  |
          |                          +-> worker(task) -+  <=1 per lane  |
          |                          +-> worker(task) -+                |
          |                          +-> worker(task) -+                |
          |                                  | completion_q             |
          |                                  +-- retry | escalate ------+
          |                                      (task_retry)
          |                               |
          |                               v  frontier drained
          |                        _merge_drain_result()
          |                        {cost_usd, session_id=None, outcome, result}
          v                               v
          +--------------> same dict shape <-------  _loop is untouched below here
                                         |
                                         v
                      run_gates(STATE -> next)   <- THE JOIN, once
                      (goal-loop's: require_tasks_done + command_gate build + test
                       + floor_gate + task_checks; each flow declares its own under `gates:`)
```

`fsm_state.current` stays the **scalar** `"DRAINING"` for the whole drain. The parallelism is
inside a state's *execution*, not in the state vocabulary — which is why `write_state`'s
legality check, the `STATE.json` export, the `pathly-*` CLI and Studio's flow editor never had
to change.

### 3. The spawn chokepoint — adapter-agnostic, run-keyed

```
  supervisor._run_stage_via_terminal(state, prompt, adapter, model, run_id, ...)
        |
        +- _resolve_spawn_argv()      <- the seam a NEW ADAPTER touches
        +- _record_spawn_identity()   <- run_history {run_id, feature=slug, board_scope}
        +- _issue_spawn_token()       <- run_tokens {sha256(token) -> run_id, role, board, scope}
        |
        +--> SSE  TERMINAL_SPAWN {tab_id, run_id, run_token, argv[], cwd, adapter}
        |         on /events/spawn (topic-independent); /events/runner and
        |         /events/runs get the same event without run_token
        |                    |
        |      +-------------+--------------+   exactly ONE host may listen
        |      v                            v
        |   Studio (node-pty tab)      pathly-pty-host (pipes, stdin=/dev/null)
        |      |  desktop, visible          |  server/CI, headless
        |      +-------------+--------------+
        |                    |
        +-<-- POST /runner/terminal/started      releases wait_started(30)
        |
        |     ... agent runs; writes AGENT_DONE to the DB mid-run ...
        |
        +-<-- POST /runner/terminal/result {run_id, exit_code, stdout_tail, adapter}
                     |
                     +- parse_result(adapter, stdout_tail)  <- ONE server parser
                     |    claude -> total_cost_usd ; codex -> tokens ; agy -> estimate
                     +- _patch_last_agent_done(run_id) -> BILLING_UPDATE  (authoritative)
                     +- record_stage_provenance()  -> git diff, SERVER-measured
                     +- run.mark_pty_result()  -> unblocks the supervisor
                                |
                                v
                     result merged from TWO sources:
                       stdout      -> session_id, cost_usd
                       AGENT_DONE  -> summary, outcome (the pass/fail signal)
```

`run_id` shapes are the identity every consumer keys off: `{topic}-{N}-{ts}` per FSM stage,
`sched-{task_id}#{attempt}` per DAG task, a bare uuid per board/parent run.

### 4. Data — the DB is the authority; disk is a seed or an export

```
  SEEDS (disk -> DB, once)                THE AUTHORITY              EXPORTS (DB -> disk)
  ------------------------                -------------              --------------------
  core/flows/*.flow.yaml --_refresh_flows-->+------------+
                                            | flow_nodes |
  abilities/*.md, prompts/*.md --compose--->| flow_yaml  |
                                            +------------+
                                            | fsm_state  |--atomic--> STATE.json  (git)
                                            +------------+
                                            | fsm_events |--debounce-> EVENTS.jsonl (ignored)
                                            +------------+
                                            | comms_*    |--debounce-> BOARD.json   (ignored)
                                            +------------+
                                            | run_history|
                                            | agent_invoc|
                                            +------------+
  Runtime code reads the DB - never the mirror.
  Enforced by scripts/check_no_mirror_reads.py (lint `consistency` job).
```

Telemetry is a **projection**, not a second write path:

```
  agent writes ---> AGENT_DONE ---+
  (completion-report)             |  append_event() live hook
                                  +---> invocation_projection
  /runner/terminal/result --->    |     - 1 row per AGENT_DONE, keyed by fsm_events.seq
  BILLING_UPDATE -----------------+     - BILLING_UPDATE folded in (billing WINS, never summed)
                                        - _price_if_needed(): cost==0 & tokens>0 -> estimate
                                              |
                                              v
                                       agent_invocations ---> /db/stats, /db/rollup,
                                                              /telemetry/trends, Monitor
```

### 5. Prompt assembly — three paths, ONE injector

```
  FSM stage            board run                 DAG task
  ---------            ---------                 --------
  build_prompt()       start_board_run()         task_prompt.build_task_prompt()
       |                    |                          |
  compose_skill()      compose_skill()           compose_skill("development/execute-task")
       |                    |                          |
       v                    v                          v
  _inject_prompt_vars( _inject_board_prompt_vars  _inject_vars(...)
    run_category=       run_category="single")     run_category="loop")
    "flow")                 |                          |
       +--------------------+--------------+-----------+
                                           v
                          ONE injector: fsm_compose._inject_prompt_vars
                          <fsm_feature> <feature_path> <feature> <board> <run_category>
                                           |
                                           v
                              + results of the tasks it depends on  (DAG task only; before the contract)
                              + RUNNER_CONTRACT_BLOCK  (one constant, all headless paths)
                              + retry ladder (attempt >= 2) + the root-cause-debug guide
                              + board context (governance + semantic, per-tier budget)
```

**Why all three must share the injector:** an unsubstituted `<fsm_feature>` makes the agent write
its `AGENT_DONE` under a literal string — mis-keyed event, no projected invocation, so the run is
unbilled and absent from the Monitor. The DAG path had no injector at all until Phase E; see the
prerequisites in the Phase E section below.

**Governance in those prompts — pending decisions and standing orders.** All three paths get
their board context from `runner/comms_context.retrieve_board_context(..., role)`, and its
decisions from `runner/comms_governance.governance_decisions`: the `pending` decisions of the
tiers the run reads (the first `/comms/acknowledge` sets a row `active`, and an ordinary decision
then leaves the governance block), plus the **standing orders**, the decisions with
`comms_messages.binding = 1`. A standing order stays in the prompts whatever its status, until the
chief supersedes it (nobody can delete one, see "Who retires or forges a standing order" below;
`db/queries/comms_directives.get_binding_decisions`: one static
statement, the board and scope lists passed as one JSON string each and unpacked by `json_each`,
built into SQLite since 3.38.0). It reaches the prompts of the role it is addressed to
(`to_agent`, matched exactly), and every prompt when it is addressed to `*`; an empty role gets `*`
only. It is read from the tiers the run reads **and always from the project board**, even when the
run's project tier is off, every tier off included (`standing_orders_only`): a context-budget
toggle does not mute a standing order. "Always" needs a project root: with an empty
`project_root` there is no project scope, so that extra project-board read is skipped. A pending row with
`binding = 1` is served by that role-aware query and left out of the pending half, and
`_is_context` keeps a binding row out of the semantic Context channel, so a directive for the
builder reaches no other role by either route.
`render_governance_lines` prints standing orders in a block of their own,
`**Standing orders (binding; a newer decision does not override them):**` with one
`BINDING for <role|all roles>: <text>  [id: …]` line each (every run of whitespace in the text,
line breaks included, becomes one space, so a row's text cannot start a line of its own and forge
a second entry or a `**Decisions …**` header), before the ranked decisions and not inside them;
the ranked list's "the one listed FIRST wins" and "post a decision with `supersedes`" rules do not
apply to it, and the block says only the human, through the chief, replaces one. The formatter
trusts only the `_binding` mark `comms_governance` sets, never the stored column.
If the standing-order query raises (no `json_each`, a lock), `governance_decisions` logs a warning
and serves no order: the pending half is then left as `get_pending_decisions` returned it, so a
pending `binding = 1` row still reaches the prompt, but as an ordinary pending decision in the
ranked list (for every role), and an acknowledged order is missing from that prompt; a run with
every tier off gets no block.

The role each path passes: `fsm_compose.build_prompt` passes `agent_role_of(agent)`, which is
`_SKILL_AGENT_ROLE` (six skills: `team/build` builder, `team/review` reviewer, `team/test` tester,
`team/plan` planner, `team/design` designer, `team/retro` planner) and otherwise the agent's last
`/` segment (`scout` is `scout`; `debug/build` and `fix/build`, the debug and quick-fix fixers,
are `build`), so a directive addressed to `builder` does not reach those fixers, and only a `*`
directive does.
That is the safe direction (nothing reaches the wrong role); `test_binding_directives.py` pins it
so a change to the table is deliberate. `task_prompt.build_task_prompt` passes `builder`;
`board_run.start_board_run` passes the run's `agent` (empty, as for a plain single-agent run,
means `*` only). `POST /comms/agent-context` (board-info mode) still lists pending decisions
without a role.

**Who retires or forges a standing order (chief-agent 16).** Only a live run token whose role is
`chief` (`run_identity.is_chief_run`, asked as `_supersede_on_post.chief_may_retire`; not the server
secret, not another role's token, not a request with no token) retires a standing order, and only by
superseding it. `is_binding` is `binding = 1`, the flag `get_binding_decisions` reads. Four doors are
closed for everyone else: a `supersedes` list on `POST /comms/post` skips a `binding = 1` row with
reason `binding` (the post itself is stored and `supersede_skipped` names the id);
`POST /comms/supersede` answers 403 `{"error": "only the chief retires a binding directive"}` for it
(`refuse_agent_supersede`) whether the caller sent another role's run token, no token, or no token and
the server secret; `POST /comms/delete` answers the same 403 for **every** caller, with or without
`force` (`soft_delete_message` answers `"binding"`; the chief gate does not list `/comms/delete`, so a
chief token never gets that far: a directive is superseded, not deleted); and hydration stores
`binding = 0` for every message row it imports. `POST /comms/hydrate` (the only caller of
`hydrate_project`) reads a file, so `hydrate_board` leaves out a row whose `board` and `scope` are not
those of the file it came from (the scope is compared exactly: `hydrate_project` passes the normalised
root and the exporter writes that spelling into every row, so an export followed by a hydrate keeps
every row of its own board, and a row that spells its root another way, `<root>/` or `C:\proj`, is left
out rather than stored under a scope no board read asks for) and a row whose `id` is not a string with
something in it after stripping (a blank id would be a blank primary key); an artifact is inserted only
when its `message_id` is a message that is in the database under the file's own board and scope once the
rows went in (a file row that reuses the id of a message on another board is not inserted, and an
artifact for that id used to land on that other message); `hydrate_board` returns True only when at least
one row of the file is in the database under that board and scope afterwards, so a file that adds
nothing is False and `hydrate_project` lists its scope under `skipped`. That is what a clone at a
different path, or at the same path in a different letter case, gets for the project board: every
row names the exporter's root, the scope is compared exactly, so no row is imported and the scope is
under `skipped` (the feature boards are keyed by name and are unaffected); a file that is not
a JSON object imports nothing; and `hydrate_board` does not raise on any of it, so one hostile entry
(an `id` that is a list or a dict, say) cannot stop the boards `hydrate_project` reads after it.
`comms_hydrate._unverified` stores `binding = 0`, and an
`author_source` the file names other than `none` is stored as `legacy` (`none` stays `none`: the read
wall withholds a `none` row from a restricted role whatever its `author_role`, which it does not do
for a `legacy` row). A standing order therefore
does not survive a fresh clone: its text comes back as an ordinary decision and the chief posts it
again. The other `author_*` columns of a hydrated row are stored as the file has them.

Still open: the standing-orders block has no cap on the number of orders or on its total size (the
writer caps one order's text at 8 KiB of UTF-8 and refuses control characters), and Studio can neither
post nor retire a standing order until the UI token (RRP-2b), because its requests carry no run token.
`tests/comms_board/test_binding_retire_writers.py` pins the writers of `deleted_at` and
`superseded_by` and their callers, so a new way to retire a row is decided, not found.

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

> `write_state` also stamps `flow` (the flow name) into the state dict whenever a flow config is
> passed. Every flow ends at the literal `"DONE"`, so `current` alone cannot distinguish
> `consultation`'s DONE ("the goal was decomposed; none of it is built") from `team`'s DONE ("the
> feature shipped") — which is how a decompose-only board reads as a delivered feature with 14/14
> tasks pending. A flow-less call leaves any existing stamp alone rather than erasing it.

- **Flows** load **DB-first at runtime** (`_load_flow`): `flow_nodes`/`flow_edges` → `flow_yaml` blob → packaged `.flow.yaml`. The `core/flows/*.flow.yaml` files are the **version-controlled seed**, re-synced into the DB on every server start (`_refresh_flows`). The filesystem read is a seed + resilience fallback (DB-unavailable / `project_root=None` CLI), not live config.
- **Gates persist per EDGE** (`flow_edges.config_json`, keyed `"SOURCE->TARGET"`), but the engine
  ALSO honours the wildcard form `"->TARGET"` (`run_gates` looks up both). A wildcard matches no
  edge row, so it used to be dropped on the way into the DB — and since flows load DB-first, a
  flow authored with one silently ran WITHOUT it. `flow_graph_ops` now carries non-edge gate keys
  through as `_nonedge_gates` flow-level config and merges them back on assemble, so the
  round-trip is lossless as `_STRUCTURAL_FLOW_KEYS` already promised for every other key.
  `team`/`team-build` use `->DONE: require_tasks_done` — a DELIVERY flow's DONE claims the feature
  shipped, so it must not be reachable while board tasks are unfinished (TESTING and RETRO can
  both post new work, which the `REVIEWING->TESTING` gate cannot see). The consultation flows
  deliberately do NOT carry it: they END at decomposition, so pending tasks are their correct
  output, not a lie.

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
POST /runner/agent-answer            ← answer an agent's mid-run human question (a chief token sends `cite` only — "Chief gate")
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
humans post messages, ask/answer questions, decompose DAG tasks, and supersede stale notes. The
message routes load from `messages.py` (`ROUTE_MODULES`): `messages_read.py` (`GET /comms`,
`POST /comms/search`), `messages_write.py` (`POST /comms/post`) and `messages_crud.py`
(acknowledge, answer, edit, delete, supersede, trash, restore).

```
POST /comms/post            ← post a message (embedding computed for hybrid search); optional `supersedes:[id,…]` retires the decisions this one replaces IN THE SAME CALL (see below; a binding directive in the list is skipped with reason `binding` unless the caller is a live chief run)
GET  /comms                 ← list board messages (scoped)
POST /comms/search          ← hybrid (semantic + keyword) search; semantic arm floored at SEMANTIC_DISTANCE_CEILING, keyword hits bypass; no match → [] (never padded with recent messages). Reached by AGENTS too via the `board-search` fragment (own board only) — the self-authored second query the pushed context can't make; Studio's search box is the other caller
POST /comms/promote         ← copy a decision/constraint UP a tier (feature→project→global). COPY not move: the source board is the audit record of HOW the decision was reached. Stamps promoted_from/original_scope on the copy + promoted_to on the source (the three columns migrations.py reserved and nothing read). Idempotent, keyed off the COPY's promoted_from so one message can promote to two tiers. Own permission set `_PROMOTE_WRITERS` = {director, evaluator, human, **retro**} — NOT _GLOBAL_WRITERS, else the RETRO stage (the one headless role whose job IS capturing lessons) could never promote. decision/constraint only
POST /comms/acknowledge     ← mark a message acknowledged
POST /comms/answer          ← answer a posted question
GET  /comms/tasks           ← list DAG tasks
POST /comms/tasks/complete  ← mark a task complete
POST /comms/tasks/status    ← BULK terminal write-back (done|failed) for a resolving agent: `{task_ids,status,reason,from}`; reports updated/newly_ready/blocked/unknown. Re-opening (→pending) is deliberately NOT offered — that is a supervisory act
POST /comms/tasks/floor-allow ← HUMAN only (403 for a live run token): set one task's floor allow list `{message_id, allow:[…], refreeze}`; `refreeze` re-copies the live text into `claimed_text` (see "Frozen task text" below)
POST /comms/tasks/run       ← run ONE task headlessly: claim it, spawn a builder on its prompt, complete on success
POST /comms/tasks/stop      ← stop a single-task run: kill its board run and revert the task to pending
POST /comms/attach          ← attach an artifact to a message
GET  /comms/artifacts       ← list artifacts linked to a message (comms_artifacts table)
GET  /comms/trash           ← list trashed messages
POST /comms/restore         ← restore a trashed message
POST /comms/supersede       ← mark a message superseded_by another (standalone form, used by Studio's supersede menu and the consolidate skill; an agent run is held to the same decision-only, own-board rules as `/comms/post` + `supersedes`; a binding directive is 403 `only the chief retires a binding directive` for every caller but a live chief run, a request with no token or only the server secret included)
POST /comms/directives      ← CHIEF TOKEN ONLY: post a BINDING directive (standing order) `{project_root, to_agent: "*"|<role>, text}` → 201 `{id}`. `blueprints/comms/directives.py`; the only route that sets `comms_messages.binding = 1` (`db/queries/comms_directives.post_directive`: a `decision` from `chief` on the project board, `from_agent="chief"`, written with `binding = 1` in its one INSERT: `post_message` takes a keyword-only `binding` (default 0) that only `post_directive` passes, and `/comms/post` still ignores a `binding` in a body, so a failure leaves no ordinary decision behind and a retry no second copy; the scope is `fsm_compose.resolve_board_scope("project", project_root, "")`). 403 for every other caller: no token, any other role's token, and a request that carries only the server secret (what Studio sends today; the UI path waits for the UI token, RRP-2b). The chief gate has already checked, for a chief token, that the tier may `decide`, that `project_root` is the session's project and that only `project_root`/`to_agent`/`text` are sent. 400 for a `to_agent` that is not `*` or `^[a-z][a-z0-9_-]{0,39}$` (matched exactly against a prompt's role, so no upper case or padding), a `project_root` that is missing, `null` or the empty string (a `project_root` of only spaces from a chief is the chief gate's 403 `that is not this chief's project` first, since it is not the session's root), or a `text` that is blank, over 8 KiB in UTF-8 BYTES, holds a control character other than newline and tab (a NUL would fail every spawn of the role: `subprocess` refuses an embedded null byte), or is not UTF-8 encodable; the text is stored stripped. Broadcasts the `COMMS_UPDATE` a new row gets. The route looks the caller up once and uses that identity for the check and for the row's stamp (a second lookup could find the session closed and store `author_source` `none`). A directive is replaced with `/comms/supersede`, never edited
GET  /comms/scope           ← read the active board scope
POST /comms/scope           ← set the active board scope
GET  /comms/permissions     ← role-based write permissions
POST /comms/delete          ← soft-delete a message; a binding directive is refused with 403 `only the chief retires a binding directive` for every caller (it is superseded, never deleted)
POST /comms/edit            ← edit a message's text (e.g. goal rename); re-stamps the row to the EDITOR (`stamp(caller_identity(request))`: their token's role and run, or `author_source="none"` with no token), not the original author, so words cannot sit under another run's `token` stamp. Anyone may still edit; Studio's goal rename sends no token yet, so it stamps `none`. A row with `binding = 1` is refused with 409 `{"error": "binding directives are superseded, not edited"}` and nothing changes (`update_message_text` answers `"binding"`; replace a directive with `/comms/supersede`)
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
POST /comms/hydrate         ← board disk-mirror: import a project's on-disk BOARD.json mirrors into the DB (fresh-clone; DB-authoritative, no-ops non-empty boards). Stores `binding = 0` for every row, leaves out a row of another board or scope than its file's, and stores a claimed `author_source` other than `none` as `legacy` (see "Who retires or forges a standing order"). Answers `{hydrated, skipped}`: a scope is under `hydrated` only when at least one row of its file is in the DB afterwards, and a file that adds nothing (empty, or every row names another scope, as in a clone at another path) is under `skipped`
GET  /events/comms          ← SSE stream of comms board updates (streams blueprint)
```

**Board closure — how a resolution lands in state.** The board is append-only, so nothing
retires on its own; three write paths make a resolution durable instead of prose:

| Resolution | Write path | Guard |
|---|---|---|
| this decision replaces that one | `POST /comms/post` with `supersedes:[id,…]` (`blueprints/comms/_supersede_on_post.py`) | explicit ids ONLY — never inferred from text/embedding similarity, because silently retiring the wrong governance is worse than a duplicate. Capped, de-duplicated; only on a `decision`/`constraint` post (else 400), and only targets that are themselves a decision or constraint on the SAME board and scope (`not_a_decision` covers escalations, so a human gate cannot be superseded away; `other_board` stops a feature post retiring a project/global call; `binding` leaves a standing order to a live chief run). Self-reference and bad ids degrade to a per-id `skipped` reason and never fail the post |
| these tasks are settled | `POST /comms/tasks/status` (`blueprints/comms/tasks_status.py`) | needs a live `X-Pathly-Run-Token` (403 otherwise), and each task must sit on the token's board and scope (else `refused`); the status line is stamped as the caller. `done`/`failed` only; unknown ids reported, not dropped |
| a human gate is closed | `POST /comms/acknowledge` (human; an agent run's live token gets 403 on a human-addressed escalation, as do `/comms/delete` and `/comms/answer` — `_helpers.refuse_agent_on_human_gate` — except a chief's acknowledgement as `agent: "chief"` that cites a human message typed after the escalation ("Cited answers" under the chief gate), which the gate lets through for that one id; and `POST /comms/supersede` holds an agent run to the same decision-only, own-board rules as `supersedes` — `_supersede_on_post.refuse_agent_supersede`) | an agent decision does NOT close an escalation — `runner/comms_formatters.render_governance_lines` says so in the injected block when a decision post-dates an open escalation, and `fsm_human_gate` now makes it structurally true (below) |

The agent-facing half is in `core/skills/fragments/comms-post.md` (supersede a decision you
replace, by the `[id: …]` the governance block now shows on each decision) and
`core/skills/planning/evaluate.md` Step 5 (close what your analysis settled — evidence-gated).
Governance decisions render higher tier first (global > project > feature), newest first within a
tier: the feature board accepts any role, so recency alone let a newer feature note outrank an
older project or global call. A binding decision sits outside that ranking, in the standing-orders
block that precedes it (see "Prompt assembly").

**Human escalation gate (`fsm_human_gate.py`).** An unacknowledged escalation with
`to_agent='human'` on the run's board/scope **blocks the transition it stands in front of**.
The gate checks the run's topic scope AND its parent board scope (`gate_scopes`): a goal run's
topic is `features/<f>/goals/<slug>` while its agents post on `<f>`.
`complete_stage` checks it after `next_state` is resolved and before the transition is
committed, returning the standard `_blocked_response` (`decision: escalate`, `blocked: true`)
plus a `human_gate` block naming the blocked transition and the escalations, and appending a
`GATE_FAILED` event. Previously these fired and gated nothing — a run walked past four pending
human checkpoints to `DONE`.

- **Only `to_agent='human'` gates.** Agent-addressed escalations are ordinary feedback routing
  and would wedge runs the pipeline self-heals; `"*"` (the default `to` on every post) does not
  gate either, or every broadcast would be a checkpoint.
- **Server-written escalations do not gate** (`author_role='system'`, from the provenance
  stamp): the park notice for a headless human checkpoint and similar rows announce a checkpoint
  the engine already enforces through a feedback file, so gating on them would re-park every
  resumed run (`POST /runner/resume-parked`). The override decision itself is posted with
  `system_stamp()`.
- **Two ways a human clears it:** `POST /comms/acknowledge` (the normal path), or re-send
  `complete_stage` with `force_past_gate: true` — which advances, posts a `GATE OVERRIDE`
  decision naming every skipped gate (so a bypassed gate stays auditable) and acknowledges
  them, so one force is enough. `force_past_gate` is a human affordance: no agent prompt,
  fragment or block response mentions it, and `/complete_stage` returns 403 for it when the
  caller sends a live run token.
- **These guards are keyed on the run token.** They stop an agent run that sends its
  `X-Pathly-Run-Token` (every runner spawn's fragments do). A tokenless loopback caller is still
  treated as a human, because the server cannot tell Studio from a local process until the UI
  token (RRP-2b) exists.
- **Fails OPEN** on a DB read error (same choice as `require_tasks_done`) — a gate that cannot
  be read is reported absent rather than blocking every transition in the product.
- Studio has no dedicated force-advance button yet; today the override is the `complete_stage`
  field. Acknowledging from the board clears the gate through the existing UI.

**Frozen task text and the human-only floor allow list (build-proof).** Two additive
`comms_messages` columns (`db/migrations_incremental.py`); a task claimed before them reads
`NULL` in both.

- **`claimed_text`** — `claim_task` sets `claimed_text = COALESCE(claimed_text, text)` in its one
  `UPDATE`, so the first claim freezes the task's text, and with it any ```` ```check ```` block. A retry
  (`task_retry.retry_task` back to pending, then a new claim) keeps the first copy, so a builder
  that edits its own task between attempts does not change what it is proven against. Every
  claim goes through `claim_task`: the scheduler's `sched-<id>#<n>` claims,
  `POST /comms/tasks/claim` (team-flow builders claim with `run_id: "build"`) and
  `/comms/tasks/run`.
- **`floor_allow`** — a JSON list of `proof.floor.CATEGORIES` names a human allowed for that one
  task. Its only writer is `POST /comms/tasks/floor-allow` (`blueprints/comms/tasks_floor.py`),
  body `{message_id, allow: [...], refreeze: false}` → 200 `{ok: true, allow: [...]}` (sorted).
  403 when the caller sends a live run token (the `force_past_gate` rule); 400 for an unknown
  category (the error names the valid ones, from `proof.floor.parse_allow`), a malformed body or
  a row that is not a task; 404 for a missing row. `refreeze: true` also copies the live `text`
  into `claimed_text`: how a human corrects a broken check without allowing `task-edit`. Task
  text is agent-written, so an allow line there would let the planner excuse the builder.
- **Limit:** as for `force_past_gate`, a caller with no token (or an unknown or revoked one) is
  treated as a human. Studio has no control for the list yet; set it with `curl` from a shell.
- Reads live in `db/queries/task_proof.py`: `get_task` (any live row; the caller checks the
  type), `tasks_claimed_since` / `tasks_completed_since` (goal-scoped when `goal_id` is given,
  else `(board, scope)`, as `require_tasks_done` scopes; the window compares parsed times, since
  claims stamp `+00:00` and event `ts` values end in `Z`) and `set_floor_allow`. The goal-loop
  task proof reads both ("Task proof in the goal-loop drain"); `floor_gate`, `scope_gate` and the
  Review packet read the claimed ones, `task_checks` the completed ones.

### Chief endpoints (chief-agent)

The chief is a long-lived interactive agent a human opens for a project. Studio has no launcher for it
yet (round two), so `POST /chief/open` is called directly.
`blueprints/chief/session.py` is a thin layer over `supervisor/chief_session.py`:

```
POST /chief/open            ← {project_root, engine, preset, prompt?, model?} → 201 {run_id, tab_id, tier, engine}
POST /chief/close           ← {project_root} → 200 {closed: true|false}
GET  /chief/session?project_root=  ← {open: false} | {open: true, run_id, tab_id, tier, engine, opened_at, runs_started, max_runs_per_session, max_cost_usd_per_run}
POST /chief/human-messages  ← {run_id, hook_secret, text, session_id, relayed?} → 201 {id, kind}   (blueprints/chief/human.py)
```

- **Open:** 403 when the caller sends a live run token (an agent cannot open a chief); 400 when a
  field is missing or not a string, or `open_chief` raises `ValueError` (its message is passed
  on); 409 `{error, run_id, tab_id}` on `ChiefAlreadyOpen`; 409 `{error, run_id}` on
  `ChiefClosedWhileOpening` (a close landed after the session row and before the token: the open
  revoked its token, sent no spawn and left the session closed). `open_chief` gets the runner
  broadcaster (`sse._broadcast_runner`), so the `TERMINAL_SPAWN` reaches whichever spawn host
  is listening. `engine` and `preset` are required strings; `prompt` and `model` are optional,
  but a key that is present must be a string (`"prompt": null` is a 400).
- **The prompt a chief is pasted** (`supervisor/chief_presets.py`, `compose_prompt`) is three
  parts: the **style**, the `chief-connect` **fragment**, then a last line `Your project root:
  <root>`. The style is the request's `prompt` when it gave one, else `default_style`: the
  user's file `chief/<preset>` (project over global) when there is one, else the built-in text
  of that name (`BUILT_IN`: `status`, `planner`, `operator`). A preset that is neither has no
  built-in text, so without a `prompt` `open_chief` raises `ValueError` ("prompt is required for
  preset ..."; a blank or non-string one is "prompt must be a non-empty string"). The fragment
  (`src/pathly_data/core/skills/fragments/chief-connect.md`) is appended to **every** chief
  prompt, the user's own style and a request's `prompt` included, so a saved style cannot drop
  the rules it holds: the one tool (`pathly api`; quote a path that has a query string, one
  `pathly` command per call with no pipe, a root percent-encoded in a query string and as written
  in a body), reading before acting (the session, goals, pending questions, pending escalations
  and runs), answering with `cite=<id>` only, and that only the user gives orders. The 64 KiB
  limit applies to the style,
  before the fragment and the root line. The root line hands the chief the stored root
  (`normalise_project_root`), the string the gate compares `project_root` with, so it never has
  to read its directory from the shell. The texts name no cost or run number: they point to
  `GET /chief/session` (`runs_started`, `max_runs_per_session`, `max_cost_usd_per_run`), where the
  current limits are. Every `pathly api` example in a text is read against the gate's tables by
  `tests/http_api/test_chief_prompt_text.py` (the route exists, the tier holds the action, every
  key is on the route's list, a post is `from` the chief, an answer carries `cite` and its target
  only), and the fragment's examples must be reads because it goes to every tier.
  `tests/http_api/test_chief_prose_rules.py` pins the rules by phrase (a deleted sentence fails a
  test); a path with a query string is quoted in every example, and a route that needs `feature`,
  `board`/`scope` or `project_root` (`GET /comms`, `GET /runs`, `GET /chief/session`) is shown with
  them in the help and in every text (`test_chief_help_routes.py`): a bare `GET /runs` answers 200
  `[]`, which a chief would read as "no runs".
- **`pathly api METHOD /path [json | -]`** (`chief_cli.py`, the `pathly` console script) is the
  chief's only door to the server, because its settings allow `Bash(pathly *)` and deny `curl`
  and `wget` (`runner/chief_argv.py`). It sends one request to `127.0.0.1:<fsm_port>` with the tab's
  `PATHLY_RUN_TOKEN` as `X-Pathly-Run-Token` (and `X-Pathly-Secret` when the machine has one),
  prints the server's answer to stdout and a `pathly: HTTP <status>` line to stderr for a non-2xx.
  Exit **0** for a 2xx, **1** for any other status or an unreachable server, **2** for a usage error
  (a missing token, a path that is not `/...`, a path or body that is not valid UTF-8, a body that
  is not a JSON object, a GET with a body, a token or server secret that holds a character an HTTP
  header cannot carry, a body nested too deeply to parse, a body read from standard input over
  `MAX_BODY_BYTES`, 1 MiB): nothing is sent in that case, and the last three give one line that names
  the problem and never the value. The token and the server
  secret (read once per command) are never printed (an answer or an error that holds either is
  redacted). At most `MAX_ANSWER_BYTES` (256 KiB) of an answer are read, in bounded reads, and
  printed; a longer one is cut (never inside a character or half a token), a `pathly: the answer was
  cut` line on stderr says how many bytes were shown, and the exit code still follows the status. What a chief may do is decided by the chief gate, not here: a refusal is the gate's 403
  body, printed as it came. `pathly help` lists the routes a chief uses most, each with what it
  needs (`GET /runs?project_root=<root>`, `GET /comms?board=project&scope=<root>&feature=project`,
  `GET /chief/session?project_root=<root>`), and `POST /comms/acknowledge` with `{message_id, agent:
  "chief", cite}`, how an operator chief closes an escalation addressed to the human.
- **Close:** 403 for a live run token. It closes the project's open session with reason
  `closed from Studio` (`close_chief`: revokes the token, removes the folder, drops the run) and
  then sends `TERMINAL_KILL {tab_id, run_id}` on topic `chief:<run_id>` so the host closes the
  tab, because `close_chief` kills no process. `closed` is false, and nothing is killed, when the
  project has no open chief (or the watcher closed it first).
- **One project, one key:** `chief_session.normalise_project_root` (`scope_names.normalise_root`:
  forward slashes, no trailing slash; a bare `/` or `C:/` keeps its one) is applied by `open_chief`
  and by all three routes, so `/p` and `/p/` are one project and cannot get two open chiefs. The
  board code (`comms/_helpers.py`, `runner/comms_context.py`, `runner/board_scope.py`) uses the same
  function, so a root has one spelling on every side.
- **Restart:** `app.main()` calls `chief_startup_cleanup()` before the server serves, inside a
  `try` that logs a warning and goes on: it closes every session still open (reason `server
  restart`, token revoked) and removes their `~/.pathly/chief/<run_id>/` folders, because a chief
  open across a restart has no watcher left to close it. It asks first whether something already
  answers on the host and port it is about to serve (`chief_session.something_answers`: a TCP
  connect, to 127.0.0.1 for a wildcard host; any error is "nothing answers"). If so it logs one
  warning (`something already answers on <host>:<port>: the chief sessions are left open`), skips
  the cleanup and goes on to fail in `app.run` ("address already in use"), so a second server
  started by mistake on the first one's port no longer closes the running server's chief. A second
  server on another port still does (not protected; not decided).
- Same limit as the other human-only routes: a caller with no token (or an unknown or revoked
  one) is treated as a human until the UI token (RRP-2b) exists. The chief's own token is refused
  here by the chief gate ("Chief gate" below).
- **Human messages:** `POST /chief/human-messages` is written to by the chief's
  UserPromptSubmit hook only, `python -m pathly_hooks.chief_prompt --run-id <id> --secret-file
  <path> --port <port>` (the command `open_chief` writes into the session's `settings.json`).
  The hook posts `{run_id, hook_secret, text, session_id}` through
  `fsm_http_client._request_json` (127.0.0.1, 5 s) and always exits 0; for a reply of kind
  `human` it prints `Pathly recorded this as human message <id>; cite it with cite=<id> when you
  relay an answer.` (Claude Code adds hook stdout to the chief's context), for `style_prompt`
  (the session's first prompt) and `relayed` it prints nothing. The route answers 400 for a body
  that is not an object or a `text` that is blank, not a string, invalid Unicode or over 64 KiB
  (bytes); 404 for an unknown or closed session; 403 when sha256 of `hook_secret` is not the
  session's `hook_secret_hash` (`hmac.compare_digest`; a session with no stored hash never
  matches) or `session_id` is missing or not the session's `cli_session_id` (`{"error": "not
  this chief's claude session"}`; a codex session has none, so it records nothing); else
  `add_human_message(..., relayed=bool(relayed))` and 201 `{id, kind}`. It is not in
  `chief_routes.ROUTE_ACTIONS`, so the chief gate refuses it to a chief token at every tier: **no
  chief token can write a message.** That is all "only the hook can write" means. The secret
  file (0600) is readable by every other process of the same user and the claude `--session-id`
  is in the chief's argv, so a same-user process that reads both (a headless builder, say) can
  post a `human` row (spec § Risks).
  - **What the hook can and cannot tell apart.** The session id binds a recorded prompt to the
    chief's claude process, not to the typist, and claude runs the hook for prompts nobody typed
    with the same keys and values as for a typed one (measured on claude 2.1.304 in `claude -p`
    stream-json and in an interactive tab). Only a wrapper around `prompt` differs. The hook
    sends `relayed: true` when `<task-notification` or `<cross-session-message` is anywhere in
    the prompt (a tag that starts with either name, `<task-notifications>` and `<task-notification_v2>`
    too, since the list cannot know every spelling), and the server stores kind `relayed`, never citable (a typed prompt that holds
    the tag is wrongly uncitable too; the human retypes it). **That list is a deny-list of the
    wrappers measured, not a test for "typed":** a prompt without one is stored as `human`
    whether or not anyone typed it. The chief's claude has exactly four tools (the `init`
    message lists `Bash`, `Glob`, `Grep`, `Read`; no MCP server, no Agent, Monitor, Cron or
    Skill). What can still make claude deliver a prompt, and what the hook does with it:

    | Source | What the hook sees | Handled |
    |---|---|---|
    | A background Bash ends (`run_in_background`) | `<task-notification>` with the Bash call's `description` in `<summary>`, so the chief picks words in it (a forged "Approved by the human: ...") | flagged. Measured: `-p` and tab |
    | A foreground Bash hits its `timeout` (moved to the background, "you will be notified") | the same wrapper | flagged. Measured: `-p` |
    | A background command's last output looks like a question (45 s without output) | the wrapper, then `Last output:` and the command's own output after the closing tag | flagged (anywhere in the prompt). Measured: `-p` |
    | Quiet-shell and goal check-ins | built by the same function (read in the binary; the first sits behind a server-side flag) | flagged; not measured switched on |
    | Another claude session's message | `<cross-session-message ...>` | flagged. Measured without `--restricted`; a `--restricted` claude binds no inbox socket, so none arrives |
    | A task in the project's `.claude/scheduled_tasks.json` (including one another session of that project made with a durable `CronCreate`) | **a bare prompt, nothing to tell it from typing** | **closed by `CLAUDE_CODE_DISABLE_CRON=1`, which the chief's settings set** (see "Switches", measured on 2.1.304 only). Without it, stored as `human`: measured in a tab with the chief's flags, fired at the first minute boundary (23-26 s after the typed prompt), also when `createdBySessionId` named another session of the project. The chief cannot write the file (no Write or Edit; Bash is `pathly *`), a same-user process can |
    | Usage-limit auto-continue, worker-restart notice | fixed text in the binary ("Your claude.ai usage limit has reset. Continue the task ...", "This session's worker process was restarted ..."), not chief-controlled | **open**, not measured (needs a usage limit). Would be stored as `human` |
    | The human accepting a suggested prompt (Tab, Enter) | model-written text submitted by a human act | accepted |

    Other tags claude names as harness input (`teammate-message`, `agent-message`, `channel`,
    `coordinator-relay`, `slack-ping`, `slack-tag-message`, `remote-review`, `tick`,
    `mcp-resource-update`) need a surface the chief does not have; they are not measured and the
    hook does not flag them.
  - **Switches in claude 2.1.304** (env vars, also accepted in the settings file's `env` block,
    measured in both places): `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` removes
    `run_in_background` from the Bash schema (the call is rejected), makes a command that hits its
    timeout die (exit 143) instead of moving to the background, and no `<task-notification>`
    arrives (measured in `-p` and a tab); `CLAUDE_CODE_DISABLE_CRON=1` keeps the scheduler from
    starting, so the file task above never fires (measured in a tab, 110 s). `claude_settings`
    sets both, as the `env` block of the `settings.json` a claude chief is started with (a codex
    chief has no settings file and is unchanged). That a claude honours them was measured on this one
    version, 2.1.304; on another the hook's deny-list is the only guard against the tags above, and
    nothing is against the file task. Not tried: `crossSessionInbound: "refuse"` (documented). A permission
    rule is NOT a switch: `Bash(run_in_background:true)` (in the settings `permissions.deny` or as
    `--disallowedTools`, both measured) refuses an explicit `run_in_background` ("Permission to use
    Bash with run_in_background:true has been denied."), but a foreground command with a long
    `timeout` is still moved to the background and still ends in a `<task-notification>` prompt
    (measured with the rule present). Only the env var closes both.
  - **`/clear` in the chief tab** gives claude a new session id (measured: the hook's
    `session_id` changes), so every later prompt is a 403 `not this chief's claude session` and
    nothing more is recorded for that tab. The hook says nothing, so neither the human nor the
    chief sees it, and the cite rule ("Cited answers" in the chief gate section) finds nothing
    recorded after it to cite: a message recorded before the `/clear`, for a question asked before
    it, can still be cited, but nothing the person types afterwards can answer a question until
    the tab is reopened. It fails safe.

### Request bodies — one lenient reader for every comms route (`_helpers.read_json_body`)

Agents reach `/comms/*` through curl. On Windows a shell not in UTF-8 mode hands curl a
**cp1252** body — one em-dash in an agent's prose is byte 0x97 — and Flask's
`request.get_json()` decodes strictly. `/comms/post` was hardened against exactly this, and
the fix was copy-pasted into `/comms/edit` and nowhere else. Measured across all 36 comms
POST routes with one em-dash in the body:

- **22 routes returned 500** — the exception was caught by the route's own
  `except Exception` and the agent's write was lost. `tasks/claim|complete|fail` were all in
  this set, and `tasks/fail` carries `reason`, agent-written prose (`team/build.md` posts it
  on every unrecoverable task failure).
- **The other 14 read `get_json(silent=True) or {}`**, so the body was **silently discarded**
  and the route then rejected the request for a "missing" field that was right there in it —
  worse, because it reads as the agent's mistake.

`_helpers.read_json_body(default=None)` is now the single reader, used by all 36. It reads
`request.get_data()` (so a client that omits the JSON content-type is still understood — what
`/comms/post` always did), tries UTF-8 then cp1252, and returns *default* when the body is
absent/undecodable/not a JSON object/holds a lone surrogate (`"\\ud800"` in a key or in a string at
any depth: Python's parser takes it, SQLite cannot store it, and the route answered 500
`UnicodeEncodeError`; other non-ASCII text, a surrogate pair and a cp1252 body read as before) — so
each caller keeps its existing contract:
`read_json_body()` for routes that 400 on a bad body, `read_json_body({})` for routes that
fall through to their own defaults.

This is SOLID rule #5 with teeth: the fix could not spread while it lived as two inline
copies, so the sweep test walks the **live `url_map`** rather than a hand-kept list —
`tests/comms_board/test_comms_body_encoding.py` covers a route added later without anyone
remembering to add it. It fails on a werkzeug `BadRequest` (body rejected) **and** on a
`NameError`/`ImportError` (helper used but not imported) — a wiring mistake that is easy to
make when touching a dozen files at once, and did happen while writing this.

### Who wrote a board row, and who may read it (role-read-policy)

Two halves, built in this order. **The first is live. The second is built and tested but not
wired, so the policy withholds nothing from any agent today.**
`tests/comms_board/test_rrp_acceptance.py` drives a spawn through to a stamped post and the
policy over it: a real spawn through `supervisor/terminal.py`, the real Flask app and the real
policy, with the spawn host and the agent faked (one fake broadcaster stands in for both and
posts with the token from the `TERMINAL_SPAWN` payload). The hosts' `PATHLY_RUN_TOKEN` export and
the fragments' header are not links it drives; `tests/runner_supervisor/test_pty_host.py`,
`studio/src/main/ipc/terminal/spawnEnv.test.ts` and
`tests/consistency/test_fragments_run_token.py` pin those. Design:
`pathly/features/role-read-policy/SPEC.md`.

**1. Identity and provenance (live).**

- **Mint.** `supervisor/terminal_identity._issue_spawn_token` is the first statement inside
  `_run_stage_via_terminal`'s `try`, the one place a `TERMINAL_SPAWN` is built, so every runner,
  board and goal spawn the supervisor drives is minted a token. Best-effort: a failed mint sends
  `run_token: None` and the spawn still goes out. A spawn that does not go through it gets none:
  Studio's one-shot editor actions and manual interactive tabs, and `pathly-run`.
  `db/queries/run_tokens.py::mint_run_token` stores only `sha256(token)` in `run_tokens`, next to
  `run_id`, `role`, `feature`, `project_root`, `board` and `scope`.
- **Role.** `_spawn_role` looks the flow's `agent_map[current_state]` entry up in
  `_SKILL_AGENT_ROLE` (`team/build` -> `builder`, `team/review` -> `reviewer`, `team/test` ->
  `tester`, `team/plan` -> `planner`, `team/design` -> `designer`, `team/retro` -> `planner`),
  else takes its last path segment; a DAG-task spawn (`sched-` run_id) is `builder`;
  a board run is its agent (`state.current_state`). It does not read the flow's `role_map`, so
  some states differ from it: `quick-fix` and `debug` FIXING mint `build` (not `builder`),
  `debug` VERIFYING mints `verify`, the consultation PLANNING states mint `plan` /
  `feature-decompose` / `project-decompose`. A row stamped `build` is not matched by the built-in
  `exclude_authors: ["builder"]`.
- **Carry.** `run_token` rides in the `TERMINAL_SPAWN` payload, and both spawn hosts put it in
  the child env as `PATHLY_RUN_TOKEN` (only when it is a non-empty string). Agents send
  `-H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN"` on every `curl` to `8765/comms` under `core/`
  (`tests/consistency/test_fragments_run_token.py` fails on one that lacks it; `.md` files that
  describe calls as bare `GET|POST /comms/...` carry an instruction line instead), and the
  Python-built board-run prompt (`supervisor/board_run.py`) and the catalog hint
  (`runner/comms_catalog.py`) say the same. An interactive `/pathly` run has no
  `PATHLY_RUN_TOKEN`, so the header expands to nothing, `curl` does not send it, and the call is
  `anonymous`.
- **Resolve.** `http_server/run_identity.py::caller_identity(request)`: a live token is
  `kind="run"` with its `run_id`, `role`, `feature`, `project_root`, `board` and `scope`; a
  missing, empty, unknown or revoked one is `anonymous` (unknown and revoked are logged at info
  with the remote address). `caller_identity` never reads the body's `role`, `run_id` or `from`.
  Studio's own requests send no token yet, so UI posts are `anonymous` too.
- **Stamp.** `POST /comms/post` stores `stamp(caller_identity(request))` as `author_role`,
  `author_run_id` and `author_source` on the `comms_messages` row (rules under "Author provenance
  on board writes" below; the columns and the `legacy` backfill are `db/migrations_provenance.py`).
  The body's `from` and `run_id` are still stored as sent (`from_agent`, `run_id`) but never used
  for provenance (only the `legacy` backfill, `add_comms_provenance`, derives a role from them,
  and only for rows that have no stamp; it runs at server start and after a board snapshot is
  hydrated). They are not inert: `from` still gates writes to the project and global boards
  (`check_write_permission`; the feature board accepts any `from`), and `run_id` still correlates
  the post to a run for RunDetail's Board tab and the `/events/runs` live push.
- **Revoke.** `_settle_spawn_identity` revokes the spawn's tokens in the spawn's `finally`. A run
  that outlives its token is not refused: its post is stored with `author_source="none"`.

**2. The read policy (built, not wired).** `runner/read_policy.py` holds `ReadPolicy` (the tier
booleans plus optional `exclude_types` / `exclude_authors`), `BUILTIN_DEFAULTS` (`reviewer`,
`tester`, `chief`, `anonymous`), `NEVER_WITHHELD_TYPES` (`decision`, `constraint`, `goal`, `task`,
`escalation`), `row_allowed` and `policy_predicate` (one rule, as a pure function and as a SQL
fragment over `type` / `author_*`; tests keep them in agreement), and
`resolve_read_policy(conn, role, feature, project_root)` (stored per-role row, else per-feature
row, else the built-in default, else allow-all; `role=None` is `anonymous`; a stored row without
`exclude_*` keys is allow-all for content and never falls to the built-in wall). **No production
code calls any of it**: `retrieve_board_context`, `POST /comms/search` and `GET /comms` select the
same rows as before this feature (each row now also carries the three `author_*` columns), and no
code reads the `read_policy.mode` setting. A role's reads still differ only by the existing
per-role `board_scope` tier switches. Wiring the predicate into the three read paths (in `warn`
first) is a later plan.

### Chief gate (chief-agent)

`http_server/chief_gate.py::chief_gate` is a `before_request` hook registered in `app.py` right
after `_log_request`, so the secret check and the rate limit run first. It acts only on a request
whose `X-Pathly-Run-Token` belongs to a token row with role `chief` (`lookup_run_token`, live or
revoked); a builder token, an unknown token and no token pass untouched. A `chief` token whose
row is revoked, or whose session (`chief_sessions`) is missing or closed, gets **401**
`{"error": "chief session closed"}`, never `caller_identity`'s anonymous fallback, because
anonymous loopback callers can do everything. A path no route matches (`request.url_rule` is
None; Flask matches the rule before any hook runs) passes, and Flask answers 404 or 405.

For a live chief the call is classed into one of seven actions by `http_server/chief_routes.py`
(`ROUTE_ACTIONS` maps `(rule, method)` to an action; `action_for` applies the three refinements),
and refused with **403** `{error, action, tier, allowed}` unless the session's tier holds it. The
tiers are `supervisor/chief_tiers.py`'s: `status` = read; `planner` = read, post, plan;
`operator` = those plus decide, run, stop, answer. A tier the row does not name is `status`.

| Action | Calls |
|---|---|
| `read` | every GET except `/events/*` and `/db/settings` (spawn tokens, stored secrets); `POST /comms/search`, `/code/query` |
| `post` | `POST /comms/post` of any type not below |
| `plan` | `/comms/post` type `goal` or `task`; `/comms/goals/decompose`, `/comms/features/decompose`, `/comms/project/decompose` |
| `decide` | `/comms/post` type `decision` or `constraint` (a `supersedes` list included); `/comms/acknowledge` on any row that is not a human-addressed escalation; `/comms/supersede`, `/comms/directives` |
| `run` | `POST /runs`, `/comms/goals/run`, `/comms/run`, `/comms/tasks/run`; `/runs/<run_id>/<action>` for `pause\|resume\|advance\|reroute\|retry` |
| `stop` | `/runs/<run_id>/stop`; `/runs/<run_id>/<action>` for `abort`; `/comms/goals/stop`, `/comms/run/stop`, `/comms/tasks/stop` |
| `answer` | `/runner/agent-answer`, `/comms/answer`; `/comms/acknowledge` on an escalation with `to_agent = "human"` (the gate looks the row up by `message_id`). Held to the cite rule ("Cited answers" below) |

- **Deny by default.** Every non-GET route the table does not list is 403 to every tier (for
  example `/db/query`, `/skills/prompts`, `/chief/open|close|human-messages`, `/comms/edit|delete|hydrate`,
  `/comms/tasks/status` and the FSM routes that take `force_past_gate`): the chief never forces
  past a human gate and never marks a task done itself. An unknown `/runs/<run_id>/<verb>` is
  unlisted too. `tests/http_api/test_chief_gate.py` walks `app.url_map` and fails when an unlisted
  route is not refused to an operator or when the table lists a rule no route has;
  `test_chief_gate_tables.py` fails when a route the chief can reach has no `ROUTE_FIELDS` entry
  (below), so a route added later is refused to the chief until someone lists it and says which
  project it reads. (The chief gate tests are `tests/http_api/test_chief_gate*.py`, one file per
  concern, with the shared fixtures in `chief_gate_support.py`; a new test goes in the file of
  its concern.) Four tests read the tables against the code, and each says what it does not read.
  `test_chief_gate_tables.py` walks `app.url_map` for the routes. `test_chief_gate_keys.py` reads
  the source of every view **and of the helpers it calls** under `blueprints/` (`create_run`,
  `handle_retry`, `_dispatch_*`, three levels deep) for the keys they read from the request, found
  by what a name is bound to, not by what the key is called: a name assigned `read_json_body()`,
  `request.get_json()` or `request.args`, or a helper parameter called `body` or `data`, read by
  `.get("k")`, `.getlist("k")`, `["k"]` or `"k" in …`. It does not read a function outside
  `blueprints/` that is handed the whole body, a key built at run time, or `request.form`,
  `request.values` and `request.json`. `test_chief_gate_kinds.py` reads the same source for a key
  the entry calls plain (text, number, flag, enum, name, id) that a view, or a helper under
  `blueprints/`, passes (directly or through the names it is assigned to, inside one function) to
  a call that makes or opens a path; the three it finds today (`board` of `POST /comms/run`,
  `adapter` of `GET /ops/export/skills`, `topic` of `GET /status`) are listed with what holds each
  in the view, and a fourth fails the test until it has a file kind or is listed. It does not see a
  key handed to a function that joins it later (`start_run(flow=...)`, `start_board_run`), a call
  that is not in its list of path calls, or whether a file kind is the *right* one (a folder name
  declared as a scope, a root declared as a path): that is left to the audit.
  `test_chief_gate_audit.py` covers what a reading of the source misses (see "What was
  measured").
- **Overrides.** A body with a non-empty `prompt_override` or `stage_overrides`, on any route,
  also needs `run` (the 403 names `run`): the Planner may call the decompose routes but cannot
  hand verbatim prompt text to the agents they start.
- **Cited answers.** A chief answers an agent only by naming a message that the hook recorded as
  typed in its own tab ("What a citation proves" below says what that does and does not show);
  Pathly relays that message's text, so the chief never words the answer
  (`http_server/chief_cite.py`, called by `chief_gate` once every reading of the body has passed
  the other checks). An `answer` action (`/runner/agent-answer`, `/comms/answer`, and
  `/comms/acknowledge` on an escalation with `to_agent = "human"`) from a chief token must send
  `cite: <number>` and nothing else:
  - A body that carries `answer` or `option_id` is 403 `send cite only: Pathly relays the cited
    message's text` (so the chief cannot word an answer or pick an option for the person; its own
    explanation goes on the board as a separate `note`).
  - `cite` must be an integer (not a bool, string or float) naming a `chief_human_messages` row of
    kind `human` and of this session's `run_id`: the style prompt (the session's first message) and
    a `relayed` message cannot be cited, nor can another session's. Otherwise 403 `cite a human
    message from this chief session` (for a session whose engine is not `claude` the text adds
    that a codex chief records none, so it can relay nothing). A number outside 64 bits is no
    message either (SQLite cannot hold it), and is this same 403.
  - On `/comms/acknowledge` the body's `agent` must be `"chief"` (as `/comms/post` needs `from ==
    "chief"`), else 403 `a chief acknowledges a human escalation as 'chief'` and nothing is
    spent: the name is stored on the row, so a chief that sent `"human"` would make the board
    read as if the person closed the gate.
  - The message must have been recorded at or after the question was asked: for a run's topic,
    `RunnerState._agent_question["asked_at"]` (set under the registry lock by
    `supervisor/interactions.py::_await_agent_question` together with the question, the options
    and `questions`, the whole list of an AskUserQuestion, and cleared on every exit); for
    `/comms/answer` the `ts` of the `question_id` row; for a human escalation the `ts` of the
    escalation. A topic whose run belongs to another project is 403 `that is not this chief's
    project`. A topic with no run, a run that is not awaiting an answer, a question id with no
    row, and a `topic` or `question_id` that is not a non-blank string are left to the route, which
    answers 404, 409, 404 and 400 (a `question_id` that is not a string is 403 first, see "Ids"
    below). A `ts` that cannot be read is a refusal.
  - A message can be cited once (`chief_citations.message_id` is unique): the gate calls
    `record_citation(run_id, cite, route, target)` last and answers 403 `that message was already
    cited` for a second use. The citation is spent when the gate lets the call through, whatever
    the route then answers (404, 409, 403, 415, 500: see "What a spent citation costs" below); the
    person types again.
  - On success the gate sets `flask.g.chief_cited_text` to the message's `text`; the two answer
    routes read their answer through `chief_cite.answer_text(data)` (the cited text for a chief,
    the body's `answer` for every other caller, so a caller without a chief token gets exactly
    what it sent). `/runner/agent-answer` strips the answer before it supplies it, so the outer
    whitespace of a cited message does not reach the agent; `/comms/answer` strips only to see
    whether it is blank and stores the cited text unstripped. For a human
    escalation the gate sets `g.chief_cited_gate = <escalation id>` instead, and
    `comms/_helpers.refuse_agent_on_human_gate` lets a live run token through only for that id;
    every other run token is refused as before, `/comms/delete` stays refused to a chief and
    `force_past_gate` stays a human-only affordance.
  - The gate reads every reading of the body (`_bodies`): the readings must agree on `cite` and on
    the target, and none may carry `answer` or `option_id`.

  **What a citation proves, and what it does not.** It shows that the words an agent receives are
  the text of a prompt the hook recorded as one that reached the chief's tab, delivered by claude
  with none of the known wrappers ("Human messages" above is a deny-list, not a test for
  "typed"), relayed to the question the chief picked, once. It does not prove the person meant them for that question: a chief can cite
  an unrelated later remark, and the person reading the board is what catches it. Against an
  `operator` chief, which can start a headless agent, a `human` row is "what the hook endpoint
  recorded", not proof that a person typed it (it need not even have reached the tab), because
  that agent runs as the same OS user and can post to `POST /chief/human-messages` itself if it
  reads the session's secret file and `--session-id` (spec § Risks). The rule guards the chief
  token's own calls, not a process the chief starts: a headless agent the operator chief starts
  can call `/runner/agent-answer` and `/comms/answer`, which are unchanged for every caller
  without a chief token, with no `cite` at all. `/clear` in the tab changes claude's session id,
  so afterwards the hook records nothing: a message recorded before it can still be cited for a
  question asked before it, but nothing typed afterwards can be, until the tab is reopened; a
  codex chief has no message at all. The gate checks the question when the request arrives and the route relays a moment later;
  if the run's question changes in that window (the agent asks a new one), the cited message goes
  to the new question although it may predate it. The words are still the person's.

  **What a spent citation costs.** The gate spends the message before the route runs, so every
  answer the route then refuses has already used it, and the person is not told: a topic with no
  run (404), a run that is not awaiting an answer (409), a `text/plain` body (the gate reads the
  body with `force=True`, the route's strict `get_json()` answers 415, then 500) and
  `/comms/answer` on a human escalation (the human gate's 403). So a chief, buggy or hostile, can
  burn any unspent message of its session by naming a topic with no run or an idle one, and the
  person types again. A `topic` or `question_id` the route rejects for its shape (blank or not a
  string) spends nothing, and so does a `topic` the gate cannot look up (`chief_bind.is_id`: over
  512 characters, a control character or a lone surrogate, left to the route); a `question_id` that
  is not an id is 403 first ("Ids" below). Two requests that cite two different messages for one
  waiting question, both before the run's poll takes the first answer, spend both messages and the
  second answer overwrites the first: `supply_agent_answer` only checks that the run is still
  awaiting an answer and stores the new one, and `_await_agent_question` clears that flag after
  its 50 ms poll sees an answer, so the person's first message is lost and the agent reads the
  second. Both sides of "at or after" are the wall clock (`time.time()` for a
  message and for a run's question, the board row's ISO `ts` for a board row), so a clock stepped
  backwards lets an older message pass.
- **Cost and run limit.** Two per-machine settings in `app_settings`, read on every call, bound an
  operator chief (`http_server/chief_budget.py`; the person sets them with `PUT
  /db/settings/<key>`, which no chief token can call, and that route keeps no list of names, so a
  new key needs no registration). `GET /chief/session` reports both, with `runs_started`.
  - `chief.max_cost_usd_per_run` (default `10.0`): the cost one run may state. `POST /runs` and the
    `retry` verb are the only start routes whose body carries `max_cost_usd`, so the ceiling is
    judged there (the other start routes list no such key and a chief that sends one is told so).
    `POST /runner/start`, `POST /runner/retry` and the `retry` verb read the key with the same
    `as_cost` (a value that is not a finite number above 0 is their 400), so no start route takes a
    `NaN`, an `Infinity` or a `true` as a cap.
    Above it is 403 `max_cost_usd above this chief's ceiling` with `ceiling`. A value that is not a
    finite number above 0 (a boolean, string, list, `null`, zero, a negative, `NaN`, `Infinity`) is
    403 `max_cost_usd must be a finite number above 0` with `ceiling` too: Python's JSON parser
    takes `NaN`, a comparison with it is false both ways, and a retry would then run with no cap at
    all. `POST /runs` of a flow now reads the key (`blueprints/control/_cost.py::flow_cost`, passed
    to `start_run` as the run's cap; a bad value is the route's 400; it ignored the key before) and
    a start that states none runs at `start_run`'s own `$1` (`DEFAULT_FLOW_COST_USD`), which the gate
    judges as stated, so a ceiling under `$1` still holds. A retry that states none is the route's
    400. A goal, a board run and a task run have no per-run cost: only the count below bounds
    them, and a goal run's own cap is the separate `goal.max_cost_usd` setting. Judged for every
    reading of the body (`_bodies`).
  - `chief.max_runs_per_session` (default `20`): the calls that start work count one each against
    the session (`chief_sessions.runs_started`): `POST /runs`, `/comms/goals/run`, `/comms/run`,
    `/comms/tasks/run` and the `retry` verb of `/runs/<run_id>/<action>`. `pause`, `resume`,
    `advance` and `reroute` are `run` too but act on a run that exists and start nothing; the
    decompose routes (`plan`), every `stop` and every read do not count
    (`test_chief_budget_edges.py` fails when a new `run` route is not decided). Past the limit is
    403 `this chief session has started its maximum number of runs` with `limit`; the person raises
    the setting or opens a new chief. `0` means no run may start.
  - **Last, and a conditional UPDATE.** `chief_budget.budget_refusal` is the gate's last check,
    after the action, project, id, key and cite rules, so a call the gate itself refuses costs no
    slot. It judges the cost, then `db/queries/chief_run_slots.take_run_slot` runs `UPDATE ... SET
    runs_started = runs_started + 1 WHERE run_id = ? AND runs_started < ?` under the write lock
    and refuses when no row changed, so two racing calls cannot both take the last slot. It sets
    `flask.g.chief_run_slot`; the `after_request` hook `refund_run_slot` (registered in `app.py`)
    runs `runs_started - 1 WHERE runs_started > 0` for a response of 400 to 499 (the route refused
    the start: a bad body, an unknown goal or task, nothing ready, a busy board, so nothing began and
    nothing was spent), once, only for the request that took a slot, and never below zero. A 2xx
    keeps the slot even if the run fails later (it may have spent), and so does a 5xx (the server
    cannot tell whether work began), and so does a `retry` of a run that is still active or not in
    the registry (200 `ok: false`). The gate clears the marker at the start of every request.
  - Refusals carry the usual `error`, `action` (`run`), `tier` and `allowed`, plus `ceiling` or
    `limit`. A setting that does not parse, is not finite, or is at or below 0 (the ceiling), or is
    negative or not a whole number (the limit) falls back to its default, which is a bound too; a
    limit past 2^62 is read as 2^62. Not here: the chief's own token cost, and a cost summed across
    a session's runs (round two bills the chief session first).
- **One project.** `http_server/chief_fields.py::ROUTE_FIELDS` is the inventory: one entry per
  `(rule, method)` a chief can get past the action table (merged from `chief_field_calls.py`, the
  POST routes, and `chief_field_reads.py`, the GETs; each entry is a `Fields` of
  `chief_field_types.py`), saying which request keys the view reads, of which kind: a project
  root, a board scope or a file (checked here), a flow or a skill (checked by `chief_keys`), and
  which ids it reads that the gate does not bind. `chief_project.project_refusal` applies the
  entry with one function, reading the query string for a GET and the JSON body for every other
  route, as the views do; a route with no entry is 403 (`the gate has no project entry for this
  route`), so the gate fails closed. Every value is
  compared with the session's by one spelling, `scope_names.root_spelling` (trailing slashes
  dropped; nothing else changed: no `.` or `..` collapse, no trimming, a drive letter's case kept),
  else 403; a value that is not a string is refused too. **The host decides what a backslash is**
  (`scope_names.host_is_windows`, the one switch a test patches): on Windows `\` and `/` both
  separate and a backslash reads as a slash; on any other host a backslash is an ordinary
  file-name character, so a `project_root` or a path-kind value (`scope`, `path`) that has one is
  refused, because the routes open the raw string and `/work/proj\` is a different folder than
  `/work/proj`. The rule is that two strings the gate calls one root must be one directory to
  the routes that open them as they are (`test_scope_names_host.py` creates the folders and asks
  the file system); a spelling that might be the same directory but cannot be shown to be (`.`
  segments, doubled slashes inside, a leading space) is refused. A session row whose root has a
  backslash on such a host binds nothing (every call that names a project is refused). No row
  `open_chief` writes is one: it stores `normalise_project_root` (backslashes made slashes on
  every host), so a POSIX project directory whose name has a backslash cannot be a chief's
  project (the stored root names another path); that limit is not changed here.
  - **`project_root`** is checked wherever it appears, in the body or the query string of any
    route.
  - **Naming it.** A route that falls back to the server's working directory,
    `PATHLY_PROJECT_ROOT` or every project when `project_root` is absent is also refused when the
    call names none (absent, null, empty, `0`, `false`, `[]`, `{}`) in the place the route reads
    it, and the 403 names the field (`a chief names its project_root on this route`). A root in
    the query string of a POST does not count: those views read the body. The routes are `POST
    /runs`, `/comms/goals/run`, `/comms/run`, `/comms/tasks/run`, the three decompose routes and
    `/code/query`; `POST /runs/<run_id>/retry` (it starts a run in the directory its body names,
    and `handle_retry` takes an empty one; `pause`, `resume`, `advance` and `reroute` act on the
    run's own state and need no root); `POST /comms/post` only when it carries `context_refs`;
    and the GETs `/db/features`, `/db/stats`, `/db/stats/trends`, `/db/recent`, `/db/rollup`,
    `/db/features/<feature>/{agents,events,otel,runs}`, `/status`, `/comms/artifacts/section`,
    `/comms/artifacts/<artifact_id>/section` (the root bounds the path the row was stored with, see
    "A stored path"), and `/telemetry/trends` when it is given no feature (a blank feature sums every project unless
    the root narrows it; a named feature is fleet-wide, see "Not bound"). The gate cannot fill the
    root in from the session, since the route reads the request's own fields.
    **The exceptions** are the reads whose absent root gives the global or packaged data or no
    rows rather than another project's (`GET /runs`, `/api/*`, `/skills/*`, `/flows/stage-config`,
    `/db/agents`, `/comms/permissions`, `/comms/scope`, `/hq/context`, `/chief/session`): they
    need no root and still refuse another project's.
  - **A project board's scope.** When the board a call reads or writes is `project`, the scope must
    be the session's root. The scope is the first usable value (truthy, not a blank string) of the
    keys the route reads, as the view's `scope or feature` does (`/comms/post`, `/comms/search`
    and the board reads `GET /comms`, `/comms/tasks`, `/comms/goals` take `scope`, else
    `feature`; `/comms/artifacts`, `/comms/run/status`, `/runs`, `/comms/run` and
    `/comms/run/stop` take `scope` only). A missing or unknown `board` is `feature`. So a
    project-board post, search or read gives its own root as `scope`. **A scope that looks like a
    path (a `/`, a `\` or a drive prefix) is bound on every board**, not only on `project`: the
    board mirror (`board_mirror.py`, a DB-to-disk export that runs on every broadcast, with or
    without a chief token) reads such a scope as a project root and writes
    `<scope>/pathly/project/BOARD.json`, so a feature or global board post of `scope:
    "/abs/proj-b"` or `"../../proj-b"` would plant a file in another project (or relative to the
    server's working directory). On a board other than `project`, any other scope is one folder
    name (below). A scope with no `board` (`GET /comms/trash`, `/hq/context`'s `board`, the
    `scope` or `feature` of `/comms/artifacts/section` and `/comms/artifacts/<id>/section`) is a
    project root when it looks like a path and is then bound; otherwise it is one folder name.
    `/code/query` logs a `discovery` row on the project board at its `scope` or `feature`, so that
    is bound unless it is blank or a parenthesized marker such as `(interactive)`; the `project`
    override of `/comms/project/decompose` is a project-board scope (the literal `project` means
    none).
  - **A file.** `/code/query`'s `target` (read against `project_root`, so a relative one is the
    project's), `/comms/post`'s `artifact_path` (it must be absolute; the row keeps it, so it is
    checked at the post) and the path an `artifact` post takes from its `text` when
    `artifact_path` is blank (always relative, so refused) must lie under the session's root, in
    two steps. First as text, once their `..` segments are collapsed (`scope_names.lies_under`,
    with the host's reading of a backslash above: on a POSIX host a path with one is refused; a
    Windows drive letter is compared as written). Then as the file system reads it: the path as
    the route will open it (a relative one under the root; the text as written, so a `..` after a
    link is taken from the link's target, not collapsed first) is resolved with symlinks followed
    and must still lie under the real root (`chief_project._opens_inside`, which asks
    `hydrate_helpers.inside_root`, the check the by-id section read makes). A symlink inside the
    project that points into another project is a 403 with the same text (`a chief names only
    files inside its project`). A path that does not exist yet resolves as far as it can, and
    the project root may itself be a symlink (both sides are resolved), so the files of a
    legitimate chief pass. A string with a drive prefix (`C:`, and so a symbol target like `a:b`)
    is read as an absolute path on every host and refused unless it lies under the root; a POSIX
    host would read it as a relative name, but the gate does not guess which a route means. A
    relative `artifact_path` is refused for the same reason as the relative path of an `artifact`
    post: the row keeps the path it is posted with. **What text alone cannot see.** Text
    containment cannot see a symlink, so it no longer decides these two fields alone. It still
    decides alone where the gate compares a project root or a path-like scope (`root_spelling`,
    `is_own`): a string is accepted there only when it spells the session's own root, so a link
    inside the project cannot change which directory it names, and any other spelling of the same
    directory (a `.` segment, a symlinked parent, another letter case) is refused, not resolved.
    That is why a chief has to use the stored root (see "Not here yet"). The real-path check does
    not see a link made after the call was checked (the gate checks, the route opens later), a
    hard link (a second name inside the project for a file that is also elsewhere) or a mount;
    and for `/code/query` it checks the `target` only: what the backend then opens by its own
    rules is the backend's.
  - **A stored path.** A row keeps the path it was posted with (`comms_artifacts.path`), and
    `GET /comms/artifacts/<artifact_id>/section` opens it, whoever posted it. So that read names
    the root it reads under (a chief must send its own `project_root`) and `hydrate_section` is
    given it as `contain_in`: a stored path that does not lie under that root (real paths on both
    sides, symlinks followed: `hydrate_helpers.inside_root`) answers 400 `path_out_of_scope`
    (`outside the project`) before anything is read, indexed or posted to the board. A caller that
    names no root (Studio, a human) reads the stored path as before. The by-path form (`artifact=`)
    and `context_refs` resolve under the root the call names through
    `hydrate_helpers.safe_artifact_path`. The 400 for a row elsewhere against the 404 for no row
    tells a chief whether an id exists, not what is in it.
  - **A folder name.** A request string becomes part of a folder name in three places, and the
    gate holds each of them with the rule below. (1) `POST /comms/features/decompose` makes
    `<project_root>/pathly/features/<feature>` and hands it to the run as its storage path, and
    `POST /comms/run` of an evaluator on a feature or global board saves a reply that posted no
    BOARD_EVAL artifact under `<project_root>/pathly/features/<scope>/artifacts/`. So the `feature`
    of the first and the `scope` of the second (on a board other than `project`) must be one folder
    name: a string with no `/`, `\`, `:` or NUL, and not `.` or `..` (`ScopeRead.segment`, which
    also refuses the chief's own root there); the 403 names the field. The routes refuse the same
    class themselves, from `storage_paths._is_unsafe_topic` (empty, absolute, backslash or colon, a
    `..` segment, a reserved name): `features/decompose` answers 400 `invalid_feature`, and
    `/comms/run` skips the save for such a scope (the board gets the usual warning). They still
    accept a nested `a/b` that stays inside the project; the gate does not. (2) A `goal` post's
    `slug` is stored on the row and the goal run and decompose later make
    `pathly/features/<scope>/goals/<slug>` of it (`supervisor/slug.py::ensure_goal_slug`,
    `goal_decomposer`), so `/comms/post` declares it in `Fields.segments` and the gate refuses a
    `slug` that is not one folder name; `ensure_goal_slug` ignores a stored slug that is not one
    (`scope_names.is_segment`) and generates a new one, for a row some other writer posted. (3) A
    scope that only reaches the board mirror, on any route that posts to a board (see "A project
    board's scope"): the gate holds it with the path rule above, and the mirror holds it itself,
    in `board_mirror.py`, for a caller the gate does not see. The mirror answers a normalised
    absolute project root on the project board and one folder name on a feature board, and ignores
    any other scope: `board_from_scope` returns None (so `mark_board_dirty_by_scope` queues nothing)
    and `write_board_mirror` returns False (`_scope_fits`, on either board). `board_mirror_path`
    itself is None for an unfit scope on a feature board only: on a project board it joins whatever
    root it is given, and it is `write_board_mirror` that stops it. Both predicates are in
    `scope_names.py` (`is_project_root`, `is_segment`); a legitimate root (POSIX or `C:/...`, spaces
    and unicode) and a feature name (dots, spaces, unicode) are accepted as before. **A project
    board whose scope is a relative root (`proj/x`) is no longer exported to disk**: it was
    written under the server's working directory before; its rows are stored and served as
    before, and a caller that wants the export names the absolute root
    (`tests/comms_board/test_board_mirror_relative_root.py` pins it).
  - **A flow or a skill.** `fsm_ops._load_flow` reads `core/flows/<flow>.flow.yaml` and
    `skills/compose_resources` reads `core/skills/<skill>.md` by joining the request's string onto
    a packaged folder (an absolute string replaces the folder), and the `team` executor of
    `POST /comms/goals/run` made `pathly/features/<scope>/<flow>/<slug>` of its `flow` before it
    checked that the flow existed. `flow` is a key of `POST /runs` and
    `POST /runs/<run_id>/<action>`, `skill` of `POST /comms/run`: the gate refuses a `flow` that is
    not one name and a `skill` that is neither `name` nor `category/name`
    (`scope_names.is_flow_name` / `is_skill_name`, `chief_keys.key_refusal`; the 403 names the key).
    The readers refuse the same spellings for every caller: `_load_flow`'s fallback to the packaged
    file and `compose_resources._skill_file` raise `FileNotFoundError` for a string that is not one
    name or that resolves (symlinks followed) outside its folder (`scope_names.resolves_inside`),
    `_skill_exists` answers False, and `goal_executor._flow_kind` raises `ValueError` for a flow
    that is neither a goal flow nor one name, which `_run_team` answers as `unknown_flow` before it
    makes any folder (it used to make the folder first). A flow stored in the database is found by
    its name and never opened as a file. `POST /comms/goals/run` takes no `flow` from a chief (see
    "The key list").
  - **The key list.** An entry is also the complete list of the keys a chief may send to its route
    (`Fields.allowed`: the keys it names, plus `project_root`, minus the variables of the URL).
    `chief_keys.key_refusal` runs last, and refuses a body key (a query key for a GET; a repeated
    key is one key) the entry does not list, with a 403 that names it (`'x' is not a key a chief
    may send to this route`). Only top-level keys are looked at and a value is opaque to it; a body
    that is not a JSON object is read as no keys, as the routes read it. A key a view reads that no
    chief flow needs is not listed but put in `not_for_chief`, so a test can tell "left out on
    purpose" from "forgotten": `ability_ids` (composition packs picked in Studio), the
    `system_prompt` and `interactive` of `/comms/run`, the `summary_backend` and `embed_summary`
    of `/comms/post`, and the `flow` of `/comms/goals/run` (the goal's executor picks its flow; a
    chief that wants another one starts it with `POST /runs`). Every listed key has a kind
    (`Fields.kinds()`): text, number, flag, enum, name or id (opaque to the gate, never joined into
    a path by design; `test_chief_gate_kinds.py` and the audit's plain values check it), or one of the kinds that can reach a file or a folder, each with a rule the
    gate applies and, where the key reaches a sink, the sink applies as well: `root` (the
    session's), `scope` and `segment` (above), `path` (inside the project), `ref` (a file ref
    the sink resolves under the root the call names, which the gate makes it name: `context_refs`,
    `artifact`), `flow` and `skill`. The `cite` of the three answer routes is read by the gate's cite
    rule (`chief_cite`, "Cited answers" above), not by a view, so `test_chief_gate_keys.py` still
    counts it as a listed key no view reads (`READ_BY_THE_GATE`); the `answer` those routes list
    is read through `chief_cite.answer_text`, which the test's walk follows (`BODY_HELPER_MODULES`
    of `chief_walk_support.py`). A key a view starts to read is refused to a chief until
    someone lists it (`test_chief_gate_keys.py` fails first), so the keys a chief's prompt may name
    are the entries' lists (the built-in texts' examples are checked against them by
    `test_chief_prompt_text.py`).
  - **What reaches a path, and what holds it.** Read in round 4 and again in round 6; round 6
    added the key list and the measurement below, which are what lets this list be short. Held at
    the gate **and** at the sink: the board mirror's scope, `features/decompose` and the evaluator
    save (`_is_unsafe_topic`), the goal `slug` (`ensure_goal_slug`), `flow` and `skill` (above), the
    stored path of an artifact row (above), `context_refs` and `artifact`
    (`safe_artifact_path`, a realpath containment check). Held at the gate only: the artifact path
    of a post and the target of `/code/query` (text containment, then the real path, symlinks
    followed: see "A file").
    Held by the route's own design: `fsm_ops._resolve_storage_path` (`_safe_topic` or the project
    root itself) for `start_run` and `start_board_run`, the `topic` of `/status`, `GET
    /skills/prompts` (a category filter; `_SEG_RE` on writes), `GET /skills/summary-format/<style>`
    (an allow-list of three), and the flows, menu, catalog and `/api/*` reads (the database or an
    allow-list). The `/db/*` reads filter rows by the bound `project_root`; `GET /db/features` and
    `GET /db/stats` also glob and read `STATE.json` and `RUNNER_STATE.json` under that root (the
    fallback for a feature that never ran), so what they open lies inside the root the gate bound.
    **Not held:** feature boards are keyed by name only, and the board mirror writes a feature
    board's `BOARD.json` into the project `run_history` last mapped that name to
    (`resolve_project_root`, through `latest_project_root_for_feature`: the newest row whose
    `feature` is the name, or whose `feature` is a legacy full topic path ending in `/<name>`; the
    startup backfill matches by an existing `pathly/features/<name>/` folder instead). The name is
    matched as it is written: `%`, `_` and `\` in it are escaped (`run_history._like_literal`,
    with an `ESCAPE` clause), so a name is not a pattern, but the match is SQLite's `LIKE`, which
    ignores the case of ASCII letters. So a chief's post to feature `demo` rewrites `demo`'s
    `BOARD.json` in the project that last ran a feature of that name (or `Demo`), which may not be
    the chief's. The gate cannot bind a feature name to a project. Nor at the sink: `event_mirror.backfill_event_mirrors`
    joins the `feature` of a stored event (`eventlog.append_event` keeps its basename;
    `terminal_phase` passes a `_safe_topic` topic), so it relies on the gate's hold on `/runs` and
    `/comms/run`; and `goal_decomposer` joins the `scope` of the goal row it decomposes, which the
    gate checks for a goal a chief posted and, for a goal a chief decomposes or runs by id, through
    `chief_bind` ("Ids": a feature scope must be one plain folder name of the project); nobody
    checks it for a goal another writer posted and a caller without a chief token decomposes.
  - **What was measured.** `tests/http_api/test_chief_gate_audit.py` runs the server with the
    spawn host faked, a database of its own, a canned `codebase-memory-mcp` (the `cli` code backend
    answers from a table, so `/code/query` reaches the file hash and the graph query) and three
    directories under a fake home (the chief's project, another project, the server's working
    directory). It sends every key of every route of the table, and every variable of its URL,
    hostile values, as a status, a planner and an operator chief, in requests that are valid but
    for that value (`chief_audit_world.py`, `chief_audit_calls.py`, `chief_audit_reads.py`: one or
    more per route, seeded as a human would). **Which values reach which key, at every tier:** a key
    of a file kind (root, scope, segment, path, ref, flow, skill) or **any variable of a URL** (the
    `feature` of eight rules, the `artifact_id` of one and the `run_id` of four, whatever kind the
    entry gives it) gets the whole list: `..`, a relative climbing path (`../..`), a relative path
    that climbs into the other project, an absolute path into the other project, into the
    server's directory and into the home directory, a UNC path in both slash directions, a drive
    letter, a NUL, a trailing slash, a 5,000-character name, and the spellings of the chief's own
    root and file that a gate might take for the chief's own (a trailing slash, two, a dot segment
    at the end or in the middle, doubled slashes, a backslash at the end, backslashes for every
    slash, mixed separators, a climb with backslashes, a leading space). Every other key (text,
    number, flag, enum, name, id: a key that is only free text) gets a shorter list of seven
    values, and only these: `..`, `../..`, a relative path that climbs into the other project, the
    other project's root and a file in it (both absolute), a NUL and a 5,000-character name. It
    has no absolute climbing path, no server or home directory, no UNC or drive spelling and none
    of the own-root spellings. (Until round 8 the URL variables were on the short list, and this
    paragraph said they were not.) `sys.addaudithook` records every file system call the process makes (`open`,
    `os.mkdir`, `rename`, `remove`, `rmdir`, `symlink`, `link`, `truncate`, `chmod`, `listdir`,
    `scandir`, `shutil` copies and moves, `glob`, `sqlite3.connect`, a child process's working
    directory) and none may fall in the other project, the server's working directory or the home
    directory (`Path.home()` in the test; the user's real home is not a zone, the repository may
    lie inside it), outside the chief's own project and `~/.pathly`. So nothing a request sends
    lands in the server's working directory, at any tier, for any key and any spelling in those
    lists. `test_chief_gate_separators.py` sends the root spellings through nine routes and
    looks for what lands in the server's directory or has a backslash in its name. The audit file
    also shows it sees each kind of call, and sees a write a request makes: a post with no token
    that names another project's root as a board's scope makes the mirror write that project's
    `BOARD.json`; the same post by a chief is refused. It was also checked by breaking the guards:
    with the project rules off, with the key list and the flow and skill name checks off, with the
    stored-path containment off, with the host switch read as "a backslash always separates" and
    with the code backend's file read left to the server's directory, it fails each time; with
    only the key list off it passes, because the sinks hold. What it cannot see: `os.stat` and
    `os.path.exists` are not audit events (a probe for a file is invisible), nor is the C layer of
    a library (sqlite is seen at `connect`) or what a child process opens; a call relative to a
    `dir_fd` is read in the directory the descriptor names,
    except `os.open`'s, whose audit event does not carry it (`shutil.rmtree` going down into a
    subdirectory), which is read against the working directory and so still counted, at the
    wrong path; a route is only as deep
    as the requests it is sent, and whether a key has the right kind is not judged by it; and
    other writers (a human's post may store any path) and the feature-board mapping above are
    outside it, since every `demo` run of the sandbox lives in the chief's project. Twenty
    baselines (`REACHES`) are asserted to get to the work their route exists for, the early-stopping
    ones included (a stop with a run held, a supersede, an answer with a question open, a query
    through the canned backend). **Not covered:** `POST /runs/<run_id>/reroute` and `retry`
    (`reroute` sets an attribute of a registered run, `retry` starts a run whose loop the audit
    replaces with one that finishes at once, so a hostile value never reaches what they would do
    with it) and the `codeintel`, `lsp` and `both` backends of `/code/query` (they need an
    external tool; the audit's backend is `cli`).
  - On `/comms/post`, a `from` other than `chief` (or none) is 403.
  - **Ids.** A write that names its target by id is bound by
    `http_server/chief_bind.py::target_in_project`, which the gate calls for a chief token after
    `project_refusal`; the route's entry lists the ids (`Fields.run_ids`, `stamped_run_ids`,
    `row_ids`: ID keys, so the key list holds them). A **run** (`/runs/<run_id>/stop` and
    `/runs/<run_id>/<action>`) is placed by the project root `run_history` recorded for it, else
    the root of a registry entry of any status, else the board its board lock is held on; a run no
    source places is 403 `not in this chief's project`. A **message** is placed by the `board` and
    `scope` of its row, a deleted one included: `/comms/acknowledge`, `/comms/supersede` (`old_id`
    and `new_id`), `/comms/answer` (`question_id`), and, because a goal and a task are rows too,
    the `goal_id` of `/comms/goals/run|stop|decompose`, `POST /runs` and `POST /comms/post`, and
    the `message_id` of `/comms/tasks/run|stop`. A `project` row is the project's when its scope
    is the session's root (`is_own`, the rule a posted scope gets); a `feature` row when its scope
    is one plain folder name and a folder of that name exists under `<root>/pathly/features/` or
    `<root>/pathly/features/.archive/` (a feature scope is a name, not a path, and feature boards
    are keyed by name only, so a feature that exists in two projects is in both, and a planner or
    operator chief can create that folder itself: `POST /comms/features/decompose` (`plan`) makes
    `<project_root>/pathly/features/<feature>` for any one-folder `feature` it is given, at every
    rigor, so for a name that exists in another project the folder check can be made true by the
    chief; a post to a feature board makes no folder); a `global` row,
    and a row on any other board, never. An id no row has passes and the route answers it (404;
    `/comms/acknowledge` does nothing and answers 200). The `run_id` that a `/comms/post` row
    carries is only a correlation stamp, so there a run placed in another project is refused and a
    run no source knows passes (the chief's own session run is one). An id that is not a string,
    is over 512 characters or holds a control character or a lone surrogate is 403 (SQLite cannot
    be handed the surrogate); a blank one names nothing and the route answers 400. Builder tokens
    and no token are not checked.
  - **Not bound.** The table lists these as `unbound` rather than leaving them out. (1) What a
    chief can still reach by id or by name: the id-addressed reads, `goal_id` (`GET /comms/tasks`,
    `/comms/artifacts`, `/comms/goals/refs-coverage`), `message_id` (`GET /comms/artifacts`),
    `run_id` (`GET /runs/<run_id>`, `/db/runs/<id>/cost`, `/api/traces`), `topic` (`GET
    /runner/status`, `/status?topic=`) and `artifact_id` (the path the row keeps is bound, see "A
    stored path"; the row is found by id), have no ticket yet; the `topic` of
    `/runner/agent-answer` is held by the cite rule and the `option_id` of `/comms/answer` is
    refused to a chief by it; a feature name is not bound to a project (feature boards are keyed
    by name only, so `board: "feature"` is not bound). A chief that knows a read's id can read
    another project's row. (2) Routes
    that are fleet-wide and have no project filter to bind: `GET /db/rollup`'s `global` block (it
    sums every project whatever `project_root` says, and its `by_project` lists every project's
    root path with its cost and tokens, so a status chief can read where the other projects are
    and what they spend), `GET /db/stats`'s `features`, `events` and `invocations` counts (global;
    only its token and cost totals follow `project_root`), `GET /telemetry/trends` with a named
    feature (summed across projects), and `GET /metrics` and `/metrics/json` (server counters). A
    status chief can read those, and so can every other token. (3) The packaged and global reads
    (`/flows`, `/registry/*`, `/skills/catalog`, the `/comms/default-*` settings, `/health`) name
    no project. A feature name that a query filters by `project_root` as well
    (`/db/features/<feature>/*`, `/api/features/<feature>/*`, `/api/traces`, `/flows/stage-config`,
    `/comms/scope`, the `feature` of `/db/rollup`) is bound by that root, so the table lists it as
    `under_root`, not as unbound.
- **The gate reads the body as the route will.** The comms routes read it with
  `comms/_helpers.read_json_body` (UTF-8, then cp1252, whatever the content type); `/runs`,
  `/runs/<id>/<verb>`, `/runner/agent-answer` and `/code/query` read it with `get_json`, which
  hands the raw bytes to `json.loads`, so a UTF-8 BOM, UTF-16 and UTF-32 body is understood there
  but not by `read_json_body`, which would show the gate `{}`. `chief_gate._bodies` therefore parses with both
  (`read_json_body` first, which fills Werkzeug's `get_data` cache, then
  `get_json(silent=True, force=True, cache=False)`, which adds no JSON cache, so a body a route
  ignores stays ignored) and every body check (action, overrides, project, `from`) runs over each
  non-empty result.
- **A project writer.** `chief` is in `_PROJECT_WRITERS` and the default project write list
  (`db/queries/app_settings._DEFAULT_WRITE_PERMISSIONS["project"]`), not the global one; a saved
  project list that omits it keeps the existing `/comms/post` 403 naming the allowed roles.
- **Reads are bound too, where the route can be.** A status chief's reads go through the same
  table: a project-board read of another project's scope, a `/db/*` read or `GET /runs` filtered
  to another project, a code query of another project and a `project_root` that is not the
  session's are 403 (the lists above). The reads that cannot be bound are the ones under "Not
  bound": id-addressed reads, the fleet-wide aggregates, and a feature name. A call the gate
  passes as bound must also be answered from its own project: the two caches behind `/code/query`
  (`query._QUERY_CACHE` and `code_context_cli._CLI_CACHE`) are keyed by the project root
  (`scope_names.cache_root`) and hold nothing for a target with no content hash, so a block built
  for a call on one project is never served to a chief on another. (Until round 8 a relative
  target with the same bytes, or a directory such as `src`, was.)
- **Reads are not all pure.** The gate treats every GET (and `POST /comms/search`,
  `/code/query`) as `read`, so a status chief can cause five small writes: `GET
  /comms/artifacts/section?scope=<feature>&trail=x` posts a `status` row ("context pull") on that
  feature's board when the hydrate succeeds (feature boards are keyed by feature name only, so the
  gate cannot bind the feature name to a project, but it does bind the `project_root` the section
  is read from); the same route, with no `trail` at all, inserts a sentinel `comms_messages` row
  (board `feature`, the scope the caller gives, from `system`, type `artifact`), a
  `comms_artifacts` row and a section index for a file it hydrates that exists under a
  `pathly/features|plans|goals|project/` folder of the project it names (bound), at any feature
  scope the caller names, once per file and scope, so this write needs no `trail` (`ensure_indexed`
  and `find_or_create_artifact_by_path`; the scope is held by the path rule above, and the hydrate
  path is unchanged); `GET /menu/<name>` broadcasts a menu push over SSE; `POST /code/query` can start a
  debounced re-index of the project it names (bound above) and logs a `discovery` row (bound
  above); and `GET /skills/prompts` without a `kind` (or with `kind=preset`) runs the one-time,
  idempotent migration of legacy preset rows in the database into prompt files, which writes the
  files and deletes the rows, for the global library and the project it names (bound above). They
  stay `read` because a status chief must be able to read artifact sections, query code and list
  prompts; none of them can change a decision, a task or a run.
- **Not here yet.** The id-addressed reads are not bound to the chief's project (listed under "Not
  bound"); the cost and run ceiling is "Cost and run limit" above.
  `/comms/directives` (ticket 12) has both entries (`decide`; `project_root`, `to_agent` and `text`),
  as every route a chief can reach needs; it is not in the "Naming it" list, because the route
  answers 400 for a body with no `project_root` and falls back to no other project. The built-in
  texts and the `chief-connect` fragment (ticket 17, "The prompt a chief is pasted") teach: name
  your `project_root`, as the last line of the prompt gives it, on the routes under "Naming it";
  send only the keys a route's entry lists (`Fields.allowed`, the 403 names a key that is not
  listed). They do **not** teach posting an artifact or `/code/query`; a text that names them later
  must say that an artifact is posted with an absolute `artifact_path` inside the project (a
  relative one is refused) and that `/code/query` takes a file path as `target` (a symbol like
  `a:b` is read as a drive path and refused). **The chief is handed the stored root.** The gate
  compares `project_root` with the string `open_chief` stored (`chief_sessions.project_root`:
  forward slashes, no trailing slash), by `root_spelling`, and refuses any other spelling of the
  same directory. `chief_presets.ROOT_LINE` puts that exact string on the last line of the pasted
  prompt. A chief that read its own root with `pwd` could get another string (a symlinked parent
  such as macOS `/var` for `/private/var`, a different letter case on Windows, a backslash form)
  and be refused (403 `that is not this chief's project`) on every call that names its project;
  `tests/http_api/test_chief_cli.py` pins that the pasted prompt ends with the stored root.
  Not taught either, because no route reports it: a run's pending question (`GET /runs` rows
  and `RunnerState.public_dict` do not carry it), so `/runner/agent-answer` is shown only for a
  topic the user names; and `pause` / `resume` (board-lock goal runs do not support them, only
  `stop`). The chief cannot write the global board (`comms/_helpers.py` `_GLOBAL_WRITERS`), so no
  text sends it there.

### SSE events (GET /events/runner)

| Event type | Payload fields | Purpose |
|---|---|---|
| `RUN_STARTED` | `topic`, `run_id` | pipeline run began |
| `TERMINAL_SPAWN` | `tab_id`, `run_id`, `run_token`, `label`, `cwd`, `argv[]`, `adapter` | Studio should open a new terminal tab and spawn the PTY. `run_token` is the spawn's identity token, sent raw on `/events/spawn` only: `_broadcast_runner` strips the key from the copies it sends to the topic's `/events/runner` clients and the `/events/runs` clients of that `run_id` (the caller's dict is not mutated), so only a client subscribed to `/events/spawn` when the spawn starts can read the token, and use it until the spawn settles (`None` when the best-effort mint failed). `/events/spawn` needs no credentials, so that hole stays open until the UI token (RRP-2b) |
| `SESSION` | `topic`, `adapter`, `kind` (`opened`/`continued`), `degraded` (the adapter cannot resume), `independent` | adapter session continuity signal. `independent` is true for a stage whose role is in `orchestrator_session.INDEPENDENT_ROLES` (the reviewer): `kind` is then always `opened`, whatever the open session is |
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
    migrations_provenance.py # run provenance (role-read-policy), called from
                           # migrations_incremental._add_additive_migrations:
                           #   add_run_tokens() creates run_tokens (per-spawn identity, only the
                           #   sha256 of the token stored);
                           #   add_comms_provenance() adds comms_messages.author_role /
                           #   author_run_id / author_source (source = token|system|legacy|none),
                           #   indexes agent_invocations(run_id) (the backfill's join would scan it
                           #   once per message otherwise), and backfills every row whose
                           #   author_source is NULL as `legacy` (supervisor/system -> role
                           #   `system`; else the role of the agent_invocations row its run_id
                           #   joins; else from_agent; author_run_id stays NULL). The NULL filter
                           #   re-runs on every start, so a writer that leaves author_source NULL
                           #   is relabelled `legacy` at the next start; hydrate_board
                           #   (board_mirror_hydrate.py) runs it after importing a snapshot, so
                           #   a pre-upgrade BOARD.json row is `legacy` at once.
    migrations_chief.py    # add_chief_tables() (chief-agent), called last from
                           # migrations_incremental._add_additive_migrations: chief_sessions
                           # (one row per chief tab, indexed on project_root), chief_human_messages
                           # (indexed on run_id) and chief_citations (message_id UNIQUE, so a human
                           # message is citable once). CREATE ... IF NOT EXISTS, idempotent;
                           # chief_sessions.runs_started (the runs a session has started, ticket
                           # 15) is ALTERed in when the table exists without it, once
    provenance_values.py   # the author_source vocabulary and the `system` stamp, defined ONCE
                           # (AUTHOR_SOURCES = token|system|legacy|none, SYSTEM_ROLE, SYSTEM_AUTHOR,
                           # SYSTEM_PAIR) and check_author_source (the one ValueError for an
                           # unknown source: post_message and update_message_text ask it before
                           # writing); imported by runner/provenance.py and comms_artifacts.py
    pricing.py             # PRICING + CACHE_RATES tables (cached tokens are a subset of tokens_in,
                           # priced at a multiple of the input rate), cache_tokens_of(),
                           # PricingRegistry, estimate_cost()/infer_provider(),
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
      comms_directives.py  # get_binding_decisions(conn, boards, scopes, role): the binding (`binding = 1`) decisions a prompt carries whatever their status, not deleted or superseded, addressed to the role or `*` (`*` only for an empty role), oldest first; board and scope lists go in as one JSON string each through `json_each`, so the statement is one static literal; `post_directive(conn, scope, to_agent, text, **author)`: the one writer of `binding = 1` (a `decision` from `chief` on the project board through `post_message(..., binding=1)`, whose one INSERT sets the flag)
      comms_edit.py        # update_message_text: edits a row's text AND sets its three author columns from the editor's stamp (none when no stamp is passed), and answers `"binding"` without changing anything for a row with `binding = 1`; re-exported from comms_messages / comms
      comms_artifacts.py   # artifact metadata CRUD (attach, list, section index, update_summary)
      comms_tasks.py       # task DAG operations (get_ready, complete, claim, fail, reclaim, goal_refs_coverage)
      task_results.py      # build-proof: latest_task_summaries(conn, task_ids) — the newest AGENT_DONE `summary` of each task's `sched-<id>#<n>` runs (a dependent task's prompt shows it)
      task_proof.py        # build-proof task reads: get_task, tasks_claimed_since / tasks_completed_since (goal- else (board, scope)-scoped, parsed-time window), set_floor_allow (the human-set floor_allow JSON list; refreeze re-copies text into claimed_text)
      comms_embeddings.py  # embedding storage + hybrid/semantic search; search_by_embedding() merges parent+child vectors, deduplicates by message_id, returns _matched_chunk for subtopic surfacing; store_chunk_embeddings() writes to comms_chunk_embeddings; SEMANTIC_DISTANCE_CEILING (0.72) + opt-in max_distance= floor scored hits for /comms/search (BM25 hits bypass; comms_context.py keeps its own per-tier gates); _fts_query() quotes each token so raw FTS5 operators (code:query, a OR b, unbalanced ") match literally instead of reparsing; search_by_hybrid() tags each row _match_source (keyword|semantic) for client grouping
      comms_counts.py      # count_goals_for_feature / count_features_for_project — gate the consultation flows' seed thresholds
      comms_goals_read.py  # get_goals_with_rollup() — backs GET /comms/goals
      comms_summary.py     # per-artifact AI-summary selection/style/note setters+getters (unified-ai-routing)
      skill_composition.py # per-project skill-composition overrides (composition editor)
      prompt_library.py    # prompt_library table CRUD — now the LEGACY kind='ability' store only; global/project merge, name-upsert, idempotent seed. kind='preset' (system-prompts) moved to FILES → skills/prompt_files.py (mirrors abilities), with a one-time lazy DB→files migration
      chief.py             # chief-agent sessions: create_session / get_session / open_session_for_project,
                           # close_session (once; revokes the run's tokens before marking it closed) and
                           # close_stale_sessions (reason `server restart`), add_human_message (first message
                           # of a session is `style_prompt`, later ones `human` or `relayed`) / get_human_message,
                           # record_citation (False when the message was already cited). Static SQL, writes under _get_write_lock
      chief_run_slots.py   # take_run_slot / give_back_run_slot: the run counter of a chief session (chief_sessions.runs_started), each one conditional UPDATE under _get_write_lock (a slot is taken only below the limit, given back only above 0); used by chief_budget
      placement.py         # run_project_root(conn, run_id) (the root run_history recorded) and message_board_scope(conn, message_id) ((board, scope) of the row, deleted or not): what chief_bind places an id by; one static statement each
      run_tokens.py        # mint_run_token / resolve_run_token / revoke_run_tokens — the per-spawn identity (role-read-policy): the raw token is returned once and only its sha256 is stored, next to run_id/role/feature/project_root/board/scope; resolve returns None for an empty, unknown or revoked token; lookup_run_token returns the row whether or not it is revoked (None only for an empty or unknown one), so the chief gate can tell a revoked token from an unknown one; revoked when the spawn settles
  runner/                  # CLI runner, agent invocation, argv, output parsing
    argv.py                # resolve_argv, resolve_interactive_argv, _storage_path
    chief_argv.py          # the chief's argv and claude settings (chief-agent), pure: chief_argv(engine, model, settings_path, mcp_path, session_id) — claude `--restricted --tools Bash,Read,Glob,Grep --settings … --mcp-config … --strict-mcp-config --session-id …` (+ `--model` only when given), codex `--sandbox read-only --ask-for-approval on-request`, any other engine ValueError, never a permission-bypass flag, the prompt or the token; claude_settings(hook_command) — allow `Bash(pathly *)`, the deny list, one UserPromptSubmit command hook
    output.py              # parse_result, _extract_json_payload; extract_tokens + the per-adapter
                           # _TOKEN_STRATEGIES registry (Strategy A — token counting; cost is
                           # Strategy B in db/pricing.py); extract_cache_tokens() → the cached
                           # subset of tokens_in, returned by parse_result for cache-aware pricing
    events.py              # read_last_agent_done, _patch_last_agent_done, tail_agent_done
    history.py             # build_pipeline_history_block
    invoke.py              # invoke_agent(abort_callback=None, proc_callback=None)
    embeddings.py          # embed()/warm() — local embedding model; embed() has a bounded LRU (check inside _model_lock) so the per-board search fan-out re-embedding one query N+2 times computes the vector once; model load RETRIES transient failures (was a permanent silent latch that disabled semantic search process-wide) and embedder_status() reports {loaded,unavailable,load_attempts} to /health; chunk_summary() splits a summary into child chunks (per-bullet for topic-map, per-### for detailed, none for gist); embed_artifact_async() stores one PARENT vector (whole message text + summary) in comms_embeddings + CHILD vectors per chunk in comms_chunk_embeddings
    board_scope.py         # ONE resolution of which tiers a run may see, serving BOTH directions: the context pushed into the prompt (board_context_for) and the tiers the board-search fragment lets an agent pull (<search_tiers>) — an agent told it may search a tier its own context channel isn't reading would be reaching AROUND the board-scope setting; search_tiers_value() renders board+scope pairs (feature->slug, project->normalized root, global->"global") since a mismatched pair returns [] rather than an error
    read_policy.py         # the role read wall (role-read-policy), defined once: ReadPolicy, BUILTIN_DEFAULTS (reviewer/tester/chief/anonymous), NEVER_WITHHELD_TYPES, row_allowed (pure) + policy_predicate (the same rule as a SQL fragment over type/author_*; tests keep them in agreement) and resolve_read_policy(conn, role, feature, project_root). BUILT BUT NOT WIRED: no read path calls it and nothing reads the read_policy.mode setting, so it withholds nothing from any agent (see "Who wrote a board row, and who may read it")
    comms_context.py       # assembles board context (governance + referenced + semantic, relevance-gated); tags each kept row _tier from the search loop (authoritative, not row["board"]) so the render can budget per tier; _matched_chunk surfaced as "matched topic: …" via comms_formatters.py; takes the prompt's `role` for the standing orders and keeps binding rows out of the Context channel
    comms_governance.py    # governance_decisions(conn, boards, scopes, role, project_scope): the pending decisions plus the standing orders for the role (from the tiers the run reads and always from the project board when the run has a project root), de-duplicated by id and marked `_binding`; if the standing-order query raises it logs a warning and leaves the pending half unfiltered; standing_orders_only() is the block of a run whose every tier is off
    comms_binding.py       # BINDING_MARK (the `_binding` key comms_governance sets on a row) and is_binding_row (`binding == 1`, nothing looser): the one meaning of "binding" that comms_governance, comms_formatters and comms_context share; a leaf module with no package imports
    comms_formatters.py    # pure list[dict]→list[str] rendering for that context, incl.
                           #   render_governance_lines(): decisions NEWEST-FIRST with a LATEST
                           #   marker, minute-precision stamps (same-day decisions are the ones
                           #   that conflict, and "13d ago" cannot order them), an explicit
                           #   precedence line, and — when a decision post-dates an open
                           #   escalation — a note that only a human acknowledgement closes a gate;
                           #   decisions marked `_binding` render first in their own
                           #   "Standing orders" block, outside that ranking
    context_budget.py      # per-tier char budget MATH (pure — no DB on the render path): allocate_budget() splits the configured char_budget by weight (feature .5/project .3/global .2) NORMALISED over the enabled tiers (a feature-only run still gets the whole budget), select_within_budget() charges each line to its own tier then pools the unspent remainder; replaces a single shared budget that let the feature tier (rendered first) starve project/global outright
    context_settings.py    # the two numbers that size every board block, as app_settings keys read at CALL time (same contract as code_context.backend): board_context.char_budget (default 4000, bounds [200,40000]) + board_context.k_{feature,project,global} (defaults 5/3/2, bounds [0,25]). They are a PAIR — k binds first in the intended case, so raising the budget alone is half a change. Garbage/out-of-range FALLS BACK to the default rather than clamping, so the rendered block always matches a documented number; k=0 legally mutes one tier's semantic pull while its governance still injects. Needs NO new route: GET /db/settings + PUT /db/settings/<key> already take arbitrary keys. Replaces bare literals (2000, and 3/2/1 inline in enabled_boards) that had no recorded justification — unlike the cosine cutoffs beside them, which carry a live-board calibration
    context_record.py      # render_stats() + record_board_context() — appends ONE `BOARD_CONTEXT` fsm_event per prompt build carrying the volume actually rendered vs dropped (rendered_entries/chars, per-tier chars, omitted_entries/chars) PLUS the budget+k in force, so the next move on those numbers is made from data. Inert to telemetry: append_event projects only AGENT_DONE/BILLING_UPDATE. Wrapped + never-raising (a telemetry write must never break prompt assembly) and create_dir=False so it can't plant an empty decoy dir that later wins _resolve_storage_path's existence probe. Opt-in via storage_path, which keeps the /comms/agent-context preview write-free
    sections.py            # parse_sections/slugify_heading/structure_key — markdown section index (anchors)
    hydrate.py             # hydrate_section/ensure_indexed — /section payload + staleness; index_artifact_async (eager, section-index only)
    code_context.py        # CodeContextProvider protocol + get_provider()/build_block() (backend=auto[default]|off|cli|lsp|both|codeintel) — codebase-intelligence context injection
    code_context_cli.py    # CliProvider — shells out to codebase-memory-mcp graph for code_context.py; the target's tail goes into the Cypher as a string literal with its backslash doubled, and a tail with a double quote is not queried at all (no section: the real tool's lexer could not be checked for a backslash-escaped quote); a relative target is hashed under the project root the call names, not the server's working directory, and the per-file cache is keyed by (project root, path, hash) so a block built for one project is never served to another
    code_context_lsp.py    # LspProvider — bridges a long-lived Serena MCP session (LSP, always-fresh); async warm-up, never-raise
    code_context_codeintel.py # CodeintelProvider — backend=codeintel: answers /code/query's op as asked (real callers/impact rows, semantic search) via the installed `codeintel` package — a running `codeintel serve-http` first, else one-shot `codeintel query --json`; `auto` prefers it when installed; never-raise
    cli.py                 # run_flow, main, resolve_stage, handle_blocked, handle_decide
  supervisor/              # Visible runner: PTY spawning, SSE broadcast, registry
    state.py               # RunnerState, OpenSession dataclasses
    registry.py            # _registry, _lock, get_state, recover_stale_mirrors,
                           #   find_active_run_for_goal (a goal's FSM run is registered under
                           #   its board-nested topic, so a scope lookup misses it)
    terminal.py            # _run_stage_via_terminal — THE SPAWN. Re-exports the names below,
                           #   because supervisor/__init__ and the tests import them from here
                           #   (and _reconciliation_window is monkeypatched in THIS namespace,
                           #   so it must be called as a bare name, never via its own module).
    terminal_argv.py       # _resolve_spawn_argv — the seam a NEW ADAPTER touches
    terminal_identity.py   # _record_spawn_identity/_record_spawn_prompt/_settle_spawn_identity, _run_board_scope; _issue_spawn_token/_spawn_role mint the spawn's run token (revoked in _settle_spawn_identity)
    terminal_reconcile.py  # _agent_done_watcher, _reconciliation_window, _synthesize_agent_done_if_missing
    terminal_billing.py    # _emit_executor_telemetry, _reconcile_billing_now (were spawn-local closures)
    terminal_phase.py      # _write_supervisor_phase_summary
    interactions.py        # _await_agent_question (keeps the pending question on RunnerState._agent_question: question, options, every question of the ask, asked_at; cleared on every exit)
    orchestrator.py        # _loop, _resolve_stage_supervised (399 lines — under the
                           #   400 ratchet since fan-out Phase C, so it can never regress)
    fan_out.py             # run_stage — THE one call site for executing an FSM stage:
                           #   no parallel_states entry -> _run_stage_via_terminal unchanged;
                           #   entry present -> scheduler_loop drains the state's ready tasks
                           #   and returns a merged result in the SAME shape. Phase D:
                           #   isolation=lane -> AuditedLaneIsolation (parallel while the
                           #   partition audits safe); serial obeyed; worktree degrades.
                           #   Phase E: the ONLY drain — `executor: loop` reaches it as the
                           #   goal-loop flow's DRAINING state. Frontier scope = the run's
                           #   BOARD scope, not state.topic (a goal run's topic is its own slug).
    spawn_window.py        # observe — wraps the single-path spawns (run_stage's and the feedback
                           #   spawn): a SPAWN_WINDOW event (role, tree + HEAD before/after) when
                           #   the flow has a floor/scope/reviewer gate (see "Spawn windows" below)
    orchestrator_session.py # resolve_session — same-adapter session reuse + the SESSION event; a stage whose
                           #   role is in INDEPENDENT_ROLES ({reviewer}, by fsm_compose_tables.agent_role_of)
                           #   always opens a fresh session (never --resume's the builder's transcript)
    api.py                 # start_run, pause_run, resume_run, abort_run, supply_decision, reroute_run
    goal_run.py            # thin re-export shim (start_goal_run / start_goal_decompose) → the two modules below
    goal_executor.py       # Board→Goals→Task-DAG executor dispatcher:
                           #   start_goal_run(goal_id, executor_override=…) reads the goal's
                           #   `executor` field and routes to one of three strategies:
                           #   single → one agent drains the whole DAG (start_board_run + drain-dag skill)
                           #   loop   → runs the 'goal-loop' FSM flow (Phase E — a flat, one
                           #            fan-out state drain; NOT team-build, which is reviewed)
                           #   team   → runs an FSM flow (default 'team-build') via start_run
    goal_decomposer.py     # start_goal_decompose() bridges an analyzed goal into a DAG
                           #   (mode='planner' or mode='consultation')
    scheduler.py           # DAG frontier loop (scheduler_loop): event-driven, blocks on completion_q;
                           #   at most one worker per lane; goal_id= scopes the frontier to one goal's tasks
    task_prompt.py         # build_task_prompt — ONE assembly of a DAG task's prompt: the composed
                           #   development/execute-task body with its fragment placeholders
                           #   SUBSTITUTED (the DAG path had no injector at all — see Phase E),
                           #   plus the dependency-results block, the runner contract, the retry
                           #   ladder (+ the root-cause-debug guide) and board context
    task_dependencies.py   # dependency_results_block(task) — `## Results of the tasks this one
                           #   depends on`: per direct depends_on id a `### <its first text line>`
                           #   heading and its latest AGENT_DONE summary (see "Dependency results")
    drain.py               # drain_frontier — the ONE scheduler_loop call site. Owns the cost
                           #   tracker (wrapping spawn_fn exactly once) and folds the cap into
                           #   abort_check, so neither fan_out nor goal_executor can forget it.
                           #   Wraps the spawn with task_proof.wrap inside the tracker.
    task_proof.py          # wrap(spawn_fn) — proves each DAG task after it reports success:
                           #   floor scan, frozen task text, check blocks, TASK_PROOF (see "Task
                           #   proof in the goal-loop drain")
    isolation.py           # lane / serial isolation strategies for the frontier loop
    file_claims.py         # CROSS-FEATURE file-claim registry (feature A vs feature B) —
                           #   wired in goal_executor only; scheduler_loop never calls it, so it
                           #   says nothing about two TASKS inside one drain. See lane_partition.
    lane_partition.py      # audit_lane_partition — checks the "disjoint files per lane"
                           #   assumption LaneIsolation rests on: undeclared footprints and
                           #   cross-lane overlaps. AuditedLaneIsolation enforces it, re-running
                           #   the audit EVERY scheduling round (the frontier grows mid-drain)
                           #   and failing closed to 1 worker.
    artifact_reconcile.py  # after a stage/goal run: attach the stage's declared <out_path>
                           #   (resolved from the FSM's own manifest via fsm_compose.resolve_stage_out_path,
                           #   passed as out_path — state-one-authority: NO ARTIFACTS.jsonl ledger) AND
                           #   <storage>/feedback/*.md (HUMAN_QUESTIONS/REVIEW/TEST_FAILURES)
                           #   to the board (idempotent). A headless human checkpoint also posts
                           #   a type='escalation' board message (orchestrator_stage.py) so it's
                           #   answerable instead of failing silently.
    slug.py                # scope / slug helpers for goal + board addressing
    orchestrator_stage.py  # single-stage resolution helpers split out of orchestrator.py
    human_escalation.py    # post_human_escalation(state, text) — the one writer of a to_agent='human'
                           #   escalation for a parked run (a human checkpoint, a red base)
    base_smoke.py          # check_base — smoke the base before the first spawn (see "Run guard rails")
    run_budget.py          # refresh — raise a goal run's max_iterations from its DAG (see "Run guard rails")
    board_run.py           # start_board_run: board-lock + skill compose + async spawn helper
    board_lock.py          # Per-board/scope advisory lock (acquire/release/holder)
    chief_tiers.py         # what a chief may do (chief-agent): ACTIONS, TIERS (status=read; planner=read,post,plan; operator=all seven), actions_for/normalise_tier, and resolve_preset_tier — a user prompt file chief/<preset> names its tier in leading front matter `tier:`, else the built-in names map to themselves, anything else (unknown tier, missing front matter, malformed name) is status. Code, never read from prompt text; strip_front_matter reuses skills/compose_base
    chief_presets.py       # the chief's prompt (chief-agent 17): the built-in styles STATUS / PLANNER / OPERATOR (BUILT_IN), default_style (user file chief/<preset> wins, else the built-in text), compose_prompt (style + the chief-connect fragment, read at call time, + ROOT_LINE with the stored project root)
    chief_session.py       # open_chief / close_chief (chief-agent): the chief is a long-lived interactive spawn, so it has its own open path instead of _run_stage_via_terminal (which blocks its caller and gives up after 30 minutes). open_chief validates (engine claude|codex, existing project_root, the style non-empty and at most 64 KiB, model not starting with `-`; `prompt` is optional for a preset that has a built-in text), raises ChiefAlreadyOpen(run_id, tab_id) for a project with an open chief, resolves the tier from the preset, writes ~/.pathly/chief/<run_id>/ (hook_secret, and for claude settings.json + an empty mcp.json; mode 0600), registers the chief_sessions row (secret sha256, the claude --session-id), mints a `chief` token on the project board, create_run(run_id), and sends one interactive TERMINAL_SPAWN (topic `chief:<run_id>`, submit false, the prompt from `chief_presets.compose_prompt`: style without front matter, then the `chief-connect` fragment, then the stored root); once the token is minted the session is read again, and a close that landed in between revokes the token, sends no spawn and raises ChiefClosedWhileOpening (POST /chief/open: 409; a close after that re-read cannot be shut out without a lock across the broadcast, it still revokes the token so the tab gets a dead one); a daemon watcher wakes on the first of the tab's `started` or its result (TerminalRun.wait_started_or_result) and closes the session as `never started` or `tab closed`. close_chief revokes the token, removes the folder and drops the run (False the second time). normalise_project_root (forward slashes, no trailing slash) keys a project's chief for open_chief and the routes; chief_startup_cleanup() closes every session still open at server start (reason `server restart`) and removes their folders; something_answers(host, port) is the TCP probe app.main() runs before it
  http_server/             # Flask HTTP server: FSM endpoints + SSE + runner routes
    app.py                 # Flask app factory, blueprint registration, main() (which calls supervisor.chief_session.chief_startup_cleanup() before serving, unless chief_session.something_answers(host, port) finds a server already answering there; a failure is logged and boot goes on)
    middleware.py          # _log_request, _log_response, rate limiting, metrics
    chief_gate.py          # chief_gate(): the before_request hook (registered after _log_request) that refuses a chief token's call its tier, project or poster does not allow, and answers 401 for a closed chief session — see "Chief gate"
    chief_routes.py        # the chief gate's route table as data: ROUTE_ACTIONS ((rule, method) -> action), the GET refusals, the post-type and run-verb refinements and action_for()
    chief_fields.py        # the chief gate's second route table: ROUTE_FIELDS ((rule, method) -> Fields), merged from CALL_FIELDS and READ_FIELDS; per route the complete list of the keys a chief may send (and the ones deliberately left out), each with a kind, and which of them the route reads as a project root, a board scope (a folder name where the route joins it into a path), a file, a flow or a skill, when the root must be named (always, for some verbs, or unless a feature is given), the names the root bounds (`under_root`) and the ids it leaves unbound (with a note for the fleet-wide reads); a test fails when a reachable route has no entry
    chief_field_types.py   # what an entry can say: the kinds of a key (text, number, flag, enum, name, id; root, scope, segment, path, ref, flow, skill), `Fields` (kinds(), declared(), allowed(rule)), `ScopeRead`, `TextPath` and `url_variables(rule)`
    chief_field_calls.py   # CALL_FIELDS: the entries of the POST routes the action table lists, each written from the view and the helpers it calls
    chief_field_reads.py   # READ_FIELDS: the entries of the GET routes a chief can reach (the query keys they read, or the reason they read no project)
    chief_project.py       # project_refusal(): applies a ROUTE_FIELDS entry to one request (query string for a GET, body otherwise, the URL's `<action>` for the retry verb) and says whether the project it names is the session's — see "Chief gate"
    chief_bind.py          # target_in_project(): places the run, goal, task or message a chief names by id (`run_ids`, `stamped_run_ids`, `row_ids` of its entry) in the session's project, and is_id() — see "Chief gate"
    chief_keys.py          # key_refusal(): refuses a key the entry does not list, and a `flow` or `skill` that is not one name (scope_names.is_flow_name / is_skill_name) — see "Chief gate"
    chief_budget.py        # the cost ceiling and the run limit of a chief session (chief.max_cost_usd_per_run, chief.max_runs_per_session): budget_refusal() is the gate's last check and takes the run slot, refund_run_slot() is the after_request hook that gives it back for a 4xx, ceiling_usd()/run_limit() read the settings — see "Chief gate"
    chief_cite.py          # cite_refusal() / answer_text(): the cite rule for an `answer` action — the chief names a human message of its session by `cite`, the gate checks it (kind human, this session, typed after the question, once; an acknowledgement must say `agent: "chief"`) and keeps its text on flask.g for the answer routes to relay — see "Chief gate"
    run_identity.py        # caller_identity(request) -> CallerIdentity: kind run|anonymous from the X-Pathly-Run-Token header (body role/run_id/from never read); unknown/revoked token logged at info with the remote addr; `ui` kind reserved (RRP-2b); `is_chief_run(identity)`: True for a live run whose role is `chief` and nobody else (the test behind who may post and who may retire a binding directive). Routes apply a policy from it: who posts and retires a directive, the human-gate refusals (`comms/_helpers.py`), a task's completion and `floor-allow` (`comms/tasks_status.py`, `tasks_floor.py`), `force_past_gate` (`core/fsm.py`) and the chief open/close routes; `chief_gate` reads the token row itself (`lookup_run_token`) instead
    sse.py                 # SSE globals (_clients, _runner_clients, _menu_clients) + broadcast helpers
    pricing.py             # MODEL_PRICING, compute_cost_usd()
    feedback.py            # _feedback_watcher, _process_feedback_file
    blueprints/            # registered in app.py via the all_blueprints list
      core/                # health.py (GET /health,/status; POST /shutdown); fsm.py (POST /next_action,/complete_stage)
      runner/              # api.py + api_lifecycle.py + api_control.py — 13 /runner/* routes; streams.py (GET /events/menu|runner|spawn|history|stream|comms)
      flows/               # defs.py (flow CRUD); stage_configs.py (per-stage overrides: agent/adapter/skill + layer-3 ability_ids + excluded_sections — the flow-phase-inspector SELECTION, applied FRESH at spawn by fsm_compose.build_prompt, never stored as trimmed text)
      catalog/             # items.py (file-tree catalog)
      skills/              # editor.py re-export shim; editor_render.py (/skills/catalog|parse|preview|compose [returns segments+tokens; accepts ability_ids]|summary-format/<style>); editor_io.py (/skills/save|export); prompt_library.py (/skills/prompts — system-prompts are file-backed via skills/prompt_files.py, kind='ability' stays legacy DB); abilities.py (/skills/abilities — layer-3 ability FILES, see skills/abilities.py)
      comms/               # board + goals/DAG, split by domain: messages*.py, tasks.py, artifacts*.py, runs.py, goals.py, goals_read.py (GET /comms/goals rollup), settings.py, context.py, directives.py (POST /comms/directives, chief token only), features.py (/comms/features/decompose), project.py (/comms/project/decompose) (+ _helpers.py); see "Comms board endpoints" above
      ops/                 # telemetry*.py (/record_activity, /record_phase*, /telemetry/*); menu.py (/menu, /metrics); db_api*.py (/db/* read API); chat.py (/chat); export.py
      code/                # query.py (POST /code/query — codebase-intelligence; its answer cache is keyed by (project root, op, target, content hash, backend) and holds nothing for a target with no hash: a directory, a missing file or a symbol)
      hq/                  # the HQ copilot (pathly/features/hq-copilot, local-operator): prompt.py
                           # (POST /hq/prompt — the model turn Studio sends its LOCAL model:
                           # hq_prompt.prepare_hq_turn, or hq_operator.prepare_operator_turn when
                           # enabled_actions survive → {redirect | system_prompt + prompt,
                           # manifest, context_tokens, tools, actions}); context.py (GET
                           # /hq/context — the same packet for inspection; 404 unknown board);
                           # actions.py (GET /hq/actions, PUT /hq/actions/available — the operator
                           # catalog and what Settings allows); actions_run.py (POST
                           # /hq/actions/check|run|report — proposals → cards → execution);
                           # _action_targets (resolve + fingerprint), _action_exec (in-process
                           # dispatch to the real route), _action_audit (local-operator board
                           # line); _helpers.manifest / available_actions.
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
                           # _helpers.py holds the shared resolution/abort/retry + create-run bodies;
                           # _cost.py: as_cost() (a finite number above 0) and flow_cost(body), the
                           # cap POST /runs gives a flow start — shared with the chief gate);
                           # run_streams.py (GET /events/runs?run_id=<run_id> — unified per-run SSE
                           # feed, T3: mirrors the /events/runner shape incl. the
                           # pathly_sse_clients_active gauge bookkeeping; fed by
                           # sse._broadcast_run_event, teed from _broadcast_runner/_broadcast_comms
                           # whenever a payload carries a run_id)
      chief/               # session.py (chief-agent): POST /chief/open, POST /chief/close, GET
                           # /chief/session; human.py: POST /chief/human-messages (the chief hook's
                           # post) — see "Chief endpoints"; __init__.py exposes all_blueprints
                           # (registered in app.py like control/)
  chief_cli.py             # the `pathly` console script (chief-agent 17): `pathly api METHOD /path
                           # [json | -]` — the chief's only door to the server; see "Chief endpoints"
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
| `fsm_compose.py` (385) — keeps `build_prompt` / `build_prompt_for_agent` / `_load_agent_text` | `fsm_compose_tables` (lookup tables) · `fsm_compose_vars` (`_inject_prompt_vars` + its inputs) · `fsm_compose_paths` (`resolve_stage_out_path`, `resolve_board_scope`) · `fsm_compose_stage` (section drops, stage overrides, adapter choice) · `fsm_compose_hints` (`_agent_hint`) · `fsm_compose_review` (the reviewer's Review packet) · `fsm_compose_feedback` (`feedback_path`, `read_feedback`, `feedback_block`: what a feedback prompt shows of its file) |
| `skills/compose.py` (197) — keeps the resolver | `compose_base` (constants + `_strip_leading_frontmatter`) · `compose_resources` (manifest/skill/fragment I/O) · `compose_caps` · `compose_segments` · `compose_validate` |
| `supervisor/terminal.py` (390) — keeps the spawn | `terminal_argv` · `terminal_identity` · `terminal_reconcile` · `terminal_billing` · `terminal_phase` |
| `fsm/engine_actions.py` (204) — keeps `run_transition_actions` | `fsm/gates/` — one module per gate type (`artifact` · `tasks` · `scope` · `command` · `reviewer` · `floor` · `task_checks`) behind the `run_gates` dispatcher in `gates/__init__.py`; `_helpers` owns `append_event` / `_write_gate_feedback` / `gate_failed` / `project_root_of`; `_proof` (stage writes, spawn windows), `_proof_record` (`proof_base`, `TASK_PROOF`) and `_scope_tasks` are shared by the build-proof gates |

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
| `scope_gate` | `scope.py` | the builder stayed inside its declared footprint (git diff ∪ untracked vs. the paths in `scope_file` ∪ the claimed tasks' `files`; see "Scope gate" below) | `scope_file` (optional); flow-level `scope_gate.exempt_prefixes` |
| `command_gate` | `command.py` | **the project's own verify command exits 0** | `command_key` (+ optional `command`, `timeout`) |
| `reviewer_unchanged` | `reviewer.py` | a reviewer spawn changed no file and made no commit (the supervisor's `SPAWN_WINDOW` events; see "Reviewer gate" below) | — |
| `floor_gate` | `floor.py` | **the run's diff since the `proof_base` weakens no test, check, config or plan** (`proof.floor.scan` over two working-tree snapshots; see "Floor gate" below) | — (app setting `floor.enabled`) |
| `task_checks` | `task_checks.py` | **each completed task's `check` block exits as it says**, run from the text frozen at the claim, once per completion (the tasks completed since the `proof_base`, minus those whose newest `TASK_PROOF` proves their current claim; see "Task checks gate" below) | — |

**The first four read state that agents produced; `command_gate` and `task_checks` execute
something.** That distinction is the point of it: `verify_gate` is satisfied by an agent writing `RESULT: PASS`, so
the FSM's pass/fail signal was, end to end, an agent's opinion of its own work. `command_gate`
re-derives the answer from a process exit code and routes the real stdout/stderr back as feedback.
`task_checks` does the same for a task's own check block. `reviewer_unchanged` reads what the
supervisor measured around the reviewer's spawn, not what the reviewer reported. `floor_gate`
reads the git working tree itself, not what the builder reported.

**Command resolution** (highest precedence first): `gate["command"]` literal → app-setting
`verify.<command_key>` → **skip**. Configure a project with
`PUT /db/settings/verify.test {"value": "python -m pytest -q"}` (also `verify.build`, `verify.lint`,
and `verify.timeout_seconds`; default timeout 600s). `verify.smoke` is run by no gate: only the
run-start base smoke runs it (see "Run guard rails"); `floor_gate` and the task proof only read it, to
tell whether a `Makefile` counts as config.

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
The splitting, the run and the clipping live in `proof/command.py` (`to_argv`, `run_command`,
`clip`, and `clip_to(text, limit)`, head and tail in a character limit), the one command runner
the gate and task check blocks share.

**Task check blocks (`proof/checks.py`).** A task's text can carry ```` ```check ```` fences;
every one anywhere in the text counts. Inside a fence: `$ <command>` starts a check, `exit <N>`
or `exit nonzero` sets the exit code it must give (default `exit 0`), each `prints <text>` names a
substring its output must contain, and `#` comments and blank lines are ignored. A command that
needs `&&` is written as two `$` lines, because each runs through `run_command` (no shell).
`checks_in(text)` raises `ParseError` on a line it cannot read (a `prints` before any `$`, a
second `exit`, an unclosed fence). `run_checks(checks, cwd, timeout)` runs every check, not
stopping at the first failure, and returns `(ok, report)`: one block per failing check with the
command, `wanted:`, `got:` (`exit <N>`, `timed out after <N>s` or `could not run: <error>`) and
the clipped output. `run_task_checks(task, cwd, timeout)` judges one task: it reads the blocks of
`claimed_text` (else `text`) and returns `(result, report)` with `result` `passed`, `failed`, `none`
or `error` (a `ParseError`, quoted in the report). `supervisor/task_proof.py` calls it for a
goal-loop task, and the `task_checks` gate for a task a builder completed ("Task checks gate"), so
the two cannot disagree about what a pass means.

**Floor guard (`proof/floor.py` over `proof/tree.py`).** Ported from feature-flow's
`floorguard.py` (MIT): its regexes and config-file content rules, not its CLI. It looks for a build
that got green by weakening the bar. `scan(root, base, after, *, allow, protected, may_change,
config_commands)` diffs two snapshots and returns `FloorReport(findings, warnings, error)`, each
finding `"<category>: <path>: <line>"`. `error` is set when a snapshot is missing or a git call
failed or timed out: the findings it holds are real, but the scan is incomplete, so a caller can
log a skip instead of reading it as clean. Categories (`CATEGORIES`, read by `parse_allow`, which raises
`ValueError` on an unknown name): `skip` (skip/xfail markers, and focused tests in test files),
`suppress` (`noqa`, `type: ignore`, `eslint-disable`, …), `empty-catch` (a one-line
`except …: pass` or `catch {}`), `threshold` (`fail_under` and kin), `trivial-assert` (an assertion
that cannot fail, in a test file), `test-delete`, `config` (lint/test/CI config by file name, plus
the guarded sections of `pyproject.toml`/`setup.cfg`, the test keys of `package.json`, collection
words added to `conftest.py`, and a `Makefile` when a verify command starts with `make`),
`plan-edit` (a path under a `protected` prefix that `may_change` does not excuse) and `task-edit`
(checked by the callers, which hold the task rows). The pattern categories, `test-delete` and
`config` apply only **outside `pathly/`**, so plan docs may mention `@pytest.mark.skip` in prose;
plan files are judged by `plan-edit`. Fewer assertion lines added than removed in test files is a
warning, not a finding; categories in `allow` are dropped. The snapshot (`tree.snapshot`) copies
the file `git rev-parse --git-path index` names to a temp file, keeping its mtime (git re-reads an
entry as new as the index file, so a fresh mtime would hide a same-second, same-size edit), points
`GIT_INDEX_FILE` at it, runs `git add -A` and `git write-tree`: a tree id for tracked and untracked
(not ignored) files, with the repo's real index and `HEAD` untouched. `head`, `changes`,
`diff_text` (with `:(exclude)<path>` pathspecs), `blob` and `read` work on those tree ids;
`changes_or_none` and `diff_text_or_none` return `None` when git fails, and `unquote_path` reads a
name git C-quotes in a patch header. Every `tree` function fails open (`None` or empty) when the
root is not the top folder of a git work tree (a project inside a larger repo included), or git
fails or is missing; each git call has a 60 s timeout and drops inherited `GIT_DIR`-style and
pathspec variables (`GIT_LITERAL_PATHSPECS`, …). Snapshot objects are unreachable, so `git gc`
prunes them later. `supervisor/task_proof.py` calls the scan for a goal-loop task and `floor_gate`
calls it for the whole run ("Floor gate").

**Proof base and task proofs (`fsm/gates/_proof_record.py`).** The floor and task-check gates
judge the whole run, not one stage: a builder fix round runs inside REVIEWING, TESTING, RETRO or
after a goal-loop drain, and `build_baseline` is popped on every transition. So STATE carries a
run-wide `proof_base {tree, started_at}`:

- **Stamped** by `fsm_ops.next_action` (`stamp_proof_base`, right after the `build_baseline`
  stamp) the first time the run is in a state `wants_proof_base` accepts, and only when STATE has
  none. A state qualifies when a gate list on an edge out of it holds a `floor_gate` or
  `task_checks` gate; the edges are the `<state>-><X>` keys and the wildcard `-><X>` keys for
  every `X` in the flow's `transitions[state]`. `tree` is `proof.tree.snapshot(project_root)`,
  `None` outside a git repo; `started_at` (`datetime.now(timezone.utc).isoformat()`) is always
  set, because the task-check gate needs it without git.
- **Kept** across every transition, and dropped only on the one into `DONE`
  (`fsm_ops_complete` pops it when `next_state == "DONE"`), so a back-edge (`REVIEWING->BUILDING`)
  and a resumed run keep the first base. `build_baseline` (per BUILDING, popped on leaving it)
  and `review_base` (the Review packet's diff base) are separate and unchanged.
- **Read** by `read_proof_base(storage_path)` through `eventlog.read_state` (the DB; no
  `STATE.json` fallback), `None` when absent or unreadable.

`TASK_PROOF {task_id, claimed_at, run_id, checks, floor, warnings}` says a task completion was
proven. `record_task_proof(storage_path, task, run_id, checks, floor, warnings=())` appends it
with `claimed_at` copied from the task row (`checks`: `passed` | `failed` | `none` | `error`;
`floor`: `clean` | `failed` | `off` | `n/a`; anything else raises `ValueError`).
`task_proven(storage_path, task)` is true when the newest `TASK_PROOF` for the task carries its
current `claimed_at`, `checks` is `passed` or `none` and `floor` is not `failed`: a retry or a
human re-open claims the task again (a new `claimed_at`), so the earlier record stops counting,
and a failed proof is run again. It reads the whole event log on each call and is false when
the events cannot be read (the checks then run again); `unproven(storage_path, tasks)` is the
batch form (the tasks `task_proven` would reject, one read of the log, all of them when it cannot
be read). `team`, `team-build` and `goal-loop`
declare a `floor_gate`, so their runs stamp a base on first entry to BUILDING (`team`,
`team-build`) or DRAINING (`goal-loop`); all three also declare a `task_checks` gate. `TASK_PROOF`
is written by the goal-loop drain's task proof ("Task proof in the goal-loop drain") and by the
`task_checks` gate ("Task checks gate").

**Spawn windows and stage writes (`supervisor/spawn_window.py`, `fsm/gates/_proof.py`).** The
floor, scope and reviewer gates must tell who wrote a file: in `team`/`team-build` a planner or
architect routed a feedback file may edit `IMPLEMENTATION_PLAN.md` while the FSM is still in
BUILDING, and a reviewer may write `REVIEW.md` and nothing else. So when a flow's `gates` hold a
`floor_gate`, `scope_gate` or `reviewer_unchanged` (`spawn_window.wants_windows`),
`spawn_window.observe` takes `proof.tree.snapshot` and `proof.tree.head` before and after a
single-path spawn and appends `SPAWN_WINDOW {role, run_id, state, before, after, head_before,
head_after}` to the run's event log (`state.storage_path`, else
`fsm_ops._resolve_storage_path(None, project_root, topic)`; `state` is the FSM state). Two spawns
record it, each passing its role explicitly: `fan_out.run_stage`'s single spawn (the flow's
`role_map[state]`) and the feedback spawn in `orchestrator_stage._resolve_stage_supervised` (the
feedback's `target_agent`, so a builder or planner routed a file inside REVIEWING is not recorded
as the `reviewer` that `terminal_identity._spawn_role` would mint). A fan-out drain records none.
The spawn's result comes back unchanged; an exception from it propagates and no window is written;
outside a git repo, or when a snapshot or the event write fails, there is no window and a log line.
`team` and `team-build` carry a `scope_gate`, and all three flows carry a `floor_gate`, so their
runs record windows (in `goal-loop` only for the feedback spawns of a builder fix round, since a
fan-out drain records none).

What each role may change (`_proof.stage_writes(storage_path, role)`, a predicate over
repo-relative POSIX paths). `<storage>` is the run's storage dir; the *board home*
(`_proof.board_home`) is `pathly/features/<feature>/` for a feature storage dir or anything nested
in one (a goal's `goals/<slug>`), else the storage dir itself (`pathly/plans/<name>/`,
`pathly/project/...`):

| Role | May change |
|---|---|
| every role | `<storage>/feedback/**`; `STATE.json`, `BOARD.json` and `EVENTS.jsonl` anywhere under `pathly/` (the server rewrites them during a run, and a user project may not gitignore them); any `*.tsbuildinfo` |
| `builder` | also `<storage>/VERIFY.md` |
| `reviewer` | also `<storage>/REVIEW.md` |
| `po`, `planner`, `architect`, `designer` (the keys of `fsm_compose_tables._FIX_MODE_ARTIFACT`), `retro` | also any file directly inside `<storage>` or the board home (the plan documents) |

`_proof.explained(project_root, path, now_tree, windows, storage_path)` is true when a window whose
role may write `path` changed it and left it at the blob it has in `now_tree` (`proof.tree.blob`; a
deletion matches a deletion). A window that never touched the path excuses nothing, so a builder's
plan edit made before a planner ran stays the builder's. `_proof.windows_since(storage_path,
since=None, roles=None)` returns the `SPAWN_WINDOW` events with `ts >= since`, oldest first,
comparing parsed times (an event `ts` ends in `Z` and has whole seconds, while `since` stamps are
`isoformat()` with an offset, so `since` is cut to its second), and raises `ValueError` when
`since` is not a time. `_proof.floor_enabled()` reads the `floor.enabled` app setting: on unless it
is `false`, `0` or `off`. `_proof` never imports `supervisor` and imports `db` lazily. `scope_gate`
reads the windows (below).

**Scope gate (`fsm/gates/scope.py`, `_scope_tasks.py`).** Did the builder stay inside what it
declared? The *declared scope* is the union of the backtick paths in the gate's `scope_file`
(optional; read from the storage dir when the file exists) and the `files` of the board tasks
claimed since `build_baseline.started_at` (`task_proof.tasks_claimed_since`, goal-scoped when the
run has a `goal_id`, else `(board, scope)`). Only a task posted before that stamp (its server `ts`)
and not stamped `author_role: builder` counts, so a builder cannot widen its scope by
posting or editing a task and claiming it (`/comms/edit` changes only the text and re-stamps the
row to the editor, so a task a builder edited is stamped `builder` and does not count). An entry
that names a directory covers everything under it, with or without a
trailing `/`. The *changed paths* are `git diff --name-only HEAD` plus every untracked file
(`git status --untracked-files=all`, so a new folder is listed file by file). A path in
`build_baseline.preexisting_dirty` (dirty when BUILDING began; a collapsed `dir/` entry covers the
files under it) is judged by content instead: it counts when its blob now differs from the
`before` tree of the first `SPAWN_WINDOW` since `started_at`, which is where the build began (a
deletion counts too). That is the usual case for the plan: `pathly.auto_commit` is off by default
and nothing commits before BUILDING, so `git status` names the plan files, or all of `pathly/`, in
the baseline. *Exempt*: what the builder stage may write (`_proof.stage_writes(storage, "builder")`:
its feedback files, `VERIFY.md`, the server's exports, any `*.tsbuildinfo`), the flow's
`scope_gate.exempt_prefixes`, and a path `_proof.explained` attributes to a `SPAWN_WINDOW` since
`build_baseline.started_at` (a planner routed `IMPL_QUESTIONS.md` inside BUILDING edits the plan).
The working-tree snapshot is taken only when some window's role may write a remaining path or a
baseline path must be judged. The old blanket `pathly/features/` and `pathly/plans/` exemption is
gone, so in a headless run a builder edit to `USER_STORIES.md` or `IMPLEMENTATION_PLAN.md` fails,
committed or not, and the scope file never covers its own edit (a builder cannot widen its scope by
adding a path to it). `SCOPE_VIOLATION.md` names the paths outside the scope (at most 20, then a
count). It skips (`GATE_SKIPPED`, fail open) with no `build_baseline`, when nothing is declared
(`no_declared_scope`), and when git or the claimed tasks (`tasks_unreadable`) cannot be read; a
truncated baseline is `GATE_DEGRADED`. When the windows (`spawn_windows_unreadable`), the snapshot
(`snapshot_failed`) or the tree diff since the build began (`git_diff_failed`) cannot be read, it
still fails on the changed paths no window could explain (with unreadable windows, those no role
may write, `_proof.any_role_writes`: a code file outside the scope; otherwise those no recorded
window's role may write) and skips only when nothing like that is left. A baseline path is not
judged then. Wired as the last gate of `BUILDING->REVIEWING` in `team` and `team-build`
(`scope_file: IMPLEMENTATION_PLAN.md`, `SCOPE_VIOLATION.md` → builder); not in `goal-loop`.

Limits of the scope gate: a run with no `SPAWN_WINDOW` (an interactive `/pathly` run; only the
supervisor records them) cannot judge a path that was dirty at the baseline, so there an
uncommitted plan edit goes unseen. A task posted without a run token is stamped `none`, as a
human's is, so a builder that drops its token can post a task whose `files` count in a later
BUILDING (the `force_past_gate` limit). And a planner or architect sub-agent that a builder spawns
itself (`team/build.md`'s "Feedback routing after builder", for `IMPL_QUESTIONS.md` or
`DESIGN_QUESTIONS.md`) would write inside the builder's window, so its plan edit would count as the
builder's; in a headless run `RUNNER_CONTRACT_BLOCK` forbids that spawn (see "Review packet"), and
an interactive run records no windows at all.

**Reviewer gate (`fsm/gates/reviewer.py`).** A reviewer judges; it does not edit. The gate finds
when the run last entered REVIEWING (the newest `STATE_TRANSITION` event with `to == "REVIEWING"`),
takes the `SPAWN_WINDOW`s of the `reviewer` role since then (`_proof.windows_since(...,
roles={"reviewer"})`) and reports, per window, a moved `HEAD` ("HEAD moved from a to b (the
reviewer committed)") and every path `proof.tree.changes` shows between its two trees that
`_proof.stage_writes(storage, "reviewer")` does not allow (`<status> <path>`: `REVIEW.md` and the
feedback files are allowed, so anything else is not). Only reviewer windows count: a builder fix
round inside REVIEWING may change code, and a feedback spawn routed to the reviewer
(`REVIEW_INCOMPLETE.md`) is a reviewer window too. On a finding the gate writes
`REVIEWER_CHANGED_FILES.md` listing each change and fails with `GATE_FAILED {gate, transition,
run_ids}`. The flows route that file to `human` (and rank it right after `BLOCKED_ON_HUMAN`), so the
supervisor takes its existing human-checkpoint path: it posts an escalation and parks the run
(`human_checkpoint`). The human decides whether to keep or revert the changes (nothing is reverted),
deletes the file and resumes the run (`POST /runner/resume-parked`); the next reviewer spawn then
runs and is judged on its own window. A window whose `run_id` an earlier `reviewer_unchanged`
`GATE_FAILED` event named is left out, so a window the human already resolved is not reported again
(a window without a `run_id` is named by its event seq). With no reviewer window (an interactive
`/pathly` run records none, and neither does a project outside a git repo) the gate skips
(`GATE_SKIPPED`, `no_reviewer_window`). It also skips, fail open, when the windows cannot be read
(`windows_unreadable`) or git cannot diff a window's trees (`git_diff_failed`); a moved `HEAD` is
read from the window itself, so it still fails. Wired as the last gate of `REVIEWING->TESTING` and
the only gate of `REVIEWING->BUILDING` in `team` and `team-build` (`REVIEWER_CHANGED_FILES.md` →
human); the REVIEWING exit requirement tells the reviewer to change nothing but `REVIEW.md` and
feedback files and not to commit. Limit: with early advance the window's closing snapshot is taken
at the reviewer's `AGENT_DONE`, so a write after its completion report can land outside the window.

**Floor gate (`fsm/gates/floor.py`).** Did the run get green by weakening the bar? The gate takes
a working-tree snapshot now and runs `proof.floor.scan` against the run-wide `proof_base.tree`
(not the stage's `build_baseline`), so a builder fix round that ran inside REVIEWING, TESTING or
RETRO, or after a goal-loop drain, while the FSM stayed in the state, is judged at the next
transition, and a back-edge or a resumed run still sees the whole run. The scan's inputs:

- **allow** is the union of the `floor_allow` lists a human set on the tasks claimed since
  `proof_base.started_at` (`task_proof.tasks_claimed_since`, goal-scoped when the run has a
  `goal_id`, else `(board, scope)`). A category allowed for one task is therefore also excused in a
  fix round or in another task's file at these gates; the per-task proof in the drain uses each
  task's own list.
- **`task-edit`**: a claimed task whose `claimed_text` differs from its live `text` is a finding
  (`task-edit: task <id>: its text was changed after the claim`) unless that task allows
  `task-edit`. A human clears it by allowing the category or by `refreeze` (both in
  `POST /comms/tasks/floor-allow`).
- **`plan-edit`**: `protected` is `_proof.board_home(storage)`. A changed path under it passes when
  `_proof.stage_writes(storage, "builder")` allows it, or when `_proof.explained` finds a
  `SPAWN_WINDOW` since the base whose role may write it and left it at its current content
  (so the reviewer's `REVIEW.md` and a planner's routed plan edit are not blamed on the builder).
  The windows are read once, on the first path that needs them. If they cannot be read, or the
  run recorded none since the base (an interactive `/pathly` run records none), a path some role
  may write is excused and `FLOOR_CHECKED` carries a warning saying which (`spawn windows
  unreadable` or `the run recorded no spawn windows`), once, and only when a path was in fact
  excused; a path no role may write is still a finding. With one window or more, only a window that explains the path excuses it, whichever
  roles the windows belong to.
- **`config_commands`** are the `verify.build`, `verify.test`, `verify.lint` and `verify.smoke`
  settings, so a `Makefile` counts as config when the project builds with make.

A finding writes `FLOOR_FAILURES.md` (it starts "Floor guard: the diff weakens the bar instead of
meeting it", lists each finding, says a human can allow a category for a claimed task through
`POST /comms/tasks/floor-allow` or turn the guard off with the `floor.enabled` setting, and ends
with the fix: undo the weakening and fix the cause) and fails with `GATE_FAILED {gate, transition,
findings, count}`; the flows route the file to `builder`. `FLOOR_CHECKED {warnings}` is appended
whenever a scan ran, pass or fail (the Review packet's supervisor notes read it). It skips
(`GATE_SKIPPED` with a reason, fail open) when `floor.enabled` is `false`, `0` or `off`
(`floor_disabled`), the run has no `proof_base` (`no_proof_base`), the base has no tree
(`no_snapshot`, not a git repo top), the snapshot now fails (`snapshot_failed`), the claimed tasks
cannot be read (`tasks_unreadable`), an unexpected error stops the scan (`scan_failed`), or git
could not diff and nothing else was found (`scan_incomplete`; the warning stays in `FLOOR_CHECKED`).

Wired in `core/flows/team.flow.yaml` and `team-build.flow.yaml` at `BUILDING->REVIEWING`
(after `command_gate`, before `scope_gate`, which stays last), `REVIEWING->TESTING` (before
`reviewer_unchanged`, which stays last), `TESTING->RETRO` and the wildcard `->DONE` (it covers an
`INCOMPLETE_TASKS` builder fix round inside RETRO, which no other floor gate sees), and in
`goal-loop.flow.yaml` at `DRAINING->DONE` after the two `command_gate`s: a builder fix round after
the drain (`BUILD_FAILURES`, `TEST_FAILURES` or `INCOMPLETE_TASKS` routed to `builder`) is a plain
feedback spawn, not a `sched-<id>#<n>` task spawn, so only this gate sees it, and it also sees a
weakening an earlier failed task attempt left in place. Each flow routes `FLOOR_FAILURES` to
`builder`. `fsm_compose_responses._exit_requirement` tells the stage's agent the diff is scanned.

Limits: the guard raises the cost of weakening the bar, it does not make it impossible (a builder
with a shell can reach the DB and the git object store). An interactive `/pathly` run records no
`SPAWN_WINDOW`, so there the gate cannot tell which role wrote a plan file: the reviewer's
`REVIEW.md` or a planner's edit is excused (with the `FLOOR_CHECKED` warning above) and so is a
plan edit by the builder, which goes unseen, as for `scope_gate`. Every other category is judged
as in a supervised run. A goal-loop drain records no window either. Its tasks' own plan edits are
caught by the per-task proof (`protected=[board home]`), which judges each attempt on its own diff,
so a plan file a role may write that a failed attempt edited and the retry left in place goes
unseen at the join (a path no role may write is still a finding there). A test or tester edit in
TESTING that trips the floor goes to the builder, who did not make it.

**Task checks gate (`fsm/gates/task_checks.py`).** In `team` and `team-build` the builder claims a
board task and completes it itself (`POST /comms/tasks/complete`), so the supervisor never sees
per-task success, and a builder fix round (`INCOMPLETE_TASKS` routed to it in REVIEWING, RETRO or
after a goal-loop drain) completes tasks the same way. The gate runs at every join such a
completion can precede and executes the task's `check` block, so a self-reported pass does not
count:

- **Which tasks:** `task_proof.tasks_completed_since` from `proof_base.started_at` (goal-scoped when
  the run has a `goal_id`, else `(board, scope)`), minus every task for which
  `_proof_record.task_proven` is true (`_proof_record.unproven` does this for the whole list with
  one read of the event log). So each completion is checked once: a task an earlier gate
  or the goal-loop drain proved is not run again, a task whose newest `TASK_PROOF` failed is run
  again, and so is a task claimed again since (a new `claimed_at`). A task completed before the
  base is not touched.
- **Which text:** `claimed_text`, the text frozen at the claim (`text` for a task claimed before
  that column existed), so editing the live task text changes nothing; the report says so.
- **How:** `proof.checks.run_task_checks` (`checks_in` then `run_checks`) in the project root with
  the `verify.timeout_seconds` timeout, the same runner as `command_gate`. A `ParseError` fails and
  the report quotes the parser's message (`TASK_PROOF checks: "error"`); a task without a block
  passes (`checks: "none"`). Every task run writes `TASK_PROOF` with `run_id` `gate:<transition>`
  and `floor: "n/a"` (the floor gate judges the diff).
- **Failure:** `TASK_CHECK_FAILURES.md`, one `## Task <id>: <first line>` section per failing task
  (at most 8, each clipped to 4000 characters, then a count) and a note that the supervisor ran the
  frozen text; `GATE_FAILED {gate, transition, tasks, count}`. The flows route it to `builder`. A
  human fixes a broken check by editing the task text and re-freezing it with
  `POST /comms/tasks/floor-allow` (`refreeze: true`); an agent cannot. So the file ends with an
  action line per kind of failure: a failing check is to be fixed in the code, while a block that
  cannot be read (`error`) sends the builder to write `HUMAN_QUESTIONS.md` and stop, since neither
  a code change nor a text edit can help it.
- **Skips** (`GATE_SKIPPED`, fail open): the run has no `proof_base` (`no_proof_base`), or the
  completed tasks cannot be read, including a base whose `started_at` is not a time
  (`tasks_unreadable`). It needs no git: `started_at` is set even outside a repo.

Wired in `core/flows/team.flow.yaml` and `team-build.flow.yaml` at `BUILDING->REVIEWING` (after
`floor_gate`, before `scope_gate`, which stays last), `REVIEWING->TESTING` (after `floor_gate`,
before `reviewer_unchanged`, which stays last) and the wildcard `->DONE` (last), and in
`goal-loop.flow.yaml` at `DRAINING->DONE` (last). Each flow routes `TASK_CHECK_FAILURES` to
`builder`. `fsm_compose_responses._exit_requirement` tells the stage's agent that each completed
task's check block is run by the supervisor. Limit: a regression after a task's checks passed is
left to `command_gate test`, which runs the whole suite at `TESTING->RETRO` and `DRAINING->DONE`.

**Review packet (`fsm_compose_review.py`) — the reviewer's view.** A reviewer judges a diff
against a task, not against the builder's account of its work. The reviewer has no Bash, so it
could not run the `git diff HEAD~1 HEAD` that `team/review.md` told it to, and its prompt carried the
builder's `AGENT_DONE` summaries (the pipeline history block). `build_prompt` now puts
`review_packet(storage_path, project_root, board, board_scope, goal_id)` in place of that block
whenever the stage's role is `reviewer` (`team/review` maps to it in `_SKILL_AGENT_ROLE`); every
other role keeps the history block. The diff's base lives in STATE: `next_action` adds `tree`
(`proof.tree.snapshot(project_root)`; left out when git cannot snapshot) to the `build_baseline` it
stamps on entering BUILDING, and `complete_stage` copies `{tree, started_at}` into `review_base` on
every transition out of BUILDING, overwriting the last build's (a build with no tree leaves none,
not a stale one). `review_base` then survives REVIEWING, a builder fix round inside it and the later
states. The packet is a `## Review packet` section:

- `### The task` — `claimed_text` (else `text`) of the tasks claimed since `review_base.started_at`
  (`task_proof.tasks_claimed_since`, goal-scoped when the run has a `goal_id`, else `(board, scope)`),
  at most 16 KiB;
- `### The diff` — `proof.tree.diff_text(root, review_base.tree, <snapshot now>,
  exclude=["pathly/"], unified=3)`: everything the last build changed outside `pathly/`, in a code
  fence one backtick longer than any run inside it (a context line `` ``` `` from a markdown file
  would close a three-backtick fence), clipped head and tail to 48 KiB in all, since the prompt is
  one argv string and Linux caps an argument at 128 KiB;
- `### Supervisor notes` — per claimed task its latest `TASK_PROOF` event since the build began
  (checks passed, failed, or "no check block: review its acceptance by reading the code") and the
  warnings of the latest `FLOOR_CHECKED` event (at most 20), else `none recorded`. `TASK_PROOF` is
  written by the `task_checks` gate and the goal-loop drain's task proof, `FLOOR_CHECKED` by the
  floor gate.

With no `review_base` (the FSM never stamped BUILDING for the run, as in an interactive session,
or git is missing) or no snapshot now, it returns a short section saying so, and `team/review.md`'s
interactive branch applies: the stage orchestrator, which has Bash, runs `git diff HEAD` itself.
Otherwise the orchestrator pastes `### The task` and `### The diff` verbatim into the reviewer
sub-agent's prompt and hydrates the task's `context_refs` itself; it never passes the builder's
report or `VERIFY.md`. It never raises: a packet that cannot be built is that short section.

`RUNNER_CONTRACT_BLOCK` gained one sentence: in any headless stage, never spawn another Pathly role
(planner, architect, po, designer, builder) to resolve a feedback file; write the file and stop,
and the supervisor routes it. A sub-agent spawned that way has no `SPAWN_WINDOW` of its own, so its
plan edit would be blamed on the stage's role. The sub-agent fixers in `team/build.md` and
`team/review.md` stay for interactive `/pathly`; the flows' `feedback_routing` does the routing.

Limits: the packet changes the prompt, and the reviewer's CLI session is fresh too ("Visible
runner" below). The retry-ladder block that
`build_prompt_for_agent` adds for a role routed a feedback file (`REVIEW_INCOMPLETE.md` sends one to
the reviewer) still lists the `AGENT_DONE` summaries. The diff covers the last build only: after a
`REVIEWING->BUILDING` round it is that round's changes, not the feature's.

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
feedback file `target_agent == "human"` named. `human_escalation.post_human_escalation` posts an answerable
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

## Run guard rails — base smoke and iteration budget (build-proof)

**Base smoke (`supervisor/base_smoke.py`).** A run that starts on a red base spends its budget on
a failure it did not cause and blames the builder for it. `api.start_run(..., smoke_base=True)`
calls `base_smoke.check_base(state, broadcast_fn)` inside `_run_and_finalize`, before `_loop`:

- It applies only to a flow whose `gates` include a `command_gate` with `command_key: build`
  (`team`, `team-build`, `goal-loop`; read with `fan_out.load_flow_config`). Any other flow, and
  the `single` executor, board runs and consultations, are not smoked.
- The command is the app setting `verify.smoke`, else `verify.build`; with neither the check is
  skipped, as `command_gate` is. It runs through `proof/command.py::run_command` in
  `state.project_root`, with the `verify.timeout_seconds` timeout (default 600) and
  `PATHLY_VERIFY_GATE=1`.
- Exit 0 lets the run go on. A non-zero exit, a timeout or a command that cannot run posts a
  `to_agent='human'` escalation (`human_escalation.post_human_escalation`: the command, the exit
  code or timeout, the clipped output, and `POST /runner/resume-parked {"topic": …}`), sets
  `error_kind = "base_red"`, parks the run and broadcasts `RUNNER_PARKED {kind: "base_red"}`.
  Nothing was spawned, and `_run_and_finalize` still calls `on_done` with `status: parked`,
  `error: base_red`. The escalation is server-written (`system` stamp), so `fsm_human_gate` does
  not block the resumed run on it.
- It fails open: if the check itself raises, the run goes on and a warning is logged.
- `resume_parked_run` passes `smoke_base=(prior.error_kind == "base_red")`: after a `base_red` park
  the smoke runs again (still red, it parks again under a new run id); after a `human_checkpoint`
  park it does not, so red work in progress on that run does not re-park it.

**Iteration budget (`supervisor/run_budget.py`).** `run_budget.refresh(state)` is called at the top
of `orchestrator_stage._resolve_stage_supervised`, which runs after every stage, so the budget
follows the DAG as decomposition adds tasks. For a run with a `goal_id` it sets
`state.max_iterations` to the larger of its current value and
`count_tasks_for_goal × task_retry.resolve_max_attempts() × (MAX_FEEDBACK_ROUNDS + 1)` (under
`registry._lock`): a goal with 5 tasks and `goal.task_max_attempts` 3 gets `5 × 3 × 4 = 60`, one
task gets 12, no tasks yet leaves the caller's 10. It logs when it raises the cap, never lowers
it (deleting tasks does not cut a running run short) and never raises. A run without a `goal_id`
keeps the caller's `max_iterations`. `iterations` counts the loop's stage passes (a fan-out drain
is one). The cost cap and the `cap_exceeded` handling are unchanged, and `resume_parked_run`
carries the raised cap over.

## Goal cost cap (`supervisor/cost_cap.py`)

The FSM loop (`orchestrator.py`) refuses to spawn a new stage once `cost_usd_so_far >=
max_cost_usd` — but that check lives entirely inside `orchestrator.py`; the DAG/loop
executor's `scheduler.py` frontier loop has no equivalent, so a goal's task-DAG could run
to any cost. `cost_cap.py` closes this WITHOUT touching `scheduler.py` (frozen at its
400-line ratchet ceiling): `CostCapTracker.wrap(spawn_fn)` returns a spawn function with
the same signature that accumulates each task's real `cost_usd` as it becomes known, and
`supervisor/drain.py::drain_frontier` folds `tracker.exceeded()` into the SAME `abort_check`
hook `scheduler_loop` already polls at the top of its frontier loop before scheduling anything
new — no new extension point, no scheduler changes. Owning it in the shared drain is what makes
the cap apply to every frontier drain by construction rather than by each caller remembering it.

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
what Studio exports. When the `TERMINAL_SPAWN` payload carries a `run_token` it also sets
`PATHLY_RUN_TOKEN` (exactly as received; absent token = no key), same as Studio's `buildSpawnEnv`.

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
(`retry_count == 0`, the default) has no ladder.** Every existing caller that never threads
the new parameter, and every golden snapshot, is unaffected; but a headless run never climbs
`retry_count`, so it would never have shown the file at all. So a round-1 prompt for any role
outside `_FIX_MODE_ARTIFACT` (typically builder, reviewer, tester) that is given a
`feedback_file` carries a `## Feedback to resolve` block
(`fsm_compose_feedback.feedback_block`), in the ladder's place, right after the
`## Current task` context: the file's path (`<storage>/feedback/<file>`, from
`fsm_compose_feedback.feedback_path`, which the Fix mode block uses too), a sentence saying the
gate or reviewer wrote it and that the cause, not the file, is to be fixed, and the file's text
in a code fence one backtick longer than any run of backticks in it (these files quote failing
command output). The text is `read_feedback`'s: stripped and clipped to 4000 characters, the
same read the ladder uses; a file longer than that gets a closing line saying the text is its
first 4000 characters and naming the full file; a file that is missing, not text or empty gets a
block that still names it and says its text could not be read. From round 2 the ladder already
carries the text, so the block is not added a second time. A call with
no `feedback_file`, and the four Fix mode roles (po, planner, architect, designer: Fix mode tells
them to read the file), are byte-identical to before. All three callers (`fsm_ops_complete` twice,
`fsm_ops.next_action` once) get it through `build_prompt_for_agent`.

**The root-cause guide rides on a builder feedback prompt.** The same function appends
`fragments/root-cause-debug.md` (`## Root-cause debugging`: read every failure, reproduce it with
the exact command, isolate the cause, fix it without weakening a check, prove it; stop after two
failed fixes of the same error) when `agent_name == "builder"` and a `feedback_file` is given, whatever
`retry_count` says. A headless run never writes `retry_count_by_key` to STATE, so the ladder above
never climbs there; and a builder handed a feedback file is, by definition, on a second attempt at
its stage. The guide comes after the feedback: the round-1 `## Feedback to resolve` block, or the ladder's
current feedback from round 2, so its first step ("Read every failure above") has something above
it. It is read at call time by `skills/compose_resources.root_cause_guide()` (empty
and logged when the file is unreadable), is not in `composition.yaml` (so no golden snapshot
moves), and does not contain the words "Retry attempt" that `tests/fsm_flows/test_retry_ladder.py`
uses to tell attempts apart. A builder prompt with no feedback file, and every other role, gets no
guide (a reviewer or tester given a feedback file gets only the feedback block). The DAG-task twin
is in "Phase 1: per-task retry" below.

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
  returns it, so the NEXT attempt's `task` dict carries it for free). Up to 4000 characters are
  kept (`retry_task`, `fail_task`, the two `reason` lines in `scheduler.py` and the retry prompt
  block), so a task proof's report survives into the next prompt.
- **Escalate** (attempt `>= goal.task_max_attempts`): the original behavior, delayed until
  retries are exhausted — `fail_task`'s cascade-to-blocked, plus a board `escalation` message
  (mirrors `goal_verify.post_gate_failure_escalation`) so a human/agent sees it instead of a
  silent DB-only cascade.

**`build_retry_context`** appends a retry-ladder block to a retried task's prompt from the
second attempt on — mirrors `fsm_compose._retry_ladder_block`'s "what varies by ATTEMPT, not
just who owns it": the attempt number and the previous failure's reason, so a retry doesn't
repeat the identical blind prompt. A first attempt (`attempts == 0`) is unaffected — byte-
identical to before this feature. The `root-cause-debug` guide (see "Retry ladder" above) is
appended after the failure block, so a retried task prompt ends with the failure it was told to
read and then the method for reading it.

**Dependency results (`task_dependencies.py`, `db/queries/task_results.py`).** A DAG task used to
see only its own text. `build_task_prompt` now puts `## Results of the tasks this one depends on`
after the task body and before the runner contract: one `### <first line of the dependency's
text>` heading per **direct** `depends_on` id (not transitive ones), in `depends_on` order,
followed by that dependency's latest result or `(no result recorded)`. The result is the
`summary` of the newest `AGENT_DONE` event whose payload `run_id` matches `sched-<id>#%`
(`latest_task_summaries`: one fixed `json_extract(payload, '$.run_id') LIKE ?` query per id, newest
`seq` first, so a retried dependency's last attempt wins). `supervisor/terminal.py` substitutes
`<run_id>` for the spawn's run id, so a task agent's `AGENT_DONE` carries it. No result column and
no migration. Each summary is clipped to 2000 characters and the whole block to 8000 (the prompt
is one argv string); a task without `depends_on`, or one whose results cannot be read, gets no
block and an unchanged prompt. `development/execute-task` asks the agent for a completion summary
that says what was built, which files changed, any shortcut and what a later task needs to know.
`fsm_events` has no index on `run_id`, so each lookup scans it newest-first until a match (the
whole table for a dependency with no result).

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

## Task proof in the goal-loop drain (`supervisor/task_proof.py`, build-proof)

A DAG task used to pass on its own `AGENT_DONE` outcome. `drain.drain_frontier` now builds its
spawn as `tracker.wrap(task_proof.wrap(spawn_fn))`, so every task of a fan-out drain (the
`goal-loop` flow's `DRAINING`) is proven after it reports success. Any run id that is not
`sched-<task_id>#<n>` passes straight through, and `spawn_fn=None` resolves
`supervisor._run_stage_via_terminal` each time the wrapper is called (a test that patches it
still works). A project root that is not a directory is not proven.

1. **Before the spawn:** read the task (`task_proof.get_task`), register it in a lock-guarded
   in-flight registry with its declared `files`, and `proof.tree.snapshot` the project root.
2. **The spawn runs.** If it raised, or `scheduler._outcome_is_failure(outcome)` already holds,
   the result is returned as is: nothing is proven and no `TASK_PROOF` is written.
3. **After it returns**, a second snapshot, then in order:
   - *Floor guard* (skipped when `floor.enabled` is off or either snapshot is `None`):
     `proof.floor.scan(root, before, after, allow=<the task's floor_allow>, protected=[board
     home], may_change=<builder stage writes>, config_commands=<verify.build/test/smoke>)`.
     The paths declared in the `files` of every task whose window overlapped this one are left
     out (a directory covers its subtree): two windows overlap when both were registered, in
     the same project root, at the same time. A path nobody declared counts against every
     overlapping task.
   - *Task text:* a `claimed_text` that differs from the live `text` is a `task-edit` finding,
     unless a human allowed `task-edit` for the task.
   - *Checks:* `proof.checks.run_task_checks` (the blocks of `claimed_text or text`, run with
     `run_checks`) in the project root (`verify.timeout_seconds`, default 600), the function the
     `task_checks` gate uses too. A `ParseError` is a failure that quotes the error; no block is
     not a failure.
4. **Record** `TASK_PROOF {task_id, claimed_at, run_id, checks, floor, warnings}` in the run's
   storage dir (`_proof_record.record_task_proof`): `checks` is `passed`, `failed`, `none` or
   `error` (an unreadable block), `floor` is `off` when the scan was skipped, `failed` on any
   floor or `task-edit` finding, else `clean`. The join's `task_checks` gate does not
   run a proven task's checks again.

On any finding or failing check the outcome comes back as a copy with `outcome: "failed"` and an
`error` of one short heading per failing part (`## Floor guard`, `## Task text`, `## Checks`)
and its report, in at most 4000 characters (the checks part gets what the others leave, head and
tail). `scheduler_loop` sees a failure and `task_retry.resolve_task_failure` retries it (the
report is the next prompt's failure block, with the root-cause guide, and the prompt shows the
text frozen at the claim: `build_task_prompt` uses `claimed_text` before `text`) or, past
`goal.task_max_attempts`, fails it and posts the escalation. The copy keeps `cost_usd`, so the
cost tracker outside the wrapper still counts a failed attempt.

Fails open on what the proof cannot do: no git (the floor is `off`, the checks still run), an
unreadable task, or an unexpected error is logged and the outcome returned unchanged. Limits:
each attempt is judged on its own diff, so a weakening an earlier failed attempt left in place
is not seen again (the retry prompt carries the finding, and the floor gate at the goal-loop
join re-checks the whole run); lane-parallel tasks share one working tree, so an
undeclared path is blamed on every overlapping task (`WorktreeIsolation` is still a stub); and
the checks run in the project root with the server's account, as a builder's commands do.

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

**Resolved (was "flagged, not fixed"): `DESIGN_QUESTIONS.md` → `architect` in every flow.** The
filename used to carry two self-consistent meanings: `team`/`test` treated it as the builder's
`[ARCH]`-tagged technical blocker (→ architect), while `team-build` and the three consultation
flows treated it as "questions for the designer" (→ designer), alongside their role-symmetric
`ARCH_QUESTION`/`PO_QUESTIONS`/`IMPL_QUESTIONS`. The writer side has only ONE contract, which is
what settled it: `team/build.md` and `development/build.md` both write the file `[ARCH]`-tagged,
`team/build.md`'s own body spawns `architect` for it, and `utilities/meet.md` tells the user it
"routes to architect" no matter which flow the feature is on — so 4 of 6 flows silently broke a
documented promise. Now uniform, with `DESIGN_FEEDBACK.md → designer` added to the consultation
flows so routing the file away does not strand the designer role (`team`/`team-build` already had
it). `fragments/feedback-protocol.md`'s hedged "→ designer/architect" line is corrected to match,
and `tests/fsm_flows/test_design_questions_routing.py` pins the uniformity — including a guard
that the parametrized check has not degraded to all-skips, and a check that every flow with a
designer stage still has an inbound file for them.

## The small flows got the 3-tier retry ladder (`debug`, `quick-fix`)

`_resolve_feedback_target` returns the BASE agent unconditionally when a flow has no
`escalation_routing`, so `debug` and `quick-fix` — the only two failure-looping flows without
one — routed a persistently failing fix back to `builder` forever: no round-3 hand-off, no
round-4 human backstop, the run just burned its iteration/cost caps. Both now carry the
ladder the team flows have, escalating to **`scout`** at round 3: when the FIX keeps failing,
the suspect is the diagnosis (debug's INVESTIGATING) or the scope (quick-fix's SCOPING) above
it — the same "blame the upstream cause, not the code" move `team.flow.yaml` makes with
`REVIEW_FAILURES → planner`. Verified against the real `route_feedback`:
builder → builder → scout → human.

## Feedback-file reachability — a flow must route what it can produce

`route_feedback` (`fsm/engine_transitions.py`) ends with a catch-all: any `.md` in
`feedback/` that no `feedback_routing` key matches returns `target_agent: "human"` with
*"Unrecognized feedback file: X. Review and resolve manually."* That is a safety **net**, not
a destination — reaching it means the flow stops and waits on a person instead of routing to
the role that can fix the problem, stalling a run that could have fixed itself. Two flows
were landing there on ordinary paths, both found by diffing what a flow's own skills WRITE
against what it ROUTES:

- **`debug.flow.yaml` never routed `VERIFY_FAILURES.md`** — the file its own VERIFYING skill
  (`debug/verify.md`) writes whenever verification fails, i.e. the flow's primary failure
  path. So a failed debug verification escalated to a human instead of looping
  VERIFYING → FIXING. Now `VERIFY_FAILURES: builder`,
  mirroring `quick-fix.flow.yaml`'s `TEST_FAILURES: builder` on the same VERIFYING→FIXING edge.
- **The three consultation flows never routed `ARCH_FEEDBACK.md`** — the canonical `[ARCH]`
  file in `fragments/feedback-protocol.md`, which `utilities/meet.md` writes into any feature
  regardless of flow under the caption "routes to architect". Now `ARCH_FEEDBACK: architect`.

`tests/fsm_flows/test_feedback_file_reachability.py` drives the real `route_feedback` against
the real packaged YAMLs for both, plus a guard that the catch-all still fires for a genuinely
unknown filename (so the assertions cannot pass by the fallback being removed).

**Why this is a test and not a CI gate.** The obvious generalization — "every feedback file a
flow's skills mention must be routed" — is regex-only and cannot tell a WRITE from a READ. It
false-positives on `test.flow.yaml`/`INCOMPLETE_TASKS.md`, which `team/build.md` only *reads*
("the completeness gate sent you back to finish…"): the writer is the `require_tasks_done`
gate, and `test.flow.yaml` has no `gates:` block at all, so that file can never appear there.
Adding a routing key for it would be unreachable noise. Checked by hand across all nine flows;
only the two above were real.

## FSM/DAG convergence — Phase 2/3 were REVERTED: one engine, one authority

Phase 2 shipped `supervisor/compiled_flow.py`, a second executor that walked a flow's states
directly in Python — no `fsm_state` row, no `/next_action`/`/complete_stage` round-trip — and
Phase 3 opted `quick-fix`/`debug` into it. Both are **removed**. The record of why, so nobody
rebuilds it:

- **It bought almost nothing.** The two calls it skipped are a localhost HTTP round-trip and a
  SQLite write — roughly 2 ms against a stage whose agent runs for minutes. The expensive part
  of a spawn (`TERMINAL_SPAWN` over SSE, waiting on `/runner/terminal/result`) went through
  HTTP either way.
- **It cost real money.** It passed `session=None` on every spawn where `orchestrator._loop`
  reuses a session across same-adapter stages, so every stage re-read its context. It saved
  microseconds of bookkeeping and spent tokens.
- **It broke the state-one-authority rule**, and that rule pays for itself. With no DB row the
  run was invisible to `pathly-status`, had no `STATE_TRANSITION` audit trail, could not
  park/resume, and silently disabled `escalation_routing` (whose tiers climb off
  `STATE.json`'s `retry_count_by_key`). Two of those needed their own patches — a whole second
  CLI discovery source and an in-memory retry dict — before anyone noticed they shared one
  cause.
- **It made the problem it was meant to solve worse.** The convergence goal was two engines
  down to one; this added a third alongside `orchestrator._loop` and `scheduler_loop`.
- **The obstacle that justified it was three lines.** The stated reason for not compiling
  flows into DAG tasks was that `fix/build.md`/`debug/*.md` carry literal `pathly-fsm-call
  complete-stage` instructions, neutralized only by the runner-contract block `build_prompt`
  appends (`fsm_compose.py`, the `### Runner contract` f-string). `scheduler.py`'s DAG prompt
  path could append the same constant. A shared string was routed around with ~1300 lines.

**The design going forward: one authority (the DB) and one engine (the FSM).** A new execution
path must persist its state in `fsm_state` like every other caller — that is what makes a run
resumable, observable, auditable and CLI-visible, and those are not optional extras. If one
engine is still the goal, start from sharing the runner-contract constant with the DAG prompt
path, not from a second executor.

**Parallelism is NOT the cost of one engine** (an earlier note here said it might be — that was
wrong). A classic FSM holds one state, but the thing Pathly needs is not concurrent *states*
(Harel orthogonal regions, where `current` becomes a set); it is one state that spawns N agents
and joins — `BUILDING` fans out over the ready tasks, waits for all, then transitions once.
`fsm_state.current` stays the scalar `"BUILDING"` throughout, so the DB stays the authority and
the gates keep running exactly where they do now, at the transition.

Most of the machinery for that is already built and merely pinned off: `scheduler.py` has real
thread fan-out with a completion queue, `isolation.py` has `LaneIsolation`
(`max_concurrency = len(ready_lanes)`), `file_claims.py` guards collisions, `depends_on` is the
graph, and `task_retry.py` handles per-task retry and deadlocks. **`LaneIsolation` is
instantiated nowhere in production** — every caller uses `SerialIsolation`, whose only job is to
force `max_concurrency` to 1, and whose own docstring says flipping to parallel is just swapping
it back.

So the real gap is architectural, not capability: `scheduler_loop` is wired as a rival ENGINE
(`goal_executor._run_loop`, a peer of `orchestrator._loop`) instead of as the fan-out executor
*inside* a state. Moving it inside is what turns two engines into one. Design, phasing and the
honest risk list: [pathly/features/.archive/fsm-fan-out/SPEC.md](../../pathly/features/.archive/fsm-fan-out/SPEC.md).
Its Phase A — sharing the `### Runner contract` constant between `build_prompt` and
`scheduler.py`'s DAG prompt path — is the same three-line fix the reverted compiled executor was
built to route around. **Phase A has landed** (below); B and C follow it.

## fsm-fan-out Phase A — ONE runner contract, shared by both prompt paths

`fsm_compose.RUNNER_CONTRACT_BLOCK` is now the single definition of the *"you are headless, the
supervisor owns the FSM, never call `complete-stage`"* block, and **both** headless prompt paths
append it:

| Path | Before | Now |
|---|---|---|
| `fsm_compose.build_prompt` (FSM stages) | inline f-string in its `context` | appends the constant — output **byte-identical** |
| `supervisor/scheduler.py` `_worker` (DAG tasks) | **appended nothing** | appends the same constant |

The scheduler side is the real change: a loop-executor task agent was the one headless agent
never told the supervisor drives the flow, and `development/execute-task` carries no such
instruction of its own. That is inert while `scheduler_loop` runs as its own engine — but under
Phase C those agents run INSIDE an FSM stage, where a self-driven transition is a double-advance
or the 404 respawn loop `tests/runner_supervisor/test_runner_contract.py` was written for. It is
appended AFTER `_worker`'s compose try/except, so the raw-task-text fallback — the path where the
agent has the least guidance — is not the one path that loses it.

This is the "three-line fix" the reverted compiled executor spent ~1300 lines routing around
(above). The `build_prompt` side is a pure extraction: the lifted f-string interpolated nothing,
and the composed `context` is byte-for-byte what it was. `compose_skill` is untouched, so the
golden snapshots in `tests/snapshots/` do **not** move. Pinned by
`tests/fsm_flows/test_runner_contract_shared.py` — present in both paths, exactly once in each
(a second copy is the obvious regression), and present on the composition-failure fallback.

Shipped inside the ratchet: `scheduler.py` 425 → 432 against its frozen 433.

## fsm-fan-out Phase B — the `parallel_states` flow-YAML key (inert)

A state opts into fan-out — one FSM state draining its ready tasks, then joining — by naming
itself in an optional `parallel_states` block. **Absent means today's exact behavior** (one spawn
per stage), so no existing flow changes:

```yaml
parallel_states:
  BUILDING:
    max_workers: 4        # optional; default = the isolation's own answer
    isolation: lane       # optional; lane | serial | worktree
```

`fsm/state.py::_validate_parallel_states` (called from `validate_flow_dict`, so
`pathly-validate-flow` and every caller get it) enforces three **errors** — a key that is not a
declared state, a `max_workers` that is not a positive int, an `isolation` outside
`_ISOLATION_VOCAB` — and one **warning**: `worktree` is legal vocabulary but `WorktreeIsolation`
is still a stub that raises `NotImplementedError`. `max_workers` rejects `bool` explicitly, since
`isinstance(True, int)` is true and `max_workers: true` is a typo, not a cap of 1. A bodiless
`BUILDING:` (YAML `None`) is a legal "all defaults" entry.

**Nothing read the key at Phase B** — Phase C is what branches on it, and no packaged flow
declared it, which made that phase inert by construction. Since **Phase E, exactly one flow opts
in**: `goal-loop`, which IS `executor: loop`. `tests/fsm_flows/test_parallel_states_schema.py`
pins the schema rules and that `goal-loop` is the ONLY opted-in flow, so opting another in stays
a deliberate, test-visible decision.

## fsm-fan-out Phase C — the fan-out moves INSIDE the FSM (still serial)

The architectural change: `scheduler_loop` stops being a rival ENGINE and becomes the fan-out
executor **of a state**. `orchestrator._loop` no longer calls `_run_stage_via_terminal` directly —
both its spawn call sites now go through `supervisor/fan_out.py::run_stage`, the ONE call site for
executing a stage:

```
  next_action() -> current_state = "BUILDING"
        |
        +- NOT parallel --> _run_stage_via_terminal      (today, unchanged)
        |
        +- parallel ------> scheduler_loop(...)          <- the fan-out
        |                     returns when the frontier is drained
        v
  run_gates(BUILDING -> REVIEWING)   <- the JOIN. ONE gate run, after every worker
        |                               finished. fan_out does NOT call gates.
        v
  complete_stage() -> write_state("REVIEWING")
```

`fsm_state.current` stays the scalar `"BUILDING"` for the whole drain, so `write_state`'s legality
check, the `STATE.json` export, the `pathly-*` CLI and Studio's flow editor are all untouched. The
FSM keeps flow, states, gates and transitions; the scheduler owns only "run these N ready tasks".

**Behaviour is byte-identical, deliberately.** `_resolve_isolation` pins `SerialIsolation`
*regardless* of the YAML's `isolation:` value — an `isolation: lane` entry is honoured as intent
and **logged**, not obeyed — so a parallel state still drains one task at a time. Turning
concurrency on is Phase D's single swap, gated on a real Phase-C run and on tasks declaring
accurate file footprints (`file_claims.py` only guards collisions it can see).

Fan-out semantics, as implemented:

| Concern | Behaviour |
|---|---|
| Frontier | `get_ready_tasks(board="feature", scope=state.topic, goal_id=state.goal_id or None)` — the SAME `(board, scope)` pair `orchestrator_stage.py` posts to `complete_stage`, so the fan-out and `require_tasks_done` cannot disagree about which tasks are this stage's |
| Isolation | `SerialIsolation()` always (Phase C); the requested strategy is logged |
| Spawn | `_run_stage_via_terminal` wrapped by `cost_cap.CostCapTracker.wrap`, exactly as `goal_executor._run_loop` does; `session=None`, `autonomy` threaded from the stage |
| Abort | the FSM's own `_abort_flag` **or** `tracker.exceeded()`, folded into `scheduler_loop`'s existing `abort_check` |
| Merge | summed `cost_usd` (from the tracker's new `total` property — never re-summed), `session_id=None`, `outcome="failed"` if any task escalated **or** deadlocked |
| Gates | not called here — `_loop` runs them at the transition, and that is the join |

`session_id` is `None` **by construction**: a fan-out cannot carry one CLI session across N
agents, and threading one would corrupt context the moment Phase D lets two workers run at once.
A failed task does not hard-fail the stage — `_loop` surfaces the self-reported failure as a
`RUNNER_WARNING` and `require_tasks_done` blocks the transition, which is the documented join
semantics ("frontier drained, these escalated").

**The `orchestrator.py` edit had to be net-negative** — it was frozen at 427 by
`scripts/check_file_size.py`, where even an added import fails CI. Two extractions paid for the
fan-out call sites: `supervisor/fan_out.py` (new) and `supervisor/orchestrator_session.py` (new,
the ~35-line session-continuity block lifted verbatim — same reuse predicate, same `degraded`
flag, same `SESSION` event). Result: **427 -> 399**, so the ratchet clicked and `orchestrator.py`
dropped OUT of `file_size_baseline.txt` entirely — it can now never grow past 400 again.

**Production behaviour was provably unchanged at Phase C**: no packaged flow declared
`parallel_states`, so no run could take the fan-out branch at all. (Phase E added the first and
only opt-in, `goal-loop`.) `tests/runner_supervisor/test_fan_out.py` asserts that, alongside the
drain, the serial pin, the failure/join semantics, and abort mid-drain.

## fsm-fan-out C.5 — `lane` and `files` had NO write path (Phase D was not one line)

Phase D was specified as a one-line isolation swap. Checking its stated precondition —
*"tasks in the target flow declare accurate file footprints"* — found the precondition
**unsatisfiable**, and the reason is worth keeping:

| Column | Schema | Writer, before C.5 |
|---|---|---|
| `comms_messages.lane` | `migrations_incremental.py` | **none anywhere** — `post_message` did not even accept it |
| `comms_messages.files` | `migrations_incremental.py` | `post_message` accepted it, but `/comms/post` — an agent's ONLY write path — never forwarded it, and no skill emitted it |

So every task reached the scheduler with `lane=NULL, files=NULL`, and `scheduler.py`'s
`lane = task.get("lane") or task_id` fallback gave **every task its own lane**. That makes
`LaneIsolation.max_concurrency = max(1, len(ready_lanes))` equal to *the number of ready
tasks*: the swap would have started N agents at once, on one shared working tree, with the
one-worker-per-lane rule vacuously satisfied and nothing checking footprints. Measured on a
6-task DAG posted the way agents actually post: `SerialIsolation -> 1`, `LaneIsolation -> 6`.

**`file_claims.py` does not cover this.** It is wired ONLY in `goal_executor.py`, at the
**cross-FEATURE** level (whole feature A vs whole feature B, its own docstring: *"gates
concurrent feature builds"*). `scheduler_loop` never calls it, so it says nothing about two
TASKS inside one drain. The fan-out SPEC's audit table lists the file-collision guard as
"built", which is true of the module and misleading about task-level parallelism.

**What C.5 adds**, so that D can be the swap it was meant to be:

- `post_message(..., lane=…)` and `POST /comms/post` forwarding **both** `lane` and `files`
  (validated: `lane` a non-empty string, `files` a list of strings; omitting either stays
  valid, so every existing caller is unaffected).
- `fragments/task-dag-post.md` teaches the planner to declare them, with the rule that makes
  them safe: **same files ⇒ same lane; disjoint files ⇒ different lanes**, and omitting them
  is safe (undeclared ⇒ treated as touching everything ⇒ serial). The fragment is
  `requires: goal_id`-gated, so it reaches the planner exactly when it seeds a DAG — and the
  `planning/plan` golden snapshot, which composes without a goal_id, does not move.
- `supervisor/lane_partition.py::audit_lane_partition(conn, board, scope, goal_id)` — checks
  the disjoint-files-per-lane assumption instead of trusting it. Two distinct failures:
  **undeclared** (a ready task with no `files` — the `file_claims` WILDCARD, overlaps
  everything) and **conflicts** (two ready tasks in DIFFERENT lanes whose footprints overlap,
  reusing `file_claims.overlaps` so directory containment counts). `safe` is the predicate
  Phase D gates activation on. Audits the READY frontier only — a task still behind
  `depends_on` cannot run concurrently, so counting it would report conflicts the DAG already
  prevents. Read-only, never raises.

Shipped inside the ratchet: `comms_messages.py` was frozen at 405, so the four goal-message
field accessors moved to `db/queries/comms_goal_fields.py` (re-exported, no call site moved),
taking it to 360 — out of `file_size_baseline.txt` entirely — which is what paid for the
`lane` parameter.

C.5 made Phase D's precondition *reachable*. Phase D (below) is what turns concurrency on.

## fsm-fan-out Phase D — parallelism is ON, gated on the partition auditing safe

`_resolve_isolation` no longer pins `SerialIsolation`. `isolation: lane` (the default) now
returns **`lane_partition.AuditedLaneIsolation`** — real lane parallelism, granted only while
the frontier's partition actually audits safe:

| YAML | Phase C | Phase D |
|---|---|---|
| `isolation: lane` | SerialIsolation (pinned, logged) | `AuditedLaneIsolation` — parallel while `audit_lane_partition(...)["safe"]`, else 1 |
| `isolation: serial` | SerialIsolation | SerialIsolation (obeyed literally) |
| `isolation: worktree` | SerialIsolation | SerialIsolation + a warning (`WorktreeIsolation` is still a stub that raises) |
| `max_workers: N` | ignored | honoured — `LaneIsolation(max_workers=N)` caps below the lane count |

**The audit is re-run every scheduling round, not once at drain start.** `scheduler_loop` calls
`max_concurrency` on every frontier poll, and the frontier GROWS as tasks complete and unblock
dependents — so a task that becomes ready *later* can conflict with one already running. A
single up-front check would be exactly the "verified once, assumed forever" guarantee this
feature exists to stop relying on. The cost is one DB read per round, against rounds that block
on agents running for minutes. Safe↔unsafe transitions are logged; the state is not re-logged
every round.

**Failure widens nothing.** An audit that raises returns 1 (fail CLOSED to serial), so a broken
audit can never be the reason two agents write the same file.

**On today's DAGs this drains serially, and that is the correct answer** — no planner declares
footprints yet, so every frontier audits `undeclared` → unsafe → 1 worker. Phase D therefore
cannot be worse than Phase C's behaviour; it becomes parallel exactly when a planner has
declared lanes and footprints that hold up. The two Phase-C serial assertions did NOT have to
flip: they declare no `files`, so they still pass — for a sounder reason than a hard pin.

**No packaged flow opted in at Phase D** — it ships the ENGINE. Phase E added the first and
only opt-in (`goal-loop`, which IS `executor: loop`). Adding `parallel_states` to any OTHER flow
stays a separate, deliberate decision, because for `team-build` it is **not** merely a
concurrency change. Its `REVIEWING` carries `on_board_count: {metric: ready, op: gt, next: BUILDING}`, so
BUILDING today drains **one task per FSM cycle** with a REVIEWING pass between tasks. A
`parallel_states: {BUILDING: …}` entry makes BUILDING drain the whole ready frontier in one
stage and review ONCE after — a change to review cadence that lands even at serial isolation.

It also changes **which skill runs the work**, which an earlier draft of this section
understated. `fan_out._drain` never uses the stage's own `instructions`: the per-task prompts
come from `scheduler.py::_worker`, which composes `development/execute-task`. So a parallel
BUILDING bypasses its `agent_map` entry entirely — `team/build` does not run. Both effects
together make the opt-in a product call, not a side effect to slip in with an engine change.

To opt a flow in, once its planner declares lanes and footprints:

```yaml
parallel_states:
  BUILDING:
    isolation: lane
    max_workers: 4
```

Pinned by `tests/runner_supervisor/test_fan_out.py`: declared-disjoint lanes DO overlap (the
assertion Phase C could not make — mutation-checked: it fails if the swap is reverted),
`max_workers` bounds the peak while still going parallel, a cross-lane conflict or a single
undeclared task keeps the drain serial, `serial`/`worktree` are obeyed/degraded, and the
re-audit-per-round property is proven with dependents that only conflict once they become ready.

**Residual risk, still open:** `audit_lane_partition` only sees *declared* footprints — a task
that writes outside its declared set stays invisible to it. Closing that needs
`WorktreeIsolation`, still a stub.

## fsm-fan-out — ONE drain (`supervisor/drain.py`)

`fan_out._drain` and (at the time) `goal_executor._run_loop` each carried their own copy of the
same scaffolding — make a cost tracker, wrap `spawn_fn`, OR `tracker.exceeded()` into an abort
predicate, call `scheduler_loop`. They now share `drain.py::drain_frontier`, the single
`scheduler_loop` call site:

| Owned by `drain_frontier` (shared) | Left with the caller |
|---|---|
| the `CostCapTracker` and wrapping `spawn_fn` with it — **exactly once**, so cost cannot double-count | the isolation (a stage reads its flow YAML) |
| folding `tracker.exceeded()` into `abort_check`, so no caller can forget the cap | the caller's own abort reason (the FSM's `_abort_flag`) |
| the `scheduler_loop` call itself | the result shape the caller's consumer expects |

Phase E then removed the second caller entirely (below), so `fan_out` is the only one left —
pinned by an **AST**-based check in `tests/dag_goals/test_drain_shared.py` (a text search would
match `drain.py`'s own ASCII diagram).

## fsm-fan-out Phase E — `executor: loop` IS an FSM flow; the second engine is gone

Phase E was specified as "`_run_loop` becomes a thin alias, then is deleted; `executor: loop`
means run the flow whose BUILDING is parallel", with the note that "E only removes code, so the
ratchet is satisfied by construction". Two of those three claims were wrong, and the shape of
the fix follows from why:

- **"the flow whose BUILDING is parallel" meant `team-build`, and that would have changed the
  PRODUCT.** `executor: loop` is a flat drain — `development/execute-task` per task, no
  REVIEWING/TESTING/RETRO between tasks. `executor: team` is the reviewed `team-build` pipeline.
  Collapsing them hands a user who picked `loop` for speed a fully reviewed run instead.
- **"only removes code" was wrong** — `_run_loop` owned real behaviour the FSM path did not
  provide. That work is addition, not deletion, and is enumerated below.

So `loop` got **its own flow** rather than someone else's: `core/flows/goal-loop.flow.yaml`, a
single working state whose drain is the flat product, run by the ONE engine.

```yaml
states: [DRAINING, DONE]
parallel_states:
  DRAINING: {isolation: lane}     # -> AuditedLaneIsolation, via fan_out
gates:
  DRAINING->DONE:                 # the JOIN, once, after every worker finished
    - {type: require_tasks_done, on_fail: INCOMPLETE_TASKS.md}
    - {type: command_gate, command_key: build, on_fail: BUILD_FAILURES.md}
    - {type: command_gate, command_key: test,  on_fail: TEST_FAILURES.md}
    - {type: floor_gate, on_fail: FLOOR_FAILURES.md}   # build-proof 06: the whole run's diff
    - {type: task_checks, on_fail: TASK_CHECK_FAILURES.md}   # build-proof 07: unproven tasks' checks
```

`goal_executor._run_loop` is now a delegation to `_run_team(flow="goal-loop")` — no
`RunnerState` of its own, no `scheduler_loop` call, no cost tracker, no isolation choice.

**What the goal run GAINS, all of it from the DB being the authority** — the same list the
compiled-executor revert was argued on: a `fsm_state` row (so `pathly-status` and the
`STATE.json` export see it), a `STATE_TRANSITION` audit trail, park/resume on a human
checkpoint, the escalation ladder, and the two verify commands as ROUTED gates.
`goal_verify.verify_clean_drain` ran those same two commands after a clean drain but could only
post a board escalation and stop; a `command_gate` failure re-drives a fix through
`feedback_routing`.

**The flow NAME is load-bearing.** `run_history_read._classify_kind` returns `loop` for a
bare-uuid run whose `adapter` column is the literal `"goal-loop"`, and `start_run` writes
`state.flow` into that column — so the parent row still classifies as a loop PARENT and still
windows its per-task `sched-*` rows into ONE run in `GET /runs`. `_flow_kind` also had to learn
the name, or the run's storage would nest at `features/<f>/goal-loop/<slug>` instead of under
`goals/`.

### Two prerequisites the plan did not anticipate — Phase E is a silent no-op without them

1. **`fan_out._drain` resolved the frontier from `state.topic`.** For a plain feature pipeline
   topic IS the board scope, so this was invisible. A GOAL run's topic is its own storage slug
   (`features/<feature>/goals/<slug>`) while its tasks live on the parent board at
   `scope=<feature>`, and `get_ready_tasks` ANDs `scope IN (…)` with `goal_id` — **measured 0
   ready tasks against 3 for the same goal.** Every goal run through a parallel flow would have
   "drained" nothing and advanced. `_frontier_scope` now uses `terminal_identity._run_board_scope`
   — the SAME derivation the spawn chokepoint stamps telemetry with — and degrades to the topic.
   The join still agrees: `require_tasks_done` counts by `goal_id` when a run has one.
2. **A DAG task's prompt was never placeholder-substituted.** `scheduler._worker` composed
   `development/execute-task` via `compose_skill` and stopped there, so `completion-report`
   reached the agent still saying to key its `AGENT_DONE` on the literal `<fsm_feature>` — the
   same defect `board_run._inject_board_prompt_vars` fixed for board runs, never fixed here. It
   was masked while the loop owned its telemetry (`_synthesize_agent_done_if_missing` wrote a
   synthetic `AGENT_DONE` stamped `category="loop"`); inside an FSM stage that safety net is off.
   The whole assembly moved to **`supervisor/task_prompt.py`**, which substitutes through the
   same `_inject_prompt_vars` the other two paths use and stamps `run_category="loop"`.
   `scheduler.py` 432 → 392, so it dropped out of `file_size_baseline.txt`.

### What had to be preserved, and how

| `_run_loop` owned | Under Phase E |
|---|---|
| `_record_run_history(flow="goal-loop")` — the loop PARENT row | `start_run` writes `state.flow` into the same column; the flow is NAMED `goal-loop`, so unchanged |
| the cost-cap tracker | `drain_frontier` owns it for every drain |
| goal-scoped storage resolution | `_run_team`'s `board_run_topic` + `_flow_kind` (now mapping `goal-loop` → `goals`) |
| `verify_clean_drain` | the two `command_gate`s at `DRAINING->DONE` — routed, so a failure re-drives a fix |
| per-task `task_claimed`/`task_done` COMMS_UPDATEs | `RunnerState._comms_broadcast_fn`, set from `start_run(event_broadcast_fn=…)` and read by `_drain`. `supervisor/` may not import `http_server/`, so the broadcaster is injected by the route that already holds it |
| the `board_lock` lease `/comms/goals/stop` released | the run is an FSM run now, so stop goes through `abort_run` — see below |
| `write_goal_root_span` (goal=trace, task=span) | **dropped.** A root span whose children are written by the FSM's own telemetry writer would be a childless trace root; `executor: team` has never had one either. Its own docstring calls this "no labelled root", not lost spans |

**Stopping a goal run was broken for `team` and would have broken for `loop`.**
`/comms/goals/stop`'s FSM branch looked the run up with `get_state(scope)`, but a goal's FSM run
is registered under its board-nested topic — so the lookup returned `None` and the route reported
`not_running` while the run kept going. Survivable while `loop`/`single` were stopped through the
board lock; not once `loop` is an FSM run. `registry.find_active_run_for_goal(goal_id, fallback)`
matches on the run's own `goal_id` — correct whatever flow it runs and whatever storage kind that
flow maps to — and keeps the scope-keyed lookup as the fallback for a non-goal run.

Pinned by `tests/dag_goals/test_loop_is_an_fsm_flow.py` and the converted golden-path suite
(`tests/fsm_flows/test_golden_path.py`), which now drives the REAL `goal-loop` YAML through
`fan_out.run_stage` with a goal-scoped state — mutation-checked: reverting `_frontier_scope` to
`state.topic` fails all seven with an empty drain.

**Still open, and deliberately:** no OTHER flow opts into `parallel_states` — for `team-build`
that would change review cadence AND which skill runs the work (a fan-out state's per-task
prompts come from `development/execute-task`, so `team/build` would not run), which is a product
call, not an engine change. And `audit_lane_partition` still only sees *declared* footprints; a
task writing outside its declared set stays invisible to it, which needs `WorktreeIsolation`
(still a stub).

## Visible runner (supervisor/)

`supervisor/` drives the pipeline by polling `/next_action` and calling `/complete_stage`. Every agent invocation goes through a visible terminal — there is no headless fallback.

**Stage flow:**
1. `supervisor/orchestrator.py` calls `/next_action` → gets `agent_hint.instructions` (full prompt)
2. `supervisor/terminal.py` builds `argv` (via `terminal_argv._resolve_spawn_argv`) and emits `TERMINAL_SPAWN` SSE with `{ tab_id, run_id, argv, cwd, label, adapter }`
3. Studio opens a PTY tab (`node-pty`) and spawns the process via the `argv`
4. Studio POSTs `/runner/terminal/started` when PTY is up
5. PTY exits → `terminal.ts` POSTs `/runner/terminal/result` with exit code and stdout tail
6. Supervisor receives the result, calls `/complete_stage`, advances to next stage

Same-adapter consecutive stages share a `session_id`. Cross-adapter transitions start a new
session, and so does a reviewer stage: `resolve_session` is given the `/next_action` `agent`, and when
`fsm_compose_tables.agent_role_of` names a role in `INDEPENDENT_ROLES` (`team/review` and
`quality/reviewer` are `reviewer`) it returns no session id, so the reviewer never `--resume`s the
builder's conversation (a resumed claude session restores all of it, tool calls and results included,
whatever the prompt leaves out). The same helper picks the stage that gets the Review packet, so the
two cannot disagree. `_loop` still stores the reviewer's own session as `open_session`: the next
same-adapter stage (TESTING, or the next task's BUILDING) continues the reviewer's session, not the
builder's. The question-answer re-spawn inside a stage resumes that stage's own session, and feedback
spawns pass no session. Only the reviewer is independent; every other role keeps same-adapter continuity.

On Windows, the argv is passed to PowerShell via `-EncodedCommand` (base64 UTF-16LE) to handle arbitrary prompt content safely.

## CLI shortcuts

```bash
pathly-ff      # fast-forward current feature state one step
pathly-back    # roll back current feature state one step
pathly-status  # show all active features and their current FSM state
pathly-log     # readable timeline of a feature's FSM events
pathly api GET '/chief/session?project_root=<root>'   # a chief's door to the server (run token from $PATHLY_RUN_TOKEN)
pathly help    # the routes a chief uses most
```

`pathly api` is for a chief agent in its tab, not for a person: it needs `PATHLY_RUN_TOKEN`
(exit 2 and no request without it) and the server decides what the chief's tier may call
("Chief endpoints").

Discovery is `cli/_discovery.py`, which globs `STATE.json` off disk across all storage
layouts, current and legacy. That is sufficient precisely BECAUSE every engine persists its
state to `fsm_state` (and thence the `STATE.json` export) — a run that skipped the DB would
be invisible here, which is one of the reasons the compiled executor was reverted.

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
- **The whole `pathly/` tree is exempt**, wider than `scope_gate`, which under `pathly/` exempts
  only what the builder stage may write. `pathly/` is entirely Pathly's own storage substrate (features/,
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

**Author provenance on board writes (role-read-policy)** lives in the same module. `stamp(identity)`
returns the three `comms_messages` author columns for a caller: a live run token whose run has a
role gives `author_role`/`author_run_id` of the run it was minted for and `author_source="token"`;
anything else gives `none` (no token, an unknown or revoked one, a UI caller, and a run whose token
carries no role, which is also logged as a warning naming the run: `token` with no role would
pass every role wall). `system_stamp()` gives `system`/`system` for rows the server writes itself,
and `post_system(conn, **fields)` is `post_message` with that stamp applied (the three size-frozen
blueprints `comms/goals.py`, `project.py` and `settings.py` import it `as _post_message`, so their
call sites need no stamp argument). The values (`AUTHOR_SOURCES`, the `system` constants) are
defined once in `db/provenance_values.py`. `POST /comms/post` computes
`stamp(caller_identity(request))` (`caller_identity` is in `http_server/`, so the identity is a
parameter here), and the body's `from` / `run_id` are still stored in `from_agent` / `run_id` but
never used for provenance. Handlers that write a row whose content is the caller's (the
`/code/query` log row, `/record_phase`, the context-pull trail) are stamped from the same
`stamp(caller_identity(request))`: the row carries the caller's role only when the request sends a
live `X-Pathly-Run-Token`, and is `none` when it does not. The context-pull trail is reached
through `8765/comms` calls, which send the header; today's agent `curl`s to `/code/query`
(`fragments/code-query.md`) and to `/record_phase` (`utilities/log-phase.md`,
`development/design.md`, `planning/storm.md`) send none, so those rows land `none`. Server-internal
`post_message` callers pass `**system_stamp()`; `post_message` itself stores a caller that passes
no source as `none`, never NULL (the startup backfill turns NULL into `legacy`), and raises
`ValueError` for a source outside `AUTHOR_SOURCES`. `promote_message` copies the source row's three
author values onto the promoted copy. `tests/comms_board/test_comms_provenance.py` scans `src/` for
a `post_message` call without a stamp (a name bound to `post_system` counts as stamped; an aliased
or indirect use of `post_message` fails), for an `INSERT`/`REPLACE INTO comms_messages` without
`author_source`, and for a hard-coded author value; the two files left on the `none` default or a
copied stamp are on its commented allow-list.

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
  finished. The goal **`loop`** executor is the same shape, and since Phase E gets there the same
  way: it runs the `goal-loop` FSM flow, so `start_run` writes the PARENT row
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

## HQ copilot (`hq_context.py`, `hq_prompt.py`, `hq_models.py`)

Studio's HQ panel answers board questions with a FREE local model that runs Studio-side, so the
server never calls a model — it builds the turn (`POST /hq/prompt`, `blueprints/hq/`). Three
modules, one concern each:

- `hq_context.assemble_packet` — board state → a `<pathly-context>` packet, token-budgeted
  (`hq.context_budget_tokens`, chars/4), whole sections dropped lowest-priority-first
  (`hq.packet_order`), 5s deadline, `HQContextUnavailable` rather than a partial packet. The
  caller picks sections (`sections=`, from `SECTION_NAMES`; unchosen → cut_reason `off`; each
  section reports its estimated `tokens` — what it took, or would have when cut over budget — which
  Studio's composer meter estimates the next question from;
  `SECTION_DEFAULTS` leaves the opt-in `summaries` section — artifact AI summaries — off). Runs
  are project-wide (the fleet view), so each run line names its board. Question options are
  read as agents post them — `{id, label, description}` objects — a plain-string-only reader
  raised on the first real question and dropped the whole packet.
- `hq_prompt` — `HQ_SYSTEM_PROMPT` (fixed, not user-editable), `build_hq_turn` (packet +
  message), `prepare_hq_turn` (the route's entry point: an action request returns
  `HQ_READONLY_REDIRECT` without the packet or model). The redirect matches IMPERATIVES only —
  a clause that opens with an action verb and names a target — so "why did the build stop?"
  still reaches the model. `HQ_TOOL_SCHEMAS = ()` is asserted empty on every build.
- `hq_models` — `MODEL_CONTEXT_WINDOWS` (fail closed for unknown ids) and
  `hq_required_context(budget) = 2*budget + 4000`: ONE number that both gates eligibility and is
  the context size Studio requests from the runtime.

Read-only by construction; `tests/hq_copilot/test_acceptance.py` diffs every row of the touched
tables around the full path.

**Operator actions (pathly/features/local-operator).** With `enabled_actions` on `POST /hq/prompt`
(the composer's Actions tab, at most `hq_actions.MAX_ENABLED` = 8, else 400) the turn becomes the
OPERATOR turn — but only for the actions Settings makes available (`hq.actions.available`,
`hq_settings.get/set_hq_available_actions`; unset = `hq_actions.default_available()`: run control +
`post_note`). Zero survivors = the read-only turn above, unchanged.

- `hq_actions` — the curated catalog (9 actions: pause/resume/retry/stop_run, run_goal, plan_goal,
  post_note, diagram_artifact, add_diagram_to_board), each with domain, risk words, model-facing
  description, JSON-schema params (every one required — node-llama-cpp ignores `required`; optional
  = a bare enum with `null`), `runs_on` server|studio. `NEVER_OFFERED` (answer_question,
  directives, settings, secrets, files, shell) can never be in it. Pure.
- `hq_operator` — `OPERATOR_SYSTEM_PROMPT` (propose, never claim it ran, never compose — propose
  `plan_goal`), `operator_refusal_redirect` (imperatives for never-offered things → the right
  surface, before the packet or model), `prepare_operator_turn` (packet built `with_ids=True`: goal
  and artifact lines carry `(id 1a2b3c4d)` so the model can name them; `HQTurn.tools` = the
  enabled actions' function definitions).
- The model only PROPOSES. Studio's record-only handlers (`main/ipc/llmProposals.ts`) return the
  calls; `POST /hq/actions/check` turns them into cards (not enabled ∩ available → dropped; bad
  args or a target in the wrong state → an `invalid` record) with a fingerprint of the state
  shown. `POST /hq/actions/run` (the Run click) resolves again — a changed fingerprint is `stale`,
  nothing runs — then executes a server action by dispatching IN-PROCESS to the route a human click
  uses (`_action_exec`: `/runs/<id>/pause|resume|retry|stop`, `/comms/goals/run`,
  `/comms/goals/decompose` mode=planner, `/comms/post` as the human's note), so validation,
  refusals (a busy board) and broadcasts are the route's own; one attempt, no retry loop. A
  Studio-run action (diagrams) returns `approved` + its resolved target; Studio runs it and reports
  (`/hq/actions/report`).
- Audit: every EXECUTED action (done or failed) writes one `status` post from `local-operator` on
  the HQ board, server-stamped (`author_source=system`) — never written by the model; proposals,
  cancels and stale cards write nothing. Tests: `tests/local_operator/`.
