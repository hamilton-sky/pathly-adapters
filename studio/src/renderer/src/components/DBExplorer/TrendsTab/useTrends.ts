import { useState, useEffect } from 'react'
import type { PricingTable } from '../costUtils'
import { gapFill, buildHeatmap, buildCsvRows } from './trendUtils'

export type DailyCostPoint = {
  date: string
  costReported: number
  costEstimated: number
  hasEstimated: boolean
}

export type HeatmapCell = {
  date: string
  count: number
  level: 0 | 1 | 2 | 3 | 4
}

export type CsvRow = {
  ts: string
  agent: string
  model: string
  provider: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cache_read_tokens: number
  cache_write_tokens: number
  cost_usd: number | null
  cost_source: string
  wall_seconds: number
  feature: string
}

type UseTrendsResult = {
  dailyCost: DailyCostPoint[]
  heatmapCells: HeatmapCell[]
  csvRows: CsvRow[]
  loading: boolean
  error: string | null
}

export function useTrends(
  featureName: string,
  events: DbEvent[],
  pricingTable: PricingTable | null,
): UseTrendsResult {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [buckets, setBuckets] = useState<DailyTrendBucket[]>([])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    window.pathly.db.trends(featureName, 126).then((res) => {
      if (cancelled) return
      const trends = Array.isArray(res?.trends) ? res.trends : []
      setBuckets(trends)
      setLoading(false)
    }).catch(() => {
      if (cancelled) return
      setError('Failed to load trend data')
      setBuckets([])
      setLoading(false)
    })

    return () => { cancelled = true }
  }, [featureName])

  const dailyCost = gapFill(buckets)
  const heatmapCells = buildHeatmap(buckets)
  const csvRows = buildCsvRows(events, featureName, pricingTable)

  return { dailyCost, heatmapCells, csvRows, loading, error }
}
