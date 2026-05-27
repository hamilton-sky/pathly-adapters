# 02 — Token Usage: studio-ai-chat

_Date: 2026-05-27 | Sourced from: pathly/plans/studio-ai-chat/EVENTS.jsonl_

---

## Per-agent breakdown

| # | Agent | Role | Tokens in | Tokens out | Total | Tool uses | Wall time | Cost |
|---|---|---|---|---|---|---|---|---|
| 1 | builder | Conv 0 | 24,282 | 6,071 | 30,353 | 38 | 858s | $0.1639 |
| 2 | reviewer | Conv 0 | 39,717 | 9,929 | 49,646 | 17 | 83s | $0.2681 |
| 3 | builder | Conv 1 | 20,018 | 5,004 | 25,022 | 14 | 82s | $0.1351 |
| 4 | reviewer | Conv 1 | 8,872 | 2,218 | 11,090 | 12 | 276s | $0.0599 |
| 5 | builder | Conv 2 | 33,035 | 8,259 | 41,294 | 38 | 225s | $0.2230 |
| 6 | reviewer | Conv 2 | 20,151 | 5,038 | 25,189 | 23 | 85s | $0.1360 |
| 7 | builder | Conv 3 | 25,058 | 6,264 | 31,322 | 27 | 158s | $0.1691 |
| 8 | reviewer | Conv 3 | 25,883 | 6,471 | 32,354 | 14 | 74s | $0.1745 |
| 9 | builder | Conv 4 | — | — | — | — | 167s | — |
| 10 | reviewer | Conv 4 | 30,484 | 7,621 | 38,105 | 24 | 138s | $0.2058 |
| 11 | builder | Conv 5 | 24,176 | 6,044 | 30,220 | 28 | 298s | $0.1632 |
| 12 | reviewer | Conv 5 | 22,535 | 5,634 | 28,169 | 25 | 92s | $0.1521 |
| 13 | builder | Conv 6 | 37,077 | 9,269 | 46,346 | 9 | 76s | $0.2503 |
| 14 | reviewer | Conv 6 | 9,913 | 2,478 | 12,391 | 9 | 34s | $0.0669 |
| 15 | builder | Conv 7 | 20,562 | 5,141 | 25,703 | 19 | 108s | $0.1388 |
| 16 | reviewer | Conv 7 | 35,626 | 8,907 | 44,533 | 21 | 81s | $0.2405 |
| 17 | builder | Conv 8 | 45,930 | 11,482 | 57,412 | 40 | 248s | $0.3100 |
| 18 | reviewer | Conv 8 | 41,936 | 10,484 | 52,420 | 29 | 124s | $0.2831 |
| 19 | builder | Conv 9 | 50,738 | 12,684 | 63,422 | 44 | 268s | $0.3425 |
| 20 | reviewer | Conv 9 | 26,041 | 6,510 | 32,551 | 21 | 74s | $0.1758 |
| 21 | tester | Testing | 23,291 | 5,823 | 29,114 | 11 | 89s | $0.1572 |
| 22 | quick | Retro | 17,354 | 4,339 | 21,693 | 3 | 24s | $0.1171 |

_Conv 4 builder tokens not captured (telemetry gap)._

---

## Totals

| Metric | Value |
|---|---|
| Agent spawns | 22 |
| Total tokens | ~728,349 |
| Total cost | ~$3.93 |
| Total tool uses | 466 |
| Total wall time | ~3,662s (~61 min) |

---

## Cost by pipeline stage

| Stage | Agents | Tokens | Cost |
|---|---|---|---|
| Discovery | — | not captured | — |
| Planning | Planner | not captured | — |
| Architect consult | — | — | — |
| Build + Review | 20 (10 builder + 10 reviewer) | ~677,542 | ~$3.66 |
| Test + fixes | 1 tester + 1 builder fix | ~29,114 | ~$0.16 |
| Retro | 1 quick | ~21,693 | ~$0.12 |
| **Total** | **22** | **~728,349** | **~$3.93** |

---

## What drove the cost

**Reviewers were expensive.** Conv 0 (reviewer: 49,646 tokens) and Conv 8 (reviewer: 52,420 tokens) drove the highest single-agent costs — deep diffs with many violations to enumerate. Reviewer cost totaled ~$1.76 across 10 conversations.

**Conv 9 builder was the largest build.** Implementing WebLLM from scratch (models.ts, webLLMEngine.ts, modelStore.ts, ModelSelector.tsx, wiring in index.tsx) required 63,422 tokens — the most of any builder conversation.

**Scope gate retries cost nothing in tokens but real wall time.** 10+ scope gate failures added ~0 tokens but forced manual orchestration overhead across 5 conversations.

**Conv 4 telemetry gap.** Builder tokens were not captured for Conv 4 — accounting gap, not a pipeline failure.

> **Rigor verdict:** `standard` rigor was appropriate.
> `lite` would have skipped per-conversation review and likely shipped S9.3 (selectedModelId not wired) silently. `strict` would have required formal test coverage for every story, which is impractical for Electron/WebGPU-dependent features. `standard` caught the real bug (S9.3) while keeping overhead manageable.
