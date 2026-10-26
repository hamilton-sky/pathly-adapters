# Map: chief-autopilot

## Destination

Round one (this folder's tickets) makes an Operator chief safe to leave open: its claude runs
only `pathly` commands, it cannot read its hook secret, no stored text carries a raw run token, a
chief-started flow runs headless, a run cannot report success over an unfinished task, an agent's
question parks its task until answered and the answer reaches the next attempt, and Studio's Chief
button shows when a chief's run has ended. Rounds two to four (outlined below) build on it to the
autopilot: agents answer agents, tasks run in parallel worktrees, and the server carries a granted
goal or feature to done.

**The bar.** `python -m pytest tests/comms_board/test_autopilot_round_one_acceptance.py -q -p
no:cacheprovider` passes (ticket 09 writes it and runs it), and `python -m pytest tests/ -q -p
no:cacheprovider` passes in full.

## How to work this

- Plans live in `pathly/features/` (root `CLAUDE.md`, "Feature plans"), so run the scripts with
  `FLOW_DIR=pathly/features FLOW_TICKETS=tasks`.
- See what is ready: `python3 scripts/flow-status.py chief-autopilot`. Take the lowest numbered
  READY ticket.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`, then add one line to
  Decisions so far below.
- See the graph: `python3 scripts/flow-status.py chief-autopilot --mermaid`.
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md` (append only).
- Status lives only in the ticket files. This map never repeats it.
- Design is in `spec.md`. The spike this round answers is
  `pathly/features/chief-agent/spike19-part-b-report.md` ("Proposed tickets" there are numbered
  S1 to S16 below).
- Hard rules from `CLAUDE.md`: 400-line ratchet (`scripts/check_file_size.py`), layer rule
  `db -> runner -> supervisor -> http_server` with lazy imports inside routes, new endpoints in a
  matching or new blueprint domain, living docs in the same change, unique test basenames and
  `python scripts/gen_test_index.py` after adding tests. CI runs `bandit -r src/ -ll -x
  src/pathly_data/`: keep SQL one literal, never `# nosec`. The full suite runs on Python 3.11,
  3.12 and 3.13.

## Round one tickets and the spike

| Ticket | Spike |
|---|---|
| 01 dontAsk permission mode | S1 |
| 02 hook secret out of the chief's reach | S2 |
| 03 redact run tokens | S3 |
| 04 headless flow runs, `kind: flow` in `GET /runs` | S11, S12 |
| 05 no success over an unfinished task | S6 |
| 06 a question parks its task | S5 |
| 07 Operator text fixes | S8, S9, S10 |
| 08 run notices on the Chief button | S13 (part 1) |
| 09 acceptance | |

## Round two: agents answer agents (outline, own folder later)

From feature-flow 0.13.0 (`## Ask: <role>`, `REVIEW: ASK <role>`, `ANSWER: USER`). Pathly's
`consult` fragment already tells agents to post a `question` with `"to": "<role>"`, but nothing
answers it.

- A question router (supervisor): a board `question` whose `to` is `architect`, `designer`, `po`,
  `planner`, `tester` or `reviewer` starts a one-shot headless agent of that role, read-only
  (`scope_gate`-style footprint: no files outside `feedback/` and board posts), with the question,
  the asking task and the board context. It answers with `type: answer`, `reply_to` the question.
- `ANSWER: USER`: the role agent may hand the question on to the person instead; it then becomes
  a `to: human` question and parks the task (round one's ticket 06).
- Caps: at most three routed questions per task and a per-goal cost line for consults; past the
  cap the question goes to the person.
- Decisions: an architect answer may post a non-binding `decision` row (the approach chosen and
  why); only the person or the chief makes a decision binding.
- Plan lint (feature-flow 0.8.0): a decompose that posts a task with no check block and no
  `Check: none` is refused back to the planner.
- Leftovers from the spike: S4 (trust dialog on first open), S7 (stamp chief-relayed answers),
  S15 and S16 (measurements).

## Round three: parallel lanes in worktrees (outline)

From feature-flow 0.10.0. Pathly has the scheduler half: `supervisor/fan_out.py` drains a goal's
frontier through `AuditedLaneIsolation` (`supervisor/lane_partition.py`), which runs lanes in
parallel only when the tasks' declared `files` are disjoint, all in one working tree.
`WorktreeIsolation` in `supervisor/isolation.py` is a stub.

- `WorktreeIsolation.acquire`: a git worktree under `.pathly/lanes/<goal>/<task>` on branch
  `pathly/<goal>/<task>` from the goal's integration head; the agent's cwd is the worktree; the DB
  and server stay shared (spec Decisions).
- Footprint enforced: a task's diff outside its declared `files` is sent back (per-task
  `scope_gate`), with or without lanes.
- Fan-in: the supervisor merges a passed task with `git merge --no-ff` in an integration
  worktree, one at a time, runs `command_gate` (`verify.build`, then `verify.test` on the last),
  and only then advances the goal's branch. No agent resolves a conflict: a conflict or a red merge
  gate rebuilds the task once from the new head; a second one parks the goal for the person.
- Across goals: two goals whose task files are disjoint run at the same time (replaces the
  `file_claims` serialisation in `goal_executor` once worktrees hold).
- Several single agents at once falls out of this: the chief starts several goals or tasks, and
  the server runs them in parallel where their files allow.
- Cleanup: worktrees and branches removed on done, abort and server start.

## Round four: the autopilot (outline)

- The grant: the person types it in the chief tab ("carry goal X to done, at most 5 runs, $3, 2
  hours"); the chief posts it with a cite, so the recorded consent is the person's own words. It
  covers that goal (or the goals of one feature, in `SEQUENCING.md` order) and that budget only.
- The driver is the server, not the chief (spec Decisions): decompose (planner or consultation
  flow) if the goal has no tasks, run with the `team` executor in lanes, retry a failed task within
  the budget, route questions (round two), and move to the next goal.
- Hard stops: the run, cost or time budget; a proof gate that fails after its rework cap; an
  escalation or question to the person; the person typing "stop". It reports and waits.
- Notices into the chief's tab, marked by the server as relayed so they are never citable (spike
  "Plan discussed" part 2), so the chief can tell the person what happened.
- The run record (feature-flow 0.15.0): per goal, the runs, reviews, rework, every catch by the
  gate that made it, where it needed the person, minutes, tokens and cost; a verdict form where
  the person marks each catch real or false. This is the "verified completion rate".
- Time budget (feature-flow 0.14.0): over budget, stop and offer a re-plan only the person can
  approve.
- Chief engine billing (the chief's own tokens), still open from chief-agent round two.

## Later, not planned here

Per-task review levels and the fast path (feature-flow 0.9.0, 0.11.0), the quick gate (0.7.0),
scouts (0.12.0), plugin packaging, profiles and Spec Kit import (0.16.0 to 0.18.0). See
`/mnt/project-files/feature-flow-assessment/chief-operator-and-feature-flow-gaps.md`.

## Decisions so far

## Open questions

- Ticket 01's `dontAsk` is pinned by tests only; whether claude 2.1.310 then denies `ls` needs a
  re-measure on the person's machine (spike question 1). Ticket 09 cannot run a real claude.
- Round four's grant wording and default budgets are the person's call when round four is planned.
