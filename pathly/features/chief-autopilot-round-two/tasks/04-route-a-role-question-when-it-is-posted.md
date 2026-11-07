# Route a run's role question to a consult when it is posted

Type: task
Status: resolved
Blocked by: 01, 02
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/http_server/consult_trigger.py (new), src/pathly_orchestrator/supervisor/consult_router.py (new), src/pathly_orchestrator/http_server/app.py, tests/comms_board/test_consult_router.py (new), src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/comms_board/INDEX.md

The trigger, server-driven with no chief turn (spec Decisions, "What triggers the router").

New `src/pathly_orchestrator/supervisor/consult_router.py` (new):
`on_question(question_id, *, project_root, broadcast_fn, host_present, start=start_consult) ->
str` returns what it did (`none`, `person`, `routed`, `no_host`):

- `route_decision` (ticket 01) `none` → nothing.
- `person` → `consult_routes.hand_to_person(question_id, decision.reason, by="pathly")`.
- `route` with `host_present` False → nothing (`no_host`): the question stays as posted (spec
  Decisions, "No spawn host").
- `route` → `record_route` (insert-or-ignore, so a second call for the same question routes
  nothing), then `start(question_id, project_root=..., broadcast_fn=..., block=False)` on a daemon
  thread named `consult-<question id prefix>`. A start that raises before the spawn hands the
  question to the person with the error and sets the route `failed`.

New `src/pathly_orchestrator/http_server/consult_trigger.py` (new), an `after_request` hook
registered in `src/pathly_orchestrator/http_server/app.py` after `record_chief_run`: for `POST /comms/post` answered 200
with `ok` and a `message_id`, when the request body's `type` is `question`, it calls `on_question`
with the body's `project_root`, `broadcast_fn=sse._broadcast_spawn` and
`host_present=bool(sse._spawn_clients)` (the queue a spawn host reads, `/events/spawn`). It never
changes the response and never raises (a failure is logged).

At server start, `app.main` calls `consult_routes.end_stale_routes` once, next to
`chief_startup_cleanup` and under the same "something already answers" check, and logs the
handed-on question ids.

Mind the tests that post role questions: a test without a spawn host routes nothing; a test that
registers a fake host (`SpawnHost` in `tests/comms_board/chief_acceptance_support.py`) and posts a role
question now gets a consult spawn. Any thread this starts in a test must end inside it
(`tests/chief_session_guard._no_watcher_outlives_its_test`).

## Not in this ticket

- Parking the asking task until the answer comes: tickets 06 (loop) and 07 (single).
- Showing the routes to the chief: ticket 09.

## Done when

- `python -m pytest tests/comms_board/test_consult_router.py -q -p no:cacheprovider` passes and
  covers, through `POST /comms/post` with a run token and a fake host and `start`: a question to
  `architect` records one route and calls `start` once; posting the response's hook twice (same
  message id) calls it once; a question to `human` and a tokenless question route nothing; a
  question to `builder` becomes `to: human`; the fourth role question of one task becomes
  `to: human` without a `start` call; a goal at its cost line routes nothing new; no spawn host →
  `no_host` and the question is unchanged; `end_stale_routes` at start hands a `running` route's
  question to the person.
- All existing tests under `tests/comms_board` and `tests/http_api` still pass.

```check
$ python -m pytest tests/comms_board/test_consult_router.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/comms_board tests/http_api -q -p no:cacheprovider
exit 0
```

## Reference

- spec.md § Happy path 1-2, § Edge cases
- `src/pathly_orchestrator/http_server/chief_run_record.py` (an after-request hook that reads the
  response), `src/pathly_orchestrator/http_server/sse.py` (read-only)

## Answer

Work started at 601ff64e27d03cece4c92e7764be252b593bad6f (HEAD b0299f8, a merge of master whose tree equals it).

**Built**

- `src/pathly_orchestrator/supervisor/consult_router.py` (new): `on_question(question_id, *,
  project_root, broadcast_fn, host_present, start=None) -> none|person|routed|no_host`, and the
  `consult-<qid[:8]>` thread body `_start` / `_fail`.
- `src/pathly_orchestrator/http_server/consult_trigger.py` (new): `trigger_consult(response)`,
  the `after_request` hook on `POST /comms/post`.
- `src/pathly_orchestrator/http_server/app.py`: registers `trigger_consult` after
  `record_chief_run`; `main()` calls `end_stale_routes` in its own `try` inside the "nothing
  answers" branch, before `chief_startup_cleanup`, and logs the handed-on ids.
- `tests/comms_board/test_consult_router.py` (new, 16 tests), `tests/INDEX.md`,
  `tests/comms_board/INDEX.md` (regenerated).
- `src/pathly_orchestrator/CLAUDE.md`: the two "nothing calls ... yet" sentences, a new
  "Consult router" section, two module-map lines.

**Proof**

- `python -m pytest tests/comms_board/test_consult_router.py -q -p no:cacheprovider`: `16 passed`,
  exit 0. Through `POST /comms/post` with a minted run token, the `SpawnHost` fixture and a fake
  `start`: architect → one `queued` route, `start` called once with the body's project root,
  `sse._broadcast_spawn`, `block=False`, on thread `consult-<qid[:8]>`; the hook called a second
  time with the same message id → still one call, one route; `human` and tokenless → no route, no
  call; `builder` → `to_agent` human, route `to_person` "unknown role builder"; the fourth question
  of one task → human, limit reason, 3 calls; a goal at its $2.00 line → human, no call; no host
  (`sse._spawn_clients == []`) → no route, `to_agent` unchanged, no reply, `on_question` says
  `no_host`; `app.main()` in a subprocess (both with the chief cleanup ok and raising) hands a
  `running` route to the person (`to_person`, "server restart", `to_agent` human, the id in the
  log). Also: a raising start → route `failed` + handed on; `{"started": False}` with the route
  still queued → same; a route another start claimed → left; `record_route` False → asks
  `route_decision` again → `person`.
- The test commit 90b390d failed at setup with `ImportError: cannot import name 'consult_router'`.
- `python -m pytest tests/comms_board tests/http_api -q -p no:cacheprovider`: `4147 passed in 1074.94s`, exit 0.
- Also run: `tests/dag_goals/test_task_waits_for_answer.py tests/comms_board/test_comms_provenance.py
  tests/consistency` 208 passed; `tests/http_api/test_chief_routes.py test_chief_startup_port.py` 78
  passed; `black --check src/ tests/`, `mypy src/` (no issues, 367 files), `check_file_size.py`
  (none new, none grown), `lint-imports` (1 kept), `check_no_mirror_reads.py`, `bandit` on the
  new files, `gen_test_index.py` then `--check` (up to date), `check_adapters.py`,
  `check_entry_points.py`: all exit 0.

**Decisions**

- `start=None` resolves `consult_run.start_consult` at call time (a module global), not a
  `start=start_consult` default bound at definition: the hook passes no `start`, so the tests
  replace `consult_router.start_consult` to inject the fake through `POST /comms/post`.
- The hook reads the body with the comms `read_json_body` (the route's own lenient decoder), so
  a cp1252 question is routed too. ~~the project root is the body's value, stripped (may be "").~~
  (Round 1: the project root, board and scope now come from the asking run's token row; see
  Review fixes.)
- A raising start: `set_route_status(failed, reason="consult start failed: <Type>: <msg>")`
  first, then `hand_to_person` (which keeps an ended route's status but re-addresses and replies).
  `start_consult` answering `{"started": False}`: the same, only while the route is still
  `queued` (a "claimed by another start" route is `running` and left to it).
- `record_route` False → `route_decision` again; `person` is handed on, anything else is `none`
  (a duplicate says "already routed").
- `end_stale_routes` runs before `chief_startup_cleanup` in the else branch, in its own `try`, so
  neither failure skips the other's work or boot; it does not run when something already answers.
- `consult_run.py` (400 lines) is unchanged.

**Shortcuts taken**

- The `only_queued` check in `_fail` reads the route and then sets it in two statements, not a
  compare-and-set; a start claiming the route between them would see it failed. Only reachable
  when `start_consult` already said it did not start; a CAS in `consult_routes` would close it.
- No spawn host means no route at all, so such a question is never routed later even when a host
  connects (spec Decisions, "No spawn host").

**For later tickets**

- The router thread is `consult-<qid[:8]>`, the consult run's own thread `consult-<12 hex>`;
  neither is in `tests/chief_session_guard.STARTED_BY_TESTS`. A test that posts a role question
  with a spawn host registered now starts a real consult unless it replaces
  `supervisor.consult_router.start_consult` (06, 07, 12): join `consult-` threads before the test
  ends (see `_join_router_threads` in `tests/comms_board/test_consult_router.py`).
- 09: `on_question`'s outcomes are not recorded anywhere but the route row and the status reply.

**Review fixes (round 1, quality review)**

Test commit b0e9b38 (4 new tests, 6 direct `on_question` calls given the new `board`/`scope`
keywords) failed for the right reasons: `start` got `''` and the other root, and the
no-root / other-board questions were started.

1. Blocker, project root from the body: fixed. `consult_trigger` now passes
   `caller_identity(request).project_root` (the `run_tokens` row), never `data["project_root"]`.
   The ticket's line "with the body's `project_root`" is deliberately not followed: the root is the
   consult's spawn cwd and what `consult_window` measures, so the asking run must not choose it;
   this follows `chief_run_record.py`'s rule (the session's root, never the body's). A routable
   question whose token names no root is handed to the person (`the asking run's token names no
   project root`); the body is never a fallback. Tests:
   `test_a_question_with_no_root_in_the_body_starts_with_the_tokens_root`,
   `test_a_question_naming_another_root_starts_with_the_tokens_root` (both: `start` gets the
   token's root), `test_a_token_with_no_root_hands_the_question_to_the_person`.
2. Minor, board/scope from the body: fixed. `on_question` takes the token's `board` and `scope`
   and, for a `route` (after the host check, before `record_route`), compares them with the stored
   question row's `board`/`scope`; a mismatch is handed to the person (`the question is on board
   <b>/<s>, the asking run's is <b>/<s>`). Test:
   `test_a_question_on_another_board_than_the_tokens_goes_to_the_person`.
3. Minor, cost line checked against billed costs only: noted, not changed. It is the ticket 01
   rule (`route_decision`, already documented as a soft line); a reservation would change
   `consult_routes`, outside Touches. Added a paragraph to the "Consult router" section of
   `src/pathly_orchestrator/CLAUDE.md` saying the per-task cap is what bounds it.
4. Minor, two threads per consult: kept. The ticket asks for `start` "on a daemon thread named
   `consult-<question id prefix>`" and the tests check that name; the router thread returns as soon
   as `start_consult(block=False)` hands off. Noted in the same doc section.

Proof after the fixes:
- `python -m pytest tests/comms_board/test_consult_router.py -q -p no:cacheprovider`: `20 passed`, exit 0.
- `python -m pytest tests/comms_board tests/http_api -q -p no:cacheprovider`: `4151 passed in 1071.71s`, exit 0.
- `tests/comms_board/test_consult_router.py tests/dag_goals/test_task_waits_for_answer.py
  tests/comms_board/test_comms_provenance.py`: 137 passed. `black --check src/ tests/` (746
  unchanged), `mypy src/` (no issues, 367 files), `check_file_size.py` (none new, none grown;
  `consult_router.py` 154 lines), `lint-imports` (1 kept, 0 broken), `gen_test_index.py` then
  `--check` (up to date), `check_no_mirror_reads.py`: all exit 0. `consult_run.py` unchanged.

For later tickets: `on_question` now requires `board` and `scope` (the asking token's); a test
that posts a role question must mint its token with the same board and scope as the post body and
a project root, or the question goes to the person.

**Review fixes (round 2, gate (quick))**

1. `tests/fsm_flows/test_review_packet_notes.py::test_the_notes_use_the_latest_task_proof_of_a_task`
   ("the project could not be snapshotted"): not caused by 04, so no code changed. What I ran
   (work at 972270d):
   - Suite order, `pytest tests/comms_board/test_consult_router.py tests/fsm_flows -p no:cacheprovider -q -x`:
     `734 passed, 9 skipped`, exit 0.
   - The full Quick list at HEAD, with a scratch pytest plugin (not committed) that logged every
     `consult_router.on_question` outcome and any live `consult-*` thread after each test:
     `5934 passed, 11 skipped in 1374.80s`, exit 0. Outside `test_consult_router.py` the router
     answered 403 `none`, 14 `person`, 1 `no_host`, never `routed`, so no other test started a
     consult; no `consult-*` thread outlived any test. 04's module and hook set no env var and
     change no cwd; `app.main()` only runs in a subprocess with its own env.
   - The full Quick list at the base 601ff64 (a detached worktree, `PYTHONPATH` its own `src`):
     `5914 passed, 11 skipped in 1467.58s`, exit 0.
   - `git diff 601ff64 HEAD` is empty for `proof/`, `event_mirror.py`, `fsm_compose_review.py`,
     `tests/fsm_flows` and `tests/conftest.py`: 04 touches nothing on that test's path.
   - The cause, shown on base code: the test's storage folder is inside its git repo, and the
     event mirror flusher (a process-wide daemon, every 0.5 s) rewrites `EVENTS.jsonl` there via
     `EVENTS.tmp` + `os.replace`. When that lands during `tree.snapshot`'s `git add -A`, git
     fails with `fatal: unable to stat 'pathly/EVENTS.tmp': No such file or directory` (exit
     128), `_git` returns None, and the packet says "could not be snapshotted". A scratch script
     with a writer thread doing the same: 35 of 200 `tree.snapshot` calls returned None. The test
     appends two `TASK_PROOF` events just before `_packet`, so the flusher is due right then; a
     slow git (cold cache after a container restart) widens the window.
   - `test_review_packet_notes.py` + `test_review_packet.py` at base, with 6 CPU-burning
     processes on 4 cores: 1 failed run in 15 (output not captured), then 55 clean runs.
   A fix belongs in the mirror or the snapshot (or that test's fixture), outside Touches.

Proof after round 2: `python -m pytest tests/comms_board/test_consult_router.py -q -p no:cacheprovider`
`20 passed`, exit 0; `python -m pytest tests/comms_board tests/http_api -q -p no:cacheprovider`
`4151 passed in 1059.47s`, exit 0.

## Review findings (round 1, quality review)

Review: chief-autopilot-round-two 04 (quality pass, level 3). Range 601ff64..b115069 (END = HEAD = b115069, so no later commits are left out). I read the ticket as it stood at 601ff64 and the diff with tasks/ excluded. I did not read the Answer. Re-run: the focused tests (test_consult_router, test_chief_routes, test_chief_startup_port, test_task_waits_for_answer): 105 passed. check_file_size OK. gen_test_index --check OK. No files were left behind.

Inputs probed: body type, body project_root, body to/to_agent, body scope/board, run token present / absent / chief, body run_id, the same message id twice, repeated questions from one run, host present / absent, start raising or returning started:false, and the startup cleanup.

Holding up: the asker comes from the token (author_run_id via stamp(caller_identity)), never from body run_id, so a tokenless or forged run_id question routes nothing. type is checked again in SQL. to_agent is lowercased and made one line, so a forged role routes to the person. Firing the hook twice, or racing it, starts once (INSERT OR IGNORE plus the in-SQL cap plus start_consult's queued->running compare-and-set). The per-task cap of 3 cannot be passed by concurrent posts. The hook never raises and never changes the response. Each routed question gets one short daemon thread, which returns as soon as start_consult hands off. The end_stale_routes block has its own try in the no-server branch.

QUALITY
1. blocker src/pathly_orchestrator/http_server/consult_trigger.py: project_root comes from the request body (data.get("project_root")), and it decides where the consult runs (RunnerState.project_root becomes the TERMINAL_SPAWN cwd) and what consult_window measures. (a) In real runs it is always empty. The fragment agents actually use to ask a role, src/pathly_data/core/skills/fragments/consult.md (and the question example in comms-post.md), sends no project_root. So every real consult spawns in the spawn host's own cwd (pty_host: os.getcwd()), and open_window("") gives None. Every answer then goes out fail-open as "answer not measured", which turns ticket 03's read-only guard off for every real consult. The tests hide this because they always put project_root in the body. (b) A hostile asking run picks the root. It can point the consult at any directory (another project, or a non-repo path so measurement is skipped on purpose), and its read-only consult then runs unmeasured with skip-permissions. chief_run_record.py states the house rule: the project root is the session's own, never the request body's. Fix: take the root from the asking run's token row, caller_identity(request).project_root (run_tokens.project_root). If the token row has none, route nothing (leave it no_host-like) or hand the question to the person; do not fall back to the body. Add a test that posts a role question with no project_root and with a different one, and asserts that start gets the token's root.
2. minor src/pathly_orchestrator/http_server/consult_trigger.py: body scope/board are also chosen by the caller. A run can ask a role question on another feature's board, and the consult then reads that board and writes that board's feedback folder. Consider checking that the question's board is the asking token's board/scope (run_tokens.board/scope) before routing.
3. minor src/pathly_orchestrator/supervisor/consult_router.py: the goal cost line is only checked against costs already billed, so up to max_per_task consults per task can start at once before any cost lands. A run that claims several tasks multiplies this. This is bounded by the cap, but worth a note in the doc's Consult router section.
4. minor src/pathly_orchestrator/supervisor/consult_router.py: the router thread only calls start_consult(block=False), which already does its own spawn on a daemon thread. The extra thread exists because the ticket asks for it, but it means two threads per consult. If the ticket allows it, call start inline.

REVIEW: FAIL

## Review findings (round 2, gate (quick))

gate: Build: python -m build --wheel && npm --prefix studio run typecheck
gate: Quick: python -m pytest tests/comms_board tests/db tests/runner_supervisor tests/http_api tests/dag_goals tests/fsm_flows tests/telemetry tests/consistency -q -x -p no:cacheprovider
gate: Quick failed. the last lines of its output:
........................................................................ [ 92%]
..................................................................F
=================================== FAILURES ===================================
______________ test_the_notes_use_the_latest_task_proof_of_a_task ______________

repo = PosixPath('/tmp/pathly-tests/tmplflnhyap/repo')
flow = {'_comments': [], 'adapter_map': {'BUILDING': 'claude', 'REVIEWING': 'claude', 'TESTING': 'claude', 'default': 'claude...test'}, 'escalation_routing': {'REVIEW_FAILURES': 'planner', 'SCOPE_VIOLATION': 'planner', 'TEST_FAILURES': 'po'}, ...}

    def test_the_notes_use_the_latest_task_proof_of_a_task(repo, flow):
        task_id = _build(repo, flow)
        fsm_ops.complete_stage(_args(repo))
        _task_proof(repo, task_id, "failed")
        _task_proof(repo, task_id, "passed")
    
>       notes = _section(_packet(repo), "Supervisor notes")
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests/fsm_flows/test_review_packet_notes.py:69: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

packet = '\n## Review packet\n\nNo review packet for this run: the project could not be snapshotted (git is not available). The...account is still left out. The stage orchestrator runs `git diff HEAD` itself and passes the output to the reviewer.\n'
heading = 'Supervisor notes'

    def _section(packet: str, heading: str) -> str:
        found = re.search(
            r"^### %s\n(.*?)(?=^### |\Z)" % re.escape(heading), packet, re.S | re.M
        )
>       assert found, "no '### %s' section in:\n%s" % (heading, packet[:2000])
               ^^^^^
E       AssertionError: no '### Supervisor notes' section in:
E       
E       ## Review packet
E       
E       No review packet for this run: the project could not be snapshotted (git is not available). The builder's own account is still left out. The stage orchestrator runs `git diff HEAD` itself and passes the output to the reviewer.

tests/fsm_flows/review_packet_support.py:153: AssertionError
=========================== short test summary info ============================
FAILED tests/fsm_flows/test_review_packet_notes.py::test_the_notes_use_the_latest_task_proof_of_a_task
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed, 5527 passed, 11 skipped in 1404.23s (0:23:24)
