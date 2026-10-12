# Send the run token on every board call in the core skills, fragments and agents

Type: task
Status: resolved
Blocked by: 05, 06
Test first: yes

Agents reach the board through `curl` lines in `src/pathly_data/core/`. Every one that calls
`http://127.0.0.1:8765/comms` must send `-H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN"` (SPEC.md
§ C4). Today that is 22 skill and fragment files plus `agents/research/evaluator.md`; find them
with `grep -rl "8765/comms" src/pathly_data/core`. Keep each edit to the added header line: no
other wording changes. The fragments already assume a POSIX shell for `curl`; keep that
assumption, and note in the Answer if any file is written for PowerShell.

Add a consistency test that fails when any `curl` to `8765/comms` under `src/pathly_data/core/`
lacks the header, so a new fragment cannot forget it. Then rebuild the adapter copies with the
repo's tooling (`python -m build` per the root `CLAUDE.md`) if the adapters are generated into
the tree, and commit what it regenerates; do not hand-edit generated adapter files.

Snapshots: this ticket edits skill and fragment text that snapshot tests may pin. Update a snapshot
only where the diff is exactly the added header line.

## Not in this ticket

- Server-side use of the header: tickets 06 (identity) and 09 (stamping).
- Interactive `/pathly` runs: they have no `PATHLY_RUN_TOKEN`, send an empty header, and resolve
  to `anonymous`, which is today's behaviour.

## Done when

- `python -m pytest tests/consistency/test_fragments_run_token.py -q` passes, and fails if the
  header is removed from any one file (the test proves this with a temp copy).
- `python -m pytest tests/install_skills -q` passes (compose, snapshots and adapter checks).
- `python scripts/check_adapters.py` exits 0.

```check
$ python -m pytest tests/consistency/test_fragments_run_token.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/install_skills -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_adapters.py
exit 0
```

## Reference

- SPEC.md § C4
- `src/pathly_data/CLAUDE.md` (core → adapter sync rule, how adapters are rebuilt)
- `tests/install_skills/test_board_search_fragment.py` (existing fragment test to follow)
- Tickets 05 and 06 Answers

## Answer

**Built**: 21 core files under `src/pathly_data/core/` now send `-H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN"` on every `curl` to `8765/comms` (56 curls: 20 skill and fragment files plus `agents/research/evaluator.md`); new `tests/consistency/test_fragments_run_token.py` (committed first and failing, 21 of 43 tests red); the 9 composed-skill snapshots in `tests/snapshots/` (`team/{build,review,test,design,retro}`, `planning/plan`, `development/{build,review,test}`); regenerated `tests/INDEX.md` and `tests/consistency/INDEX.md`; living doc `src/pathly_data/CLAUDE.md` (one paragraph under Skill composition).

Review round 1 added: one `Send ... on ...` instruction line in each of 10 `.md` files (`development/{drain-dag,build,review}.md`, `team/{build,review}.md`, `fragments/consult.md`, `custom/testing.md`, `planning/{plan,goalize,consolidate}.md`); the rewritten test (`_goes_on` continuation scan, pseudo-request check, synthetic tests); 6 snapshots regenerated (`team/{build,review,test}`, `planning/plan`, `development/{build,review}`); the rewritten paragraph in `src/pathly_data/CLAUDE.md`; a line each in `map.md` and `learnings.md`.

**Proof**:
- `python -m pytest tests/consistency/test_fragments_run_token.py -q -p no:cacheprovider` -> 41 passed, exit 0 (after review round 1). It has one scan sanity test, 21 per-file "every board curl has the header" tests, 10 per-file "a file with pseudo-requests tells the agent to send the token" tests, two temp-copy tests (strip the header from each of the 21 curl files; strip the instruction line from each of the 10 pseudo-request files; each must then fail the check) and 7 synthetic scanner tests. At the round 1 test-only commit it was `10 failed, 31 passed` (exactly the 10 pseudo-request files red). At the original test-only commit it was `21 failed, 22 passed`.
- `python -m pytest tests/install_skills -q -p no:cacheprovider` -> 415 passed, 2 skipped, exit 0. Before the round 1 content change 6 golden-snapshot tests failed (`team/{build,review,test}`, `planning/plan`, `development/{build,review}`). I regenerated them from `compose_skill(...)` and checked by script (difflib opcodes) that every change is a pure insert and every inserted line is one of the new `Send ... on ...` instruction lines: 8 lines added, 0 removed. The original 9 snapshots' header lines are untouched: 19 lines modified by the header insertion only and 26 pure added `-H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN" \` lines.
- `python scripts/check_adapters.py` -> `Adapter consistency OK: ['antigravity', 'claude', 'codex', 'copilot']`, exit 0.
- commands.md after the round 1 fix: Build (compileall) exit 0; Smoke exit 0; Lint: black clean (476 files), check_file_size OK (932 files, none new, none grown), check_no_mirror_reads OK, gen_test_index --check up to date, lint-imports 1 kept 0 broken, exit 0; Test (comms_board, db, runner_supervisor, http_api, the token test) -> 967 passed, 2 skipped, exit 0.

**Decisions**:
- Single-line curls get the header inline right after `curl -s`; multi-line curls (trailing `\`) get one new continuation line with the same indent as the next line. The test treats a curl as its own line plus the following lines while the previous one ends in a backslash or leaves a quote open, so both shapes and a multi-line `-d` body are covered.
- `python -m build` writes only `dist/` (git-ignored). The four adapters hold only `_meta/*.yaml`; no generated adapter copy of any skill text is tracked, so nothing was regenerated and nothing was hand-edited.
- No file is written for PowerShell; all edited curls are POSIX shell, unchanged assumption.

**Shortcuts taken**: The bare pseudo-requests (`GET|POST ... /comms/...`, no `curl`) are not rewritten as curl; each of the 10 `.md` files that holds one gets a single instruction line telling the agent to send the header, and the test checks that line exists in the file. It cannot check that an agent obeys it, and a file holding both pseudo-requests and curls needs the line outside the curls (the curls' own header does not count). Where it stops working: a pseudo-request written without a verb or without `/comms`, and a curl to a shell-variable URL, are not seen by the scan (stated in the test docstring and `src/pathly_data/CLAUDE.md`). Worth upgrading if ticket 09 wants these calls stamped without trusting the agent: rewrite them as curl blocks.

**Review fixes** (round 1, quality review):
1. major, pseudo-request calls carry no token: took the smallest fix. Added one `Send `-H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN"` on ...` line to each of the 10 `.md` files the scan flags: `development/drain-dag.md`, `team/review.md`, `development/review.md`, `team/build.md`, `development/build.md`, `fragments/consult.md`, `custom/testing.md`, `planning/plan.md`, `planning/goalize.md`, and `planning/consolidate.md` (its line 12 `POST /comms/consolidate` matches the same pattern; the reviewer's list did not name it, but the scan does, so it got the line too). No other wording changed. The test now flags a `.md` file that has a `VERB [http://127.0.0.1:8765]/comms` line outside a board curl but no line outside the curls naming the header, so a header inside the file's own curls (plan.md, goalize.md, team/build.md) does not satisfy it. Pseudo-requests are read in `.md` files only: `composition.yaml` has a `POST /comms/run` in a comment, which is config prose, not an agent instruction. 6 composed snapshots regenerated, only added lines (script-checked, see Proof). The `development/build.md` and `consult.md` gap that the original Shortcuts note named is closed.
2. minor, CLAUDE.md paragraph understated the gap: rewrote the "Run token" paragraph in `src/pathly_data/CLAUDE.md` (retitled "on every board call") to say what the pseudo-request handling is (an instruction line per `.md` file, checked by the test), its textual limits, and that a new fragment of either shape must follow it.
3. minor, `_board_curls` continuation bug: the old loop tested the accumulated command, so a blank line after a trailing backslash made the next line join the command and let a missing header borrow a later curl's header. The scanner now decides continuation per line (`_goes_on`: the last line added ends in a backslash, or a quote opened by the command is still open, tracked from the `curl` token). A synthetic test pins it.
4. minor, 21 repeated strip tests: replaced by two temp-copy tests that loop over the real files (header strip over the 21 curl files, instruction strip over the 10 pseudo-request files, still the "temp copy" proof the Done when names) plus 7 synthetic scanner tests: two curls one missing, header on a later continuation line, continuation that never reaches the header, blank line after a backslash, header after a multi-line `-d` body (and the same body without the header flagged), shell-variable URL not seen, and pseudo-request handling. The shell-variable-URL limit is in the module docstring. I made the quote-awareness part of the scanner rather than only noting the multi-line-body shape as a limit, because a plain "backslash ends the line" rule would flag a correct curl whose header follows a multi-line body.
5. minor, `supervisor/board_run.py:416`: not changed (outside `core/`, and the instruction was not to touch it). Recorded in `map.md` (decision line `07 (review round 1)`) and `learnings.md` as a note for ticket 09: the Python-built board-run prompt tells the agent to `POST http://127.0.0.1:8765/comms/post` with a JSON body and no token header. A grep of `src/pathly_orchestrator` for `8765/comms` finds only that one.

**For later tickets**:
- Ticket 09 (stamping): `supervisor/board_run.py:416` (board-run prompt, outside `core/`) still gives the agent a token-less `POST /comms/post`; add the header line there. Calls in the 10 `.md` files above rely on the agent following the instruction line, so a missing token is still possible for them and the server must keep treating it as `anonymous` / `author_source=none`.
- The header value is the empty string for interactive runs (`$PATHLY_RUN_TOKEN` unset); ticket 06's `caller_identity` already treats empty as `anonymous`.
- Any future change to composed skill text needs the 9 snapshots regenerated; the pattern is writing `compose_skill(skill, "claude")` to `tests/snapshots/<skill with / as __>.claude.md`.

## Review findings (round 1, quality review)

QUALITY
1. major tests/consistency/test_fragments_run_token.py, src/pathly_data/core/skills/development/drain-dag.md: about 25 agent-run board calls written as `GET|POST [http://127.0.0.1:8765]/comms/...` pseudo-requests carry no token and the scanner skips them (drain-dag.md 8 calls, team/review.md and development/review.md artifacts/section, team/build.md 3, development/build.md 5, fragments/consult.md 1, custom/testing.md 3, plan.md and goalize.md 1 each). The ticket counted build.md and consult.md among the files to edit; both untouched. The "a new fragment cannot forget it" promise is false for this style - extend the scan to flag such lines in a file that never mentions X-Pathly-Run-Token, or rewrite them in curl form, and add an instruction line per affected skill to send -H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN".
2. minor src/pathly_data/CLAUDE.md: the new paragraph understates the pseudo-request gap - fix it together with 1.
3. minor tests/consistency/test_fragments_run_token.py: _board_curls tests the accumulated command's rstrip().endswith("\\") so a blank line after a trailing backslash swallows the next curl - test lines[j].rstrip().endswith("\\").
4. minor tests/consistency/test_fragments_run_token.py: test_removing_the_header_from_a_file_is_caught repeats the same logic 21 times and strips every header at once; add synthetic per-curl cases and note the shell-variable-URL limitation in the docstring.
5. minor src/pathly_orchestrator/supervisor/board_run.py:416: the Python-built board-run prompt tells the agent to POST http://127.0.0.1:8765/comms/post with no token; outside core/ and this ticket, record it in map.md or ticket 09.

REVIEW: FAIL
