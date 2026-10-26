# Chief autopilot — Spec

## Problem

The Operator chief (chief-agent round one) can plan a goal, start runs, steer them and relay the
person's answers, but only while the person sits at the tab. Spike 19 part B
(`pathly/features/chief-agent/spike19-part-b-report.md`, 2026-10-26, claude 2.1.310) and the
independent review of this plan (`/mnt/project-files/chief-autopilot/independent-review-2026-10-26.md`)
show why it cannot be left alone yet:

- The chief starts in claude's auto mode, so commands other than `pathly` run when a classifier
  allows them. Its hook secret sits in `~/.pathly/chief/<run_id>/hook_secret`; a chief that reads
  it can forge a "typed by the person" message and cite it.
- A headless agent printed its `PATHLY_RUN_TOKEN` into its output, which a chief can read back
  through `GET /runs/<id>` (`run_log.stdout`). The chief gate treats a request with an unknown or a
  non-chief token as anonymous, with full rights, so a leaked or junk token is a way around it.
- `POST /runs` with `kind: flow` opens interactive tabs that wait forever at claude's "Bypass
  Permissions" dialog.
- A `single` goal run whose agent asks a question on the board ends `done` / `success` while its
  task stays `in_progress`. Nothing ties the task to the run (`claimed_by` holds whatever the
  agent sent, `"$GOAL_ID-single"` for drain-dag), the task can never be claimed again, and the
  answer never reaches an agent.
- Nobody is told when a run ends.

The person also wants the chief to carry a goal, or a whole feature, to done: decompose it, run
several agents (in parallel where the work allows), let agents answer each other's questions
(architect, designer, product owner) and only stop for the person when only the person can
decide. feature-flow (0.10.0 to 0.15.0) has working versions of three pieces Pathly lacks:
parallel lanes in git worktrees with an enforced file footprint, questions routed to a role agent,
and a per-run record of what each check caught.

## Goal and the bar

The whole feature is built in four rounds. This plan tickets round one; rounds two to four are
outlined in `map.md` and get their own folders (`chief-autopilot-round-two/` and so on) when
round one is resolved.

- **Round one: safe to leave alone.** The spike's and the review's security findings closed for a
  claude chief, a chief-started flow runs headless, every task claim names its real run, a run
  cannot claim success over an unfinished task, an agent's question parks its task until it is
  answered and the answer reaches the next attempt (single and loop), and Studio shows when a
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
-p no:cacheprovider` passes with a fake spawn host and fake agents (ticket 09), and `python -m
pytest tests/ -q -p no:cacheprovider` passes in full.

## Stories

### Leave a claude chief running

**As** the person, **I want** to leave an Operator chief (claude engine) open while a goal runs,
**so that** I do not have to watch the tab for it to be safe.

- [ ] The chief's claude runs in `dontAsk` mode: `pathly` commands and claude's built-in read-only
      commands inside the project run, everything else is denied without asking.
- [ ] Nothing outside the project folder is readable to it, and `~/.pathly/` is denied by name.
- [ ] A request with a run token Pathly does not know, or a revoked one, is refused (401), so a
      leaked or invented token is no way around the chief gate.
- [ ] No text Pathly stores (events, run logs, board rows, task reasons) contains a raw run token.

A codex chief is not covered: `--sandbox read-only` reads the whole file system. The launcher
says so next to the engine choice (ticket 13), and round two looks at it.

### Run the full pipeline from the chief

**As** the person, **I want** "run the team flow on this feature" from the chief to start planner,
designer, builder, reviewer and tester without a dialog, **so that** the pipeline runs while I am
away.

- [ ] A chief-token `POST /runs {"kind": "flow"}` starts a headless run; Studio's New-run button
      keeps its own choice.
- [ ] `GET /runs` reports a packaged flow's run as `kind: "flow"` (`goal-loop` stays `loop`).

### Questions do not dead-end

**As** the person, **I want** an agent's question to wait for an answer instead of being lost,
**so that** the answer I give in the chief tab reaches the work.

- [ ] Every task claim made with a live run token records that run as `claimed_by`.
- [ ] A `single` run whose agent exits with its task `in_progress` reports `outcome: failed`, and
      the task goes back to `pending` (counted as an attempt) so the next goal start claims it.
- [ ] A task whose agent asked an unanswered question is parked: `blocked` with
      `waiting_for_answer`, no attempt spent, its dependents not deadlocked; single and loop alike.
- [ ] Any answer to the question (`/comms/answer` or a `type: answer` post) makes it ready again,
      and its next attempt sees the question and the answer.

### Know when a run ends

**As** the person, **I want** the Chief button to show that a run the chief started has finished,
**so that** I know to come back and read the result.

- [ ] Each run a chief session starts is recorded against that session.
- [ ] `GET /chief/notices?project_root=` lists the project's chief runs that ended and are unread,
      with status, outcome, cost and the questions waiting.
- [ ] The Chief button shows the unread count.

## Scope

In (round one): spike 19 proposed tickets S1, S2, S3, S5, S6, S8, S9, S10, S11, S12 and part 1 of
its "Plan discussed" (notify the person, not the chief), and the review's findings on the gate's
anonymous pass-through and on task-to-run identity.

Not in round one:

- The codex chief's file-system reach and the headless agents' reach to the hook secret (both are
  same-user processes): round two, with a server-held secret (map).
- Spike S4 (trust dialog on first open), S7 (stamp chief-relayed answers), S15 and S16
  (measurements): round two's list.
- A notice typed into the chief's tab: round four.
- Question routing to role agents: round two. Worktree lanes: round three. Grants, budgets and
  the run record: round four.

## Happy path (round one)

1. The person opens an Operator chief (claude). It starts with `--permission-mode dontAsk`.
2. The person asks for a goal run. The chief posts the goal and tasks and starts the run.
3. The run's agent claims the task (recorded as its run), posts a question and exits. The run
   ends `failed` with `waiting_for_answer`; the task is `blocked` on that question.
4. The Chief button shows "1". The person opens the tab and asks what happened; the chief reads
   `GET /chief/notices` and the question, and the person answers in the tab.
5. The chief relays the cited answer. The task is `pending` again. The person says "carry on"; the
   chief starts the goal again and the agent sees the question and the answer with the task.

## Edge cases

| Trigger | Expected behaviour | Handled in ticket |
|---|---|---|
| A claude without `dontAsk` | claude exits on the flag; the chief never starts in auto mode (unverified, map Open questions) | 01 |
| `PATHLY_RUN_TOKEN=<x> pathly api ...` from the chief | not matched by `Bash(pathly *)` (docs), so denied under `dontAsk`; a junk or revoked token is 401 at the server anyway | 01, 10 |
| A token printed in the middle of a long line | the stored copy shows `[run token]` in its place | 03 |
| Studio's Monitor New-run button starts a flow | unchanged: headless only when a chief token starts it, or the body says `"interactive": false` | 04 |
| drain-dag claims with `"$GOAL_ID-single"` | `claimed_by` is the caller's run id; the body value is ignored | 11 |
| A loop task's agent asks a question | the scheduler parks it instead of retrying or completing it | 12 |
| An agent asks two questions and exits | the task waits for both; it is ready when the last is answered | 06 |
| A question is answered by a `type: answer` post | the same unblock as `/comms/answer` | 06 |
| Three park-and-answer cycles on one task | no attempt is spent by waiting; the task is not escalated | 06 |
| A question is answered after the task was deleted | the answer is stored; nothing else happens | 06 |
| The chief session closes before its run ends | the notice is kept for the next chief of that project | 08 |

## Design

```
 chief tab ──pathly api──► chief gate ──► POST /runs ──► start_run (headless for chief)
               (dontAsk)   unknown token: 401  │
                               │ record run_id  ▼
                               ▼          agent claims task ── claimed_by = run id (token)
                      chief_session_runs        │
                               │          run ends: single ── terminal_reconcile
                               │                    loop ──── scheduler completion
                               │                    question open? ─► task blocked (waiting)
                               ▼                    else in_progress? ─► failed, task pending
             Studio Chief button ◄── GET /chief/notices
```

### Decisions

- **Where the chief is locked down** — options: claude's `--permission-mode dontAsk`, or keep
  auto mode and add deny rules for everything we can think of. Chosen: `dontAsk`. Why: it denies
  every call that would otherwise prompt (docs, map Decisions so far); a deny list can never be
  complete. `manual` (ask the person) rejected: an unattended chief would block on a prompt nobody
  answers. Claude's built-in read-only commands still run in every mode (docs), so the chief can
  list and read the project; reads outside the working directories need approval and are denied.
- **Hook-secret protection** — options: deny rules for each way the chief might read it, or no
  read path plus no way to call Pathly as anyone else. Chosen: the second, with a sliding-window
  scan of chief text as defence in depth. Redirect deny rules (`Bash(pathly *<*)`) rejected: an
  input redirect is already checked against `Read` deny rules (docs), a raw file is not a JSON body
  (`chief_cli.py::_json_object`), and the rule would deny ordinary bodies containing `<`.
- **Unknown run tokens** — options: keep treating them as anonymous, or refuse them. Chosen: a
  request carrying `X-Pathly-Run-Token` that does not resolve to a live token is 401 on every
  route. Why: a leaked token, once revoked, and an invented one are both ways around the chief
  gate today (`chief_gate` passes them untouched). No header at all stays anonymous, as today.
- **Run-token redaction** — options: redact with the raw token at the spawn site, or scan for
  anything that hashes to a known token. Chosen: scan. Why: the server stores only `sha256` of each
  token (`db/queries/run_tokens.py`), and `AGENT_DONE` arrives without a token or is written by the
  agent's own process. A sliding window of 43 URL-safe characters (`secrets.token_urlsafe(32)`) is
  hashed and looked up in `run_tokens`, at the DB write, plus the `PATHLY_RUN_TOKEN=` / `:`
  patterns. The same scanner serves ticket 02's hook-secret check.
- **Which run a task belongs to** — options: trust the claim body's `run_id`, or stamp it from the
  caller's run token. Chosen: the token (`runner/provenance` already resolves the caller); the
  body value is kept only for a caller with no token. Rounds three and four need this link.
- **How a waiting task is marked** — options: a new `task_status` value, or `blocked` with
  `fail_reason='waiting_for_answer:<ids>'`. Chosen: `blocked` with that reason. Why: every reader
  already treats `blocked` as not ready. The park gives back the attempt the claim counted, and the
  deadlock guard skips tasks that wait on such a task.
- **Which questions a task waits for** — the run's open `question` rows by `author_run_id`
  (`runner/provenance.stamp`), recorded as ids in the reason, so a later re-post by another author
  (round two's `ANSWER: USER`) is still matched by id.
- **Headless flows** — options: always headless on `POST /runs`, or headless for a chief token and
  on an explicit `"interactive": false`. Chosen: the second. Why: Studio's Monitor New-run button
  posts `/runs` with `kind: flow` and no `interactive`, and that behaviour is the person's.
- **Notices** — options: the server pushes into the chief's tab, or Studio shows a badge and the
  person writes. Chosen: badge (spike "Plan discussed" part 1): nothing enters the tab, so there
  is no citation risk.
- **Worktrees (round three)** — options: per-task worktree with its own DB and port (the
  `WorktreeIsolation` stub's docstring), or per-task worktree sharing the one server and DB
  (feature-flow 0.10.0). Chosen: shared server and DB. Why: the board is the shared substrate.
- **Lanes (round three)** — options: every parallel task in its own worktree, or only those that
  need one. Chosen (the person, 2026-10-26): mixed. Tasks with disjoint files share the one tree;
  a task that overlaps a running one, or declares no files, gets its own worktree and is merged and
  gated afterwards.
- **Where the autopilot loop lives (round four)** — options: the chief (an LLM) wakes on notices
  and decides each next step, or the server drives the goal deterministically and the chief only
  reports. Chosen: the server drives. Why: the FSM supervisor already drives stages without a
  human; an LLM loop that wakes on injected text carries the most citation and cost risk. The
  grant (goal, dollars, runs, hours) is set by the person in the chief launcher, with a credential
  only Studio holds (map round four), so no typed text is the consent and the chief can never raise
  its own budget.

## Interfaces

- `runner/chief_argv.py::chief_argv` (claude): adds `--permission-mode dontAsk`.
- `runner/chief_argv.py::claude_settings`: `Grep(~/.pathly/**)` and `Glob(~/.pathly/**)` denies,
  and `permissions.blockReadsOutsideWorkingDirectories: true`.
- New `db/secret_scan.py`: `find_run_tokens(conn, text)`, `redact_run_tokens(conn, text)`,
  `contains_secret_hash(text, sha256_hex)` (sliding window).
- Every route: an unresolvable `X-Pathly-Run-Token` is 401 `{"error": "unknown run token"}`.
- `POST /runs` `kind: flow`: headless for a chief token or `"interactive": false`;
  `GET /runs` reports packaged flows as `kind: "flow"`.
- `POST /comms/tasks/claim`, `/comms/tasks/run`: `claimed_by` = the caller's run id.
- `task_status='blocked'`, `fail_reason='waiting_for_answer:<id>[,<id>]'`.
- `GET /comms/tasks?ready=true` rows gain `answered_questions: [{question, answer}]` for a task
  that waited.
- New table `chief_session_runs(session_run_id, run_id, project_root, started_at, read_at)`.
- New `GET /chief/notices?project_root=` and `POST /chief/notices/read` (blueprint `chief/`).

## Migration and compatibility

All additive. The new table is created by `migrations_chief`. A chief opened before the change
keeps its argv until it is closed. A caller that sent a junk `X-Pathly-Run-Token` and relied on
being anonymous gets 401: no Pathly code path does that (ticket 10 checks the fragments).

## Risks

- `dontAsk` and the rule matching behave differently in claude 2.1.310 than the docs say — the
  tickets pin the argv and settings with tests, map Open questions lists the re-measure on the
  person's machine.
- The redaction scan misses a stored field — it runs at the DB write chokepoints (event append,
  run log, message insert and update), not per route; ticket 03 lists them and tests each.
- A loop change in `scheduler.py` (393 lines) or `comms_tasks.py` (418, ratchet baseline) grows a
  frozen file — the tickets say to move code out first.
