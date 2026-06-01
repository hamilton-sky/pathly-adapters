# 02 — Token Usage: antigravity-adapter

_Date: 2026-06-01 | Sourced from: plans/antigravity-adapter/EVENTS.jsonl_

---

## Per-agent breakdown

| # | Agent | Conv | Tokens in | Tokens out | Total | Tool uses | Wall time | Cost |
|---|---|---|---|---|---|---|---|---|
| 1 | builder | 4 | 0 | 0 | 0 | 0 | 96s | $0.000000 |
| 2 | reviewer | 4 | 28,888 | 7,222 | 36,110 | 20 | 71s | $0.194994 |
| 3 | tester | 0 | ~20,758 | ~5,190 | 25,948 | 16 | 162s | $0.140124 |
| 4 | quick (retro) | — | ~9,729 | ~2,432 | 12,161 | 7 | 15s | $0.065670 |

> Builder token data shows zero — the stop hook fired but builder token capture was not recorded in EVENTS.jsonl (pre-existing telemetry gap; see `[multi-adapter-routing]` lesson in LESSONS_CANDIDATE.md).

---

## Totals

| Metric | Value |
|---|---|
| Agent spawns | 4 (builder, reviewer, tester, quick) |
| Total tokens (captured) | ~74,219 |
| Total cost (captured) | ~$0.401 |
| Total tool uses | 43 |
| Total wall time | ~344s |

---

## Cost by pipeline stage

| Stage | Agents | Tokens | Cost |
|---|---|---|---|
| Discovery / Planning / Designing | — (prior sessions) | not captured | not captured |
| Build Conv 4 | builder | 0 (not captured) | $0.00 |
| Review | reviewer | 36,110 | $0.195 |
| Test + fix cycle | tester | 25,948 | $0.140 |
| Retro | quick | 12,161 | $0.066 |
| **Total (captured)** | | **~74,219** | **~$0.401** |

---

## What drove the cost

The reviewer was the most expensive per-spawn ($0.195), driven by 20 tool uses to read test files, compare against plan acceptance criteria, and verify scope boundaries. The tester's fix cycle was included in a single agent spawn.

Builder cost is zero in telemetry — the stop hook records session tokens but the Conv 4 builder run happened in a separate session before this pipeline resumption. This is a known gap.

> **Rigor verdict:** lite rigor was correct for this feature.
> All changes were additive YAML files, detection config, and test assertions — low blast radius, no schema migrations, no auth/payment/secrets. Reviewer ran only on the final conversation. Standard rigor would have added per-conversation reviews on Convs 1–3 with no benefit for additive, config-only changes.
