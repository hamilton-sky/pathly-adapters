# 02 — Token Usage: {{FEATURE}}

_Date: {{DATE}} | Sourced from: plans/{{FEATURE}}/EVENTS.jsonl_

---

## Per-agent breakdown

| # | Agent | Role | Tokens in | Tokens out | Total | Tool uses | Wall time | Cost |
|---|---|---|---|---|---|---|---|---|
{{AGENT_TOKEN_ROWS}}

---

## Totals

| Metric | Value |
|---|---|
| Agent spawns | {{TOTAL_SPAWNS}} |
| Total tokens | {{TOTAL_TOKENS}} |
| Total cost | {{TOTAL_COST_USD}} |
| Total tool uses | {{TOTAL_TOOL_USES}} |
| Total wall time | {{TOTAL_WALL_TIME}} |

---

## Cost by pipeline stage

| Stage | Agents | Tokens | Cost |
|---|---|---|---|
| Discovery | {{DISCOVERY_AGENTS}} | {{DISCOVERY_TOKENS}} | {{DISCOVERY_COST}} |
| Planning | Planner | {{PLANNING_TOKENS}} | {{PLANNING_COST}} |
| Architect consult | Architect | {{ARCHITECT_TOKENS}} | {{ARCHITECT_COST}} |
| Build + Review | {{BUILD_AGENTS}} | {{BUILD_TOKENS}} | {{BUILD_COST}} |
| Test + fixes | {{TEST_AGENTS}} | {{TEST_TOKENS}} | {{TEST_COST}} |
| Retro | Retro | {{RETRO_TOKENS}} | {{RETRO_COST}} |
| **Total** | | **{{TOTAL_TOKENS}}** | **{{TOTAL_COST_USD}}** |

---

## What drove the cost

{{COST_ANALYSIS}}

> **Rigor verdict:** {{RIGOR_VERDICT}}
> Was {{RIGOR}} rigor the right call for this feature? What would lite/standard/strict have changed?
