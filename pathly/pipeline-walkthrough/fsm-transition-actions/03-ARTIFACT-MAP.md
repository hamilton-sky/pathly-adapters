# 03 — Artifact Map: fsm-transition-actions

Every file produced or consumed during this pipeline run.

---

## Plan files (FSM persistent state)

These files are the pipeline's memory. An interrupted run can be resumed by reading
PROGRESS.md and re-entering at the last incomplete conversation.

| File | Written by | Read by | Purpose |
|---|---|---|---|
| USER_STORIES.md | Planner | Tester | Acceptance criteria — the contract |
| IMPLEMENTATION_PLAN.md | Planner | Planner | Exact code changes — the design |
| CONVERSATION_PROMPTS.md | Planner | Builder agents | Verbatim prompts — the instructions |
| PROGRESS.md | Orchestrator | Orchestrator | Conversation status — the checkpoint |
| RETRO.md | Retro agent | Humans, /lessons | What we learned — the feedback loop |

---

## Transient feedback files (deleted after resolution)

These files no longer exist. They were the inter-agent communication medium.

| File | Written by | Resolved by | Content summary |
|---|---|---|---|
| REVIEW_FAILURES.md (×2) | Reviewer | Builder | Orchestrator generalization violations in Conv 2 — fixed across 2 fix cycles |

---

## Source files changed

| File | Stories | What changed |
|---|---|---|
| `src/pathly_orchestrator/state.py` | S3.1 | Added `_KNOWN_OPTIONAL_FLOW_KEYS`, `_ACTION_VOCAB`, `get_transition_actions()`, extended `validate_flow_cli()` with transition_actions validation |
| `tests/test_transition_actions.py` | S1.1, S1.2, S2.1, S3.1 | New — 9 pytest tests covering `get_transition_actions()` and `validate_flow_cli()` |

_Note: Conv 1 (flow YAMLs) and Conv 2 (orchestrator.md) changes were committed in a prior session and are not reflected in the current branch diff._

---

## Artifact flow diagram

```
USER_STORIES.md          ←── what to build
       │
       ▼
IMPLEMENTATION_PLAN.md   ←── how to build it
       │
       ▼
CONVERSATION_PROMPTS.md  ←── exact builder prompts
       │
       ▼
PROGRESS.md              ←── which conversations done
       │
       ▼
RETRO.md                 ←── what we learned
       │
       ▼
lessons/LESSONS.md       ←── promoted patterns → next planner
pipeline-walkthrough/fsm-transition-actions/  ←── metrics record → this folder
```
