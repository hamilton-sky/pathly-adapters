import { useEffect, useRef } from 'react'
import type { AgentData } from './dbExplorerData'
import styles from './AgentsTab.module.css'

interface AgentsTabProps {
  agents: AgentData[]
}

export function AgentsTab({ agents }: AgentsTabProps): JSX.Element {
  const maxFraction = Math.max(...agents.map((a) => a.costFraction))
  const barRefs = useRef<(HTMLDivElement | null)[]>([])

  useEffect(() => {
    agents.forEach((agent, i) => {
      const el = barRefs.current[i]
      if (el) {
        const pct = maxFraction > 0 ? (agent.costFraction / maxFraction) * 100 : 0
        el.style.setProperty('--bar-w', `${pct}%`)
        el.style.setProperty('--bar-color', agent.stateColor)
      }
    })
  }, [agents, maxFraction])

  return (
    <div>
      <p className={styles.sublabel}>Agent Cost Breakdown</p>
      <div className={styles.agents}>
        {agents.map((agent, i) => (
          <div key={i} className={styles.arow}>
            <span className={styles.aname}>
              {agent.role} <span className={styles.conv}>{agent.conv}</span>
            </span>
            <div
              ref={(el) => { barRefs.current[i] = el }}
              className={styles.abar}
            />
            <span className={styles.acost}>${agent.costFraction.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
