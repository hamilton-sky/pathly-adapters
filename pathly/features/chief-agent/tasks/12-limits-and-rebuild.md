# Cap chief turns, show provider refusals in the thread, and rebuild a lost session from the board

Type: task
Status: open
Blocked by: 05
Test first: yes

SPEC.md § C5 and story US-7, in `supervisor/chief_turn.py` (or a new `chief_limits.py` it calls):

- `chief.max_turns_per_hour` (app setting, default 20): over the cap, no spawn; append one
  `role=system` thread row "paused until HH:MM (turn cap)" per pause, and leave the inbox rows for
  the next allowed turn.
- A turn the provider refused → one `role=system` row "paused until …" with the provider's
  reason; no silent drop. The refusal classifier exists only in Studio
  (`studio/src/main/ipc/engineFailure.ts`), and pty-host spawns never pass through it, so add a
  small Python mirror of its markers in `chief_limits.py`. Keep its rule: a refusal needs a
  non-zero exit or an engine abort marker, so a reply that merely mentions rate limits is not
  one.
- `--resume` fails or `chief_session` is missing → clear the session, start a fresh one, and add a
  "Current state" block to the prompt built only from the board (goal rollups via
  `GET /comms/goals` logic, open interactions, binding directives) and the episodic tier. No state
  is read from the old transcript.

## Not in this ticket

- Changing the global spawn caps or the provider retry policy.

## Done when

- `python -m pytest tests/runner_supervisor/test_chief_limits.py -q` passes and covers: the 21st
  turn in an hour does not spawn and writes one pause row; a refused turn writes a pause row with
  the reason; a failed resume starts a fresh session whose prompt contains the current goal
  status from the board.

```check
$ python -m pytest tests/runner_supervisor/test_chief_limits.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- SPEC.md § C5; `supervisor/chief_turn.py`; `studio/src/main/ipc/engineFailure.ts` (markers to
  mirror) and root `CLAUDE.md` "Studio CLI spawn scheduler"
- Tickets 04 and 05 Answers

## Answer
