import React from 'react'

interface Step4AgentsProps {
  nonTerminalStates: string[]
  terminalState: string | undefined
  agentMap: Record<string, string>
  onUpdateAgent: (state: string, value: string) => void
  styles: Record<string, React.CSSProperties>
}

export function Step4Agents({
  nonTerminalStates,
  terminalState,
  agentMap,
  onUpdateAgent,
  styles
}: Step4AgentsProps): JSX.Element {
  return (
    <div>
      <div style={styles.stepHeader}>Assign agents</div>
      <div style={styles.stepSub}>Step 4 / 8 — Map agents to non-terminal states</div>
      {nonTerminalStates.filter((s) => s.trim()).map((state) => (
        <div key={state} style={styles.agentRow}>
          <span style={styles.agentStateName}>{state}</span>
          <input
            id={`agent-${state}`}
            style={styles.agentInput}
            type="text"
            placeholder="team/build"
            value={agentMap[state] ?? ''}
            onChange={(e) => onUpdateAgent(state, e.target.value)}
          />
        </div>
      ))}
      {terminalState && terminalState.trim() && (
        <div style={styles.agentRow}>
          <span style={styles.agentStateName}>{terminalState}</span>
          <span style={styles.terminalNote}>— (terminal, no agent)</span>
        </div>
      )}
    </div>
  )
}
