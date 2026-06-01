# fsm-friction-fixes — Token Usage

**Total spawns:** 7
**Total tokens:** 273,222
**Total cost:** $1.475274
**Total tool uses:** 128
**Total wall time:** ~1,500s

## Per-Agent Breakdown

| # | Agent        | Role      | In      | Out    | Total  | Tools | Wall  | Cost    |
|---|--------------|-----------|---------|--------|--------|-------|-------|---------|
| 1 | team/discover| planner   | 62,510  | 15,627 | 78,137 | 20    | 184s  | $0.422  |
| 2 | builder      | builder   | n/c     | n/c    | n/c    | n/c   | n/c   | n/c     |
| 3 | reviewer     | reviewer  | 38,337  | 9,584  | 47,921 | 21    | 86s   | $0.259  |
| 4 | builder      | builder   | n/c     | n/c    | n/c    | n/c   | n/c   | n/c     |
| 5 | reviewer     | reviewer  | 26,374  | 6,594  | 32,968 | 12    | 480s  | $0.178  |
| 6 | reviewer     | reviewer  | 37,701  | 9,425  | 47,126 | 18    | 121s  | $0.254  |
| 7 | tester       | tester    | 53,656  | 13,414 | 67,070 | 39    | 344s  | $0.362  |

> Builder token costs were not captured (sessions ran without usage-block logging). Total of 3 builder spawns.

## Stage Breakdown

| Stage    | Agents           | Cost    | % of total |
|----------|------------------|---------|------------|
| PLANNING | team/discover    | $0.422  | 28.6%      |
| BUILDING | builder ×3       | n/c     | —          |
| REVIEWING| reviewer ×3      | $0.691  | 46.9%      |
| TESTING  | tester           | $0.362  | 24.5%      |

## Cost Analysis

Reviewers were the largest captured cost driver at 46.9% across 3 conversations. This is expected for standard rigor — reviewer runs after every conv. Tester at 24.5% reflects full acceptance-criteria verification across S1, S2, S3 (21 criteria total).

**Rigor verdict:** Standard rigor was appropriate. Reviewer caught two meaningful bugs before they shipped (missing test coverage, regex overcounting). Lite rigor would have missed these.
