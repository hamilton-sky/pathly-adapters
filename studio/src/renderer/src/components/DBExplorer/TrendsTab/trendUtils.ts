import { computeCost } from '../costUtils'
import type { PricingTable } from '../costUtils'
import type { DailyCostPoint, HeatmapCell, CsvRow } from './useTrends'

function countToLevel(count: number): 0 | 1 | 2 | 3 | 4 {
  if (count === 0) return 0
  if (count <= 2) return 1
  if (count <= 5) return 2
  if (count <= 9) return 3
  return 4
}

function addDays(dateStr: string, n: number): string {
  const d = new Date(dateStr + 'T00:00:00')
  d.setDate(d.getDate() + n)
  return d.toLocaleDateString('en-CA')
}

type GapFillContext = {
  agentDoneByDate: Map<string, DbEvent[]>
  pricingTable: PricingTable | null
}

export function gapFill(
  buckets: DailyTrendBucket[],
  ctx?: GapFillContext,
): DailyCostPoint[] {
  if (buckets.length === 0) return []

  const byDate = new Map<string, DailyTrendBucket>()
  for (const b of buckets) byDate.set(b.bucket, b)

  const sorted = [...buckets].sort((a, b) => a.bucket.localeCompare(b.bucket))
  const start = sorted[0].bucket
  const end = sorted[sorted.length - 1].bucket

  const result: DailyCostPoint[] = []
  let cur = start
  while (cur <= end) {
    const b = byDate.get(cur)
    if (b) {
      const hasEstimated = b.has_estimated_rows === 1
      let costEstimated = 0
      if (hasEstimated && ctx?.pricingTable) {
        const dayEvents = ctx.agentDoneByDate.get(cur) ?? []
        for (const e of dayEvents) {
          const result = computeCost(
            String(e.payload.model ?? ''),
            Number(e.payload.input_tokens ?? 0),
            Number(e.payload.total_tokens ?? 0) - Number(e.payload.input_tokens ?? 0),
            ctx.pricingTable,
          )
          costEstimated += result.cost ?? 0
        }
      }
      result.push({
        date: cur,
        costReported: b.cost_usd_reported,
        costEstimated,
        hasEstimated,
      })
    } else {
      result.push({ date: cur, costReported: 0, costEstimated: 0, hasEstimated: false })
    }
    cur = addDays(cur, 1)
  }
  return result
}

export function buildHeatmap(buckets: DailyTrendBucket[]): HeatmapCell[] {
  const byDate = new Map<string, number>()
  for (const b of buckets) byDate.set(b.bucket, b.count)

  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const cells: HeatmapCell[] = []

  const startDate = new Date(today)
  startDate.setDate(startDate.getDate() - 125)

  for (let i = 0; i < 126; i++) {
    const d = new Date(startDate)
    d.setDate(d.getDate() + i)
    const dateStr = d.toLocaleDateString('en-CA')
    const count = byDate.get(dateStr) ?? 0
    cells.push({ date: dateStr, count, level: countToLevel(count) })
  }
  return cells
}

export function buildCsvRows(
  events: DbEvent[],
  featureName: string,
  pricingTable: PricingTable | null,
): CsvRow[] {
  return events
    .filter((e) => e.event_type === 'AGENT_DONE')
    .map((e) => {
      const p = e.payload
      const storedCost = Number(p.cost_usd ?? 0)
      let cost_usd: number | null = null
      let cost_source = 'unpriced'

      if (storedCost > 0) {
        cost_usd = storedCost
        cost_source = 'provider_reported'
      } else {
        const result = computeCost(
          String(p.model ?? ''),
          Number(p.tokens_in ?? p.input_tokens ?? 0),
          Number(p.tokens_out ?? p.output_tokens ?? 0),
          pricingTable,
        )
        cost_usd = result.cost
        cost_source = result.source ?? 'unpriced'
      }

      return {
        ts: String(p.ts ?? e.ts ?? ''),
        agent: String(p.agent ?? p.agent_role ?? ''),
        model: String(p.model ?? ''),
        provider: String(p.provider ?? ''),
        input_tokens: Number(p.tokens_in ?? p.input_tokens ?? 0),
        output_tokens: Number(p.tokens_out ?? p.output_tokens ?? 0),
        total_tokens: Number(p.total_tokens ?? 0),
        cache_read_tokens: Number(p.cache_read_tokens ?? 0),
        cache_write_tokens: Number(p.cache_write_tokens ?? 0),
        cost_usd,
        cost_source,
        wall_seconds: Number(p.wall_seconds ?? 0),
        feature: featureName,
      }
    })
}
