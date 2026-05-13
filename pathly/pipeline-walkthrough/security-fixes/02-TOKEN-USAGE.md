# 02 — Token Usage: security-fixes

Token counts per agent spawn, in execution order.
All figures are estimates from agent self-reports during the run.

---

## Per-agent breakdown

| # | Agent | Role | Tokens | Tool uses | Wall time |
|---|---|---|---|---|---|
| 1 | Explore | Map full project structure | ~28,003 | 35 | 98s |
| 2 | Reviewer | Initial security audit | ~15,000 | est. | est. |
| 3 | Planner | Write 4 lite plan files | ~20,451 | 11 | 105s |
| 4 | Architect (meet/consult) | Pre-build validation, CONSULT_architect.md | ~22,716 | 6 | 42s |
| 5 | Builder — Conv 1 | Code fixes (3 files) | ~26,153 | 23 | 85s |
| 6 | Reviewer — Conv 1 | Review code changes | ~15,633 | 6 | 38s |
| 7 | Builder — Conv 2 | .gitignore + SECURITY.md | ~16,015 | 9 | 39s |
| 8 | Reviewer — Conv 2, pass 1 | Review docs — FAIL | ~16,695 | 10 | 58s |
| 9 | Builder — fix cycle 1 | Partial SECURITY.md fix | ~12,847 | 7 | 24s |
| 10 | Reviewer — Conv 2, pass 2 | Re-review — FAIL again | ~10,370 | 6 | 41s |
| 11 | Builder — fix cycle 2 | Full SECURITY.md rewrite | ~12,313 | 5 | 22s |
| 12 | Reviewer — Conv 2, pass 3 | Final check — PASS | ~7,901 | 2 | 10s |
| 13 | Tester — run 1 | Acceptance criteria check | ~35,813 | 33 | 231s |
| 14 | Builder — story update | Update Story 3b criterion | ~13,267 | 5 | est. |
| 15 | Tester — run 2 | Full retest + pre-existing check | ~32,233 | 28 | 197s |
| 16 | Builder — test fix | Fix broken test, 16/16 pass | ~17,337 | 7 | 44s |
| 17 | Retro | Write RETRO.md | ~9,062 | 6 | 15s |

---

## Totals

| Metric | Value |
|---|---|
| Named agents (known) | 17 spawns |
| Known tokens | ~283,756 |
| Estimated total (incl. untracked) | ~300,000 – 310,000 |
| Total tool uses (known) | ~199 |
| Total wall time (known) | ~1,049s (~17.5 min of agent time) |

---

## What drove the cost

### Testers are the most expensive agents (runs 1 + 2 = ~68,000 tokens)
Testers read USER_STORIES.md, run pytest, capture output, then cross-reference each
acceptance criterion against real code and test output. Two full passes were needed
because Story 3b's criterion did not match actual server behavior.

### Explore is front-loaded but one-time (~28,000 tokens)
The explore agent reads every file in src/ to build the full picture before the
reviewer runs. This is a fixed cost paid once — it prevents reviewers and planners
from missing files or guessing at structure.

### Feedback loops are the multiplier (3 loops × ~40,000 tokens)
Each review failure triggers a builder + reviewer pair:
- Review loop 1: ~12,847 + ~10,370 = ~23,217 tokens
- Review loop 2: ~12,313 + ~7,901 = ~20,214 tokens
- Test loop: ~13,267 tokens

Without the two SECURITY.md wording failures, the total would be ~260,000 tokens.
The lesson: precise wording in conversation prompts reduces loop cost.

### Architect consult pays off (~22,716 tokens)
The architect caught two real bugs (single-pass uninstall, negative Content-Length)
before the builder ran. Fixing them in planning cost ~22,716 tokens. Fixing them
after a reviewer failure would have cost at least one builder + reviewer loop
(~28,000+ tokens). Net saving: ~5,000+ tokens and one review cycle.

---

## Token cost by pipeline stage

| Stage | Agents | Tokens |
|---|---|---|
| Discovery | Explore + Reviewer | ~43,003 |
| Planning | Planner | ~20,451 |
| Architect consult | Architect | ~22,716 |
| Build + Review (Conv 1) | Builder + Reviewer | ~41,786 |
| Build + Review (Conv 2, 3 cycles) | Builder × 3 + Reviewer × 3 | ~75,141 |
| Test + fixes (2 runs) | Tester × 2 + Builder × 2 | ~98,650 |
| Retro | Retro | ~9,062 |
| **Total (known)** | | **~283,756** |
