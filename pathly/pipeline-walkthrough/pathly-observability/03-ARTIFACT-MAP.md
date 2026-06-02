# 03 — Artifact Map: pathly-observability

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
| feedback/TEST_FAILURES.md | Tester | Builder | S-06: wrong grep path `development/plan.md`; S-07: wrong path + case error. Both fixed in USER_STORIES.md — no code changes. |

---

## Source files changed

| File | Stories | What changed |
|---|---|---|
| `src/pathly_orchestrator/http_server.py` | S-01, S-02 | Added `/record_phase` POST endpoint |
| `src/pathly_orchestrator/fsm.py` | S-03 | `_is_exempt()` reads `scope_gate.exempt_prefixes` from flow YAML; `recover_state()` `corrupted_state` flag; `route_feedback()` unrecognized-file fallback |
| `src/pathly_orchestrator/fsm_ops.py` | S-01–S-11 | `_stage_brief()` fully implemented; stale feedback warning; `_blocked_response()` uses stage_brief |
| `src/pathly_data/core/skills/utilities/log-phase.md` | S-06 | New skill: `log-phase` wraps `/record_phase` curl call |
| `src/pathly_data/core/skills/development/build.md` | S-04, S-10, S-11 | Phase-boundary logging (6 calls); fast/auto mode detection; auto-chain to review on pass |
| `src/pathly_data/core/skills/development/review.md` | S-05, S-11 | Phase-boundary logging (6 calls); exit contract marks PROGRESS.md DONE |
| `src/pathly_data/core/skills/development/test.md` | S-05 | Phase-boundary logging (6 calls) |
| `src/pathly_data/core/skills/planning/plan.md` | S-06 | Phase-boundary logging (6 calls) |
| `src/pathly_data/core/skills/planning/design.md` | S-07 | `## Phase: analyze` section added; log-phase calls |
| `src/pathly_data/core/skills/planning/storm.md` | S-07 | `## Phase: analyze` section added; log-phase calls |
| `src/pathly_data/core/agents/building/builder.md` | S-08, S-09 | Stage brief + rigor contract sections; scout min-2 → max-4 |
| `src/pathly_data/core/agents/building/designer.md` | S-08, S-09 | Stage brief (UI UX Pro Max engine line) + rigor contract |
| `src/pathly_data/core/agents/planning/architect.md` | S-08, S-09 | Stage brief + rigor contract |
| `src/pathly_data/core/agents/planning/planner.md` | S-08, S-09 | Stage brief + rigor contract |
| `src/pathly_data/core/agents/quality/reviewer.md` | S-08, S-09 | Stage brief + rigor contract |
| `src/pathly_data/core/agents/quality/tester.md` | S-08, S-09 | Stage brief + rigor contract |
| `src/pathly_data/core/flows/team.flow.yaml` | S-03 | `scope_gate.exempt_prefixes: []`; PLANNING/DESIGNING `on_content` gates |
| `src/pathly_data/core/flows/debug.flow.yaml` | — | `REPRO_QUESTIONS: human` feedback routing |
| `src/pathly_data/core/skills/flow/go.md` | — | Director routing explanation line |
| `tests/test_observability.py` | S-01, S-02, S-03 | 8 tests for `/record_phase` and `_is_exempt()` |
| `tests/test_fsm.py` | S-03 | Fixed L1/L2 test for `on_content` PLANNING gate |
| `tests/test_fsm_ops.py` | S-03 | Fixed `IMPLEMENTATION_PLAN.md` content for `on_content` check |
| `docs/PATHLY_IMPROVEMENT_RECOMMENDATIONS.md` | — | All 15 recommendations marked ✅ done |
| `pathly/plans/pathly-observability/USER_STORIES.md` | Planner + Builder | Acceptance criteria; S-06/S-07 grep paths corrected post-test |

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
pipeline-walkthrough/pathly-observability/  ←── metrics record → this folder
```
