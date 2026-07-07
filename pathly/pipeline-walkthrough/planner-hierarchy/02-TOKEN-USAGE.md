# 02 — Token Usage: planner-hierarchy (g1-feature-planner-decompose)

_Date: 2026-07-06 | Sourced from: pathly/features/planner-hierarchy/goals/g1-feature-planner-decompose-2672c936/EVENTS.jsonl_

---

## Per-agent breakdown

| # | Agent | Role | Tokens | Tool uses | Wall time | Cost |
|---|---|---|---|---|---|---|
| 1 | builder (conv 1) | Build | 18,000 | 14 | 39s | $0.0504 |
| 2 | reviewer (conv 1, attempt 1) | Review | 8,000 | 18 | 268s | $0.0432 |
| 3 | reviewer (conv 1, attempt 2) | Review | 4,000 | 12 | 155s | $0.0216 |
| 4 | tester (conv 0) | Test | 94,745 | 7 | 195s | $0.3075 |

---

## Totals

| Metric | Value |
|---|---|
| Agent spawns | 4 |
| Total tokens | 124,745 |
| Total cost | $0.4227 |
| Total tool uses | 51 |
| Total wall time | ~657s (~11 min active) |

---

## Cost by pipeline stage

| Stage | Agents | Tokens | Cost |
|---|---|---|---|
| Discovery | — | — | — |
| Planning | — | — | — |
| Architect consult | — | — | — |
| Build + Review | builder, reviewer ×2 | 30,000 | $0.1152 |
| Test + fixes | tester | 94,745 | $0.3075 |
| Retro | retro (quick) | ~130,000 | ~$0.15 (est.) |
| **Total** | | **~254,745** | **~$0.57 est.** |

---

## What drove the cost

The tester dominated at 94,745 tokens — it ran comprehensive acceptance-criteria checks across four distinct CLAUDE.md locations plus structural integrity verification. The high token count is partly explained by the tester's claude-sonnet-4-6 context loading large files (CLAUDE.md, composition.yaml, the skill itself) for each check.

The review retry (attempt 2) was much cheaper than attempt 1 (4k vs 8k tokens) because the second pass had fewer files to evaluate after the fix.

> **Rigor verdict:** `lite` (build + review + test, no architect consult, no multi-conv build).
> Appropriate for a small, isolated skill addition — the main risk was doc-sync, which review caught. A `nano` run would have missed the CLAUDE.md violations entirely.
