# Chief autopilot — Spec

## Problem

The Operator chief (chief-agent round one) can plan a goal, start runs, steer them and relay the
person's answers, but only while the person sits at the tab. Spike 19 part B
(`pathly/features/chief-agent/spike19-part-b-report.md`, 2026-10-26, claude 2.1.310) showed why it
cannot be left alone yet:

- The chief starts in claude's auto mode, so commands other than `pathly` run without asking, and
  its Grep and Glob tools are not denied the session folder that holds the hook secret. A chief
  that can read the hook secret can forge a "typed by the person" message and cite it.
- A headless agent printed its `PATHLY_RUN_TOKEN` into its own output.
- `POST /runs` with `kind: flow` opens an interactive tab that waits forever at claude's "Bypass
  Permissions" dialog, so the full pipeline cannot run unattended from the chief.
- A goal run whose agent asks a question on the board ends `done` / `success` while its task stays
  `in_progress`, and the answer never reaches an agent.
- Nobody is told when a run ends.

The person also wants the chief to carry a goal, or a whole feature, to done: decompose it, run
several agents (in parallel where the work allows), let agents answer each other's questions
(architect, designer, product owner) and only stop for the person when only the person can
decide. feature-flow (0.10.0 to 0.15.0) has working versions of three of the pieces Pathly lacks:
parallel lanes in git worktrees with an enforced file footprint, questions routed to a role agent,
and a per-run record of what each check caught.

## Goal and the bar

The whole feature is built in four rounds. This plan tickets round one; rounds two to four are
outlined in `map.md` and get their own folders (`chief-autopilot-round-two/` and so on) when
round one is resolved.

- **Round one: safe to leave alone.** The spike's security findings closed, a chief-started flow
  runs headless, a run cannot claim success over an unfinished task, an agent's question parks its
  task until it is answered and the answer reaches the next attempt, and the person is told when a
  chief's run ends.
- **Round two: agents answer agents.** A board question addressed to a role is answered by a
  one-shot agent of that role; only questions for the person reach the person.
- **Round three: parallel lanes.** Tasks with disjoint declared files build at the same time in
  the shared tree; a task that overlaps a running one builds in its own git worktree and is merged
  and gated after. Every task is held to its declared files.
- **Round four: the autopilot.** The person grants one goal (or one feature's goals) a budget in
  the chief launcher's Autopilot fields; the server carries it to done or to a hard stop, and
  keeps a record of the run.

**Round one's bar:** `python -m pytest tests/comms_board/test_autopilot_round_one_acceptance.py -q
-p no:cacheprovider` passes with a fake spawn host and a fake claude (see ticket 09), and
`python -m pytest tests/ -q -p no:cacheprovider` passes in full.

## Stories

### Leave the chief running

**As** the person, **I want** to leave an Operator chief open while a goal runs, **so that** I do
not have to watch the tab for it to be safe.

- [ ] The chief's claude runs only `pathly` commands; anything else is denied, not asked and not
      approved by auto mode.
- [ ] Nothing the chief can run or read shows it the hook secret.
- [ ] No run token Pathly stores or shows (stdout tail, summaries, board rows) contains a raw run
      token.

### Run the full pipeline from the chief

**As** the person, **I want** "run the team flow on this feature" to start planner, designer,
builder, reviewer and tester without a dialog, **so that** the pipeline runs while I am away.

- [ ] `POST /runs {"kind": "flow"}` starts a headless run.
- [ ] `GET /runs` reports that run's kind as `flow`.

### Questions do not dead-end

**As** the person, **I want** an agent's question to wait for an answer instead of being lost,
**so that** the answer I give in the chief tab reaches the work.

- [ ] A single or loop run whose agent asked a question and exited leaves its task `blocked`
      waiting for that question, and the run's outcome is not `success`.
- [ ] Answering the question makes the task ready again, and its next prompt carries the question
      and the answer.
- [ ] A run whose agent exits with its task still `in_progress` and no question reports
      `outcome: failed`, so the existing retry takes over.

### Know when a run ends

**As** the person, **I want** the Chief button to show that a run the chief started has finished,
**so that** I know to come back and read the result.

- [ ] Each run a chief session starts is recorded against that session.
- [ ] `GET /chief/notices?project_root=` lists that session's runs that ended since last read,
      with status, cost and the number of questions waiting.
- [ ] The Chief button shows a count of unread notices.

## Scope

In (round one): spike 19 proposed tickets 1, 2, 3, 5, 6, 8, 9, 10, 11, 12 and part 1 of its
"Plan discussed" (notify the person, not the chief).

Not in round one:

- Spike ticket 4 (the trust dialog on first open): the person is present when a chief opens, so
  it does not block unattended work; round two's list.
- Spike ticket 7 (stamp a chief-relayed answer on the board row): audit only; round two's list.
- Spike tickets 15 and 16 (cron positive control, `ls` printing nothing): measurements on the
  person's machine, not code; round two's list.
- A notice typed into the chief's tab (spike "Plan discussed" part 2): round four, where the
  autopilot needs it.
- Question routing to role agents: round two. Worktree lanes: round three. Grants, budgets and
  the run record: round four.

## Happy path (round one)

1. The person opens an Operator chief. It starts with `--permission-mode dontAsk`; `ls` is denied.
2. The person asks for a goal run. The chief posts the goal and tasks and starts the run.
3. The run's agent posts a question and exits. The run ends `failed` with reason
   `waiting_for_answer`; the task is `blocked` on that question.
4. The Chief button shows "1". The person opens the tab and asks what happened; the chief reads
   `GET /chief/notices` and the question, and the person answers in the tab.
5. The chief relays the cited answer. The task is `pending` again. The person says "carry on"; the
   chief starts the goal again and the task's prompt carries the question and the answer.

## Edge cases

| Trigger | Expected behaviour | Handled in ticket |
|---|---|---|
| claude version without `dontAsk` | claude exits on the unknown value and the tab shows its error; the chief never starts in auto mode | 01 |
| `pathly api POST ... - < ~/.pathly/chief/<id>/hook_secret` | refused by claude (the redirect is not `pathly *`) or, if claude allows it, the posted text is redacted; measured and pinned by a test of the settings | 02 |
| A token is printed in the middle of a long line | the stored copy shows `[run token]` in its place | 03 |
| A flow run started by Studio's Start button | unchanged: Studio passes `interactive` itself | 04 |
| An agent asks two questions and exits | the task waits for both; it is ready when the last is answered | 06 |
| A question is answered after the task was deleted | the answer is stored; nothing else happens | 06 |
| The chief session closes before its run ends | the notice is kept for the next chief of that project | 08 |

## Design

```
 chief tab ──pathly api──► chief gate ──► POST /runs ──► start_run (interactive=False)
                               │                │
                               │ record run_id   ▼
                               ▼            run ends ──► terminal_reconcile
                      chief_session_runs        │  task still in_progress?
                               │                │  question asked? ─► task blocked(question)
                               ▼                ▼
             Studio Chief button ◄── GET /chief/notices
```

### Decisions

- **Where the chief is locked down** — options: claude's `--permission-mode dontAsk`, or keep auto
  mode and add deny rules for every command we can think of. Chosen: `dontAsk`. Why: a deny list
  can never be complete; `dontAsk` denies everything not allowed ahead of time, and only
  `Bash(pathly *)` is allowed. `manual` (ask the person) rejected: an unattended chief would block
  on a prompt nobody answers.
- **Run-token redaction** — options: redact where text is stored (stdout tail, `AGENT_DONE`
  summary, board post text) or ask agents not to print it. Chosen: both, redaction being the
  guarantee. The fragment line costs nothing; claude's own transcript under `~/.claude/` is outside
  Pathly and is named as a known limit.
- **How a waiting task is marked** — options: a new `task_status` value `waiting`, or the existing
  `blocked` with `fail_reason` `waiting_for_answer:<question id>`. Chosen: `blocked` with that
  reason. Why: every reader of `task_status` (scheduler, Studio, retry) already treats `blocked` as
  not ready; a new value would need each of them changed. A JSON list of question ids goes in the
  reason when there are several.
- **Which task asked** — the question's run token names its run (`run_tokens.run_id`); the asking
  tasks are those `in_progress` with `claimed_by` that run when the run ends. No new column on
  `comms_messages`.
- **Notices** — options: the server pushes into the chief's tab, or Studio shows a badge and the
  person writes. Chosen: badge (spike "Plan discussed" part 1). Why: nothing enters the tab, so
  there is no citation risk; the tab notice waits for round four.
- **Worktrees (round three)** — options: per-task worktree with its own DB and port (the
  `WorktreeIsolation` stub's docstring), or per-task worktree sharing the one server and DB
  (feature-flow 0.10.0). Chosen: shared server and DB. Why: the board is the shared substrate;
  splitting it per task would need a fan-in of DB rows as well as of git. Recorded now so round
  three does not reopen it.
- **Where the autopilot loop lives (round four)** — options: the chief (an LLM) wakes on notices
  and decides each next step, or the server drives the goal deterministically and the chief only
  takes the grant and reports. Chosen: the server drives. Why: the FSM supervisor already drives
  stages without a human; an LLM loop that wakes on injected text is the part with the most
  citation and cost risk, and every step it takes would cost a chief turn. The chief stays the
  person's interface: it answers questions the person answers, and reports. The grant (goal,
  dollars, runs, hours) is set by the person in the chief launcher, through a route a chief token
  cannot call, so no typed text is the consent and the chief can never raise its own budget.
- **Lanes (round three)** — options: every parallel task in its own worktree, or only those that
  need one. Chosen (the person, 2026-10-26): mixed. Tasks with disjoint files share the one tree
  (no merge step, fastest); a task that overlaps a running one, or declares no files, gets its own
  worktree and is merged and gated afterwards.

## Interfaces

- `runner/chief_argv.py::chief_argv` (claude): adds `--permission-mode dontAsk`.
- `runner/chief_argv.py::claude_settings`: deny rules for `Grep` and `Glob` on `~/.pathly/**`.
- New `runner/token_redact.py::redact_run_tokens(text) -> str`.
- `POST /runs` `kind: flow`: headless; `GET /runs` reports `kind: "flow"` for flow runs.
- `task_status='blocked'`, `fail_reason='waiting_for_answer:<id>'` (or a JSON list).
- New table `chief_session_runs(session_run_id, run_id, project_root, started_at, read_at)`.
- New `GET /chief/notices?project_root=` and `POST /chief/notices/read` (blueprint `chief/`).

## Migration and compatibility

All additive. The new table is created by `migrations_chief`. A chief opened before the change
keeps its argv until it is closed. Studio without the badge still works.

## Risks

- `--permission-mode dontAsk` behaves differently in another claude version — ticket 01 pins the
  argv with a test and the docs name the measured version; the acceptance re-measure happens on the
  person's machine (map Open questions).
- Redaction misses a place tokens are stored — ticket 03 lists every stored text field the spawn
  path writes and tests each.
