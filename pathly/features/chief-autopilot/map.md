# Map: chief-autopilot

## Destination

Round one (this folder's tickets) makes an Operator chief on claude safe to leave open: it runs in
`dontAsk` mode and cannot read outside its project, an unknown run token is refused instead of
passing as anonymous, no stored text carries a raw run token, a chief-started flow runs headless,
every task claim names its real run, a run cannot report success over an unfinished task, an
agent's question parks its task (single and loop) until answered and the answer reaches the next
attempt, and Studio's Chief button shows when a chief's run has ended. Rounds two to four (outlined below) build on it to the
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

| Ticket | Spike / review |
|---|---|
| 01 dontAsk permission mode | S1 |
| 02 hook secret out of the chief's reach | S2, review M2, M3 |
| 03 redact run tokens at the DB writes | S3, review M4, M5, M6 |
| 04 headless chief flows, `kind: flow` in `GET /runs` | S11, S12, review M7 |
| 05 no success over an unfinished task (single) | S6, review M11 |
| 06 park a task on its question, unblock on any answer | S5, review M8, M9, M10, B3 |
| 07 Operator text fixes | S8, S9, S10 |
| 08 record chief runs, `GET /chief/notices` | S13 (part 1) |
| 09 acceptance | |
| 10 refuse unknown run tokens | review M1 |
| 11 `claimed_by` from the caller's run token | review B1 |
| 12 park and resume loop tasks in the scheduler | review B2 |
| 13 Chief button badge and the codex note | S13 (part 1), review m3, m4 |

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
- The hook secret out of every same-user process's reach (headless agents run with
  `--dangerously-skip-permissions` and can read `~/.pathly/chief/`, `blueprints/chief/human.py`
  says so; a codex chief's read-only sandbox reads the whole file system): the server keeps the
  secret it generated (`chief_session._write_session_folder`) and hands it to the hook in a way
  agents cannot read. Then a codex chief can be called safe to leave alone.

## Round three: parallel lanes in worktrees (outline)

From feature-flow 0.10.0. Pathly has the scheduler half: `supervisor/fan_out.py` drains a goal's
frontier through `AuditedLaneIsolation` (`supervisor/lane_partition.py`), which runs lanes in
parallel only when the tasks' declared `files` are disjoint, all in one working tree.
`WorktreeIsolation` in `supervisor/isolation.py` is a stub.

- Two kinds of lane, picked per task by the server (the person's decision, 2026-10-26):
  - **Shared tree:** tasks whose declared `files` are disjoint (for example backend under
    `src/` and frontend under `studio/`) build at the same time in the one working tree. This is
    today's `AuditedLaneIsolation`, which already runs lanes in parallel when the partition audits
    safe; round three makes it the default for disjoint tasks and enforces the footprint.
  - **Own worktree:** a task whose files overlap a running task's, or that declares none, or that
    the plan marks `isolation: worktree`, gets a git worktree under `.pathly/lanes/<goal>/<task>`
    on branch `pathly/<goal>/<task>` from the goal's integration head, instead of waiting. The
    agent's cwd is the worktree; the DB and server stay shared (spec Decisions).
  - Several builders at once is the point: disjoint tasks never wait, overlapping ones run apart
    and meet at the merge.
- Footprint enforced: a task's diff outside its declared `files` is sent back (per-task
  `scope_gate`), with or without lanes.
- Fan-in (own-worktree tasks): the supervisor merges a passed task with `git merge --no-ff` in an integration
  worktree, one at a time, runs `command_gate` (`verify.build`, then `verify.test` on the last),
  and only then advances the goal's branch. No agent resolves a conflict: a conflict or a red merge
  gate rebuilds the task once from the new head; a second one parks the goal for the person.
- Across goals: two goals whose task files are disjoint run at the same time (replaces the
  `file_claims` serialisation in `goal_executor` once worktrees hold).
- Several single agents at once falls out of this: the chief starts several goals or tasks, and
  the server runs them in parallel where their files allow.
- Cleanup: worktrees and branches removed on done, abort and server start.

## Round four: the autopilot (outline)

- The grant is set in Studio, not typed (the person's decision, 2026-10-26): the chief launcher
  (`ChiefButton` → `ChiefLauncher`, beside engine and style) gets an **Autopilot** switch and
  budget fields (dollars, runs, hours), with defaults from settings. When the switch is on, the
  launcher asks which goal (or which feature's goals) it covers. Studio sends the grant through a
  route a chief token cannot call (like `POST /chief/notices/read`), so the grant is the person's
  click, recorded with who and when; the chief only reads it (`GET /chief/session` shows it) and
  can never raise it. A grant can be stopped or changed from the same menu while it runs.
  Prerequisite (review M12): "a route a chief token cannot call" is still open to every tokenless
  loopback caller, headless builders included (they can read the server secret). The grant route
  needs a credential only Studio holds, for example a per-launch secret kept in Electron main and
  never written to disk. Round one's ticket 10 closes the unknown-token pass-through it also
  relies on.
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

Outside facts the tickets rely on, from the Claude Code docs as read on 2026-10-26 (the person's
claude is 2.1.310; the docs name no version for most of these, so each is re-measured, see Open
questions):

- `dontAsk` "auto-denies every tool call that would otherwise prompt you"; allow rules still run
  matching calls. docs: https://code.claude.com/docs/en/permission-modes
- Claude's built-in read-only commands (`ls`, `cat`, `grep`, `find`, read-only `git`, ...) "run
  without a permission prompt in every mode"; reads outside the working directories need approval
  (so `dontAsk` denies them), and `permissions.blockReadsOutsideWorkingDirectories` exists for
  those paths. docs: https://code.claude.com/docs/en/permissions (Read-only commands)
- Deny rules win over allow rules, from any scope. docs: same page (Manage permissions,
  Settings precedence)
- `Read` deny rules apply to Grep and Glob (to the directory they search), to file commands in
  Bash such as `cat`, and to `< file` input redirects; not to a program that opens files itself.
  docs: same page (Read and Edit, Redirections)
- An allow rule does not match past a leading assignment of a variable outside a known-safe set,
  so `PATHLY_RUN_TOKEN=x pathly api ...` is not matched by `Bash(pathly *)`; a deny rule matches
  past any assignment. docs: same page (Compound commands)
- Deny and ask rules apply to every subcommand, including command substitutions; a compound
  command needs every part allowed. docs: same page (Compound commands)
- auto mode is claude's built-in starting mode for interactive sessions from v2.1.283; the
  `--permission-mode` flag comes first in the order that picks the mode. docs:
  https://code.claude.com/docs/en/permission-modes (Startup behavior)
- 01 — the claude chief argv carries `--permission-mode dontAsk` (`CLAUDE_PERMISSION_MODE` in `runner/chief_argv.py`), right after `--tools`, before `--settings`; codex unchanged.
- 03 — run tokens are redacted at the DB writes by `db/secret_scan.py` (43-char window hashes looked up in `run_tokens`, plus `PATHLY_RUN_TOKEN=`/`:` values, never `$PATHLY_RUN_TOKEN`), replaced by `[run token]`; `insert_artifact` moved to `comms_artifact_rows.py`; `contains_secret_hash` is ready for 02.

## Open questions

- Re-measure on the person's machine after ticket 01 (spike question 1): the tab shows "don't ask
  on"; `python3 -c 1` and `PATHLY_RUN_TOKEN=x pathly api GET /health` are denied; `cat
  ~/.pathly/chief/<id>/hook_secret` and `Grep` on `~/.pathly/` are denied; `ps e`, `ps auxe` and
  `printenv` (which could show another process's live token) are denied or show nothing of the
  kind; `ls` in the project still runs. Ticket 09 cannot run a real claude.
- What a claude that does not know `dontAsk` does with the flag (exit or ignore): not in the docs.
- Round four's grant wording, default budgets and the Studio-only credential are the person's call
  when round four is planned.
