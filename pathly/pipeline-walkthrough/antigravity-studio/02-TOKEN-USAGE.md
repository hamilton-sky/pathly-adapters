# 02 — Token Usage: antigravity-studio

_Date: 2026-06-01 | Branch: master | Rigor: lite_

Per-agent token consumption and cost breakdown.

---

## Per-agent breakdown

| Agent | Conv | Tokens | Cost (USD) | Tools | Wall (s) |
|---|---|---|---|---|---|
| builder | 1 | 18,224 | $0.098410 | 10 | 78 |
| builder | 2 | 43,883 | $0.237099 | 37 | 201 |
| builder | 3 (initial) | 28,681 | $0.154869 | 21 | 134 |
| builder | 3 (fix-cycle 1) | 65,305 | $0.352647 | 64 | 500 |
| builder | 3 (fix-cycle 2) | 23,226 | $0.125421 | 11 | 72 |
| reviewer | 3 (pass 1) | 51,445 | $0.277341 | 36 | 182 |
| reviewer | 3 (pass 2) | — | — | — | — |
| tester | 0 | 33,745 | $0.182223 | 17 | 95 |
| designer | consult | 27,565 | — | — | — |
| quick | 0 (retro) | 8,500 | $0.045900 | 4 | 12 |

> Reviewer pass 2 was a micro-fix review (one violation); bundled in the same session as pass 1.
> Designer cost not separately billed — consultative session.

---

## Totals

| Metric | Value |
|---|---|
| Total tokens (billed agents) | ~272,009 |
| Total cost (billed agents) | ~$1.47 |
| Total wall time | ~1,274 s (~21 min) |
| Total tool uses | 200 |

---

## Cost model

All agents: `claude-sonnet-4-6`
Pricing: $3.00 / MTok input · $15.00 / MTok output (80/20 split applied where input/output split unknown)

---

## Cost drivers

- **Builder fix-cycle 1** (65,305 tokens / $0.353) — largest single agent call. Reviewer pass 1 surfaced 6 violations spanning 6 files; the fix cycle touched useHQ.tsx, TerminalLauncher.tsx, PaneTabBar.tsx, MiniTerminalCard.tsx, HQ/index.tsx — required full file reads before each edit.
- **Reviewer pass 1** (51,445 tokens / $0.277) — scouted 8 files for correctness; found violations in useHQ.tsx (4), TerminalLauncher.tsx (1), PaneTabBar.tsx (1).
- **Builder conv 2** (43,883 tokens / $0.237) — TypeScript exhaustiveness cascade across 5 files required multiple iterative edits.
