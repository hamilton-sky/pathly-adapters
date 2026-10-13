# Send the raw run token only on /events/spawn

Type: task
Status: open
Blocked by: —
Test first: yes

`sse._broadcast_runner` serialises the whole payload once and puts the same string on three
channels: the topic's `/events/runner` clients (`_runner_clients`), every `/events/spawn` client
(`_broadcast_spawn`, for `_SPAWN_EVENT_TYPES`) and the run's `/events/runs` clients
(`_broadcast_run_event`). A `TERMINAL_SPAWN` payload carries the spawn's raw `run_token`, and none
of the `/events/` streams needs credentials, so any client watching a topic or a run can read a
live token. Only the spawn hosts read `run_token`, and both read it from `/events/spawn`
(`pty_host/host.py`, Studio's `TerminalSpawnListener`).

Change `_broadcast_runner` so the copies sent to `/events/runner` and `/events/runs` never contain
a `run_token` key, while the `/events/spawn` copy keeps it unchanged. Do not mutate the caller's
dict (callers reuse it). `_broadcast_comms` never carries the key; leave it alone.

Living docs in the same change: in `src/pathly_orchestrator/CLAUDE.md`, the `TERMINAL_SPAWN` row
under "SSE events" and the spawn-chokepoint diagram (`TERMINAL_SPAWN {..., run_token, ...} on
/events/spawn`) say where the token goes; and the CHANGELOG "Unreleased" role-read-policy bullet
that says the token reaches all three channels.

## Not in this ticket

- Taking the token off `/events/spawn` too: needs the UI token (RRP-2b), a later plan.
- Any change to the spawn hosts: they already read `/events/spawn` only.

## Done when

- `python -m pytest tests/http_api/test_sse_run_token_strip.py -q -p no:cacheprovider` passes and
  covers: a `TERMINAL_SPAWN` with a marker token reaches a queue registered in `_runner_clients`
  for its topic and one in `_run_clients` for its run without `run_token`, and a queue in
  `_spawn_clients` with it; the caller's payload dict still has `run_token` afterwards; an event
  without the key is delivered unchanged on all three.
- `python -m pytest tests/comms_board/test_rrp_acceptance.py tests/http_api/test_run_streams.py -q -p no:cacheprovider` still passes.

```check
$ python -m pytest tests/http_api/test_sse_run_token_strip.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/comms_board/test_rrp_acceptance.py tests/http_api/test_run_streams.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Decisions ("SSE token hole")
- `src/pathly_orchestrator/http_server/sse.py` (`_broadcast_runner`, `_broadcast_spawn`,
  `_broadcast_run_event`, the client registries)
- `pathly/features/role-read-policy/map.md`, the ticket-10 open item about the three channels
  (read-only)

## Answer
