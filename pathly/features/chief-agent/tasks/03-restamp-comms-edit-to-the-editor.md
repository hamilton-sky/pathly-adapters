# Stamp an edited board row with the editor, not the original author

Type: task
Status: open
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
