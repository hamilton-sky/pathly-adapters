import { useState } from 'react'
import { AdapterBadge } from '../Monitor/EngineBoard'
import { KindBadge } from './KindBadge/KindBadge'
import { StatusBadge } from './StatusBadge/StatusBadge'
import { StagesTab } from './StagesTab/StagesTab'
import { LogsTab } from './LogsTab/LogsTab'
import { BoardTab } from './BoardTab/BoardTab'
import { CostTab } from './CostTab/CostTab'
import { useRunDetail } from './hooks/useRunDetail'
import { adapterFromProvider } from './runAdapter'
import s from './RunDetailPage.module.css'

type TabId = 'stages' | 'logs' | 'board' | 'cost'

interface Props {
  runId: string
  onBack: () => void
  /** Label for the back button — the entrance's home (default "Monitor"). */
  backLabel?: string
}

const fmtCost = (c: number): string => (c > 0 ? `$${c.toFixed(3)}` : '$0')
const fmtTok = (t: number): string =>
  t >= 1000 ? `${(t / 1000).toFixed(1)}k` : String(t || 0)
const fmtDur = (a: string | null, b: string | null): string => {
  if (!a) return '—'
  const start = Date.parse(a)
  if (Number.isNaN(start)) return '—'
  const secs = Math.max(0, Math.round(((b ? Date.parse(b) : Date.now()) - start) / 1000))
  const m = Math.floor(secs / 60)
  return m > 0 ? `${m}m ${secs % 60}s` : `${secs}s`
}

// Shared full-page run view (unified-control-plane P0e), keyed by run_id, reachable from multiple
// entrances (each holds its own detailRunId + back-target and swaps the panel body). Mirrors
// DBExplorerRedesign's FeatureDetailPage shell: back · header (kind/adapter/status) · big-stats ·
// tab bar · body. Data via useRunDetail → GET /runs/<id>.
export function RunDetailPage({ runId, onBack, backLabel = 'Monitor' }: Props): JSX.Element {
  const [tab, setTab] = useState<TabId>('stages')
  const { detail, loading, notFound, refresh } = useRunDetail(runId)
  const run = detail.run

  if (notFound || (!loading && !run)) {
    return (
      <div className={s.page}>
        <div className={s.top}>
          <button type="button" className={s.back} onClick={onBack}>← {backLabel}</button>
        </div>
        <div className={s.body}>
          <div className={s.empty}>
            This run isn’t in the run history yet — it may still be starting, or it predates run tracking.
          </div>
        </div>
      </div>
    )
  }

  const adapter = run ? adapterFromProvider(run.adapter) : null
  const tabs: { id: TabId; label: string; count?: number }[] = [
    { id: 'stages', label: 'Stages', count: detail.stages.length || undefined },
    { id: 'logs', label: 'Logs', count: detail.logs.length || undefined },
    { id: 'board', label: 'Board', count: detail.board.length || undefined },
    { id: 'cost', label: 'Cost' },
  ]

  return (
    <div className={s.page}>
      <div className={s.top}>
        <button type="button" className={s.back} onClick={onBack}>← {backLabel}</button>
        <div className={s.headRow}>
          <h2 className={s.name}>{run?.feature || runId}</h2>
          {run && <KindBadge kind={run.kind} />}
          {adapter && <AdapterBadge adapter={adapter} />}
          {run && <StatusBadge status={run.status} />}
          <div className={s.spacer} />
          <button type="button" className={s.action} onClick={refresh}>↻ Refresh</button>
        </div>
        <div className={s.runId}>{runId}</div>
      </div>

      <div className={s.bigStats}>
        <BigStat k="Cost" v={run ? fmtCost(run.cost_usd) : '—'} cost />
        <BigStat k="Tokens" v={run ? fmtTok(run.tokens_total) : '—'} />
        <BigStat k="Stages" v={detail.stages.length} />
        <BigStat k="Duration" v={run ? fmtDur(run.started_at, run.finished_at) : '—'} />
      </div>

      <div className={s.tabs}>
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            className={s.tab}
            {...(tab === t.id ? { 'data-active': '' } : {})}
            onClick={() => setTab(t.id)}
          >
            {t.label}
            {t.count !== undefined && <span className={s.count}>{t.count}</span>}
          </button>
        ))}
      </div>

      <div className={s.body}>
        {loading && !run ? (
          <div className={s.empty}>Loading…</div>
        ) : (
          <>
            {tab === 'stages' && <StagesTab stages={detail.stages} onOpenStage={() => setTab('logs')} />}
            {tab === 'logs' && <LogsTab logs={detail.logs} />}
            {tab === 'board' && <BoardTab board={detail.board} artifacts={detail.artifacts} />}
            {tab === 'cost' && <CostTab cost={detail.cost} stages={detail.stages} />}
          </>
        )}
      </div>
    </div>
  )
}

function BigStat({ k, v, cost = false }: { k: string; v: string | number; cost?: boolean }): JSX.Element {
  return (
    <div className={s.bigStat}>
      <div className={s.bsk}>{k}</div>
      <div className={`${s.bsv} ${cost ? s.cost : ''}`}>{v}</div>
    </div>
  )
}
