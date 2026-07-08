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

---

# 02 — Token Usage: planner-hierarchy (g3-modernize-bmad-prd-9f77f795)

_Date: 2026-07-08 | Sourced from: fsm_events (central DB)_

---

## Per-agent breakdown

| # | Agent | Role | Tokens | Tool uses | Wall time | Cost |
|---|---|---|---|---|---|---|
| 1 | builder (conv 0) | Build | 28,000 | 22 | 591s | $0.1140 |
| 2 | reviewer (conv 1, attempt 1) | Review | 280,993 | 50 | 906s | $1.1010 |
| 3 | builder (conv 0) | Test check | 8,000 | 12 | 61s | $0.0432 |
| 4 | reviewer (conv 1, re-review) | Review | 200,998 | 49 | 650s | $0.6421 |
| 5 | tester (conv 0) | Test | 93,731 | 12 | 697s | $0.5061 |

---

## Totals

| Metric | Value |
|---|---|
| Agent spawns | 5 |
| Total tokens | 611,722 |
| Total cost | $2.4064 |
| Total tool uses | 145 |
| Total wall time | ~2905s (~48 min active) |

---

## Cost by pipeline stage

| Stage | Agents | Tokens | Cost |
|---|---|---|---|
| Build | builder | 28,000 | $0.1140 |
| Review | reviewer ×2 | 481,991 | $1.7431 |
| Test check | builder | 8,000 | $0.0432 |
| Test | tester | 93,731 | $0.5061 |
| Retro | retro (quick) | ~1,842 | ~$0.00 est. |
| **Total** | | **~613,564** | **~$2.41** |

---

## What drove the cost

The two reviewer passes dominated at ~482k tokens combined — the reviewer loaded large context files (prd-import.md, composition.yaml, CLAUDE.md, ArtifactsView.tsx, useWorkspaceTree.ts, conftest.py, test files) for thorough analysis. The first pass (281k) was more expensive than the second (201k) because it had to do the MAJOR violation fix inline.

The tester at 94k was comparable to G1's tester — comprehensive acceptance-criteria verification across 7 distinct checks.

> **Rigor verdict:** `lite` (build + double-review + test).
> The double review was warranted — the first pass caught and self-fixed a MAJOR violation; the second pass confirmed everything was clean after the test-check step. A single review pass would have left the MAJOR to be caught later.
