# 02 — Token Usage: multi-adapter-routing

_Date: 2026-06-01 | Sourced from: pathly/plans/multi-adapter-routing/EVENTS.jsonl_

---

## Per-agent breakdown

| # | Agent | Conv | Tokens in | Tokens out | Total | Tool uses | Wall time | Cost |
|---|---|---|---|---|---|---|---|---|
| 1 | builder | 1 | not captured | not captured | not captured | not captured | 379s | not captured |
| 2 | builder | 2 | not captured | not captured | not captured | not captured | 185s | not captured |
| 3 | reviewer | 2 | 87,662 | 21,916 | 109,578 | 59 | 206s | $0.591726 |
| 4 | builder | 3 | not captured | not captured | not captured | not captured | 844s | not captured |
| 5 | reviewer | 3 | 21,831 | 5,458 | 27,289 | 17 | 100s | $0.147363 |
| 6 | builder | 4 | not captured | not captured | not captured | not captured | 780s | not captured |
| 7 | reviewer | 4 | 16,297 | 4,074 | 20,371 | 9 | 199s | $0.110001 |
| 8 | tester | 0 | 25,314 | 6,329 | 31,643 | 41 | 594s | $0.170877 |

---

## Totals

| Metric | Value |
|---|---|
| Agent spawns | 8 |
| Total tokens (captured) | 188,881 |
| Total tokens (builder, uncaptured) | not captured |
| Total cost (captured) | $1.019967 |
| Total cost (builder, uncaptured) | not captured |
| Total tool uses (captured) | 126 |
| Total wall time | ~3,287 seconds |

---

## Cost by pipeline stage

| Stage | Agents | Tokens | Cost |
|---|---|---|---|
| Discovery | — | — | — |
| Planning | — | — | — |
| Build | builder ×4 | not captured | not captured |
| Review | reviewer ×3 | 157,238 | $0.849090 |
| Test | tester ×1 | 31,643 | $0.170877 |
| Retro | retro | — | — |
| **Total (captured)** | | **188,881** | **$1.019967** |

---

## What drove the cost

The Conv 2 review pass was the single most expensive agent run ($0.59, 109,578 tokens, 59 tool uses). This was the deepest review — covering `git diff HEAD~2 HEAD` across both Conv 1 and Conv 2 changes (fsm_ops.py, state.py, CLAUDE.md, team.flow.yaml, and two test modules). The reviewer also added a missing edge-case test during the review cycle, extending its scope beyond read-only analysis.

Builder token telemetry is entirely absent — all four builder AGENT_DONE events have `tokens_in: 0, tokens_out: 0, cost_usd: 0.0`. The stop hook is not capturing builder session usage. True pipeline cost is unknown but likely 2-4x the captured figure.

> **Rigor verdict:** standard rigor was appropriate for this feature. The FSM/validator/Studio/skill stack crossed four layers and four files — lite would have missed the edge-case test gap found by the reviewer. Strict would not have added significant value given the clean test suite.
