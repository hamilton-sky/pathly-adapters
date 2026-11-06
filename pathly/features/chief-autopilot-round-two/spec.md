# Chief autopilot, round two: agents answer agents — Spec

## Problem

The person wants a chief that carries a goal or a feature to done and "only stops for me when
only I can decide". Round one (`pathly/features/chief-autopilot/`, 14 tickets, PRs #110 to #123,
merged by 2026-11-02) made a claude chief safe to leave open and made a question to `human` park
its task until it is answered, for `single` and `loop` goals. It did nothing for the other kind of
question. The `consult` fragment (`src/pathly_data/core/skills/fragments/consult.md`) tells every
team agent to post a board `question` with `"to": "<role>"` (architect, designer, po, planner,
tester, reviewer) and "never block", but nothing answers it: the agent goes on with its fallback
assumption, the question rots on the board, and the person is the only one who could ever answer
it. `db/queries/task_waits.py::open_questions_by_run` even says so: role questions never park a
task, "nothing answers them until round two".

Round one also left gaps that make a parked or answered question misreport
(`/mnt/project-files/chief-autopilot/handoffs.md`): a parked goal-loop run writes no
`RUN_OUTCOME`, so `GET /runs/<id>` and `GET /chief/notices` show `error: null` (only
`/runner/status` says `waiting_for_answer`); the orchestrator broadcasts "continuing to the next
stage" just before the loop run parks; `park_task` returning False lets the task be completed with
no trace; `task_proof` still runs the floor scan and check blocks of an attempt that only asked; a
question answered between `open_questions_by_run` and `park_task` leaves the task parked on an
answered question; `chief_session_runs` grows forever and `GET /chief/notices` has no limit. And
the answer a chief relays is stored `author_source: none`, so the board cannot tell it from an
unverified post (spike 19 part B, proposed ticket 7). The first open of a never-trusted folder lost
the chief's pasted prompt to claude's folder-trust screen (proposed ticket 4). And the chief's hook
secret is a 0600 file under `~/.pathly/chief/<id>/` that every headless agent (run with
`--dangerously-skip-permissions`, same user) can read.

## Goal and the bar

A board `question` that a running agent addresses to a role is answered by a one-shot, read-only
headless agent of that role that Pathly starts itself (a **consult run**). The answer reaches the
asking task: a loop task waits for it and is run again in the same drain; a single run's task that
the agent left unfinished waits for it and gets it on its next run. Only questions for the person
reach the person: those addressed to `human`, those a role hands on with `ANSWER: USER`, those past
the caps (three routed questions per task, a per-goal consult cost line), and those whose consult
changed the project or did not answer. The chief sees the consult runs and which questions a role
answered and which wait for the person. A decompose cannot post a task without a check block or a
`Check: none <why>` line. Round one's question gaps are closed. A chief's first prompt is never
pasted into claude's trust screen, and no file holds the chief's hook secret (the strongest
measurable mitigation: same-user secrecy is impossible without OS isolation, and the plan says so).

**The bar:** `python -m pytest tests/comms_board/test_autopilot_round_two_acceptance.py -q -p
no:cacheprovider` passes with a fake spawn host, fake agents and the server in process (ticket 12,
built like `tests/comms_board/test_autopilot_round_one_acceptance.py`), covering: a loop goal and a
single goal each with a task whose agent asks the architect; one read-only architect consult run per
question, which answers; the loop task resumed in the same run with the answer in its prompt, the
single task parked and given the answer on its next run; a second question the architect hands on
with `ANSWER: USER` parking the task for the person and showing in `GET /chief/notices`; a fourth
routed question on one task going straight to the person; a consult agent that edits a source file
having its answer withheld and the task parked for the person; a parked loop run showing `error:
waiting_for_answer` in `GET /runs/<id>`; a decompose with a checkless task refused. And `python -m
pytest tests/ -q -p no:cacheprovider` passes in full.

## Stories

### A role answers the agent, not the person

**As** the person, **I want** an agent's question to the architect (or designer, po, planner,
tester, reviewer) to be answered by an agent of that role, **so that** a goal does not stop for me
over a design question an architect can settle.

- [ ] A `question` posted with a live run token and `to` one of the six roles starts one consult
      run of that role (`consult-<hex>`), with the question, the asking task's text and the board
      context.
- [ ] The consult's answer is posted on the board as `type: answer`, `reply_to` the question,
      `from` the role, stamped with the consult run.
- [ ] An architect, po or designer answer may add a non-binding `decision` row; nothing it posts is
      binding.
- [ ] A consult run is billed and listed like any other run, with run category and kind `consult`.

### Only what only I can decide reaches me

**As** the person, **I want** only the questions that need me to wait for me, **so that** the
chief stops for me only when it must.

- [ ] A consult that answers `ANSWER: USER <why>` hands the question to the person: the same row
      becomes `to: human`, and the task waits for it as round one's questions do.
- [ ] The fourth routed question on one task, any question past the goal's consult cost line, and a
      question to an unknown role go to the person without a consult run.
- [ ] A consult that changed a file outside the board's `feedback/` folder (or committed) has its
      answer withheld; the question goes to the person with an escalation that lists the changes.
- [ ] A consult that fails, times out or gives no `ANSWER:` line hands the question to the person.

### The answer reaches the work

**As** the person, **I want** a routed answer to reach the task that asked, **so that** the
question was worth asking.

- [ ] A loop task whose attempt asked a role is parked, released when the role answers, and run
      again in the same goal-loop run with `## Answers to your questions` in its prompt.
- [ ] A single run's task that the agent left unfinished after asking a role is parked; when the
      answer is there it is `pending` with `answered_questions`, and its next run sees them.
- [ ] Waiting never spends an attempt (round one's `attempts - waits`).

### The chief can tell me what happened

**As** the person, **I want** the chief's notices and run list to show consult runs and routed
questions, **so that** I know what was answered for me and what waits for me.

- [ ] `GET /runs` lists consult runs as `kind: consult`; a loop or flow parent's cost does not
      count them twice.
- [ ] `GET /runs/<id>` and each `GET /chief/notices` entry carry the run's `consults` (question,
      role, status) and how many questions wait for the person.
- [ ] A parked goal-loop run reads `outcome: failed`, `error: waiting_for_answer` in
      `GET /runs/<id>` and in its notice.
- [ ] An answer the chief relays is stored `author_source: chief_relayed`.

### Opening a chief keeps its prompt and its secret

**As** the person, **I want** a chief opened in a new folder to start with its instructions, and
its hook secret kept from the agents it starts, **so that** what the chief records as my words is
mine.

- [ ] A chief tab's first prompt is pasted only after claude's ready prompt, never into its
      folder-trust screen and never on a blind timer (Studio answers the screen: ticket 13, answer A).
- [ ] No file holds the hook secret; Studio's main process claims it once from the server and puts
      it only in the chief claude's environment; no other spawn gets it.
- [ ] The docs say plainly what stays readable to a same-user process and what a codex chief
      cannot promise.

### Plans carry their checks

**As** the person, **I want** a decompose that posts a task with no check to be told so, **so
that** every task the server proves has something to prove.

- [ ] A `type: task` post whose caller is a planner run token, with no ```check block and no
      `Check: none <why>` line, is refused 422 with the reason; nothing is stored.

## Scope

In:

- Question router, consult runs, answer delivery, `ANSWER: USER`, caps and cost line, non-binding
  decision rows, consult run category and kind (tickets 01 to 04, 10, 16, 17).
- Parking per executor and the loop drain that waits for consults (06, 07).
- Plan lint for decompose tasks (08).
- The chief's view: notices, run list, run detail, Operator text (09).
- Round one's question gaps: parked loop `RUN_OUTCOME`, the "continuing" warning, a silent
  `park_task` False, proving an asking task, the park/answer race (05); notices limit and pruning
  (09).
- Spike S7: chief-relayed answers stamped (11).
- Spike S4: the chief's first prompt is never lost to the trust screen (13 settles, 14 builds).
- The hook secret out of every file, claimed once, the residue said plainly (13 settled; 15 builds
  the server side, 18 the pty host, Studio's main process and the launcher's text).

Not in scope:

- **OS isolation of headless agents** (another uid, a container, a sandbox), which alone would keep
  the hook secret from every same-user process: platform work for a later round (ticket 13 says
  so to the person).
- Writing the person's `~/.claude.json` to pre-accept a folder: not done (ticket 13 chose A).
- Restarting an ended run after an answer (a single goal whose task waits must be started again by
  the person or the chief), the autopilot driver, grants and budgets in the launcher, notices in
  the chief's tab, the run record, time budgets: round four.
- Parallel lanes and worktrees: round three. Running a consult in its own worktree would make the
  read-only check exact; it waits for round three.
- An explicit answers block in team-flow stage prompts (see Decisions).
- S15, S16 (measurements only the person can make), chief engine billing, the run-token
  carry-forwards (`/events/spawn` token broadcast and the rest): round two does not depend on them.
- A real claude or codex in the acceptance test.

## Happy path

1. A loop goal runs. Task T's agent (`sched-T#1`) posts `{"type": "question", "to": "architect",
   "text": "...; I will proceed on X"}` with its run token and goes on.
2. The `/comms/post` after-request hook sees a role question from a run with a spawn host
   listening; `route_decision` says route (T has 0 routed questions, the goal is under its cost
   line). A `consult_routes` row is recorded and `start_consult` runs on a thread.
3. The consult run `consult-1a2b…` (role architect, category `consult`) reads the question, T's
   text and the board, writes nothing, and ends with an `AGENT_DONE` whose summary starts
   `ANSWER: use the existing queue`.
4. The tree did not change outside `feedback/` and the in-flight tasks' declared files, so the
   router posts the answer row (`from: architect`, `reply_to` the question).
5. `sched-T#1` ends. The scheduler parks T on its asked question and re-checks at once: the
   question is answered, so T is `pending` again with `answered_questions`, no attempt counted.
6. The scheduler claims T again as `sched-T#2`; its prompt has `## Answers to your questions`. T
   finishes; the goal-loop run ends `success`.
7. The chief's notice for the run lists one consult, `answered`, and 0 questions waiting.

Failure path: the architect ends with `ANSWER: USER the person must choose the vendor`. The router
makes the question `to: human` and posts the reason; T stays parked; the drain ends; the run ends
`error: waiting_for_answer` with a `RUN_OUTCOME`; the notice shows `waiting_for_person: 1`.

## Edge cases

| Trigger | Expected behaviour | Handled in ticket |
|---|---|---|
| A question to `human` or `*` | not routed; round one's park, unchanged | 01 |
| A question to `builder`, `director` or a made-up role from a run | goes to the person (`to: human`) | 01, 04 |
| A question posted with no run token (the person, an interactive session) | not routed, no park | 01 |
| A question posted by a consult run | never routed (no consult of a consult); left as posted | 01 |
| The fourth role question on one task | to the person, no consult run | 01, 04 |
| `consult.goal_cost_usd` reached, or set to 0 | every new role question of that goal to the person | 01, 04 |
| The same question posted to the hook twice (retry) | one route: `record_route` is insert-or-ignore on the question id | 01 |
| No spawn host listening when the question is posted | not routed, left as posted (the asking run itself needs a host, so only tests see this) | 04 |
| The server restarts with a route `queued` or `running` | at start the route ends `to_person` and the question goes to the person | 04 |
| The consult agent posts its own `type: answer` row (or calls `/comms/answer`) | 403, nothing stored: only the router's measured answer is delivered (see Decisions) | 17 |
| The consult's summary has no `ANSWER:` line, the spawn raises or times out | question to the person, route `failed` with the reason | 02 |
| `ANSWER: USER` with no reason | to the person with reason "no reason given" | 02 |
| The asking run ran on codex | the consult runs on codex with codex's model for the role (else codex's default) | 02 |
| The asking run has no adapter recorded, or one with no headless mode | the consult runs on claude | 02 |
| A tester or reviewer answer carries a `DECISION:` line | the decision line is ignored (only architect, po, designer post one) | 02 |
| The consult edits a source file, or commits | answer and decision withheld, question to the person, escalation lists the changes | 03 |
| A loop builder edits its declared files while a consult runs | those paths are left out of the consult's check | 03 |
| A builder edits a file outside every declared footprint while a consult runs | blamed on the consult: answer withheld (fails safe, the person decides) | 03 |
| The project is not a git repo | the check cannot measure; the answer is delivered with a status note saying it was not measured (fail-open, as `reviewer_unchanged`) | 03 |
| The answer arrives before the asking spawn ends | the park re-check releases the task at once; it is run again with the answer | 05, 06, 07 |
| The answer arrives between the read of open questions and the park | the re-check after `park_task` releases it | 05 |
| `park_task` returns False (the task was no longer `in_progress`) | a warning names the task, its status and the questions; the handler goes on as before | 05 |
| A loop attempt that asked reports success | no `TASK_PROOF`, no check runs; the next attempt is proven | 05, 06 |
| A loop drain ends with tasks waiting only on routed questions in flight | the drain waits for those consults (bounded), then drains again | 06 |
| A routed answer never comes (consult hung past its timeout) | the drain stops waiting; the run ends `waiting_for_answer` | 06 |
| A single run's agent asked a role and completed the task on its fallback | the task stays `done`; the answer is on the board only (enrich) | 07 |
| A single run whose parked task was released before the run settled | run error `answer_ready`: the task is `pending` with its answers, no attempt counted | 07 |
| A planner token posts a task whose check block does not parse | 422 with the parser's message | 08 |
| A person or chief posts a checkless task by hand | accepted, as today | 08 |
| `GET /chief/notices?limit=0` or `limit=x` | 400 | 09 |
| A read notice row older than 30 days | deleted the next time a run is recorded | 09 |
| The person answers in Studio (no token) | stored as before (`none`); only a chief's cited answer is `chief_relayed` | 11 |
| A chief opens in a never-trusted folder (current or old trust wording) | Studio answers the screen (ticket 13, A); the prompt is pasted after claude's ready prompt | 14 |
| claude never shows its ready prompt in a chief tab | nothing is pasted (no blind fallback); the person sees the tab | 14 |
| A same-user process claims the hook secret before Studio | Studio's claim is the second: the chief is closed (13 answer A); Studio refuses the spawn | 15, 18 |
| An agent calls `POST /chief/hook-secret` with its run token | 403 | 15 |
| A codex chief | no secret, no hash, nothing to claim | 15 |

## Design

```
 agent (run token) ─POST /comms/post question to:architect─► post_message
                                     │ after_request (consult_trigger)
                                     ▼
                         route_decision ──person──► hand_to_person
                                     │ route          (to: human)
                                     ▼
                         consult_routes row (queued)
                                     │ thread
                                     ▼
 start_consult ──TERMINAL_SPAWN consult-<hex>──► spawn host ─► architect
   │ tree before                                   AGENT_DONE summary
   │◄────────────── /runner/terminal/result ◄──────────┘
   │ tree after: changed outside feedback/? ──yes──► withheld,
   │                                                  to the person
   ▼ no
 parse summary: ANSWER: USER ──► hand_to_person
   │ ANSWER: <text>
   ▼
 post answer (reply_to) ──► release_on_answer ──► task pending
                                                   │
 loop: scheduler parks on asked q, re-checks ──────┤
       drain waits for consults, drains again ─────┘─► sched-T#2
 single: run end parks unfinished task, re-checks ──► next run
```

### Decisions

- **What triggers the router** — options: an `after_request` hook on `POST /comms/post` (the only
  route that posts a `question`), or a supervisor thread polling the board. Chosen: the hook, in a
  new `http_server/consult_trigger.py` registered in `app.py` like `chief_run_record`. Why: the
  answer can arrive while the asking agent still runs, there is no poll interval, and
  `messages_write.py` (400 lines) does not grow. The server drives, no chief turn (round one's
  spec). Poll rejected: it adds a thread and latency for nothing the hook misses.
- **How a consult is spawned** — options: `board_run.start_board_run` with a new skill (the brief's
  assumption), or a new `supervisor/consult_run.py` that builds its own headless `RunnerState`
  (`flow="consult"`) and calls `terminal._run_stage_via_terminal`, the way
  `board_run._default_spawn` does. Chosen: the second. Why: `start_board_run` takes the board
  lock, which the asking `single`/`loop` goal run already holds (`board_lock`, "a goal single/loop
  run holds its board"), so a consult would always get `board_busy`; and `board_run.py` is at its
  ratchet baseline (484 lines) and hardcodes `run_category="single"`. The new skill
  `planning/consult-answer` (composes `comms-post`, `completion-report`; `code-query` for code
  roles) is kept.
- **Where the answer comes from** — options: the consult agent posts its own `type: answer` row
  (as `consult.md` says today), or the agent writes the answer into its `AGENT_DONE` summary and the
  router posts the row after measuring the tree. Chosen: the router posts it. Why: a `type: answer`
  post frees parked tasks the moment it is written (`post_message` → `release_on_answer`), before
  any check of what the consult changed; the brief requires the answer not be delivered when the
  consult changed the project. The summary is already the authoritative semantic result (root
  `CLAUDE.md`, "AGENT_DONE.summary ... authoritative"). The skill tells the consult to post no
  answer row; an `answer` from a consult run token is refused 403 at `/comms/post` and `/comms/answer`
  (ticket 17) so a disobedient agent cannot get around the check.
- **Park or enrich, per executor** (the brief leaves this to the planner):
  - `loop`: **park**. The scheduler, not the agent, completes loop tasks, so it can hold any
    attempt that asked a role (answered yet or not) and run it again with the answer; the drain
    waits for in-flight consults before it ends (bounded by the consult spawn timeout), so a
    routed question does not stop the run. Enrich rejected: the attempt usually finishes on its
    fallback before the answer is used, and there is no next attempt to enrich.
  - `single`: **park when the agent leaves the task unfinished**, otherwise enrich. The drain-dag
    agent completes its own tasks; the server cannot un-complete one. The fragments tell it: when
    the answer decides how to build the task, post the question and leave the task unfinished;
    otherwise go on with the fallback. At run end an unfinished task whose run asked a role is
    parked and re-checked (released at once when the answer is there). The run still ends; starting
    it again is the person's or the chief's (round four restarts). Parking every asked task
    rejected: it cannot be done for a task already `done`.
  - team flow stages (`team`, `team-build`): **enrich via the board, no new code**. A stage spawn
    holds no task to park; the team flows already block on questions through feedback files
    (`ARCH_QUESTION`, `PO_QUESTIONS`, `DESIGN_QUESTIONS`, routed by the FSM), and the routed answer
    is a board row to the asking role. An explicit answers block in stage prompts is dropped
    (listed in the reply) because nothing in the bar needs it.
- **Handing a question to the person** — options: re-address the same row (`to_agent='human'`),
  or post a new `to: human` question. Chosen: the same row. Why: a parked task's reason names the
  question ids (round one's spec: "recorded as ids in the reason, so a later re-post ... is still
  matched by id"); the same id needs no re-link, and `open_questions_by_run`,
  `open_questions_on_board` and the cite rule all read it as a human question at once. A system
  `status` row replying to it records who handed it on and why.
- **What the read-only check blames** — options: every path that changed during the consult's
  window, or those minus the board's `feedback/` folder, Pathly's own exports and the declared
  `files` of every task `in_progress` at the window's start or end. Chosen: the second. Why: a
  single or loop builder runs while the consult runs; blaming its declared work would withhold
  most answers. A change outside every declared footprint is still blamed on the consult: it fails
  safe (the person decides). An own worktree per consult would be exact: round three.
- **Caps and cost** — options: count question rows, or a `consult_routes` table. Chosen: the table
  (one row per routed or handed-on question: role, task, goal, consult run, status, reason). Why:
  the caps, the drain wait, the notices and the startup cleanup all need the status, and a
  question row has nowhere to keep it. Settings `consult.max_per_task` (default 3) and
  `consult.goal_cost_usd` (default 2.0; 0 routes nothing), read with `app_settings.get_setting`
  like `goal.task_max_attempts`. The cost of a goal's consults is the sum of `agent_invocations`
  over its consult run ids; a question with no task goal counts against its asking run.
- **No spawn host** — options: hand the question to the person, or leave it as posted. Chosen:
  leave it. Why: the asking run needed a host to run at all, so in practice only tests lack one,
  and a change of `to_agent` there would rewrite rows other tests read.
- **Which engine and model a consult uses** — decided in the brief (2026-11-06): a consult runs on
  the adapter (engine) of the run that asked, with that adapter's model for the role, falling back
  to claude only when the asking run has none. The asking run's adapter is `run_history.adapter` of
  the question's `author_run_id` (every spawn writes it in
  `terminal_identity._record_spawn_identity`); it is used when `adapters.headless_capable(adapter)`
  is true, else `claude`. The model is `spawn_policy.effective_model(role, adapter, "")` (the role's
  configured model when it is for that adapter, the call board runs make); when that is empty, a
  claude consult uses `claude-sonnet-4-6` and any other adapter its engine's own default (an empty
  model drops `--model`, `adapters.resolve_command`). Rejected: every consult on claude, which
  would bill a codex person's goal on an engine they did not pick.
- **Where the plan lint runs** — options: refuse the post at `/comms/post`, or check the tasks
  after the decompose run ends and re-run the planner. Chosen: refuse the post (422). Why: the
  planner gets the reason while it still runs and can post again; a re-run costs a second
  decompose. "A decompose" is a caller whose live run token has role `planner` (both
  `planning/dag-sketch` and `planning/plan` board runs, and the consultation flow's planner stage);
  tokenless, chief and builder posts are unchanged (the brief's assumption).
- **Consult run identity** — run id `consult-` + 12 hex digits (like `chief-`), so
  `run_history_read._classify_kind` can name the kind from the id alone; `<run_category>`
  `consult`, the synthetic `AGENT_DONE`, the spawn payload's `category` and the invocation
  projection's guard accept it.
- **The trust screen (S4)** — options: Studio answers the screen and never pastes blind into a
  chief tab; the person answers it and Studio pastes after; the server writes
  `projects["<path>"].hasTrustDialogAccepted` into `~/.claude.json` (docs:
  https://code.claude.com/docs/en/permissions, "Project allow rules and workspace trust"). This
  changes what the person sees, so it was ticket 13's question 1. **Decided: A, Studio answers**
  (the brief's Decided line, 2026-11-06, recommended answer pending the person's tap): it does so
  for every interactive tab today, and a `--restricted`, `--strict-mcp-config` chief gains nothing
  from the trust. Rejected: B (the person answers once per folder), C (Pathly would write a file
  every running claude rewrites).
- **The hook secret** — same-user secrecy is impossible without OS isolation (`/proc/<pid>/environ`
  is readable by a same-uid process; map Decisions so far), so the mitigation is measured instead:
  no file holds it, the server hands it once to Studio's main process (tokenless `POST
  /chief/hook-secret`), which puts it only in the chief claude's environment, and the command hook
  reads it there (a command hook inherits claude's environment). Rejected: an `http` hook with
  `headers` and `allowedEnvVars` (docs-supported too) needs a new route and moves the tag rule to
  the server for the same exposure, since the secret is in claude's environment either way. What a
  second claim does was ticket 13's question 2. **Decided: A, a second claim closes the chief**
  (the brief's Decided line, 2026-11-06, recommended answer pending the person's tap). Rejected:
  B, refusing the second claim and leaving the chief open, which leaves a first claimer holding a
  working secret.
- **Chief-relayed answers (S7)** — options: `author_source: token` with role `chief`, or a new
  source `chief_relayed`. Chosen: the new source (the brief's wording). Why: `token` says the
  caller wrote the words; a cited relay carries the person's words, which only the new value says.

## Interfaces

- New table `consult_routes(question_id TEXT PRIMARY KEY, role, task_id, goal_key,
  asking_run_id, consult_run_id, status, reason, created_at, ended_at)`; `status` in `queued`,
  `running`, `answered`, `to_person`, `withheld`, `failed` (migration `db/migrations_consult.py`).
- New `db/queries/consult_routes.py`: `CONSULT_ROLES`, `route_decision`, `asking_task`,
  `record_route`, `set_route_status`, `hand_to_person`, `routes_for_questions`, `pending_routes`,
  `goal_consult_cost`, `consult_limits`, `end_stale_routes`.
- Settings `consult.max_per_task` (3), `consult.goal_cost_usd` (2.0).
- New skill `planning/consult-answer`; its summary format:
  `ANSWER: <text>` or `ANSWER: USER <why>`, optional `DECISION: <approach> — <why>`.
- New `supervisor/consult_run.py::start_consult(question_id, *, project_root, broadcast_fn,
  spawn_fn=None, block=False)`; new `supervisor/consult_window.py` (tree check);
  `supervisor/consult_router.py::on_question(...)`; `supervisor/consult_wait.py` (drain wait).
- Run id `consult-<12 hex>`, run category and run kind `consult`.
- `POST /comms/post` (`type: answer`) and `POST /comms/answer`: 403 from a consult run token; `POST /comms/post`: 422
  `{"error": "task has no check block", "reason": ...}` for a planner-token task without a check.
- `db/queries/task_waits.py`: `asked_questions_by_run`, `park_and_recheck`.
- Run error `answer_ready` (single run whose parked task was released at settle time).
- `RUN_OUTCOME` for a parked goal-loop run.
- `GET /runs`: `kind: consult` rows. `GET /runs/<id>` and `GET /chief/notices` entries:
  `consults: [{question_id, role, status, consult_run_id}]`, `waiting_for_person`.
  `GET /chief/notices?limit=` (1 to 200, default 50).
- `author_source` value `chief_relayed`.
- Studio: `EngineCategory` gains `consult`.
- `POST /chief/hook-secret` `{run_id}`: 200 `{hook_secret}` once, 409 after, 403 with a run token,
  404 for an unknown or closed session. Env var `PATHLY_CHIEF_HOOK_SECRET` (chief claude only); the
  hook loses `--secret-file`; no `hook_secret` file.

## Migration and compatibility

All additive: one new table, new settings with defaults, a new source value, a new category and
kind. Behaviour changes on purpose: a run's question to a role now parks a loop task (and a single
task the agent left unfinished) where round one completed or freed it; round one's two tests that
assert "a question to architect does not park" are updated in place (tickets 06, 07). A task text a
planner token posts without a check block was accepted and is now 422. An old answer row stays
`none`.

## Risks

- The chief's own Bash could print its environment — the settings deny `env`, `printenv` and
  `/proc` reads, and the chief gate refuses a body holding the secret; a re-encoded print is not
  caught (as today's file read was not).
- claude's current trust wording comes from a user's report, not from a claude measured here
  (map Decisions so far) — ticket 14 matches both wordings and records a fixture of the screen
  with its claude version, and a chief tab that never sees the ready prompt pastes nothing rather
  than paste blind.

- A consult adds cost without the person asking — the per-task cap, the per-goal cost line
  (setting 0 routes nothing) and the `consult` category in the Monitor bound and show it; tickets
  01, 02, 04, 16, 17 are level 3.
- False withholds when builders edit outside their declared `files` while a consult runs — the
  answer goes to the person (fails safe); round three's worktrees make it exact.
- A real claude may not follow the summary format — no `ANSWER:` line hands the question to the
  person; the person re-measures on a real claude (map Open questions).
- A loop drain waiting on a hung consult — bounded by the consult spawn's own timeout plus a
  margin, and the run's abort flag.
- Files at the 400-line limit (`messages_write.py` 400, `scheduler.py` 399, `orchestrator.py` 399,
  `terminal.py` 398, `run_history_read.py` 389, `comms_messages.py` 392) — each ticket says what
  to move out first; baseline files (`board_run.py`, `invocation_projection.py`) only get
  line-neutral edits.
