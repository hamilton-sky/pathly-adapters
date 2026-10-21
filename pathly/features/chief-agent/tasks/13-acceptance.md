# Prove the chief core end to end

Type: task
Status: resolved
Blocked by: 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 14, 15, 16, 17
Test first: no

Write `tests/comms_board/test_chief_acceptance.py`: the brief's bar, run against the real Flask
app and the real supervisor, with a fake spawn host: a thread reading a queue registered in
`sse._spawn_clients` (what `/events/spawn` clients get) that records every payload and, for a
worker `TERMINAL_SPAWN`, marks the run started and finished the way
`tests/comms_board/test_rrp_acceptance.py` does. One scenario per bar item:

1. Open: `POST /chief/open` with engine `claude`, preset `operator` and a prompt that starts with
   front matter → 201 with `tier: "operator"`; the recorded `TERMINAL_SPAWN` has
   `interactive: true` and `submit: false`, its `prompt` is the text without front matter
   followed by the `chief-connect` fragment and contains no token, its `argv` starts claude in
   restricted mode with `--session-id`, and its `run_token` resolves to role `chief` with the
   session's run id.
2. Operator acts through the API: with that token, `POST /comms/post` creates a `goal` on the
   project board, and `POST /runs` starts a single run; the fake host sees a second
   `TERMINAL_SPAWN` whose token resolves to the worker's role (not `chief`), proving the run went
   through `_run_stage_via_terminal`. Resolve it in the host thread before marking the run
   finished: the spawn revokes its token when it settles.
3. Status is read-only: close the operator, open with preset `status`; `GET /comms?feature=<f>`
   is 200 and `POST /comms/post` is 403.
4. Cited answers: with a `RunnerState` waiting in `_await_agent_question`, an uncited chief answer
   is 403 and the question stays pending; a chief answer that cites a later human message but
   carries its own `answer` text is 403; citing that message alone delivers the message's text
   to the agent, and citing it again for a second question is 403. A `to_agent: "human"`
   escalation is acknowledged by the chief only with a cite recorded after it. The test states
   the limit in a comment: Pathly relays the user's real words, but to the question the chief
   picked.
5. Binding directive: an operator chief posts a `*` directive, `/comms/acknowledge` marks it, and
   `fsm_compose.build_prompt` for the `team/build`, `team/review` and `team/test` agents of a
   feature in the project carries its text in the standing-orders block. A project-board run
   token's `supersedes` naming it, and a token-less `/comms/supersede` of it, leave it in place.
6. Limits: an operator chief's `POST /runs` above `chief.max_cost_usd_per_run` is 403, and a run
   control call on a run of another project is 403.
7. Usable from the tab: `pathly api GET /chief/session?project_root=…`, run as a subprocess with
   the chief's token in `PATHLY_RUN_TOKEN`, exits 0.
8. Token stays off the open streams: queues registered on `/events/runner` (the chief's topic and a
   worker's) and on `/events/runs` receive the spawns without `run_token`; the `/events/spawn`
   queue receives it.

Then the release notes: a CHANGELOG "Unreleased" entry whose heading ends in `(chief-agent)`, in
the style of the role-read-policy entry: what exists, what is refused, the three holes closed,
and the gaps that wait for round two and RRP-2b. Check every living doc touched by tickets 01 to
12 and 14 to 17 against the code once more (verify-then-fix, do not rewrite).
Regenerate the test indexes and run the full suite.

## Not in this ticket

- Studio, the friendly `pathly` commands, the overview and inbox calls, the badge and the
  re-queue: round two.

## Done when

- `python -m pytest tests/comms_board/test_chief_acceptance.py -q -p no:cacheprovider` passes.
- `python -m pytest tests/ -q -p no:cacheprovider` passes in full.
- `python scripts/gen_test_index.py --check` exits 0.
- `CHANGELOG.md` has a `### ... (chief-agent)` entry under "Unreleased".

```check
$ python -m pytest tests/comms_board/test_chief_acceptance.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/ -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/gen_test_index.py --check
exit 0
$ grep -n "(chief-agent)" CHANGELOG.md
exit 0
prints (chief-agent)
```

## Reference

- map.md (the bar), spec.md § Goal and the bar, § Happy path
- `tests/comms_board/test_rrp_acceptance.py` (fake host, `client` fixture, token helpers)
- `tests/conftest.py` (fresh temporary DB per test; `get_db()` is per thread)

## Answer

Work started at `2c5c16278bab08cedc73f80ca65f0e5ec91fe708`.

### Built

- `tests/comms_board/test_chief_acceptance.py` (new, 665 lines, 15 tests), with two helper modules
  beside it that it imports by bare name: `chief_acceptance_support.py` (349 lines: `SpawnHost`, the
  fixtures, the leak guard, `open_chief`, `type_in_tab`, `serving`) and `chief_acceptance_calls.py`
  (292 lines: the waiting agent question, the request builders, the `pathly api` subprocess). The
  tests: scenario 1 three (open with a `prompt` that has front matter, open without a `prompt`, a
  preset with no built-in text), scenario 2 one, scenario 3 two (status, and planner as the tier
  between), scenario 4 two (an agent question, a human escalation), scenario 5 two, scenario 6 three,
  scenario 7 one, scenario 8 one.
- `CHANGELOG.md`: a new `### Board — a chief agent that works the board through a gated API
  (chief-agent)` entry at the top of "Unreleased" (lines 5 to 81), and one corrected sentence in the
  role-read-policy entry (lines 212 to 215).
- `src/pathly_orchestrator/CLAUDE.md` lines 548 to 549: one corrected sentence.
- `tests/INDEX.md` and `tests/comms_board/INDEX.md` regenerated (comms_board 66 to 67 files).
- `map.md`: one `13 —` line under "Decisions so far". `learnings.md`: two `(13)` lines.
- No production code changed: none of the scenarios exposed a defect.

### Proof

Every command below was run fresh after the last edit to the tree (the only edit after the full
suite started was a docstring in the new test file; the acceptance file was run again after it, on
all three Pythons).

- `python -m pytest tests/comms_board/test_chief_acceptance.py -q -p no:cacheprovider`: `15 passed in
  5.40s`, exit 0 on 3.12.3. The same on 3.13.16 (`15 passed in 5.52s`) and 3.11.17 (`15 passed in
  5.34s`).
- `python -m pytest tests/ -q -p no:cacheprovider` in full on 3.12.3 (the output file has no FAILED or
  ERROR line): `6039 passed, 14 skipped in 1324.75s (0:22:04)`. None of the 14 skips is in the new
  file, which has no skip.
- `python scripts/gen_test_index.py --check`: `All test INDEX.md files up to date.`, exit 0, after
  `python scripts/gen_test_index.py` wrote the two indexes.
- `grep -n "(chief-agent)" CHANGELOG.md`: `5:### Board — a chief agent that works the board through
  a gated API (chief-agent)`, exit 0.
- Lint chain of `commands.md`: `black --check src/ tests/` (679 files unchanged), `mypy src/
  --ignore-missing-imports --no-strict-optional` (`no issues found in 343 source files`),
  `lint-imports` (1 kept, 0 broken), `check_file_size.py` (`1038 source files checked; 18 known over
  400 lines, none new, none grown`), `check_no_mirror_reads.py` (OK), `check_version_sync.py` (`OK:
  2.24.1`) all exit 0. Bandit was not run: no file under `src/` other than a `CLAUDE.md` changed. No
  duplicate test basename (`find tests -name "*.py" | sort | uniq -d` prints nothing). The three new
  files contain no `skip`, `xfail`, `noqa`, `type: ignore` or `fmt:` text except the key
  `supersede_skipped`, which the board returns.
- **Mutation** (a scratch copy of the repo at `scratchpad/rv13`, one-line reverts in `src/`, the
  acceptance file run per mutant): 31 mutants, 31 killed, 0 survivors, each by a named failing test.
  They are: gate tier check dropped; status may post; planner may decide; a closed session not
  refused; an uncited answer passes; the chief's own `answer` text passes; a citation can be reused;
  a message from before the question is citable; a relayed message is citable; a human escalation
  needs no cite; an acknowledgement signed as the person; standing orders not injected; a `supersedes`
  list retires a binding row; a token-less `/comms/supersede` retires one; `/comms/delete` of one is
  allowed; the chief may not retire one either; cost ceiling dropped; run limit dropped; a refused
  start keeps its slot; project binding by id dropped; `pathly api` sends no token; the token back on
  `/events/runs`; the token back on `/events/runner`; the paste submitted; claude not `--restricted`;
  `--tools` dropped; `--strict-mcp-config` dropped; front matter pasted; the root line missing; a
  worker token not revoked; the tab not killed on close. The first harness run printed 27 KILLED with
  empty failure lists because it ran the system python, which has no pytest; I fixed it to call the
  venv python and to count a mutant killed only when a named test failed, then reran all of them.
- **Hygiene** (the ticket-17 lesson). With HOME at an empty folder and a throwaway plugin that sleeps
  40 seconds after the session (past the chief watcher's 30 second start timeout) and then lists
  threads and files: `HYGIENE threads: []`, `HYGIENE under HOME: []`, `15 passed in 45.74s`. With the
  guard's import deleted from a copy of the test module: `HYGIENE threads` lists 14
  `chief-watch-chief-...` threads and `HYGIENE under HOME` lists `.pathly/pathly.db`, `-shm`, `-wal`
  and `.pathly/global/BOARD.json`, and all 15 tests still pass, so only the guard sees it. A second
  leak came to light: the process-wide `event-mirror-flusher` and `board-mirror-flusher` threads, if
  they wake between two tests with a mark queued, open the DB of the unpatched home. One run in eight
  showed it; the guard now drains both mirrors at teardown. Over the final code, 30 traced runs
  (HOME at an empty folder, `sqlite3.connect` wrapped to print any open under HOME): `bad=0 of 30`.
  The same loop on a copy with the two drain lines removed: `bad=3 of 24`.

### Decisions

- **The tests follow the code, not the ticket text** (the stale points the caller listed). Scenario 1:
  the pasted prompt is `strip_front_matter(style)` + the `chief-connect` fragment + the root line
  `Your project root: <stored root>`, and `POST /chief/open` without a `prompt` is covered too.
  Scenario 4: a human escalation is acknowledged with `{"message_id", "agent": "chief", "cite"}`;
  `agent: "human"` is refused and spends nothing. Scenario 5: the project-board token's `supersedes` is
  skipped with reason `binding`, a token-less `/comms/supersede` is 403, `/comms/delete` of a binding
  row is 403 for no token, a planner token and the chief. Scenario 6: the cost ceiling, the run limit,
  and a run of another project. Scenario 7: a `pathly api` subprocess with `PATHLY_RUN_TOKEN` exits
  0. Scenario 8: `/events/runner` and `/events/runs` have no `run_token`, `/events/spawn` has it.
- **Scenario 7 runs the module, not the console script**: `python -m pathly_orchestrator.chief_cli api`
  with `PYTHONPATH=src`, HOME at the test's folder, against the app served by `werkzeug.make_server` on
  a free port, because the `pathly` script may not be on the CI `PATH`. It makes three calls: the
  ticket's read (exit 0), a goal post (the board stamps it as the chief's run, so the token was sent)
  and `PUT /db/settings/...` (exit 1, the gate's body printed). The refusal is not `/events/spawn`:
  a stream would hang if the token were missing. The token is checked to appear in no output.
- **Scenario 6 uses `busy("demo")`**: a flow start that passes the gate then ends as a route 409, so
  the test shows the ceiling is what separates 403 from the route's answer without spawning a flow.
  It also shows the chief cannot raise its own ceiling (`PUT /db/settings/...` is 403 with `allowed`)
  and that a refused start costs no slot.
- **Scenario 4 states the limit in a comment**: Pathly relays the person's real words once, but to the
  question the chief picked. Both questions are asked before the person's words are typed, so the
  reuse refusal (and not the timestamp rule) is what stops the second use.
- **Beyond the ticket**: the planner tier (scenario 3 has a second test), a relayed message cannot be
  cited, an acknowledgement signed as the person is refused, and the chief's token is shown to be
  revoked and its tab killed on close. Each closes a gap that a mutant showed.
- **The leak guard is imported by name** into the test module (an autouse fixture in a support module
  runs only where it is imported), and it also clears `board_lock._held` and drains the mirrors.
- **CHANGELOG**: the entry is 77 lines against the role-read-policy entry's 50, because the feature is
  larger. Every claim in it was checked against the code or a test (the refusals against the ones the
  scenarios and the named gate, cite and binding test files drive). The three holes of tickets 01 to
  03 are named. The limits listed are the ones the living docs already state: the raw token on
  `/events/spawn`, a `human` row being "what the hook recorded", the scheduled-task prompt stored as
  typed, the cite-free `/comms/answer` of a headless agent an operator chief starts, standing orders
  lost on a fresh clone, id-addressed reads and fleet-wide totals unbound, and round two items.
- **Doc pass** (verify-then-fix; tickets 01 to 12 and 14 to 17; two demonstrably false claims, both
  fixed): (1) `CHANGELOG.md:212-215`, role-read-policy "Known limits": a hydrated board "keeps the
  stamps written in the file" was untrue after ticket 16, which stores every `author_source` but
  `none` as `legacy`; it now says `author_role` and `author_run_id` are kept and `author_source`
  becomes `legacy`. (2) `src/pathly_orchestrator/CLAUDE.md:548-549`: "a human opens for a project from
  Studio's launcher" is untrue (no Studio code calls `/chief/open`); it now says Studio has no
  launcher yet and `POST /chief/open` is called directly. Checked against the code and left alone:
  root `CLAUDE.md` (the `chief/` and `comms/directives` rows of the blueprint map, the `pathly api`
  line), `src/pathly_data/CLAUDE.md:254-258` (the `chief-connect` fragment outside
  `composition.yaml`, its checking tests exist), `docs/WHAT_IS_PATHLY.md:130-138` (the standing-order
  rules match scenario 5), the rest of the chief sections of `src/pathly_orchestrator/CLAUDE.md`
  (every file, class and function it names exists; the route table, `GET /chief/session` fields, the
  tier table, the budget defaults and the retire/hydrate/delete rules match the code and the
  scenarios). `docs/API.md` and `studio/CLAUDE.md` were not touched by these tickets and name nothing
  they changed. Carried reviewer minors left alone, as told: the `CLAUDE_CODE_DISABLE_*` switches,
  where `BINDING_REFUSED` lives, `messages_crud.py` at 400 lines, the `pathly api` output cap and
  stray prose pins.

### Shortcuts taken

- No scenario opens a real `claude`: `SpawnHost` stands in for Studio, so that claude honours
  `--restricted`, that its hook fires and that the person's words reach the cite are not checked
  here (ticket 19 is the planned live check). The test module says so.
- The guard clears `board_lock._held` through the module's private lock, to release a board lock a
  test left behind. Worth replacing with a public call if `board_lock` ever gets one.
- The 40 second hygiene proof and the HOME trace are procedures run once by hand (above), not CI
  tests; the guard itself asserts every thread the module starts is gone and fails the test when not.
- Scenario 8 attaches its queues by replacing `sse._runner_clients` and `sse._run_clients` with a dict
  that hands one queue to every key (`Subscribed`), because the topic and run ids do not exist before
  the spawns. It would stop working if those registries stopped being dicts read through `get`.

### For later tickets

- Ticket 19 (the daycap guard spike) can use `SpawnHost` only for the open path; it needs a real
  claude. Its text says to confirm the guard does not run in the chief tab with the chief open: that
  is the first real check of `--restricted` and of the hook.
- Any new test that opens a chief must import `_no_watcher_outlives_its_test` by name from
  `chief_acceptance_support` (or define its own): a chief left open starts a `chief-watch-*` thread
  that wakes 30 seconds later in a later test with no patched home.
- The two mirror flushers are process-wide: a test that writes a board and ends without draining them
  can touch the real `~/.pathly`. `learnings.md` (13) has the trace recipe.
