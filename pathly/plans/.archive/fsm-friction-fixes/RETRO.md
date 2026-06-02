# fsm-friction-fixes — Retrospective

## Cost Summary
Total: $1.48

| Agent       | Model              | Tokens in | Tokens out | Cost    | % of total |
|-------------|--------------------|-----------|------------|---------|------------|
| discoverer  | claude-sonnet-4-6  | 62,510    | 15,627     | $0.42   | 28.6%      |
| reviewer×3  | claude-sonnet-4-6  | 102,412   | 25,603     | $0.69   | 46.9%      |
| tester      | claude-sonnet-4-6  | 53,656    | 13,414     | $0.36   | 24.5%      |
| builder×3   | claude-sonnet-4-6  | —         | —          | n/c     | —          |

> Builder token costs were not captured for Conv 1–3 (sessions ran without usage-block logging).
> Was standard rigor worth the cost? Yes — reviewer caught two meaningful bugs (missing GATE_DEGRADED test, regex overcounting in _count_planned_convs).

## Plan Quality
**Conversation sizing:** Good — all 3 conversations completed in scope. Conv 2 and Conv 3 each had one reviewer violation caught and fixed in the same session, which is expected cycle behaviour.

**Surprises:** Two things: (1) Removing the `src/pathly_orchestrator/` self-exemption in Conv 2 meant Conv 3 had to explicitly declare its own source files in scope — the plan anticipated this with a note, which worked well. (2) `on_state_counter` routing to TESTING requires a `update_progress: mark: conv_done` action wired into `BUILDING->REVIEWING` in `team.flow.yaml`. The mechanism was built but not wired up, requiring manual STATE.json manipulation to advance the pipeline to TESTING.

**Missing from plan:** The Conv 3 task list should have included: "Add `update_progress: mark: conv_done` to the `BUILDING->REVIEWING` transition actions in `team.flow.yaml` — without it, `on_state_counter` never increments `convs_done` and the last conversation cannot advance to TESTING."

## What Worked
- Conversation scope notes (explicitly listing files to touch and files NOT to touch) prevented scope gate violations
- Reviewer catching the `_count_planned_convs` regex overcounting before it shipped
- GATE_DEGRADED permissive mode for truncated baselines — graceful rather than hard-blocking

## What to Improve Next Time
- When implementing a new FSM counter mechanism, also wire it into the flow YAML in the same conversation — don't split mechanism from wiring across convs
- Builder token costs should be logged at session close; add `pathly-log-agent-done` calls at the start of each building session
- The `on_state_counter` mechanism still needs the `BUILDING->REVIEWING: update_progress: mark: conv_done` action to be added to `team.flow.yaml` to be production-ready — schedule as a follow-up nano task

## Seed for Next Storm
> The fsm-friction-fixes feature delivered server auto-start, scope gate preexisting-dirty tracking, and the `on_state_counter` rule evaluator. The counter mechanism is built but not fully wired — `team.flow.yaml` needs a `BUILDING->REVIEWING: update_progress: mark: conv_done` action before it can replace `MORE_CONVS_NEEDED.md` in production. Removing `MORE_CONVS_NEEDED.md` from `review.md` was correct; the backwards-compat fallback in the YAML covers the transition window.
