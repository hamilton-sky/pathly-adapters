# Adapter Integration Contract — Retrospective

## Cost Summary
Total: $1.12

| Agent    | Model              | Tokens in | Tokens out | Cost    | % of total |
|----------|--------------------|-----------|------------|---------|------------|
| builder  | claude-sonnet-4-6  | 94,958    | 23,739     | $0.641  | 57%        |
| tester   | claude-sonnet-4-6  | 36,934    | 9,234      | $0.249  | 22%        |
| reviewer | claude-sonnet-4-6  | 33,965    | 8,491      | $0.229  | 20%        |

> Use this to decide: was lite rigor worth the cost? Build drove most of the spend (3 fix cycles in conv 1 plus 2 conversations).

## Plan Quality
**Conversation sizing:** Good — both conversations finished cleanly with no mid-conversation scope cuts needed.
**Surprises:** None.
**Missing from plan:** Nothing identified.

## What Worked
- Plan accurately scoped the two conversations: FSM contract normalization (Conv 1) and Codex surface alignment (Conv 2).
- Reviewer correctly caught the missing `storage_path` field in escalate envelopes, triggering a fix cycle rather than shipping a broken contract.
- Tester correctly identified coverage gaps (escalate path + escalate-not-continuable) that required a second fix cycle in Conv 1.
- Conv 2 completed cleanly with no reviewer or tester failures.

## What to Improve Next Time
- The scope gate triggered repeatedly due to stale `conv_start_sha` in STATE.json — a known FSM limitation when commits happen outside the pipeline. Consider documenting this explicitly in plan prerequisites.

## Seed for Next Storm
> The adapter contract normalization landed cleanly: `agent_hint` (neutral keys) and `codex_subagent` (frozen legacy compat) coexist in every envelope. The `decision` enum (`continue`/`block`/`escalate`) is documented in both the FSM layer and the Codex adapter surface. Any adapter that reads `agent_hint.role` and respects `escalate` as a human gate is fully compliant with the contract.
