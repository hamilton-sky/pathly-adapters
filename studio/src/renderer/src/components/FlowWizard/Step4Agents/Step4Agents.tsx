import React from 'react'
import styles from './Step4Agents.module.css'

interface Step4AgentsProps {
  nonTerminalStates: string[]
  terminalState: string | undefined
  agentMap: Record<string, string>
  onUpdateAgent: (state: string, value: string) => void
}

export function Step4Agents({
  nonTerminalStates,
  terminalState,
  agentMap,
  onUpdateAgent,
}: Step4AgentsProps): JSX.Element {
  return (
    <div className={styles.root}>
      <div className={styles.title}>Assign agents</div>
      <div className={styles.sub}>Step 4 / 5 - Map agents to non-terminal states</div>
      {nonTerminalStates.filter((s) => s.trim()).map((state) => (
        <div key={state} className={styles.row}>
          <span className={styles.name}>{state}</span>
          <input
            id={`agent-${state}`}
            className={styles.input}
            type="text"
            placeholder="team/build"
            value={agentMap[state] ?? ''}
            onChange={(e) => onUpdateAgent(state, e.target.value)}
          />
        </div>
      ))}
      {terminalState && terminalState.trim() && (
        <div className={styles.row}>
          <span className={styles.name}>{terminalState}</span>
          <span className={styles.terminal}>— (terminal, no agent)</span>
        </div>
      )}
    </div>
  )
}
