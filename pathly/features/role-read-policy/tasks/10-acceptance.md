# Prove the identity and provenance layer end to end, and update the living docs

Type: task
Status: resolved
Blocked by: 02, 07, 09
Test first: no

Write `tests/comms_board/test_rrp_acceptance.py`, the bar in map.md, driving the real pieces
together (no mocks of the code this plan built):

1. Spawn an FSM stage through `supervisor/terminal.py` with a fake broadcaster; read `run_token`
   from the `TERMINAL_SPAWN` payload; it resolves to the stage's run and role.
2. With that token as `X-Pathly-Run-Token`, `POST /comms/post` a `discovery` with `from: "explorer"`
   through the Flask test client: stored as `author_role=builder` (or the stage's role),
   `author_source=token`.
3. Post a second row with no header: `author_source=none`.
4. `resolve_read_policy(conn, "reviewer", feature)` and `policy_predicate` select neither the
   builder discovery nor the unverified row; `row_allowed` agrees on both; a `decision` posted by
   the builder is still selected.
5. After the spawn settles, the token resolves to `None`.

Then update the living docs in the same commit (root `CLAUDE.md`, "Documentation sync"):
`src/pathly_orchestrator/CLAUDE.md` (comms board: provenance columns, `run_tokens`, the
`X-Pathly-Run-Token` header, `runner/read_policy.py` existing but not yet wired), and root
`CLAUDE.md` if its comms-board paragraph names who may read what. Add a `CHANGELOG.md` entry.

Run the full suite and the Studio typechecks once here.

## Not in this ticket

- Withholding anything from any agent: a later plan (RRP-4 onward).

## Done when

- `python -m pytest tests/comms_board/test_rrp_acceptance.py -q` passes.
- `python -m pytest tests/ -q -p no:cacheprovider` passes in full.
- Both Studio typechecks exit 0.
- `python scripts/gen_test_index.py --check` exits 0.

```check
$ python -m pytest tests/comms_board/test_rrp_acceptance.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/ -q -p no:cacheprovider
exit 0
prints passed
$ studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.node.json
exit 0
$ studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json
exit 0
$ python scripts/gen_test_index.py --check
exit 0
```

## Reference

- map.md "The bar"; SPEC.md § C1–C4
- Answers of tickets 01–09
- Root `CLAUDE.md` "Documentation sync", `src/pathly_orchestrator/CLAUDE.md`

## Answer

**Built**: `tests/comms_board/test_rrp_acceptance.py` (new, 7 tests, 303 lines); regenerated `tests/INDEX.md` and `tests/comms_board/INDEX.md`; `src/pathly_orchestrator/CLAUDE.md` (a new section "Who wrote a board row, and who may read it (role-read-policy)"; `db/queries/run_tokens.py`, `runner/read_policy.py` and the token functions of `terminal_identity.py` added to the package map; `run_token` added to the spawn-chokepoint diagram and to the `TERMINAL_SPAWN` row of the SSE table; the sentence "so the row keeps the caller's role" in the Author provenance paragraph reworded, see Decisions); `CHANGELOG.md` (a new top entry under Unreleased); this ticket's Status and Answer, and lines appended to `map.md` and `learnings.md`. No production code changed. Root `CLAUDE.md` is unchanged: its comms-board paragraph names no read rule (checked), so the ticket's condition does not apply.

**Proof** (every command run fresh on the final tree):
- `python -m pytest tests/comms_board/test_rrp_acceptance.py -q -p no:cacheprovider` -> `7 passed in 2.30s`, exit 0. The tests map to the ticket's steps: the payload token resolves mid-spawn to the stage's run id and role (`builder` for BUILDING, `reviewer` for REVIEWING), with feature `feat-rrp`, board `feature` and scope `feat-rrp`; the builder-token post labelled `explorer`, with the reviewer's run id in its body, is stored `('builder', <builder run>, 'token')` while `from_agent` and the body `run_id` are still stored as sent; the header-less post is `(None, None, 'none')`; for the reviewer's own identity `resolve_read_policy` gives the built-in wall (`exclude_authors == ['builder']`), `policy_predicate` selects the builder's `decision` and the reviewer's own discovery but neither the builder discovery nor the unverified row, `row_allowed` keeps exactly the same set over every row of the board, and those two are the only rows not selected; both tokens resolve to `None` after the spawns settle and a post made later with the dead token is `(None, None, 'none')`; `add_comms_provenance` (what every start runs) leaves all stamps alone and the unverified row is not relabelled `legacy`; `GET /comms` with the reviewer's live token returns all four rows.
- The test can fail. I mutated one line of `src/` at a time (bytes restored in a `finally`; `git status` on `src/` was empty after each) and ran the file: `caller_identity` never resolving a token -> 2 failed; `author_role` taken from the body's `from` -> 5 failed; `policy_predicate` withholding nothing -> 1 failed; `row_allowed` allowing everything -> 1 failed; the spawn never revoking -> 1 failed; no token minted -> 3 failed; the own-run exemption keyed on the body `run_id` column instead of `author_run_id` -> 1 failed; BUILDING minting `build` instead of `builder` -> 3 failed. Two mutations survived and cannot be reached through `/comms/post`: `post_message` storing NULL for a missing source (the route always passes a stamp) and `stamp()` trusting a role-less run (the `team` spawn always has a role); `tests/comms_board/test_comms_provenance.py` covers both.
- `python -m pytest tests/ -q -p no:cacheprovider` -> `2302 passed, 14 skipped in 348.38s (0:05:48)`, exit 0 (no skip markers added).
- `studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.node.json` -> exit 0; `-p studio/tsconfig.web.json` -> exit 0. `git status` shows no `*.tsbuildinfo` (both are git-ignored and I stage explicit paths only).
- `python scripts/gen_test_index.py --check` -> `All test INDEX.md files up to date.`, exit 0.
- Also, from commands.md and CI: `black --check src/ tests/` -> 480 files unchanged; `check_file_size.py` -> OK, none new, none grown; `check_no_mirror_reads.py` OK; `lint-imports` -> 1 kept, 0 broken; Build (`compileall`) and Smoke exit 0; `bandit -r src/ -ll -x src/pathly_data/` -> "No issues identified", 0 lines skipped by `#nosec`; `mypy src/ --ignore-missing-imports --no-strict-optional` -> no issues in 273 files; `check_version_sync.py`, `check_adapters.py`, `check_entry_points.py` OK.

**Decisions**:
- Two stages are spawned, BUILDING then REVIEWING, rather than minting the reviewer's token by hand. The role handed to `resolve_read_policy` is the one `caller_identity` returns for the reviewer stage's own token (asserted to be `"reviewer"`), so the test also pins that the `team` flow's REVIEWING mints the key the built-in policy is written in.
- The labels are chosen so only the server's stamp can explain a result: the builder's discovery says `explorer` and carries the reviewer's run id in its body (SPEC section E, own-post case); the header-less post also says `explorer`; the reviewer's own discovery says `builder` and stays visible.
- Beyond the five steps I added two small tests and one extra assertion, each a consequence of the same chain: a post made with a dead token is `none` (an extra assertion in the step 5 test); a restart's backfill keeps the stamps (a test); and `GET /comms` still returns every row (a test), which is the plan's "nothing is withheld" made executable. Only `GET /comms` is pinned: `POST /comms/search` in keyword mode returns `[]` when FTS5 is missing, so it would prove nothing on such a machine, and the pushed context needs the embedding path.
- Doc claim "keeps the caller's role", checked against the code. `/code/query`'s log row (`code/query.py:196`), `/record_phase`'s row (`ops/_phase_board.py:60`) and the context-pull trail (`comms/artifacts.py:247`) are stamped from `stamp(caller_identity(request))`, so they carry a role only when the request sends a live token. A grep of `src/pathly_data/core` shows the agent `curl`s to `/code/query` (`fragments/code-query.md`) and to `/record_phase` (`utilities/log-phase.md`, `development/design.md`, `planning/storm.md`) send no `X-Pathly-Run-Token`, so those rows are `none` today. I reworded the sentence to that and did not touch the skill files, as instructed; the gap is an open item in `map.md`.
- `src/pathly_orchestrator/CLAUDE.md` got additions, not a rewrite; every claim in the new section was checked against the code (for instance that nothing outside `read_policy.py` references it and that no code reads `read_policy.mode`: both greps were empty). The CHANGELOG entry sits at the top of Unreleased with no version bump, like the entries below it.
- The four findings from ticket 09's review were checked before I wrote them down. `_spawn_role` against the 10 packaged flows' `role_map`: 13 (flow, state) pairs differ, including quick-fix and debug FIXING (`build`), debug VERIFYING (`verify`) and the consultation PLANNING states. `POST /db/query` with `WITH t AS (SELECT 1) INSERT ...` returned 200 and created both a `run_tokens` row and a `comms_messages` row stamped `explorer/run-x/token` (on a scratch DB with `Path.home` patched; the real DB's mtime was unchanged). `update_message_text` touches only `text` and `/comms/edit` reads no caller identity. `stamp()` returns the role as minted. All are in `map.md` and `learnings.md` as open items for RRP-4.

**Shortcuts taken**:
- The agent is simulated. The broadcaster posts with the payload's token the way a fragment's `curl` would; no CLI process runs, so the hosts' `PATHLY_RUN_TOKEN` export and the fragments' header are not links in this chain. A regression in either would not fail this test; they are pinned by `tests/runner_supervisor/test_pty_host.py`, `studio/src/main/ipc/terminal/spawnEnv.test.ts` and `tests/consistency/test_fragments_run_token.py`. Worth upgrading only if a host/fragment mismatch ever shows up: spawn a real `pathly-pty-host` child that `curl`s with `$PATHLY_RUN_TOKEN`.
- Only the `team` flow's BUILDING and REVIEWING stages are spawned, so the roles minted by other flows are not proved (see the `_spawn_role` open item).
- `GET /comms` is the only read path pinned as unfiltered.

**For later tickets**:
- This is the last ticket of the plan. The next plan to start is chief-agent (`/feature-flow chief-agent auto`, same branch). It can use `caller_identity`, `stamp` / `post_system`, `run_tokens`, and `resolve_read_policy` / `policy_predicate` (the `chief` built-in is in `BUILTIN_DEFAULTS`).
- A spawn whose role cannot be resolved mints `role=None` and its posts are stored `none`. A chief spawn is only stamped `chief` if its role resolves, through a board run (`state.current_state`) or an `agent_map` entry.
- The plan that wires the policy in `enforce` must change `test_get_comms_still_returns_every_row_to_a_reviewer` on purpose; it fails the day a read path starts withholding.
- RRP-4 open items, all in `map.md`: `_spawn_role` versus `role_map`; `POST /db/query` forging provenance and minting tokens; `POST /comms/edit` keeping the original stamp; roles not normalised by `stamp()`; the agent `curl`s to `/code/query` and `/record_phase` sending no token.
