# Stamp an edited board row with the editor, not the original author

Type: task
Status: resolved
Blocked by: —
Test first: yes

`POST /comms/edit` (`blueprints/comms/messages_crud.py::comms_edit`) calls
`db/queries/comms_messages.py::update_message_text`, which changes `text` only. The row keeps its
`author_role` / `author_run_id` / `author_source`, so anyone can put words under a reviewer's
token stamp, and a read wall that trusts `author_source="token"` would trust them.

Re-stamp on edit: `comms_edit` computes `stamp(caller_identity(request))` (as `comms_post` does,
imports lazy inside the route) and passes it to `update_message_text`, which sets the three
author columns in the same `UPDATE` as the text. Validate `author_source` against `AUTHOR_SOURCES`
the way `post_message` does. An edit with no token stores `author_source="none"`, which is what
Studio's goal rename (`studio/src/renderer/src/services/messages.ts`) will produce until the UI
token exists. `comms_messages.py` is at 377 lines: if the change would take it past 400, move
`update_message_text` to a new `db/queries/comms_edit.py` and re-export it from `comms_messages.py`
and `db/queries/comms.py` so existing imports keep working.

`messages_crud.py` is at 395 lines since #63 (`b141dde`), which added the human-gate and
supersede refusals to it. The route may not grow past 400: move the stamping into a helper (for
example `_helpers.edit_stamp(request)`, `_helpers.py` is at 261) or move `comms_edit` into its own
blueprint file, so `comms_edit` itself gains at most one line.

Living docs: the `POST /comms/edit` line under "Comms board endpoints" in
`src/pathly_orchestrator/CLAUDE.md` says the edit re-stamps the row to the editor.

## Not in this ticket

- Refusing edits of binding directives: ticket 12.
- Refusing edits by non-authors: rejected in spec.md § Decisions (breaks Studio's goal rename).

## Done when

- `python -m pytest tests/comms_board/test_comms_edit_restamp.py -q -p no:cacheprovider` passes
  and covers: a row posted with a reviewer token and edited with no token ends with
  `author_source="none"` and no `author_role`; edited with a builder token it ends with
  `author_role="builder"`, `author_source="token"` and the builder's run id; the text changes in
  both; an unknown id still returns 404.
- `python scripts/check_file_size.py` exits 0.

```check
$ python -m pytest tests/comms_board/test_comms_edit_restamp.py -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_file_size.py
exit 0
```

## Reference

- spec.md § Decisions ("`/comms/edit` provenance")
- `src/pathly_orchestrator/runner/provenance.py::stamp`
- `src/pathly_orchestrator/http_server/blueprints/comms/messages_write.py::comms_post` (the
  stamping pattern)
- `tests/comms_board/test_rrp_acceptance.py` (posting with a minted token)

## Answer

**Built**

- `src/pathly_orchestrator/db/queries/comms_edit.py` (new): `update_message_text(conn, message_id, text, author_role=None, author_run_id=None, author_source=None)`. It validates `author_source` against `AUTHOR_SOURCES` (raises `ValueError` before any write, as `post_message` does), then sets `text` and the three author columns in one `UPDATE`. A `None` source is stored as `none`, as in `post_message`.
- `src/pathly_orchestrator/db/queries/comms_messages.py`: the old `update_message_text` is removed and re-exported from `comms_edit` at the bottom (next to `insert_message_row`), as a plain `from .comms_edit import update_message_text` with no suppression comment; 377 -> 363 lines. `db/queries/comms.py` is unchanged: it already imports the name from `comms_messages`, so `comms.update_message_text` and `comms_messages.update_message_text` both still resolve.
- `src/pathly_orchestrator/http_server/blueprints/comms/_helpers.py`: new `edit_stamp(request)` = `stamp(caller_identity(request))` (lazy imports inside the function, as `refuse_agent_on_human_gate` does); 261 -> 273 lines.
- `src/pathly_orchestrator/http_server/blueprints/comms/messages_crud.py`: `comms_edit` passes `**edit_stamp(request)` to `_update_text` (same line count: 395, one import name added to the existing `_helpers` import).
- `tests/comms_board/test_comms_edit_restamp.py` (new, committed first as `6109641`) plus the regenerated `tests/INDEX.md` and `tests/comms_board/INDEX.md`.
- `src/pathly_orchestrator/CLAUDE.md`: the `POST /comms/edit` line says the row is re-stamped to the editor; one line for `comms_edit.py` in the package map.

**Proof** (each run fresh after the last code edit)

- Test-first: at `6109641` the new file ran `5 failed, 2 passed` for the right reasons (`assert 'token' == 'none'`, `TypeError: unexpected keyword argument 'author_role'`); the 2 passes are the two 404 cases, which already held.
- `python -m pytest tests/comms_board/test_comms_edit_restamp.py -q -p no:cacheprovider` -> `7 passed`, exit 0. It covers: reviewer-token row edited with no token -> `author_source="none"`, `author_role` and `author_run_id` NULL, text changed; same row edited with a builder token -> `builder` / `token` / `run-builder`, text changed; a body naming `from`, `run_id` and `author_role` as the reviewer changes nothing (still `none`); a revoked token edits as `none`; an unknown id is 404 with and without a token; an unknown `author_source` raises `ValueError` and leaves the row as it was.
- `python scripts/check_file_size.py` -> `OK: 1010 source files checked; 19 known over 400 lines, none new, none grown.`, exit 0.
- commands.md Test (`tests/comms_board tests/db tests/runner_supervisor tests/http_api`, `-x`), re-run after the round 2 edit: `1208 passed, 2 skipped in 234.36s`, exit 0. Lint chain: exit 0 (black, mypy, file size, mirror reads, `gen_test_index --check`, lint-imports, bandit, adapters, entry points). Smoke exit 0. `python -m build --wheel` exit 0. An import check shows `comms.update_message_text`, `comms_messages.update_message_text` and `comms_edit.update_message_text` are the same object. Round 1 also ran `tests/fsm_flows/test_review_packet.py` + `tests/consistency`: 70 passed (they import `update_message_text`); the round 2 edit changes no code, only drops a comment.

**Decisions**

- `comms_messages.py` came to 401 lines after `black`, so I took the ticket's fallback and moved the function to `comms_edit.py` rather than trimming the docstring to fit.
- A caller that passes no stamp (the existing test callers of `update_message_text`) gets `none`, not "leave the old stamp": the function always re-stamps, so it cannot reopen the hole at function level. The only `src/` caller is the `/comms/edit` route, which always passes a stamp.
- The edit route does not refuse non-authors and does not change `from_agent`; both are outside the ticket.

**Shortcuts taken**: none.

**Review fixes** (round 1, floor guard: `suppress: .../comms_messages.py: from .comms_edit import update_message_text  # noqa: E402, F401`)

- Reproduced: `python3 scripts/floor-guard.py chief-agent 03 2ed26ae3145f00ac457a0bcd395362255c8a003e` printed that finding, exit 1.
- Cause: the re-export line I added at the bottom of `comms_messages.py` copied the `# noqa: E402, F401` comment from the `insert_message_row` line above it. The guard treats any added `noqa` as a suppression, whatever the line is.
- Fix: removed the `# noqa: E402, F401` from my line, one line changed, nothing else. No `Floor: allow` line was added. No check needs the comment: `commands.md`'s Lint chain has no flake8 or ruff step, and no flake8 or ruff config exists in `pyproject.toml` or the workflows. The line stays a working re-export (import check above), and black, mypy and lint-imports pass with it. The two `noqa` comments already in the file (the `comms_goal_fields` import and the `insert_message_row` re-export) are older than this ticket and untouched.
- The guard reads the committed diff (`base..HEAD`), so it can only be re-run after the commit; the commit sha and the re-run result are in the report that came back with this commit.

**For later tickets**

- Ticket 12 (refuse edits of binding directives) and 08 (the gate lists `/comms/edit` as an unlisted write for a chief token) are unaffected; ticket 12 adds its refusal to the `/comms/edit` route in `messages_crud.py`, which is at 395 lines, so it needs room first (move more into `_helpers`, or the route into its own file).
- A builder that edits a task's text now leaves the task stamped `builder`. `fsm/gates/_scope_tasks.py` skips tasks with `author_role == "builder"` when it builds the declared scope, so a planner's task that a builder edits stops widening the builder's scope. That matches the gate's intent; no change needed.
- The ticket named `studio/src/renderer/src/services/messages.ts` for Studio's goal rename; the `/comms/edit` caller is now `studio/src/renderer/src/store/commsApi/messages.ts`. Not touched. Studio sends no run token, so a goal rename now stamps `none` until the UI token exists.

## Review findings (round 1, floor guard)

floor guard: the diff weakens the bar instead of meeting it
suppress: src/pathly_orchestrator/db/queries/comms_messages.py: from .comms_edit import update_message_text  # noqa: E402, F401
if a finding is intended, the ticket needs a line like: Floor: allow <category>
