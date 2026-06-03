# Studio A11y Phase 1 — Token Usage

**Feature:** studio-a11y-p1
**Date:** 2026-06-03

## Agent Spawns

| # | Agent | Role | Tokens In | Tokens Out | Total | Tools | Wall (ms) | Cost |
|---|-------|------|-----------|------------|-------|-------|-----------|------|
| 1 | builder | Conv 1 — chip toggles | 36,149* | — | 36,149 | 34 | 285,586 | not captured |
| 2 | builder | Conv 2 — modal ARIA | 27,250* | — | 27,250 | 24 | 150,977 | not captured |
| 3 | builder | Conv 3 — ContextMenu + tokens | 41,700* | — | 41,700 | 40 | 1,502,994 | not captured |
| 4 | reviewer | initial review | 40,735* | — | 40,735 | 24 | 116,825 | not captured |
| 5 | builder | ContextMenu CSS fix | 29,292* | — | 29,292 | 17 | 138,527 | not captured |
| 6 | reviewer | re-review | 13,951* | — | 13,951 | 5 | 25,731 | not captured |
| 7 | tester | 22 criteria | 43,769* | — | 43,769 | 25 | 175,474 | not captured |

\* `total_tokens` from agent completion metadata (in+out combined)

**Total spawns:** 7
**Total tokens:** ~233,046 (combined in+out)
**Total tool uses:** ~169
**Total wall time:** ~2,396 seconds (~40 min)
**Total cost:** not captured (cost_usd not recorded in EVENTS.jsonl)

## Stage Breakdown

| Stage | Agents | Tokens |
|-------|--------|--------|
| BUILDING | builder ×3 | ~105,099 |
| REVIEWING | reviewer ×2, builder ×1 | ~83,978 |
| TESTING | tester ×1 | ~43,769 |

## Cost Analysis

Cost data was not captured at spawn time. Token volume was highest in Conv 3 (ContextMenu + 12-theme tokens.css) and the initial review round. The unplanned fix round (agents 4–6) added ~84k tokens — roughly 36% of total spend — due to the pre-existing ContextMenu violations. Pre-flighting files for CLAUDE.md violations before listing them as touchpoints would have eliminated this overhead.

## Rigor Verdict

Standard rigor was appropriate: the reviewer catch of ContextMenu violations was valuable (would have shipped a CLAUDE.md violation otherwise). Lite rigor would have missed it.
