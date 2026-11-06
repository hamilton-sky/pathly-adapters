# Refuse a consult run's own `answer` post

Type: task
Status: open
Blocked by: 02
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/http_server/consult_guard.py (new), src/pathly_orchestrator/http_server/app.py, tests/http_api/test_consult_answer_guard.py (new), src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/http_api/INDEX.md

Split from ticket 02. A `type: answer` post frees parked tasks the moment it is written
(`post_message` → `release_on_answer`), before the router measures what the consult changed, so a
consult agent must not deliver around the check (spec Decisions, "Where the answer comes from").
Ticket 02's skill tells it not to; this ticket makes it so.

New `src/pathly_orchestrator/http_server/consult_guard.py` (new): a `before_request` registered in
`src/pathly_orchestrator/http_server/app.py` after `run_token_guard` (search `run_token_guard`),
that answers 403 `{"error": "a consult answers in its completion summary; Pathly posts the
answer"}` to `POST /comms/answer`, and to `POST /comms/post` whose JSON body has `"type": "answer"`,
when the caller is a live run token whose run id starts `consult-` (resolve it the way `run_token_guard` does; imports lazy
inside the function). Every other post of a consult run passes (status, discovery, question), and
an answer from any other caller is unchanged. A body that is not JSON passes to the route, which
already refuses it.

Document the guard in `src/pathly_orchestrator/CLAUDE.md` beside the consult run.

## Not in this ticket

- Measuring the tree and withholding the router's own answer: the read-only check (spec Decisions).
- The other board writes a consult may make (`/comms/edit`, `/comms/supersede`): unchanged; they do
  not post an answer or free a parked task.

## Done when

- `python -m pytest tests/http_api/test_consult_answer_guard.py -q -p no:cacheprovider` passes and
  covers: a `POST /comms/post` `type: answer` and a `POST /comms/answer` with a consult run's token
  are each 403, store no row and free no parked task; a `status` and a `question` post with the same token are 200; an
  `answer` from a builder run token and from a tokenless caller are 200; a revoked consult token
  is refused by `run_token_guard` as today.
- All existing tests under `tests/http_api` and `tests/comms_board` still pass.

```check
$ python -m pytest tests/http_api/test_consult_answer_guard.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/http_api tests/comms_board -q -p no:cacheprovider
exit 0
```

## Reference

- spec.md § Decisions ("Where the answer comes from", "Consult run identity")
- `src/pathly_orchestrator/http_server/run_token_guard.py`, `src/pathly_orchestrator/http_server/blueprints/comms/messages_crud.py` (`/comms/answer`)

## Answer
