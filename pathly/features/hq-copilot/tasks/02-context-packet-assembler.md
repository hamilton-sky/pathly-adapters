# Build the context packet assembler

Type: task
Status: resolved
Blocked by: 01
Test first: yes

New module `src/pathly_orchestrator/hq_context.py` implementing ticket
01's settled schema:

- `assemble_packet(board_id, budget_tokens) -> ContextPacket`, where
  `ContextPacket` is a small dataclass: `text: str`,
  `tokens_est: int`, `sections: list[SectionStatus]`
  (`name`, `included: bool`, `cut_reason: str | None`), `budget: int`.
- Reads only through existing server read paths (the board hydration and
  run-history queries named in the Reference); no new tables, no writes.
- Renders sections in 01's priority order, truncating whole lowest-
  priority sections first until `tokens_est <= budget`; every cut is
  recorded in `sections`.
- Empty board → valid empty packet (`text == ""`, all sections
  `included=False`), never an exception.
- Any unexpected failure inside assembly raises a single
  `HQContextUnavailable` exception (the caller in 03 turns it into the
  visible "board context unavailable" note; the packet layer never
  returns a half-built packet silently).
- Own timeout: assembly must return or raise within 5 seconds (guard
  against huge boards; use a monotonic deadline check around the section
  loop).

## Not in this ticket

- Prompt wiring into `chat_agent.py`: ticket 03 consumes this module.
- The HTTP endpoint: ticket 03 exposes `GET /hq/context` from the same
  assembler.

## Done when

- `python -m pytest tests/hq_copilot/test_assembler.py -q -p no:cacheprovider` passes and covers: priority order respected under a tight budget (low-priority sections cut first, cut recorded); empty board yields a valid empty packet; a forced failure inside a section reader surfaces `HQContextUnavailable`, never a partial packet; assembly of a 10k-message fixture board finishes within the timeout.
- `python scripts/check_file_size.py` exits 0.

```check
$ python -m pytest tests/hq_copilot/test_assembler.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Design, § Interfaces; ticket 01's Answer (the settled schema)
- `src/pathly_orchestrator/board_mirror_hydrate.py`,
  `src/pathly_orchestrator/db/queries/run_history_read.py`,
  `src/pathly_orchestrator/db/queries/comms_hydrate.py` (read-only)

## Answer

Implemented 2026-10-14 in `src/pathly_orchestrator/hq_context.py` (new,
~230 lines) with tests in `tests/hq_copilot/test_assembler.py` (7
tests, all passing).

Read paths used (all pre-existing, read-only): pending questions via a
direct `comms_messages` query (`type='question'`,
`COALESCE(status,'pending') != 'answered'`); live runs via
`run_history_read.list_runs` + `get_run_detail` for the current stage
name; goals via `comms_goals_read.get_goals_with_rollup`; recent events
via a LIMIT-bounded `comms_messages` query excluding structural types;
artifact titles via `comms_artifacts` joined to `comms_messages`.

Two deliberate deviations from the ticket text, both documented in the
module: (1) signature is `assemble_packet(board_id, budget_tokens=6000,
project_root=None)` — the optional `project_root` scopes the live-runs
section (the run read-model keys on it); when omitted the runs section
is recorded cut as "no project_root" rather than silently empty.
(2) Strict priority truncation: once a section misses the budget, it
and every lower-priority section are cut — no low-priority section can
displace a higher one.

Verification: `tests/hq_copilot/test_assembler.py` 7 passed (incl. the
10k-message timeout test and the forced-failure test); the ticket's
full Test command (`tests/comms_board tests/db tests/http_api
tests/hq_copilot`) run — result recorded below; `check_file_size.py`
exits 0.

Full suite result: 895 passed, 2 skipped in 190s —
`tests/comms_board tests/db tests/http_api tests/hq_copilot`, run
2026-10-14 against a clean clone at the Mac's commit era (the Mac has
no shell runner; verified via git-clone + venv on the assistant's
machine).
