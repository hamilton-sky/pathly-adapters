# Token Usage — brightsky-chat-connect

**Total spawns:** 5
**Total tokens:** 175,181  (in: 140,145 · out: 35,036)
**Total cost:** $0.946135
**Total tool uses:** 112
**Total wall time:** ~816s (~14 min)

## Per-Agent Breakdown

| # | Agent   | Role    | Tokens in | Tokens out | Total   | Tools | Wall (s) | Cost    |
|---|---------|---------|-----------|------------|---------|-------|----------|---------|
| 1 | planner | worker  | 18,553    | 4,638      | 23,191  | 13    | 212      | $0.1252 |
| 2 | builder | worker  | 31,966    | 7,991      | 39,957  | 36    | 208      | $0.2158 |
| 3 | builder | worker  | 22,590    | 5,648      | 28,238  | 22    | 110      | $0.1525 |
| 4 | builder | worker  | 40,818    | 10,204     | 51,022  | 26    | 192      | $0.2756 |
| 5 | builder | worker  | 26,218    | 6,555      | 32,773  | 15    | 96       | $0.1770 |

## Stage Breakdown

| Stage    | Spawns | Tokens  | Cost    |
|----------|--------|---------|---------|
| PLANNING | 1      | 23,191  | $0.13   |
| BUILDING | 4      | 151,990 | $0.82   |

## Cost Analysis
Builder drove 87% of total cost ($0.82 of $0.95). The four builder passes reflect: Conv 1 implementation, Conv 1 review-fix retry, Conv 2 first pass, Conv 2 second pass. No reviewer or tester agent was spawned — review was handled inline by the FSM retry loop.

## Rigor Verdict
Standard rigor was justified — the IPC/preload TypeScript boundary produced real review failures. Lite rigor (no review pass) would likely have shipped broken types. Cost was reasonable at $0.95 for OAuth + full WebSocket streaming integration.
