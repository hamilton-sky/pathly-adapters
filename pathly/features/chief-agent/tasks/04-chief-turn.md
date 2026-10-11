# Run one chief turn: compose, spawn with --resume under its own lock, record the session

Type: task
Status: open
Blocked by: 01, 03
Test first: yes

Add `src/pathly_orchestrator/supervisor/chief_turn.py` with `run_chief_turn(project_root,
spawn_fn=None) -> dict` (SPEC.md § C1):

1. Take the per-project chief lock `("chief", project_root)` through `supervisor/board_lock.py`;
   if held, return `{ok: False, error: "chief_busy"}` (the pending inbox rows wait for the next
   turn). Never take the project board's own lock.
2. `take_batch` from the inbox; nothing pending → release and return `{ok: True, idle: True}`.
3. Compose the prompt: the chief contract and fragments (ticket 01) through the existing
   composition path, the board context for the project board via `retrieve_board_context` with
   role `chief` (so the chief wall applies once wired), and the inbox batch rendered as
   "New since your last turn".
4. Spawn through the same spawn path board runs use (`board_run`'s spawn function, injectable as
   `spawn_fn`), with role `chief` so the run token from role-read-policy carries it, and with
   `--resume <session_id>` when `chief_session` has one. Record the CLI `session_id` from the
   terminal result into `chief_session`.
5. Release the lock when the spawn ends, success or not.

Run category gains `chief`: widen the closed set everywhere it is listed (learnings.md) in this
same ticket, including the projection guard in `invocation_projection.py` (edit the tuple in
place; that file may not grow) and the Studio TS unions. `POST /chief/message` (ticket 03) now
calls `run_chief_turn` in a background thread after enqueueing.

## Not in this ticket

- Events other than human messages: ticket 05. Turn caps and session rebuild: ticket 12.

## Done when

- `python -m pytest tests/runner_supervisor/test_chief_turn.py -q` passes with a fake `spawn_fn`
  and covers: one human message → one spawn whose prompt contains the message and the chief
  tools; the spawn's token resolves to role `chief`; a second turn passes `--resume` with the
  session id from the first result; a turn while another holds the chief lock returns
  `chief_busy` and leaves the batch for the next turn (no row lost); the project board lock is
  free during a chief turn; an `AGENT_DONE` with `category: "chief"` projects with that category.
- `invocation_projection.py` is not longer than before.

```check
$ python -m pytest tests/runner_supervisor/test_chief_turn.py -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_file_size.py
exit 0
```

## Reference

- SPEC.md § C1; `supervisor/board_run.py::start_board_run`, `supervisor/board_lock.py`,
  `supervisor/orchestrator_session.py` (how `--resume` is passed)
- learnings.md (closed category set, file-size traps)
- Tickets 01 and 03 Answers

## Answer
