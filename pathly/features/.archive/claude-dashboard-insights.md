# Claude Dashboard — Insights for Pathly

> Source reviewed: [`iftahs/claude-dashboard`](https://github.com/iftahs/claude-dashboard) (read-only review, June 2026).
> A third-party, local, offline React/TS + Express dashboard that parses the
> JSON/JSONL logs Claude Code writes to `~/.claude` and visualizes usage, cost,
> burn rate, cache efficiency, per-model and per-project breakdowns. No API key,
> no network egress.

This is **not** a proposal to adopt or fork that project. It's a record of what's
worth borrowing and how it maps onto Pathly's existing telemetry work — chiefly
the [`provider-agnostic-telemetry`](./provider-agnostic-telemetry.md) plan and
the Studio app.

---

## TL;DR — three concrete takeaways

1. **Cache tokens are a first-class cost driver and Pathly's telemetry currently ignores them.**
   The dashboard's pricing model and "effective tokens" math both center on
   `cacheCreateTokens` / `cacheReadTokens`. Our `provider-agnostic-telemetry`
   schema and `PRICING` registry capture only `tokens_in` / `tokens_out`. This is
   a real accuracy gap, not a cosmetic one — for long agent sessions cache
   read/write often dominates spend.

2. **Pathly can build a usage dashboard the original structurally cannot.**
   The dashboard reads `~/.claude` logs, which know *nothing* about pipeline
   phase or agent role. Pathly's FSM assigns every spend to a phase
   (STORM/PLAN/DESIGN/BUILD/REVIEW/TEST/RETRO) and a role (architect/builder/
   reviewer/…). Cost-per-phase and cost-per-role is a cut nobody reading raw
   `~/.claude` can produce. That's the differentiated feature.

3. **Borrow the math, not the code.** Reuse the pricing table, the cost formula,
   and the aggregation shapes as a reference. Implement natively against Pathly's
   own `EVENTS.jsonl` / `02-TOKEN-USAGE.md`, which we control and which won't
   break when Anthropic changes its log format.

---

## What the dashboard actually does (verified from source)

| Server file | Responsibility |
|---|---|
| `server/scan.ts` | Recursively reads `~/.claude/projects/**/*.jsonl`; also `~/.claude/usage-data/session-meta/*.json`. Dedupes by `requestId:messageId` to survive streaming/retries. Decodes project path from the encoded dir name. |
| `server/pricing.ts` | Per-model rate table + `estimateCost()`. |
| `server/aggregate.ts` | Rolls events into the 5h / weekly / heatmap / per-project / per-model / tool-usage shapes the UI renders. |
| `server/cache.ts`, `index.ts` | 30s cache; Express `/api` endpoints. |

**Per-record fields extracted** (`UsageEvent`): `ts`, `sessionId`, `model`,
`inputTokens`, `outputTokens`, `cacheCreateTokens`, `cacheReadTokens`, `tools[]`,
decoded project path.

**Key formulas worth copying verbatim:**

```
effectiveTokens = inputTokens + outputTokens + cacheCreateTokens
cacheEfficiency = (cacheReadTokens / totalTokens) * 100
cost            = (inputTokens      * input
                 + outputTokens     * output
                 + cacheCreateTokens * cacheWrite
                 + cacheReadTokens   * cacheRead) / 1_000_000
```

**Pricing table** (USD per 1M tokens) — current as of the review, includes cache
columns our registry is missing:

| Model | Input | Output | Cache write | Cache read |
|---|---|---|---|---|
| Fable / Mythos | 10 | 50 | 12.50 | 1.0 |
| Opus 4.5–4.8 | 5 | 25 | 6.25 | 0.5 |
| Opus (legacy) | 15 | 75 | 18.75 | 1.5 |
| Sonnet (all) | 3 | 15 | 3.75 | 0.3 |
| Haiku 4.5 | 1 | 5 | 1.25 | 0.1 |
| Haiku 3.5 | 0.8 | 4 | 1.0 | 0.08 |
| Haiku (legacy/default) | 0.25 | 1.25 | 0.3125 | 0.03 |

Default fallback = Sonnet rates. Cache-write is consistently `input × 1.25` and
cache-read is `input × 0.1` — a useful rule for filling unknown models.

---

## Recommendations

### R1 — Add cache tokens to the telemetry schema and pricing registry *(highest value, smallest change)*

Folds directly into the open `provider-agnostic-telemetry` plan.

- Extend the canonical event (Layer 1) with `cache_create_tokens` and
  `cache_read_tokens`. Keep them optional/zero-default so existing logs still parse.
- Extend the `PRICING` registry (Layer 2) entries from `{input, output}` to
  `{input, output, cache_write, cache_read}`, using the table above as the seed
  for `claude`. For providers that don't bill cache separately, set those to `0`.
- Update the cost-resolution formula to the 4-term version above. Provider-reported
  `cost_usd` still wins when present (the plan's existing policy).
- This makes Pathly's `cost_usd` materially more accurate for long sessions, where
  cache read/write is the bulk of token volume.

**Where:** `log-agent-done`, `stop_telemetry.py`, and the shared pricing util the
telemetry plan calls for. The dashboard's `pricing.ts` is a ready-made reference
for the table values.

### R2 — Capture `cache_*` tokens at the source

Confirm the supervisor / `AGENT_DONE` path actually records cache token counts
from the CLI's `--output-format=json` usage block (the dashboard reads
`cache_creation_input_tokens` / `cache_read_input_tokens`). R1's schema is inert
if these never get populated. If the runner only stores `cost_usd` + `session_id`
today, widen it to persist the full usage object.

### R3 — Studio "Usage" panel, attributed by phase and role *(the differentiated feature)*

A new tab in the Electron app, fed by a supervisor aggregation endpoint over
`EVENTS.jsonl` (mirrors the dashboard's `/api` + `aggregate.ts` pattern). Cuts the
original can't make:

- **Cost per feature** — sum across a `pathly/plans/<feature>/` run.
- **Cost per phase** — STORM vs PLAN vs BUILD vs REVIEW vs TEST. Answers "is review
  costing more than the build it's reviewing?"
- **Cost per role/model** — opus architect vs sonnet builder vs haiku scout.
  Directly informs rigor-level tuning (`nano`/`lite`/`standard`/`strict`).
- **Cache efficiency per run** — reuse the dashboard's formula; low cache-read %
  on a long run is a prompt-stability smell.

Reuse from the dashboard: the aggregation output shapes (`TokenTotals`,
per-model/per-bucket rollups), the heatmap idea, and CSV/JSON export.

### R4 — Pricing as data, with a manual override

The dashboard hardcodes rates in `pricing.ts`; they already drift (note the
Opus 4.5–4.8 vs legacy split). Pathly should keep the pricing registry as a small
declarative data file with an override hook — which the telemetry plan's open
question #4 ("manual override file for pricing changes?") already anticipates.
**Recommendation: yes, ship the override file.**

---

## What to deliberately ignore

- **Account-level rate-limit / weekly-cap tracking.** Account-global, orthogonal to
  Pathly's per-feature model, and (per the dashboard's own README) can't be made
  exact because reset times live in API response headers Claude Code never persists.
- **Reading `~/.claude` directly.** Pathly already owns richer, phase-tagged data in
  `EVENTS.jsonl`. Don't couple to an external log format we don't control.
- **Vendoring/forking the project.** Single-author third-party tool. Treat it as a
  reference implementation for the math and the panel design only.

---

## Suggested sequencing

1. **R1 + R2** — small, high-accuracy win; lands inside the existing telemetry plan. Do first.
2. **R4** — trivial once R1 makes pricing a registry; closes an open question in that plan.
3. **R3** — larger Studio feature; worth running through Pathly's own pipeline
   (`/pathly plan studio-usage-dashboard`) once R1–R2 give it clean, cache-aware,
   role-tagged data to render.
