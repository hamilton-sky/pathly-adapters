# Send the raw run token only on /events/spawn

Type: task
Status: resolved
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

**Built**

- `src/pathly_orchestrator/http_server/sse.py`: `_broadcast_runner` builds `public`, a copy of the
  payload without the `run_token` key (the payload itself when it has none), and uses it for the
  `/events/runner` copy and the `/events/runs` tee. The `/events/spawn` tee still gets the original
  `payload`. The caller's dict is never mutated. `_broadcast_comms` is unchanged.
- `tests/http_api/test_sse_run_token_strip.py` (new, 6 tests) and the regenerated
  `tests/INDEX.md` and `tests/http_api/INDEX.md`.
- Living docs: `src/pathly_orchestrator/CLAUDE.md` (the `TERMINAL_SPAWN` row under "SSE events" and
  the spawn-chokepoint diagram) and the `CHANGELOG.md` "Unreleased" role-read-policy bullet.
- The failing test was committed alone first (`19c7c29`, `test(chief-agent): 01 failing test`):
  3 of its 6 tests failed there, on `run_token` still present in the `/events/runner` and
  `/events/runs` copies. The other 3 (caller's dict kept, no-key event unchanged on all three,
  non-spawn event unchanged) passed at that commit, since they guard behaviour the change must keep.

**Proof**

- `python -m pytest tests/http_api/test_sse_run_token_strip.py -q -p no:cacheprovider`: `6 passed`,
  exit 0. It covers a `TERMINAL_SPAWN` with marker token `marker-token-7f3a9c1e5b` reaching a queue
  in `_runner_clients[topic]` and one in `_run_clients[run_id]` with no `run_token` key and no
  marker substring, and a queue in `_spawn_clients` with it; the caller's payload dict still equal
  to the original afterwards; a `TERMINAL_KILL` (no key) delivered equal on all three; a
  `run_token: None` stripped from the two and kept on `/events/spawn`.
- `python -m pytest tests/comms_board/test_rrp_acceptance.py tests/http_api/test_run_streams.py -q -p no:cacheprovider`:
  `14 passed`, exit 0.
- Commands from `commands.md`, run after the last code edit: Lint chain exit 0 (black, mypy,
  file size, mirror reads, `gen_test_index.py --check`, lint-imports, bandit, adapters, entry
  points); Smoke exit 0; Build (`python -m build --wheel`) exit 0; Test (comms_board, db,
  runner_supervisor, http_api) `1194 passed, 2 skipped`, exit 0.

**Decisions**

- Strip by building a new dict for the two non-spawn channels rather than popping from the
  caller's dict: the ticket says callers reuse it. The copy is made only when the key is present,
  so every other event goes out exactly as before.
- Strip the key even when its value is `None` (a failed best-effort mint): the key's presence is
  what the ticket forbids, and it keeps the three payload shapes predictable for a client.
- Checked the only consumers of `run_token` in `studio/src` and `src/`: `TerminalSpawnListener.tsx`
  (`/events/spawn`) and `pty_host/host.py` (`/events/spawn`). Neither reads it from the other two
  streams.

**Shortcuts taken**

none

**For later tickets**

- `/events/spawn` still carries the raw token and needs no credentials, so a client that
  subscribes there before a spawn starts can still read it. Closing that needs the UI token
  (RRP-2b). The docs I changed say so. Ticket 13 (acceptance) and any ticket that relies on a
  chief token staying secret should not assume more than this.
- A test that reads a `TERMINAL_SPAWN` from `/events/runner` or `/events/runs` to get the token
  no longer can; read it from a `_spawn_clients` queue or a fake broadcaster passed to
  `_run_stage_via_terminal`, as `test_rrp_acceptance.py` does.
