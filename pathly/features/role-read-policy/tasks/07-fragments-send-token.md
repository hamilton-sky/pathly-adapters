# Send the run token on every board call in the core skills, fragments and agents

Type: task
Status: open
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

**Proof**:
- `python -m pytest tests/consistency/test_fragments_run_token.py -q -p no:cacheprovider` -> 43 passed, exit 0. It has one scan sanity test (at least 20 files found), 21 per-file "every board curl has the header" tests, and 21 per-file tests that copy the file to a temp dir, strip the header and assert the check then fails. At the test-only commit it was `21 failed, 22 passed` (the 21 real-tree tests failed).
- `python -m pytest tests/install_skills -q -p no:cacheprovider` -> 415 passed, 2 skipped, exit 0. Before updating snapshots 9 golden-snapshot tests failed, exactly the snapshots above. I regenerated them from `compose_skill(...)` and checked the diff by script: 19 lines modified by the header insertion only (removing the header from the new line gives the old line) and 26 pure added `-H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN" \` lines; nothing else changed.
- `python scripts/check_adapters.py` -> `Adapter consistency OK: ['antigravity', 'claude', 'codex', 'copilot']`, exit 0.
- commands.md Test (comms_board, db, runner_supervisor, http_api) -> 926 passed, 2 skipped. Lint: black clean (476 files), check_file_size OK (none new, none grown), check_no_mirror_reads OK, gen_test_index --check up to date, lint-imports 1 kept 0 broken. Build (compileall) ok.

**Decisions**:
- Single-line curls get the header inline right after `curl -s`; multi-line curls (trailing `\`) get one new continuation line with the same indent as the next line. The test treats a curl as its own line plus lines joined by a trailing backslash, so both shapes are covered.
- `python -m build` writes only `dist/` (git-ignored). The four adapters hold only `_meta/*.yaml`; no generated adapter copy of any skill text is tracked, so nothing was regenerated and nothing was hand-edited.
- No file is written for PowerShell; all edited curls are POSIX shell, unchanged assumption.

**Shortcuts taken**: Three board references are not `curl` and were left without a header, because the ticket scopes the edit to curl lines and adding one means rewording: `development/build.md` lines 101 and 131 (`GET http://127.0.0.1:8765/comms/tasks?...`) and `fragments/consult.md` line 16 (`POST http://127.0.0.1:8765/comms/post` plus a JSON body). An agent that turns those into curl will post as anonymous. The test scans only `curl` lines, so it does not see them. Worth upgrading if ticket 09 wants those paths stamped: rewrite them as curl blocks.

**For later tickets**:
- Ticket 09 (stamping): `development/build.md` and `consult.md` are the two files in the 23-file list that have no curl, so their calls may reach the server without a token.
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
