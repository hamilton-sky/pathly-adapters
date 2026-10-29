# Changelog

## Unreleased

### Board — a chief agent that works the board through a gated API (chief-agent)

A person can now open a **chief** for a project: a long-lived interactive agent tab that reads the
board, posts goals and decisions, answers agents' questions and starts and stops runs, so the
person talks to one agent instead of driving every board call. The chief itself is not trusted: it
holds a run token, its only door to the server is the `pathly` command, and the server decides
every call by the tier the person gave it. Studio has no Chief button yet, so today it is opened
with `POST /chief/open`. Design: `pathly/features/chief-agent/spec.md`. It builds on the run
identity of role-read-policy.

- Open, close, session: `POST /chief/open` (`{project_root, engine, preset, prompt?, model?}`),
  `POST /chief/close` and `GET /chief/session?project_root=`. One chief per project (a second open
  is 409), and an agent's run token cannot open or close one. The claude tab runs `--restricted`
  with four tools (`Bash`, `Read`, `Glob`, `Grep`), no MCP server, `pathly *` allowed and `curl`
  and `wget` denied; a codex chief is read-only and records no typed messages, so it can relay no
  answer. The session ends when the tab exits, on close, or at the next server start. The prompt
  is pasted, not submitted: the style, the fixed `chief-connect` rules, `Your project root: <root>`.
- The claude chief starts with `--permission-mode dontAsk` (chief-autopilot 01): claude 2.1.310
  started it in auto mode, which ran `python3` without asking (spike 19). Now every call that would
  prompt is denied; `pathly` commands and claude's read-only commands still run.
- Tiers: `status` reads; `planner` adds posting and planning (goals, tasks, decompose); `operator`
  adds deciding, running, stopping and answering. A preset names the tier: the built-in `status`,
  `planner` and `operator`, or a saved `chief/<preset>` style by its front matter, else `status`.
  The built-in styles and the fixed rules ship in the package, so a saved style cannot drop them.
- Chief gate (`http_server/chief_gate.py`): a `before_request` hook that acts only on a `chief`
  token. `chief_routes.py` classes a call into one of seven actions and the gate answers 403
  `{error, action, tier, allowed}` unless the tier holds it. A route the table does not list is
  refused to every tier. Once the session is closed its token is 401, not anonymous.
- Identity: the token is role `chief` on the project board, minted at open and revoked at close.
  What the chief posts is stamped `chief` and must say `from: chief`. A run it starts gets its own
  worker token, as any run does.
- Cited answers: the chief never words an answer to an agent. It sends `cite=<id>` of a message
  the person typed in its tab (recorded by a `UserPromptSubmit` hook), and Pathly relays that
  message's text.
- Standing orders: `POST /comms/directives` (chief only) posts a decision with `binding = 1`. It
  goes into the prompts of the role it is addressed to (every role for `*`) and stays there after
  it is acknowledged, whatever the run's context toggles say.
- One project: every `project_root`, board scope, file path and run, goal, task or message id a
  write names must belong to the chief's project. Two settings limit a session, and only the
  person sets them, with `PUT /db/settings/<key>`: `chief.max_runs_per_session` (default `20`)
  counts every call that starts work, and `chief.max_cost_usd_per_run` (default `10.0`) is the
  most a start may state as its cost. Only `POST /runs` of a flow and the `retry` verb state a
  cost, so goal, board and task runs are bounded by the run count alone (a goal's own cap is
  `goal.max_cost_usd`, when the person has set it).
- `pathly api METHOD /path [json]` (the new `pathly` console script) sends one request with the
  tab's token and prints the answer, never the token.

What is refused: a call outside the tier, and any write the gate does not list (`/db/query`,
`/db/settings`, `/comms/edit`, `/comms/delete`, `/comms/hydrate`, the routes that force past a human
gate); an answer that is not a bare `cite`, or that cites a message from before the question, one
already used, the style prompt, a relayed prompt or another session's message; acknowledging an
escalation addressed to the human without a cite, or as anyone but `chief`; a flow start or retry
that states a cost above the ceiling, and any run start past the run limit (a start the route
itself refuses gives its slot back);
stopping or pausing another project's run; retiring a standing order as anyone but a live chief
run (another role's `supersedes` skips it with reason `binding`, `/comms/supersede` without a chief
token is 403, `/comms/delete` is 403 for everyone, `/comms/edit` is 409, and hydrating a
`BOARD.json` stores `binding = 0`); and the raw run token on any stream but `/events/spawn`.
`tests/comms_board/test_chief_acceptance.py` runs the main ones end to end against the real app
and supervisor with a fake spawn host; the rest are in `tests/http_api/test_chief_gate*.py`,
`test_chief_cited_*.py` and `tests/comms_board/test_binding_*.py`.

Three holes the chief would have walked through are closed, each with its own test: the
`TERMINAL_SPAWN` payload's `run_token` was sent to `/events/runner` and `/events/runs` clients,
which need no credentials, and is now stripped from both copies; `POST /db/query` accepted a
`WITH ... INSERT|UPDATE|DELETE`, which could write a row with a forged stamp, and now runs under
`PRAGMA query_only` (400); and `POST /comms/edit` kept the old author's stamp on the text it
replaced, and now re-stamps the row to the editor (a request with no token stores `none`).

Known limits, for round two and RRP-2b (the UI token): the raw run token is still sent to every
`/events/spawn` client, and one subscribed when a spawn starts can use it until the spawn ends. A
`human` message is what the hook endpoint recorded, not proof that a person typed it: an operator
chief can start a headless agent that runs as the same OS user and, if it reads the session's
secret file and claude session id, could post to `/chief/human-messages` itself, and, on a claude
that ignores `CLAUDE_CODE_DISABLE_CRON` (the chief's settings set it; measured on claude 2.1.304
only), a scheduled task in the project's `.claude` folder would be recorded as typed. That agent can also call
`/runner/agent-answer` with no cite, because the cite rule guards the chief's own token. A fresh
clone loses its standing orders (hydration never restores the flag), so the chief posts them
again, and until the UI token Studio can neither post nor retire one. Reads that name an id
(`GET /runs/<run_id>`, an artifact, a goal's tasks) and the fleet-wide totals of `GET /db/rollup`
are not bound to the chief's project. The Studio Chief button, the friendly `pathly` commands, the
overview and inbox calls and the cost of the chief's own token are round two. Every test fakes the
spawn host: none opens a real `claude`. Spike 19 part B put eight questions to a real claude by
hand (claude 2.1.310, macOS, 2026-10-26; `pathly/features/chief-agent/spike19-part-b-report.md`,
answered in `pathly/features/chief-agent/tasks/19-daycap-guard-coverage-spike.md`). Measured: the
hook records a typed message as `human` and the chief cites it, `pathly api` works from inside the
tab and a post carries the chief's stamp, an answer without a cite is refused (403) and stores
nothing, the run limit refuses the extra run (403, no run starts) and the chief tells the person,
the operator text leads to sensible first reads with no curl, and closing the chief makes its
token 401. The restricted flags do not hold as written: claude 2.1.310 started the chief in auto
mode (the argv passes no `--permission-mode`), and its classifier ran `ls`, `git status` and
`python3 -c` without asking; only `curl` was denied (`wget` was not tried). Still unmeasured: that
a cited answer reaches a waiting agent (the goal run's agent asked on the board and exited, so no
run waited), that the two switches are what stops the prompts nobody typed (the Bash tool offered
no background option and a scheduled task did not fire, but no chief without the switches was
tried), and whether daycap's guard fires on Pathly's headless spawns (part A was not run).

### Licensed under Apache-2.0

The repository now carries a `LICENSE` (Apache-2.0), declared in `pyproject.toml` (which also gets a description that
says what Pathly is, and `setuptools>=77` for the license metadata) and linked from the README. The readiness and
architecture docs name the current version.

### Headless runs prove a build is done instead of trusting the agent (build-proof)

A headless run used to advance on what its agents said: a builder wrote `RESULT: PASS`, completed
its tasks and moved on, and a reviewer resumed the builder's own conversation and read the
builder's summary of the work. Now the supervisor measures the project itself, at the points where
a claim used to be taken on trust. It judges the whole run since a run-wide `proof_base`, so a
builder fix round that runs inside REVIEWING, TESTING or after a goal-loop drain is judged too.
Design: `pathly/features/build-proof/spec.md`. The measuring is on by default in a git project and
needs no setting, except `command_gate` and the base smoke, which still wait for `verify.build` /
`verify.test` (and `verify.smoke`) to be configured.

What is now measured:

- Floor guard: `floor_gate` (`proof/floor.py` over `proof/tree.py` working-tree snapshots) scans
  the run's diff for a skipped, focused or deleted test, a silenced linter, an empty catch, a
  lowered threshold, a trivial assertion, edited lint/test/CI config, an edited plan file and an
  edited task text, and sends the builder back with `FLOOR_FAILURES.md`. It sits at
  `BUILDING->REVIEWING`, `REVIEWING->TESTING`, `TESTING->RETRO` and `->DONE` in `team` and
  `team-build`, and at the `goal-loop` join, so a builder that turns a red test command green with a
  skip is caught.
- Checks: a task's text can carry a ```` ```check ```` block (`$ <command>`, `exit`, `prints`). The
  supervisor runs it after the builder reports the task done, and a failing check is a failure
  whatever the builder reported. In `goal-loop` each task attempt is proven as it returns and a
  failure goes through the existing per-task retry with the real output (up to 4000 characters
  now, was 500); in `team` and `team-build` the `task_checks` gate runs each completed task's
  block once (`TASK_CHECK_FAILURES.md`). The planner now writes a `Check:` field per phase.
- Frozen task text: `claim_task` copies the text into the new `comms_messages.claimed_text`, and
  every proof runs from that copy, so a builder that rewrites its own task (or drops its check) is
  caught as a `task-edit` and the retry prompt shows the text it was claimed with.
- Scope: `scope_gate` now declares the claimed tasks' `files` as well as the plan's paths, exempts
  only what the builder stage may write, and no longer excuses the plan files, so a builder edit to
  `USER_STORIES.md` or `IMPLEMENTATION_PLAN.md` fails. It is wired into `team` and `team-build`.
- Reviewer no-change: the supervisor records the tree and `HEAD` around every stage spawn
  (`SPAWN_WINDOW`), and `reviewer_unchanged` parks the run for a human
  (`REVIEWER_CHANGED_FILES.md`) when a reviewer spawn changed a file other than `REVIEW.md` and its
  feedback files, or committed.
- Review packet: the reviewer's prompt carries the tasks' frozen text, the diff outside `pathly/`
  (3 lines of context, clipped to 48 KiB) and the supervisor's notes (task proofs, floor
  warnings), in place of the builder's `AGENT_DONE` summaries. The reviewer also opens a fresh CLI
  session instead of resuming the builder's (`SESSION` events carry `independent: true`), and the
  next same-adapter stage continues the reviewer's session.

What helps the agents: a DAG task's prompt gets `## Results of the tasks this one depends on` (each
direct dependency's latest result), and a retried task, and a builder given a feedback file, gets a
`## Root-cause debugging` guide (read the failure, reproduce it, fix the cause and never the check).

Run guard rails: before the first spawn of `team`, `team-build` or `goal-loop` the supervisor runs
`verify.smoke` (else `verify.build`), and a red base parks the run (`error_kind: base_red`, a human
escalation, nothing spawned; resuming it smokes again). A goal run's iteration cap is raised to
`tasks x goal.task_max_attempts x 4` as its DAG grows, and never lowered.

New settings and route: `floor.enabled` (`false`, `0` or `off` turns the floor guard off),
`verify.smoke`, and `POST /comms/tasks/floor-allow` `{message_id, allow, refreeze}`, the only way
to set a task's `floor_allow` list (the floor categories a human excuses for that task) or to
re-freeze its text; it answers 403 to a live run token. The new `comms_messages` columns are
`claimed_text` and `floor_allow`; the new events are `SPAWN_WINDOW`, `TASK_PROOF` and
`FLOOR_CHECKED`. `tests/fsm_flows/test_build_proof_acceptance.py` drives the real `team-build` and
`goal-loop` flows through `supervisor.start_run` with a scripted fake agent and shows each of
these, and a clean run reaching `done`.

Known limits: the proof raises the cost of cheating, it does not make it impossible (an agent with
a shell can reach the DB and the git object store, and a caller that drops its run token counts as
a human, as for `force_past_gate`). Early advance can leave a write after an agent's completion
report outside its spawn window, though the next gate's whole-run diff still sees it. Lane-parallel
goal-loop tasks share one working tree, so an undeclared write is blamed on every overlapping
task and a check can see another lane's half-done work (`WorktreeIsolation` is still a stub).
Check commands come from task text that agents write and run in the project root under the
server's account; a task's checks run once per completion, so a later regression is left to
`command_gate test`. The whole-run floor gates take the union of the claimed tasks' allow lists,
and a test edit by the tester that trips the floor goes to the builder. Snapshots leave
unreachable objects in `.git/objects` until `git gc`. A fresh reviewer session costs tokens.
Headless runs never write `retry_count_by_key`, so the FSM retry ladder never climbs (a first-round
feedback prompt names its file and shows its text in a `## Feedback to resolve` block instead).
Studio has no control for the allow list yet (use `curl`). An interactive `/pathly` run records no
`SPAWN_WINDOW`, so `scope_gate` cannot judge a path that was dirty when BUILDING began,
`reviewer_unchanged` skips there, and `floor_gate` cannot tell which role wrote a plan file: it
excuses one a role may write (with a `FLOOR_CHECKED` warning), so a plan edit by the builder goes
unseen in such a run.

### Board — run identity and authorship provenance (role-read-policy)

Runner, board and goal spawns that the supervisor drives now get a server-issued identity, and
a board post made with it is stamped with the role that really wrote it. Until now a post's
author was whatever its `from` field said, so "independent review" rested on the reviewer's
prompt, not on the board. Spawns the supervisor does not drive (Studio's one-shot editor
actions and manual interactive tabs, `pathly-run`) get no identity, and neither do Studio's own
posts; a post without one is stored as unverified (`none`). This is the identity half only:
**this change withholds nothing from any agent.** Design:
`pathly/features/role-read-policy/SPEC.md`.

- Run token: each runner, board and goal spawn the supervisor drives mints a random token at
  the spawn chokepoint (`supervisor/terminal_identity.py`; best-effort, a failed mint still
  lets the spawn go out). It is stored hashed in the new `run_tokens` table with the run's id,
  role and board scope, sent as `run_token` in the `TERMINAL_SPAWN` payload, exported to the
  agent as `PATHLY_RUN_TOKEN` by both spawn hosts (Studio and `pathly-pty-host`), and revoked
  when the spawn ends. The `TERMINAL_SPAWN` payload carries the raw token and
  `_broadcast_runner` sends it to every `/events/spawn` client only: the copies for the topic's
  `/events/runner` clients and the run's `/events/runs` clients have the `run_token` key removed.
  A client subscribed to `/events/spawn` when the spawn starts can still read the token and use
  it until the spawn ends (that stream needs no credentials; closing it needs the UI token).
- `X-Pathly-Run-Token`: every `curl` to `8765/comms` in the core skills, fragments and the
  evaluator agent sends it (a consistency test fails on one that does not).
  `http_server/run_identity.py::caller_identity` resolves it to a run, or to `anonymous` when
  it is missing, unknown or revoked, and never reads the body's `role`, `run_id` or `from`.
- `comms_messages` gains `author_role`, `author_run_id` and `author_source`
  (`token | system | legacy | none`), stamped by the server when a board route or server code
  posts a row: a post with a live token is stored with that run's role whatever its `from`
  says, server-written lines are `system`, a post with no live token is `none`, and rows that
  predate the upgrade are backfilled as `legacy`. The body's `from` and `run_id` are still
  stored as sent and never decide a new post's stamp: `from` still gates writes to the project
  and global boards, and `run_id` still correlates the post to a run.
- New `runner/read_policy.py`: the role read wall written once, as a pure `row_allowed` and an
  equivalent SQL `policy_predicate`, with built-in defaults for `reviewer`, `tester`, `chief`
  and `anonymous`, and `resolve_read_policy`. Tests keep the two forms in agreement, and
  `tests/comms_board/test_rrp_acceptance.py` drives a spawn through to a stamped post and the
  policy over it (the spawn host and the agent are faked).

No change to which rows any agent can read: no production code calls the policy
(`retrieve_board_context`, `POST /comms/search` and `GET /comms` select the same rows as
before), so a reviewer still reads the builder's posts. `POST /db/query` runs its statement under
`PRAGMA query_only`, so a `WITH ... INSERT|UPDATE|DELETE` is refused with a 400 instead of writing
a row with a forged stamp. Known limits: Studio's own posts carry
no token yet and are stored `none`; the agent `curl`s to `/code/query` and `/record_phase` send
none; roles are minted from a flow's `agent_map`, which differs from its `role_map` in some
states; and a board restored from a `BOARD.json` snapshot (`POST /comms/hydrate`) keeps the
`author_role` and `author_run_id` written in the file (any `author_source`
other than `none` is stored as `legacy`). Not included: wiring the policy into the read paths,
`(board, scope)` pair binding, the UI token.

### Code intelligence — `codeintel` backend for `/code/query`

- New `code_context.backend` value `codeintel`: `/code/query` hands the requested op to the
  installed codeintel package (`pip install codecortex`) and returns its real answer —
  caller/callee/impact rows marked `resolved` vs `name-matched`, LSP symbol lookups and
  semantic `search` — instead of the per-file symbol-count block the `cli`/`lsp` backends
  return for every op. Pathly calls a running `codeintel serve-http`
  (`code_context.codeintel_url`, default `http://127.0.0.1:8766`), else one-shot
  `codeintel query --json`; codeintel's `reason`/`hint` pass through.
- `auto` now prefers codeintel when it is on PATH; machines without it behave as before.
- New ops `callees` and `search`; `engine` is forwarded to codeintel
  (`graph|lsp|semantic|both|all`), and `engine: cli` still reaches the legacy graph.
- Prompt injection (`build_block`) still uses the `cli` file-structure block.

### Telemetry — cached tokens priced at cache rates

Estimated costs (every codex run, and claude runs whose CLI reported no dollar figure) priced
cached input tokens at the full input rate, overstating a heavily-cached codex run ~3-4x.
`parse_result` now returns the cached subset of `tokens_in` (`cache_read_tokens` /
`cache_write_tokens`), every billing path carries it on `BILLING_UPDATE`, and
`db/pricing.py::CACHE_RATES` prices it (claude read 0.1x / write 1.25x; GPT-5 family cached
0.1x). Models without a verified cache rate keep the flat price. Provider-reported costs are
unchanged.

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

### Supervisor — ONE drain shared by both frontier callers

`supervisor/drain.py::drain_frontier` is now the single `scheduler_loop` call site. The two
paths that drive the DAG frontier — an FSM stage with `parallel_states`, and the
`executor: loop` goal drain — each carried their own copy of the same scaffolding, which is
how two paths drift: a fix to one silently misses the other.

- The shared helper owns the `CostCapTracker`, wraps `spawn_fn` with it **exactly once** (a
  second wrap would double-count every task's cost), and folds `tracker.exceeded()` into
  `abort_check` — so neither caller can forget the cost cap. What genuinely differs stays
  with the callers: the isolation, their own abort reason, and the result shape.
- **`executor: loop` gains the same audit-gated parallelism** an FSM fan-out stage has,
  replacing a hardcoded `SerialIsolation()`. On a DAG with no declared footprints — every DAG
  today — that is exactly the isolation it replaced, so the fast path cannot behave worse; it
  gets faster once a planner declares lanes and footprints.

**`executor: loop` is NOT retired**, and the fan-out plan's Phase E is not the deletion it was
scoped as. `loop` (a flat drain: `development/execute-task` per task, no review/test/retro, no
gates) and `team` (the full `team-build` FSM with two `command_gate`s) are different products,
not two implementations of one — collapsing them would delete the fast path a user chose for
speed and cost, and `'flow' | 'loop' | 'single'` is a Studio-visible category. It is also
addition rather than removal: `_run_loop` owns its own board-lock lease, goal storage
resolution, goal trace/span telemetry, the `run_history` `goal-loop` parent row that folds
`sched-*` rows into one run in `GET /runs`, `verify_clean_drain`, the cost tracker, and the
Monitor's run-type bucketing — none of which the FSM path provides.

Also corrected from the Phase D notes above: opting a flow into `parallel_states` does not only
change review cadence, it changes **which skill runs the work**. `fan_out._drain` never uses the
stage's own `instructions`, so a parallel `BUILDING` bypasses its `agent_map` entry entirely and
`team/build` never runs.

### FSM — `executor: loop` is an FSM flow; the second engine is retired (Phase E)

`executor: loop` no longer bypasses the FSM. It used to build its own `RunnerState` and drive
`scheduler_loop` top-level, as a peer of `orchestrator._loop` — the last rival engine the
fan-out feature exists to remove. It now runs a new packaged flow, **`goal-loop`**, whose
single `DRAINING` state declares `parallel_states`, so the same scheduler drains the same
frontier as the executor *of a state*.

**The product is unchanged.** Phase E was scoped as "`executor: loop` means run the flow whose
BUILDING is parallel" — i.e. `team-build`. That would have handed a user who picked `loop` for
speed a fully reviewed pipeline, because `loop` is a FLAT drain (`development/execute-task` per
task, no REVIEWING/TESTING/RETRO between tasks) and `team-build` is not. So `loop` got its own
one-state flow instead of someone else's. It is the ENGINE that was retired, not the fast path.

What a goal run gains, all of it from the DB being the authority — the same list the reverted
compiled executor was argued on:

- a `fsm_state` row, so `pathly-status` and the `STATE.json` export can see the run;
- a `STATE_TRANSITION` audit trail;
- park/resume on a human checkpoint;
- the escalation ladder (rounds 1-2 builder → round 3 planner → round 4+ human);
- the two verify commands as **routed** gates. `goal_verify.verify_clean_drain` ran the same
  `verify.build` / `verify.test` after a clean drain, but could only post a board escalation and
  stop; a `command_gate` failure re-drives a fix through `feedback_routing`.

The flow NAME is load-bearing, not cosmetic: `run_history` classifies a bare-uuid run whose
adapter column is `"goal-loop"` as a loop PARENT, and `start_run` writes `state.flow` there — so
a loop still shows as ONE run in `GET /runs` with its per-task `sched-*` rows folded in, and the
Monitor still buckets it as `loop`.

### Two prerequisite bugs Phase E would otherwise have shipped on top of

Both were found by checking the plan's assumptions against the code rather than taking them, and
either one alone makes Phase E a silent no-op:

- **The fan-out drained the wrong scope for a goal run.** `fan_out._drain` resolved the frontier
  from `state.topic`. For a plain feature pipeline the topic IS the board scope, so this was
  invisible — but a goal run's topic is its own storage slug (`features/<feature>/goals/<slug>`)
  while its tasks live on the parent board, and `get_ready_tasks` ANDs `scope IN (…)` with
  `goal_id`. Measured: **0 ready tasks found against 3 for the same goal.** Every goal run through
  a parallel flow would have "drained" nothing and advanced. The frontier now resolves through the
  same board-scope derivation the spawn chokepoint stamps telemetry with, and degrades to the
  topic. The join still agrees — `require_tasks_done` counts by `goal_id` when a run has one.
- **A DAG task's prompt was never placeholder-substituted.** `scheduler._worker` composed
  `development/execute-task` and stopped there, so `completion-report` reached the agent still
  telling it to key its `AGENT_DONE` on the literal string `<fsm_feature>` — a mis-keyed event,
  no projected invocation, the task unbilled and absent from the Monitor. This is the same defect
  `board_run._inject_board_prompt_vars` fixed for board runs and nothing had fixed on the DAG
  path; it was masked while the loop owned its own telemetry and wrote a synthetic `AGENT_DONE`.
  Prompt assembly moved to `supervisor/task_prompt.py`, which substitutes through the same
  injector the FSM and board paths use and stamps `run_category="loop"`.

### Fixed — stopping a goal run reported success while the run kept going

`POST /comms/goals/stop`'s FSM branch looked the run up by board scope, but a goal's FSM run is
registered under its board-nested topic — so the lookup found nothing and the route answered
`not_running` without stopping anything. This already affected `executor: team`; it would have
made a Phase-E `loop` run unstoppable. Runs are now resolved by their own `goal_id`, which is
correct whatever flow they run, with the scope lookup kept as the fallback for a non-goal run.

### Changed — a `loop` goal no longer writes an OTel goal root span

`write_goal_root_span` belonged to the retired engine. Per-task spans are still written, by the
FSM's own telemetry writer; what is lost is the labelled `goal:<id>` trace root, which
`executor: team` has never had either. The helper's own docstring calls this "no labelled root",
not lost spans.

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
