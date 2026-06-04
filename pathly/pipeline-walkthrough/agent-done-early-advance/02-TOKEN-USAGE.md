# 02-TOKEN-USAGE.md — agent-done-early-advance

**Date:** 2026-06-04  
**Total agent spawns:** 11 (planner + 5 builders + 5 reviewers + 1 tester)

*Cost columns not captured — all cost_usd == 0.0 (runs did not emit billing data).*

---

## Per-Agent Breakdown

| Agent | Conv | Result | Tokens | Tool Uses | Wall (s) |
|---|---|---|---|---|---|
| planner | 0 | DONE | not captured | not captured | not captured |
| builder | 1 | DONE | 47,778 | 47 | 418 |
| reviewer | 1 | PASS | 51,581 | 8 | 49 |
| builder | 2 | DONE | 164,080 | 33 | 820 |
| reviewer | 2 | PASS | 34,982 | 12 | 99 |
| builder | 3 | DONE | not captured | — | not captured |
| reviewer | 3 | PASS | 53,204 | 19 | 309 |
| builder | 4 | DONE | not captured | — | 235 |
| reviewer | 4 | PASS | 34,220 | 13 | 117 |
| builder | 5 | DONE | not captured | — | 165 |
| reviewer | 5 | PASS | 22,503 | 8 | 108 |
| tester | 0 | PASS | 40,018 | 33 | 790 |

---

## Totals (captured only)

| Metric | Value |
|---|---|
| Total tokens (captured) | 448,366 |
| Total tool uses (captured) | 173 |
| Total wall time | ~3,110s (~52 min) |
| Total cost | not captured |

---

## Notes

- Conv 2 builder was the heaviest conversation at 164K tokens — reconciliation window threading required careful analysis.
- Conv 3 builder tokens not captured (session ran without token logging).
- Interactive/fast mode confirmed production-stable: no human gates required between stages.
