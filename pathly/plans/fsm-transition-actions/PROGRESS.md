# PROGRESS.md — fsm-transition-actions

| Conv | Scope | Stories | Status |
|------|-------|---------|--------|
| 1 | Extend flow YAMLs with transition_actions | S1.1, S1.2 | NOT STARTED |
| 2 | Generalize orchestrator.md; remove hardcoded side effects | S2.1 | NOT STARTED |
| 3 | Update state.py / validate_flow (BLOCKED on fsm-configurable Phase 5c) | S3.1 | BLOCKED |

## Status key

| Symbol | Meaning |
|--------|---------|
| NOT STARTED | Work has not begun |
| IN PROGRESS | Conversation is active |
| DONE | All acceptance criteria verified |
| BLOCKED | Cannot begin — upstream dependency not met |

## Blocker detail

**Conv 3** — blocked on `fsm-configurable` Phase 5c landing. `_REQUIRED_FLOW_KEYS` and `validate_flow_cli` must exist in `src/pathly_orchestrator/state.py` before this conversation begins. Check `fsm-configurable` PROGRESS.md before starting.
