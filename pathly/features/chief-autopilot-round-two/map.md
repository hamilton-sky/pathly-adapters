# Map: chief-autopilot-round-two

## Destination

Round two of `pathly/features/chief-autopilot/` ("agents answer agents"). When it is done, a
board `question` that a running agent addresses to architect, designer, po, planner, tester or
reviewer is answered by a one-shot, read-only consult run of that role that the server starts
itself; the answer reaches the asking task (a loop task is parked and run again in the same drain,
a single run's unfinished task is parked and given the answer on its next run); the role can hand
the question to the person (`ANSWER: USER`); caps (three routed questions per task, a per-goal
consult cost line) and a measured read-only check send the rest to the person. Consult runs are
billed and shown as their own category and kind. A decompose cannot post a checkless task. The
chief's notices and run views show which questions a role answered and which wait for the person.
Round one's question gaps are closed, and an answer the chief relays is stamped `chief_relayed`.
A chief's first prompt is never lost to claude's trust screen (spike S4), and no file holds the
chief's hook secret: the server hands it once to the chief claude's environment, and the docs say
plainly what a same-user process can still read and what a codex chief cannot promise.

**The bar.** `python -m pytest tests/comms_board/test_autopilot_round_two_acceptance.py -q -p
no:cacheprovider` passes (ticket 12 writes it and runs it), and `python -m pytest tests/ -q -p
no:cacheprovider` passes in full.

## How to work this

- Plans live in `pathly/features/` (root `CLAUDE.md`, "Feature plans"); once this draft is copied
  there, run the scripts with `FLOW_DIR=pathly/features FLOW_TICKETS=tasks`.
- See what is ready: `python3 scripts/flow-status.py chief-autopilot-round-two`. Take the lowest
  numbered READY ticket.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`, then add one line to
  Decisions so far below.
- See the graph: `python3 scripts/flow-status.py chief-autopilot-round-two --mermaid`.
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md` (append only). Round
  one's `pathly/features/chief-autopilot/learnings.md` has the test recipes (driving a board spawn,
  a goal-loop run, a loop goal end to end, an in-process fake host): read it first.
- Status lives only in the ticket files. This map never repeats it.
- Design is in `spec.md`. Round one's plan and its HANDOFF lines
  (`/mnt/project-files/chief-autopilot/handoffs.md`, read-only network mount: use exact paths) are
  the background.
- Hard rules from `CLAUDE.md`: 400-line ratchet (`scripts/check_file_size.py`; files at or near
  400 are named in each ticket), layer rule `db -> runner -> supervisor -> http_server` with lazy
  imports inside routes, new endpoints in a matching or new blueprint domain, living docs in the
  same change, unique test basenames and `python scripts/gen_test_index.py` after adding tests.
  CI runs `bandit -r src/ -ll -x src/pathly_data/`: keep SQL one literal, never `# nosec`.

## Round two tickets and the brief

| Ticket | Brief item |
|---|---|
| 01 consult routes table and routing rules | caps and cost, unknown role, router rules |
| 02 consult run and answer delivery | router spawn, `ANSWER: USER`, decisions, the asking run's engine |
| 03 withhold a consult that changed the project | read-only, measured like `reviewer_unchanged` |
| 04 route on post, stale routes at start | router trigger (server-driven) |
| 05 round one's park gaps | RUN_OUTCOME, RUNNER_WARNING, park False, task_proof, re-check race |
| 06 loop: park on a role question, drain waits | delivery (loop) |
| 07 single: park an unfinished task, fragment text | delivery (single), team stages enrich |
| 08 plan lint | plan lint |
| 09 the chief sees it | notices, `GET /runs`, Operator text, notices limit and pruning |
| 10 Monitor consult category | "appear in the Monitor ... their own run category" |
| 11 chief-relayed answers | spike S7 |
| 12 acceptance | the bar |
| 13 settle: trust screen, second claim (resolved: A, A) | S4 approach and the hook secret's reach |
| 14 chief prompt pasted only when ready | spike S4 |
| 15 hook secret out of every file, server side | the hook secret out of every same-user process's reach |
| 16 consult billing and category | "billed and appear in the Monitor ... their own run category" |
| 17 a consult cannot post its own answer | read-only: the answer is not delivered around the check |
| 18 hook secret in Studio, the pty host and the launcher | the hook secret out of every same-user process's reach |

## Decisions so far

The router, delivery, caps and lint are decided by the codebase.

- Ticket 13 resolved (the brief's Decided line, 2026-11-06, recommended answers pending the
  person's tap): question 1 = A, Studio answers a chief's trust screen and never pastes blind;
  question 2 = A, a second claim of the hook secret closes the chief.
- A consult runs on the asking run's adapter with that adapter's model for the role, else claude
  (the brief's Decided line, 2026-11-06; spec Decisions).
- 01 — `consult_routes` table + `db/queries/consult_routes.py`: `route_decision` (none/person/route with reasons), caps from `consult.max_per_task`/`consult.goal_cost_usd`, `hand_to_person` re-addresses the same row to `human` with a system status reply.
- 01 (rework) — the per-task cap is recounted inside `record_route`'s insert (False over the cap); the cost line is soft; agent-written `to_agent` is echoed only as one line of at most 40 chars; `hand_to_person` skips deleted questions and keeps an ended route's status.
- 02 — `supervisor/consult_run.start_consult` spawns a `consult-<12hex>` headless run (`planning/consult-answer`, flow `consult`, asking run's headless adapter else claude-sonnet-4-6), reads its AGENT_DONE by run id and posts `ANSWER:` stamped `**runner.provenance.consult_stamp(role, run_id)` (token, the role, the consult run; callable only from `consult_run.py`) (+ architect/po/designer `DECISION:` row), `ANSWER: USER`/no answer → `hand_to_person` (no answer: route `failed`).
- 02 (rework) — the consult's route moves only by compare-and-set on its run id (`queued`→`running`→end; a lost claim spawns nothing; a question handed on or answered meanwhile keeps its end); two non-synthetic AGENT_DONEs for one consult run fail it; the answer is posted before the decision. A forged AGENT_DONE for a consult whose agent writes none is still read: `/runner/event` is unauthenticated (outside 02).
- 03 — `supervisor/consult_window.py`: `open_window` before the consult spawn, `blamed` after its summary; findings (HEAD moved, paths outside feedback/, `pathly/` and in-progress tasks' `files`) withhold the answer (route `withheld`, `hand_to_person`, one system escalation to human); no git -> delivered plus an "answer not measured" status.

Outside facts relied on (tickets 13 to 15, 18):

- On Linux a same-uid process may read `/proc/<pid>/environ` of another same-uid process, and
  Yama's ptrace scope does not restrict that read, so no same-uid secrecy exists without OS
  isolation (scout finding; man7 `proc_pid_environ(5)`, `ptrace(2)`; not re-run here).
- claude's folder trust can be pre-accepted with `~/.claude.json`
  `projects["<path>"].hasTrustDialogAccepted = true`, `<path>` the repository root; the trust
  dialog shows in interactive sessions only, never for `claude -p`; docs:
  https://code.claude.com/docs/en/permissions ("Project allow rules and workspace trust", fetched
  2026-11-06). Ticket 13 option C only, rejected.
- A claude command hook "inherits the parent environment" (apart from `OTEL_*` and, with
  `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`, the scrubbed variables); docs:
  https://code.claude.com/docs/en/hooks. Ticket 15 relies on it.
- claude hooks can be `type: "http"`, whose `headers` interpolate only variables listed in
  `allowedEnvVars`; docs: https://code.claude.com/docs/en/hooks (the rejected alternative in spec
  Decisions, "The hook secret").
- claude's current trust-screen wording: "Accessing workspace: … Quick safety check: Is this a
  project you created or one you trust? … ❯ 1. Yes, I trust this folder  2. No, exit · Enter to
  confirm · Esc to cancel", as a user quotes it in
  https://github.com/anthropics/claude-code/issues/40002 (fetched 2026-11-06; the issue names no
  claude version). Ticket 14 matches it and the old wording.

## Open questions

- A real claude following `planning/consult-answer`'s summary format (`ANSWER:` first) is not
  measured: ticket 12 cannot run one. The person re-measures one consult on their machine; a run
  that gives no `ANSWER:` line hands its question to the person, so the failure mode is safe.
- How often concurrent builders cause false withholds (a change outside every declared `files`)
  is unknown until real goals run; if it is often, round three's worktree per consult closes it.
- The trust screen's wording is unmeasured: its only source is a user's issue report with no
  claude version (Decisions so far), not a real claude run here. Ticket 14 records what it can
  (`claude --version` beside a fixture of the screen's text in
  `studio/src/main/ipc/terminal/fixtures/claude-trust-screen.txt`, its source and version noted in
  the file); the person confirms one first open in a never-trusted folder on their claude after
  ticket 14, and replaces the fixture if the wording differs.
- Ticket 13's answers are the brief's recommended ones, pending the person's tap; if the tap
  differs, ticket 13 reopens and tickets 14, 15 and 18 are planned again.
- Whether `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` (if a person sets it) strips
  `PATHLY_CHIEF_HOOK_SECRET` from the hook is not measured; ticket 15's hook then records nothing
  (exit 0), which loses citations but forges nothing.
