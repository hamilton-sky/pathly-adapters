# Run consolidate and promote automatically at RETRO/DONE, with a provenance gate on global

Type: task
Status: open
Blocked by: 10
Test first: yes

SPEC.md § C3 (semantic tier) and role-read-policy SPEC § C8 "Provenance before promotion".

- `supervisor/memory_schedule.py::on_feature_milestone(project_root, feature, state)`: when a
  team flow reaches `RETRO` or `DONE`, run the deterministic part of `/comms/consolidate`
  (`dedupe_board`) on the feature board, then promote `decision`/`constraint` rows to the project
  board through `db/queries/comms_promote.py::promote_message`. Call it from where the FSM records
  the transition (one line). The LLM synthesis part of consolidate is not run automatically.
- Promotion gate (in `comms_promote.py` or a new helper it calls): to `project`, only rows with
  `author_source IN ('token','system')`; to `global`, the same plus an approval record from the
  `evaluator` or the human. Rows that fail the gate are left as pending promotions on the board
  for the human, not dropped.
- Never auto-promote to `global`.

## Not in this ticket

- A UI for approving pending promotions.

## Done when

- `python -m pytest tests/comms_board/test_memory_schedule.py -q` passes and covers: reaching
  DONE promotes a token-stamped builder decision to the project board; a `legacy` or `none` row is
  not promoted and is left pending; nothing reaches `global` automatically; a promotion to global
  without an approval record is refused; running the milestone twice promotes nothing twice.
- `python -m pytest tests/comms_board/test_comms_promote.py tests/comms_board/test_comms_consolidate.py -q`
  still passes.

```check
$ python -m pytest tests/comms_board/test_memory_schedule.py tests/comms_board/test_comms_promote.py tests/comms_board/test_comms_consolidate.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- `db/queries/comms_promote.py`, `blueprints/comms/promote.py`, `blueprints/comms/settings.py`
  (`/comms/consolidate`), `db/queries/comms_embeddings.py::dedupe_board`
- Ticket 10's Answer

## Answer
