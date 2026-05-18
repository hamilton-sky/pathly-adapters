# fsm-transition-actions — Plan Summary

## Phase 1 — FSM Changes
_Inside pathly-adapters. Low risk — additive changes, existing flows still work._

| Conv | Scope |
|------|-------|
| 1 | Add `transition_actions` key to all 3 flow YAMLs (`team`, `debug`, `explore`) |
| 2 | Update `orchestrator.md` — remove hardcoded side effects, add blind dict substitution executor |
| 3 | Update `state.py` validation — accept new `transition_actions` key |

**Verify:** `grep` confirms no hardcoded commit/archive logic remains in `orchestrator.md`

---

## Phase 2 — Discovery Wrapper
_Small build (~20 lines). Runs after Phase 1. Validates the full chain end-to-end._

One generic skill template that resolves:
```
/pathly-{name}  →  flows/{name}.flow.yaml
```
No more hardcoded `flow_config` paths in individual skills.

---

## Phase 3 — Wizard App
_New surface, built on top of Phase 1 + 2._

| Step | Scope |
|------|-------|
| 1 | Read package to populate dropdowns (skills, agents, action types) |
| 2 | Wizard UI — states → exit routing → side effects |
| 3 | Validation layer — errors hard-block, warnings soft-block |
| 4 | Export — writes YAML + skill template to package, triggers `materialize_flows()` |




Phase 1 — FSM changes (inside pathly-adapters):
  Conv 1: Add transition_actions key to all 3 flow YAMLs
  Conv 2: Update orchestrator.md — remove hardcoded side
          effects, add blind dict substitution executor
  Conv 3: Update state.py validation — accept new key

  Verify: grep confirms no hardcoded commits in orchestrator
  Risk: low — additive changes, existing flows still work

══════════════════════════════════════════════

Phase 2 — Discovery wrapper (small, after Phase 1):
  One skill template that resolves:
    /pathly-{name} → flows/{name}.flow.yaml
  ~20 lines. Validates Phase 1 actually works end-to-end.

══════════════════════════════════════════════

Phase 3 — Wizard app (new surface, on top of Phase 1+2):
  Step 1: Read package to populate dropdowns
          (skills, agents, action types)
  Step 2: Wizard UI — states → routing → side effects
  Step 3: Validation layer (errors vs warnings)
  Step 4: Export → writes YAML + skill template
          to package, triggers materialize_flows()