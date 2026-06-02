# 02 — Token Usage: multi-adapter-runner

_Date: 2026-06-02 | Sourced from: pathly/plans/multi-adapter-runner/EVENTS.jsonl_

---

## Per-agent breakdown

| # | Agent | Role | Tokens in | Tokens out | Total | Tool uses | Wall time | Cost |
|---|---|---|---|---|---|---|---|---|
| 1 | builder | Conv 1 — adapter contract | 36,175 | 9,044 | 45,219 | 32 | 281s | $0.2442 |
| 2 | builder | Conv 2 — supervisor loop | 49,563 | 12,391 | 61,954 | 32 | 436s | $0.3346 |
| 3 | builder | Conv 3 — HTTP endpoints + SSE | 48,941 | 12,235 | 61,176 | 16 | 220s | $0.3304 |
| 4 | reviewer | Conv 3 round 1 — FAIL | ~38,000 | ~9,500 | ~47,500 | ~12 | ~90s | ~$0.2568 |
| 5 | builder | Conv 3 fix — 3 violations | ~35,000 | ~8,750 | ~43,750 | ~18 | ~160s | ~$0.2363 |
| 6 | reviewer | Conv 3 round 2 — PASS | 38,670 | 9,667 | 48,337 | 12 | 78s | $0.2611 |
| 7 | tester | Test stage | 64,410 | 16,102 | 80,512 | 35 | 202s | $0.4348 |
| 8 | quick | Retro | 2,000 | 500 | 2,500 | 7 | 22s | $0.0135 |

_Note: Rows 4–5 are estimates (reviewer round 1 and fix pass ran before EVENTS.jsonl tracking was fully active). Row 8 retro ran inline._

---

## Totals

| Metric | Confirmed | Estimated total |
|---|---|---|
| Agent spawns | 8 | 8 |
| Total tokens (confirmed) | 168,349 | ~391,248 |
| Total cost (confirmed) | $0.9092 | ~$2.1117 |
| Total tool uses (confirmed) | 80 | ~164 |
| Total wall time (confirmed) | 937s | ~1,489s (~24.8 min) |

---

## Cost by pipeline stage

| Stage | Agents | Tokens | Cost |
|---|---|---|---|
| Planning | — | — | — |
| Build + Review | 5 builders + 2 reviewers | ~303,198 | ~$1.6634 |
| Test | Tester | 80,512 | $0.4348 |
| Retro | Quick | 2,500 | $0.0135 |
| **Total** | | **~386,210** | **~$2.1117** |

---

## What drove the cost

- **Conv 2 and Conv 3 were the heaviest builds** — supervisor loop with caps/abort/session logic required deep multi-file reads and careful threading design.
- **The review failure cycle added ~$0.50** — a first reviewer pass (FAIL) plus builder fix plus second reviewer pass. The 3 violations were all schema/contract gaps that should have been caught at planning time.
- **Tester at $0.43** — standard for a feature with 25 acceptance criteria across 3 stories and both Python + TypeScript layers.

> **Rigor verdict:** standard was correct. The multi-adapter dispatch pattern has cross-layer implications (YAML → Python → TypeScript) that nano/lite rigor would have missed. Strict wasn't needed — no auth, payments, or destructive data changes.
