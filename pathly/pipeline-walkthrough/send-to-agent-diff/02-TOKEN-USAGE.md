# Token Usage — send-to-agent-diff

**Date:** 2026-06-10
**Total agent spawns:** 8

---

## Per-agent breakdown

| Agent | Conv | Model | Tokens | Tool uses | Cost (USD) |
|---|---|---|---|---|---|
| planner | 0 | claude-sonnet-4-6 | 42,000 | 25 | not captured |
| builder | 1 | claude-sonnet-4-6 | 46,357 | 33 | $0.2503 |
| reviewer | 1 | claude-sonnet-4-6 | 264,755 | 95 | $1.4297 |
| builder | 2 | claude-opus-4-8 | 130,386 | 34 | $1.9000 |
| reviewer | 2 | claude-sonnet-4-6 | 125,316 | 46 | $0.4104 |
| builder | 3 | claude-sonnet-4-6 | 69,926 | 17 | $0.3776 |
| reviewer | 3 | claude-sonnet-4-6 | 81,081 | 29 | $0.4378 |
| tester | 0 | claude-sonnet-4-6 | 169,263 | 123 | $0.9140 |
| **TOTAL** | | | **929,084** | **402** | **~$5.72** |

> Planner cost not captured (cost_usd=0.0 in event). Total excludes planner cost.

---

## Heaviest stages

1. **reviewer conv 1** — 264,755 tokens · $1.43 · 3 fix iterations (subscription leak, path normalization, resolvedTabId)
2. **builder conv 2** — 130,386 tokens · $1.90 · 11-file component build (claude-opus-4-8)
3. **tester** — 169,263 tokens · $0.91 · scout + test + 1 fix cycle (5 criteria)

---

## Notes

- Conv 2 builder ran on `claude-opus-4-8` (higher cost per token) — drove 33% of total cost for a single conversation.
- Reviewer conv 1 required 3 full review + fix cycles — the most expensive review stage.
- Test stage included a builder fix subagent; tokens are summed across all tester subagents.
