# Only the chief retires a binding directive, and hydration cannot forge one

Type: task
Status: open
Blocked by: 11, 12
Test first: yes

After ticket 12, only a chief token posts a binding directive. Four other paths can still retire
or forge one:

1. `/comms/post` with `supersedes` (#63, `_supersede_on_post.apply_supersedes`): any run whose
   token is on the project board can retire a project-board directive, and the governance block
   invites every agent to do so.
2. `/comms/supersede`: `refuse_agent_supersede` checks run tokens only for type and board, and a
   caller with no token passes.
3. `/comms/delete`: anyone may soft-delete the row, which drops it from `get_binding_decisions`.
4. `/comms/hydrate` and the fresh-clone import: `db/queries/comms_hydrate._insert_snapshot_row`
   inserts every real column a `BOARD.json` row carries, `binding`, `board`, `scope` and the
   `author_*` stamps included. Any process that can write a mirror file can plant
   `binding = 1, author_role = "chief", author_source = "token"`, and a feature `BOARD.json` can
   carry rows for the project board.

Close all four:

- Add `_supersede_on_post.is_binding(conn, message_id) -> bool` and
  `chief_may_retire(identity) -> bool` (a live run with role `chief`; the gate has already checked
  `decide` and the project). `apply_supersedes` skips a binding row with reason `binding` unless
  the caller may retire it. `refuse_agent_supersede` returns 403 `{"error": "only the chief
  retires a binding directive"}` for a binding `old_id` unless the caller may retire it, whether
  or not the caller sent a token. The routes do not change.
- `/comms/delete` on a binding row returns the same 403 for every caller (the chief gate already
  refuses `/comms/delete` for chief tokens; a directive is retired by superseding it). Put the
  check where the route needs no new lines, for example in the db layer's soft delete returning
  `"binding"`; `messages_crud.py` is at 395 lines and must stay at or under 400.
- Hydration: `_insert_snapshot_row` for `comms_messages` always stores `binding = 0`, skips a row
  whose `board` and `scope` differ from the board and scope of the file being hydrated
  (`hydrate_board(conn, board, scope, path)` knows them), and stores `author_source = "legacy"`
  for every row that names one (a stamp read from disk cannot be verified). A fresh clone
  therefore loses standing orders, and the chief posts them again; say so in the living doc.

Living docs: the binding-directive and hydration paragraphs in `src/pathly_orchestrator/CLAUDE.md`
(verify-then-fix).

## Not in this ticket

- Letting Studio retire a directive: waits for the UI token (RRP-2b), like posting one.
- Re-stamping non-binding hydrated rows other than `author_source`: `legacy` is enough for a read
  wall that trusts only `token`.

## Done when

- `python -m pytest tests/comms_board/test_binding_directive_guard.py -q -p no:cacheprovider`
  passes and covers, with a directive posted by an operator chief: a project-board planner token's
  `/comms/post` with `supersedes: [<directive>]` stores the post and reports the directive as
  skipped with reason `binding`, and the directive still reaches builder prompts;
  `/comms/supersede` on it with a project-board run token, with no token, and with no token and
  the server secret is 403; the operator chief's `/comms/supersede` succeeds; `/comms/delete` on it
  is 403 with no token; a feature `BOARD.json` holding a `binding: 1` project-board row hydrates
  into an empty DB without that row, and a project `BOARD.json` holding a `binding: 1` row with
  `author_source: "token"` hydrates it with `binding = 0` and `author_source = "legacy"`.
- `python -m pytest tests/comms_board/test_board_closure.py -q -p no:cacheprovider` still passes
  (#63's supersession tests).
- `python scripts/check_file_size.py` exits 0.

```check
$ python -m pytest tests/comms_board/test_binding_directive_guard.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/comms_board/test_board_closure.py -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_file_size.py
exit 0
```

## Reference

- `src/pathly_orchestrator/http_server/blueprints/comms/_supersede_on_post.py` (#63)
- `src/pathly_orchestrator/http_server/blueprints/comms/messages_crud.py::comms_delete`,
  `comms_supersede`
- `src/pathly_orchestrator/db/queries/comms_hydrate.py`, `board_mirror_hydrate.py::hydrate_board`
- `src/pathly_orchestrator/db/provenance_values.py` (`SOURCE_LEGACY`)

## Answer

### Built

Source:

- `http_server/run_identity.py`: `is_chief_run(identity)`, true for a live run whose role is `chief`.
- `http_server/blueprints/comms/_supersede_on_post.py`: `is_binding(conn, message_id)` (one static
  statement, `binding=1`, the flag `get_binding_decisions` reads), `chief_may_retire(identity)`,
  `BINDING_REFUSED`. `apply_supersedes` skips a binding row with reason `binding` unless the caller
  may retire it; `refuse_agent_supersede` returns 403 `only the chief retires a binding directive`
  for a binding `old_id` unless the caller may, before its run-token checks, so a caller with no
  token and one with only the server secret get it too. The two routes did not change.
- `db/queries/comms_messages.py::soft_delete_message` returns `"binding"` for a `binding = 1` row,
  for every caller and ahead of the `locked` check, so `force` does not get past it.
  `http_server/blueprints/comms/messages_crud.py::comms_delete` maps it to the 403 in two lines
  (the file is **exactly 400 lines**, the limit).
- `db/queries/comms_hydrate.py`: `_unverified(row)` is applied to a `comms_messages` row in
  `_insert_snapshot_row`: `binding = 0`, and an `author_source` the row names other than `none`
  becomes `legacy`.
- `board_mirror_hydrate.py`: `_belongs(msg, board, scope)`; `hydrate_board` stores only the message
  rows that belong to the file's board and scope, leaves out the artifacts of a row it left out,
  and re-embeds only stored rows.
- `http_server/blueprints/comms/directives.py` reuses `is_chief_run` (was an inline copy of the
  same test). `runner/comms_formatters.py`: the docstring of `_render_standing_orders` said the
  rule was not enforced; it now says the routes enforce it.

Docs: `src/pathly_orchestrator/CLAUDE.md` (the "Not enforced yet" paragraph is now "Who retires or
forges a standing order (chief-agent 16)" plus a "Still open" paragraph; the `/comms/post`,
`/comms/supersede`, `/comms/delete` and `/comms/hydrate` route lines; the supersedes table row;
the `run_identity.py` layout entry), `docs/WHAT_IS_PATHLY.md` (one sentence). Root `CLAUDE.md`,
`README.md` and `studio/CLAUDE.md` were checked and carry no claim that this ticket makes false.
A fresh clone loses its standing orders and the chief posts them again; the living doc says so.

Tests (test-only commit `ef78445`, then changed in this commit):

- `tests/comms_board/binding_guard_support.py` (helpers), `test_binding_directive_guard.py` (the
  named file), `test_board_hydrate_forgery.py` (round trips and the skip matrix),
  `test_binding_retire_writers.py` (source tripwires).
- `tests/comms_board/test_comms_provenance.py`: one assertion changed, see Decisions 10.
- `tests/INDEX.md` and `tests/comms_board/INDEX.md` regenerated.

### Proof

Run fresh after the last edit, on Python 3.12.3:

- `python -m pytest tests/comms_board/test_binding_directive_guard.py -q -p no:cacheprovider`:
  `43 passed`, exit 0.
- `python -m pytest tests/comms_board/test_board_closure.py -q -p no:cacheprovider`: `34 passed`,
  exit 0.
- `python scripts/check_file_size.py`: `OK: 1036 source files checked; 18 known over 400 lines,
  none new, none grown.`, exit 0.

Also run:

- `python -m pytest tests/comms_board -q -p no:cacheprovider` (after the last code edit): `1190
  passed`, exit 0.
- `python -m pytest tests/http_api -k chief -q -p no:cacheprovider`: `2071 passed, 155
  deselected`, exit 0. Only a comment, a docstring and docs changed after it started.
- Python 3.13.16 (`venv313`), the guard, forgery, retire-writers, board-closure and provenance
  files together: `214 passed`; an earlier 3.13 run over those plus the mirror-hydrate, directives
  route and query, delete and supersede files: `290 passed`.
- `black --check src tests` (665 files unchanged), `mypy src` (341 files, no issues),
  `lint-imports` (1 kept, 0 broken), `check_no_mirror_reads.py` OK, `gen_test_index.py --check`
  up to date, `bandit -ll` clean, `check_adapters.py`, `check_entry_points.py` and
  `check_version_sync.py` exit 0. I did not run the whole repo suite, as told.
- Test-first: `ef78445` holds only test files. On the base source its run failed for the specific
  reasons (`binding` rows retired, 200 where the ticket says 403, forged rows stored), not on a
  collection error. The floor guard on that commit was clean.
- Mutation checks were done: 24 mutants of my own code (one per behaviour: each of the three
  retire paths without its guard, the guard inverted, the chief test widened to any run token or to
  the server secret or to `None`, `binding>=1` in `is_binding`, `force` skipping the delete guard,
  `binding` kept on hydration, each of `board` and `scope` unchecked, project scope compared raw,
  `none` relabelled, `token` kept, artifacts of a left-out row kept, a non-dict row not skipped,
  and others) plus mutants of the tripwire scans. All were killed. Mutant `binding>=1` survived
  at first; `test_is_binding_and_the_standing_orders_query_never_disagree` was added and it is now
  killed.

### Decisions

1. `none` is not relabelled `legacy`. The ticket says "for every row that names one"; a row with
   `author_source = none` is withheld from a restricted role by `read_policy.row_allowed`, a
   `legacy` row is not, so relabelling would show a hidden row to a reviewer. The existing test
   `test_insert_message_row_round_trip_preserves_all_fields` also needs it. A `none` row cannot be
   verified as a chief anyway.
2. The artifacts of a message row that hydration left out are left out too, otherwise the file
   would plant artifact rows for messages that do not exist on this board.
3. A project scope is compared with `board_mirror._norm_project_root` on both sides (forward
   slashes, no trailing slash), the way the exporter writes it, so `C:\proj\` and `C:/proj` are one
   board and a row for another root, or one that differs in case, is skipped. Other boards are
   compared exactly. A row with no `board` or `scope`, or a non-object entry, is skipped.
4. `is_binding` lives in `_supersede_on_post.py` as the ticket says; `soft_delete_message` is in
   the db layer, which cannot import upward, so it reads the `binding` column in its own existing
   `SELECT` (the same predicate, `binding == 1`). `test_is_binding_and_the_standing_orders_query_
   never_disagree` pins `is_binding` and `get_binding_decisions` to one answer; the delete guard
   is covered by its own tests (a binding row is refused for every caller and for the db function
   called directly, an ordinary decision is still deleted) and is not tied to `is_binding` by a
   test.
5. `is_chief_run` was added to `run_identity.py` and `directives.py` now calls it, because ticket
   12 had the same test inline and the lead asked to reuse, not copy. `chief_may_retire` is
   `is_chief_run`.
6. One constant, `BINDING_REFUSED`, is the 403 text of the supersede refusal and of the delete
   route, so the two cannot drift.
7. In `apply_supersedes` the binding check comes after the board checks, so a row on another board
   still reports its existing reason.
8. `chief_may_retire(None)` is false: an in-process call with no request cannot retire a directive.
9. `/comms/delete` on a binding row is refused to a chief too (the chief gate already refuses the
   route to a chief token). A directive is retired by superseding it.
10. `test_comms_provenance.py::test_hydrating_a_pre_upgrade_snapshot_row_labels_it_legacy` asserted
    that a hydrated token-stamped row stays `token`. The ticket reverses exactly that, so its one
    assertion now reads `legacy` (with a comment saying why) and the comment on
    `_DYNAMIC_INSERT_ALLOW` was brought up to date. No check was loosened: the stamp is now
    asserted to be the weaker one.

### Shortcuts taken

None. One known edge, not a shortcut: the 400-line limit leaves `messages_crud.py` at exactly 400
lines, so the next change to that file must split it first.

### Other paths that can retire a binding directive

None found beyond the four closed. I read every writer of `deleted_at`, `superseded_by` and
`binding`: `/comms/post` `supersedes`, `/comms/supersede`, `/comms/delete`, `/comms/hydrate` (all
closed here), `/comms/acknowledge` (sets a read mark only), `/comms/answer` (a `question` row),
`restore` (it clears `deleted_at`, so it can only bring a row back), `purge_expired_trash` (no
caller), `dedupe_board` (it never touches a decision), the task and goal routes (they act on
`task`/`goal` rows), `promote`, the HQ actions (they go through the routes above) and `/db/query`
(read-only). A process with write access to the SQLite file itself can still do anything; that is
outside what a route can close. `test_binding_retire_writers.py` pins the set of statements that
write `deleted_at` or `superseded_by` and the callers of their functions, so a ticket that adds a
new way to retire a row fails it until the author decides whether a binding row is guarded.

### For later tickets

- Ticket 17 (and 13, which runs the two named test files): `binding = 0` after a hydrate means a
  fresh clone has no standing orders until the chief posts them again; a test that hydrates a
  project board and expects a directive to still bind will now fail by design.
- The Studio retire button and the UI token (RRP-2b) wait on a Studio caller being allowed to
  retire; today `chief_may_retire` accepts a live chief run only, so Studio (server secret, no
  token) gets the 403. That is the ticket's "Not in this ticket" and nothing was added for it.
- Still open, as the living doc says: no cap on the number or the total size of standing orders.
- Minors seen and not fixed (outside this ticket): `messages_crud.py` is at the 400-line limit;
  `comms_hydrate.insert_message_row` still stores `author_role` and `author_run_id` as the file
  names them (only `author_source` and `binding` are reset, as the ticket says; the read wall
  trusts `token` only); `hydrate_board` swallows a per-row insert error and reports success for the
  file, which is its documented behaviour.

## Review findings (round 1, quality review)

QUALITY
1. major src/pathly_orchestrator/board_mirror_hydrate.py:79-85 - `hydrate_board` now hashes ids from the file (`kept = {m.get("id") ...}`, `left_out`, `a.get("message_id") in left_out`) outside any try. A message row whose `id` is a list or dict raises `TypeError` out of a function documented as "Never raises". Failing input: a feature BOARD.json with messages `[{"id": [1], "board": "feature", "scope": "feat-q", ...}, <good row>]`.
   - Result at HEAD: `TypeError: unhashable type: 'list'` at line 79, and nothing is imported. At base 5b6c481 the same file imported the good row and returned True. A list/dict id on a row that is left out raises at line 80, and an unhashable artifact `message_id` raises at line 84.
   - Through `hydrate_project` the exception is swallowed by its outer try. One bad row in the project BOARD.json (the first candidate) silently stops hydration of every later feature board and the global board. I probed this: the feature row was imported at base and absent at HEAD. That is worse than a file of garbage JSON, which only skips its own board.
   - The ticket treats the mirror file as hostile input, so this is a boundary regression in the code it hardens.
   - Change: only count ids that are `str` when building `kept` and `left_out` (and compare `message_id` only when it is a `str`), or wrap the filtering in the same try as the read. Add a test with an unhashable `id` on a kept row, on a skipped row and on an artifact.
2. minor src/pathly_orchestrator/board_mirror_hydrate.py:46 - `_belongs` accepts a row whose project scope is spelled `<root>/` or `C:\proj`, but `insert_message_row` stores it under that spelling. The probe stored scope `'.../proj/'` and `get_all_messages(conn, "project", root)` returned `[]`, so the row never reaches the board. `test_a_project_root_is_compared_the_way_the_exporter_writes_it` only checks `count(id) == 1`, so it passes vacuously. `hydrate_project` already passes the normalised root and the exporter writes normalised scopes. Compare exactly, or store the normalised scope, and have the test assert the row is visible through `get_all_messages`.
3. minor tests/comms_board/test_binding_directive_guard.py - Nothing pins the order "binding before `locked`" in `soft_delete_message`. Mutants that check `locked` first, or that apply the binding check only when `read_by` is empty, survive the three new files plus closure, mirror-hydrate and provenance. No test deletes a binding row whose `read_by` names an agent. Today only hydration writes `read_by`, so the impact is small. At HEAD my probe gives 403 `REFUSED`; a mutant would give 409 `locked`. The `== 1` in `soft_delete_message` is also a third spelling of the flag, next to `_BINDING_SQL` and `get_binding_decisions`, and the "never disagree" test does not cover it. Add one test with `read_by='["builder"]'`, with and without `force`, expecting 403 and `"binding"`.
4. minor src/pathly_orchestrator/board_mirror_hydrate.py:81-85 - The artifact filter is negative: it drops only artifacts of rows that were left out. An artifact whose `message_id` is not in the file at all is imported. Probe: a feature BOARD.json planted artifact `a-planted` (path `/etc/hostname`) on the id of an existing project-board directive, and it was stored. This surface existed before the ticket. Keep an artifact only when `message_id in kept`, which loses nothing an export wrote.
5. minor Stale text, none of it relied on by a later ticket:
   - src/pathly_orchestrator/CLAUDE.md:235 still says a standing order stays "until it is superseded or deleted"; nobody can delete one now.
   - src/pathly_orchestrator/runner/comms_formatters.py:205-207 groups `/comms/delete` with the routes that "leave a binding row to a live chief run". Not even the chief can delete one.
   - board_mirror_hydrate.py:55 says "full-fidelity" and :58 says "Never raises" (see 1). db/queries/comms_hydrate.py:1-9 says rows are inserted "AS-IS (id/ts/status/... all preserved)", which the new paragraph below it contradicts.
   - src/pathly_orchestrator/CLAUDE.md:1547: the run_identity line that was edited still ends "Nothing applies a policy from it yet", which is false.
6. minor src/pathly_orchestrator/http_server/blueprints/comms/_supersede_on_post.py:50 - `BINDING_REFUSED` is shared by two route files but defined in one of them. SOLID rule 5 puts shared constants in `comms/_helpers.py`. Low cost to move.
7. minor src/pathly_orchestrator/http_server/blueprints/comms/messages_crud.py - It is exactly 400 lines. `check_file_size.py` passes, but any later ticket that edits it (17 or round two) has to split it first. Not a defect now.

Checks run (not findings):
- Range and what I read: I reviewed 5b6c481..6fa0382. `END` is HEAD, so no later commits were excluded. I read the ticket at 5b6c481 and never read its Answer. The diff hunks of `map.md` and `learnings.md` (author notes) reached me after I had formed finding 1 from the code and a probe.
- Tests: The three new test files pass: 87 on Python 3.12. Under 3.13 those three plus `test_board_closure.py`, `test_board_mirror_hydrate.py` and `test_comms_provenance.py` pass: 227. `tests/comms_board`, `tests/db` and `tests/consistency` pass on 3.12: 1399 passed, 2 skipped.
- Tooling: `check_file_size.py`, `gen_test_index.py --check` and `check_no_mirror_reads.py` are clean. black, mypy on all of `src/` and lint-imports are clean. Test basenames are unique across `tests/`.
- Weakened checks: The only loosened existing assertion is `tests/comms_board/test_comms_provenance.py:634` (`token` to `legacy`), plus two comment edits. No other assertion line was removed from `tests/`.
- Mutations: I ran 29 single-line mutants in a scratch copy; 27 were killed and 2 survived (both in finding 3). Hydration: keeping the file's `binding`, keeping its `author_source`, relabelling only `token`, relabelling `none`, dropping the scope check, ignoring `board`, exact project-scope compare, artifacts of skipped rows kept, artifacts of kept rows dropped, removing the non-dict check, applying `_unverified` to no table. Supersede and delete: dropping the binding skip in `apply_supersedes`; `chief_may_retire` always true, true for any run token, true for anonymous, or checking role only; the binding check removed or reordered in `refuse_agent_supersede`; the route's binding branch removed, 403 changed to 409, or the refusal text changed; the skip reason renamed; `is_binding` as `>= 1`; `soft_delete_message` binding check only without `force`.
- Callers: A feature-board run token on `/comms/supersede` gets 403 `REFUSED`. On `/comms/post` it gets a skip with reason `other_board`. No token and the server secret alone get 403/`binding`. `chief_may_retire(None)` is False and `is_binding` is False for unknown or empty ids. `is_binding` and the standing-orders query agree for flags 0, 1, 2 and -1. A run token with role `chief` but no chief session is stopped by the chief gate (401) before any route.
- Other writers: Delete is the only route that can trash a row. `dedupe_board` skips decisions, and consolidate, closure, acknowledge, answer and edit cannot retire a binding row. `/comms/restore` is unauthenticated. It reaches a binding row only to reset an active row's status to `pending`, or to un-trash a row trashed before this fix. It retires nothing. `test_binding_retire_writers.py` pins the writers and their callers.

REVIEW: FAIL
