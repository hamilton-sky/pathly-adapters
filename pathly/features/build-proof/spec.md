# Build proof — Spec

## Problem

Pathly's headless runs take the agent's word that a build is done. A DAG task passes on the
agent's own `AGENT_DONE` outcome (`supervisor/scheduler.py::_outcome_is_failure`).
`command_gate` runs the project's real build and tests, so the cheapest way to get green is to
weaken the tests, and nothing looks for that. The planner's `Verify:` lines are never run.
`scope_gate` is wired into no packaged flow, and it exempts all of `pathly/features/`, so a
builder can rewrite its own plan or acceptance criteria. Nothing checks that a reviewer changed
nothing, and the reviewer reads the builder's self-report (the pipeline history block in
`fsm_compose.build_prompt`). Worse, in `team` and `team-build` both stages run on `claude`, so
the reviewer's spawn resumes the builder's CLI session (`supervisor/orchestrator_session.py::resolve_session`)
and holds the builder's whole transcript. `team/review.md` tells a reviewer sub-agent that has
no Bash to run `git diff`. Dependent tasks never get the results of the tasks they depend on. Retries get no
debugging method. A red base is blamed on the first builder. Goal runs use a fixed
`max_iterations=10` whatever the DAG size.

The assessment at `/mnt/project-files/feature-flow-assessment/what-pathly-can-borrow.md` found
all of this, comparing Pathly with feature-flow. Items 1 to 8 of that assessment are this
feature. The patterns come from a read-only clone of feature-flow at
`/home/claude/hamilton-sky/feature-flow`, which is MIT licensed. They are reused, never imported.

## Goal and the bar

Make a headless run prove that a build is done. It runs the floor guard, the task's own checks
and the reviewer no-change check itself. It freezes what the agent was asked to do. It tells
agents what they need: dependency results and a debugging method. It checks the base before
spending, and gives a run a budget that scales with its DAG.

**The bar.** `python -m pytest tests/fsm_flows/test_build_proof_acceptance.py -q -p no:cacheprovider`
passes. It drives the real `team-build` and `goal-loop` flows through `supervisor.start_run`,
with scripted fake agents in place of `_run_stage_via_terminal` and no model, and it shows each
of these:

- a builder that skips a test is sent back by the floor gate;
- a task that reports success but whose check block fails is retried with the real check
  output, and then fails;
- a builder that edits its own task text or the plan is caught;
- a reviewer that edits a tracked file fails the review stage;
- a red base blocks the run before any agent is spawned;
- a dependent task's prompt carries its dependency's result;
- a retry prompt carries the debugging fragment;
- a clean happy path reaches DONE.

The full pytest suite and the Lint commands stay green.

## Stories

### The floor guard

**As a** human supervising a headless run, **I want** the run to refuse a build that got green
by weakening the bar, **so that** green means the work was done.

- [ ] In `team` and `team-build`, a diff that skips, xfails, focuses or deletes tests, silences
      a linter or type check, adds an empty catch, lowers a threshold, adds an assertion that
      cannot fail, edits lint, test or CI config, or edits the plan is sent back to the builder
      with `FLOOR_FAILURES.md` naming each finding. The gate runs on every transition out of
      BUILDING, REVIEWING and TESTING and into DONE, over the whole run's diff, so builder fix
      rounds inside those states are judged too.
- [ ] In `goal-loop`, the same findings in one task's diff fail that task attempt, and the
      finding goes into the next attempt's prompt.
- [ ] In `goal-loop`, the join (`DRAINING->DONE`) runs the same gate over the whole run's diff,
      so a builder fix round after the drain, or a weakening a failed attempt left in place, is
      sent back to the builder.
- [ ] A task whose text was changed after it was claimed is caught (`task-edit`).
- [ ] A human can allow categories for one task. An agent run token cannot.
- [ ] The app setting `floor.enabled` set to `false` turns the guard off.

### Checks the supervisor runs

**As a** human, **I want** each task's own check block run by the supervisor after the task
reports success, **so that** "done" is measured rather than reported.

- [ ] A failing check in `goal-loop` fails the attempt. The retry prompt carries the command,
      what was wanted, what happened and the end of its output. When attempts run out, the task
      fails and an escalation is posted.
- [ ] A failing check in `team`/`team-build` sends the builder `TASK_CHECK_FAILURES.md`.
- [ ] A task completed in a builder fix round (`INCOMPLETE_TASKS.md` in REVIEWING or RETRO, or
      after the goal-loop drain) has its checks run at the next join: `REVIEWING->TESTING`,
      `->DONE` or `DRAINING->DONE`. Each completion's checks run once.
- [ ] A task without a check block is not failed. The skip is recorded for the reviewer.
- [ ] Checks run from the text the task had when it was claimed, not from the live text.

### Scope

**As a** human, **I want** `scope_gate` to catch a builder that strays, including into the
plan, **so that** the plan and acceptance criteria stay what was approved.

- [ ] `scope_gate` runs in `team` and `team-build`. The scope is the claimed tasks' `files`
      plus the paths named in `IMPLEMENTATION_PLAN.md`.
- [ ] Only the files a stage is meant to write are exempt under `pathly/`, not all of
      `pathly/features/`.

### An independent reviewer

**As a** human, **I want** a reviewer that judges the diff against the task without the
builder's account and without touching the code, **so that** review is a second opinion.

- [ ] A reviewer spawn that changes a tracked file or moves `HEAD` parks the run with a human
      escalation (`REVIEWER_CHANGED_FILES.md`).
- [ ] The REVIEWING prompt carries a Review packet: the claimed task text, the diff of the last
      build and the supervisor's notes. It does not carry the builder's `AGENT_DONE` summaries.
- [ ] The REVIEWING spawn opens a fresh CLI session. It never resumes the builder's session,
      even when both stages run on the same adapter.
- [ ] `team/review.md` never asks a no-Bash reviewer to run `git diff`.

### Prompts that help

**As a** builder agent, **I want** my dependencies' results and, on a retry, a debugging method,
**so that** I do not redo or guess.

- [ ] A DAG task's prompt lists each direct `depends_on` task's latest `AGENT_DONE` summary.
- [ ] From the second attempt on, a DAG task's retry prompt, and every builder feedback prompt in
      `team`/`team-build`, carry the `root-cause-debug` fragment.

### Guard rails on the run

**As a** human, **I want** a red base caught before any spend, and a run budget that fits the
DAG, **so that** failures are blamed correctly and big DAGs are not cut off at 10 iterations.

- [ ] Before the first spawn of `team`, `team-build` or `goal-loop`, the supervisor runs
      `verify.smoke` (else `verify.build`). On failure the run parks (`error_kind: base_red`)
      with a human escalation, and nothing is spawned. With neither setting, the check is skipped.
- [ ] A goal run's `max_iterations` grows to
      `tasks × goal.task_max_attempts × (MAX_FEEDBACK_ROUNDS + 1)` when that is larger, and is
      recomputed after every stage. Cost caps are unchanged.

## Scope

In: items 1 to 8 of the assessment, server side only. That covers `src/pathly_orchestrator`
and the skills, fragments and flows in `src/pathly_data`, with the living docs (root
`CLAUDE.md`, `src/pathly_orchestrator/CLAUDE.md`, `src/pathly_data/CLAUDE.md`) updated in the
same ticket as the code they describe.

Not in scope (from the brief): test-first proof; a quick versus full test command; size-based
single review; splitting review into spec and quality passes; installer per-file hashes; a run
report; Studio graph replay and any Studio UI change (the floor-allow route has no Studio button
yet, and Studio's FlowWizard gate list stays as it is); a plan-reviewer role; builder learnings;
anything in the chief-agent plan; feature-flow's HANDOFF lines, session tokens and flow-trust
loader. Also not here: `WorktreeIsolation` (still a stub in `supervisor/isolation.py`), and the
headless `retry_count` gap described in map.md § Open questions.

## Happy path

1. A human starts a `team-build` goal run → `start_run` runs `verify.build` once (exit 0) →
   the run starts and the FSM enters BUILDING. `fsm_ops.next_action` stamps `proof_base` (kept
   until DONE) and `build_baseline.tree`.
2. The builder claims task T (`claim_task` freezes `claimed_text`), edits the files T declares
   and completes T → the supervisor records a `SPAWN_WINDOW` event for the builder spawn.
3. BUILDING→REVIEWING gates: `command_gate` build passes; `floor_gate` finds nothing;
   `task_checks` runs T's check block from `claimed_text` (exit 0) and records a passing
   `TASK_PROOF`; `scope_gate` finds every changed path inside T's `files` or the stage's own
   writes → REVIEWING.
4. The reviewer's spawn opens a fresh session (no `--resume`, although the builder's ran on the
   same adapter). Its prompt has the Review packet (T's frozen text, the diff since
   `review_base`, "checks passed") and no builder summary. It writes `REVIEW.md`
   (`RESULT: PASS`). Its `SPAWN_WINDOW` shows only `REVIEW.md` changed.
5. REVIEWING→TESTING gates pass, including `floor_gate`, `task_checks` (T is already proven,
   so nothing runs) and `reviewer_unchanged` → TESTING → RETRO. RETRO→DONE runs `floor_gate`
   and `task_checks` once more → DONE, and `proof_base` is dropped.

Main failure path: in step 2 the builder adds `@pytest.mark.skip`. At step 3 `floor_gate` writes
`FLOOR_FAILURES.md` ("skip: tests/test_x.py: @pytest.mark.skip"). The supervisor routes it to
the builder with the `root-cause-debug` fragment in the prompt. The builder removes the skip and
fixes the code, and the gates pass.

## Edge cases

| Trigger | Expected behaviour | Handled in ticket |
|---|---|---|
| Project root is not a git repo, or git fails | Snapshots return `None`; floor, window, reviewer and per-task proof skip with a `GATE_SKIPPED`/log line (fail open, like `scope_gate`) | 02, 04, 05, 06, 09 |
| A repo index with unmerged entries | The snapshot works on a copy of the index after `git add -A`; if `write-tree` still refuses (it needs a fully merged index), `None` as above | 02 |
| Plan docs mention `@pytest.mark.skip` in prose | Pattern categories apply only outside `pathly/`; plan files are judged by `plan-edit` | 02 |
| Planner or architect routed a feedback file inside BUILDING edits `IMPLEMENTATION_PLAN.md` | Explained by their `SPAWN_WINDOW` (the file's current blob is what that role left), so neither `floor_gate` nor `scope_gate` blames the builder | 04, 06, 08 |
| Builder edits a plan file after the planner did | The current blob differs from the planner's after-blob → `plan-edit` finding | 04, 06 |
| Two lane-parallel goal-loop tasks overlap in time | Each task's diff leaves out paths declared in the `files` of the tasks it overlapped. Paths nobody declared count against every overlapping task (conservative) | 05 |
| A builder fix round after the goal-loop drain (`BUILD_FAILURES`, `TEST_FAILURES`, `INCOMPLETE_TASKS`) adds a skip that turns `verify.test` green | `floor_gate` on `DRAINING->DONE` diffs the whole run since `proof_base` → `FLOOR_FAILURES.md` → builder | 06 |
| An `INCOMPLETE_TASKS` builder fix round inside RETRO weakens a test | `floor_gate` on `->DONE` → builder | 06 |
| A goal-loop retry leaves an earlier attempt's skip in place | The retry's own diff does not show it; its prompt carries the earlier finding; the join's `floor_gate` catches it | 05, 06 |
| A task is first completed in a builder fix round (team flows, or after the drain) | `task_checks` on the next join (`REVIEWING->TESTING`, `->DONE`, `DRAINING->DONE`) runs its checks | 07 |
| A task's checks already passed (at an earlier gate, or inside the drain) | Not run again: a passing `TASK_PROOF` for its current `claimed_at` exists. A re-claimed task is run again | 07, 15 |
| A failed task is completed by a fix-round builder without a new claim | Its newest `TASK_PROOF` failed, so the join runs its checks | 07, 15 |
| A REVIEWING→BUILDING back-edge, or a resumed run | `proof_base` is kept, so the floor gate still sees the whole run | 15 |
| `project_root` is a folder inside a larger git repo | Snapshots return `None` (git would name paths from the outer folder); the proof gates skip and fail open | 02 |
| A task has no check block | Not failed; `TASK_PROOF` event with `checks: "none"`; the Review packet says so | 05, 07, 10 |
| A check block that cannot be parsed | The attempt fails with the parse error quoted. A human can fix the text and refreeze it through the floor-allow route | 01, 03, 05, 07 |
| A check that hangs | Killed at `verify.timeout_seconds` (default 600), reported as timed out | 01 |
| An agent edits task text through `/comms/edit` | `task-edit` finding unless a human allowed `task-edit` for that task | 03, 05, 06 |
| An agent with a run token calls the floor-allow route | 403, nothing stored | 03 |
| Unknown category in an allow list | 400 naming the valid categories | 03 |
| Reviewer edits only `REVIEW.md` and feedback files | Allowed (the reviewer's own writes) | 04, 09 |
| Reviewer commits (HEAD moves) | `reviewer_unchanged` fails → human | 09 |
| Builder and reviewer on the same resumable adapter (`claude` in `team` and `team-build`) | The reviewer spawn gets `session=None`, never `--resume <builder session>`; the `SESSION` event says `independent` | 16 |
| A reviewer asks a mid-run question | The answer re-spawn resumes the reviewer's own session, as for any stage | 16 |
| Resume of a run parked on a human checkpoint mid-build | No smoke on resume, so in-progress red work does not re-park it | 12 |
| Resume of a run parked as `base_red` | Smoke runs again | 12 |
| A goal-loop retry with the same check failing | Same retry path as any failure: attempts up to `goal.task_max_attempts`, then `fail_task` and an escalation | 05 |
| A diff too big for a prompt | The Review packet's diff and every report are clipped (head and tail) to stay well under Linux's per-argument limit | 01, 10 |

## Design

```
 start_run ──► base_smoke ──red──► park base_red + escalation
     │ green
     ▼
 _loop ──► next_action (stamps proof_base, build_baseline.tree)
     │
     ├─ single stage ──► spawn_window.observe ──► SPAWN_WINDOW
     │
     ├─ DRAINING ──► drain_frontier ──► task_proof.wrap(spawn)
     │                  │ success reported
     │                  ▼
     │             floor scan + task-edit + checks ──► TASK_PROOF
     │                  │ fail
     │                  ▼
     │             outcome failed ──► task_retry (real output)
     ▼
 complete_stage ──► run_gates (whole run since proof_base)
     floor_gate / task_checks / scope_gate / reviewer_unchanged
     │ fail
     ▼
 feedback file ──► builder fix spawn (+ debug guide, observed)
     │                 └─► next complete_stage re-runs the gates
     └─► human (reviewer changed)
```

Pure helpers sit in a new package, `src/pathly_orchestrator/proof/`. They are stdlib only,
take a project root and plain values, never import `db`, `runner`, `supervisor` or
`http_server`, and so sit outside the import-linter layers like `fsm/`:

- `proof/command.py`: run one command with no shell, a timeout and clipped output. It is
  extracted from `fsm/gates/command.py`, which then uses it.
- `proof/checks.py`: parse and run ```check blocks (port of feature-flow `proof.checks_in` and
  `run_checks`).
- `proof/tree.py`: git working-tree snapshots and diffs between them.
- `proof/floor.py`: the floor scan over a diff between two snapshots (port of feature-flow
  `floorguard.py`).

The FSM side gets three new gates and changes one. `fsm/gates/floor.py` (`floor_gate`),
`fsm/gates/task_checks.py` (`task_checks`) and `fsm/gates/reviewer.py` (`reviewer_unchanged`)
are new, and `fsm/gates/scope.py` is narrowed. They share `fsm/gates/_proof.py`, which knows
what each role may write and which `SPAWN_WINDOW` explains a change, and
`fsm/gates/_proof_record.py`, which stamps the run-wide `proof_base` and records and reads
`TASK_PROOF` events. The join gates run on every `complete_stage`, so a builder fix round
spawned while the FSM stays in a state (REVIEWING, TESTING, RETRO, or DRAINING after the
drain) is judged before the run can leave that state.

The supervisor side adds `supervisor/spawn_window.py`, `supervisor/task_proof.py`,
`supervisor/base_smoke.py` and `supervisor/run_budget.py`, and
`supervisor/orchestrator_session.resolve_session` opens a fresh session for the reviewer. The DB side adds
`db/queries/task_proof.py` and `db/queries/task_results.py`. A new blueprint,
`http_server/blueprints/comms/tasks_floor.py`, holds the human-only route.

### Decisions

- **Where a check block lives** — options: (A) a fenced ```check block inside the task `text`;
  (B) a new JSON `checks` column. Chosen: A. Why: the planner already writes task text, the
  snapshot of the text then freezes the checks too, and B needs `/comms/post` and schema changes
  in `messages_write.py`, which is at 400 lines. Every ```check fence anywhere in the text
  counts (task text has no `## Done when` heading). The grammar is feature-flow's: `$ <command>`,
  `exit <N>|nonzero` (default `exit 0`), `prints <text>`, `#` comments and blank lines.
- **How a check command runs** — options: (A) no shell, `shlex.split` or a JSON argv list, like
  `command_gate`; (B) `bash -c` like feature-flow. Chosen: A. Why: one way to run commands in
  Pathly, it works on Windows hosts without bash, and bandit stays clean. A command that needs
  `&&` is written as two `$` lines.
- **Where the snapshot lives** — options: (A) a `claimed_text` column filled by `claim_task` with
  `COALESCE(claimed_text, text)`; (B) a separate snapshot table. Chosen: A. Why: `claim_task` is
  the one chokepoint for the scheduler and `POST /comms/tasks/claim`, so team-flow builders
  (which claim with `run_id: "build"`) and DAG tasks are both covered. The `COALESCE` keeps the
  first snapshot across retries, so a builder cannot change the checks between attempts.
- **Who may set a floor allow list** — options: (A) a new human-only route that refuses any
  caller with a live run token (the `force_past_gate` precedent in `blueprints/core/fsm.py`);
  (B) a `Floor: allow` line in the task text, as feature-flow reads it from the ticket. Chosen:
  A. Why: task text on the board is written by agents, so B would let the planner grant the
  builder an excuse. The same route can `refreeze` (copy the live text into `claimed_text`), so a
  human can correct a broken check without allowing `task-edit`.
- **The per-task diff base in goal-loop (the brief's concurrency question)** — options: (A) a
  working-tree snapshot taken by the supervisor just before the task's spawn and just after it
  returns, with overlap handling; (B) `HEAD` at claim time; (C) only the task's declared
  `files`. Chosen: A. Why: B misses uncommitted work and sees other lanes' edits. C cannot see
  a test deleted outside the declared files. A is exact for serial drains, which is every DAG
  today: `AuditedLaneIsolation` stays serial unless every ready task declares `files`. When
  windows overlap, the paths declared by the other overlapping tasks are left out of this task's
  diff, and undeclared paths count against every overlapping task.
- **The diff base for the floor gate** — options: (A) a run-wide `proof_base {tree,
  started_at}` stamped on first entry to a state with an outgoing `floor_gate` or `task_checks`,
  kept across every transition and dropped only on entry to DONE, so every floor gate re-checks
  the whole run's diff; (B) a per-stage base. Chosen: A. Why: builder fix rounds run inside
  REVIEWING, TESTING, RETRO and DRAINING (feedback agents run while the FSM stays in the state),
  and back-edges (REVIEWING→BUILDING) would let a per-stage base drop changes. Re-checking
  passed changes is deterministic and cheap. Its `started_at` is also the task-check window.
- **Telling an upstream role's legitimate plan edit from the builder's** — options: (A) a
  `SPAWN_WINDOW` event per single-path spawn (role, tree before and after). A protected path is
  explained when its current blob equals the blob a window by a role allowed to write it left
  behind. (B) re-baseline the plan after any upstream feedback round. Chosen: A. Why: B would
  also excuse a builder edit made before the planner ran, and A also gives the reviewer gate its
  evidence for free.
- **What a reviewer may not change** — options: (A) any path whose content differs between the
  reviewer spawn's before and after snapshots, other than the reviewer's own writes, or a `HEAD`
  move; (B) only files git already tracks, as feature-flow's `tracked_clean`. Chosen: A. Why: in
  Pathly the builder's work is usually uncommitted at review time (`auto_commit` is off by
  default), so B would let a reviewer rewrite the builder's new files unseen.
- **What "without the builder's summary" removes** — options: (A) the two channels that carry
  the builder's self-report to the reviewer: the pipeline history block
  (`build_pipeline_history_block`, the `AGENT_DONE` summaries) in the prompt, replaced by the
  Review packet, and the builder's resumed CLI session, whose transcript ends with the same
  summary; (B) A, plus filtering builder-authored posts out of the reviewer's board context.
  Chosen: A. Why: both channels hand over the builder's own account. Board context is shared
  governance, and filtering by author would hide decisions the reviewer needs.
- **How the reviewer avoids the builder's session** — options: (A) a role rule in
  `resolve_session`: a stage whose role is `reviewer` never resumes the open session; (B) a flow
  YAML key (for example `fresh_session: [REVIEWING]`) that `resolve_session` reads. Chosen: A.
  Why: independence belongs to the reviewer role, so every flow with a reviewer stage (`team`,
  `team-build`, `test`) gets it without a flow edit. B needs a schema rule in
  `fsm/state.py::validate_flow_dict` and a YAML edit in each flow, a flow that leaves the key
  out would silently resume, and `resolve_session` would also need the flow config and state
  name, which do not fit the call in `orchestrator.py` (399 of 400 lines). The role comes from
  one helper, `fsm_compose_tables.agent_role_of`, which `build_prompt` (the Review packet) also
  uses, so the packet and the fresh session always pick the same stage.
- **The `team/build.md` and `team/review.md` sub-agent fixers** — options: (A) one sentence in
  `RUNNER_CONTRACT_BLOCK`: headless agents write the feedback file and stop, and the supervisor
  routes it; (B) delete the spawn sections from both skills. Chosen: A. Why: interactive
  `/pathly` still needs them, and the flows' `feedback_routing` already sends `IMPL_QUESTIONS` to
  the planner and `DESIGN_QUESTIONS` to the architect. Without it, a planner sub-agent's edit
  inside the builder's window would be a `plan-edit` finding.
- **When the debug guide is added** — options: (A) a DAG task's retry prompt from attempt 2, and
  every builder-targeted feedback prompt; (B) only when the FSM `retry_count` is above 0. Chosen:
  A. Why: headless runs never write `retry_count_by_key`, so B would never fire (map.md § Open
  questions). A feedback prompt is by definition a second attempt at the stage.
- **Where dependency results come from** — options: (A) the latest `AGENT_DONE` summary in
  `fsm_events` whose payload `run_id` is `sched-<dep id>#<n>`; (B) a new result column written on
  completion. Chosen: A. Why: no migration and no new write path, and `supervisor/terminal.py`
  already substitutes `<run_id>` with the spawn's run id.
- **The run budget** — options: (A) `max(max_iterations, tasks × attempts × (MAX_FEEDBACK_ROUNDS + 1))`
  for runs with a `goal_id`, raised after each stage and never lowered; (B) recompute exactly and
  allow lowering. Chosen: A. Why: a shrinking DAG must not cut a running run short, and runs
  without a goal keep the caller's cap. `MAX_FEEDBACK_ROUNDS` is the brief's "review rounds"
  (the supervisor's per-stage send-back limit).
- **Floor gate in goal-loop** — options: (A) per task inside the drain only (`task_proof`);
  (B) per task, plus the team flows' `floor_gate` on `DRAINING->DONE` over the whole run's diff
  since `proof_base`; (C) per task, plus a join gate that scans only the builder fix-round
  `SPAWN_WINDOW`s. Chosen: B. Why: A misses every builder fix round after the drain. When the
  join's `command_gate test` fails, `TEST_FAILURES.md` goes to a builder feedback spawn (as do
  `BUILD_FAILURES.md` and `INCOMPLETE_TASKS.md`), and that builder could add a skip, turn
  `verify.test` green and reach DONE. A also misses a weakening that a failed attempt left in
  place, because each attempt is judged on its own diff. B catches both and reuses the team-flow
  gate unchanged. Fix-round changes belong to that one builder, so sending them to the builder
  is right. C attributes a little more exactly, but needs a second gate mode and still misses
  leftovers of failed attempts. Per-task proof stays: it gives early feedback to the task that
  caused a failure, through `task_retry`. At the join, the human allow lists of the goal's tasks
  are unioned, as in the team flows.
- **When task checks run** — options: (A) at every join that can follow a task completion
  (`BUILDING->REVIEWING`, `REVIEWING->TESTING` and `->DONE` in the team flows, `DRAINING->DONE`
  in goal-loop), for tasks completed since `proof_base.started_at`, each completion run once:
  a task is skipped when its newest `TASK_PROOF` passed for its current `claimed_at`; (B) the
  same joins, re-running every task's checks each time. Chosen: A. Why: builders complete tasks
  in fix rounds. `require_tasks_done` routes `INCOMPLETE_TASKS.md` to the builder in REVIEWING,
  RETRO and after the drain, and `team/build.md` tells it to finish the task there. A covers
  those completions, and a long DAG's checks run once, not three times. A regression after a
  task's checks passed is left to `command_gate test`, which runs the whole suite at
  TESTING->RETRO and DRAINING->DONE. The window keeps tasks completed in earlier runs out.

## Interfaces

New modules (signatures are the contract; names inside may differ):

- `proof/command.py`: `CommandResult(code: int | None, output: str, timed_out: bool, error: str | None)`;
  `to_argv(command: str | list[str]) -> list[str]`; `clip(text: str) -> str` (head 3000 + tail
  5000, as `command_gate._clip` today); `run_command(command, cwd, timeout, extra_env=None) -> CommandResult`.
- `proof/checks.py`: `Check(command, exit=0 | "nonzero", prints=())`; `ParseError(ValueError)`;
  `checks_in(text) -> list[Check]`; `run_checks(checks, cwd, timeout) -> tuple[bool, str]`. The
  report has one block per failing check: `$ <command>`, `wanted: …`, `got: …` and the clipped
  output.
- `proof/tree.py`: `snapshot(root) -> str | None` (a tree id covering tracked and untracked,
  not ignored files); `head(root) -> str | None`;
  `changes(root, a, b, paths=None) -> list[tuple[str, str]]` (status, path; `--no-renames`);
  `diff_text(root, a, b, paths=None, exclude=None, unified=0) -> str`;
  `blob(root, tree, path) -> str | None`.
- `proof/floor.py`: `CATEGORIES = ("skip", "suppress", "empty-catch", "test-delete",
  "threshold", "trivial-assert", "config", "plan-edit", "task-edit")`;
  `parse_allow(value) -> frozenset[str]` (raises `ValueError` on an unknown name);
  `scan(root, base, after, *, allow, protected, may_change, config_commands) -> FloorReport(findings: list[str], warnings: list[str])`.
  `may_change(path) -> bool` excuses a protected path. Findings read `"<category>: <path>: <line>"`.
- `fsm/gates/_proof_record.py`: `wants_proof_base(flow_config, state_name) -> bool`;
  `stamp_proof_base(prior_state, flow_config, state_name, project_root) -> dict | None`;
  `read_proof_base(storage_path) -> dict | None`;
  `record_task_proof(storage_path, task, run_id, checks, floor, warnings=())`;
  `task_proven(storage_path, task) -> bool` (the newest `TASK_PROOF` for the task has its current
  `claimed_at`, `checks` `passed` or `none`, and `floor` not `failed`).

DB:

- `comms_messages.claimed_text TEXT` and `comms_messages.floor_allow TEXT` (a JSON list), added in
  `db/migrations_incremental.py`.
- `claim_task` sets `claimed_text = COALESCE(claimed_text, text)`.
- `db/queries/task_proof.py`: `get_task(conn, id)`;
  `tasks_claimed_since(conn, board, scope, goal_id, since)`;
  `tasks_completed_since(conn, board, scope, goal_id, since)`;
  `set_floor_allow(conn, id, allow, refreeze=False)`.
- `db/queries/task_results.py`: `latest_task_summaries(conn, task_ids) -> dict[str, str]`.

HTTP: `POST /comms/tasks/floor-allow` `{"message_id", "allow": [...], "refreeze": false}` →
200 `{"ok": true, "allow": [...]}`; 403 when the caller has a live run token; 400 for an unknown
category or a non-task; 404 when the task is missing.

Flow gates (YAML `type`, the feedback file in parentheses): `floor_gate` (`FLOOR_FAILURES.md`,
routed to builder); `task_checks` (`TASK_CHECK_FAILURES.md`, builder); `reviewer_unchanged`
(`REVIEWER_CHANGED_FILES.md`, human); `scope_gate` (`SCOPE_VIOLATION.md`, builder), where
`scope_file` becomes optional. Where each one goes: § Migration and compatibility.

Events (in `fsm_events` through `eventlog.append_event`):

- `SPAWN_WINDOW {role, run_id, state, before, after, head_before, head_after}`;
- `TASK_PROOF {task_id, claimed_at, run_id, checks: "passed"|"failed"|"none"|"error", floor: "clean"|"failed"|"off"|"n/a", warnings}`
  (`floor` is `n/a` when the team-flow `task_checks` gate writes it: the floor gate judges those);
- `FLOOR_CHECKED {warnings}`.

STATE (`fsm_state`) keys: `proof_base {tree, started_at}` (stamped on first entry to a state
with an outgoing `floor_gate` or `task_checks`; `tree` is `None` outside a git repo; kept across
transitions and dropped on the transition into DONE); `build_baseline.tree` (new key in the
existing stamp); `review_base` (the last BUILDING's tree, kept on BUILDING→REVIEWING).

App settings: `floor.enabled` (default on; `false`, `0` or `off` turns it off); `verify.smoke`
(optional).

Prompt blocks: `## Results of the tasks this one depends on` (DAG tasks); the
`root-cause-debug` fragment (`src/pathly_data/core/skills/fragments/root-cause-debug.md`);
`## Review packet` (REVIEWING).

Run status: parked with `error_kind: "base_red"`. `start_run(..., smoke_base: bool = True)`.

Sessions: `fsm_compose_tables.agent_role_of(agent: str) -> str` (`_SKILL_AGENT_ROLE`, else the
last `/` segment); `orchestrator_session.resolve_session(state, topic, preferred_adapter,
broadcast, stage_agent="")`, which returns `session_id=None` when `agent_role_of(stage_agent)`
is in `INDEPENDENT_ROLES` (`{"reviewer"}`); the `SESSION` event gains `independent: true` for
that case.

## Migration and compatibility

- Two additive columns; existing rows read `NULL` (no snapshot yet, no allow list). A task
  claimed before this feature has `claimed_text` `NULL`. Proof then falls back to the live text
  and skips the `task-edit` check for that task.
- Flows: new gates go after the existing ones in each transition list, so
  `tests/fsm_flows/test_two_flows.py`'s "`[0]` is the `verify_gate`" contract holds. The final
  order (where it says "the existing gates", each flow keeps its own):

  | Flow | Transition | Gates, in order |
  |---|---|---|
  | `team`, `team-build` | `BUILDING->REVIEWING` | the existing gates, `floor_gate`, `task_checks`, `scope_gate` |
  | `team`, `team-build` | `REVIEWING->TESTING` | the existing gates, `floor_gate`, `task_checks`, `reviewer_unchanged` |
  | `team`, `team-build` | `REVIEWING->BUILDING` | `reviewer_unchanged` |
  | `team`, `team-build` | `TESTING->RETRO` | the existing gates, `floor_gate` |
  | `team`, `team-build` | `->DONE` | the existing `require_tasks_done`, `floor_gate`, `task_checks` |
  | `goal-loop` | `DRAINING->DONE` | `require_tasks_done`, `command_gate` build, `command_gate` test, `floor_gate`, `task_checks` |

  `tests/comms_board/test_comms_goals_run.py` pins the goal-loop join's gate types; its
  expected set grows by the two new types (deliberate).
- `scope_gate` keeps its fail-open behaviour. The `pathly/features/` and `pathly/plans/`
  exemption tests in `tests/fsm_flows/test_gates.py` change to the narrower rule (deliberate).
- `team/review.md` and `planning/plan.md` change, so their golden snapshots in
  `tests/snapshots/` are regenerated from `compose_skill(skill, "claude")`.
- `fail_reason` keeps up to 4000 characters instead of 500, so a check report survives into the
  retry prompt.

## Risks

- Snapshots, `claimed_text` and `floor_allow` live in a DB and a git object store that an agent
  can reach through Python. This raises the cost of cheating; it does not make it impossible. The
  run-token check also cannot tell a human from an agent that drops its token header (same limit
  as `force_past_gate`). Named in `src/pathly_orchestrator/CLAUDE.md`.
- Early advance returns on `AGENT_DONE` before the process exits. A write after the agent's
  completion report can land after the window's "after" snapshot. The completion report is the
  agent's last act by contract. The next gate's whole-run diff still sees it, in the team
  flows and at the goal-loop join.
- Lane-parallel checks run while other lanes are mid-edit. A check can see another lane's
  half-done work. Today's DAGs drain serially; `WorktreeIsolation` is the real fix (out of scope).
- Snapshots write blob and tree objects into `.git/objects`. They are unreachable, so `git gc`
  prunes them after its grace period (two weeks by default). A repo with large untracked, not
  ignored files pays to hash them on every snapshot.
- Check commands come from task text that agents write, and the supervisor runs them in the
  project root with the server's environment. Builders already run arbitrary commands there, so
  this is not a new capability, but the run happens under the server's account. Documented with
  the gate.
- A test or tester edit in TESTING that trips the floor is sent to the builder, who did not make
  it. Accepted: it is rare, and the finding names the file.
- The whole-run floor gates (team flows, and the goal-loop join) take the union of the claimed
  tasks' human allow lists. A category a human allowed for one task is therefore also excused in
  a fix round or another task's file at those gates. Per-task proof in the drain still uses each
  task's own list. Named in `src/pathly_orchestrator/CLAUDE.md` with the route.
- A task's checks run once per completion. A later change that breaks a proven task's check is
  caught only by `command_gate test`, which is inert until `verify.test` is set.
- A fresh reviewer session costs tokens: the reviewer reads the code it needs instead of
  inheriting the builder's context. And `_loop` stores the reviewer's session as the open one,
  so the next same-adapter stage (TESTING, or the next task's BUILDING in `team-build`)
  continues the reviewer's conversation, not the builder's. Builder fix rounds are unaffected:
  feedback spawns already open fresh sessions.
