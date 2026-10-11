# Add the chief blueprint domain: post a human message and read the thread

Type: task
Status: open
Blocked by: 02
Test first: yes

Create a new HTTP domain `src/pathly_orchestrator/http_server/blueprints/chief/` (`__init__.py`
with `all_blueprints`, `messages.py`) and register it in `http_server/app.py` like `comms` and
`control`:

- `POST /chief/message {project_root, text}` → append `role=human` to `chief_thread`, enqueue an
  inbox row `kind="human_message"`, broadcast SSE `CHIEF_MESSAGE`, return `{ok, id}`. Empty text
  or a missing project root is `400`. A call carrying a run token is `403`: only the human (no
  token, or the UI token once RRP-2b exists) writes human turns.
- `GET /chief/thread?project_root=&limit=&before=` → the thread, newest last.
- `POST /chief/reply {text}` → only with a run token whose role is `chief`; appends
  `role=chief` for the token's project, broadcasts `CHIEF_REPLY`. Any other caller is `403`.

All `db`/`runner` imports lazy inside the route functions. Add `chief/` to the blueprint domain
map in root `CLAUDE.md` and `src/pathly_orchestrator/CLAUDE.md`.

## Not in this ticket

- Starting a chief turn when a message arrives: ticket 04 (this ticket only enqueues).

## Done when

- `python -m pytest tests/http_api/test_chief_routes.py -q` passes and covers: a message is
  stored, enqueued and broadcast; empty text is `400`; a message posted with a builder token is
  `403`; `/chief/reply` with a chief token appends `role=chief` and broadcasts; with a builder
  token or none it is `403`; the thread reads back in order.

```check
$ python -m pytest tests/http_api/test_chief_routes.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- Root `CLAUDE.md` "Blueprint domain map"; `http_server/app.py`
- `http_server/run_identity.py::caller_identity` (from role-read-policy)
- Ticket 02's Answer

## Answer
