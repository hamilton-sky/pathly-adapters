# Add binding decisions that every targeted worker prompt carries until superseded

Type: task
Status: open
Blocked by: 03
Test first: yes

Today a decision is injected unconditionally only while `status='pending'`
(`db/queries/comms_messages.py::get_pending_decisions`), and the first `/comms/acknowledge` sets
the whole row `active`, which drops it for every role (SPEC.md § C6). Add standing directives:

- `db/migrations_chief.py`: add `binding INTEGER NOT NULL DEFAULT 0` to `comms_messages`
  (`to_agent` already exists).
- `db/queries/comms_directives.py::get_binding_decisions(conn, boards, scopes, role)`: rows with
  `type='decision' AND binding=1`, not deleted, not superseded, any `status`, and
  `to_agent IN (role, '*')`.
- `runner/comms_context.py`: the governance block also takes `get_binding_decisions` for the
  reader's role, de-duplicated by id with the pending decisions. Call site only: the file is 394
  lines; put rendering helpers in a new module if needed.
- Write gate: `/comms/post` with `binding=1` is accepted only from a `chief` run token (or the UI
  token once RRP-2b exists); any other caller → `403`. Put the check in a new helper next to
  `blueprints/comms/_helpers.py`, called from `messages_write.py`.
- Add `chief` to `_PROJECT_WRITERS` in `blueprints/comms/_helpers.py` and to
  `_DEFAULT_WRITE_PERMISSIONS` in `db/queries/app_settings.py` (kept in sync, per the comment
  there). Not to `_GLOBAL_WRITERS`.

## Not in this ticket

- Re-queuing a stage that ran across a newer directive: the stale-directive ticket.

## Done when

- `python -m pytest tests/comms_board/test_binding_directives.py -q` passes and covers: a chief
  binding decision to `*` is in the next builder, reviewer and tester contexts; still there after
  `/comms/acknowledge`; `to_agent='reviewer'` reaches the reviewer and not the builder; a
  superseded directive reaches none; a builder-token post with `binding=1` is `403`; the chief can
  write the project board and cannot write global.

```check
$ python -m pytest tests/comms_board/test_binding_directives.py -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_file_size.py
exit 0
```

## Reference

- SPEC.md § C6; `runner/comms_context.py` (governance block), `db/queries/comms_messages.py`
  (`get_pending_decisions`, `acknowledge_message`, supersede)
- `blueprints/comms/_helpers.py` (`_PROJECT_WRITERS`, `_GLOBAL_WRITERS`), `db/queries/app_settings.py`

## Answer
