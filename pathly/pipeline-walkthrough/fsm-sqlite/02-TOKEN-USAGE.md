# 02 — Token Usage: fsm-sqlite

_Date: 2026-06-04 | Sourced from: pathly/plans/fsm-sqlite/EVENTS.jsonl_

---

## Per-agent breakdown

| # | Agent | Role | Tokens in | Tokens out | Total | Tool uses | Wall time | Cost |
|---|---|---|---|---|---|---|---|---|
| 1 | builder (conv 1) | worker | not split | not split | 45,376 | 30 | 22s | $0.245 |
| 2 | reviewer (conv 1) | worker | not split | not split | 25,341 | 6 | 121s | $0.137 |
| 3 | builder (conv 2) | worker | not split | not split | 124,138 | 79 | 1046s | $0.670 |
| 4 | reviewer (conv 2) | worker | not split | not split | 34,713 | 8 | 59s | $0.187 |
| 5 | builder (conv 3) | worker | not split | not split | 127,627 | 60 | 997s | $0.689 |
| 6 | reviewer (conv 3) | worker | not split | not split | 67,541 | 14 | 116s | $0.365 |
| 7 | reviewer (conv 4) | worker | not split | not split | 167,728 | 56 | 442s | $0.906 |
| 8 | reviewer (conv 4 re-review) | worker | not split | not split | 11,219 | 2 | 35s | $0.061 |

> **Note:** builder (conv 4) ran across a session boundary — no AGENT_DONE was written to EVENTS.jsonl. Cost and tokens not captured.

---

## Totals

| Metric | Value |
|---|---|
| Agent spawns | 8 |
| Total tokens | 603,683 |
| Total cost | $3.26 |
| Total tool uses | 255 |
| Total wall time | 2,838s (~47 min) |

---

## Cost by pipeline stage

| Stage | Agents | Tokens | Cost |
|---|---|---|---|
| Discovery | — | — | — |
| Planning | Planner | not captured | not captured |
| Architect consult | — | — | — |
| Build + Review (conv 1) | builder + reviewer | 70,717 | $0.382 |
| Build + Review (conv 2) | builder + reviewer | 158,851 | $0.857 |
| Build + Review (conv 3) | builder + reviewer | 195,168 | $1.054 |
| Build + Review (conv 4) | reviewer ×2 | 178,947 | $0.967 |
| Test + fixes | tester | not captured | not captured |
| Retro | Retro | not captured | not captured |
| **Total (captured)** | | **603,683** | **$3.26** |

---

## What drove the cost

Conv 3 and Conv 4 were the most expensive build conversations — each involved large multi-file reads across supervisor.py (~1200 lines), http_server.py (~700 lines), and the full test suites. The Conv 4 re-review was unusually efficient (11k tokens) because the idempotency fix was isolated to a single guard in the migration script.

The reviewer consumed 278k tokens (~46% of total) across 4 invocations, which is high relative to 3 builder invocations at 297k (~49%). This reflects the thorough multi-file structural checks the reviewer performs.

> **Rigor verdict:** Standard rigor was appropriate here. This was a cross-cutting storage migration touching 5 files and 430 tests — lite rigor would have missed the idempotency bug and the BEGIN IMMEDIATE conflict.
> Was standard rigor the right call for this feature? Yes — the two feedback loops caught real bugs that would have surfaced in production.
