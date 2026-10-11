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

**Built**: added `-H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN"` right after `curl -s` on every `curl` to `8765/comms` in 22 files under `src/pathly_data/core/` (skills, fragments, `agents/research/evaluator.md`); new `tests/consistency/test_fragments_run_token.py` (+ regenerated INDEX); 9 golden snapshots in `tests/snapshots/` regenerated.
**Proof**: `pytest tests/consistency/test_fragments_run_token.py` 2 passed (second test strips the header from a temp copy and asserts detection; both failed in the test-only commit); `pytest tests/install_skills` 417 passed, 2 skipped; `python scripts/check_adapters.py` exit 0 "Adapter consistency OK".
**Decisions**: header placed inline after `curl -s` (single-line curls need it on the same line; also covers inline-backtick curls in project-decompose/goalize). Snapshot diffs are only those curl lines gaining the header. The test treats a curl and its backslash continuations as one command. Non-curl mentions (`GET http...`, consult.md `POST http...`) are prose and unchanged.
**Shortcuts taken**: none. All files assume POSIX shell; none written for PowerShell. Adapter copies are not tracked in the tree (generated at install), so `python -m build` produced nothing to commit.
**For later tickets**: new fragments with a board curl must carry the header or the consistency test fails.

**Review fixes**: gate Lint failure (black would reformat tests/consistency/test_fragments_run_token.py): ran black on that file; black --check, file-size, mirror-reads, gen_test_index --check and lint-imports all pass; install_skills 417 passed, check_adapters exit 0.

## Review findings (round 1, gate)

gate: Build: python -m compileall -q src/pathly_orchestrator
gate: Test: python -m pytest tests/comms_board tests/db tests/runner_supervisor tests/http_api -q -x -p no:cacheprovider
gate: Lint: black --check src/ tests/ && python scripts/check_file_size.py && python scripts/check_no_mirror_reads.py && python scripts/gen_test_index.py --check && lint-imports
gate: Lint failed. the last lines of its output:
would reformat /home/user/pathly-adapters/tests/consistency/test_fragments_run_token.py

Oh no! 💥 💔 💥
1 file would be reformatted, 475 files would be left unchanged.
