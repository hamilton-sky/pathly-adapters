# Changelog

## Unreleased

### FSM — fan-out foundation: one engine, one authority (Phases A/B/C)

Moves the DAG fan-out machinery INSIDE the FSM, so `scheduler_loop` stops being a rival
engine (a peer of `orchestrator._loop`) and becomes the fan-out executor *of a state*.
Behaviour is deliberately unchanged in this pass — Phase C pins `SerialIsolation`
regardless of configuration, so a parallel state still drains one task at a time. Design
and phasing: `pathly/features/fsm-fan-out/SPEC.md`.

- One runner contract, shared by both prompt paths: `fsm_compose.RUNNER_CONTRACT_BLOCK`
  is now the single definition of the "you are headless, the supervisor owns the FSM"
  block, and `supervisor/scheduler.py`'s DAG-task prompts append it too. A loop-executor
  task agent was previously the one headless agent never told the supervisor drives the
  flow — under fan-out that means a double-advance or a 404 respawn loop.
  `build_prompt`'s output is byte-identical.
- New optional flow-YAML key `parallel_states`: a state opts into fan-out by naming
  itself, with optional `max_workers` (positive int) and `isolation`
  (`lane` | `serial` | `worktree`, the last still a stub). Validated in
  `validate_flow_dict`, so `pathly-validate-flow` catches a typo'd state name or a zero
  `max_workers` instead of it silently doing nothing. No shipped flow declares it.
- New `supervisor/fan_out.py`: `run_stage` is the one call site for executing an FSM
  stage — no `parallel_states` entry spawns a single agent exactly as before; an entry
  present drains the state's ready tasks via `scheduler_loop` and returns a merged result
  in the same shape. `fsm_state.current` stays a scalar throughout, and gates still run
  once at the transition — that is the join.
- New `supervisor/orchestrator_session.py`: the session-continuity block lifted out of
  `orchestrator._loop` verbatim (same reuse predicate, same `SESSION` event). With
  `fan_out.py` this took `orchestrator.py` 427 → 399 lines, dropping it out of
  `scripts/file_size_baseline.txt` entirely.
- `CostCapTracker` gained a `total` property, so a drain reports its summed cost without
  re-summing the per-task figures the tracker already holds.

Not included, and gated on a real run of the above: turning concurrency on (the
`LaneIsolation` swap) and retiring `goal_executor._run_loop`.

### DAG — `lane` and `files` are writable, and the lane partition is checkable (C.5)

Two `comms_messages` columns the DAG scheduler's whole concurrency-safety model rests on
had **no write path**: `post_message` never accepted `lane`, and `POST /comms/post` — the
only way an agent creates a task — silently dropped `files`. Every task therefore reached
the scheduler with both NULL, and `scheduler.py`'s `lane or task_id` fallback put each task
in its own lane, making "at most one worker per lane" vacuously true.

- `post_message(..., lane=…)`, and `POST /comms/post` now forwards **both** `lane` and
  `files`, validated (`lane` a non-empty string, `files` a list of strings). Omitting
  either stays valid, so every existing caller is unaffected.
- `fragments/task-dag-post.md` teaches the planner to declare them, with the rule that
  makes them safe — **same files ⇒ same lane; disjoint files ⇒ different lanes** — and
  that omitting them is safe (undeclared ⇒ treated as touching everything ⇒ serial; costs
  wall-clock, never correctness). `requires: goal_id`-gated, so it reaches the planner
  exactly when it seeds a DAG.
- New `supervisor/lane_partition.py::audit_lane_partition` checks the disjoint-files-per-lane
  assumption instead of trusting it, reporting **undeclared** footprints and cross-lane
  **conflicts** separately (reusing `file_claims.overlaps`, so directory containment counts).
  It audits the ready frontier only — a task behind `depends_on` cannot run concurrently.
- Note for anyone reading `file_claims.py` as the task-collision guard: it is not. It is
  wired only in `goal_executor`, at the **cross-feature** level; `scheduler_loop` never
  calls it, so it says nothing about two tasks inside one drain.

No behaviour change: nothing consumes the two fields yet. This is the prerequisite Phase D
turned out to need — it makes D's "tasks declare accurate file footprints" precondition
reachable, where before it was unsatisfiable.

### FSM — parallelism is on, gated on the lane partition auditing safe (Phase D)

A `parallel_states` state with `isolation: lane` now drains its ready tasks **concurrently**
— but only while the frontier's lane partition actually audits safe. `_resolve_isolation`
returns `lane_partition.AuditedLaneIsolation` instead of the pinned `SerialIsolation`.

- `isolation: lane` (default) → parallel while `audit_lane_partition(...)["safe"]`, else one
  worker. `isolation: serial` is obeyed literally; `isolation: worktree` degrades to serial
  with a warning (`WorktreeIsolation` is still a stub that raises).
- `max_workers: N` is now honoured — `LaneIsolation` gained a cap below the lane count.
- **The audit re-runs every scheduling round, not once at drain start.** The ready frontier
  grows as tasks complete and unblock dependents, so a task that becomes ready later can
  conflict with one already running; a single up-front check would miss it. An audit that
  raises returns one worker — failure never widens concurrency.

**On a DAG whose tasks declare no footprints this drains serially**, which is every DAG
today: Phase D cannot behave worse than before it, and becomes parallel exactly when a
planner has declared lanes and footprints that hold up.

**No shipped flow opts in.** Adding `parallel_states` to a flow stays a deliberate decision,
because for `team-build` it is not only a concurrency change: its `REVIEWING` loops back to
`BUILDING` while ready tasks remain, so BUILDING drains one task per FSM cycle with a review
between each. Opting in makes it drain the whole frontier and review once — a change to
review cadence that lands even at serial isolation.

```yaml
parallel_states:
  BUILDING:
    isolation: lane
    max_workers: 4
```

Not included: retiring `goal_executor._run_loop`. Still open: the audit sees only *declared*
footprints, so a task writing outside its declared set remains invisible to it — closing that
needs `WorktreeIsolation`.

## 2.20.0

### Board — project-planner (G2): spec → sibling features

- New skill `planning/project-decompose` — splits a big spec dropped on the PROJECT
  board into 2-5 sibling `type=feature` cards, each scaffolded under
  `pathly/features/<slug>/SPEC.md`.
- New `project-consultation` flow (PO→…→project-decompose) plus a feature-count exit
  gate (`count_features_for_project`, mirrored by `count_goals_for_feature` for the
  feature-consultation gate) — both counters live in `db/queries/comms_counts.py`.
- `POST /comms/project/decompose` and `POST /comms/features/decompose` — light/full
  (single-agent board run) or consultation (FSM flow) rigor tiers.
- Project-board scope is the normalized `project_root` path (not a fixed literal),
  matching how Studio and `comms_context` injection already key the project board.

### Board — goals read-model + `/pathly goalize`

- `GET /comms/goals` — goals enriched with a task-DAG rollup
  (`{total, done, in_progress, pending, blocked, failed, ready}`), the symmetric
  read partner to the existing `/comms/goals/{run,stop,decompose}` write routes.
- New interactive skill `planning/goalize` (`/pathly goalize`) — chats an idea into
  a goal + task DAG with the human, then posts both to the board only after sign-off.

### Code intelligence — `/code/query` fixes

- `/code/query` now serves real data: relative file paths passed to the `cli` backend
  are anchored to `project_root` instead of the FSM server's own process CWD, which
  previously made every relative-path lookup resolve to nothing.
- `code_context.reindex=auto` now actually refreshes the graph — `maybe_reindex` runs
  the tool's incremental `index_repository` itself (debounced to once per 30s),
  instead of only flipping the tool's own `auto_index` flag, whose change-detection
  could silently miss genuinely-changed files.
- The `code-query` skill fragment gained a direct-CLI fallback
  (`codebase-memory-mcp cli search_code` / `query_graph`) for when the `/code/query`
  proxy returns a null result.

## 2.19.0

### Studio — Workspace sidebar rebuilt as a real file tree

- The Workspace tab is now a plain, lazy-loaded project file tree (folders/files),
  replacing the curated-sections panel. Animated icons; single-click selects, with
  Open / New / Rename / Delete / Move via the right-click + ⋯ menu.
- Pinned `pathly/` section at the top (independent expand) plus the folder in place.
- Project-wide search with an All/pathly scope chip and a tree/list results toggle;
  true collapse-all. Feature folders get an "Open board" action (→ Command Center).
- New projects scaffold a `pathly/` workspace (features/debugs/explorations/lessons).
- Bottom-nav icons aligned in fixed slots; `Sidebar.tsx` trimmed (~700→~300 lines).

### Storage — feature-centric layout

- Features live flat at `pathly/features/<name>/`; goals nest under their feature;
  comms-board relocated; legacy `pathly/plans/` retired. CLI discovers flat features.

### Studio — board redesign & board-scoped planning

- Board readability pass (filter, header Evaluate, unified summary popover);
  consultation board-scope + board-level planning UI; project-level run lock
  (features build one at a time); CLI Command Center toolbar refinements.

## 2.18.1

### SOLID — 400-line limit enforced

- `refactor(solid)`: split oversized modules across the orchestrator (supervisor, fsm,
  blueprints) to hold the 400-line-per-file rule.

### Studio — summary depth + artifact cards

- Summary depth picker in the Artifacts toolbar (app-default, persisted).
- Collapsible artifact banners + per-section copy; card shows the description only.
- Drag-to-board summary honors the selected depth and uses file capture (like Re-summarize).
- Derive a description when the model omits the `## Description` section.

### Python — DB migration safety

- Migrate per db-path so test-swapped DBs never skip schema init.

## 2.18.0

### Structured summaries — depth formats + retrieval

- Three summary-depth styles (gist / topic-map / detailed) with per-artifact persistence;
  depth selector in the gear popover and on artifact cards; depth actually changes the
  compose prompt and renders as styled markdown.
- One structured-summary contract for all paths (markdown, not JSON); single-sourced
  output-format templates per depth; summarize also rewrites the artifact description.
- Summary capture via an engine-written file, not stdout tail (P0b/c); transient capture
  files gitignored + deleted after read.
- Hierarchical chunked embeddings — one parent vector (message + summary) plus per-bullet /
  per-section child vectors; board context surfaces the matched per-topic chunk.

### Skill composition — compose endpoint + fragments

- `POST /skills/compose` endpoint + `composeClientSkill` client seam (P0a).
- `client-file-output` + `artifact-transform` fragments + transform skills (P0b).
- `no_defaults` opt-out drops `progress-logging` from pure-transform skills.
- DB-backed fragment overrides + per-project skill-editor scoping — stop rewriting packaged YAML.
- On-demand skill export to adapters + auto-commit toggle + VERIFY template.

### FSM

- `complete_stage` returns `next_state` so multi-stage headless runs advance (fixes the
  driver contract that stalled every multi-stage run).
- Proactive exit-requirement + gated, scoped auto-commit.

### Studio — Command Center + AI routing

- Rename the HQ panel tree → **CommandCenter**; CommsPanel refactor into per-component
  subfolders with a `cards/` tree (GoalCard / MsgCard / TaskCard).
- Unify AI routing — Model Manager + Router; retire the server-side summarizer.
- Unify board spawn controls + Evaluate confirm-preview; copy-to-clipboard and copy-file-path
  on artifact cards; Stop cancels queued CLI engines (not only running PTYs).

### Docs

- Lead with Pathly's primary goal (board-driven headless orchestration); align narrative
  docs/READMEs with headless-primary + the agnostic-skills principle.

### Chore / CI

- Remove the differ scaffold placeholder; black-format `src/` + `tests/`, pin black / mypy /
  bandit to stop CI drift; suppress a false-positive bandit B310.

## 2.17.0

### Comms board — Goals → Task-DAG → pluggable executors

- `goal_id` / `executor` columns on `comms_messages`; a goal is `type='goal'`, its DAG is
  `tasks WHERE goal_id=<goal>` + `depends_on` edges (Phase 0a/0b).
- `/comms/goals/run` dispatches a goal's DAG to one of three executors via
  `supervisor/goal_run.py`: **single** (one agent drains the whole goal via the `drain-dag`
  skill), **loop** (supervisor-owned frontier, fresh agent per task via `scheduler_loop`),
  **team** (the trimmed `team-build` FSM flow). `/comms/goals/stop` halts any of them.
- `/comms/goals/decompose` turns a goal into a DAG — `mode=planner` (fast, DAG-only) or
  `mode=consultation` (PO→architect→researcher→designer→planner flow).
- Two-flow split: new `consultation` flow + trimmed `team-build` flow.
- Evaluator (`planning/evaluate`) now seeds a real `type=goal` + `type=task` DAG.
- Studio: Goals & Tasks board view, per-goal executor + CLI-engine selectors,
  Decompose / Run / Stop controls.

### Comms board — context retrieval

- `context_refs` manifest on messages; per-`.md` section index (`comms_artifact_sections`)
  with anchors + staleness gates (mtime → hash → structure_key).
- `GET /comms/artifacts/<id>/section` hydrates a named section (+ Board Catalog listing).
- Opt-in offline summarizer (`runner/inference.py`, backends `minilm`=off / `ollama` / `haiku`)
  fills artifact + section summaries; default off ⇒ behavior-identical.
- §3a: an uploaded `.md`'s generated summary feeds the message's display text + search
  vector, so it surfaces in the 💡 semantic channel of `retrieve_board_context`.
- Summarizer controls: global default + per-upload backend override, plus
  start/done/fail observability (`summarizing` / `summary_ready` / `summary_failed`).

### Comms board — memory consolidation

- `/comms/consolidate` — relevance-gated 💡 channel, deterministic near-duplicate dedup,
  and a manual reflection pass (`mode=full`).

### Docs

- `pathly/plans/comms-board/` reorganized: shipped-phase specs archived to `_archive/`;
  ROADMAP/README trimmed to the remaining P3 (parallel) + deferred-polish items.

## 2.16.2

### Studio topbar / sidebar redesign

- Replace the `Projects` text button and the topbar hamburger with a corner `PathlyLogo`
  component that acts as a back-to-home button; the `☰` sidebar toggle is removed from
  the topbar entirely.
- Add `ProjectSelector` dropdown to the topbar — switch project, open-in-new-window per
  row, open project folder. Replaces the old `TopicSelector` (feature/topic dropdown).
- Move sidebar collapse/expand inside the sidebar itself via a `PanelLeft` button in
  `TabBar` / `IconStrip`; uniform 28 px header height across all topbar items.
- Rename the CLI Engines toggle icon from `Activity` → `Cpu`.

### Studio CLI spawn scheduler — dual-cap gate + queue UI

- `studio/src/main/ipc/terminal.ts` — process-wide concurrency caps: global ≤ 8,
  headless ≤ 5, interactive ≤ 5 (all configurable at runtime via `update-caps` action).
- Headless one-shots are **queued** (FIFO + priority) when the cap is reached; interactive
  sessions are **rejected** with a toast instead of queuing.
- `SpawnQueuePanel` (`components/CliMonitorBar/SpawnQueuePanel.tsx`) — queue management
  UI: reorder (up/down), cancel, and live cap editing.
- `SPAWN_DEBUG` flag in `terminal.ts` — `[spawn]` prefixed `console.log` lines trace
  spawn lifecycle (reject reasons, PTY errors, exit codes, wall time).
- Rate-limit backoff in the headless queue path.

### Studio — Codex headless fix

- `cliEngine.ts` now invokes `codex exec --skip-git-repo-check` for headless runs,
  preventing "Not inside a trusted directory" rejections on arbitrary project paths.
- `terminal.ts` pipes `$null` into the Codex PTY so `codex exec` does not stall waiting
  for stdin when the prompt is passed as a CLI argument.

### Python — process-wide DB write lock

- `src/pathly_orchestrator/db/connection.py` replaces per-connection locks with a single
  process-wide `threading.RLock` (`_global_write_lock`, returned by `_get_write_lock`).
  Reentrant so nested write paths under the same lock do not deadlock.
  WAL mode + `busy_timeout=5000` remain in place.

### Python — prompt dash-safety

- `src/pathly_orchestrator/adapters.py` — `_dash_safe_prompt` strips a leading `---`
  block from composed/headless prompts before they reach the CLI (root cause: `claude -p`
  treated a prompt starting with `--` as an unknown option and rejected it).
- `src/pathly_orchestrator/skills/compose.py` — `_strip_leading_frontmatter` applied to
  skill body and raw converted paths so assembled prompts never start with `---`.
- `studio/src/renderer/src/services/cliEngine.ts` — `dashSafePrompt` applies the same
  guard in `buildHeadlessArgv` on the Studio side.

---

## 2.14.1 — 2026-06-12

### Antigravity adapter + Studio improvements

- Add `antigravity` adapter (`src/pathly_data/adapters/antigravity/`) — installs Pathly
  skills and agents into the Antigravity CLI (`~/.gemini/antigravity-cli/`). Models:
  `gemini-2.5-pro` (pro-tier) and `gemini-2.5-flash` (flash-tier). Install via
  `pathly-setup antigravity --apply`.
- Add `antigravity` to `_KNOWN_ADAPTERS` in FSM validator — `adapter_map` entries using
  `antigravity` now pass flow validation instead of raising an error.
- Add `antigravity` to `ALLOWED_HOSTS` in `install_cli/orchestrate.py` and to
  `detect.py` host discovery (detected by `~/.gemini/antigravity-cli/` directory).
- Comms board: multi-feature boards, per-panel reads, live DB connection, feature
  card last-activity from EVENTS.jsonl, real feature stage/status from STATE.json,
  retract-while-unread, compose redesign, custom drop-up message-type picker.
- Flow storage: normalize flow graph into DB tables (`flow_nodes`, `flow_edges`);
  FSM reads rows-first with disk fallback.
- Studio: responsive sidebar collapse, topbar compact mode, Notebook landing page,
  breadcrumb cleanup, Ctrl+1–5 panel shortcuts, `Update` button (pip upgrade + deploy).
- Security: per-thread SQLite connections (WAL mode), `X-Pathly-Secret` header auth
  on all POST routes, centralized `apiFetch` in renderer.
- Skills directory reorganized from flat layout to categorized subdirectories
  (`controls/`, `development/`, `planning/`, `team/`, `utilities/`, `fix/`,
  `custom/`, `debug/`, `fragments/`).

---

## 2.11.7 - 2026-05-27

### Studio library packaging

- Bundle the canonical Pathly `agents`, `skills`, `templates`, and `flows`
  content with Pathly Studio so the Library sidebar works in installed builds.
- Load the bundled library through a read-only IPC path while keeping writes
  restricted to user-owned workspace content.

---

## 2.4.1 — 2026-05-13

### Schema fixes

- Add missing `inputs` property to `pathly-meta.schema.json` — VS Code was
  reporting "Property inputs is not allowed" on `orchestrator.yaml` because the
  schema predated the `inputs` field added for agent input definitions.
- Move `state.schema.json` into `src/pathly_data/schemas/` — it previously only
  existed as a root-level copy that was deleted when redundant root copies were
  removed. Now lives alongside `pathly-meta.schema.json` as the canonical location.
- Remove redundant root-level `schemas/` directory — `.vscode/settings.json`
  already pointed to `src/pathly_data/schemas/` directly; the root copies caused
  drift and false validation errors.

---

## 2.4.0 — 2026-05-13

### Mandatory scout spawning rules enforced across all agents

- Add `## Scout spawning rules — MANDATORY` block to all 6 scout-spawning agents
  (`explorer`, `planner`, `builder`, `architect`, `reviewer`, `tester`) and to the
  `explore` skill. Rules enforce: orientation scout required when spawning ≥2 scouts,
  clustering rule for all remaining scouts (2–3 related files per concern), minimum 2
  scouts when scouts are used, maximum 4 (5 only with written justification), parallel
  launch required (all scouts in one message), and no direct file reads by the
  orchestrating agent while scouts are active.
- Add `docs/RISK_ASSESSMENT.md` — architecture risk assessment for 5 identified risks
  (hook contract mismatch, Codex clean-machine gap, unversioned event schema,
  version drift, installer configuration opacity) with proposed solutions for each.
- Add `pathly/explorations/architecture-risk-assessment/` — full exploration artifacts
  (EXPLORE.md, TRACE.md, CONCLUSIONS.md) from the risk assessment conducted 2026-05-13.

---

## 2.3.0 — 2026-05-13

### FSM configurable via flow_config YAML (breaking for skill authors)

- Orchestrator is now a generic FSM engine driven by a `flow_config` YAML file at
  spawn time. Skills pass `flow_config`, `topic`, `rigor`, and `autoFlow` — the
  orchestrator reads the state machine, agent_map, storage_path, and feedback_routing
  from the YAML rather than having them hard-coded.
- `src/pathly_data/core/flows/` — new directory shipping `*.flow.yaml` files for
  `team`, `explore`, `debug`, and `test` pipelines. Installed alongside agents by
  `pathly-setup`.
- `materialize_flows()` added to `install_cli/materialize.py` — copies all
  `*.flow.yaml` files from the installed package to the host destination.
- Sub-skills now write artifacts only; orchestrator exclusively owns `STATE.json`
  writes and event appends. Commit template updated to use neutral
  "Pathly Orchestrator" identity.
- `pathly/` root consolidation — all pipeline workspace artifacts (`plans/`,
  `pipeline-walkthrough/`, `lessons/`, `explorations/`) live under `pathly/`.
  Repo-root `plans/` and `pipeline-walkthrough/` directories removed.

---

## 2.2.0 — 2026-05-13

### Agent architecture refactor and archive consolidation

- Archive consolidation: `_archive/` → `.archive/` across all pipeline plan directories.
- Fix tester: remove `builder` from `can_spawn` — orchestrator spawns builder,
  tester does not.
- Archive `agent-architecture-refactor` pipeline (DONE).

---

## 2.1.0 — 2026-05-13

### Orchestrator and hooks are now first-class shipped packages

- Move `orchestrator/` → `src/pathly_orchestrator/` and `hooks/` → `src/pathly_hooks/`
  so both ship in the installed wheel. The repo-root copies are removed.
- Add `pathly-events summary <feature>` console script — prints a token/cost table
  from `plans/<feature>/EVENTS.jsonl`.
- Add `pathly-state <feature>` console script — prints current FSM state from
  `plans/<feature>/STATE.json`.
- This is non-breaking for end users: the repo-root `orchestrator/` and `hooks/`
  directories were never exported by prior releases.

### FSM hardening

- `schemas/state.schema.json` — JSON Schema with all 13 state names and allowed-transitions
  table. `write_state` and `append_event` validate against it at write time; invalid state or
  illegal transition raises `ValueError`.
- `eventlog.append_event` is now concurrency-safe via `fcntl.flock` / `msvcrt.locking`.
- `state.schema.json` gains an optional `iteration_by_stage` map (key = FSM stage name,
  value = attempt count) alongside the existing `retry_count_by_key`.

### Hook contract integrity

- `classify_feedback.py` — drop `"how"` keyword trigger; use word-boundary regex for all
  keywords; keyword set extended with `layer`, `boundary`.
- `protocol_contract.yaml` gains `version: 1`; `pathly_hooks.PROTOCOL_VERSION` constant
  cross-checked at import. Desync raises loudly.

### Hook deployment to Codex and Copilot VS Code

- `pathly-setup codex --apply` writes `~/.codex/hooks.json` with two `PostToolUse` entries
  under a `"pathly"` namespace key. Merge-safe: user hooks outside the `"pathly"` key are
  never touched. `--uninstall` removes only the `"pathly"` key.
- `pathly-setup copilot --apply` writes `.github/hooks/pathly-classify.json` and
  `.github/hooks/pathly-ttl.json` with platform-keyed commands (windows/linux/osx).
  `--uninstall` deletes both files.
- Codex `install.yaml` hook event updated from `post_tool_call` → `PostToolUse`; matcher
  added (`tool_name: apply_patch`).
- `docs/SECURITY.md` — new "Hook surface coverage" table documenting per-host deployment
  status; README links to it under Known Limitations.

### Skill system refactor (breaking rename)

- `scout-flow` renamed to **`scout-path`** across all adapters (claude, codex, copilot).
  `scout-path` is now properly installed via `scout-path_skill.yaml` — it was previously
  missing from all adapter manifests.
- `team-flow` renamed to **`team`** across all adapters and all skill content files.
  `/pathly team-flow` → `/pathly team`. Sub-skills follow: `team/build`, `team/discover`, etc.
- Build skill (`/pathly build`) no longer owns mode selection, commits, or PROGRESS.md
  updates. Those are the orchestrator's (`/pathly team`) responsibility.
- `/pathly team` now asks auto/manual mode once at entry, commits after BUILDING→REVIEWING,
  and marks PROGRESS.md DONE only after REVIEWING→TESTING (reviewer passed).

---

## 2.0.3 - 2026-05-12

- Fix Codex plugin installation by creating a real local marketplace copy and enabling `pathly@pathly-local` in Codex config.
- Use relative `./skills/` and `./agents/` paths in the Codex plugin manifest.
- Add regression coverage for Codex marketplace install, idempotency, and uninstall.

---

## 2.0.2 — 2026-05-12

- Add the PO phase to `team-flow/plan` so `PO_NOTES.md` is created before planner decomposition.
- Separate PO requirements authorship from planner decomposition and add `ARCH_QUESTION` escalation rules for planner and tester.
- Install a complete Codex plugin bundle under `~/.codex/plugins/pathly`, including plugin-local agents and skills, so Pathly can appear as a Codex plugin.
- Accept Codex skill metadata that uses `natural_language` instead of slash-command `invocation`.

---

## 2.0.0 — 2026-05-12

### Breaking changes

- **All skills now install as `pathly-*`** — installed slash commands are `/pathly-build`,
  `/pathly-retro`, `/pathly-explore` etc. instead of `/build`, `/retro`, `/explore`.
  If you had direct skill invocations bookmarked, update them to use `/pathly <subcommand>`.
- **`/pathly` is the single user-facing entry point.** Direct slash commands like `/build`,
  `/help`, `/start`, `/end` no longer exist after reinstall with this version.
- **Feature argument removed from invocations.** Commands that previously required a feature
  name (`/pathly retro my-feature`, `/pathly team-flow my-feature`) now auto-detect the
  active feature from `plans/*/STATE.json`. Pass a feature name only when you need to
  override auto-detection.

### New skills

- **`/pathly explore`** — codebase investigation via the new `explorer` agent (analyze →
  scout-flow → trace → conclude). Replaces the previous direct scout spawn.
- **`/pathly test`** — standalone acceptance test runner (tester + scout-flow pipeline).
  Previously only available inside `team-flow`.

### New agents

- **`explorer`** — three-phase agent (analyze / explore / conclude) that orchestrates
  scout-flow for codebase investigations. Spawned by `/pathly explore`.

### Improvements

- **Dispatcher now covers all subcommands.** `/pathly retro`, `/pathly archive`,
  `/pathly lessons`, `/pathly prd-import`, `/pathly team-flow`, `/pathly plan`,
  `/pathly review`, `/pathly test` are all properly routed. Previously these hit the
  catch-all and were misrouted through the director.
- **`build` and `storm` route directly** to their skills instead of going through the
  director first.
- **scout-flow integrated** into `explore`, `test`, and `team-flow/test` — all three now
  use the standard analyze → scout-flow → implement/test phases matching builder and reviewer.
- **Discovery path 4** in `team-flow` now routes through the `explore` skill (explorer +
  scout-flow) instead of spawning a scout inline.
- **`tester` agent** updated to use `phase: analyze` / `phase: test` protocol, matching
  the builder/reviewer/planner/architect pattern.
- **`help` menu** updated: `/pathly explore` and `/pathly test` added to all states;
  no-feature menu now offers explore as option 4.

### Migration

Run `pathly-setup --repair` after upgrading to reinstall skills with the new `pathly-*`
naming. Old skill directories (`build/`, `explore/`, etc.) will be replaced with the new
prefixed names (`pathly-build/`, `pathly-explore/`, etc.).

---

## 1.1.0 — 2026-05-11

- Add missing skill YAMLs for go, start, end, pause, help, meet across all adapters
- Add full skill set to codex and copilot adapters
- Sync README, flow diagram, and architecture with current skill set and install flow
- Document Windows broken-stub issue when pip-installing outside pipx
