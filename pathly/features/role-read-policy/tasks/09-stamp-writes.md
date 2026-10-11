# Stamp author_role, author_run_id and author_source on every board write from the caller, not the body

Type: task
Status: open
Blocked by: 06, 08
Test first: yes

Add `src/pathly_orchestrator/runner/provenance.py` with `stamp(identity) -> dict` returning the
three provenance values (SPEC.md § C1):

- run identity → `author_role=identity.role`, `author_run_id=identity.run_id`,
  `author_source="token"`, whatever the body's `from` and `run_id` say;
- server-internal writer → `author_role="system"`, `author_source="system"` (a separate
  `system_stamp()`; never chosen from a body field);
- anonymous → `author_role=None`, `author_run_id=None`, `author_source="none"`.

Wire it in:

- `db/queries/comms_messages.py::post_message` accepts the three values (keyword arguments,
  default `None`) and inserts them.
- `http_server/blueprints/comms/messages_write.py` (`/comms/post`) computes
  `stamp(caller_identity(request))` and passes it. The file is 386 lines: keep the change to the
  call, with any logic in `provenance.py`. The `from_agent` and body `run_id` columns keep being
  written as today; only provenance ignores them.
- Server-internal writers pass `system_stamp()`: the `from_agent="system"` post inside
  `messages_write.py`, `supervisor/goal_verify.py`, `supervisor/task_retry.py`, and any other
  direct `post_message` caller in `supervisor/` or `runner/` (find them with
  `grep -rn "post_message(" src/pathly_orchestrator`; list them in the Answer).

An unknown or revoked token is stored as `author_source="none"` and logged, not refused (map.md,
Open questions).

## Not in this ticket

- The UI token (Studio posts stay `none` until RRP-2b).
- Refusing `binding` decisions by role: chief-agent CHF-4.

## Done when

- `python -m pytest tests/comms_board/test_comms_provenance.py -q` passes and covers: a post with
  a builder token and `from: "explorer"` is stored `author_role=builder`, `author_source=token`,
  `author_run_id=<builder run>`; a body `run_id` naming another run changes none of the three; a
  post with no token is `author_source=none`; a post with a revoked token is `none`; a
  `goal_verify` post is `system`/`system`.
- Every `post_message(` call under `src/pathly_orchestrator/supervisor` and `runner` passes a
  stamp (the test greps for it).

```check
$ python -m pytest tests/comms_board/test_comms_provenance.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/comms_board -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- SPEC.md § C1 "The author role is not from_agent"
- `src/pathly_orchestrator/http_server/blueprints/comms/messages_write.py`,
  `db/queries/comms_messages.py` (`post_message`)
- Tickets 06 and 08 Answers

## Answer
