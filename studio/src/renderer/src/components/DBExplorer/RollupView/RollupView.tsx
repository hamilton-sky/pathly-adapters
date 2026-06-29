import { useEffect, useState, useCallback } from 'react'
import { useProjectStore } from '../../../store/projectStore'
import styles from './RollupView.module.css'

const TIERS = ['feature', 'project', 'global'] as const

function fmtCost(n: number): string {
  return `$${n.toFixed(4)}`
}
function shortRoot(p: string): string {
  const parts = p.replace(/\\/g, '/').split('/').filter(Boolean)
  return parts.slice(-2).join('/') || p || '—'
}

function Totals({ totals }: { totals: DbRollupTier }): JSX.Element {
  return (
    <div className={styles.totals}>
      <div className={styles.stat}><span className={styles.statN}>{totals.invocations}</span><span className={styles.statL}>agents</span></div>
      <div className={styles.stat}><span className={styles.statN}>{fmtCost(totals.cost_usd)}</span><span className={styles.statL}>cost</span></div>
      <div className={styles.stat}><span className={styles.statN}>{(totals.tokens_in + totals.tokens_out).toLocaleString()}</span><span className={styles.statL}>tokens</span></div>
    </div>
  )
}

function TierTable({ byTier }: { byTier: DbRollupByTier }): JSX.Element {
  return (
    <table className={styles.table}>
      <thead>
        <tr><th>Scope tier</th><th>Agents</th><th>Cost</th><th>Tokens</th></tr>
      </thead>
      <tbody>
        {TIERS.map((t) => (
          <tr key={t}>
            <td><span className={styles.tier} data-tier={t}>{t}</span></td>
            <td>{byTier[t].invocations}</td>
            <td>{fmtCost(byTier[t].cost_usd)}</td>
            <td>{(byTier[t].tokens_in + byTier[t].tokens_out).toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function RollupView(): JSX.Element {
  const projectPath = useProjectStore((s) => s.projectPath)
  const [rollup, setRollup] = useState<DbRollup | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setRollup(await window.pathly.db.rollup(projectPath || undefined))
    } catch {
      setRollup(null)
    } finally {
      setLoading(false)
    }
  }, [projectPath])

  useEffect(() => {
    load()
  }, [load])

  if (loading) return <div className={styles.loading}>Loading roll-up…</div>
  if (!rollup)
    return (
      <div className={styles.loading}>
        No telemetry yet — run a goal (board/single/loop) to populate the trace tables.
      </div>
    )

  const { project, global } = rollup
  return (
    <div className={styles.wrap}>
      <section className={styles.card}>
        <header className={styles.cardHead}>
          <h3 className={styles.cardTitle}>Project</h3>
          <span className={styles.root} title={project.root}>{shortRoot(project.root)}</span>
        </header>
        <Totals totals={project.totals} />
        <TierTable byTier={project.by_tier} />
      </section>

      <section className={styles.card}>
        <header className={styles.cardHead}>
          <h3 className={styles.cardTitle}>Global</h3>
          <span className={styles.muted}>{global.by_project.length} project(s)</span>
        </header>
        <Totals totals={global.totals} />
        <TierTable byTier={global.by_tier} />
        <ul className={styles.projList}>
          {global.by_project.map((p) => (
            <li key={p.project_root} className={styles.projRow}>
              <span className={styles.projName} title={p.project_root}>{shortRoot(p.project_root)}</span>
              <span className={styles.projCost}>{fmtCost(p.cost_usd)}</span>
              <span className={styles.muted}>{p.invocations} agents</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
