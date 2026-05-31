# 02 — Token Usage: wizard-e2e-flow

_Date: 2026-05-31 | Sourced from: pathly/plans/wizard-e2e-flow/EVENTS.jsonl_

---

## Per-agent breakdown

| # | Agent | Role | Tokens in | Tokens out | Total | Tool uses | Wall time | Cost |
|---|---|---|---|---|---|---|---|---|
| 1 | planner | Planning | 40,482 | 10,120 | 50,602 | 57 | 380s | $0.2733 |
| 2 | builder (conv 1) | Build — Studio testids | 24,603 | 6,151 | 30,754 | 30 | 261s | $0.1661 |
| 3 | reviewer (conv 1) | Review — Studio testids | 16,297 | 4,074 | 20,371 | 19 | 137s | $0.1100 |
| 4 | builder (conv 2) | Build — POM + glue + workflow | 32,961 | 8,240 | 41,201 | 39 | 543s | $0.2228 |
| 5 | tester (conv 0) | Test — all stories | 26,520 | 6,630 | 33,150 | 16 | 162s | $0.1790 |

---

## Totals

| Metric | Value |
|---|---|
| Agent spawns | 5 |
| Total tokens | 176,078 |
| Total cost | $0.9512 |
| Total tool uses | 161 |
| Total wall time | 1,483s (~24.7 min) |

---

## Cost by pipeline stage

| Stage | Agents | Tokens | Cost |
|---|---|---|---|
| Discovery | — | 0 | $0.00 |
| Planning | Planner | 50,602 | $0.2733 |
| Architect consult | — | 0 | $0.00 |
| Build + Review | Builder x2, Reviewer | 92,326 | $0.4989 |
| Test + fixes | Tester | 33,150 | $0.1790 |
| Retro | Retro | not captured | not captured |
| **Total** | | **176,078** | **$0.9512** |

---

## What drove the cost

The largest single spend was the planner (50,602 tokens, $0.27). This is elevated because the
initial plan draft was incorrect (Vitest unit-test format instead of Stepper automation) and
required correction, adding an extra planning iteration.

Builder Conv 2 (41,201 tokens, $0.22) was the costliest build conversation — creating three
new files (POM, glue, workflow) and modifying two existing files in a different repo accounts
for the higher tool-use count (39).

The reviewer was efficient (20,371 tokens, $0.11) for the scope it covered (6 component files
plus pre-existing violation audit).

The tester was within normal range (33,150 tokens, $0.18) for a 22-criterion test plan across
two repos.

> **Rigor verdict:** Standard rigor was appropriate for this feature.
> The reviewer caught a real pre-existing violation (missing type="button") that would have
> been missed at lite rigor. The planning correction cycle added ~$0.05 overhead that would
> have been avoided with a clearer feature-class declaration in the planner prompt.
