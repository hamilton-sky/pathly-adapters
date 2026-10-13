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
