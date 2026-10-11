# Prove the chief end to end and update the living docs

Type: task
Status: open
Blocked by: 06, 08, 09, 11, 12
Test first: no

Write `tests/comms_board/test_chief_acceptance.py`, the bar in map.md, with a fake spawn host
that plays the chief by issuing its fragment calls (no mocks of code this plan built):

1. `POST /chief/message "add rate limiting, standard rigor"` → one chief turn with a `chief`
   token; the fake chief calls decompose and run → the goal and its tasks are on the board.
2. A stage asks a question → it reaches the chief inbox → the chief asks in the thread → the human
   answers with a thread message → the fake chief relays it with `human_message_id` → the stage
   unblocks; the board shows question and answer.
3. The human says "use Postgres" → the chief posts a binding decision to `*` → after an
   acknowledgement, the next builder, reviewer and tester prompts all contain it; a builder-token
   `binding` post is `403`.
4. A finished builder run's episode is in the next builder prompt on the same feature and not in
   the reviewer's.

Then update the living docs in the same commit: root `CLAUDE.md` (the chief in "Primary goal" and
the blueprint map), `src/pathly_orchestrator/CLAUDE.md` (chief domain, inbox, binding directives,
episodic tier, scheduled promotion), `src/pathly_data/CLAUDE.md` (chief role and fragments), and a
`CHANGELOG.md` entry.

## Not in this ticket

- Turning `chief.enabled` on by default.

## Done when

- `python -m pytest tests/comms_board/test_chief_acceptance.py -q` passes.
- `python -m pytest tests/ -q -p no:cacheprovider` passes in full; both Studio typechecks exit 0;
  `python scripts/gen_test_index.py --check` exits 0.

```check
$ python -m pytest tests/comms_board/test_chief_acceptance.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/ -q -p no:cacheprovider
exit 0
prints passed
$ studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json
exit 0
$ studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.node.json
exit 0
$ python scripts/gen_test_index.py --check
exit 0
```

## Reference

- map.md "The bar"; SPEC.md; USER_STORIES.md
- Answers of tickets 01–12; root `CLAUDE.md` "Documentation sync"

## Answer
