import { useState, useEffect } from 'react'
import { useProjectStore } from '../../../store/projectStore'
import type { RollupCard, RollupTier } from '../types'
import styles from './RollupView.module.css'

const money = (v: number): string => `$${(v ?? 0).toFixed(2)}`
const num = (v: number): string => (v ?? 0).toLocaleString()

function shortRoot(root: string): string {
  const parts = root.replace(/\\/g, '/').split('/').filter(Boolean)
  return parts.slice(-2).join('/') || root
}

function tierRows(byTier: DbRollupByTier): RollupTier[] {
  return (['feature', 'project', 'global'] as const).map((tier) => {
    const t = byTier[tier]
    return {
      tier,
      agents: t?.invocations ?? 0,
      cost: money(t?.cost_usd ?? 0),
      tokens: num((t?.tokens_in ?? 0) + (t?.tokens_out ?? 0)),
    }
  })
}

function toCards(rollup: DbRollup): RollupCard[] {
  const p = rollup.project
  const g = rollup.global
  const projectCard: RollupCard = {
    title: 'Project',
    sub: shortRoot(p.root),
    totals: [
      { n: num(p.totals.invocations), l: 'agents' },
      { n: money(p.totals.cost_usd), l: 'cost' },
      { n: num(p.totals.tokens_in + p.totals.tokens_out), l: 'tokens' },
    ],
    tiers: tierRows(p.by_tier),
    projects: null,
  }
  const globalCard: RollupCard = {
    title: 'Global',
    sub: `${g.by_project.length} project(s)`,
    totals: [
      { n: num(g.totals.invocations), l: 'agents' },
      { n: money(g.totals.cost_usd), l: 'cost' },
      { n: num(g.totals.tokens_in + g.totals.tokens_out), l: 'tokens' },
    ],
    tiers: tierRows(g.by_tier),
    projects: g.by_project.map((proj) => ({
      name: shortRoot(proj.project_root),
      cost: money(proj.cost_usd),
      agents: `${num(proj.invocations)} agents`,
    })),
  }
  return [projectCard, globalCard]
}

/**
 * Roll-up (Σ) view — feature → project → global cost aggregation. Self-fetches
 * from window.pathly.db.rollup(projectPath) and maps DbRollup → the card shape.
 */
export function RollupView(): JSX.Element {
  const projectPath = useProjectStore((s) => s.projectPath)
  const [cards, setCards] = useState<RollupCard[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    setLoading(true)
    window.pathly.db
      .rollup(projectPath || undefined)
      .then((rollup) => { if (alive) setCards(rollup ? toCards(rollup) : []) })
      .catch(() => { if (alive) setCards([]) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [projectPath])

  if (loading && cards.length === 0) {
    return <div className={styles.wrap}><span className={styles.empty}>Loading roll-up…</span></div>
  }
  if (cards.length === 0) {
    return <div className={styles.wrap}><span className={styles.empty}>No roll-up data yet.</span></div>
  }

  return (
    <div className={styles.wrap}>
      {cards.map((c) => (
        <section key={c.title} className={styles.card}>
          <header className={styles.head}>
            <h3 className={styles.title}>{c.title}</h3>
            <span className={styles.sub}>{c.sub}</span>
          </header>
          <div className={styles.totals}>
            {c.totals.map((t) => (
              <div key={t.l} className={styles.stat}>
                <span className={styles.statN}>{t.n}</span>
                <span className={styles.statL}>{t.l}</span>
              </div>
            ))}
          </div>
          <div className={styles.table}>
            <div className={styles.thead}>
              <span>Scope tier</span>
              <span className={styles.r}>Agents</span>
              <span className={styles.r}>Cost</span>
              <span className={styles.r}>Tokens</span>
            </div>
            {c.tiers.map((t) => (
              <div key={t.tier} className={styles.trow}>
                <span><span className={styles.tier} data-tier={t.tier}>{t.tier}</span></span>
                <span className={styles.r}>{t.agents}</span>
                <span className={styles.r}>{t.cost}</span>
                <span className={styles.r}>{t.tokens}</span>
              </div>
            ))}
          </div>
          {c.projects && (
            <ul className={styles.projList}>
              {c.projects.map((proj) => (
                <li key={proj.name} className={styles.projRow}>
                  <span className={styles.projName}>{proj.name}</span>
                  <span className={styles.projCost}>{proj.cost}</span>
                  <span className={styles.sub}>{proj.agents}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </div>
  )
}
