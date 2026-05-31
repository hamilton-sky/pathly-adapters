# Token Usage — adapter_integration_contract

**Date:** 2026-06-01  
**Total spawns:** 8  
**Total tokens:** 207,321  
**Total cost:** $1.119534  
**Total tool uses:** 114  
**Total wall time:** 732s (~12 min)

## Per-Agent Breakdown

| # | Agent        | Role     | In     | Out    | Total  | Tools | Wall  | Cost     |
|---|--------------|----------|--------|--------|--------|-------|-------|----------|
| 1 | team/build   | builder  | 41,348 | 10,337 | 51,685 | 42    | 271s  | $0.2791  |
| 2 | team/review  | reviewer | 20,747 | 5,187  | 25,934 | 9     | 68s   | $0.1400  |
| 3 | team/build   | builder  | 16,869 | 4,217  | 21,086 | 9     | 52s   | $0.1139  |
| 4 | team/test    | tester   | 20,035 | 5,009  | 25,044 | 20    | 104s  | $0.1352  |
| 5 | team/build   | builder  | 20,748 | 5,187  | 25,935 | 8     | 61s   | $0.1400  |
| 6 | team/build   | builder  | 15,993 | 3,998  | 19,991 | 11    | 59s   | $0.1080  |
| 7 | team/review  | reviewer | 13,218 | 3,304  | 16,522 | 6     | 52s   | $0.0892  |
| 8 | team/test    | tester   | 16,899 | 4,225  | 21,124 | 9     | 65s   | $0.1141  |

## Stage Breakdown

| Stage    | Agents spawned | Tokens  | Cost     |
|----------|---------------|---------|----------|
| BUILDING | 4 (builder)   | 118,697 | $0.6410  |
| REVIEWING| 2 (reviewer)  | 42,456  | $0.2293  |
| TESTING  | 2 (tester)    | 46,168  | $0.2493  |

## Cost Analysis

Builder drove 57% of spend across 4 spawns (2 conversations + 2 fix cycles).
Conv 1 required 2 fix cycles (reviewer catch + tester gaps) — those 3 build spawns total $0.533.
Conv 2 was clean: 1 build + 1 review + 1 test, $0.311.

**Rigor verdict:** Lite rigor was appropriate. The reviewer and tester catches were genuine — the reviewer found a missing field in the contract and the tester found real coverage gaps. Standard rigor (architect + web-researcher) was not needed given the plan was already fully specified.
