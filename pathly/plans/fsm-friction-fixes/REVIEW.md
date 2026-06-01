RESULT: PASS

## Conv 3 — Multi-conversation routing (on_state_counter)

Reviewer: claude-sonnet-4-6

### Summary

All 7 acceptance criteria verified. One violation found and fixed:

**Violation (fixed):** `_count_planned_convs` used `re.search` which could overcount on PROGRESS.md files with multiple rows per conversation number. Fixed to use anchored `re.match` + unique-number set.

### Files reviewed

- `src/pathly_orchestrator/fsm_ops.py` — `_count_planned_convs`, `convs_total`/`convs_done` stamping ✓
- `src/pathly_orchestrator/fsm.py` — `on_state_counter` rule level, `convs_done` increment in `update_progress` ✓
- `src/pathly_data/core/flows/team.flow.yaml` — REVIEWING block with `on_state_counter`, `MORE_CONVS_NEEDED.md` fallback ✓
- `src/pathly_data/core/skills/team/review.md` — removed MORE_CONVS_NEEDED instruction ✓
- `tests/test_on_state_counter.py` — 4 new tests ✓

Full suite: 223 passed, 3 skipped.
